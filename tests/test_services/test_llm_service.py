"""Unit tests for the LLM service."""
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.llm_service import (
    ConversationHistory,
    LLMResponse,
    LLMService,
    ToolCall,
)
from app.utils.exceptions import LLMRateLimitError, LLMServiceError


@pytest.fixture
def llm():
    """Create an LLMService instance."""
    service = LLMService(api_key="test-key", model="test-model")
    yield service
    service.close()


def _mock_httpx_response(data, status_code=200, headers=None):
    """Create a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    resp.text = json.dumps(data)
    resp.headers = headers or {}
    return resp


class TestChatCompletion:
    """Tests for LLMService.chat_completion."""

    def test_text_response(self, llm):
        mock_data = {
            "choices": [
                {
                    "message": {"content": "Hello! How can I help?", "role": "assistant"},
                    "finish_reason": "stop",
                }
            ],
            "model": "test-model",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        with patch.object(llm._client, "post", return_value=_mock_httpx_response(mock_data)):
            result = llm.chat_completion(
                messages=[{"role": "user", "content": "Hi"}]
            )

        assert isinstance(result, LLMResponse)
        assert result.content == "Hello! How can I help?"
        assert result.has_tool_calls is False
        assert result.usage["total_tokens"] == 15
        assert result.finish_reason == "stop"

    def test_tool_call_response(self, llm):
        mock_data = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call_abc123",
                                "type": "function",
                                "function": {
                                    "name": "search_anime",
                                    "arguments": '{"query": "Naruto", "limit": 5}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "model": "test-model",
            "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        }
        with patch.object(llm._client, "post", return_value=_mock_httpx_response(mock_data)):
            result = llm.chat_completion(
                messages=[{"role": "user", "content": "Search for Naruto"}],
                tools=[{"type": "function", "function": {"name": "search_anime"}}],
            )

        assert result.has_tool_calls is True
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search_anime"
        assert result.tool_calls[0].arguments == {"query": "Naruto", "limit": 5}
        assert result.tool_calls[0].id == "call_abc123"

    def test_empty_choices_raises(self, llm):
        mock_data = {"choices": [], "model": "test", "usage": {}}
        with patch.object(llm._client, "post", return_value=_mock_httpx_response(mock_data)):
            with pytest.raises(LLMServiceError, match="no choices"):
                llm.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_rate_limit_raises(self, llm):
        resp = _mock_httpx_response({}, status_code=429, headers={"Retry-After": "1"})
        with patch.object(llm._client, "post", return_value=resp):
            with pytest.raises(LLMRateLimitError):
                llm.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_server_error_raises(self, llm):
        resp = _mock_httpx_response({"error": "Internal"}, status_code=500)
        with patch.object(llm._client, "post", return_value=resp):
            with pytest.raises(LLMServiceError):
                llm.chat_completion(messages=[{"role": "user", "content": "Hi"}])

    def test_timeout_raises(self, llm):
        with patch.object(llm._client, "post", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(LLMServiceError, match="timed out"):
                llm.chat_completion(messages=[{"role": "user", "content": "Hi"}])


class TestConversationHistory:
    """Tests for ConversationHistory."""

    def test_basic_flow(self):
        history = ConversationHistory(system_prompt="You are a bot.")
        history.add_user_message("Hello")
        history.add_assistant_message("Hi there!")

        assert len(history.messages) == 3
        assert history.messages[0]["role"] == "system"
        assert history.messages[1]["role"] == "user"
        assert history.messages[2]["role"] == "assistant"

    def test_trimming_preserves_system(self):
        history = ConversationHistory(max_length=4, system_prompt="System prompt.")
        for i in range(10):
            history.add_user_message(f"Message {i}")
        assert len(history.messages) <= 4
        assert history.messages[0]["role"] == "system"
        assert history.messages[0]["content"] == "System prompt."

    def test_tool_calls_in_history(self):
        history = ConversationHistory()
        tc = ToolCall(id="call_1", name="search_anime", arguments={"query": "Naruto"})
        history.add_assistant_tool_calls([tc])
        history.add_tool_result("call_1", "search_anime", '{"results": []}')

        assert history.messages[-2]["role"] == "assistant"
        assert history.messages[-2]["tool_calls"][0]["function"]["name"] == "search_anime"
        assert history.messages[-1]["role"] == "tool"
        assert history.messages[-1]["tool_call_id"] == "call_1"

    def test_clear_preserves_system(self):
        history = ConversationHistory(system_prompt="Keep me.")
        history.add_user_message("Hello")
        history.add_assistant_message("Hi")
        history.clear()

        assert len(history.messages) == 1
        assert history.messages[0]["content"] == "Keep me."

    def test_no_system_prompt(self):
        history = ConversationHistory()
        history.add_user_message("Hello")
        assert len(history.messages) == 1
        assert history.messages[0]["role"] == "user"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_has_tool_calls_false(self):
        resp = LLMResponse(content="Hello")
        assert resp.has_tool_calls is False

    def test_has_tool_calls_true(self):
        tc = ToolCall(id="1", name="test", arguments={})
        resp = LLMResponse(tool_calls=[tc])
        assert resp.has_tool_calls is True
