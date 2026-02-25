# Python Style Guide — Project-Specific

> Quick reference for code patterns used throughout this project.

---

## Pydantic Model Patterns

### Request Models
```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """Incoming chat message from the user."""
    message: str = Field(..., min_length=1, max_length=2000, description="User's chat message")
    session_id: str = Field(..., description="Unique session identifier (UUID)")
```

### Response Models
```python
class ChatResponse(BaseModel):
    """Outgoing chat response to the user."""
    response: str = Field(..., description="Bot's response message")
    session_id: str = Field(..., description="Session identifier")
    tools_used: list[str] = Field(default_factory=list, description="APIs called during this request")
```

### API Data Models
```python
class AnimeData(BaseModel):
    """Parsed anime data from Jikan API."""
    mal_id: int
    title: str
    title_english: str | None = None
    synopsis: str | None = None
    score: float | None = None
    episodes: int | None = None
    status: str
    genres: list[str] = Field(default_factory=list)
    url: str

    @classmethod
    def from_api_response(cls, data: dict) -> "AnimeData":
        """Factory method to parse raw Jikan API response into structured model."""
        return cls(
            mal_id=data["mal_id"],
            title=data["title"],
            title_english=data.get("title_english"),
            synopsis=data.get("synopsis"),
            score=data.get("score"),
            episodes=data.get("episodes"),
            status=data.get("status", "Unknown"),
            genres=[g["name"] for g in data.get("genres", [])],
            url=data.get("url", ""),
        )
```

---

## API Client Pattern

```python
import time
import httpx
import structlog
from app.api_clients.base_client import BaseAPIClient
from app.utils.exceptions import APIClientError

logger = structlog.get_logger(__name__)


class JikanClient(BaseAPIClient):
    """Client for the Jikan (MyAnimeList) API v4."""

    def __init__(self, base_url: str, rate_limit: float, timeout: int):
        super().__init__(base_url=base_url, rate_limit=rate_limit, timeout=timeout)

    def search_anime(self, query: str, limit: int = 5) -> list[dict]:
        """Search for anime by name.

        Args:
            query: Search term.
            limit: Max results (1-25).

        Returns:
            List of anime data dictionaries.

        Raises:
            APIClientError: If API request fails.
        """
        params = {"q": query, "limit": min(limit, 25), "sfw": True}
        response = self._request("GET", "/anime", params=params)
        return response.get("data", [])
```

---

## Service Pattern

```python
class ChatOrchestrator:
    """Orchestrates the conversation flow between the user, LLM, and API tools."""

    def __init__(self, llm_service: LLMService, tool_router: ToolRouter):
        self.llm_service = llm_service
        self.tool_router = tool_router
        self._conversations: dict[str, list[dict]] = {}

    def process_message(self, session_id: str, user_message: str) -> str:
        """Process a user message and return the bot's response.

        Args:
            session_id: Unique session identifier.
            user_message: The user's message text.

        Returns:
            The bot's response text.
        """
        ...
```

---

## Route / Blueprint Pattern

```python
from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from app.models.requests import ChatRequest

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat():
    """Process a chat message."""
    try:
        body = ChatRequest.model_validate(request.get_json())
    except ValidationError as e:
        return jsonify({"success": False, "error": {"message": str(e), "code": 422}}), 422

    orchestrator = current_app.config["ORCHESTRATOR"]
    response_text = orchestrator.process_message(body.session_id, body.message)

    return jsonify({
        "success": True,
        "data": {"response": response_text, "session_id": body.session_id},
    })
```

---

## Exception Hierarchy

```python
class ChatBotError(Exception):
    """Base exception for the chatbot application."""

class APIClientError(ChatBotError):
    """Raised when an external API call fails."""
    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)

class LLMServiceError(ChatBotError):
    """Raised when the LLM API call fails."""

class ToolExecutionError(ChatBotError):
    """Raised when a tool/function call fails during orchestration."""
```

---

## Test Pattern

```python
import pytest
from unittest.mock import MagicMock, patch

class TestJikanClient:
    """Tests for JikanClient."""

    @pytest.fixture
    def client(self):
        return JikanClient(base_url="https://api.jikan.moe/v4", rate_limit=1.0, timeout=10)

    @pytest.fixture
    def mock_response(self):
        return {
            "data": [
                {"mal_id": 20, "title": "Naruto", "score": 8.0, ...}
            ]
        }

    def test_search_anime_success(self, client, mock_response):
        with patch.object(client, "_request", return_value=mock_response):
            results = client.search_anime("Naruto", limit=5)
            assert len(results) == 1
            assert results[0]["title"] == "Naruto"

    def test_search_anime_empty_query(self, client):
        with pytest.raises(ValueError):
            client.search_anime("", limit=5)
```
