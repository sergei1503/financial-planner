"""
Portfolio export / import — native full-fidelity JSON.

Serializes a whole portfolio (assets, loans, revenue streams, cash flows, historical
measurements) to a self-contained JSON document, with all foreign keys re-linked by
`external_id` so it round-trips into a fresh portfolio (with new primary keys) in any
database. This is the transport for moving a portfolio between environments (e.g. local
-> Neon) and the backing logic for the export/import API endpoints.

CLI:
    python -m fplan_v2.scripts.portfolio_io export --portfolio-id 1 --out mine.json
    python -m fplan_v2.scripts.portfolio_io import --in mine.json --user-id 1 --name "Imported"

Respects NEON_DATABASE_URL / DATABASE_URL from the environment.
"""

import argparse
import json
import sys
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import inspect as sa_inspect

from fplan_v2.db.connection import get_db_manager
from fplan_v2.db.models import (
    Asset,
    CashFlow,
    HistoricalMeasurement,
    Loan,
    Portfolio,
    RevenueStream,
    User,
)

FORMAT_VERSION = 1

# Columns never carried across databases (identity / ownership / audit).
_SKIP_COLS = {"id", "user_id", "portfolio_id", "created_at", "updated_at"}


def _to_jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _row_to_dict(obj, extra_skip=()):
    skip = _SKIP_COLS | set(extra_skip)
    out = {}
    for attr in sa_inspect(obj).mapper.column_attrs:
        if attr.key in skip:
            continue
        out[attr.key] = _to_jsonable(getattr(obj, attr.key))
    return out


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_portfolio(portfolio_id: int) -> dict:
    db = get_db_manager()
    with db.session() as session:
        portfolio = session.get(Portfolio, portfolio_id)
        if portfolio is None:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        assets = session.query(Asset).filter_by(portfolio_id=portfolio_id).all()
        loans = session.query(Loan).filter_by(portfolio_id=portfolio_id).all()
        streams = session.query(RevenueStream).filter_by(portfolio_id=portfolio_id).all()
        flows = session.query(CashFlow).filter_by(portfolio_id=portfolio_id).all()
        measurements = session.query(HistoricalMeasurement).filter_by(portfolio_id=portfolio_id).all()

        # id -> external_id maps for FK re-linking
        asset_ext = {a.id: a.external_id for a in assets}
        loan_ext = {l.id: l.external_id for l in loans}

        def entity_ext(entity_type, entity_id):
            return (asset_ext if entity_type == "asset" else loan_ext).get(entity_id)

        doc = {
            "format_version": FORMAT_VERSION,
            "portfolio": {"name": portfolio.name},
            "assets": [_row_to_dict(a) for a in assets],
            "loans": [
                {**_row_to_dict(l, extra_skip=("collateral_asset_id",)),
                 "collateral_external_id": asset_ext.get(l.collateral_asset_id)}
                for l in loans
            ],
            "revenue_streams": [
                {**_row_to_dict(s, extra_skip=("asset_id",)),
                 "asset_external_id": asset_ext.get(s.asset_id)}
                for s in streams
            ],
            "cash_flows": [
                {**_row_to_dict(f, extra_skip=("target_asset_id",)),
                 "target_asset_external_id": asset_ext.get(f.target_asset_id)}
                for f in flows
            ],
            "historical_measurements": [
                {**_row_to_dict(m, extra_skip=("entity_id",)),
                 "entity_external_id": entity_ext(m.entity_type, m.entity_id)}
                for m in measurements
            ],
        }
        return doc


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _parse_scalars(d, date_keys=(), decimal_keys=()):
    """Return a shallow copy with date/decimal strings parsed back to types."""
    out = dict(d)
    for k in date_keys:
        if out.get(k) is not None:
            out[k] = date.fromisoformat(out[k])
    for k in decimal_keys:
        if out.get(k) is not None:
            out[k] = Decimal(str(out[k]))
    return out


