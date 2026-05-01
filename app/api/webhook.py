from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import get_settings
from app.orchestrator.pipeline import run_review_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhook", tags=["webhook"])


def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    settings = get_settings()
    secret = settings.git.webhook_secret
    if not secret:
        return True

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)


@router.post("/pr-event")
async def handle_pr_event(
    request: Request,
    background_tasks: BackgroundTasks,
):
    body = await request.body()

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    event_type = payload.get("event_type", "")
    if not event_type:
        event_type = request.headers.get("X-Gitlab-Event", "")
        if not event_type:
            event_type = request.headers.get("X-GitHub-Event", "")

    supported_events = {
        "merge_request.opened",
        "merge_request.update",
        "pull_request.opened",
        "pull_request.synchronize",
    }

    if event_type not in supported_events:
        return {"status": "ignored", "message": f"Event type '{event_type}' not supported"}

    pr_id = str(payload.get("pr_id", payload.get("merge_request", {}).get("iid", "")))
    repo_url = payload.get("repo_url", "")
    branch = payload.get("branch", payload.get("source_branch", ""))
    base_branch = payload.get("base_branch", payload.get("target_branch", "main"))
    author = payload.get("author", "")
    changed_files = payload.get("changed_files", [])

    if not pr_id or not repo_url:
        raise HTTPException(status_code=400, detail="Missing required fields: pr_id, repo_url")

    review_id = f"REV-{datetime.now().strftime('%Y%m%d')}-{pr_id}"

    pipeline_state = {
        "pr_id": pr_id,
        "repo_url": repo_url,
        "branch": branch,
        "base_branch": base_branch,
        "author": author,
        "changed_files": changed_files,
        "diff_content": "",
        "review_state": "received",
        "review_id": review_id,
        "historical_debt": [],
    }

    background_tasks.add_task(_run_pipeline_background, pipeline_state, review_id)

    return {
        "status": "accepted",
        "review_id": review_id,
        "message": "代码审查任务已提交，预计 3 分钟内完成",
    }


async def _run_pipeline_background(state: dict[str, Any], review_id: str) -> None:
    try:
        logger.info(f"Starting review pipeline for {review_id}")

        git_client = _get_git_client()
        if git_client:
            try:
                diff_data = await git_client.get_pr_diff(
                    state["repo_url"],
                    int(state["pr_id"]),
                    state.get("branch"),
                )
                state["diff_content"] = _format_diff(diff_data.get("changed_files", []))
                if not state["changed_files"]:
                    state["changed_files"] = diff_data.get("changed_files", [])
            except Exception as e:
                logger.warning(f"Failed to fetch PR diff: {e}")

        result = await run_review_pipeline(state)

        await _save_review_result(review_id, result)

        logger.info(f"Review pipeline completed for {review_id}")

    except Exception as e:
        logger.error(f"Review pipeline failed for {review_id}: {e}")
        await _save_review_result(review_id, {
            "review_state": "failed",
            "error": str(e),
        })


def _get_git_client():
    try:
        from app.tools.git_client import GitClient
        return GitClient()
    except Exception:
        return None


def _format_diff(changed_files: list[dict[str, Any]]) -> str:
    parts = []
    for f in changed_files:
        path = f.get("new_path", f.get("path", ""))
        diff = f.get("diff", "")
        if diff:
            parts.append(f"--- {path} ---\n{diff}")
    return "\n\n".join(parts)


async def _save_review_result(review_id: str, result: dict[str, Any]) -> None:
    try:
        from app.models.database import get_session_factory
        from app.models.schemas import CodeReview
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(CodeReview).where(CodeReview.pr_id == result.get("pr_id", ""))
            db_result = await session.execute(stmt)
            existing = db_result.scalar_one_or_none()

            if existing:
                existing.status = result.get("review_state", "completed")
                existing.scan_report = result.get("scan_report")
                existing.compliance_report = result.get("compliance_report")
                existing.refactoring_plan = result.get("refactoring_plan")
                existing.test_result = result.get("test_result")
            else:
                review = CodeReview(
                    pr_id=result.get("pr_id", ""),
                    repo_url=result.get("repo_url", ""),
                    branch=result.get("branch"),
                    status=result.get("review_state", "completed"),
                    scan_report=result.get("scan_report"),
                    compliance_report=result.get("compliance_report"),
                    refactoring_plan=result.get("refactoring_plan"),
                    test_result=result.get("test_result"),
                )
                session.add(review)

            await session.commit()

    except Exception as e:
        logger.error(f"Failed to save review result: {e}")
