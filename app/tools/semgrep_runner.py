from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SemgrepRunner:
    def __init__(self) -> None:
        self._rules_path = None

    def set_rules_path(self, path: str) -> None:
        self._rules_path = path

    async def scan_file(self, file_path: str, content: str) -> list[dict[str, Any]]:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=Path(file_path).suffix, delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            return await self._run_semgrep(tmp_path, file_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def scan_directory(self, dir_path: str) -> list[dict[str, Any]]:
        return await self._run_semgrep(dir_path)

    async def _run_semgrep(
        self,
        target: str,
        original_path: str = "",
    ) -> list[dict[str, Any]]:
        cmd = ["semgrep", "--json", "--config", "auto"]

        if self._rules_path:
            cmd.extend(["--config", self._rules_path])

        cmd.append(target)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )

            if proc.returncode != 0 and proc.returncode != 1:
                logger.warning(f"Semgrep exit code {proc.returncode}: {stderr.decode()}")
                return []

            result = json.loads(stdout.decode())
            return self._parse_results(result, original_path)

        except asyncio.TimeoutError:
            logger.error("Semgrep scan timed out")
            return []
        except FileNotFoundError:
            logger.warning("Semgrep not installed, skipping static analysis")
            return []
        except Exception as e:
            logger.error(f"Semgrep scan failed: {e}")
            return []

    def _parse_results(
        self,
        result: dict[str, Any],
        original_path: str = "",
    ) -> list[dict[str, Any]]:
        findings = []
        for r in result.get("results", []):
            file_path = r.get("path", "")
            if original_path:
                file_path = original_path

            severity = "info"
            extra = r.get("extra", {})
            sev = extra.get("severity", "INFO")
            if sev == "ERROR":
                severity = "critical"
            elif sev == "WARNING":
                severity = "warning"

            findings.append({
                "file": file_path,
                "line": r.get("start", {}).get("line", 0),
                "severity": severity,
                "category": "security" if extra.get("metadata", {}).get("category") == "security" else "code-smell",
                "rule": r.get("check_id", "unknown"),
                "description": extra.get("message", ""),
                "suggestion": extra.get("fix", "") or extra.get("message", ""),
            })

        return findings

    async def quick_scan(self, file_path: str, content: str) -> list[dict[str, Any]]:
        return await self.scan_file(file_path, content)
