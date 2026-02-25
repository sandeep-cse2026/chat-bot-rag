"""Jikan API v4 client for anime and manga data.

Jikan is an unofficial MyAnimeList REST API.
Base URL: https://api.jikan.moe/v4
Rate Limit: ~3 req/sec, 60 req/min (we use 1 req/sec for safety)
Auth: None required

Implements all endpoints defined in the plan:
- search_anime, get_anime_by_id
- search_manga, get_manga_by_id
- get_top_anime, get_top_manga
- get_anime_characters, get_season_anime, get_anime_recommendations
"""
from __future__ import annotations

from typing import Any

import structlog

from app.api_clients.base_client import BaseAPIClient
from app.models.api_schemas import (
    AnimeCharacter,
    AnimeData,
    AnimeRecommendation,
    MangaData,
)

logger = structlog.get_logger(__name__)


class JikanClient(BaseAPIClient):
    """Client for the Jikan (MyAnimeList) API v4."""

    def __init__(
        self,
        base_url: str = "https://api.jikan.moe/v4",
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
        )

    # ── Anime Endpoints ───────────────────────────────────────────────

    def search_anime(self, query: str, limit: int = 5) -> list[AnimeData]:
        """Search anime by name.

        Args:
            query: Search query string.
            limit: Max results to return (1-25).

        Returns:
            List of normalized AnimeData objects.
        """
        data = self.get("/anime", params={"q": query, "limit": min(limit, 25), "sfw": True})
        return [self._parse_anime(item) for item in data.get("data", [])]

    def get_anime_by_id(self, anime_id: int) -> AnimeData | None:
        """Get full anime details by MAL ID.

        Args:
            anime_id: MyAnimeList anime ID.

        Returns:
            AnimeData or None if not found.
        """
        data = self.get(f"/anime/{anime_id}/full")
        if "data" in data:
            return self._parse_anime(data["data"])
        return None

    def get_top_anime(self, filter_type: str = "bypopularity", limit: int = 10) -> list[AnimeData]:
        """Get top anime lists.

        Args:
            filter_type: Filter — 'airing', 'upcoming', 'bypopularity', 'favorite'.
            limit: Max results (1-25).

        Returns:
            List of AnimeData objects.
        """
        data = self.get("/top/anime", params={"filter": filter_type, "limit": min(limit, 25)})
        return [self._parse_anime(item) for item in data.get("data", [])]

    def get_season_anime(self, year: int, season: str, limit: int = 10) -> list[AnimeData]:
        """Get anime airing in a specific season.

        Args:
            year: Year (e.g., 2024).
            season: Season — 'winter', 'spring', 'summer', 'fall'.
            limit: Max results.

        Returns:
            List of AnimeData objects.
        """
        data = self.get(f"/seasons/{year}/{season}", params={"limit": min(limit, 25)})
        return [self._parse_anime(item) for item in data.get("data", [])]

    def get_anime_characters(self, anime_id: int) -> list[AnimeCharacter]:
        """Get characters for an anime.

        Args:
            anime_id: MyAnimeList anime ID.

        Returns:
            List of AnimeCharacter objects (limited to top 10).
        """
        data = self.get(f"/anime/{anime_id}/characters")
        characters = data.get("data", [])[:10]  # Limit to avoid overwhelming LLM
        return [
            AnimeCharacter(
                name=char.get("character", {}).get("name", "Unknown"),
                role=char.get("role"),
                image_url=char.get("character", {}).get("images", {}).get("jpg", {}).get("image_url"),
            )
            for char in characters
        ]

    def get_anime_recommendations(self, anime_id: int) -> list[AnimeRecommendation]:
        """Get recommendations for an anime.

        Args:
            anime_id: MyAnimeList anime ID.

        Returns:
            List of AnimeRecommendation objects (limited to top 5).
        """
        data = self.get(f"/anime/{anime_id}/recommendations")
        recs = data.get("data", [])[:5]
        return [
            AnimeRecommendation(
                mal_id=rec.get("entry", {}).get("mal_id", 0),
                title=rec.get("entry", {}).get("title", "Unknown"),
                url=rec.get("entry", {}).get("url"),
                image_url=rec.get("entry", {}).get("images", {}).get("jpg", {}).get("image_url"),
                votes=rec.get("votes", 0),
            )
            for rec in recs
        ]

    # ── Manga Endpoints ───────────────────────────────────────────────

    def search_manga(self, query: str, limit: int = 5) -> list[MangaData]:
        """Search manga by name.

        Args:
            query: Search query string.
            limit: Max results (1-25).

        Returns:
            List of MangaData objects.
        """
        data = self.get("/manga", params={"q": query, "limit": min(limit, 25), "sfw": True})
        return [self._parse_manga(item) for item in data.get("data", [])]

    def get_manga_by_id(self, manga_id: int) -> MangaData | None:
        """Get full manga details by MAL ID.

        Args:
            manga_id: MyAnimeList manga ID.

        Returns:
            MangaData or None if not found.
        """
        data = self.get(f"/manga/{manga_id}/full")
        if "data" in data:
            return self._parse_manga(data["data"])
        return None

    def get_top_manga(self, filter_type: str = "bypopularity", limit: int = 10) -> list[MangaData]:
        """Get top manga lists.

        Args:
            filter_type: Filter — 'publishing', 'upcoming', 'bypopularity', 'favorite'.
            limit: Max results (1-25).

        Returns:
            List of MangaData objects.
        """
        data = self.get("/top/manga", params={"filter": filter_type, "limit": min(limit, 25)})
        return [self._parse_manga(item) for item in data.get("data", [])]

    # ── Health Check ──────────────────────────────────────────────────

    def health_check(self) -> bool:
        """Verify Jikan API is reachable."""
        try:
            self.get("/anime", params={"q": "test", "limit": 1}, use_cache=False)
            return True
        except Exception:
            return False

    # ── Private Parsers ───────────────────────────────────────────────

    @staticmethod
    def _parse_anime(raw: dict[str, Any]) -> AnimeData:
        """Parse raw Jikan anime JSON into AnimeData model."""
        return AnimeData(
            mal_id=raw.get("mal_id", 0),
            title=raw.get("title", "Unknown"),
            title_english=raw.get("title_english"),
            title_japanese=raw.get("title_japanese"),
            synopsis=raw.get("synopsis"),
            score=raw.get("score"),
            scored_by=raw.get("scored_by"),
            rank=raw.get("rank"),
            popularity=raw.get("popularity"),
            episodes=raw.get("episodes"),
            status=raw.get("status"),
            rating=raw.get("rating"),
            source=raw.get("source"),
            duration=raw.get("duration"),
            season=raw.get("season"),
            year=raw.get("year"),
            genres=[g["name"] for g in raw.get("genres", [])],
            studios=[s["name"] for s in raw.get("studios", [])],
            themes=[t["name"] for t in raw.get("themes", [])],
            url=raw.get("url"),
            image_url=raw.get("images", {}).get("jpg", {}).get("large_image_url"),
            trailer_url=raw.get("trailer", {}).get("url"),
        )

    @staticmethod
    def _parse_manga(raw: dict[str, Any]) -> MangaData:
        """Parse raw Jikan manga JSON into MangaData model."""
        return MangaData(
            mal_id=raw.get("mal_id", 0),
            title=raw.get("title", "Unknown"),
            title_english=raw.get("title_english"),
            title_japanese=raw.get("title_japanese"),
            synopsis=raw.get("synopsis"),
            score=raw.get("score"),
            scored_by=raw.get("scored_by"),
            rank=raw.get("rank"),
            popularity=raw.get("popularity"),
            chapters=raw.get("chapters"),
            volumes=raw.get("volumes"),
            status=raw.get("status"),
            type=raw.get("type"),
            genres=[g["name"] for g in raw.get("genres", [])],
            authors=[a["name"] for a in raw.get("authors", [])],
            themes=[t["name"] for t in raw.get("themes", [])],
            url=raw.get("url"),
            image_url=raw.get("images", {}).get("jpg", {}).get("large_image_url"),
        )
