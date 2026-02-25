"""Open Library API client for book and author data.

Open Library provides free book data including search, works, editions, and authors.
Base URL: https://openlibrary.org
Rate Limit: 1 req/sec (default), 3 req/sec (with User-Agent header — we set this)
Auth: None required

Implements all endpoints defined in the plan:
- search_books, search_by_author
- get_work, get_edition_by_isbn
- get_author, search_authors
- get_cover_url (static helper)
"""
from __future__ import annotations

from typing import Any

import structlog

from app.api_clients.base_client import BaseAPIClient
from app.models.api_schemas import (
    AuthorData,
    BookData,
    BookEditionData,
    BookWorkData,
)

logger = structlog.get_logger(__name__)

# Cover image base URL
COVER_BASE_URL = "https://covers.openlibrary.org/b/id"


class OpenLibraryClient(BaseAPIClient):
    """Client for the Open Library API."""

    def __init__(
        self,
        base_url: str = "https://openlibrary.org",
        rate_limit: float = 1.0,
        timeout: int = 30,
        max_retries: int = 3,
        cache_ttl: int = 300,
        cache_max_size: int = 256,
    ) -> None:
        super().__init__(
            base_url=base_url,
            rate_limit=rate_limit,
            timeout=timeout,
            max_retries=max_retries,
            cache_ttl=cache_ttl,
            cache_max_size=cache_max_size,
            headers={
                # Custom User-Agent for 3x rate limit boost
                "User-Agent": "ChatBotRAG/1.0 (entertainment-chatbot@example.com)",
            },
        )

    # ── Book Search Endpoints ─────────────────────────────────────────

    def search_books(self, query: str, limit: int = 5) -> list[BookData]:
        """Search books by title, author, or keyword.

        Args:
            query: Search query string.
            limit: Max results (1-20).

        Returns:
            List of BookData objects.
        """
        data = self.get("/search.json", params={
            "q": query,
            "limit": min(limit, 20),
            "fields": "key,title,author_name,first_publish_year,edition_count,"
                      "isbn,subject,cover_i,ratings_average,number_of_pages_median,"
                      "language,publisher",
        })
        return [self._parse_book(doc) for doc in data.get("docs", [])]

    def search_by_author(self, author: str, limit: int = 5) -> list[BookData]:
        """Search books by a specific author.

        Args:
            author: Author name.
            limit: Max results (1-20).

        Returns:
            List of BookData objects.
        """
        data = self.get("/search.json", params={
            "author": author,
            "limit": min(limit, 20),
            "fields": "key,title,author_name,first_publish_year,edition_count,"
                      "isbn,subject,cover_i,ratings_average,number_of_pages_median,"
                      "language,publisher",
        })
        return [self._parse_book(doc) for doc in data.get("docs", [])]

    # ── Work / Edition Endpoints ──────────────────────────────────────

    def get_work(self, work_id: str) -> BookWorkData | None:
        """Get work details by Open Library work key.

        Args:
            work_id: Open Library work ID (e.g., "OL27448W").

        Returns:
            BookWorkData or None if not found.
        """
        # Ensure the work_id has the correct format
        if not work_id.startswith("/works/"):
            work_id = f"/works/{work_id}"

        data = self.get(f"{work_id}.json")
        if not data or "error" in data:
            return None

        description = data.get("description", "")
        if isinstance(description, dict):
            description = description.get("value", "")

        return BookWorkData(
            title=data.get("title", "Unknown"),
            key=data.get("key", work_id),
            description=description if isinstance(description, str) else None,
            subjects=data.get("subjects", [])[:15],  # Limit subjects
            covers=data.get("covers", [])[:3],
            first_publish_date=data.get("first_publish_date"),
        )

    def get_edition_by_isbn(self, isbn: str) -> BookEditionData | None:
        """Get book edition details by ISBN.

        Args:
            isbn: ISBN-10 or ISBN-13.

        Returns:
            BookEditionData or None if not found.
        """
        # Clean the ISBN
        isbn = isbn.replace("-", "").replace(" ", "").strip()

        data = self.get(f"/isbn/{isbn}.json")
        if not data or "error" in data:
            return None

        covers = data.get("covers", [])
        cover_url = self.get_cover_url(covers[0]) if covers else None

        return BookEditionData(
            title=data.get("title", "Unknown"),
            isbn_13=data.get("isbn_13", []),
            isbn_10=data.get("isbn_10", []),
            publishers=data.get("publishers", []),
            publish_date=data.get("publish_date"),
            number_of_pages=data.get("number_of_pages"),
            covers=covers[:3],
            key=data.get("key"),
            cover_url=cover_url,
        )

    # ── Author Endpoints ──────────────────────────────────────────────

    def get_author(self, author_id: str) -> AuthorData | None:
        """Get author details by Open Library author key.

        Args:
            author_id: Open Library author ID (e.g., "OL26320A").

        Returns:
            AuthorData or None if not found.
        """
        if not author_id.startswith("/authors/"):
            author_id = f"/authors/{author_id}"

        data = self.get(f"{author_id}.json")
        if not data or "error" in data:
            return None

        bio = data.get("bio", "")
        if isinstance(bio, dict):
            bio = bio.get("value", "")

        photos = data.get("photos", [])
        photo_url = self.get_cover_url(photos[0], "a") if photos else None

        return AuthorData(
            name=data.get("name", "Unknown"),
            key=data.get("key", author_id),
            birth_date=data.get("birth_date"),
            death_date=data.get("death_date"),
            bio=bio if isinstance(bio, str) else None,
            photo_url=photo_url,
        )

    def search_authors(self, query: str, limit: int = 5) -> list[AuthorData]:
        """Search for authors by name.

        Args:
            query: Author name to search.
            limit: Max results (1-10).

        Returns:
            List of AuthorData objects.
        """
        data = self.get("/search/authors.json", params={"q": query, "limit": min(limit, 10)})
        authors = data.get("docs", [])
        return [
            AuthorData(
                name=a.get("name", "Unknown"),
                key=f"/authors/{a.get('key', '')}",
                birth_date=a.get("birth_date"),
                death_date=a.get("death_date"),
                top_work=a.get("top_work"),
                work_count=a.get("work_count"),
            )
            for a in authors
        ]

    # ── Cover URL Helper ──────────────────────────────────────────────

    @staticmethod
    def get_cover_url(cover_id: int, cover_type: str = "b", size: str = "M") -> str:
        """Construct an Open Library cover image URL.

        Args:
            cover_id: Cover image ID.
            cover_type: 'b' for book, 'a' for author.
            size: 'S' (small), 'M' (medium), 'L' (large).

        Returns:
            Full cover image URL.
        """
        base = f"https://covers.openlibrary.org/{cover_type}/id"
        return f"{base}/{cover_id}-{size}.jpg"

    # ── Health Check ──────────────────────────────────────────────────

    def health_check(self) -> bool:
        """Verify Open Library API is reachable."""
        try:
            self.get("/search.json", params={"q": "test", "limit": 1}, use_cache=False)
            return True
        except Exception:
            return False

    # ── Private Parsers ───────────────────────────────────────────────

    @staticmethod
    def _parse_book(doc: dict[str, Any]) -> BookData:
        """Parse raw Open Library search doc into BookData model."""
        cover_id = doc.get("cover_i")
        cover_url = None
        if cover_id:
            cover_url = f"{COVER_BASE_URL}/{cover_id}-M.jpg"

        return BookData(
            title=doc.get("title", "Unknown"),
            author_name=doc.get("author_name", []),
            first_publish_year=doc.get("first_publish_year"),
            edition_count=doc.get("edition_count"),
            isbn=doc.get("isbn", [])[:5],  # Limit ISBNs
            subject=doc.get("subject", [])[:10],  # Limit subjects
            cover_id=cover_id,
            key=doc.get("key"),
            ratings_average=doc.get("ratings_average"),
            number_of_pages=doc.get("number_of_pages_median"),
            language=doc.get("language", [])[:5],
            publisher=doc.get("publisher", [])[:5],
            cover_url=cover_url,
        )
