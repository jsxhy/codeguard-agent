from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import get_settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = ""

    def __init__(self) -> None:
        settings = get_settings()
        self._llm = ChatOpenAI(
            model=settings.llm.model,
            api_key=settings.llm.api_key,
            base_url=settings.llm.api_base,
            max_tokens=settings.llm.max_tokens,
            temperature=settings.llm.temperature,
        )
        self._timeout = 120
        self._max_retries = settings.llm.retry_max_attempts
        self._retry_backoff = settings.llm.retry_backoff_seconds

    @abstractmethod
    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        ...

    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        output_format: str = "json",
    ) -> str:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        last_error = None
        for attempt in range(self._max_retries):
            try:
                response = await asyncio.wait_for(
                    self._llm.ainvoke(messages),
                    timeout=self._timeout,
                )
                content = response.content

                if output_format == "json":
                    content = self._extract_json(content)

                return content

            except asyncio.TimeoutError:
                logger.warning(
                    f"Agent {self.name} LLM call timed out (attempt {attempt + 1})"
                )
                last_error = TimeoutError("LLM call timed out")
            except Exception as e:
                logger.warning(
                    f"Agent {self.name} LLM call failed (attempt {attempt + 1}): {e}"
                )
                last_error = e

            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_backoff * (attempt + 1))

        raise RuntimeError(
            f"Agent {self.name} failed after {self._max_retries} retries: {last_error}"
        )

    def _extract_json(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = text[start : end + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    pass

            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                candidate = text[start : end + 1]
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    pass

        return text

    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        start_time = time.time()
        logger.info(f"Agent {self.name} starting execution")

        try:
            result = await asyncio.wait_for(
                self.run(state),
                timeout=self._timeout,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            result["_agent_name"] = self.name
            result["_duration_ms"] = duration_ms
            result["_status"] = "success"
            logger.info(
                f"Agent {self.name} completed in {duration_ms}ms"
            )
            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Agent {self.name} timed out after {duration_ms}ms")
            return {
                "_agent_name": self.name,
                "_duration_ms": duration_ms,
                "_status": "timeout",
                "error": f"Agent {self.name} timed out",
            }
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Agent {self.name} failed: {e}")
            return {
                "_agent_name": self.name,
                "_duration_ms": duration_ms,
                "_status": "error",
                "error": str(e),
            }

    def _load_prompt(self, prompt_name: str) -> str:
        from pathlib import Path

        prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / prompt_name
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""
