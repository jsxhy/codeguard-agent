import pytest
from app.utils.token_counter import TokenCounter, record_tokens, get_token_usage, reset_token_usage


class TestTokenCounter:
    def setup_method(self):
        self.counter = TokenCounter(model="gpt-4o")
        reset_token_usage()

    def test_count_english_text(self):
        text = "Hello, this is a test."
        count = self.counter.count(text)
        assert count > 0

    def test_count_chinese_text(self):
        text = "你好，这是一个测试。"
        count = self.counter.count(text)
        assert count > 0

    def test_count_empty_string(self):
        assert self.counter.count("") == 0

    def test_count_messages(self):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ]
        count = self.counter.count_messages(messages)
        assert count > 0

    def test_record_and_get_tokens(self):
        record_tokens("agent1", 100)
        record_tokens("agent1", 50)
        record_tokens("agent2", 200)

        usage = get_token_usage()
        assert usage["agent1"] == 150
        assert usage["agent2"] == 200

    def test_reset_token_usage(self):
        record_tokens("agent1", 100)
        reset_token_usage()
        usage = get_token_usage()
        assert len(usage) == 0
