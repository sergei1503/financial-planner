"""
SQLAlchemy ORM models for FPlan v2 PostgreSQL schema.

These models provide type-safe database access and support for:
- Connection pooling with Neon/PgBouncer
- JSONB queries and indexing
- Foreign key relationships
- Automatic timestamp management
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ======================
# Core Tables
# ======================


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    email = Column(Text, unique=True)
    clerk_id = Column(Text, unique=True, index=True, nullable=True)
    auth_provider = Column(Text, default="clerk")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    settings = Column(JSONB, server_default="{}")
    is_active = Column(Boolean, default=True)
    portfolio_version = Column(Integer, default=1, nullable=False)

    # Relationships
    assets = relationship("Asset", back_populates="user", cascade="all, delete-orphan")
    loans = relationship("Loan", back_populates="user", cascade="all, delete-orphan")
    revenue_streams = relationship("RevenueStream", back_populates="user", cascade="all, delete-orphan")
    cash_flows = relationship("CashFlow", back_populates="user", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(Text, nullable=False)
    asset_type = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    original_value = Column(Numeric(15, 2), nullable=False)
    current_value = Column(Numeric(15, 2))
    appreciation_rate_annual_pct = Column(Numeric(5, 2), default=0)
    yearly_fee_pct = Column(Numeric(5, 2), default=0)
    sell_date = Column(Date)
    sell_tax = Column(Numeric(5, 2), default=0)
    currency = Column(Text, default="ILS")
    config_json = Column(JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="assets")
    loans = relationship("Loan", back_populates="collateral_asset")
    revenue_streams = relationship("RevenueStream", back_populates="asset", cascade="all, delete-orphan")
    cash_flows = relationship("CashFlow", back_populates="target_asset", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_asset_user_external_id"),
        CheckConstraint(
            "asset_type IN ('real_estate', 'stock', 'pension', 'cash')",
            name="ck_asset_type",
        ),
        Index("idx_assets_user_id", "user_id"),
        Index("idx_assets_external_id", "user_id", "external_id"),
        Index("idx_assets_type", "asset_type"),
        Index("idx_assets_start_date", "start_date"),
        Index("idx_assets_config_json", "config_json", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<Asset(id={self.id}, name='{self.name}', type='{self.asset_type}', value={self.current_value})>"


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(Text, nullable=False)
    loan_type = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    original_value = Column(Numeric(15, 2), nullable=False)
    current_balance = Column(Numeric(15, 2))
    interest_rate_annual_pct = Column(Numeric(5, 2), nullable=False)
    duration_months = Column(Integer, nullable=False)
    collateral_asset_id = Column(Integer, ForeignKey("assets.id", ondelete="SET NULL"))
    config_json = Column(JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="loans")
    collateral_asset = relationship("Asset", back_populates="loans")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_loan_user_external_id"),
        CheckConstraint(
            "loan_type IN ('fixed', 'prime_pegged', 'cpi_pegged', 'variable')",
            name="ck_loan_type",
        ),
        CheckConstraint("duration_months > 0", name="ck_loan_duration"),
        Index("idx_loans_user_id", "user_id"),
        Index("idx_loans_external_id", "user_id", "external_id"),
        Index("idx_loans_type", "loan_type"),
        Index("idx_loans_collateral", "collateral_asset_id"),
        Index("idx_loans_config_json", "config_json", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<Loan(id={self.id}, name='{self.name}', type='{self.loan_type}', balance={self.current_balance})>"


class RevenueStream(Base):
    __tablename__ = "revenue_streams"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"))
    stream_type = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    amount = Column(Numeric(15, 2), nullable=False)
    period = Column(Text, default="monthly")
    tax_rate = Column(Numeric(5, 2), default=0)
    growth_rate = Column(Numeric(5, 2), default=0)
    config_json = Column(JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="revenue_streams")
    asset = relationship("Asset", back_populates="revenue_streams")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "stream_type IN ('rent', 'dividend', 'pension', 'salary')",
            name="ck_revenue_stream_type",
        ),
        CheckConstraint(
            "period IN ('monthly', 'quarterly', 'yearly')",
            name="ck_revenue_stream_period",
        ),
        Index("idx_revenue_streams_user_id", "user_id"),
        Index("idx_revenue_streams_asset_id", "asset_id"),
        Index("idx_revenue_streams_type", "stream_type"),
        Index("idx_revenue_streams_dates", "start_date", "end_date"),
    )

    def __repr__(self):
        return f"<RevenueStream(id={self.id}, name='{self.name}', type='{self.stream_type}', amount={self.amount})>"


class CashFlow(Base):
    __tablename__ = "cash_flows"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    flow_type = Column(Text, nullable=False)
    target_asset_id = Column(Integer, ForeignKey("assets.id", ondelete="CASCADE"))
    name = Column(Text, nullable=False)
    amount = Column(Numeric(15, 2), nullable=False)
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    from_own_capital = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", back_populates="cash_flows")
    target_asset = relationship("Asset", back_populates="cash_flows")

    # Constraints
    __table_args__ = (
        CheckConstraint("flow_type IN ('deposit', 'withdrawal')", name="ck_cash_flow_type"),
        CheckConstraint("from_date <= to_date", name="ck_cash_flow_dates"),
        Index("idx_cash_flows_user_id", "user_id"),
        Index("idx_cash_flows_asset_id", "target_asset_id"),
        Index("idx_cash_flows_type", "flow_type"),
        Index("idx_cash_flows_dates", "from_date", "to_date"),
    )

    def __repr__(self):
        return f"<CashFlow(id={self.id}, type='{self.flow_type}', amount={self.amount})>"


# ======================
# Historical Tracking
# ======================


class HistoricalMeasurement(Base):
    __tablename__ = "historical_measurements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(Integer, nullable=False)
    measurement_date = Column(Date, nullable=False)
    actual_value = Column(Numeric(15, 2), nullable=False)
    rate_at_time = Column(Numeric(5, 2))
    notes = Column(Text)
    source = Column(Text, default="manual")
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "measurement_date", name="uq_measurement_entity_date"),
        CheckConstraint("entity_type IN ('asset', 'loan')", name="ck_measurement_entity_type"),
        CheckConstraint("source IN ('manual', 'import', 'auto')", name="ck_measurement_source"),
        Index("idx_measurements_user_id", "user_id"),
        Index("idx_measurements_entity", "entity_type", "entity_id"),
        Index("idx_measurements_date", "measurement_date"),
        Index("idx_measurements_recorded_at", "recorded_at"),
    )

    def __repr__(self):
        return f"<HistoricalMeasurement(id={self.id}, entity={self.entity_type}:{self.entity_id}, value={self.actual_value})>"


# ======================
# Projection Caching
# ======================


class ProjectionCache(Base):
    __tablename__ = "projection_cache"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    cache_key = Column(Text, nullable=False)
    result_json = Column(JSONB, nullable=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "cache_key", name="uq_projection_cache_user_key"),
        Index("idx_projection_cache_user", "user_id"),
    )

    def __repr__(self):
        return f"<ProjectionCache(id={self.id}, user_id={self.user_id}, cache_key='{self.cache_key[:16]}...')>"


# ======================
# Audit Trail
# ======================


class OperationLog(Base):
    __tablename__ = "operations_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    operation_type = Column(Text, nullable=False)
    entity_type = Column(Text)
    entity_id = Column(Integer)
    parameters = Column(JSONB, nullable=False)
    description = Column(Text)
    source = Column(Text, default="ui")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint("source IN ('ui', 'nlp', 'import', 'api', 'scenario')", name="ck_operation_source"),
        Index("idx_operations_log_user_id", "user_id"),
        Index("idx_operations_log_type", "operation_type"),
        Index("idx_operations_log_entity", "entity_type", "entity_id"),
        Index("idx_operations_log_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index("idx_operations_log_parameters", "parameters", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<OperationLog(id={self.id}, type='{self.operation_type}', source='{self.source}')>"


# ======================
# Index Data
# ======================


class IndexData(Base):
    __tablename__ = "index_data"

    id = Column(Integer, primary_key=True)
    index_type = Column(Text, nullable=False)
    date = Column(Date, nullable=False)
    value = Column(Numeric(10, 4), nullable=False)
    change = Column(Numeric(10, 4))
    change_percent = Column(Numeric(10, 4))
    source_url = Column(Text)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    # Constraints
    __table_args__ = (
        UniqueConstraint("index_type", "date", name="uq_index_type_date"),
        CheckConstraint("index_type IN ('prime', 'cpi')", name="ck_index_type"),
        Index("idx_index_data_type", "index_type"),
        Index("idx_index_data_date", "date", postgresql_ops={"date": "DESC"}),
        Index("idx_index_data_fetched_at", "fetched_at"),
    )

    def __repr__(self):
        return f"<IndexData(id={self.id}, type='{self.index_type}', date={self.date}, value={self.value})>"


class IndexNotification(Base):
    __tablename__ = "index_notifications"

    id = Column(Integer, primary_key=True)
    index_type = Column(Text, nullable=False)
    change_date = Column(Date, nullable=False)
    old_value = Column(Numeric(10, 4))
    new_value = Column(Numeric(10, 4))
    change_percent = Column(Numeric(10, 4))
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Constraints
    __table_args__ = (
        CheckConstraint("index_type IN ('prime', 'cpi')", name="ck_notification_index_type"),
        Index("idx_index_notifications_type", "index_type"),
        Index("idx_index_notifications_acknowledged", "acknowledged"),
        Index("idx_index_notifications_created_at", "created_at", postgresql_ops={"created_at": "DESC"}),
    )

    def __repr__(self):
        return f"<IndexNotification(id={self.id}, type='{self.index_type}', change={self.change_percent}%)>"


# ======================
# Scenarios
# ======================


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    version = Column(Integer, nullable=False, default=1)
    parent_version = Column(Integer)
    actions_json = Column(JSONB, nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="scenarios")
    results = relationship("ScenarioResult", back_populates="scenario", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "name", "version", name="uq_scenario_user_name_version"),
        CheckConstraint("version > 0", name="ck_scenario_version"),
        Index("idx_scenarios_user_id", "user_id"),
        Index("idx_scenarios_name", "user_id", "name"),
        Index("idx_scenarios_active", "is_active"),
        Index("idx_scenarios_actions", "actions_json", postgresql_using="gin"),
    )

    def __repr__(self):
        return f"<Scenario(id={self.id}, name='{self.name}', version={self.version}, active={self.is_active})>"


class ScenarioResult(Base):
    __tablename__ = "scenario_results"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False)
    result_type = Column(Text, nullable=False)
    result_data = Column(JSONB, nullable=False)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())
    config_hash = Column(Text)

    # Relationships
    scenario = relationship("Scenario", back_populates="results")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "result_type IN ('net_worth', 'cash_flow', 'asset_projection', 'loan_schedule')",
            name="ck_result_type",
        ),
        Index("idx_scenario_results_scenario_id", "scenario_id"),
        Index("idx_scenario_results_type", "result_type"),
        Index("idx_scenario_results_computed_at", "computed_at", postgresql_ops={"computed_at": "DESC"}),
        Index("idx_scenario_results_hash", "config_hash"),
    )

    def __repr__(self):
        return f"<ScenarioResult(id={self.id}, scenario_id={self.scenario_id}, type='{self.result_type}')>"
