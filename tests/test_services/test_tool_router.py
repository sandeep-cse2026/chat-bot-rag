"""Unit tests for the Tool Router."""
import json
from unittest.mock import MagicMock

import pytest

from app.api_clients.jikan_client import JikanClient
from app.api_clients.tvmaze_client import TVMazeClient
from app.api_clients.openlibrary_client import OpenLibraryClient
from app.models.api_schemas import AnimeData, TVShowData, BookData
from app.services.tool_router import ToolRouter
from app.utils.exceptions import ToolExecutionError


@pytest.fixture
def mock_clients():
    """Create mock API clients."""
    jikan = MagicMock(spec=JikanClient)
    tvmaze = MagicMock(spec=TVMazeClient)
    openlibrary = MagicMock(spec=OpenLibraryClient)
    return jikan, tvmaze, openlibrary


@pytest.fixture
def router(mock_clients):
    """Create a ToolRouter with mock clients."""
    return ToolRouter(*mock_clients)


class TestAvailableTools:
    """Tests for ToolRouter.available_tools."""

    def test_has_13_tools(self, router):
        assert len(router.available_tools) == 13

    def test_contains_all_expected_tools(self, router):
        expected = [
            "search_anime", "get_anime_details", "search_manga",
            "get_manga_details", "get_top_anime", "get_seasonal_anime",
            "search_tv_shows", "get_tv_show_details", "get_tv_episode",
            "get_tv_schedule", "search_books", "get_book_by_isbn",
            "search_authors",
        ]
        for tool in expected:
            assert tool in router.available_tools


class TestExecute:
    """Tests for ToolRouter.execute."""

    def test_search_anime_routes_correctly(self, router, mock_clients):
        jikan, _, _ = mock_clients
        anime = AnimeData(mal_id=1, title="Naruto", score=8.0)
        jikan.search_anime.return_value = [anime]

        result = router.execute("search_anime", {"query": "Naruto", "limit": 5})
        data = json.loads(result)

        jikan.search_anime.assert_called_once_with(query="Naruto", limit=5)
        assert data["count"] == 1
        assert data["results"][0]["title"] == "Naruto"

    def test_get_anime_details_maps_arg(self, router, mock_clients):
        jikan, _, _ = mock_clients
        anime = AnimeData(mal_id=20, title="Naruto")
        jikan.get_anime_by_id.return_value = anime

        result = router.execute("get_anime_details", {"anime_id": 20})
        data = json.loads(result)

        jikan.get_anime_by_id.assert_called_once_with(anime_id=20)
        assert data["title"] == "Naruto"

    def test_search_tv_shows_routes(self, router, mock_clients):
        _, tvmaze, _ = mock_clients
        show = TVShowData(id=169, name="Breaking Bad")
        tvmaze.search_shows.return_value = [show]

        result = router.execute("search_tv_shows", {"query": "Breaking Bad"})
        data = json.loads(result)

        tvmaze.search_shows.assert_called_once_with(query="Breaking Bad")
        assert data["count"] == 1

    def test_search_books_routes(self, router, mock_clients):
        _, _, openlibrary = mock_clients
        book = BookData(title="1984", key="/works/OL1")
        openlibrary.search_books.return_value = [book]

        result = router.execute("search_books", {"query": "1984", "limit": 5})
        data = json.loads(result)

        openlibrary.search_books.assert_called_once_with(query="1984", limit=5)
        assert data["count"] == 1

    def test_unknown_tool_raises(self, router):
        with pytest.raises(ToolExecutionError, match="Unknown tool"):
            router.execute("nonexistent_tool", {})

    def test_empty_list_result(self, router, mock_clients):
        jikan, _, _ = mock_clients
        jikan.search_anime.return_value = []

        result = router.execute("search_anime", {"query": "nothing"})
        data = json.loads(result)

        assert data["count"] == 0
        assert "No results" in data["result"]

    def test_none_result(self, router, mock_clients):
        jikan, _, _ = mock_clients
        jikan.get_anime_by_id.return_value = None

        result = router.execute("get_anime_details", {"anime_id": 99999})
        data = json.loads(result)

        assert "No results" in data["result"]

    def test_client_exception_wraps_in_tool_error(self, router, mock_clients):
        jikan, _, _ = mock_clients
        jikan.search_anime.side_effect = Exception("Connection failed")

        with pytest.raises(ToolExecutionError):
            router.execute("search_anime", {"query": "test"})
