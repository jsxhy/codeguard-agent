import pytest
from app.agents.code_scan_agent import CodeScanAgent
from app.agents.standard_compare_agent import StandardCompareAgent
from app.agents.refactor_agent import RefactorAgent
from app.agents.verify_agent import VerifyAgent


class TestCodeScanAgent:
    def setup_method(self):
        self.agent = CodeScanAgent()

    def test_agent_name(self):
        assert self.agent.name == "code_scan"

    def test_detect_security_issues(self):
        code = """
API_KEY = 'sk-1234567890abcdef'
password = 'hardcoded_password_123'
"""
        issues = self.agent._detect_security_issues("config.py", code)
        assert len(issues) > 0
        assert any(i["rule"] == "hardcoded-secret" for i in issues)

    def test_detect_sql_injection(self):
        code = """
query = "SELECT * FROM users WHERE id=" + user_id
"""
        issues = self.agent._detect_security_issues("db.py", code)
        assert len(issues) > 0

    def test_detect_duplication(self):
        code = """
def func_a():
    x = 1
    y = 2
    z = 3
    w = 4
    return x + y + z + w

def func_b():
    x = 1
    y = 2
    z = 3
    w = 4
    return x + y + z + w
"""
        issues = self.agent._detect_duplication("test.py", code)
        assert len(issues) > 0

    def test_build_summary(self):
        issues = [
            {"severity": "critical"},
            {"severity": "warning"},
            {"severity": "warning"},
            {"severity": "info"},
        ]
        summary = self.agent._build_summary(issues)
        assert summary["issues_found"] == 4
        assert summary["critical"] == 1
        assert summary["warning"] == 2
        assert summary["info"] == 1


class TestStandardCompareAgent:
    def setup_method(self):
        self.agent = StandardCompareAgent()

    def test_agent_name(self):
        assert self.agent.name == "standard_compare"

    def test_check_naming_convention_camel_case(self):
        from app.tools.ast_parser import ASTParser
        parser = ASTParser()
        code = """
def getUsrInfo():
    pass
"""
        ast_result = parser.parse_file("test.py", code)
        violations = self.agent._check_naming_convention("test.py", ast_result)
        assert len(violations) > 0
        assert violations[0]["rule"] == "naming-convention"

    def test_check_dependencies_forbidden(self):
        from app.tools.ast_parser import ASTParser
        parser = ASTParser()
        code = """
import pickle
import marshal
"""
        ast_result = parser.parse_file("test.py", code)
        violations = self.agent._check_dependencies("test.py", ast_result)
        assert len(violations) > 0
        assert any(v["rule"] == "forbidden-dependency" for v in violations)


class TestRefactorAgent:
    def setup_method(self):
        self.agent = RefactorAgent()

    def test_agent_name(self):
        assert self.agent.name == "refactor_suggest"

    def test_severity_to_priority(self):
        assert self.agent._severity_to_priority("critical") == "critical"
        assert self.agent._severity_to_priority("warning") == "high"
        assert self.agent._severity_to_priority("info") == "medium"

    def test_map_category(self):
        assert self.agent._map_category("security") == "security"
        assert self.agent._map_category("code-smell") == "quality"
        assert self.agent._map_category("architecture") == "architecture"

    def test_estimate_hours(self):
        critical_hours = self.agent._estimate_hours("critical", "security")
        assert critical_hours > 0
        low_hours = self.agent._estimate_hours("low", "compliance")
        assert low_hours < critical_hours

    def test_sort_by_priority(self):
        items = [
            {"_priority_score": 3, "title": "low"},
            {"_priority_score": 8, "title": "high"},
            {"_priority_score": 5, "title": "medium"},
        ]
        sorted_items = self.agent._sort_by_priority(items)
        assert sorted_items[0]["title"] == "high"
        assert sorted_items[-1]["title"] == "low"


class TestVerifyAgent:
    def setup_method(self):
        self.agent = VerifyAgent()

    def test_agent_name(self):
        assert self.agent.name == "verify"

    def test_determine_action_passed(self):
        from app.tools.test_runner import TestResult
        result = TestResult(status="passed", total_tests=10, passed=10, failed=0, skipped=0)
        action = self.agent._determine_action(result, {"regressions_found": 0}, "DEBT-001")
        assert "已标记为已修复" in action

    def test_determine_action_failed(self):
        from app.tools.test_runner import TestResult
        result = TestResult(status="failed", total_tests=10, passed=8, failed=2, skipped=0)
        action = self.agent._determine_action(result, {"regressions_found": 0}, "DEBT-001")
        assert "未通过" in action
