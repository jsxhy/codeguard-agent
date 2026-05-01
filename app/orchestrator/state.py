from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from typing_extensions import TypedDict


class PRReviewState(str, Enum):
    RECEIVED = "received"
    SCANNING = "scanning"
    SCAN_COMPLETE = "scan_complete"
    COMPARING = "comparing"
    COMPARE_COMPLETE = "compare_complete"
    PLANNING = "planning"
    PLAN_COMPLETE = "plan_complete"
    VERIFYING = "verifying"
    VERIFY_COMPLETE = "verify_complete"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewState(TypedDict, total=False):
    pr_id: str
    repo_url: str
    branch: str
    base_branch: str
    author: str
    changed_files: list[dict[str, Any]]
    diff_content: str
    review_state: str
    scan_report: dict[str, Any]
    compliance_report: dict[str, Any]
    refactoring_plan: dict[str, Any]
    test_result: dict[str, Any]
    has_refactoring: bool
    historical_debt: list[dict[str, Any]]
    error: Optional[str]
    review_id: str
    refactored_files: list[str]
    refactoring_item_id: str
    test_scope: list[str]
    test_command: str
    coverage_threshold: float
    project_root: Optional[str]
    historical_bug_ids: list[str]


class VerifyState(TypedDict, total=False):
    pr_id: str
    refactored_files: list[str]
    test_scope: list[str]
    refactoring_item_id: str
    test_command: str
    coverage_threshold: float
    project_root: Optional[str]
    historical_bug_ids: list[str]
    test_result: dict[str, Any]
    regression_check: dict[str, Any]
    action_taken: str
