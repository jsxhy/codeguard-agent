from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class FunctionInfo:
    name: str
    start_line: int
    end_line: int
    parameters: list[str] = field(default_factory=list)
    return_type: Optional[str] = None
    calls: list[str] = field(default_factory=list)
    complexity: int = 1


@dataclass
class ClassInfo:
    name: str
    start_line: int
    end_line: int
    methods: list[FunctionInfo] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)


@dataclass
class ImportInfo:
    module: str
    names: list[str] = field(default_factory=list)
    line: int = 0
    is_from: bool = False


@dataclass
class FileAST:
    file_path: str
    language: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)


_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".rb": "ruby",
}


def _detect_language(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    return _LANGUAGE_MAP.get(suffix, "unknown")


class ASTParser:
    def __init__(self) -> None:
        self._tree_sitter_available = False
        try:
            import tree_sitter  # noqa: F401
            self._tree_sitter_available = True
        except ImportError:
            logger.warning("tree-sitter not installed, using fallback parser")

    def parse_file(self, file_path: str, content: str) -> FileAST:
        language = _detect_language(file_path)

        if self._tree_sitter_available and language != "unknown":
            try:
                return self._parse_with_tree_sitter(file_path, content, language)
            except Exception as e:
                logger.warning(f"Tree-sitter parsing failed for {file_path}: {e}")

        return self._fallback_parse(file_path, content, language)

    def _parse_with_tree_sitter(
        self, file_path: str, content: str, language: str
    ) -> FileAST:
        import tree_sitter

        lang_map = {
            "python": "python",
            "javascript": "javascript",
            "typescript": "typescript",
            "java": "java",
            "go": "go",
            "rust": "rust",
            "cpp": "cpp",
            "c": "c",
            "ruby": "ruby",
        }

        ts_lang_name = lang_map.get(language)
        if not ts_lang_name:
            return self._fallback_parse(file_path, content, language)

        try:
            lang_module = __import__(f"tree_sitter_{ts_lang_name}", fromlist=["language"])
            ts_language = tree_sitter.Language(lang_module.language())
        except ImportError:
            return self._fallback_parse(file_path, content, language)

        parser = tree_sitter.Parser(ts_language)
        tree = parser.parse(content.encode("utf-8"))

        result = FileAST(file_path=file_path, language=language)
        self._walk_tree(tree.root_node, result)
        return result

    def _walk_tree(self, node: Any, result: FileAST) -> None:
        if node.type == "function_definition":
            func = self._extract_function(node)
            if func:
                result.functions.append(func)
        elif node.type == "class_definition":
            cls = self._extract_class(node)
            if cls:
                result.classes.append(cls)
        elif node.type in ("import_statement", "import_from_statement"):
            imp = self._extract_import(node)
            if imp:
                result.imports.append(imp)

        for child in node.children:
            self._walk_tree(child, result)

    def _extract_function(self, node: Any) -> Optional[FunctionInfo]:
        name = ""
        for child in node.children:
            if child.type == "identifier":
                name = child.text.decode("utf-8")
                break

        params = []
        for child in node.children:
            if child.type == "parameters":
                for param in child.children:
                    if param.type == "identifier":
                        params.append(param.text.decode("utf-8"))
                    elif param.type == "typed_parameter":
                        for pc in param.children:
                            if pc.type == "identifier":
                                params.append(pc.text.decode("utf-8"))
                                break

        calls = []
        self._find_calls(node, calls)

        return FunctionInfo(
            name=name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            parameters=params,
            calls=calls,
            complexity=self._estimate_complexity(node),
        )

    def _extract_class(self, node: Any) -> Optional[ClassInfo]:
        name = ""
        bases: list[str] = []
        methods: list[FunctionInfo] = []

        for child in node.children:
            if child.type == "identifier":
                name = child.text.decode("utf-8")
            elif child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(arg.text.decode("utf-8"))
            elif child.type == "function_definition":
                method = self._extract_function(child)
                if method:
                    methods.append(method)

        return ClassInfo(
            name=name,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            methods=methods,
            bases=bases,
        )

    def _extract_import(self, node: Any) -> Optional[ImportInfo]:
        text = node.text.decode("utf-8")
        is_from = text.startswith("from ")
        line = node.start_point[0] + 1

        if is_from:
            parts = text.replace("from ", "").split(" import ")
            module = parts[0].strip()
            names = [n.strip() for n in parts[1].split(",")] if len(parts) > 1 else []
        else:
            module = text.replace("import ", "").strip()
            names = []

        return ImportInfo(module=module, names=names, line=line, is_from=is_from)

    def _find_calls(self, node: Any, calls: list[str]) -> None:
        if node.type == "call":
            for child in node.children:
                if child.type == "identifier":
                    calls.append(child.text.decode("utf-8"))
                    break
                elif child.type == "attribute":
                    calls.append(child.text.decode("utf-8"))
                    break

        for child in node.children:
            self._find_calls(child, calls)

    def _estimate_complexity(self, node: Any) -> int:
        decision_types = {
            "if_statement", "elif_clause", "for_statement",
            "while_statement", "except_clause", "with_statement",
            "boolean_operator", "ternary_expression",
        }
        complexity_ref = [1]
        self._count_decision_points(node, decision_types, complexity_ref)
        return complexity_ref[0]

    def _count_decision_points(
        self, node: Any, decision_types: set, complexity_ref: list[int]
    ) -> None:
        if node.type in decision_types:
            complexity_ref[0] += 1
        for child in node.children:
            self._count_decision_points(child, decision_types, complexity_ref)

    def _fallback_parse(
        self, file_path: str, content: str, language: str
    ) -> FileAST:
        result = FileAST(file_path=file_path, language=language)
        lines = content.split("\n")

        if language == "python":
            self._parse_python_simple(lines, result)

        return result

    def _parse_python_simple(self, lines: list[str], result: FileAST) -> None:
        import re

        func_pattern = re.compile(r"^\s*def\s+(\w+)\s*\((.*?)\)")
        class_pattern = re.compile(r"^\s*class\s+(\w+)")
        import_pattern = re.compile(r"^\s*import\s+(\S+)")
        from_pattern = re.compile(r"^\s*from\s+(\S+)\s+import\s+(.+)")

        current_class: Optional[ClassInfo] = None
        current_func: Optional[FunctionInfo] = None
        func_indent = 0

        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()

            m = from_pattern.match(stripped)
            if m:
                result.imports.append(ImportInfo(
                    module=m.group(1),
                    names=[n.strip() for n in m.group(2).split(",")],
                    line=i,
                    is_from=True,
                ))
                continue

            m = import_pattern.match(stripped)
            if m:
                result.imports.append(ImportInfo(
                    module=m.group(1),
                    line=i,
                    is_from=False,
                ))
                continue

            m = class_pattern.match(stripped)
            if m:
                if current_class:
                    result.classes.append(current_class)
                current_class = ClassInfo(
                    name=m.group(1),
                    start_line=i,
                    end_line=i,
                )
                continue

            m = func_pattern.match(stripped)
            if m:
                if current_func:
                    current_func.end_line = i - 1
                    if current_class and func_indent <= len(stripped) - len(stripped.lstrip()):
                        current_class.methods.append(current_func)
                    else:
                        result.functions.append(current_func)
                        if current_class:
                            result.classes.append(current_class)
                            current_class = None

                indent = len(stripped) - len(stripped.lstrip())
                params = [p.strip().split(":")[0].split("=")[0].strip()
                          for p in m.group(2).split(",") if p.strip()]
                current_func = FunctionInfo(
                    name=m.group(1),
                    start_line=i,
                    end_line=i,
                    parameters=params,
                )
                func_indent = indent
                continue

        if current_func:
            current_func.end_line = len(lines)
            if current_class:
                current_class.methods.append(current_func)
            else:
                result.functions.append(current_func)

        if current_class:
            current_class.end_line = len(lines)
            result.classes.append(current_class)

    def get_call_graph(self, file_ast: FileAST) -> dict[str, list[str]]:
        graph: dict[str, list[str]] = {}
        for func in file_ast.functions:
            graph[func.name] = func.calls
        for cls in file_ast.classes:
            for method in cls.methods:
                graph[f"{cls.name}.{method.name}"] = method.calls
        return graph

    def check_layer_violation(
        self,
        file_ast: FileAST,
        layer_rules: dict[str, list[str]],
    ) -> list[dict[str, Any]]:
        violations = []
        for imp in file_ast.imports:
            for allowed_prefix, forbidden_patterns in layer_rules.items():
                for pattern in forbidden_patterns:
                    if pattern in imp.module:
                        violations.append({
                            "file": file_ast.file_path,
                            "line": imp.line,
                            "rule": "layer-violation",
                            "severity": "warning",
                            "description": (
                                f"模块 {imp.module} 违反分层架构规范，"
                                f"当前层不应直接依赖 {pattern}"
                            ),
                            "imported_module": imp.module,
                        })
        return violations
