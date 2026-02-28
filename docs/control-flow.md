# EntertainBot — Control Flow & Request Lifecycle

## 1. End-to-End Request Lifecycle

This document traces the complete path of a user message from the browser to the final response.

```mermaid
sequenceDiagram
    actor User
    participant Browser as Frontend (JS)
    participant Flask as Flask Route
    participant Orch as ChatOrchestrator
    participant Ctx as ContextService
    participant LLM as LLM Service
    participant OR as OpenRouter API
    participant TR as ToolRouter
    participant API as External API

    User->>Browser: Types message, presses EXEC
    Browser->>Flask: POST /chat {message, session_id}
    Flask->>Flask: Validate & sanitize input
    Flask->>Orch: process_message(session_id, message)

    Note over Orch: Step 1: Session Setup
    Orch->>Orch: Get/create ConversationHistory
    Orch->>Orch: Cleanup expired sessions

    Note over Orch: Step 2: RAG Context Retrieval
    Orch->>Ctx: retrieve_context(session_id, message)
    Ctx->>Ctx: Vector similarity search (ChromaDB)
    Ctx-->>Orch: Relevant past interactions
    Orch->>Orch: Inject context into history

    Note over Orch: Step 3: Add user message
    Orch->>Orch: history.add_user_message(message)

    Note over Orch: Step 4: Conversation Loop
    loop Up to 5 iterations
        Orch->>LLM: chat_completion(messages, tools)
        LLM->>OR: HTTP POST /chat/completions
        OR-->>LLM: Response (text or tool_calls)
        LLM-->>Orch: LLMResponse

        alt Has tool_calls
            Orch->>Orch: Add tool_calls to history
            loop For each tool call
                Orch->>TR: execute(tool_name, arguments)
                TR->>API: HTTP GET (with cache/retry)
                API-->>TR: JSON response
                TR-->>Orch: Serialized result string
                Orch->>Orch: Add tool result to history
            end
            Note over Orch: Loop continues → send results back to LLM
        else Has text content
            Note over Orch: Final response received
            Orch->>Orch: Break loop
        end
    end

    Note over Orch: Step 5: Post-processing
    Orch->>Orch: Add assistant response to history
    Orch->>Ctx: store_interaction(session_id, Q, A)
    Orch->>Orch: Log interaction (ConversationLogger)
    Orch-->>Flask: Response text
    Flask-->>Browser: JSON {success, response, session_id}
    Browser->>Browser: Render with streaming animation
    Browser-->>User: Sees response appear character-by-character
```

---

## 2. Application Startup Flow

```mermaid
flowchart TD
    A["docker compose up"] --> B["Gunicorn starts<br/>2 workers × 4 threads"]
    B --> C["Worker calls create_app()"]

    C --> D["Load Settings<br/>(Pydantic + .env)"]
    D --> E["Setup structlog"]
    E --> F["Init Middleware<br/>(Request ID + Error Handlers)"]
    F --> G["Init CORS"]
    G --> H["Init Services"]

    H --> H1["JikanClient"]
    H --> H2["TVMazeClient"]
    H --> H3["OpenLibraryClient"]
    H --> H4["LLMService"]
    H --> H5["ToolRouter"]
    H --> H6["ConversationLogger"]
    H --> H7["ContextService<br/>(ChromaDB with retry)"]
    H --> H8["ChatOrchestrator"]

    H7 --> I{"ChromaDB init<br/>successful?"}
    I -- Yes --> J["Continue"]
    I -- "No (race condition)" --> K["Retry with backoff<br/>(1s, 2s)"]
    K --> I

    J --> L["Startup Validation<br/>(API health checks)"]
    L --> M["Register Blueprints<br/>(chat, health, logs)"]
    M --> N["App Ready ✓<br/>Listening on :5000"]
```

---

## 3. Tool Calling Loop (Detailed)

This is the core intelligence loop inside `ChatOrchestrator._run_conversation_loop()`:

```mermaid
flowchart TD
    START["Enter Loop<br/>iteration = 1"] --> SEND["Send messages + tools<br/>to LLM via OpenRouter"]
    SEND --> PARSE["Parse LLM Response"]

    PARSE --> CHECK{"Response type?"}

    CHECK -- "Text content<br/>(no tool calls)" --> DONE["Return text response<br/>✓ Loop complete"]

    CHECK -- "Tool calls" --> ADDTC["Add tool_calls<br/>to conversation history"]
    ADDTC --> EXEC["Execute each tool call<br/>via ToolRouter"]

    EXEC --> RESULT["Add tool results<br/>to conversation history"]
    RESULT --> ITER{"iteration < 5?"}

    ITER -- Yes --> INC["iteration += 1"] --> SEND
    ITER -- No --> FORCE["Force final LLM call<br/>WITHOUT tools"]
    FORCE --> FALLBACK["Return whatever<br/>LLM responds with"]
```

### Tool Execution Detail

When the LLM returns a tool call like `search_anime(query="Death Note")`:

```
1. ToolRouter looks up "search_anime" in TOOL_MAP
   → ("jikan", "search_anime", {})

2. Gets the JikanClient instance and its search_anime method

3. Maps arguments (LLM names → client parameter names)
   → No mapping needed for search_anime

4. Calls jikan.search_anime(query="Death Note")
   → BaseAPIClient.get() handles caching, rate limiting, retry

5. Serializes result: list[AnimeData] → JSON string
   → {"results": [...], "count": 5}

6. Returns JSON string to Orchestrator
   → Added to history as tool result message
```

