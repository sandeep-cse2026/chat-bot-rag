"""Unit tests for the Open Library API client."""
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.api_clients.openlibrary_client import OpenLibraryClient
from app.models.api_schemas import BookData, AuthorData


@pytest.fixture
def openlibrary():
    """Create an OpenLibraryClient with caching disabled."""
    client = OpenLibraryClient(cache_ttl=0)
    yield client
    client.close()


class TestSearchBooks:
    """Tests for OpenLibraryClient.search_books."""

    def test_search_returns_book_list(self, openlibrary):
        mock_data = {
            "num_found": 1,
            "docs": [
                {
                    "key": "/works/OL1234W",
                    "title": "The Lord of the Rings",
                    "author_name": ["J.R.R. Tolkien"],
                    "first_publish_year": 1954,
                    "isbn": ["9780618640157"],
                    "subject": ["Fantasy", "Adventure"],
                    "cover_i": 12345,
                    "number_of_pages_median": 1200,
                    "language": ["eng"],
                }
            ],
        }
        with patch.object(openlibrary, "get", return_value=mock_data):
            results = openlibrary.search_books("lord of the rings", limit=5)

        assert len(results) == 1
        assert isinstance(results[0], BookData)
        assert results[0].title == "The Lord of the Rings"
        assert "J.R.R. Tolkien" in results[0].author_name

    def test_search_empty_results(self, openlibrary):
        with patch.object(openlibrary, "get", return_value={"num_found": 0, "docs": []}):
            results = openlibrary.search_books("nonexistent12345")
        assert results == []

    def test_search_passes_limit_to_api(self, openlibrary):
        mock_data = {
            "num_found": 1,
            "docs": [{"key": "/works/OL1W", "title": "Book 1"}],
        }
        with patch.object(openlibrary, "get", return_value=mock_data) as mock_get:
            openlibrary.search_books("test", limit=3)
        call_args = mock_get.call_args
        assert call_args[1]["params"]["limit"] == 3 or 3 in str(call_args)


class TestSearchAuthors:
    """Tests for OpenLibraryClient.search_authors."""

    def test_search_returns_author_list(self, openlibrary):
        mock_data = {
            "num_found": 1,
            "docs": [
                {
                    "key": "/authors/OL1234A",
                    "name": "J.R.R. Tolkien",
                    "birth_date": "3 January 1892",
                    "top_work": "The Lord of the Rings",
                    "work_count": 100,
                }
            ],
        }
        with patch.object(openlibrary, "get", return_value=mock_data):
            results = openlibrary.search_authors("Tolkien", limit=5)

        assert len(results) == 1
        assert isinstance(results[0], AuthorData)
        assert results[0].name == "J.R.R. Tolkien"

    def test_search_empty_results(self, openlibrary):
        with patch.object(openlibrary, "get", return_value={"num_found": 0, "docs": []}):
            results = openlibrary.search_authors("nonexistent12345")
        assert results == []


class TestGetEditionByIsbn:
    """Tests for OpenLibraryClient.get_edition_by_isbn."""

    def test_returns_edition_data(self, openlibrary):
        mock_data = {
            "key": "/books/OL1234M",
            "title": "1984",
            "isbn_13": ["9780451524935"],
            "publishers": ["Signet Classic"],
            "publish_date": "1961",
            "number_of_pages": 328,
            "covers": [12345],
            "authors": [{"key": "/authors/OL1234A"}],
        }
        with patch.object(openlibrary, "get", return_value=mock_data):
            result = openlibrary.get_edition_by_isbn("9780451524935")

        assert result is not None
        assert result.title == "1984"

    def test_returns_none_on_error_response(self, openlibrary):
        with patch.object(openlibrary, "get", return_value={"error": "notfound"}):
            result = openlibrary.get_edition_by_isbn("0000000000")
        assert result is None


class TestCoverUrl:
    """Tests for OpenLibraryClient.get_cover_url (static method)."""

    def test_cover_url_default_book(self):
        url = OpenLibraryClient.get_cover_url(12345)
        assert "12345" in url
        assert "-M.jpg" in url
        assert "/b/id/" in url

    def test_cover_url_large_author(self):
        url = OpenLibraryClient.get_cover_url(67890, cover_type="a", size="L")
        assert "67890" in url
        assert "-L.jpg" in url
        assert "/a/id/" in url


class TestHealthCheck:
    """Tests for OpenLibraryClient.health_check."""

    def test_health_check_success(self, openlibrary):
        with patch.object(openlibrary, "get", return_value={"num_found": 1, "docs": [{"key": "test"}]}):
            assert openlibrary.health_check() is True

    def test_health_check_failure(self, openlibrary):
        with patch.object(openlibrary, "get", side_effect=Exception("down")):
            assert openlibrary.health_check() is False
