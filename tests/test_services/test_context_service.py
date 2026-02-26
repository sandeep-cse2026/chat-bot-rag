"""Tests for context_service (ChromaDB vector DB context).

Verifies store, retrieve, format, clear, and stats operations.
Uses a temporary directory for ChromaDB persistence.
"""
from __future__ import annotations

import tempfile

import pytest

from app.services.context_service import ContextService


@pytest.fixture
def context_svc(tmp_path):
    """Create a ContextService with a temp ChromaDB directory."""
    return ContextService(
        persist_dir=str(tmp_path / "chroma_test"),
        collection_name="test_conversations",
        max_results=3,
        similarity_threshold=1.5,
    )


# ── Initialization ───────────────────────────────────────────────────


class TestInit:
    """Tests for ContextService initialization."""

    def test_creates_collection(self, context_svc):
        stats = context_svc.get_collection_stats()
        assert stats["collection_name"] == "test_conversations"
        assert stats["document_count"] == 0

    def test_reuses_existing_collection(self, tmp_path):
        path = str(tmp_path / "chroma_reuse")
        svc1 = ContextService(persist_dir=path, collection_name="test")
        svc1.store_interaction("s1", "Hello", "Hi!")

        svc2 = ContextService(persist_dir=path, collection_name="test")
        assert svc2.get_collection_stats()["document_count"] == 1


# ── Store ─────────────────────────────────────────────────────────────


class TestStoreInteraction:
    """Tests for ContextService.store_interaction."""

    def test_stores_document(self, context_svc):
        context_svc.store_interaction("sess1", "What is Naruto?", "Naruto is an anime.")
        assert context_svc.get_collection_stats()["document_count"] == 1

    def test_stores_with_tool_calls(self, context_svc):
        context_svc.store_interaction(
            "sess1", "Find anime", "Here are results.",
            tool_calls=["search_anime"],
        )
        assert context_svc.get_collection_stats()["document_count"] == 1

    def test_stores_multiple_interactions(self, context_svc):
        for i in range(5):
            context_svc.store_interaction(f"sess{i}", f"Q{i}", f"A{i}")
        assert context_svc.get_collection_stats()["document_count"] == 5


# ── Retrieve ──────────────────────────────────────────────────────────


class TestRetrieveContext:
    """Tests for ContextService.retrieve_context."""

    def test_returns_empty_when_no_data(self, context_svc):
        results = context_svc.retrieve_context("sess1", "anything")
        assert results == []

    def test_retrieves_relevant_context(self, context_svc):
        context_svc.store_interaction(
            "sess1", "Tell me about Naruto",
            "Naruto is a popular anime about a ninja.",
        )
        context_svc.store_interaction(
            "sess1", "What is One Piece?",
            "One Piece is a pirate adventure anime.",
        )

        results = context_svc.retrieve_context("sess1", "What anime is about ninjas?")
        assert len(results) >= 1
        # The Naruto context should be more relevant
        assert "Naruto" in results[0]["document"]

    def test_filters_by_session(self, context_svc):
        context_svc.store_interaction("sess1", "Q1", "A1")
        context_svc.store_interaction("sess2", "Q2", "A2")

        results = context_svc.retrieve_context("sess1", "Q1")
        for r in results:
            assert r["metadata"]["session_id"] == "sess1"

    def test_cross_session_retrieval(self, context_svc):
        context_svc.store_interaction("sess1", "Naruto info", "Naruto is great")
        context_svc.store_interaction("sess2", "One Piece", "One Piece is top anime")

        results = context_svc.retrieve_context(
            "sess3", "anime", cross_session=True,
        )
        assert len(results) >= 1

    def test_respects_max_results(self, context_svc):
        for i in range(10):
            context_svc.store_interaction("sess1", f"anime {i}", f"response {i}")

        results = context_svc.retrieve_context("sess1", "anime", n_results=2)
        assert len(results) <= 2

    def test_result_has_expected_keys(self, context_svc):
        context_svc.store_interaction("sess1", "Test Q", "Test A")
        results = context_svc.retrieve_context("sess1", "Test")
        assert len(results) == 1
        assert "document" in results[0]
        assert "metadata" in results[0]
        assert "distance" in results[0]


# ── Format ────────────────────────────────────────────────────────────


class TestFormatContext:
    """Tests for ContextService.format_context_for_prompt."""

    def test_empty_contexts_returns_empty_string(self, context_svc):
        result = context_svc.format_context_for_prompt([])
        assert result == ""

    def test_formats_non_empty_contexts(self, context_svc):
        contexts = [
            {
                "document": "Q: What is Naruto?\nA: An anime.",
                "metadata": {"session_id": "s1"},
                "distance": 0.3,
            },
        ]
        result = context_svc.format_context_for_prompt(contexts)
        assert "Naruto" in result
        assert "Past Interaction 1" in result
        assert "relevance" in result


# ── Clear ─────────────────────────────────────────────────────────────


class TestClearSessionContext:
    """Tests for ContextService.clear_session_context."""

    def test_clears_session_documents(self, context_svc):
        context_svc.store_interaction("sess1", "Q1", "A1")
        context_svc.store_interaction("sess1", "Q2", "A2")
        assert context_svc.get_collection_stats()["document_count"] == 2

        deleted = context_svc.clear_session_context("sess1")
        assert deleted == 2
        assert context_svc.get_collection_stats()["document_count"] == 0

    def test_clear_nonexistent_returns_zero(self, context_svc):
        deleted = context_svc.clear_session_context("nonexistent")
        assert deleted == 0

    def test_clear_only_affects_target_session(self, context_svc):
        context_svc.store_interaction("sess1", "Q1", "A1")
        context_svc.store_interaction("sess2", "Q2", "A2")

        context_svc.clear_session_context("sess1")
        assert context_svc.get_collection_stats()["document_count"] == 1


# ── Stats ─────────────────────────────────────────────────────────────


class TestGetCollectionStats:
    """Tests for ContextService.get_collection_stats."""

    def test_returns_stats_dict(self, context_svc):
        stats = context_svc.get_collection_stats()
        assert "collection_name" in stats
        assert "document_count" in stats
        assert isinstance(stats["document_count"], int)
