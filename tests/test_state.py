import pytest
from app.orchestrator.state import PRReviewState, ReviewState, VerifyState


class TestPRReviewState:
    def test_state_values(self):
        assert PRReviewState.RECEIVED == "received"
        assert PRReviewState.SCANNING == "scanning"
        assert PRReviewState.SCAN_COMPLETE == "scan_complete"
        assert PRReviewState.COMPARING == "comparing"
        assert PRReviewState.COMPARE_COMPLETE == "compare_complete"
        assert PRReviewState.PLANNING == "planning"
        assert PRReviewState.PLAN_COMPLETE == "plan_complete"
        assert PRReviewState.VERIFYING == "verifying"
        assert PRReviewState.VERIFY_COMPLETE == "verify_complete"
        assert PRReviewState.COMPLETED == "completed"
        assert PRReviewState.FAILED == "failed"


class TestReviewState:
    def test_review_state_creation(self):
        state: ReviewState = {
            "pr_id": "1024",
            "repo_url": "https://gitlab.com/team/backend",
            "branch": "feature/auth",
            "review_state": "received",
        }
        assert state["pr_id"] == "1024"
        assert state["review_state"] == "received"

    def test_review_state_optional_fields(self):
        state: ReviewState = {
            "pr_id": "1024",
            "review_state": "received",
        }
        assert "scan_report" not in state


class TestVerifyState:
    def test_verify_state_creation(self):
        state: VerifyState = {
            "pr_id": "1024",
            "refactored_files": ["src/auth/login.py"],
            "test_scope": ["unit", "integration"],
            "refactoring_item_id": "DEBT-2024-0312",
        }
        assert state["pr_id"] == "1024"
        assert len(state["refactored_files"]) == 1
