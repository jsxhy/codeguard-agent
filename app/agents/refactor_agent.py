from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from app.agents.base import BaseAgent
from app.tools.ast_parser import ASTParser

logger = logging.getLogger(__name__)


class RefactorAgent(BaseAgent):
    name = "refactor_suggest"
    description = "对存量技术债进行分析，生成重构方案"

    def __init__(self) -> None:
        super().__init__()
        self._ast_parser = ASTParser()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        pr_id = state.get("pr_id", "")
        scan_report = state.get("scan_report", {})
        compliance_report = state.get("compliance_report", {})
        historical_debt = state.get("historical_debt", [])

        all_items = self._classify_debt(scan_report, compliance_report)

        refactoring_items = []
        for item in all_items:
            enriched = self._enrich_item(item, state)
            refactoring_items.append(enriched)

        llm_suggestions = await self._generate_llm_suggestions(
            scan_report, compliance_report, historical_debt
        )
        refactoring_items.extend(llm_suggestions)

        refactoring_items = self._sort_by_priority(refactoring_items)

        total_hours = sum(
            item.get("estimated_hours", 0) for item in refactoring_items
        )
        priority_breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for item in refactoring_items:
            p = item.get("priority", "medium")
            priority_breakdown[p] = priority_breakdown.get(p, 0) + 1

        return {
            "pr_id": pr_id,
            "refactoring_plan": {
                "total_items": len(refactoring_items),
                "estimated_effort_hours": round(total_hours, 1),
                "priority_breakdown": priority_breakdown,
            },
            "items": refactoring_items,
            "debt_ledger_update": {
                "new_items_added": len(refactoring_items),
                "existing_items_updated": 0,
                "total_open_debt": len(refactoring_items) + len(historical_debt),
            },
            "has_refactoring": len(refactoring_items) > 0,
        }

    def _classify_debt(
        self,
        scan_report: dict[str, Any],
        compliance_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        items = []

        issues = scan_report.get("issues", [])
        for issue in issues:
            category = issue.get("category", "quality")
            priority = self._severity_to_priority(issue.get("severity", "warning"))

            if category == "security":
                priority = "critical"

            items.append({
                "id": f"DEBT-{datetime.now().strftime('%Y-%m%d')}-{len(items) + 1:04d}",
                "title": f"{issue.get('file', '')}: {issue.get('rule', '')}",
                "priority": priority,
                "category": self._map_category(category),
                "affected_files": [issue.get("file", "")],
                "affected_modules": [],
                "estimated_hours": self._estimate_hours(priority, category),
                "risk_level": self._assess_risk(priority),
                "description": issue.get("description", ""),
                "refactoring_steps": [issue.get("suggestion", "")],
                "code_suggestion": {
                    "before": "",
                    "after": issue.get("suggestion", ""),
                },
                "source_pr_id": scan_report.get("pr_id", ""),
            })

        violations = compliance_report.get("violations", [])
        for violation in violations:
            items.append({
                "id": f"DEBT-{datetime.now().strftime('%Y-%m%d')}-{len(items) + 1:04d}",
                "title": f"{violation.get('file', '')}: {violation.get('rule', '')}",
                "priority": self._severity_to_priority(violation.get("severity", "info")),
                "category": "compliance",
                "affected_files": [violation.get("file", "")],
                "affected_modules": [],
                "estimated_hours": 1.0,
                "risk_level": "low",
                "description": violation.get("description", ""),
                "refactoring_steps": [violation.get("suggestion", "")],
                "code_suggestion": {
                    "before": "",
                    "after": violation.get("suggestion", ""),
                },
                "source_pr_id": compliance_report.get("pr_id", ""),
            })

        return items

    def _enrich_item(
        self, item: dict[str, Any], state: dict[str, Any]
    ) -> dict[str, Any]:
        affected_files = item.get("affected_files", [])
        modules = set()

        for f in affected_files:
            parts = f.replace("\\", "/").split("/")
            if len(parts) > 1:
                modules.add(parts[-2] if parts[-2] != "src" else parts[-1].replace(".py", ""))

        item["affected_modules"] = list(modules)

        priority_score = self._compute_priority_score(item)
        item["_priority_score"] = priority_score

        return item

    def _compute_priority_score(self, item: dict[str, Any]) -> float:
        severity_weights = {"critical": 10, "high": 7, "medium": 4, "low": 1}
        risk_weights = {"high": 3, "medium": 2, "low": 1}

        severity_score = severity_weights.get(item.get("priority", "medium"), 4)
        risk_score = risk_weights.get(item.get("risk_level", "medium"), 2)
        files_score = min(len(item.get("affected_files", [])), 5)
        hours_score = min(item.get("estimated_hours", 1), 10)

        return (
            severity_score * 0.4
            + files_score * 0.3
            + (10 - hours_score) * 0.2
            + risk_score * 0.1
        )

    async def _generate_llm_suggestions(
        self,
        scan_report: dict[str, Any],
        compliance_report: dict[str, Any],
        historical_debt: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        system_prompt = self._load_prompt("refactor_prompt.txt")
        if not system_prompt:
            system_prompt = (
                "你是一名架构师级别的代码重构专家。基于以下代码扫描报告和规范比对报告，"
                "请为每个技术债项生成重构方案。\n\n"
                "要求：\n"
                "1. 对每个问题给出明确的优先级（critical / high / medium / low）\n"
                "2. 分析影响范围（受影响的文件和模块列表）\n"
                "3. 给出具体的重构步骤（按顺序列出）\n"
                "4. 提供重构前后的代码对比示例\n"
                "5. 评估重构风险和预估工作量\n"
                "6. 考虑向后兼容性\n\n"
                "请输出JSON格式的重构建议列表。"
            )

        scan_summary = json.dumps(
            {
                "issues": scan_report.get("issues", [])[:10],
                "metrics": scan_report.get("code_metrics", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
        compliance_summary = json.dumps(
            {
                "violations": compliance_report.get("violations", [])[:10],
            },
            ensure_ascii=False,
            indent=2,
        )

        user_prompt = (
            f"扫描报告：{scan_summary}\n\n"
            f"规范比对报告：{compliance_summary}\n\n"
            f"历史技术债数量：{len(historical_debt)}"
        )

        try:
            result = await self._call_llm(
                system_prompt, user_prompt, output_format="json"
            )
            parsed = json.loads(result)

            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "items" in parsed:
                return parsed["items"]
            return []
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM refactor suggestions parsing failed: {e}")
            return []

    def _sort_by_priority(
        self, items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return sorted(
            items,
            key=lambda x: x.get("_priority_score", 0),
            reverse=True,
        )

    def _severity_to_priority(self, severity: str) -> str:
        mapping = {
            "critical": "critical",
            "error": "critical",
            "warning": "high",
            "warn": "high",
            "info": "medium",
            "informational": "low",
        }
        return mapping.get(severity.lower(), "medium")

    def _map_category(self, category: str) -> str:
        mapping = {
            "security": "security",
            "code-smell": "quality",
            "performance": "quality",
            "maintainability": "quality",
            "architecture": "architecture",
            "compliance": "compliance",
        }
        return mapping.get(category, "quality")

    def _estimate_hours(self, priority: str, category: str) -> float:
        base_hours = {
            "critical": 4.0,
            "high": 2.0,
            "medium": 1.0,
            "low": 0.5,
        }
        category_multiplier = {
            "security": 1.5,
            "architecture": 2.0,
            "quality": 1.0,
            "compliance": 0.8,
        }
        base = base_hours.get(priority, 1.0)
        multiplier = category_multiplier.get(category, 1.0)
        return round(base * multiplier, 1)

    def _assess_risk(self, priority: str) -> str:
        if priority in ("critical", "high"):
            return "medium"
        return "low"
