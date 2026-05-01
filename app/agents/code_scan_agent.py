from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.base import BaseAgent
from app.tools.semgrep_runner import SemgrepRunner
from app.tools.ast_parser import ASTParser

logger = logging.getLogger(__name__)


class CodeScanAgent(BaseAgent):
    name = "code_scan"
    description = "对 PR 代码变更进行多维度静态分析"

    def __init__(self) -> None:
        super().__init__()
        self._semgrep = SemgrepRunner()
        self._ast_parser = ASTParser()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        pr_id = state.get("pr_id", "")
        changed_files = state.get("changed_files", [])
        diff_content = state.get("diff_content", "")

        all_issues: list[dict[str, Any]] = []
        all_metrics: dict[str, Any] = {
            "cyclomatic_complexity": {"avg": 0, "max": 0, "max_location": ""},
            "duplication_rate": "0%",
            "test_coverage_delta": "0%",
        }

        for file_info in changed_files:
            file_path = file_info.get("path", file_info.get("new_path", ""))
            content = file_info.get("content", "")
            diff = file_info.get("diff", "")

            if not content and diff:
                content = diff

            if not content:
                continue

            ast_result = self._ast_parser.parse_file(file_path, content)

            semgrep_issues = await self._semgrep.quick_scan(file_path, content)
            all_issues.extend(semgrep_issues)

            ast_issues = self._analyze_ast(file_path, ast_result)
            all_issues.extend(ast_issues)

            security_issues = self._detect_security_issues(file_path, content)
            all_issues.extend(security_issues)

            complexity_metrics = self._compute_complexity(file_path, ast_result)
            self._merge_metrics(all_metrics, complexity_metrics)

            duplication_issues = self._detect_duplication(file_path, content)
            all_issues.extend(duplication_issues)

        llm_issues = await self._llm_scan(diff_content, changed_files)
        all_issues.extend(llm_issues)

        summary = self._build_summary(all_issues)

        return {
            "pr_id": pr_id,
            "scan_summary": summary,
            "issues": all_issues,
            "code_metrics": all_metrics,
        }

    def _analyze_ast(
        self, file_path: str, ast_result: Any
    ) -> list[dict[str, Any]]:
        issues = []

        for func in ast_result.functions:
            if func.end_line - func.start_line > 50:
                issues.append({
                    "file": file_path,
                    "line": func.start_line,
                    "severity": "warning",
                    "category": "code-smell",
                    "rule": "long-function",
                    "description": f"函数 {func.name} 超过 50 行，建议拆分",
                    "suggestion": f"将 {func.name}() 拆分为多个职责单一的子函数",
                })

            if func.complexity > 10:
                issues.append({
                    "file": file_path,
                    "line": func.start_line,
                    "severity": "warning" if func.complexity <= 15 else "critical",
                    "category": "code-smell",
                    "rule": "high-complexity",
                    "description": f"函数 {func.name} 圈复杂度为 {func.complexity}，超过阈值 10",
                    "suggestion": f"建议拆分 {func.name}()，降低圈复杂度",
                })

            if len(func.parameters) > 5:
                issues.append({
                    "file": file_path,
                    "line": func.start_line,
                    "severity": "info",
                    "category": "code-smell",
                    "rule": "too-many-params",
                    "description": f"函数 {func.name} 参数数量为 {len(func.parameters)}，超过 5 个",
                    "suggestion": "考虑使用参数对象或 Builder 模式减少参数数量",
                })

        for cls in ast_result.classes:
            if len(cls.methods) > 15:
                issues.append({
                    "file": file_path,
                    "line": cls.start_line,
                    "severity": "warning",
                    "category": "code-smell",
                    "rule": "large-class",
                    "description": f"类 {cls.name} 包含 {len(cls.methods)} 个方法，建议拆分",
                    "suggestion": "考虑按职责拆分为多个类",
                })

        return issues

    def _detect_security_issues(
        self, file_path: str, content: str
    ) -> list[dict[str, Any]]:
        issues = []
        lines = content.split("\n")

        import re

        secret_patterns = [
            (r"(?:api_key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]", "hardcoded-secret"),
            (r"(?:SELECT|INSERT|UPDATE|DELETE).*\+\s*(?:f['\"]|['\"].*format|%s)", "sql-injection-risk"),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, rule in secret_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    severity = "critical" if rule == "hardcoded-secret" else "warning"
                    suggestion_map = {
                        "hardcoded-secret": "将密钥迁移至环境变量或密钥管理服务",
                        "sql-injection-risk": "使用参数化查询替代字符串拼接",
                    }
                    issues.append({
                        "file": file_path,
                        "line": i,
                        "severity": severity,
                        "category": "security",
                        "rule": rule,
                        "description": f"检测到潜在安全问题: {rule}",
                        "suggestion": suggestion_map.get(rule, ""),
                    })

        return issues

    def _detect_duplication(
        self, file_path: str, content: str
    ) -> list[dict[str, Any]]:
        issues = []
        lines = content.split("\n")
        seen_blocks: dict[str, int] = {}

        block_size = 6
        for i in range(len(lines) - block_size + 1):
            block = "\n".join(lines[i : i + block_size]).strip()
            if len(block) < 30:
                continue
            if block in seen_blocks:
                issues.append({
                    "file": file_path,
                    "line": i + 1,
                    "severity": "info",
                    "category": "code-smell",
                    "rule": "duplicate-code",
                    "description": f"检测到重复代码块，与第 {seen_blocks[block]} 行相似",
                    "suggestion": "提取公共方法消除重复代码",
                })
            else:
                seen_blocks[block] = i + 1

        return issues

    def _compute_complexity(
        self, file_path: str, ast_result: Any
    ) -> dict[str, Any]:
        complexities = []
        max_complexity = 0
        max_location = ""

        for func in ast_result.functions:
            complexities.append(func.complexity)
            if func.complexity > max_complexity:
                max_complexity = func.complexity
                max_location = f"{file_path}:{func.start_line}"

        for cls in ast_result.classes:
            for method in cls.methods:
                complexities.append(method.complexity)
                if method.complexity > max_complexity:
                    max_complexity = method.complexity
                    max_location = f"{file_path}:{method.start_line}"

        avg = sum(complexities) / len(complexities) if complexities else 0

        return {
            "cyclomatic_complexity": {
                "avg": round(avg, 1),
                "max": max_complexity,
                "max_location": max_location,
            },
        }

    def _merge_metrics(self, target: dict, source: dict) -> None:
        if "cyclomatic_complexity" in source:
            sc = source["cyclomatic_complexity"]
            tc = target["cyclomatic_complexity"]
            all_avgs = [tc.get("avg", 0), sc.get("avg", 0)]
            tc["avg"] = round(sum(all_avgs) / len(all_avgs), 1) if all_avgs else 0
            if sc.get("max", 0) > tc.get("max", 0):
                tc["max"] = sc["max"]
                tc["max_location"] = sc.get("max_location", "")

    async def _llm_scan(
        self,
        diff_content: str,
        changed_files: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not diff_content:
            file_summaries = []
            for f in changed_files:
                path = f.get("path", f.get("new_path", ""))
                content = f.get("content", f.get("diff", ""))
                if content:
                    file_summaries.append(f"--- {path} ---\n{content[:2000]}")
            diff_content = "\n\n".join(file_summaries)

        if not diff_content:
            return []

        system_prompt = self._load_prompt("scan_prompt.txt")
        if not system_prompt:
            system_prompt = (
                "你是一名资深代码审查专家。请对以下代码变更进行审查，重点关注：\n"
                "1. 安全漏洞（SQL注入、XSS、硬编码密钥、权限绕过）\n"
                "2. 代码异味（过长函数、过大类、重复代码、魔法数字）\n"
                "3. 性能问题（N+1查询、不必要的循环、内存泄漏风险）\n"
                "4. 可维护性（命名规范、注释缺失、耦合度过高）\n\n"
                "对于每个发现的问题，请输出JSON数组，每个元素包含：\n"
                "- file: 文件路径\n"
                "- line: 行号\n"
                "- severity: critical/warning/info\n"
                "- category: security/code-smell/performance/maintainability\n"
                "- rule: 规则标识\n"
                "- description: 问题描述\n"
                "- suggestion: 修复建议\n"
            )

        user_prompt = f"代码变更内容：\n{diff_content[:8000]}"

        try:
            result = await self._call_llm(system_prompt, user_prompt, output_format="json")
            parsed = json.loads(result)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "issues" in parsed:
                return parsed["issues"]
            return []
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM scan result parsing failed: {e}")
            return []

    def _build_summary(self, issues: list[dict[str, Any]]) -> dict[str, Any]:
        critical = sum(1 for i in issues if i.get("severity") == "critical")
        warning = sum(1 for i in issues if i.get("severity") == "warning")
        info = sum(1 for i in issues if i.get("severity") == "info")

        return {
            "total_files": 0,
            "issues_found": len(issues),
            "critical": critical,
            "warning": warning,
            "info": info,
        }
