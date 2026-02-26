"""Context service — semantic conversation memory using ChromaDB.

Stores past Q&A interactions as embeddings in ChromaDB and retrieves
semantically relevant context for new queries. This is the core RAG
component — the "R" (Retrieval) in Retrieval-Augmented Generation.

Uses ChromaDB's built-in sentence-transformer model (all-MiniLM-L6-v2)
for embeddings. No external API call needed — runs locally on CPU.

Usage:
    service = ContextService(persist_dir="data/chromadb")
    service.store_interaction("sess1", "What is Naruto?", "Naruto is a popular anime...")
    contexts = service.retrieve_context("sess1", "Tell me more about anime")
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ContextService:
    """Manages semantic conversation memory with ChromaDB.

    Stores user/assistant Q&A pairs as vector embeddings and retrieves
    relevant past context to augment new queries.

    Args:
        persist_dir: Directory for ChromaDB persistence.
        collection_name: Name of the ChromaDB collection.
        max_results: Default number of results to retrieve.
        similarity_threshold: Max distance for relevant context (lower = more relevant).
    """

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        collection_name: str = "conversations",
        max_results: int = 3,
        similarity_threshold: float = 1.2,
    ) -> None:
        import chromadb

        self._max_results = max_results
        self._similarity_threshold = similarity_threshold

        # Initialize persistent ChromaDB client
        self._client = chromadb.PersistentClient(path=persist_dir)

        # Get or create collection — uses default embedding function
        # (all-MiniLM-L6-v2, auto-downloaded on first use ~80MB)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "context_service_initialized",
            persist_dir=persist_dir,
            collection=collection_name,
            doc_count=self._collection.count(),
        )

    # ── Public API ────────────────────────────────────────────────────

    def store_interaction(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        tool_calls: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store a Q&A interaction as a vector embedding.

        The document is a combined "Q: ... A: ..." string for semantic
        coherence when retrieved.

        Args:
            session_id: Session identifier.
            user_message: The user's original message.
            assistant_message: The assistant's response.
            tool_calls: Names of tools used during this interaction.
            metadata: Additional metadata to store.
        """
        # Build the document
        document = f"Q: {user_message}\nA: {assistant_message}"

        # Build metadata
        doc_metadata = {
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_message": user_message[:500],  # Truncate for metadata limits
            "tools_used": ",".join(tool_calls) if tool_calls else "",
        }
        if metadata:
            doc_metadata.update(metadata)

        # Generate a unique ID for this document
        doc_id = f"{session_id}_{int(time.time() * 1000)}"

        try:
            self._collection.upsert(
                ids=[doc_id],
                documents=[document],
                metadatas=[doc_metadata],
            )
            logger.info(
                "context_stored",
                session_id=session_id,
                doc_id=doc_id,
                doc_length=len(document),
            )
        except Exception as e:
            logger.error("context_store_failed", session_id=session_id, error=str(e))

    def retrieve_context(
        self,
        session_id: str,
        query: str,
        n_results: int | None = None,
        cross_session: bool = False,
    ) -> list[dict]:
        """Retrieve semantically relevant past context.

        Args:
            session_id: Current session ID (for filtering).
            query: The query to search for similar past interactions.
            n_results: Max results to return (defaults to self._max_results).
            cross_session: If True, search across all sessions.

        Returns:
            List of context dicts with 'document', 'metadata', 'distance'.
        """
        if self._collection.count() == 0:
            return []

        n = n_results or self._max_results

        try:
            # Build query parameters
            query_params: dict[str, Any] = {
                "query_texts": [query],
                "n_results": min(n, self._collection.count()),
            }

            # Filter by session unless cross-session
            if not cross_session:
                query_params["where"] = {"session_id": session_id}

            results = self._collection.query(**query_params)

            # Parse and filter by similarity threshold
            contexts = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    distance = results["distances"][0][i] if results["distances"] else 0
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                    if distance <= self._similarity_threshold:
                        contexts.append({
                            "document": doc,
                            "metadata": metadata,
                            "distance": round(distance, 4),
                        })

            logger.info(
                "context_retrieved",
                session_id=session_id,
                query_length=len(query),
                results_found=len(contexts),
            )
            return contexts

        except Exception as e:
            logger.error(
                "context_retrieval_failed",
                session_id=session_id,
                error=str(e),
            )
            return []

    def format_context_for_prompt(self, contexts: list[dict]) -> str:
        """Format retrieved contexts into a string for the system prompt.

        Args:
            contexts: List of context dicts from retrieve_context().

        Returns:
            Formatted string ready for injection into the prompt.
        """
        if not contexts:
            return ""

        parts = ["Here is relevant context from our previous conversations:\n"]

        for i, ctx in enumerate(contexts, 1):
            relevance = f"(relevance: {1 - ctx['distance']:.0%})"
            parts.append(f"--- Past Interaction {i} {relevance} ---")
            parts.append(ctx["document"])
            parts.append("")

        parts.append("Use this context to provide more informed and personalized responses.")
        return "\n".join(parts)

    def clear_session_context(self, session_id: str) -> int:
        """Delete all stored context for a session.

        Args:
            session_id: Session to clear.

        Returns:
            Number of documents deleted.
        """
        try:
            # Get all document IDs for this session
            results = self._collection.get(
                where={"session_id": session_id},
            )

            if results and results["ids"]:
                self._collection.delete(ids=results["ids"])
                count = len(results["ids"])
                logger.info(
                    "context_cleared",
                    session_id=session_id,
                    docs_deleted=count,
                )
                return count

            return 0

        except Exception as e:
            logger.error("context_clear_failed", session_id=session_id, error=str(e))
            return 0

    def get_collection_stats(self) -> dict:
        """Return collection statistics for health checks.

        Returns:
            Dict with collection name and document count.
        """
        return {
            "collection_name": self._collection.name,
            "document_count": self._collection.count(),
        }
