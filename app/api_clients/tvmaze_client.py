"""TV Maze API client for TV show data.

TV Maze provides free TV show data including shows, episodes, cast, and schedules.
Base URL: https://api.tvmaze.com
Rate Limit: 20 requests per 10 seconds per IP
Auth: None required

Note: TV Maze returns HTML in summary fields. All summaries are automatically
stripped of HTML tags via the sanitizer utility.

Implements all endpoints defined in the plan:
- search_shows, get_show, get_show_with_details
- get_show_episodes, get_show_cast
- get_episode_by_number, get_schedule, search_people
"""
from __future__ import annotations

from typing import Any

import structlog

from app.api_clients.base_client import BaseAPIClient
from app.models.api_schemas import (
    TVCastMember,
    TVEpisodeData,
    TVPersonData,
    TVScheduleEntry,
    TVShowData,
)
from app.utils.sanitizer import strip_html

logger = structlog.get_logger(__name__)


class TVMazeClient(BaseAPIClient):
    """Client for the TV Maze API."""

    def __init__(
        self,
        base_url: str = "https://api.tvmaze.com",
        rate_limit: float = 0.5,
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

    # ── Show Endpoints ────────────────────────────────────────────────

    def search_shows(self, query: str) -> list[TVShowData]:
        """Fuzzy search for TV shows.

        Args:
            query: Search query string.

        Returns:
            List of TVShowData objects (limited to top 10).
        """
        results = self.get("/search/shows", params={"q": query})
        # TV Maze search returns [{score, show}, ...]
        shows = [item.get("show", {}) for item in results[:10]] if isinstance(results, list) else []
        return [self._parse_show(show) for show in shows]

    def get_show(self, show_id: int) -> TVShowData | None:
        """Get show details by ID.

        Args:
            show_id: TV Maze show ID.

        Returns:
            TVShowData or None if not found.
        """
        data = self.get(f"/shows/{show_id}")
        return self._parse_show(data) if data else None

    def get_show_with_details(self, show_id: int) -> dict[str, Any]:
        """Get show with embedded episodes and cast.

        Args:
            show_id: TV Maze show ID.

        Returns:
            Dict with 'show', 'episodes', and 'cast' keys.
        """
        data = self.get(f"/shows/{show_id}", params={"embed[]": ["episodes", "cast"]})
        show = self._parse_show(data)

        embedded = data.get("_embedded", {})

        episodes = [
            self._parse_episode(ep)
            for ep in embedded.get("episodes", [])[:20]  # Limit episodes
        ]

        cast = [
            self._parse_cast_member(member)
            for member in embedded.get("cast", [])[:10]  # Limit cast
        ]

        return {
            "show": show,
            "episodes": episodes,
            "cast": cast,
        }

    # ── Episode Endpoints ─────────────────────────────────────────────

    def get_show_episodes(self, show_id: int) -> list[TVEpisodeData]:
        """Get all episodes of a show.

        Args:
            show_id: TV Maze show ID.

        Returns:
            List of TVEpisodeData (limited to 50 per response for LLM context).
        """
        data = self.get(f"/shows/{show_id}/episodes")
        episodes = data if isinstance(data, list) else []
        return [self._parse_episode(ep) for ep in episodes[:50]]

    def get_episode_by_number(
        self, show_id: int, season: int, episode: int
    ) -> TVEpisodeData | None:
        """Get a specific episode by season and episode number.

        Args:
            show_id: TV Maze show ID.
            season: Season number.
            episode: Episode number.

        Returns:
            TVEpisodeData or None if not found.
        """
        data = self.get(
            f"/shows/{show_id}/episodebynumber",
            params={"season": season, "number": episode},
        )
        return self._parse_episode(data) if data else None

    # ── Cast Endpoint ─────────────────────────────────────────────────

    def get_show_cast(self, show_id: int) -> list[TVCastMember]:
        """Get main cast of a show.

        Args:
            show_id: TV Maze show ID.

        Returns:
            List of TVCastMember objects (limited to top 15).
        """
        data = self.get(f"/shows/{show_id}/cast")
        cast_list = data if isinstance(data, list) else []
        return [self._parse_cast_member(member) for member in cast_list[:15]]

    # ── Schedule Endpoint ─────────────────────────────────────────────

    def get_schedule(self, country: str = "US", date: str | None = None) -> list[TVScheduleEntry]:
        """Get TV schedule for a country and date.

        Args:
            country: ISO 3166-1 country code (default: "US").
            date: Date string in YYYY-MM-DD format (default: today).

        Returns:
            List of TVScheduleEntry objects (limited to 20).
        """
        params: dict[str, Any] = {"country": country}
        if date:
            params["date"] = date

        data = self.get("/schedule", params=params)
        entries = data if isinstance(data, list) else []
        return [
            TVScheduleEntry(
                show_name=entry.get("show", {}).get("name", "Unknown"),
                episode_name=entry.get("name"),
                season=entry.get("season"),
                number=entry.get("number"),
                airtime=entry.get("airtime"),
                network=entry.get("show", {}).get("network", {}).get("name") if entry.get("show", {}).get("network") else None,
            )
            for entry in entries[:20]
        ]

    # ── People Endpoint ───────────────────────────────────────────────

    def search_people(self, query: str) -> list[TVPersonData]:
        """Search for actors/crew.

        Args:
            query: Search query.

        Returns:
            List of TVPersonData objects (limited to 10).
        """
        results = self.get("/search/people", params={"q": query})
        people = [item.get("person", {}) for item in results[:10]] if isinstance(results, list) else []
        return [
            TVPersonData(
                id=person.get("id", 0),
                name=person.get("name", "Unknown"),
                birthday=person.get("birthday"),
                country=person.get("country", {}).get("name") if person.get("country") else None,
                image_url=person.get("image", {}).get("medium") if person.get("image") else None,
                url=person.get("url"),
            )
            for person in people
        ]

    # ── Health Check ──────────────────────────────────────────────────

    def health_check(self) -> bool:
        """Verify TV Maze API is reachable."""
        try:
            self.get("/shows/1", use_cache=False)
            return True
        except Exception:
            return False

    # ── Private Parsers ───────────────────────────────────────────────

    @staticmethod
    def _parse_show(raw: dict[str, Any]) -> TVShowData:
        """Parse raw TV Maze show JSON into TVShowData model."""
        network = raw.get("network", {})
        schedule = raw.get("schedule", {})
        rating = raw.get("rating", {})

        return TVShowData(
            id=raw.get("id", 0),
            name=raw.get("name", "Unknown"),
            summary=strip_html(raw.get("summary")),  # Strip HTML!
            genres=raw.get("genres", []),
            status=raw.get("status"),
            premiered=raw.get("premiered"),
            ended=raw.get("ended"),
            rating=rating.get("average") if isinstance(rating, dict) else None,
            network=network.get("name") if isinstance(network, dict) else None,
            schedule_time=schedule.get("time") if isinstance(schedule, dict) else None,
            schedule_days=schedule.get("days", []) if isinstance(schedule, dict) else [],
            runtime=raw.get("runtime"),
            language=raw.get("language"),
            type=raw.get("type"),
            url=raw.get("url"),
            image_url=raw.get("image", {}).get("medium") if raw.get("image") else None,
        )

    @staticmethod
    def _parse_episode(raw: dict[str, Any]) -> TVEpisodeData:
        """Parse raw TV Maze episode JSON into TVEpisodeData model."""
        return TVEpisodeData(
            id=raw.get("id", 0),
            name=raw.get("name", "Unknown"),
            season=raw.get("season", 0),
            number=raw.get("number"),
            airdate=raw.get("airdate"),
            runtime=raw.get("runtime"),
            summary=strip_html(raw.get("summary")),
            url=raw.get("url"),
        )

    @staticmethod
    def _parse_cast_member(raw: dict[str, Any]) -> TVCastMember:
        """Parse raw TV Maze cast JSON into TVCastMember model."""
        person = raw.get("person", {})
        character = raw.get("character", {})
        return TVCastMember(
            person_name=person.get("name", "Unknown"),
            character_name=character.get("name"),
            person_image_url=person.get("image", {}).get("medium") if person.get("image") else None,
        )
