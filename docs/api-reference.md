# EntertainBot — API Reference

## Overview

EntertainBot exposes a simple REST API for the chat frontend and health monitoring. All responses use JSON with a consistent structure.

---

## Base URL

```
http://localhost:5000
```

---

## Endpoints

### 1. Chat UI

```
GET /
```

Renders the EntertainBot terminal UI (HTML page).

**Response:** HTML page

---

### 2. Send Message

```
POST /chat
```

Process a user message through the AI orchestrator and return the response.

**Request Body:**
```json
{
  "message": "Tell me about Naruto",
  "session_id": "abc-123"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | ✅ | User's message (1–2000 chars) |
| `session_id` | string | ❌ | Session ID for conversation continuity. Auto-generated if omitted. |

**Success Response (200):**
```json
{
  "success": true,
  "response": "## Naruto ナルト\n\n**Score:** ★ 8.25/10...",
  "session_id": "abc-123"
}
```

**Error Responses:**

| Code | Cause |
|---|---|
| 400 | Invalid JSON body |
| 422 | Validation error (empty message, too long, etc.) |
| 500 | Internal processing error |

```json
{
  "success": false,
  "error": {
    "message": "Failed to process your message. Please try again.",
    "code": 500
  }
}
```

---

### 3. Clear Session

```
POST /chat/clear
```

Clear a session's conversation history and ChromaDB context.

**Request Body:**
```json
{
  "session_id": "abc-123"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Session cleared"
}
```

---

### 4. Health Check

```
GET /health
```

Returns system health status including all external API connectivity and ChromaDB stats.

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2025-02-28T22:00:00Z",
  "services": {
    "jikan": { "status": "healthy", "response_time_ms": 150 },
    "tvmaze": { "status": "healthy", "response_time_ms": 80 },
    "openlibrary": { "status": "healthy", "response_time_ms": 200 },
    "llm": { "status": "healthy", "model": "google/gemini-2.0-flash-001" }
  },
  "context_db": {
    "collection_name": "conversations",
    "document_count": 42
  },
  "active_sessions": 3
}
```

---

### 5. Conversation Logs

```
GET /logs
```

Returns available conversation log files and their metadata.

---

## Error Response Format

All error responses follow this structure:

```json
{
  "success": false,
  "error": {
    "message": "Human-readable error description",
    "code": 400
  }
}
```

| HTTP Code | Error Type |
|---|---|
| 400 | Bad request / Invalid JSON |
| 404 | Route not found |
| 405 | Method not allowed |
| 422 | Validation error |
| 429 | Rate limit exceeded |
| 500 | Internal server error |
| 502 | Upstream API / LLM failure |
| 504 | Upstream API timeout |

---

## LLM Tool Definitions (Internal)

The following 13 tools are defined in `app/prompts/templates.py` and sent to the LLM as function schemas. Users don't call these directly — the LLM decides when to use them.

### Anime & Manga (Jikan API)

#### `search_anime`
Search for anime by name.
```json
{
  "query": "Death Note",
  "limit": 5
}
```

#### `get_anime_details`
Get detailed anime information by MAL ID.
```json
{
  "anime_id": 1535
}
```

#### `search_manga`
Search for manga by name.
```json
{
  "query": "One Piece",
  "limit": 5
}
```

#### `get_manga_details`
Get detailed manga information by MAL ID.
```json
{
  "manga_id": 13
}
```

#### `get_top_anime`
Get top anime lists.
```json
{
  "filter": "airing",
  "limit": 10
}
```
Filters: `airing`, `upcoming`, `bypopularity`, `favorite`

#### `get_seasonal_anime`
Get anime airing in a specific season.
```json
{
  "year": 2025,
  "season": "winter",
  "limit": 10
}
```
Seasons: `winter`, `spring`, `summer`, `fall`

---

### TV Shows (TV Maze API)

#### `search_tv_shows`
Search for TV shows by name.
```json
{
  "query": "Breaking Bad"
}
```

#### `get_tv_show_details`
Get detailed show info including cast.
```json
{
  "show_id": 169
}
```

#### `get_tv_episode`
Get a specific episode by season and episode number.
```json
{
  "show_id": 169,
  "season": 5,
  "number": 16
}
```

#### `get_tv_schedule`
Get TV schedule for a specific date.
```json
{
  "date": "2025-02-28",
  "country": "US"
}
```

---

### Books (Open Library API)

#### `search_books`
Search for books by title or query.
```json
{
  "query": "1984 George Orwell",
  "limit": 5
}
```

#### `get_book_by_isbn`
Get book edition details by ISBN.
```json
{
  "isbn": "9780451524935"
}
```

#### `search_authors`
Search for authors by name.
```json
{
  "query": "Haruki Murakami",
  "limit": 5
}
```
