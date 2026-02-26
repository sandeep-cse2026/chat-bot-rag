"""Conversation logger — structured JSON logging for full observability.

Records every interaction (user prompt → tool calls → LLM calls → response)
into per-session JSON files. Each file contains a summary with counts of
tool calls, API endpoints, tokens used, and the full interaction history.

Usage:
    logger = ConversationLogger(log_dir="logs/conversations")
    interaction = logger.start_interaction("session-1", "Tell me about Naruto")
    logger.log_tool_call(interaction, "search_anime", {"query": "Naruto"}, "jikan", "Found 5", 450)
    logger.log_llm_call(interaction, 1, "tool_calls", {"prompt": 500, "completion": 50, "total": 550})
    logger.end_interaction(interaction, "Naruto is a popular anime...")
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ToolCallLog:
    """Log entry for a single tool call."""

    tool_name: str
    arguments: dict[str, Any]
    api_client: str
    result_summary: str = ""
    duration_ms: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "api_client": self.api_client,
            "result_summary": self.result_summary,
            "duration_ms": round(self.duration_ms, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class LLMCallLog:
    """Log entry for a single LLM call."""

    iteration: int
    finish_reason: str
    tokens: dict[str, int] = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "finish_reason": self.finish_reason,
            "tokens": self.tokens,
            "timestamp": self.timestamp,
        }


@dataclass
class InteractionLog:
    """Tracks a single user → response interaction."""

    session_id: str
    user_prompt: str
    tool_calls: list[ToolCallLog] = field(default_factory=list)
    llm_calls: list[LLMCallLog] = field(default_factory=list)
    model_response: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.start_time:
            self.start_time = time.time()
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def total_duration_ms(self) -> float:
        if self.end_time:
            return round((self.end_time - self.start_time) * 1000, 2)
        return 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "user_prompt": self.user_prompt,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "llm_calls": [lc.to_dict() for lc in self.llm_calls],
            "model_response": self.model_response,
            "total_duration_ms": self.total_duration_ms,
        }


# ── Client-to-tool mapping for log classification ────────────────────
_TOOL_TO_CLIENT = {
    "search_anime": "jikan",
    "get_anime_details": "jikan",
    "search_manga": "jikan",
    "get_manga_details": "jikan",
    "get_top_anime": "jikan",
    "get_seasonal_anime": "jikan",
    "search_tv_shows": "tvmaze",
    "get_tv_show_details": "tvmaze",
    "get_tv_episode": "tvmaze",
    "get_tv_schedule": "tvmaze",
    "search_books": "openlibrary",
    "get_book_by_isbn": "openlibrary",
    "search_authors": "openlibrary",
}


class ConversationLogger:
    """Writes structured conversation logs to per-session JSON files.

    Each session produces one JSON file in the log directory containing:
    - A computed summary (total tool calls, endpoints, tokens, etc.)
    - Full interaction history with tool calls and LLM calls

    Args:
        log_dir: Directory path for conversation log files.
    """

    def __init__(self, log_dir: str = "logs/conversations") -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # In-memory session data: session_id → list of InteractionLog
        self._sessions: dict[str, list[InteractionLog]] = {}

        logger.info("conversation_logger_initialized", log_dir=str(self._log_dir))

    # ── Public API ────────────────────────────────────────────────────

    def start_interaction(
        self, session_id: str, user_prompt: str
    ) -> InteractionLog:
        """Begin tracking a new user interaction.

        Args:
            session_id: Unique session identifier.
            user_prompt: The user's message.

        Returns:
            InteractionLog to pass to subsequent log_* calls.
        """
        interaction = InteractionLog(
            session_id=session_id,
            user_prompt=user_prompt,
        )

        if session_id not in self._sessions:
            self._sessions[session_id] = []

        return interaction

    def log_tool_call(
        self,
        interaction: InteractionLog,
        tool_name: str,
        arguments: dict[str, Any],
        result_summary: str = "",
        duration_ms: float = 0.0,
    ) -> None:
        """Record a tool call within an interaction.

        Args:
            interaction: The current InteractionLog.
            tool_name: Function name (e.g., "search_anime").
            arguments: Arguments passed to the tool.
            result_summary: Brief description of the result.
            duration_ms: Execution time in milliseconds.
        """
        api_client = _TOOL_TO_CLIENT.get(tool_name, "unknown")

        tc = ToolCallLog(
            tool_name=tool_name,
            arguments=arguments,
            api_client=api_client,
            result_summary=result_summary,
            duration_ms=duration_ms,
        )
        interaction.tool_calls.append(tc)

    def log_llm_call(
        self,
        interaction: InteractionLog,
        iteration: int,
        finish_reason: str,
        tokens: dict[str, int] | None = None,
    ) -> None:
        """Record an LLM call within an interaction.

        Args:
            interaction: The current InteractionLog.
            iteration: Which iteration of the conversation loop (1-based).
            finish_reason: LLM finish reason ("stop", "tool_calls", etc.).
            tokens: Token usage dict (prompt, completion, total).
        """
        lc = LLMCallLog(
            iteration=iteration,
            finish_reason=finish_reason,
            tokens=tokens or {},
        )
        interaction.llm_calls.append(lc)

    def end_interaction(
        self, interaction: InteractionLog, model_response: str
    ) -> None:
        """Finalize an interaction and persist to disk.

        Args:
            interaction: The current InteractionLog.
            model_response: The final assistant response text.
        """
        interaction.model_response = model_response
        interaction.end_time = time.time()

        self._sessions[interaction.session_id].append(interaction)
        self._save_session_log(interaction.session_id)

        logger.info(
            "interaction_logged",
            session_id=interaction.session_id,
            tool_calls=len(interaction.tool_calls),
            llm_calls=len(interaction.llm_calls),
            duration_ms=interaction.total_duration_ms,
        )

    def get_session_log(self, session_id: str) -> dict | None:
        """Read and return a session's log file.

        Args:
            session_id: Session to look up.

        Returns:
            Parsed log dict, or None if not found.
        """
        log_file = self._get_log_file_path(session_id)
        if not log_file.exists():
            return None

        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def list_sessions(self) -> list[dict]:
        """List all session log summaries.

        Returns:
            List of session summary dicts (session_id, created_at, summary).
        """
        summaries = []
        for log_file in sorted(self._log_dir.glob("*.json"), reverse=True):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                summaries.append({
                    "session_id": data.get("session_id", ""),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "summary": data.get("summary", {}),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return summaries

    # ── Private Helpers ───────────────────────────────────────────────

    def _get_log_file_path(self, session_id: str) -> Path:
        """Build the log file path for a session."""
        # Sanitize session_id for safe filenames
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        return self._log_dir / f"{date_prefix}_{safe_id}.json"

    def _save_session_log(self, session_id: str) -> None:
        """Write/update the session JSON file with computed summary."""
        interactions = self._sessions.get(session_id, [])
        if not interactions:
            return

        log_file = self._get_log_file_path(session_id)

        # Compute summary across all interactions
        summary = self._compute_summary(interactions)

        log_data = {
            "session_id": session_id,
            "created_at": interactions[0].timestamp,
            "updated_at": interactions[-1].timestamp,
            "summary": summary,
            "interactions": [i.to_dict() for i in interactions],
        }

        try:
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            logger.error("log_save_failed", session_id=session_id, error=str(e))

    @staticmethod
    def _compute_summary(interactions: list[InteractionLog]) -> dict:
        """Compute aggregate summary across all interactions."""
        total_tool_calls = 0
        total_llm_calls = 0
        tools_counter: Counter = Counter()
        clients_counter: Counter = Counter()
        total_tokens: dict[str, int] = {"prompt": 0, "completion": 0, "total": 0}

        for interaction in interactions:
            total_tool_calls += len(interaction.tool_calls)
            total_llm_calls += len(interaction.llm_calls)

            for tc in interaction.tool_calls:
                tools_counter[tc.tool_name] += 1
                clients_counter[tc.api_client] += 1

            for lc in interaction.llm_calls:
                for key in ("prompt", "completion", "total"):
                    total_tokens[key] += lc.tokens.get(
                        f"{'prompt' if key == 'prompt' else key}_tokens",
                        lc.tokens.get(key, 0),
                    )

        return {
            "total_interactions": len(interactions),
            "total_tool_calls": total_tool_calls,
            "total_api_endpoints_hit": total_tool_calls,
            "tools_used": dict(tools_counter),
            "api_clients_used": dict(clients_counter),
            "total_llm_calls": total_llm_calls,
            "total_tokens": total_tokens,
        }
