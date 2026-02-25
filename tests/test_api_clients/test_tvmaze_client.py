"""Unit tests for the TV Maze API client."""
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.api_clients.tvmaze_client import TVMazeClient
from app.models.api_schemas import TVShowData, TVEpisodeData, TVCastMember


@pytest.fixture
def tvmaze():
    """Create a TVMazeClient with caching disabled."""
    client = TVMazeClient(cache_ttl=0)
    yield client
    client.close()


class TestSearchShows:
    """Tests for TVMazeClient.search_shows."""

    def test_search_returns_show_list(self, tvmaze):
        mock_data = [
            {
                "score": 0.9,
                "show": {
                    "id": 169,
                    "name": "Breaking Bad",
                    "summary": "<p>A high school chemistry teacher.</p>",
                    "status": "Ended",
                    "rating": {"average": 9.3},
                    "genres": ["Drama", "Crime"],
                    "language": "English",
                    "premiered": "2008-01-20",
                    "network": {"name": "AMC"},
                    "image": {"medium": "https://img.jpg"},
                },
            }
        ]
        with patch.object(tvmaze, "get", return_value=mock_data):
            results = tvmaze.search_shows("Breaking Bad")

        assert len(results) == 1
        assert isinstance(results[0], TVShowData)
        assert results[0].name == "Breaking Bad"
        assert results[0].rating == 9.3
        # HTML should be stripped
        assert "<p>" not in (results[0].summary or "")

    def test_search_empty_results(self, tvmaze):
        with patch.object(tvmaze, "get", return_value=[]):
            results = tvmaze.search_shows("nonexistent12345")
        assert results == []

    def test_html_stripping_in_summary(self, tvmaze):
        mock_data = [
            {
                "score": 0.8,
                "show": {
                    "id": 1,
                    "name": "Test Show",
                    "summary": "<p>This is <b>bold</b> and <i>italic</i>.</p>",
                },
            }
        ]
        with patch.object(tvmaze, "get", return_value=mock_data):
            results = tvmaze.search_shows("test")

        assert "<" not in (results[0].summary or "")
        assert "bold" in (results[0].summary or "")


class TestGetShow:
    """Tests for TVMazeClient.get_show."""

    def test_get_show_returns_data(self, tvmaze):
        mock_data = {
            "id": 169,
            "name": "Breaking Bad",
            "summary": "<p>Chemistry teacher.</p>",
            "status": "Ended",
            "rating": {"average": 9.3},
            "genres": ["Drama"],
        }
        with patch.object(tvmaze, "get", return_value=mock_data):
            result = tvmaze.get_show(169)

        assert isinstance(result, TVShowData)
        assert result.name == "Breaking Bad"


class TestGetShowEpisodes:
    """Tests for TVMazeClient.get_show_episodes."""

    def test_episodes_returns_list(self, tvmaze):
        mock_data = [
            {
                "id": 1,
                "name": "Pilot",
                "season": 1,
                "number": 1,
                "summary": "<p>Walter White starts cooking.</p>",
                "airdate": "2008-01-20",
                "runtime": 58,
            },
            {
                "id": 2,
                "name": "Cat's in the Bag...",
                "season": 1,
                "number": 2,
                "summary": None,
            },
        ]
        with patch.object(tvmaze, "get", return_value=mock_data):
            results = tvmaze.get_show_episodes(169)

        assert len(results) == 2
        assert isinstance(results[0], TVEpisodeData)
        assert results[0].name == "Pilot"
        assert results[0].season == 1


class TestGetShowCast:
    """Tests for TVMazeClient.get_show_cast."""

    def test_cast_returns_members(self, tvmaze):
        mock_data = [
            {
                "person": {"id": 1, "name": "Bryan Cranston"},
                "character": {"id": 1, "name": "Walter White"},
            },
            {
                "person": {"id": 2, "name": "Aaron Paul"},
                "character": {"id": 2, "name": "Jesse Pinkman"},
            },
        ]
        with patch.object(tvmaze, "get", return_value=mock_data):
            results = tvmaze.get_show_cast(169)

        assert len(results) == 2
        assert isinstance(results[0], TVCastMember)
        assert results[0].person_name == "Bryan Cranston"
        assert results[0].character_name == "Walter White"


class TestHealthCheck:
    """Tests for TVMazeClient.health_check."""

    def test_health_check_success(self, tvmaze):
        mock_data = {"id": 1, "name": "Test"}
        with patch.object(tvmaze, "get", return_value=mock_data):
            assert tvmaze.health_check() is True

    def test_health_check_failure(self, tvmaze):
        with patch.object(tvmaze, "get", side_effect=Exception("down")):
            assert tvmaze.health_check() is False
