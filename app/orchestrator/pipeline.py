from __future__ import annotations

import logging
from typing import Any, Optional

from langgraph.graph import END, StateGraph

from app.agents.code_scan_agent import CodeScanAgent
from app.agents.refactor_agent import RefactorAgent
from app.agents.standard_compare_agent import StandardCompareAgent
from app.agents.verify_agent import VerifyAgent
from app.orchestrator.state import ReviewState, VerifyState

logger = logging.getLogger(__name__)


_code_scan_agent = CodeScanAgent()
_standard_compare_agent = StandardCompareAgent()
_refactor_agent = RefactorAgent()
_verify_agent = VerifyAgent()


async def code_scan_node(state: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"[Pipeline] Code scan starting for PR {state.get('pr_id')}")
    result = await _code_scan_agent.execute(state)

    if result.get("_status") != "success":
        return {
            "review_state": "failed",
            "error": result.get("error", "Code scan failed"),
        }

    return {
        "review_state": "scan_complete",
        "scan_report": {
            "pr_id": result.get("pr_id"),
            "scan_summary": result.get("scan_summary", {}),
            "issues": result.get("issues", []),
            "code_metrics": result.get("code_metrics", {}),
        },
    }


async def standard_compare_node(state: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"[Pipeline] Standard compare starting for PR {state.get('pr_id')}")
    result = await _standard_compare_agent.execute(state)

    if result.get("_status") != "success":
        return {
            "review_state": "failed",
            "error": result.get("error", "Standard compare failed"),
        }

    return {
        "review_state": "compare_complete",
        "compliance_report": {
            "pr_id": result.get("pr_id"),
            "compliance_summary": result.get("compliance_summary", {}),
            "violations": result.get("violations", []),
        },
    }


async def refactor_suggest_node(state: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"[Pipeline] Refactor suggestion starting for PR {state.get('pr_id')}")
    result = await _refactor_agent.execute(state)

    if result.get("_status") != "success":
        return {
            "review_state": "failed",
            "error": result.get("error", "Refactor suggestion failed"),
        }

    return {
        "review_state": "plan_complete",
        "refactoring_plan": {
            "pr_id": result.get("pr_id"),
            "refactoring_plan": result.get("refactoring_plan", {}),
            "items": result.get("items", []),
            "debt_ledger_update": result.get("debt_ledger_update", {}),
        },
        "has_refactoring": result.get("has_refactoring", False),
    }


async def generate_report_node(state: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"[Pipeline] Generating final report for PR {state.get('pr_id')}")

    scan_report = state.get("scan_report", {})
    compliance_report = state.get("compliance_report", {})
    refactoring_plan = state.get("refactoring_plan", {})

    scan_summary = scan_report.get("scan_summary", {})
    compliance_summary = compliance_report.get("compliance_summary", {})
    refactoring_summary = refactoring_plan.get("refactoring_plan", {})

    final_report = {
        "review_id": state.get("review_id", ""),
        "pr_id": state.get("pr_id", ""),
        "status": "completed",
        "summary": {
            "total_issues": scan_summary.get("issues_found", 0),
            "critical": scan_summary.get("critical", 0),
            "warning": scan_summary.get("warning", 0),
            "info": scan_summary.get("info", 0),
            "compliance_violations": compliance_summary.get("violations", 0),
            "refactoring_items": refactoring_summary.get("total_items", 0),
        },
        "reports": {
            "scan_report": scan_report,
            "compliance_report": compliance_report,
            "refactoring_plan": refactoring_plan,
        },
    }

    return {
        "review_state": "completed",
        "final_report": final_report,
    }


def should_verify(state: dict[str, Any]) -> str:
    if state.get("review_state") == "failed":
        return "generate_report"

    has_refactoring = state.get("has_refactoring", False)
    refactored_files = state.get("refactored_files", [])
    refactoring_item_id = state.get("refactoring_item_id", "")

    if has_refactoring and refactored_files and refactoring_item_id:
        return "verify_close_loop"

    return "generate_report"


def build_review_pipeline() -> StateGraph:
    graph = StateGraph(ReviewState)

    graph.add_node("code_scan", code_scan_node)
    graph.add_node("standard_compare", standard_compare_node)
    graph.add_node("refactor_suggest", refactor_suggest_node)
    graph.add_node("verify_close_loop", verify_close_loop_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("code_scan")

    graph.add_edge("code_scan", "standard_compare")
    graph.add_edge("standard_compare", "refactor_suggest")

    graph.add_conditional_edges(
        "refactor_suggest",
        should_verify,
        {
            "verify_close_loop": "verify_close_loop",
            "generate_report": "generate_report",
        },
    )

    graph.add_edge("verify_close_loop", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


async def verify_close_loop_node(state: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"[Pipeline] Verify close-loop starting for PR {state.get('pr_id')}")
    result = await _verify_agent.execute(state)

    if result.get("_status") != "success":
        return {
            "review_state": "failed",
            "error": result.get("error", "Verify failed"),
        }

    return {
        "review_state": "verify_complete",
        "test_result": result,
    }


def build_verify_pipeline() -> StateGraph:
    graph = StateGraph(VerifyState)

    graph.add_node("verify", verify_close_loop_node)

    graph.set_entry_point("verify")
    graph.add_edge("verify", END)

    return graph.compile()


_review_pipeline = None
_verify_pipeline = None


def get_review_pipeline():
    global _review_pipeline
    if _review_pipeline is None:
        _review_pipeline = build_review_pipeline()
    return _review_pipeline


def get_verify_pipeline():
    global _verify_pipeline
    if _verify_pipeline is None:
        _verify_pipeline = build_verify_pipeline()
    return _verify_pipeline


async def run_review_pipeline(state: dict[str, Any]) -> dict[str, Any]:
    pipeline = get_review_pipeline()
    result = await pipeline.ainvoke(state)
    return result


async def run_verify_pipeline(state: dict[str, Any]) -> dict[str, Any]:
    pipeline = get_verify_pipeline()
    result = await pipeline.ainvoke(state)
    return result
