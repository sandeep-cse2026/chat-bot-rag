# Project Rules & Agent Guidelines

> These rules govern all code generation for the **Entertainment & Books RAG Chatbot** project.
> Every file produced MUST adhere to these standards without exception.

---

## 1. Language & Runtime

- **Python 3.11+** — use modern syntax (`match`, `type` unions `X | Y`, f-strings).
- **UTF-8** encoding everywhere.
- All files must end with a single trailing newline.
- Max line length: **100 characters** (soft limit), **120 characters** (hard limit).

---

## 2. Architecture & Design Patterns

### 2.1 Separation of Concerns
- **Routes** (`app/routes/`) — HTTP handling only. No business logic. Validate input, call service, return response.
- **Services** (`app/services/`) — Business logic and orchestration. No HTTP concerns.
- **API Clients** (`app/api_clients/`) — External API communication. No business logic.
- **Models** (`app/models/`) — Pydantic models for data validation. No behavior.
- **Prompts** (`app/prompts/`) — LLM prompt templates and tool definitions. No logic.

### 2.2 Dependency Injection
- Never hardcode dependencies. Pass services/clients via constructor (`__init__`).
- Use the Flask app factory pattern (`create_app()`).
- All services are initialized in the factory and attached to `app` or passed through context.

### 2.3 Single Responsibility
- Each class/module has ONE clear purpose.
- Functions should do one thing. If a function exceeds 30 lines, consider breaking it up.
- No god classes or god functions.

---

## 3. Pydantic & Type Safety

### 3.1 Pydantic v2 Conventions
- Use `pydantic.BaseModel` for ALL data structures crossing boundaries (API responses, request bodies, configs).
- Use `pydantic-settings` for configuration (`BaseSettings` with `.env` loading).
- Use `model_validator`, `field_validator` for complex validation — never validate manually.
- Use `Field(...)` with descriptions for all model fields used in API schemas.

### 3.2 Type Hints
- **Every** function signature must have full type hints (params + return type).
- Use `Optional[X]` or `X | None` for nullable fields.
- Use `list[str]` (lowercase) not `List[str]` (Python 3.11+).
- Use `dict[str, Any]` (lowercase) not `Dict[str, Any]`.
- Never use `Any` unless absolutely unavoidable — prefer specific types.

### 3.3 Example

```python
# ✅ CORRECT
def search_anime(self, query: str, limit: int = 5) -> list[AnimeData]:
    ...

# ❌ WRONG — missing types, using old-style
def search_anime(self, query, limit=5):
    ...
```

---

## 4. Error Handling

### 4.1 Custom Exceptions
- Define a custom exception hierarchy in `app/utils/exceptions.py`.
- Base: `ChatBotError` → `APIClientError`, `LLMServiceError`, `ValidationError`.
- Never catch bare `Exception` unless re-raising or logging.

### 4.2 API Client Errors
- Raise `APIClientError` with the original status code, URL, and response body.
- Always handle HTTP 429 (rate limit) with exponential backoff retry.
- Handle HTTP 404 gracefully — return `None` or empty result, don't crash.
- Timeout errors must be caught and wrapped in `APIClientError`.

### 4.3 Flask Error Handlers
- Register global error handlers for 400, 404, 422, 500.
- Always return JSON error responses with `{"error": "message", "status_code": N}`.
- Never expose stack traces in production responses.

### 4.4 Pattern

```python
# ✅ CORRECT
try:
    response = self.client.get(endpoint, params=params)
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        # retry logic
        ...
    raise APIClientError(f"Jikan API error: {e.response.status_code}") from e
except httpx.TimeoutException as e:
    raise APIClientError(f"Jikan API timeout: {endpoint}") from e

# ❌ WRONG — swallowing errors silently
try:
    response = self.client.get(endpoint)
except:
    return None
```

---

## 5. HTTP Client Best Practices

### 5.1 Connection Management
- Use `httpx.Client()` (sync) as a persistent session — do NOT create a new client per request.
- Set explicit `timeout=httpx.Timeout(connect=5.0, read=25.0)`.
- Set a descriptive `User-Agent` header on all clients.
- Close clients properly using context managers or explicit `.close()`.

### 5.2 Rate Limiting
- Implement per-client rate limiting using `time.monotonic()` and `time.sleep()`.
- Jikan: max 3 req/sec → enforce 0.4s minimum delay between requests.
- TV Maze: max 20 req/10sec → enforce 0.5s minimum delay.
- Open Library: max 1 req/sec (default) → enforce 1.0s minimum delay.

### 5.3 Retry Logic
- Retry on: HTTP 429, 500, 502, 503, 504.
- Use exponential backoff: `delay = base_delay * (2 ** attempt)` with jitter.
- Max retries: 3.
- Never retry on: 400, 401, 403, 404, 422.

---

## 6. LLM / OpenRouter Integration

### 6.1 Function Calling
- Define all tools using the OpenAI-compatible `tools` schema format.
- Tool descriptions MUST be clear and specific — the LLM uses them to decide which tool to call.
- Always set `"tool_choice": "auto"` — let the LLM decide.
- Handle the function calling loop: LLM → tool call → execute → send result → LLM → response.
- Limit tool-calling iterations to **3 max** to prevent infinite loops.

