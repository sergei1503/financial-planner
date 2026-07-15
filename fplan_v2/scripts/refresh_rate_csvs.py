"""
Refresh the interest-rate / CPI CSVs the projection engine reads
(`data/prime_interest_rates.csv`, `data/cpi_interest_rates.csv`).

WHY: `LoanPrimePegged` / `LoanCPIPegged` project future loan payments off these series. Beyond
the last row the tracker holds the value flat, so the series should be topped up when the Bank of
Israel changes its rate or the CBS publishes a new CPI month.

DATA SOURCES (fetch the numbers with `/grok_research` or the web-researcher, then feed them here):
  - Prime CSV actually stores the **Bank of Israel BASE rate** (prime = base + 1.5%; the loan model
    uses the *delta* so base vs prime doesn't matter as long as it's consistent). Source: Bank of
    Israel monetary-committee decisions — https://www.boi.org.il/en/economic-roles/monetary-policy/
    Format rows: `start,end,rate` (DD/MM/YYYY). The current row has an empty `end` (open-ended);
    when a new decision lands, close that row's `end` and append a new open row.
  - CPI: CBS "Consumer Price Index – General", series id 120010, base = Average 2024 = 100.
    Source/API: https://api.cbs.gov.il/index/data/price?format=json&id=120010&lang=en
    Format rows: `date,cpi,change,change_percent` (date = MM/YY). change/%change vs the prior month.

Grok query that works (verified 2026-07-15):
  "As of <today>: current BoI base rate + Israeli prime; every 2026 BoI decision (date + rate);
   latest CBS CPI index level + MoM% per 2026 month; state base year; flag if the newest month
   isn't published yet. Exact numbers, cite BoI/CBS URLs, do not invent."

USAGE (idempotent — skips a row that's already present):
  # close the current open prime row at <effective-1day> and add the new BoI base rate:
  python -m fplan_v2.scripts.refresh_rate_csvs prime --effective DD/MM/YYYY --rate 3.5
  # append a CPI month (index level; change/%change computed from the previous row):
  python -m fplan_v2.scripts.refresh_rate_csvs cpi --month MM/YY --index 104.9
  # just show the tail of both + the sources:
  python -m fplan_v2.scripts.refresh_rate_csvs status
"""

import argparse
import csv
import os
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRIME = os.path.join(BASE, "data", "prime_interest_rates.csv")
CPI = os.path.join(BASE, "data", "cpi_interest_rates.csv")


def _rows(path):
    with open(path, newline="") as f:
        return list(csv.reader(f))


def _write(path, rows):
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def add_prime(effective: str, rate: float):
    """Close the current open row the day before `effective`, append a new open row at `effective`."""
    rows = _rows(PRIME)
    eff = datetime.strptime(effective, "%d/%m/%Y")
    if any(r[0] == effective and r[2] == str(rate) for r in rows[1:]):
        print(f"prime: {effective} @ {rate} already present — nothing to do")
        return
    last = rows[-1]
    if last[1] == "":  # open-ended -> close it the day before the new effective date
        last[1] = (eff - timedelta(days=1)).strftime("%d/%m/%Y")
    rows.append([effective, "", str(rate)])
    _write(PRIME, rows)
    print(f"prime: closed prior row at {last[1]}, appended {effective},,{rate}")


def add_cpi(month: str, index: float):
    """Append a CPI month; compute change + change_percent from the previous row."""
    rows = _rows(CPI)
    if any(r[0] == month for r in rows[1:]):
        print(f"cpi: {month} already present — nothing to do")
        return
    prev = float(rows[-1][1])
    change = index - prev
    change_pct = (change / prev * 100) if prev else 0.0
    rows.append([month, str(index), str(change), str(change_pct)])
    _write(CPI, rows)
    print(f"cpi: appended {month},{index} (change {change:+.2f}, {change_pct:+.4f}%)")


def status():
    print("PRIME (BoI base rate) — last 4 rows:")
    for r in _rows(PRIME)[-4:]:
        print("  ", ",".join(r))
    print("CPI (CBS, base Avg-2024=100) — last 4 rows:")
    for r in _rows(CPI)[-4:]:
        print("  ", ",".join(r))
    print("\nFetch fresh numbers via /grok_research or web-researcher (see module docstring), "
          "then re-run with `prime`/`cpi`.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prime"); p.add_argument("--effective", required=True); p.add_argument("--rate", type=float, required=True)
    c = sub.add_parser("cpi"); c.add_argument("--month", required=True); c.add_argument("--index", type=float, required=True)
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "prime":
        add_prime(a.effective, a.rate)
    elif a.cmd == "cpi":
        add_cpi(a.month, a.index)
    else:
        status()
