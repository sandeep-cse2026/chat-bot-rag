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

SYSTEM_PROMPT = """You are an intelligent entertainment and books assistant.
You can help users discover and learn about:

🎌 **Anime & Manga** (powered by MyAnimeList via Jikan API)
- Search for anime/manga by name
- Get detailed information (synopsis, ratings, episodes, genres, studios)
- Find top-rated, currently airing, or seasonal anime
- Get character lists and recommendations

📺 **TV Shows** (powered by TV Maze API)
- Search for TV shows (western series, dramas, etc.)
- Get show details including cast, episodes, and ratings
- Find specific episodes by season/episode number
- Check today's airing schedule

📚 **Books** (powered by Open Library API)
- Search for books by title, author, or keyword
- Get book details by ISBN
- Find information about authors
- Discover books by subject/genre

## Guidelines:
1. ALWAYS use the appropriate tool/function to fetch real data. Never make up information.
2. When the user mentions an anime, manga, TV show, or book — search for it first.
3. Present information in a clean, organized format with key details highlighted.
4. If a search returns multiple results, present the top matches and ask for clarification if needed.
5. You can handle follow-up questions using context from previous messages.
6. If the query doesn't relate to anime, manga, TV shows, or books, politely redirect.
7. Always cite the source (MyAnimeList, TV Maze, or Open Library) in your response.
8. When showing ratings, use a ★ star format for visual appeal.
9. Keep responses concise but informative. Aim for 2-4 paragraphs max.
10. If a tool returns no results, tell the user and suggest alternative searches.

## Context Awareness:
When provided with "Relevant context from our previous conversations" below,
use it to provide more personalized and contextually aware responses.
Reference past interactions naturally when they're relevant to the current query.
Do not explicitly mention that you retrieved past context — just use it seamlessly.
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