### 6.2 Conversation History
- Maintain per-session conversation history as a list of `{"role": ..., "content": ...}` dicts.
- Cap history at 20 messages (configurable) — use sliding window, always keep the system prompt.
- Include `tool` role messages when sending tool results back.

### 6.3 Prompt Engineering
- System prompt must clearly define the bot's capabilities and boundaries.
- Include explicit instructions to ALWAYS use tools for data — never fabricate.
- Include formatting guidelines (use ★ for ratings, bullet points for lists, etc.).

---

## 7. Flask & Web Application

### 7.1 Flask Patterns
- Use the **application factory** pattern (`create_app()`).
- Use **Blueprints** for route organization.
- Use `flask.jsonify()` for all JSON responses.
- Validate all incoming request data with Pydantic before processing.

### 7.2 API Response Format
- All API responses must follow a consistent schema:

```json
{
  "success": true,
  "data": { "response": "...", "session_id": "..." },
  "error": null
}
```

- Error responses:

```json
{
  "success": false,
  "data": null,
  "error": { "message": "...", "code": 400 }
}
```

### 7.3 Security
- Set `SECRET_KEY` from environment variable — never hardcode.
- Sanitize all user input before passing to the LLM.
- Strip any HTML tags from API responses before including in LLM context.
- Set proper CORS headers if needed.
- Never log sensitive data (API keys, full request bodies with PII).

---

## 8. Code Style & Formatting

### 8.1 Naming Conventions
| Element | Convention | Example |
|---------|-----------|---------|
| Files/modules | `snake_case` | `jikan_client.py` |
| Classes | `PascalCase` | `JikanClient` |
| Functions/methods | `snake_case` | `search_anime()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Private methods | `_leading_underscore` | `_rate_limit_wait()` |
| Pydantic models | `PascalCase` + `Data`/`Request`/`Response` suffix | `AnimeData`, `ChatRequest` |

### 8.2 Imports
- Order: stdlib → third-party → local (separated by blank lines).
- Use absolute imports, never relative.
- Group imports logically within each section.

```python
# ✅ CORRECT
import time
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import Settings
from app.utils.exceptions import APIClientError
```

### 8.3 Docstrings
- All public classes and functions MUST have docstrings.
- Use Google-style docstrings.

```python
def search_anime(self, query: str, limit: int = 5) -> list[AnimeData]:
    """Search for anime by name or keyword.

    Args:
        query: Search term (anime title, keyword, etc.).
        limit: Maximum number of results to return (1-25).

    Returns:
        List of AnimeData objects matching the query.

    Raises:
        APIClientError: If the Jikan API request fails.
    """
```

---

## 9. Logging

- Use `structlog` for structured JSON logging.
- Log levels: `DEBUG` for development, `INFO` for production.
- Log every external API call with: endpoint, params, status code, response time.
- Log every LLM call with: model, token count (if available), response time.
- Never log API keys, secrets, or full response bodies (truncate if needed).
- Use `logger = structlog.get_logger(__name__)` at module level.

```python
logger.info("api_request", client="jikan", endpoint="/anime", query=query, status=200, duration_ms=145)
```

---

## 10. Docker & Deployment

### 10.1 Dockerfile Rules
- Use **multi-stage builds** (builder → runtime).
- Use `python:3.11-slim` as base — never `python:3.11` (full).
- Run as **non-root user** in production.
- Use `--no-cache-dir` with pip to reduce image size.
- Add a `HEALTHCHECK` instruction.
- Use `gunicorn` as the WSGI server — never Flask dev server in production.

### 10.2 Environment Variables
- All secrets must come from environment variables (`.env` file or Docker env).
- Never commit `.env` files — only `.env.example` with placeholder values.
- Validate all required env vars at startup (Pydantic Settings will handle this).

---

## 11. Testing

- All API clients must have unit tests with **mocked HTTP responses** (use `pytest-mock` or `respx`).
- Test both success and error paths (200, 404, 429, 500, timeout).
- Test Pydantic models with valid and invalid data.
- Use `pytest` fixtures for shared test setup.
- Aim for **>80% code coverage** on the `app/` directory.
- Test files mirror source structure: `app/api_clients/jikan_client.py` → `tests/test_api_clients/test_jikan_client.py`.

---

## 12. Git & Version Control

- Commit messages: `type: short description` (e.g., `feat: add jikan api client`, `fix: handle 429 rate limit`).
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`.
- Never commit: `.env`, `__pycache__/`, `.pyc`, `*.egg-info`, `.vscode/`, `.idea/`.

---

## 13. Performance & Production Optimization

- Use connection pooling (httpx client reuse) — never create clients per-request.
- Implement response caching for repeated identical queries (optional, in-memory dict with TTL).
- Keep LLM context window small — trim conversation history when it exceeds the max.
- Minimize API calls — use search results before making detail calls unless needed.
- Use `gunicorn` with `--workers 2 --threads 4` for production concurrency.
