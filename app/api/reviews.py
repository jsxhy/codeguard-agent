from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.database import get_session_factory
from app.models.schemas import CodeReview, AgentExecutionLog
from sqlalchemy import select, desc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])


class ReviewSummary(BaseModel):
    review_id: str = ""
    pr_id: str = ""
    status: str = ""
    total_issues: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    compliance_violations: int = 0
    refactoring_items: int = 0
    test_passed: Optional[bool] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class ReviewDetail(BaseModel):
    review_id: str = ""
    pr_id: str = ""
    repo_url: str = ""
    branch: Optional[str] = None
    status: str = ""
    summary: dict[str, Any] = {}
    reports: dict[str, Any] = {}
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


@router.get("")
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
):
    factory = get_session_factory()
    async with factory() as session:
        stmt = select(CodeReview).order_by(desc(CodeReview.created_at))

        if status:
            stmt = stmt.where(CodeReview.status == status)

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(stmt)
        reviews = result.scalars().all()

        items = []
        for r in reviews:
            scan = r.scan_report or {}
            scan_summary = scan.get("scan_summary", {})
            compliance = r.compliance_report or {}
            compliance_summary = compliance.get("compliance_summary", {})
            refactoring = r.refactoring_plan or {}
            refactoring_plan = refactoring.get("refactoring_plan", {})

            test_result = r.test_result or {}
            test_status = test_result.get("test_result", {}).get("status")

            items.append(ReviewSummary(
                review_id=str(r.id),
                pr_id=r.pr_id,
                status=r.status,
                total_issues=scan_summary.get("issues_found", 0),
                critical=scan_summary.get("critical", 0),
                warning=scan_summary.get("warning", 0),
                info=scan_summary.get("info", 0),
                compliance_violations=compliance_summary.get("violations", 0),
                refactoring_items=refactoring_plan.get("total_items", 0),
                test_passed=test_status == "passed" if test_status else None,
                created_at=r.created_at.isoformat() if r.created_at else None,
            ))

        return {"items": items, "page": page, "page_size": page_size}


@router.get("/{review_id}")
async def get_review(review_id: str):
    factory = get_session_factory()
    async with factory() as session:
        try:
            rid = int(review_id)
        except ValueError:
            stmt = select(CodeReview).where(CodeReview.pr_id == review_id)
        else:
            stmt = select(CodeReview).where(CodeReview.id == rid)

        result = await session.execute(stmt)
        review = result.scalar_one_or_none()

        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        scan = review.scan_report or {}
        scan_summary = scan.get("scan_summary", {})
        compliance = review.compliance_report or {}
        compliance_summary = compliance.get("compliance_summary", {})
        refactoring = review.refactoring_plan or {}
        refactoring_plan = refactoring.get("refactoring_plan", {})

        return ReviewDetail(
            review_id=str(review.id),
            pr_id=review.pr_id,
            repo_url=review.repo_url,
            branch=review.branch,
            status=review.status,
            summary={
                "total_issues": scan_summary.get("issues_found", 0),
                "critical": scan_summary.get("critical", 0),
                "warning": scan_summary.get("warning", 0),
                "info": scan_summary.get("info", 0),
                "compliance_violations": compliance_summary.get("violations", 0),
                "refactoring_items": refactoring_plan.get("total_items", 0),
            },
            reports={
                "scan_report": scan,
                "compliance_report": compliance,
                "refactoring_plan": refactoring,
                "test_result": review.test_result or {},
            },
            created_at=review.created_at.isoformat() if review.created_at else None,
        )


@router.get("/{review_id}/logs")
async def get_review_logs(review_id: int):
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(AgentExecutionLog)
            .where(AgentExecutionLog.review_id == review_id)
            .order_by(AgentExecutionLog.created_at)
        )
        result = await session.execute(stmt)
        logs = result.scalars().all()

        return {
            "items": [
                {
                    "id": log.id,
                    "agent_name": log.agent_name,
                    "status": log.status,
                    "duration_ms": log.duration_ms,
                    "token_consumed": log.token_consumed,
                    "error_message": log.error_message,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ]
        }
