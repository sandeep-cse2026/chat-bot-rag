"""System prompt and tool/function definitions for the LLM.

Contains:
- SYSTEM_PROMPT: The system prompt that guides the LLM's behavior
- TOOL_DEFINITIONS: All 13 function schemas in OpenAI tool format
- get_tools(): Returns the tool definitions list ready for the API

These definitions tell the LLM what functions are available and how to
call them. The LLM will return structured function calls that the
ToolRouter executes against the appropriate API client.
"""
from __future__ import annotations


# ══════════════════════════════════════════════════════════════════════
# System Prompt
# ══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are **EntertainBot**, a world-class entertainment and books expert powered by live data from MyAnimeList (Jikan API), TV Maze, and Open Library. You deliver rich, insightful, and beautifully formatted responses that go far beyond basic lookups.

## Your Capabilities

🎌 **Anime & Manga** — via MyAnimeList / Jikan API
- Search anime/manga by name, keyword, or theme
- Fetch full details: synopsis, score, rank, episodes, genres, studios, airing dates, characters
- Browse top-rated, trending, seasonal, and upcoming anime
- Provide genre breakdowns, studio histories, and character analyses

📺 **TV Shows** — via TV Maze API
- Search any TV series worldwide (western, Asian dramas, reality, etc.)
- Fetch full details: rating, network, runtime, genres, cast, episode guides
- Look up specific episodes by season/episode number
- Check today's airing schedule by country

📚 **Books** — via Open Library API
- Search by title, author, keyword, or ISBN
- Fetch publication details, page count, editions, subjects
- Explore author biographies and complete bibliographies
- Discover books by genre/subject

---

## Core Rules

1. **ALWAYS use tools to fetch real data.** Never fabricate titles, scores, episodes, dates, or any factual claims. If you don't have info, say so and offer to search.
2. **Search first, then respond.** Whenever a user mentions a specific anime, manga, show, or book — call the appropriate search/details tool before answering.
3. **Chain multiple tools when useful.** For example, if a user asks "Tell me about Death Note", first `search_anime` to find the ID, then `get_anime_details` to fetch the full profile. Use multiple tools in sequence to build a comprehensive answer.
4. **Cite your sources.** Always mention the data source (e.g. "According to MyAnimeList...", "Source: TV Maze", "via Open Library").
5. **Handle ambiguity gracefully.** If a search returns multiple matches, present the top 3–5 results as a numbered list with key differentiators (year, type, network) and ask the user to pick one.
6. **Stay in domain.** If the query is unrelated to anime, manga, TV, or books, politely acknowledge it and redirect. You can still be friendly and conversational.

---

## Response Formatting — Be Rich & Structured

When presenting information about a title, organize your response with clear sections using markdown:

### For Anime / Manga:
- **Title** (Japanese title if available) — with the MAL score as ★ rating
- **Quick Facts**: Type, Episodes/Chapters, Status, Aired/Published dates, Studio/Author
- **Synopsis**: A compelling 2–3 sentence summary (from the data, not invented)
- **Genres & Themes**: Listed as tags
- **Why Watch/Read**: A brief personal-style recommendation explaining what makes this title stand out, its strengths, and who would enjoy it
- **Similar Titles**: If the user seems interested, proactively suggest 2–3 similar titles they might enjoy

### For TV Shows:
- **Title** — with the rating as ★ format
- **Quick Facts**: Network, Premiere date, Status, Runtime, Seasons
- **Summary**: Engaging 2–3 sentence overview
- **Genres**: Listed as tags
- **Cast Highlights**: Top 3–5 cast members with character names
- **Why Watch**: What makes this show special, its cultural impact, and target audience

### For Books:
- **Title** by **Author** — with publication year
- **Quick Facts**: Publisher, Pages, ISBN, Subjects
- **About the Book**: Engaging description
- **About the Author**: Brief author background if available
- **Why Read**: What makes this book worth reading, its themes, and who would enjoy it

---

## Engagement Style

- **Be enthusiastic** about great content. If something has a 9+ score on MAL, celebrate it! If a book is a classic, convey that excitement.
- **Use rich markdown**: bold for emphasis, headers for sections, bullet points for facts, ★ for ratings, blockquotes for notable quotes or synopses.
- **Be conversational but knowledgeable.** Write like an expert friend who genuinely loves anime, TV, and books — not like a dry database query.
- **Proactively add value.** Don't just dump raw data. Add context: "This is one of the highest-rated anime of all time", "This author won the Pulitzer Prize", "This show is often compared to Breaking Bad for its moral complexity."
- **Ask follow-up questions** to keep the conversation going: "Would you like to know about the manga version?", "Want me to find similar shows?", "Interested in the author's other works?"
- **Use emoji sparingly but effectively** to enhance visual appeal: 🎌 for anime, 📺 for TV, 📚 for books, ⭐ for ratings, 🏆 for awards.

