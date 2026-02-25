# 🎌📺📚 Entertainment & Books RAG Chatbot

An AI-powered chatbot that helps you discover anime, manga, TV shows, and books using real-time data from multiple APIs — powered by an LLM with function calling.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-lightgrey?logo=flask)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Features

- **🎌 Anime & Manga** — Search, get details, top charts, seasonal lists, characters, and recommendations (via [Jikan/MyAnimeList](https://jikan.moe/))
- **📺 TV Shows** — Search, cast, episodes, schedules, and people lookup (via [TV Maze](https://www.tvmaze.com/api))
- **📚 Books** — Search by title/author/ISBN, author details, and cover images (via [Open Library](https://openlibrary.org/developers/api))
- **🤖 LLM-Powered** — Natural language understanding with function calling via [OpenRouter](https://openrouter.ai/)
- **💬 Multi-Turn Conversations** — Context-aware follow-up questions
- **🎨 Modern Dark UI** — Glassmorphism design with domain-specific accent colors
- **🐳 Dockerized** — Production-ready containerization with health checks
- **🔒 Production Infrastructure** — Structured logging, rate limiting, caching, error handling

---

## 🏗 Architecture

```
User ──► Flask App ──► Chat Orchestrator ──► LLM (OpenRouter)
                            │                      │
                            │                ◄── Tool Calls
                            │
                       Tool Router
                      /     |     \
               Jikan    TV Maze   Open Library
              (Anime)  (TV Shows)   (Books)
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+ / Flask |
| LLM | OpenRouter (google/gemini-2.0-flash-001) |
| Validation | Pydantic v2 |
| HTTP Client | httpx (connection pooling, retries) |
| Logging | structlog (JSON output) |
| Server | Gunicorn (production) |
| Container | Docker / Docker Compose |
| Tunnel | ngrok (local deployment) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- An [OpenRouter API key](https://openrouter.ai/keys)
- Docker & Docker Compose (for containerized deployment)
- ngrok (for public URL tunneling)

### 1. Clone & Setup

```bash
git clone <repository-url>
cd chat-bot-rag

# Create virtual environment
python -m venv venv
source venv/bin/activate    # Linux/Mac
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set your **OpenRouter API key**:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

### 3. Run Locally

```bash
# Development server
python run.py

# Or with Flask CLI
flask run --host=0.0.0.0 --port=5000
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🐳 Docker Deployment

### Build and Run

```bash
# Build and start the container
docker-compose up --build -d

# Check logs
docker-compose logs -f chatbot

# Verify it's running
curl http://localhost:5000/health
```

### Stop

```bash
docker-compose down
```

---

## 🌐 ngrok Deployment

Expose your local instance to the internet:

### 1. Install ngrok

```bash
# Via snap (Linux)
sudo snap install ngrok

# Or download from https://ngrok.com/download
```

### 2. Authenticate (one-time)

```bash
ngrok config add-authtoken YOUR_NGROK_AUTH_TOKEN
```

### 3. Start the Tunnel

```bash
# Make sure the app is running first (locally or via Docker)
docker-compose up -d

# Start ngrok tunnel
ngrok http 5000
```

### 4. Access Your Chatbot

Copy the **HTTPS Forwarding URL** from the ngrok output:
```
Forwarding  https://abc-123-xyz.ngrok-free.app → http://localhost:5000
```

Share this URL — anyone can access your chatbot! 🎉

---

## 📁 Project Structure

```
chat-bot-rag/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Pydantic Settings configuration
│   ├── api_clients/
│   │   ├── base_client.py       # Abstract base (retry, rate-limit, cache)
│   │   ├── jikan_client.py      # Anime/manga API (9 endpoints)
│   │   ├── tvmaze_client.py     # TV shows API (8 endpoints)
│   │   └── openlibrary_client.py # Books API (7 endpoints)
│   ├── models/
│   │   ├── api_schemas.py       # Pydantic models for API responses
│   │   ├── requests.py          # Chat request validation
│   │   └── responses.py         # Chat response models
│   ├── services/
│   │   ├── llm_service.py       # OpenRouter LLM integration
│   │   ├── chat_orchestrator.py # Multi-turn conversation loop
│   │   └── tool_router.py       # Function → API client mapping
│   ├── prompts/
│   │   └── templates.py         # System prompt + 13 tool definitions
│   ├── routes/
│   │   ├── chat.py              # Chat endpoints (/, /chat, /chat/clear)
│   │   └── health.py            # Health check (/health)
│   ├── middleware/
│   │   ├── request_id.py        # X-Request-ID injection
│   │   └── error_handlers.py    # Global JSON error handlers
│   ├── utils/
│   │   ├── logger.py            # Structured logging setup
│   │   ├── exceptions.py        # Custom exception hierarchy
│   │   ├── sanitizer.py         # Input sanitization
│   │   └── cache.py             # TTL-based in-memory cache
│   ├── templates/
│   │   └── index.html           # Chat UI
│   └── static/
│       ├── css/style.css        # Dark theme styles
│       └── js/chat.js           # Frontend logic
├── tests/                       # Unit & integration tests
├── docs/
│   └── plan.md                  # Implementation plan
├── run.py                       # Application entry point
├── requirements.txt             # Python dependencies
├── Dockerfile                   # Multi-stage Docker build
├── docker-compose.yml           # Container orchestration
├── .env.example                 # Environment variable template
├── .gitignore
└── .dockerignore
```

---

## 🔧 Configuration

All settings are managed via environment variables (`.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | **required** | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `google/gemini-2.0-flash-001` | LLM model to use |
| `FLASK_ENV` | `development` | Environment (`development` / `production`) |
| `SECRET_KEY` | `dev-secret-key-change-me` | Flask secret key |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `console` | Log format (`console` / `json`) |
| `CACHE_TTL_SECONDS` | `300` | API response cache TTL |
| `SESSION_TTL_SECONDS` | `3600` | Chat session expiry |

---

## 💬 Example Queries

| Domain | Query |
|--------|-------|
| 🎌 Anime | "What is Attack on Titan about?" |
| 🎌 Anime | "Show me the top rated anime right now" |
| 🎌 Manga | "Tell me about the manga One Piece" |
| 📺 TV | "Search for Breaking Bad" |
| 📺 TV | "What shows are airing today in the US?" |
| 📚 Books | "Find books by Haruki Murakami" |
| 📚 Books | "Look up ISBN 9780451524935" |

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v --tb=short

# Run with coverage
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## 📜 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Chat UI |
| `POST` | `/chat` | Send a chat message |
| `POST` | `/chat/clear` | Clear session history |
| `GET` | `/health` | Health check (dependency status) |

### POST /chat

```json
// Request
{ "message": "Tell me about Naruto", "session_id": "optional-uuid" }

// Response
{ "success": true, "response": "Naruto is a...", "session_id": "uuid" }
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