def import_portfolio(doc: dict, user_id: int, name: str = None, email: str = "sergei@fplan.local") -> int:
    if doc.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"Unsupported export format_version: {doc.get('format_version')}")

    db = get_db_manager()
    db.create_all()
    with db.session() as session:
        user = session.get(User, user_id)
        if user is None:
            user = User(id=user_id, name="Sergei", email=email, auth_provider="clerk")
            session.add(user)
            session.flush()

        portfolio_name = name or doc.get("portfolio", {}).get("name") or "Imported Portfolio"
        is_first = session.query(Portfolio).filter_by(user_id=user.id).count() == 0
        portfolio = Portfolio(user_id=user.id, name=portfolio_name, is_default=is_first)
        session.add(portfolio)
        session.flush()

        common = dict(user_id=user.id, portfolio_id=portfolio.id)
        asset_id_by_ext = {}
        loan_id_by_ext = {}

        for a in doc.get("assets", []):
            row = _parse_scalars(a, date_keys=("start_date", "sell_date"),
                                  decimal_keys=("original_value", "current_value",
                                                "appreciation_rate_annual_pct", "yearly_fee_pct", "sell_tax"))
            asset = Asset(**common, **row)
            session.add(asset)
            session.flush()
            asset_id_by_ext[asset.external_id] = asset.id

        for l in doc.get("loans", []):
            row = _parse_scalars(l, date_keys=("start_date",),
                                 decimal_keys=("original_value", "current_balance", "interest_rate_annual_pct"))
            collateral_ext = row.pop("collateral_external_id", None)
            loan = Loan(**common, **row,
                        collateral_asset_id=asset_id_by_ext.get(collateral_ext))
            session.add(loan)
            session.flush()
            loan_id_by_ext[loan.external_id] = loan.id

        for s in doc.get("revenue_streams", []):
            row = _parse_scalars(s, date_keys=("start_date", "end_date"),
                                 decimal_keys=("amount", "tax_rate", "growth_rate"))
            asset_ext = row.pop("asset_external_id", None)
            session.add(RevenueStream(**common, **row,
                                      asset_id=asset_id_by_ext.get(asset_ext)))

        for f in doc.get("cash_flows", []):
            row = _parse_scalars(f, date_keys=("from_date", "to_date"), decimal_keys=("amount",))
            target_ext = row.pop("target_asset_external_id", None)
            session.add(CashFlow(**common, **row,
                                 target_asset_id=asset_id_by_ext.get(target_ext)))

        for m in doc.get("historical_measurements", []):
            row = _parse_scalars(m, date_keys=("measurement_date",),
                                 decimal_keys=("actual_value", "rate_at_time"))
            ext = row.pop("entity_external_id", None)
            id_map = asset_id_by_ext if row.get("entity_type") == "asset" else loan_id_by_ext
            entity_id = id_map.get(ext)
            if entity_id is None:
                continue  # orphan measurement — skip
            session.add(HistoricalMeasurement(**common, **row, entity_id=entity_id))

        print(f"Imported portfolio id={portfolio.id} ('{portfolio.name}'): "
              f"{len(asset_id_by_ext)} assets, {len(loan_id_by_ext)} loans")
        return portfolio.id


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Export/import a portfolio as native JSON")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export")
    pe.add_argument("--portfolio-id", type=int, required=True)
    pe.add_argument("--out", required=True)

    pi = sub.add_parser("import")
    pi.add_argument("--in", dest="infile", required=True)
    pi.add_argument("--user-id", type=int, required=True)
    pi.add_argument("--name", default=None)

    args = parser.parse_args()
    if args.cmd == "export":
        doc = export_portfolio(args.portfolio_id)
        with open(args.out, "w") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        print(f"Exported portfolio {args.portfolio_id} -> {args.out} "
              f"({len(doc['assets'])} assets, {len(doc['loans'])} loans, "
              f"{len(doc['historical_measurements'])} measurements)")
    elif args.cmd == "import":
        with open(args.infile) as f:
            doc = json.load(f)
        import_portfolio(doc, args.user_id, args.name)


if __name__ == "__main__":
    main()