---

## 4. Available Tool Functions (13 Total)

### Jikan API (Anime/Manga)
| Tool | Client Method | Description |
|---|---|---|
| `search_anime` | `JikanClient.search_anime` | Search anime by name |
| `get_anime_details` | `JikanClient.get_anime_by_id` | Full anime profile by MAL ID |
| `search_manga` | `JikanClient.search_manga` | Search manga by name |
| `get_manga_details` | `JikanClient.get_manga_by_id` | Full manga profile by MAL ID |
| `get_top_anime` | `JikanClient.get_top_anime` | Top anime lists (airing, popular, etc.) |
| `get_seasonal_anime` | `JikanClient.get_season_anime` | Anime by season/year |

### TV Maze API
| Tool | Client Method | Description |
|---|---|---|
| `search_tv_shows` | `TVMazeClient.search_shows` | Search TV shows by name |
| `get_tv_show_details` | `TVMazeClient.get_show_with_details` | Full show profile with cast |
| `get_tv_episode` | `TVMazeClient.get_episode_by_number` | Specific episode by S/E number |
| `get_tv_schedule` | `TVMazeClient.get_schedule` | TV schedule for a date |

### Open Library API
| Tool | Client Method | Description |
|---|---|---|
| `search_books` | `OpenLibraryClient.search_books` | Search books by title/author |
| `get_book_by_isbn` | `OpenLibraryClient.get_edition_by_isbn` | Book edition by ISBN |
| `search_authors` | `OpenLibraryClient.search_authors` | Search authors by name |

---

## 5. Conversation History Management

### Message Types in History

```mermaid
graph LR
    SYS["system<br/>System prompt"] --> USR["user<br/>User message"]
    USR --> CTX["system<br/>Injected RAG context"]
    CTX --> AST_TC["assistant<br/>Tool calls"]
    AST_TC --> TOOL["tool<br/>Tool results"]
    TOOL --> AST_TXT["assistant<br/>Final text response"]
```

### Trimming Strategy

When history exceeds `MAX_CONVERSATION_HISTORY` (default: 20 messages):
1. **Always keep**: System prompt (position 0)
2. **Keep**: Most recent N messages
3. **Preserve**: Tool call + result pairs (never orphaned)
4. **Drop**: Oldest user/assistant pairs first

---

## 6. RAG Context Flow

```mermaid
flowchart LR
    subgraph "Store (after each response)"
        Q["User Question"] --> DOC["Q: question<br/>A: answer"]
        DOC --> EMB["Embed via<br/>all-MiniLM-L6-v2"]
        EMB --> STORE["Upsert to<br/>ChromaDB"]
    end

    subgraph "Retrieve (before each LLM call)"
        NEW["New user message"] --> SEARCH["Cosine similarity<br/>search in ChromaDB"]
        SEARCH --> FILTER["Filter by<br/>similarity threshold ≤ 1.2"]
        FILTER --> FORMAT["Format as<br/>context string"]
        FORMAT --> INJECT["Inject into<br/>conversation history"]
    end
```

The context is injected as a system message just before the user's message, so the LLM naturally references it when generating a response.

---

## 7. Error Recovery Flow

```mermaid
flowchart TD
    ERR["Error occurs"] --> TYPE{"Error type?"}

    TYPE -- "API timeout/5xx" --> RETRY["BaseAPIClient retries<br/>with exponential backoff<br/>(up to 3 attempts)"]
    RETRY --> PASS{"Succeeds?"}
    PASS -- Yes --> CONTINUE["Continue normally"]
    PASS -- No --> TOOL_ERR["Return error JSON<br/>to LLM as tool result"]

    TYPE -- "API 429 Rate Limit" --> WAIT["Wait for<br/>Retry-After header"]
    WAIT --> RETRY

    TYPE -- "Tool execution failure" --> TOOL_ERR
    TOOL_ERR --> LLM_HANDLE["LLM sees error in context<br/>→ explains gracefully to user"]

    TYPE -- "LLM failure" --> LLM_RETRY["LLM Service retries<br/>(2 attempts)"]
    LLM_RETRY --> ORCH_ERR["ChatOrchestrator<br/>catches exception"]
    ORCH_ERR --> USER_ERR["User sees:<br/>'Failed to process your message'"]

    TYPE -- "Input validation" --> VALIDATE["Return 422<br/>with error message"]

    TYPE -- "Unexpected" --> CATCH["Global error handler<br/>logs full traceback"]
    CATCH --> GENERIC["Return 500<br/>'An unexpected error occurred'"]
```

---

## 8. Frontend Message Flow

```mermaid
sequenceDiagram
    actor User
    participant Input as Textarea
    participant JS as chat.js
    participant DOM as Chat Feed

    User->>Input: Types message
    Input->>Input: Auto-resize height
    User->>Input: Press Enter (or click EXEC)
    Input->>JS: Submit event

    JS->>JS: Disable input + button
    JS->>DOM: Append user message row
    JS->>DOM: Append "thinking" indicator

    JS->>JS: fetch POST /chat
    Note over JS: Await server response

    JS->>DOM: Remove "thinking" indicator
    JS->>DOM: Create bot message row (empty)
    JS->>JS: Start streaming animation

    loop Character by character (15ms delay)
        JS->>DOM: Append next character
        JS->>DOM: Update cursor position
    end

    JS->>DOM: Parse Markdown (marked.js)
    JS->>DOM: Remove cursor
    JS->>JS: Re-enable input
    JS->>DOM: Scroll to bottom
```
