from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.base import BaseAgent
from app.tools.test_runner import TestRunner

logger = logging.getLogger(__name__)


class VerifyAgent(BaseAgent):
    name = "verify"
    description = "在重构 PR 提交后自动触发测试，验证改动未引入回归问题"

    def __init__(self) -> None:
        super().__init__()
        self._test_runner = TestRunner()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        pr_id = state.get("pr_id", "")
        refactored_files = state.get("refactored_files", [])
        test_scope = state.get("test_scope", ["unit", "integration"])
        refactoring_item_id = state.get("refactoring_item_id", "")

        self._test_runner.configure(
            test_command=state.get("test_command", "pytest --cov=src --cov-report=json -v"),
            coverage_threshold=state.get("coverage_threshold", 75.0),
            project_root=state.get("project_root"),
        )

        test_result = await self._test_runner.run_tests(
            test_scope=test_scope,
            refactored_files=refactored_files,
        )

        regression_check = await self._test_runner.check_regression(
            state.get("historical_bug_ids")
        )

        action_taken = self._determine_action(test_result, regression_check, refactoring_item_id)

        result = {
            "pr_id": pr_id,
            "refactoring_item_id": refactoring_item_id,
            "test_result": {
                "status": test_result.status,
                "total_tests": test_result.total_tests,
                "passed": test_result.passed,
                "failed": test_result.failed,
                "skipped": test_result.skipped,
                "coverage_before": test_result.coverage_before,
                "coverage_after": test_result.coverage_after,
                "duration_seconds": test_result.duration_seconds,
            },
            "regression_check": regression_check,
            "action_taken": action_taken,
        }

        if test_result.status == "failed" and test_result.errors:
            result["failure_analysis"] = await self._analyze_failures(test_result.errors)

        return result

    def _determine_action(
        self,
        test_result: Any,
        regression_check: dict[str, Any],
        refactoring_item_id: str,
    ) -> str:
        if test_result.status == "passed":
            if regression_check.get("regressions_found", 0) == 0:
                return f"技术债 {refactoring_item_id} 已标记为已修复，PR 可合并"
            return f"技术债 {refactoring_item_id} 测试通过但存在回归风险，需人工确认"

        if test_result.status == "failed":
            return f"技术债 {refactoring_item_id} 测试未通过，需修复后重新验证"

        if test_result.status == "timeout":
            return f"技术债 {refactoring_item_id} 测试超时，需检查测试配置"

        return f"技术债 {refactoring_item_id} 验证状态: {test_result.status}"

    async def _analyze_failures(self, errors: list[str]) -> dict[str, Any]:
        if not errors:
            return {"analysis": "无失败详情", "suggestions": []}

        error_text = "\n".join(errors[:5])

        system_prompt = self._load_prompt("verify_prompt.txt")
        if not system_prompt:
            system_prompt = (
                "你是一名测试工程师。请分析以下测试失败原因，"
                "判断是否与重构相关，并给出修复建议。\n"
                "请输出JSON格式，包含 analysis 和 suggestions 字段。"
            )

        user_prompt = f"测试失败信息：\n{error_text[:4000]}"

        try:
            result = await self._call_llm(
                system_prompt, user_prompt, output_format="json"
            )
            return json.loads(result)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failure analysis parsing failed: {e}")
            return {
                "analysis": "自动分析失败，需人工检查",
                "suggestions": errors[:3],
            }