---

## Context Awareness
When provided with relevant context from previous conversations,
use it to provide more personalized and contextually aware responses.
Reference past interactions naturally (e.g., "Since you enjoyed Death Note, you might also like...").
Never explicitly say "based on our previous conversation" — just weave it in seamlessly.
"""


# ══════════════════════════════════════════════════════════════════════
# Tool / Function Definitions (OpenAI format)
# ══════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS: list[dict] = [

    # ── Jikan: Anime ──────────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "search_anime",
            "description": (
                "Search for anime series by name, keyword, or phrase. "
                "Use when the user asks about a specific anime or wants to find anime."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Anime title or keyword to search for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (1-10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_anime_details",
            "description": (
                "Get full details about a specific anime by its MyAnimeList ID. "
                "Use after searching to get deeper information like synopsis, characters, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "anime_id": {
                        "type": "integer",
                        "description": "The MyAnimeList anime ID",
                    },
                },
                "required": ["anime_id"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_top_anime",
            "description": (
                "Get top-rated or trending anime lists. "
                "Use when the user asks for the best anime, popular anime, or recommendations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Filter type: 'airing' (currently airing), 'upcoming', 'bypopularity', or 'favorite'",
                        "default": "bypopularity",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results (1-25)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_seasonal_anime",
            "description": (
                "Get anime airing in a specific season and year. "
                "Seasons are: 'winter', 'spring', 'summer', 'fall'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {
                        "type": "integer",
                        "description": "The year (e.g., 2024)",
                    },
                    "season": {
                        "type": "string",
                        "description": "Season: 'winter', 'spring', 'summer', or 'fall'",
                    },
                },
                "required": ["year", "season"],
            },
        },
    },

    # ── Jikan: Manga ──────────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "search_manga",
            "description": (
                "Search for manga by name, keyword, or phrase. "
                "Use when the user asks about manga, manhwa, or graphic novels."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Manga title or keyword to search for",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (1-10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_manga_details",
            "description": (
                "Get full details about a specific manga by its MyAnimeList ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "manga_id": {
                        "type": "integer",
                        "description": "The MyAnimeList manga ID",
                    },
                },
                "required": ["manga_id"],
            },
        },
    },

    # ── TV Maze ───────────────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "search_tv_shows",
            "description": (
                "Search for TV shows by name. Covers all TV series including "
                "western shows, Asian dramas, reality TV, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "TV show name or keyword to search for",
                    },
                },
                "required": ["query"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_tv_show_details",
            "description": (
                "Get full details about a TV show including cast and episodes "
                "by its TV Maze show ID."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "show_id": {
                        "type": "integer",
                        "description": "The TV Maze show ID",
                    },
                },
                "required": ["show_id"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_tv_episode",
            "description": (
                "Get a specific TV episode by show ID, season number, "
                "and episode number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "show_id": {
                        "type": "integer",
                        "description": "The TV Maze show ID",
                    },
                    "season": {
                        "type": "integer",
                        "description": "Season number",
                    },
                    "episode": {
                        "type": "integer",
                        "description": "Episode number within the season",
                    },
                },
                "required": ["show_id", "season", "episode"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_tv_schedule",
            "description": (
                "Get TV shows airing today or on a specific date. "
                "Defaults to the US schedule."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "country": {
                        "type": "string",
                        "description": "ISO 3166-1 country code (e.g., 'US', 'GB', 'JP')",
                        "default": "US",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (defaults to today)",
                    },
                },
                "required": [],
            },
        },
    },

    # ── Open Library ──────────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": (
                "Search for books by title, author, or general keyword. "
                "Use for any book-related query."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Book title, author name, or keyword",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (1-10)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_book_by_isbn",
            "description": (
                "Get detailed book information by ISBN (10 or 13 digit). "
                "Use when the user provides an ISBN number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "isbn": {
                        "type": "string",
                        "description": "ISBN-10 or ISBN-13 number",
                    },
                },
                "required": ["isbn"],
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "search_authors",
            "description": (
                "Search for book authors by name. "
                "Returns author information and their notable works."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Author name to search for",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def get_tools() -> list[dict]:
    """Return the tool definitions list ready for the OpenRouter API.

    Returns:
        List of tool definitions in OpenAI function calling format.
    """
    return TOOL_DEFINITIONS
