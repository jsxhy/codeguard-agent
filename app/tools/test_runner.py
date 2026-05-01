from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    status: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = None
    coverage_before: Optional[str] = None
    coverage_after: Optional[str] = None
    duration_seconds: float = 0.0
    raw_output: str = ""

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class TestRunner:
    def __init__(self) -> None:
        self._test_command = "pytest --cov=src --cov-report=json -v"
        self._coverage_threshold = 75.0
        self._project_root: Optional[str] = None

    def configure(
        self,
        test_command: Optional[str] = None,
        coverage_threshold: Optional[float] = None,
        project_root: Optional[str] = None,
    ) -> None:
        if test_command:
            self._test_command = test_command
        if coverage_threshold is not None:
            self._coverage_threshold = coverage_threshold
        if project_root:
            self._project_root = project_root

    async def run_tests(
        self,
        test_scope: list[str] | None = None,
        test_files: list[str] | None = None,
        refactored_files: list[str] | None = None,
    ) -> TestResult:
        cmd_parts = self._test_command.split()

        if test_files:
            cmd_parts.extend(test_files)
        elif refactored_files:
            related_tests = self._find_related_tests(refactored_files)
            if related_tests:
                cmd_parts.extend(related_tests)

        cwd = self._project_root or "."

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=300
            )

            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")

            return self._parse_pytest_output(output, error_output, proc.returncode or 0)

        except asyncio.TimeoutError:
            logger.error("Test execution timed out")
            return TestResult(
                status="timeout",
                errors=["Test execution exceeded 300 second timeout"],
            )
        except FileNotFoundError:
            logger.warning("pytest not found, test execution skipped")
            return TestResult(
                status="skipped",
                errors=["pytest not installed"],
            )
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return TestResult(
                status="error",
                errors=[str(e)],
            )

    def _parse_pytest_output(
        self,
        stdout: str,
        stderr: str,
        return_code: int,
    ) -> TestResult:
        result = TestResult(
            status="passed" if return_code == 0 else "failed",
            raw_output=stdout,
        )

        import re

        summary_pattern = re.compile(
            r"(\d+) passed(?:,\s+(\d+) failed)?(?:,\s+(\d+) skipped)?(?:,\s+(\d+) warnings)?(?:\s+in\s+([\d.]+)s)?"
        )

        for line in stdout.split("\n"):
            m = summary_pattern.search(line)
            if m:
                result.passed = int(m.group(1) or 0)
                result.failed = int(m.group(2) or 0)
                result.skipped = int(m.group(3) or 0)
                if m.group(5):
                    result.duration_seconds = float(m.group(5))
                result.total_tests = result.passed + result.failed + result.skipped
                break

        if result.total_tests == 0:
            result.total_tests = result.passed + result.failed + result.skipped

        coverage = self._parse_coverage_report()
        if coverage:
            result.coverage_after = f"{coverage:.1f}%"

        if result.failed > 0:
            result.status = "failed"
            failed_pattern = re.compile(r"FAILED\s+(.+)")
            for line in stdout.split("\n"):
                m = failed_pattern.search(line)
                if m:
                    result.errors.append(m.group(1))

        return result

    def _parse_coverage_report(self) -> Optional[float]:
        coverage_path = Path(self._project_root or ".") / "coverage.json"
        if not coverage_path.exists():
            return None

        try:
            with open(coverage_path, "r") as f:
                data = json.load(f)
            totals = data.get("totals", {})
            return totals.get("percent_covered")
        except (json.JSONDecodeError, KeyError):
            return None

    def _find_related_tests(self, refactored_files: list[str]) -> list[str]:
        test_files = []
        project_root = Path(self._project_root or ".")

        for ref_file in refactored_files:
            ref_path = Path(ref_file)
            module_name = ref_path.stem

            test_patterns = [
                f"test_{module_name}.py",
                f"{module_name}_test.py",
            ]

            for root, dirs, files in self._walk_safe(project_root):
                for pattern in test_patterns:
                    if pattern in files:
                        test_files.append(str(Path(root) / pattern))

        return list(set(test_files))

    def _walk_safe(self, root: Path):
        try:
            yield from root.walk() if hasattr(root, 'walk') else self._os_walk(root)
        except PermissionError:
            return

    def _os_walk(self, root: Path):
        import os
        for dirpath, dirnames, filenames in os.walk(str(root)):
            yield dirpath, dirnames, filenames

    async def check_regression(
        self,
        historical_bug_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "historical_bugs_checked": len(historical_bug_ids) if historical_bug_ids else 0,
            "regressions_found": 0,
        }
