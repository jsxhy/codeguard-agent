from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.base import BaseAgent
from app.models.vector_store import VectorStore
from app.tools.ast_parser import ASTParser

logger = logging.getLogger(__name__)


class StandardCompareAgent(BaseAgent):
    name = "standard_compare"
    description = "将代码与团队架构规范、编码规范进行一致性检查"

    def __init__(self) -> None:
        super().__init__()
        self._vector_store = VectorStore()
        self._ast_parser = ASTParser()

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        pr_id = state.get("pr_id", "")
        changed_files = state.get("changed_files", [])
        scan_report = state.get("scan_report", {})

        all_violations: list[dict[str, Any]] = []
        total_checks = 0
        passed = 0

        for file_info in changed_files:
            file_path = file_info.get("path", file_info.get("new_path", ""))
            content = file_info.get("content", "")

            if not content:
                continue

            ast_result = self._ast_parser.parse_file(file_path, content)

            naming_violations = self._check_naming_convention(file_path, ast_result)
            total_checks += len(naming_violations) + 1
            passed += 1 - len(naming_violations) if not naming_violations else 0
            all_violations.extend(naming_violations)

            layer_violations = self._check_layer_violation(file_path, ast_result)
            total_checks += len(layer_violations) + 1
            passed += 1 - len(layer_violations) if not layer_violations else 0
            all_violations.extend(layer_violations)

            api_violations = self._check_api_convention(file_path, content)
            total_checks += len(api_violations) + 1
            passed += 1 - len(api_violations) if not api_violations else 0
            all_violations.extend(api_violations)

            dependency_violations = self._check_dependencies(file_path, ast_result)
            total_checks += len(dependency_violations) + 1
            passed += 1 - len(dependency_violations) if not dependency_violations else 0
            all_violations.extend(dependency_violations)

        standard_violations = await self._check_with_standards(
            changed_files, scan_report
        )
        all_violations.extend(standard_violations)
        total_checks += len(standard_violations) + len(standard_violations)

        if all_violations:
            passed = total_checks - len(all_violations)

        return {
            "pr_id": pr_id,
            "compliance_summary": {
                "total_checks": total_checks,
                "passed": max(passed, 0),
                "violations": len(all_violations),
            },
            "violations": all_violations,
        }

    def _check_naming_convention(
        self, file_path: str, ast_result: Any
    ) -> list[dict[str, Any]]:
        violations = []
        import re

        for func in ast_result.functions:
            if re.search(r"[A-Z]", func.name) and not func.name.startswith("_"):
                violations.append({
                    "file": file_path,
                    "line": func.start_line,
                    "rule": "naming-convention",
                    "severity": "info",
                    "description": f"函数名 {func.name} 未使用 snake_case 命名",
                    "reference": "团队编码规范 - 命名规范",
                    "suggestion": f"重命名为 {re.sub(r'([A-Z])', r'_\1', func.name).lower().lstrip('_')}",
                })

            for param in func.parameters:
                if re.search(r"[A-Z]", param) and not param.startswith("_"):
                    violations.append({
                        "file": file_path,
                        "line": func.start_line,
                        "rule": "naming-convention",
                        "severity": "info",
                        "description": f"参数名 {param} 未使用 snake_case 命名",
                        "reference": "团队编码规范 - 命名规范",
                        "suggestion": f"重命名为 {re.sub(r'([A-Z])', r'_\1', param).lower().lstrip('_')}",
                    })

        for cls in ast_result.classes:
            if not re.match(r"^[A-Z]", cls.name):
                violations.append({
                    "file": file_path,
                    "line": cls.start_line,
                    "rule": "naming-convention",
                    "severity": "info",
                    "description": f"类名 {cls.name} 未使用 PascalCase 命名",
                    "reference": "团队编码规范 - 命名规范",
                    "suggestion": f"重命名为 {cls.name[0].upper()}{cls.name[1:]}",
                })

        return violations

    def _check_layer_violation(
        self, file_path: str, ast_result: Any
    ) -> list[dict[str, Any]]:
        layer_rules = {
            "repository": ["controller", "api", "handler"],
            "model": ["controller", "api", "handler"],
            "dao": ["controller", "service"],
        }

        violations = self._ast_parser.check_layer_violation(ast_result, layer_rules)

        for v in violations:
            v["reference"] = "《后端架构规范》分层依赖规则"
            v["suggestion"] = "通过 Service 层进行间接调用"

        return violations

    def _check_api_convention(
        self, file_path: str, content: str
    ) -> list[dict[str, Any]]:
        violations = []
        import re

        if "controller" in file_path.lower() or "api" in file_path.lower() or "router" in file_path.lower():
            route_pattern = re.compile(
                r'@(?:app|router)\.(?:get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
                re.IGNORECASE,
            )
            for match in route_pattern.finditer(content):
                path = match.group(1)
                if re.search(r"[A-Z]", path):
                    violations.append({
                        "file": file_path,
                        "line": content[: match.start()].count("\n") + 1,
                        "rule": "api-convention",
                        "severity": "info",
                        "description": f"API 路径 {path} 包含大写字母，不符合 RESTful 规范",
                        "reference": "《API 设计规范》路径命名",
                        "suggestion": f"使用小写路径: {path.lower()}",
                    })

                if "//" in path:
                    violations.append({
                        "file": file_path,
                        "line": content[: match.start()].count("\n") + 1,
                        "rule": "api-convention",
                        "severity": "warning",
                        "description": f"API 路径 {path} 包含双斜杠",
                        "reference": "《API 设计规范》路径格式",
                        "suggestion": "移除多余的斜杠",
                    })

        return violations

    def _check_dependencies(
        self, file_path: str, ast_result: Any
    ) -> list[dict[str, Any]]:
        violations = []
        forbidden_packages = {"pickle", "marshal", "subprocess", "eval", "exec"}

        for imp in ast_result.imports:
            if imp.module in forbidden_packages:
                violations.append({
                    "file": file_path,
                    "line": imp.line,
                    "rule": "forbidden-dependency",
                    "severity": "warning",
                    "description": f"使用了禁止的模块: {imp.module}",
                    "reference": "《依赖管理规范》禁止使用库列表",
                    "suggestion": f"寻找 {imp.module} 的安全替代方案",
                })

        return violations

    async def _check_with_standards(
        self,
        changed_files: list[dict[str, Any]],
        scan_report: dict[str, Any],
    ) -> list[dict[str, Any]]:
        violations = []

        try:
            from langchain_openai import OpenAIEmbeddings
            from app.config import get_settings

            settings = get_settings()
            embeddings_model = OpenAIEmbeddings(
                model=settings.vector_db.embedding_model,
                api_key=settings.llm.api_key,
                base_url=settings.llm.api_base,
            )

            for file_info in changed_files:
                file_path = file_info.get("path", file_info.get("new_path", ""))
                content = file_info.get("content", "")

                if not content:
                    continue

                query_text = content[:1000]
                query_embedding = await embeddings_model.aembed_query(query_text)

                results = self._vector_store.search_standards(
                    query_embedding=query_embedding,
                    top_k=3,
                )

                for result in results:
                    if result.get("distance", 1.0) < 0.25:
                        metadata = result.get("metadata", {})
                        violations.append({
                            "file": file_path,
                            "line": 0,
                            "rule": "standard-violation",
                            "severity": "warning",
                            "description": f"代码与规范文档《{metadata.get('doc_name', '')}》"
                                           f"第 {metadata.get('section', '')} 节存在偏差",
                            "reference": f"《{metadata.get('doc_name', '')}》"
                                         f"第 {metadata.get('section', '')} 节",
                            "suggestion": "请参照规范文档调整代码实现",
                        })

        except Exception as e:
            logger.warning(f"Vector-based standard comparison failed: {e}")

        return violations
