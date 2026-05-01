import pytest
import json
from app.tools.ast_parser import ASTParser, _detect_language


class TestASTParser:
    def setup_method(self):
        self.parser = ASTParser()

    def test_detect_language_python(self):
        assert _detect_language("main.py") == "python"

    def test_detect_language_javascript(self):
        assert _detect_language("app.js") == "javascript"

    def test_detect_language_typescript(self):
        assert _detect_language("app.ts") == "typescript"

    def test_detect_language_java(self):
        assert _detect_language("Main.java") == "java"

    def test_detect_language_unknown(self):
        assert _detect_language("file.xyz") == "unknown"

    def test_parse_python_simple_function(self):
        code = """
def hello(name):
    print(f"Hello {name}")
    return True
"""
        result = self.parser.parse_file("test.py", code)
        assert result.language == "python"
        assert len(result.functions) >= 1
        assert result.functions[0].name == "hello"
        assert "name" in result.functions[0].parameters

    def test_parse_python_class(self):
        code = """
class UserService:
    def get_user(self, user_id):
        return user_id

    def create_user(self, name):
        return name
"""
        result = self.parser.parse_file("service.py", code)
        assert len(result.classes) >= 1
        assert result.classes[0].name == "UserService"

    def test_parse_python_imports(self):
        code = """
import os
from typing import List, Optional
from fastapi import FastAPI
"""
        result = self.parser.parse_file("test.py", code)
        assert len(result.imports) >= 2

    def test_get_call_graph(self):
        code = """
def main():
    hello()

def hello():
    print("hi")
"""
        result = self.parser.parse_file("test.py", code)
        graph = self.parser.get_call_graph(result)
        assert "main" in graph
        assert "hello" in graph["main"]

    def test_check_layer_violation(self):
        code = """
from controller.user_controller import UserController

class UserRepository:
    def find(self, id):
        pass
"""
        result = self.parser.parse_file("repo.py", code)
        violations = self.parser.check_layer_violation(
            result,
            {"repository": ["controller"]},
        )
        assert len(violations) > 0
        assert violations[0]["rule"] == "layer-violation"

    def test_parse_empty_file(self):
        result = self.parser.parse_file("empty.py", "")
        assert result.language == "python"
        assert len(result.functions) == 0

    def test_parse_complex_function(self):
        code = """
def complex_func(x, y, z, a, b, c):
    if x > 0:
        for i in range(y):
            if z:
                while a:
                    pass
    return x
"""
        result = self.parser.parse_file("test.py", code)
        assert len(result.functions) >= 1
        assert result.functions[0].name == "complex_func"
        assert len(result.functions[0].parameters) == 6
