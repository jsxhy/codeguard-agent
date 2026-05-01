from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.database import get_session_factory
from app.models.schemas import TechDebtLedger
from sqlalchemy import select, desc, func, case

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/debt", tags=["debt"])


class DebtItem(BaseModel):
    id: int
    debt_id: str
    title: str
    category: Optional[str] = None
    priority: Optional[str] = None
    status: str = "open"
    affected_files: Optional[list[str]] = None
    affected_modules: Optional[list[str]] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    risk_level: Optional[str] = None
    description: Optional[str] = None
    refactoring_steps: Optional[list[str]] = None
    code_suggestion: Optional[dict[str, Any]] = None
    source_pr_id: Optional[str] = None
    resolved_pr_id: Optional[str] = None
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None


class DebtUpdateRequest(BaseModel):
    status: Optional[str] = None
    actual_hours: Optional[float] = None
    resolved_pr_id: Optional[str] = None


class DebtStatistics(BaseModel):
    total_open: int = 0
    by_priority: dict[str, int] = {}
    by_category: dict[str, int] = {}
    trend: dict[str, int] = {}
    estimated_remaining_hours: float = 0.0


@router.get("")
async def list_debt(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
):
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(TechDebtLedger).order_by(desc(TechDebtLedger.created_at))

        if status:
            stmt = stmt.where(TechDebtLedger.status == status)
        if category:
            stmt = stmt.where(TechDebtLedger.category == category)
        if priority:
            stmt = stmt.where(TechDebtLedger.priority == priority)

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        items = result.scalars().all()

        return {
            "items": [_debt_to_dict(item) for item in items],
            "page": page,
            "page_size": page_size,
        }


@router.get("/statistics")
async def get_debt_statistics():
    factory = get_session_factory()
    async with factory() as session:
        total_open_stmt = select(func.count()).where(TechDebtLedger.status == "open")
        total_open = (await session.execute(total_open_stmt)).scalar() or 0

        priority_stmt = (
            select(TechDebtLedger.priority, func.count())
            .where(TechDebtLedger.status == "open")
            .group_by(TechDebtLedger.priority)
        )
        priority_result = await session.execute(priority_stmt)
        by_priority = {row[0] or "unclassified": row[1] for row in priority_result}

        category_stmt = (
            select(TechDebtLedger.category, func.count())
            .where(TechDebtLedger.status == "open")
            .group_by(TechDebtLedger.category)
        )
        category_result = await session.execute(category_stmt)
        by_category = {row[0] or "unclassified": row[1] for row in category_result}

        week_ago = datetime.now() - timedelta(days=7)
        new_this_week_stmt = select(func.count()).where(
            TechDebtLedger.created_at >= week_ago
        )
        new_this_week = (await session.execute(new_this_week_stmt)).scalar() or 0

        resolved_this_week_stmt = select(func.count()).where(
            TechDebtLedger.resolved_at >= week_ago,
            TechDebtLedger.status == "resolved",
        )
        resolved_this_week = (await session.execute(resolved_this_week_stmt)).scalar() or 0

        remaining_hours_stmt = select(func.sum(TechDebtLedger.estimated_hours)).where(
            TechDebtLedger.status == "open"
        )
        remaining_hours = (await session.execute(remaining_hours_stmt)).scalar() or 0.0

        return DebtStatistics(
            total_open=total_open,
            by_priority=by_priority,
            by_category=by_category,
            trend={
                "this_week_new": new_this_week,
                "this_week_resolved": resolved_this_week,
                "net_change": new_this_week - resolved_this_week,
            },
            estimated_remaining_hours=float(remaining_hours),
        )


@router.get("/{debt_id}")
async def get_debt(debt_id: str):
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(TechDebtLedger).where(TechDebtLedger.debt_id == debt_id)
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(status_code=404, detail="Debt item not found")

        return _debt_to_dict(item)


@router.patch("/{debt_id}")
async def update_debt(debt_id: str, update: DebtUpdateRequest):
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(TechDebtLedger).where(TechDebtLedger.debt_id == debt_id)
        result = await session.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(status_code=404, detail="Debt item not found")

        if update.status is not None:
            valid_statuses = {"open", "in_progress", "resolved", "wontfix"}
            if update.status not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {valid_statuses}",
                )
            item.status = update.status

            if update.status == "resolved":
                item.resolved_at = datetime.now()

        if update.actual_hours is not None:
            item.actual_hours = update.actual_hours

        if update.resolved_pr_id is not None:
            item.resolved_pr_id = update.resolved_pr_id

        await session.commit()
        await session.refresh(item)

        return _debt_to_dict(item)


def _debt_to_dict(item: TechDebtLedger) -> dict[str, Any]:
    return {
        "id": item.id,
        "debt_id": item.debt_id,
        "title": item.title,
        "category": item.category,
        "priority": item.priority,
        "status": item.status,
        "affected_files": item.affected_files,
        "affected_modules": item.affected_modules,
        "estimated_hours": float(item.estimated_hours) if item.estimated_hours else None,
        "actual_hours": float(item.actual_hours) if item.actual_hours else None,
        "risk_level": item.risk_level,
        "description": item.description,
        "refactoring_steps": item.refactoring_steps,
        "code_suggestion": item.code_suggestion,
        "source_pr_id": item.source_pr_id,
        "resolved_pr_id": item.resolved_pr_id,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
    }
