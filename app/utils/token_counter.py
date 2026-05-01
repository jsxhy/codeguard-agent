from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import tiktoken
    _tiktoken_available = True
except ImportError:
    _tiktoken_available = False
    logger.warning("tiktoken not installed, token counting will use estimation")


class TokenCounter:
    def __init__(self, model: str = "gpt-4o") -> None:
        self._model = model
        self._encoder = None

        if _tiktoken_available:
            try:
                self._encoder = tiktoken.encoding_for_model(model)
            except KeyError:
                self._encoder = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        if self._encoder:
            return len(self._encoder.encode(text))
        return self._estimate(text)

    def _estimate(self, text: str) -> int:
        char_count = len(text)
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        non_chinese_chars = char_count - chinese_chars
        return int(chinese_chars * 1.5 + non_chinese_chars / 4)

    def count_messages(self, messages: list[dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            total += 4
            for key, value in msg.items():
                total += self.count(str(value))
                if key == "name":
                    total -= 1
            total += 2
        return total


_total_tokens: dict[str, int] = {}


def record_tokens(agent_name: str, token_count: int) -> None:
    _total_tokens[agent_name] = _total_tokens.get(agent_name, 0) + token_count


def get_token_usage() -> dict[str, int]:
    return dict(_total_tokens)


def reset_token_usage() -> None:
    _total_tokens.clear()
