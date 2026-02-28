# EntertainBot — Configuration Guide

## Overview

All configuration is managed through environment variables loaded via **Pydantic Settings**. Variables are read from a `.env` file at the project root with full type validation and sensible defaults.

---

## Quick Start

```bash
# Copy the example and fill in your API key
cp .env.example .env

# Edit .env and set your OpenRouter API key
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# Start the application
docker compose up --build
```

---

## Environment Variables Reference

### Flask Settings

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | Environment mode (`development` / `production`) |
| `FLASK_DEBUG` | `true` | Enable Flask debug mode |
| `SECRET_KEY` | `change-me-in-production` | Flask secret key for sessions. **Must be changed in production.** |

---

### LLM Configuration (OpenRouter)

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | **(required)** | OpenRouter API key. Get one at [openrouter.ai/keys](https://openrouter.ai/keys) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `OPENROUTER_MODEL` | `google/gemini-2.0-flash-001` | LLM model identifier |

> [!IMPORTANT]
> `OPENROUTER_API_KEY` is the only **required** variable. The app will refuse to start without a valid key.

---

### External API Base URLs

| Variable | Default | Description |
|---|---|---|
| `JIKAN_BASE_URL` | `https://api.jikan.moe/v4` | Jikan API v4 (MyAnimeList) |
| `TVMAZE_BASE_URL` | `https://api.tvmaze.com` | TV Maze API |
| `OPENLIBRARY_BASE_URL` | `https://openlibrary.org` | Open Library API |

These default values should work for most users. Only change if using a self-hosted proxy.

---

### Rate Limiting

| Variable | Default | Range | Description |
|---|---|---|---|
| `JIKAN_RATE_LIMIT` | `1.0` | ≥ 0.0 | Min seconds between Jikan requests |
| `TVMAZE_RATE_LIMIT` | `0.5` | ≥ 0.0 | Min seconds between TVMaze requests |
| `OPENLIBRARY_RATE_LIMIT` | `1.0` | ≥ 0.0 | Min seconds between Open Library requests |

> [!NOTE]
> Jikan's official limit is ~3 req/sec. We default to 1.0s for safety margin. TV Maze is more lenient.

---

### HTTP Client

| Variable | Default | Range | Description |
|---|---|---|---|
| `HTTP_TIMEOUT` | `30` | 1–120 | HTTP request timeout in seconds |
| `HTTP_MAX_RETRIES` | `3` | 0–10 | Max retry attempts for failed requests |

---

### Logging

| Variable | Default | Options | Description |
|---|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Logging verbosity |
| `LOG_FORMAT` | `json` | `json`, `console` | Log output format. Use `json` in production, `console` for development. |

---

### Conversation Management

| Variable | Default | Range | Description |
|---|---|---|---|
| `MAX_CONVERSATION_HISTORY` | `20` | 1–100 | Max messages to keep per session (including system prompt) |
| `SESSION_TTL_SECONDS` | `3600` | ≥ 60 | Idle session TTL before cleanup (seconds) |

---

### API Response Cache

| Variable | Default | Range | Description |
|---|---|---|---|
| `CACHE_TTL_SECONDS` | `300` | ≥ 0 | Cache TTL for API responses (5 minutes default) |
| `CACHE_MAX_SIZE` | `256` | ≥ 1 | Max number of cached API responses |

> [!TIP]
> Set `CACHE_TTL_SECONDS=0` to disable caching entirely (useful for debugging).

---

### Conversation Logging

| Variable | Default | Description |
|---|---|---|
| `CONVERSATION_LOG_DIR` | `logs/conversations` | Directory for JSON conversation logs |
| `CONVERSATION_LOG_ENABLED` | `true` | Enable/disable conversation logging |

---

### Vector Database (ChromaDB)

| Variable | Default | Range | Description |
|---|---|---|---|
| `CHROMA_PERSIST_DIR` | `data/chromadb` | — | Directory for ChromaDB persistence |
| `CHROMA_COLLECTION_NAME` | `conversations` | — | ChromaDB collection name |
| `CONTEXT_MAX_RESULTS` | `3` | 1–10 | Max context results to retrieve per query |
| `CONTEXT_SIMILARITY_THRESHOLD` | `1.2` | 0.0–2.0 | Max cosine distance for relevant context (lower = stricter) |

> [!NOTE]
> The similarity threshold uses **cosine distance**, not similarity. A value of 0.0 means exact match, 2.0 means opposite. The default 1.2 allows moderately related context.

---

## Example `.env` File

```bash
# ── Required ──
OPENROUTER_API_KEY=sk-or-v1-your-key-here

# ── Flask ──
FLASK_ENV=production
FLASK_DEBUG=false
SECRET_KEY=your-random-secret-key-here

# ── LLM ──
OPENROUTER_MODEL=google/gemini-2.0-flash-001

# ── Logging ──
LOG_LEVEL=INFO
LOG_FORMAT=json

# ── Rate Limiting ──
JIKAN_RATE_LIMIT=1.0
TVMAZE_RATE_LIMIT=0.5
OPENLIBRARY_RATE_LIMIT=1.0

# ── Cache ──
CACHE_TTL_SECONDS=300
CACHE_MAX_SIZE=256

# ── ChromaDB ──
CHROMA_PERSIST_DIR=data/chromadb
CHROMA_COLLECTION_NAME=conversations
CONTEXT_MAX_RESULTS=3
CONTEXT_SIMILARITY_THRESHOLD=1.2

# ── Sessions ──
MAX_CONVERSATION_HISTORY=20
SESSION_TTL_SECONDS=3600

# ── Conversation Logging ──
CONVERSATION_LOG_ENABLED=true
CONVERSATION_LOG_DIR=logs/conversations
```

---

## Validation Rules

The config system enforces these rules at startup:

| Rule | Effect |
|---|---|
| `OPENROUTER_API_KEY` must be set and not a placeholder | App refuses to start |
| `SECRET_KEY` must be changed if `FLASK_ENV=production` | App refuses to start |
| `LOG_LEVEL` must be a valid Python log level | ValueError |
| `LOG_FORMAT` must be `json` or `console` | ValueError |
| All base URLs are stripped of trailing slashes | Auto-corrected |
| Numeric fields have min/max constraints | ValidationError |

---

## Docker Override

The `docker-compose.yml` overrides some defaults for production:

```yaml
environment:
  - FLASK_ENV=production
  - FLASK_DEBUG=false
  - LOG_FORMAT=json
```

These take precedence over `.env` file values.
