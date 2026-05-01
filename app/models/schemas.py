from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.database import Base


class CodeReview(Base):
    __tablename__ = "code_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pr_id: Mapped[str] = mapped_column(String(64), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(512), nullable=False)
    branch: Mapped[Optional[str]] = mapped_column(String(128))
    base_branch: Mapped[Optional[str]] = mapped_column(String(128))
    author: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    scan_report: Mapped[Optional[dict]] = mapped_column(JSONB)
    compliance_report: Mapped[Optional[dict]] = mapped_column(JSONB)
    refactoring_plan: Mapped[Optional[dict]] = mapped_column(JSONB)
    test_result: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class TechDebtLedger(Base):
    __tablename__ = "tech_debt_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    debt_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64))
    priority: Mapped[Optional[str]] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default="open")
    affected_files: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    affected_modules: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    estimated_hours: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    actual_hours: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[Optional[str]] = mapped_column(String(16))
    description: Mapped[Optional[str]] = mapped_column(Text)
    refactoring_steps: Mapped[Optional[dict]] = mapped_column(JSONB)
    code_suggestion: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_pr_id: Mapped[Optional[str]] = mapped_column(String(64))
    resolved_pr_id: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class StandardDocument(Base):
    __tablename__ = "standard_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_name: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AgentExecutionLog(Base):
    __tablename__ = "agent_execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    token_consumed: Mapped[Optional[int]] = mapped_column(Integer)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(32))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
