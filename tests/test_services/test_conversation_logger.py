"""Tests for conversation_logger service.

Verifies InteractionLog, ToolCallLog, ConversationLogger lifecycle,
file persistence, list/get operations, and summary computation.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.services.conversation_logger import (
    ConversationLogger,
    InteractionLog,
    LLMCallLog,
    ToolCallLog,
)


@pytest.fixture
def log_dir(tmp_path):
    """Provide a temporary directory for log files."""
    return str(tmp_path / "test_logs")


@pytest.fixture
def conv_logger(log_dir):
    """Create a ConversationLogger with a temp directory."""
    return ConversationLogger(log_dir=log_dir)


# ── Data Classes ──────────────────────────────────────────────────────


class TestToolCallLog:
    """Tests for ToolCallLog dataclass."""

    def test_to_dict_contains_all_fields(self):
        tc = ToolCallLog(
            tool_name="search_anime",
            arguments={"query": "Naruto"},
            api_client="jikan",
            result_summary="Found 5 results",
            duration_ms=450.123,
        )
        d = tc.to_dict()
        assert d["tool_name"] == "search_anime"
        assert d["arguments"] == {"query": "Naruto"}
        assert d["api_client"] == "jikan"
        assert d["result_summary"] == "Found 5 results"
        assert d["duration_ms"] == 450.12
        assert "timestamp" in d

    def test_auto_timestamp(self):
        tc = ToolCallLog(
            tool_name="search_books",
            arguments={},
            api_client="openlibrary",
        )
        assert tc.timestamp  # Should be auto-set


class TestLLMCallLog:
    """Tests for LLMCallLog dataclass."""

    def test_to_dict_with_tokens(self):
        lc = LLMCallLog(
            iteration=1,
            finish_reason="tool_calls",
            tokens={"prompt": 500, "completion": 50, "total": 550},
        )
        d = lc.to_dict()
        assert d["iteration"] == 1
        assert d["finish_reason"] == "tool_calls"
        assert d["tokens"]["total"] == 550


class TestInteractionLog:
    """Tests for InteractionLog dataclass."""

    def test_duration_calculation(self):
        interaction = InteractionLog(
            session_id="s1",
            user_prompt="Test",
        )
        interaction.start_time = 100.0
        interaction.end_time = 100.5
        assert interaction.total_duration_ms == 500.0

    def test_to_dict_structure(self):
        interaction = InteractionLog(
            session_id="s1",
            user_prompt="Tell me about Naruto",
        )
        interaction.model_response = "Naruto is a popular anime."
        interaction.end_time = interaction.start_time + 1.0

        d = interaction.to_dict()
        assert d["user_prompt"] == "Tell me about Naruto"
        assert d["model_response"] == "Naruto is a popular anime."
        assert d["tool_calls"] == []
        assert d["llm_calls"] == []
        assert d["total_duration_ms"] == pytest.approx(1000.0, abs=1)


# ── ConversationLogger ───────────────────────────────────────────────


class TestConversationLoggerInit:
    """Tests for ConversationLogger initialization."""

    def test_creates_log_directory(self, log_dir):
        ConversationLogger(log_dir=log_dir)
        assert Path(log_dir).exists()

    def test_works_with_existing_directory(self, tmp_path):
        existing = tmp_path / "existing"
        existing.mkdir()
        logger = ConversationLogger(log_dir=str(existing))
        assert logger is not None


class TestStartInteraction:
    """Tests for ConversationLogger.start_interaction."""

    def test_returns_interaction_log(self, conv_logger):
        interaction = conv_logger.start_interaction("sess1", "Hello")
        assert isinstance(interaction, InteractionLog)
        assert interaction.session_id == "sess1"
        assert interaction.user_prompt == "Hello"

    def test_initializes_session_list(self, conv_logger):
        conv_logger.start_interaction("sess1", "Test")
        assert "sess1" in conv_logger._sessions


class TestLogToolCall:
    """Tests for ConversationLogger.log_tool_call."""

    def test_appends_tool_call(self, conv_logger):
        interaction = conv_logger.start_interaction("s1", "Test")
        conv_logger.log_tool_call(
            interaction,
            tool_name="search_anime",
            arguments={"query": "Naruto"},
            result_summary="Found 5 results",
            duration_ms=450.0,
        )
        assert len(interaction.tool_calls) == 1
        assert interaction.tool_calls[0].tool_name == "search_anime"
        assert interaction.tool_calls[0].api_client == "jikan"

    def test_auto_detects_api_client(self, conv_logger):
        interaction = conv_logger.start_interaction("s1", "Test")
        conv_logger.log_tool_call(
            interaction, "search_books", {"query": "1984"}, "Found 3", 200,
        )
        assert interaction.tool_calls[0].api_client == "openlibrary"

    def test_unknown_tool_defaults_to_unknown(self, conv_logger):
        interaction = conv_logger.start_interaction("s1", "Test")
        conv_logger.log_tool_call(
            interaction, "unknown_tool", {}, "", 0,
        )
        assert interaction.tool_calls[0].api_client == "unknown"


class TestLogLLMCall:
    """Tests for ConversationLogger.log_llm_call."""

    def test_appends_llm_call(self, conv_logger):
        interaction = conv_logger.start_interaction("s1", "Test")
        conv_logger.log_llm_call(
            interaction,
            iteration=1,
            finish_reason="stop",
            tokens={"prompt": 100, "completion": 50, "total": 150},
        )
        assert len(interaction.llm_calls) == 1
        assert interaction.llm_calls[0].finish_reason == "stop"

    def test_handles_none_tokens(self, conv_logger):
        interaction = conv_logger.start_interaction("s1", "Test")
        conv_logger.log_llm_call(interaction, 1, "stop", tokens=None)
        assert interaction.llm_calls[0].tokens == {}


class TestEndInteraction:
    """Tests for ConversationLogger.end_interaction."""

    def test_saves_to_disk(self, conv_logger, log_dir):
        interaction = conv_logger.start_interaction("sess1", "Hi")
        conv_logger.end_interaction(interaction, "Hello! How can I help?")

        # Check that a .json file was created
        log_files = list(Path(log_dir).glob("*.json"))
        assert len(log_files) == 1

    def test_json_file_has_correct_structure(self, conv_logger, log_dir):
        interaction = conv_logger.start_interaction("sess1", "Tell me about Naruto")
        conv_logger.log_tool_call(
            interaction, "search_anime", {"query": "Naruto"}, "Found 5", 450,
        )
        conv_logger.log_llm_call(
            interaction, 1, "tool_calls", {"prompt": 500, "completion": 50},
        )
        conv_logger.log_llm_call(
            interaction, 2, "stop", {"prompt": 800, "completion": 200},
        )
        conv_logger.end_interaction(interaction, "Naruto is a popular anime.")

        log_files = list(Path(log_dir).glob("*.json"))
        with open(log_files[0]) as f:
            data = json.load(f)

        assert data["session_id"] == "sess1"
        assert data["summary"]["total_interactions"] == 1
        assert data["summary"]["total_tool_calls"] == 1
        assert data["summary"]["total_llm_calls"] == 2
        assert "search_anime" in data["summary"]["tools_used"]
        assert "jikan" in data["summary"]["api_clients_used"]
        assert len(data["interactions"]) == 1
        assert data["interactions"][0]["user_prompt"] == "Tell me about Naruto"
        assert data["interactions"][0]["model_response"] == "Naruto is a popular anime."


class TestGetSessionLog:
    """Tests for ConversationLogger.get_session_log."""

    def test_returns_none_for_missing_session(self, conv_logger):
        result = conv_logger.get_session_log("nonexistent")
        assert result is None

    def test_returns_data_for_existing_session(self, conv_logger):
        interaction = conv_logger.start_interaction("sess1", "Test")
        conv_logger.end_interaction(interaction, "Response")

        result = conv_logger.get_session_log("sess1")
        assert result is not None
        assert result["session_id"] == "sess1"


class TestListSessions:
    """Tests for ConversationLogger.list_sessions."""

    def test_returns_empty_list_initially(self, conv_logger):
        sessions = conv_logger.list_sessions()
        assert sessions == []

    def test_returns_session_after_interaction(self, conv_logger):
        interaction = conv_logger.start_interaction("sess1", "Test")
        conv_logger.end_interaction(interaction, "Response")

        sessions = conv_logger.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "sess1"
        assert "summary" in sessions[0]

    def test_multiple_sessions(self, conv_logger):
        for i in range(3):
            interaction = conv_logger.start_interaction(f"sess{i}", f"Test {i}")
            conv_logger.end_interaction(interaction, f"Response {i}")

        sessions = conv_logger.list_sessions()
        assert len(sessions) == 3


class TestSummaryComputation:
    """Tests for summary computation across multiple interactions."""

    def test_accumulates_across_interactions(self, conv_logger):
        # First interaction
        i1 = conv_logger.start_interaction("sess1", "Query 1")
        conv_logger.log_tool_call(i1, "search_anime", {"query": "test"}, "Found 3", 100)
        conv_logger.log_tool_call(i1, "search_books", {"query": "test"}, "Found 2", 200)
        conv_logger.log_llm_call(i1, 1, "tool_calls", {"prompt": 100, "completion": 50})
        conv_logger.log_llm_call(i1, 2, "stop", {"prompt": 200, "completion": 100})
        conv_logger.end_interaction(i1, "Response 1")

        # Second interaction in same session
        i2 = conv_logger.start_interaction("sess1", "Query 2")
        conv_logger.log_tool_call(i2, "search_anime", {"query": "test2"}, "Found 1", 150)
        conv_logger.log_llm_call(i2, 1, "stop", {"prompt": 300, "completion": 150})
        conv_logger.end_interaction(i2, "Response 2")

        log = conv_logger.get_session_log("sess1")
        summary = log["summary"]

        assert summary["total_interactions"] == 2
        assert summary["total_tool_calls"] == 3
        assert summary["total_llm_calls"] == 3
        assert summary["tools_used"]["search_anime"] == 2
        assert summary["tools_used"]["search_books"] == 1
        assert summary["api_clients_used"]["jikan"] == 2
        assert summary["api_clients_used"]["openlibrary"] == 1
