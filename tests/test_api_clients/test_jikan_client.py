"""Unit tests for the Jikan API client."""
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.api_clients.jikan_client import JikanClient
from app.models.api_schemas import AnimeData, MangaData


@pytest.fixture
def jikan():
    """Create a JikanClient with caching disabled."""
    client = JikanClient(cache_ttl=0)
    yield client
    client.close()


class TestSearchAnime:
    """Tests for JikanClient.search_anime."""

    def test_search_returns_anime_list(self, jikan):
        mock_data = {
            "data": [
                {
                    "mal_id": 20,
                    "title": "Naruto",
                    "synopsis": "Naruto Uzumaki wants to be Hokage.",
                    "score": 8.0,
                    "episodes": 220,
                    "status": "Finished Airing",
                    "type": "TV",
                    "genres": [{"name": "Action"}, {"name": "Adventure"}],
                    "studios": [{"name": "Pierrot"}],
                    "images": {"jpg": {"large_image_url": "https://img.jpg"}},
                }
            ]
        }
        with patch.object(jikan, "get", return_value=mock_data):
            results = jikan.search_anime("Naruto", limit=5)

        assert len(results) == 1
        assert isinstance(results[0], AnimeData)
        assert results[0].title == "Naruto"
        assert results[0].mal_id == 20
        assert results[0].score == 8.0
        assert results[0].episodes == 220
        assert "Action" in results[0].genres

    def test_search_empty_results(self, jikan):
        with patch.object(jikan, "get", return_value={"data": []}):
            results = jikan.search_anime("nonexistent12345")
        assert results == []

    def test_search_passes_limit_to_api(self, jikan):
        mock_data = {"data": [{"mal_id": 1, "title": "Anime 1"}]}
        with patch.object(jikan, "get", return_value=mock_data) as mock_get:
            jikan.search_anime("test", limit=3)
        # Verify limit param gets passed to the API call
        call_args = mock_get.call_args
        assert call_args[1]["params"]["limit"] == 3 or call_args[0][1].get("limit") == 3


class TestGetAnimeById:
    """Tests for JikanClient.get_anime_by_id."""

    def test_get_anime_returns_data(self, jikan):
        mock_data = {
            "data": {
                "mal_id": 1,
                "title": "Cowboy Bebop",
                "synopsis": "Space bounty hunters.",
                "score": 8.78,
                "episodes": 26,
                "status": "Finished Airing",
                "type": "TV",
                "genres": [{"name": "Sci-Fi"}],
                "studios": [{"name": "Sunrise"}],
            }
        }
        with patch.object(jikan, "get", return_value=mock_data):
            result = jikan.get_anime_by_id(1)

        assert isinstance(result, AnimeData)
        assert result.title == "Cowboy Bebop"
        assert result.score == 8.78

    def test_get_anime_none_on_missing(self, jikan):
        # When no "data" key exists, should return None
        with patch.object(jikan, "get", return_value={}):
            result = jikan.get_anime_by_id(99999)
        assert result is None


class TestSearchManga:
    """Tests for JikanClient.search_manga."""

    def test_search_returns_manga_list(self, jikan):
        mock_data = {
            "data": [
                {
                    "mal_id": 13,
                    "title": "One Piece",
                    "synopsis": "Gol D. Roger was known...",
                    "score": 9.2,
                    "chapters": None,
                    "volumes": None,
                    "status": "Publishing",
                    "type": "Manga",
                    "genres": [{"name": "Action"}],
                    "authors": [{"name": "Oda, Eiichiro"}],
                }
            ]
        }
        with patch.object(jikan, "get", return_value=mock_data):
            results = jikan.search_manga("One Piece")

        assert len(results) == 1
        assert isinstance(results[0], MangaData)
        assert results[0].title == "One Piece"


class TestGetTopAnime:
    """Tests for JikanClient.get_top_anime."""

    def test_top_anime_returns_list(self, jikan):
        mock_data = {
            "data": [
                {"mal_id": 1, "title": "Top Anime 1", "score": 9.5},
                {"mal_id": 2, "title": "Top Anime 2", "score": 9.4},
            ]
        }
        with patch.object(jikan, "get", return_value=mock_data):
            results = jikan.get_top_anime(limit=2)

        assert len(results) == 2
        assert results[0].title == "Top Anime 1"


class TestHealthCheck:
    """Tests for JikanClient.health_check."""

    def test_health_check_success(self, jikan):
        with patch.object(jikan, "get", return_value={"data": []}):
            assert jikan.health_check() is True

    def test_health_check_failure(self, jikan):
        with patch.object(jikan, "get", side_effect=Exception("timeout")):
            assert jikan.health_check() is False
