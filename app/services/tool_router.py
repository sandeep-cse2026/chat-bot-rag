"""Tool router — maps LLM function calls to API client methods.

The ToolRouter is the bridge between the LLM's function calls and
the actual API client methods. When the LLM responds with a tool call
like `search_anime(query="Naruto")`, the router:

1. Looks up the function name in TOOL_MAP
2. Finds the correct API client and method
3. Executes the call with the provided arguments
4. Serializes the result back to a string for the LLM

Usage:
    router = ToolRouter(jikan_client, tvmaze_client, openlibrary_client)
    result = router.execute("search_anime", {"query": "Naruto"})
"""
from __future__ import annotations

import json
from typing import Any

import structlog

from app.api_clients.jikan_client import JikanClient
from app.api_clients.tvmaze_client import TVMazeClient
from app.api_clients.openlibrary_client import OpenLibraryClient
from app.utils.exceptions import ToolExecutionError

logger = structlog.get_logger(__name__)


class ToolRouter:
    """Routes LLM function calls to the appropriate API client method.

    Maps all 13 tool function names to their corresponding
    (client, method) pairs and handles argument mapping.

    Args:
        jikan: JikanClient instance.
        tvmaze: TVMazeClient instance.
        openlibrary: OpenLibraryClient instance.
    """

    def __init__(
        self,
        jikan: JikanClient,
        tvmaze: TVMazeClient,
        openlibrary: OpenLibraryClient,
    ) -> None:
        self._clients = {
            "jikan": jikan,
            "tvmaze": tvmaze,
            "openlibrary": openlibrary,
        }

        # Map: function_name → (client_key, method_name, arg_mapping)
        # arg_mapping translates LLM argument names to client method parameter names
        self._tool_map: dict[str, tuple[str, str, dict[str, str]]] = {
            # ── Jikan (Anime/Manga) ──
            "search_anime":       ("jikan", "search_anime", {}),
            "get_anime_details":  ("jikan", "get_anime_by_id", {"anime_id": "anime_id"}),
            "search_manga":       ("jikan", "search_manga", {}),
            "get_manga_details":  ("jikan", "get_manga_by_id", {"manga_id": "manga_id"}),
            "get_top_anime":      ("jikan", "get_top_anime", {"filter": "filter_type"}),
            "get_seasonal_anime": ("jikan", "get_season_anime", {}),

            # ── TV Maze ──
            "search_tv_shows":      ("tvmaze", "search_shows", {}),
            "get_tv_show_details":  ("tvmaze", "get_show_with_details", {}),
            "get_tv_episode":       ("tvmaze", "get_episode_by_number", {}),
            "get_tv_schedule":      ("tvmaze", "get_schedule", {}),

            # ── Open Library ──
            "search_books":    ("openlibrary", "search_books", {}),
            "get_book_by_isbn": ("openlibrary", "get_edition_by_isbn", {}),
            "search_authors":  ("openlibrary", "search_authors", {}),
        }

    @property
    def available_tools(self) -> list[str]:
        """Return list of available tool/function names."""
        return list(self._tool_map.keys())

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool call and return the result as a JSON string.

        Args:
            tool_name: The function name from the LLM's tool call.
            arguments: The arguments dict from the LLM's tool call.

        Returns:
            JSON string of the tool result (for sending back to the LLM).

        Raises:
            ToolExecutionError: If the tool name is unknown or execution fails.
        """
        if tool_name not in self._tool_map:
            raise ToolExecutionError(
                tool_name=tool_name,
                message=f"Unknown tool: '{tool_name}'. Available: {self.available_tools}",
            )

        client_key, method_name, arg_mapping = self._tool_map[tool_name]
        client = self._clients[client_key]
        method = getattr(client, method_name)

        # Map LLM argument names to client method parameter names
        mapped_args = self._map_arguments(arguments, arg_mapping)

        logger.info(
            "tool_execution",
            tool=tool_name,
            client=client_key,
            method=method_name,
            args=mapped_args,
        )

        try:
            result = method(**mapped_args)
            serialized = self._serialize_result(result)

            logger.info(
                "tool_result",
                tool=tool_name,
                result_length=len(serialized),
            )

            return serialized

        except ToolExecutionError:
            raise
        except Exception as e:
            logger.error(
                "tool_execution_failed",
                tool=tool_name,
                error=str(e),
                exc_info=True,
            )
            raise ToolExecutionError(
                tool_name=tool_name,
                message=str(e),
            ) from e

    # ── Private Helpers ───────────────────────────────────────────────

    @staticmethod
    def _map_arguments(
        arguments: dict[str, Any], mapping: dict[str, str]
    ) -> dict[str, Any]:
        """Map LLM argument names to client method parameter names.

        Args:
            arguments: Raw arguments from the LLM.
            mapping: Dict of {llm_arg_name: client_param_name}.

        Returns:
            Mapped arguments dict.
        """
        if not mapping:
            return arguments

        mapped = {}
        for key, value in arguments.items():
            mapped_key = mapping.get(key, key)
            mapped[mapped_key] = value
        return mapped

    @staticmethod
    def _serialize_result(result: Any) -> str:
        """Serialize a tool result to a JSON string for the LLM.

        Handles Pydantic models, dicts, lists, and primitives.

        Args:
            result: The raw result from the API client method.

        Returns:
            JSON-encoded string.
        """
        if result is None:
            return json.dumps({"result": "No results found."})

        if isinstance(result, list):
            if not result:
                return json.dumps({"result": "No results found.", "count": 0})

            serialized_items = []
            for item in result:
                if hasattr(item, "model_dump"):
                    serialized_items.append(item.model_dump(exclude_none=True))
                elif isinstance(item, dict):
                    serialized_items.append(item)
                else:
                    serialized_items.append(str(item))

            return json.dumps({"results": serialized_items, "count": len(serialized_items)})

        if hasattr(result, "model_dump"):
            return json.dumps(result.model_dump(exclude_none=True))

        if isinstance(result, dict):
            # Handle nested Pydantic models (e.g., from get_show_with_details)
            serialized = {}
            for key, value in result.items():
                if hasattr(value, "model_dump"):
                    serialized[key] = value.model_dump(exclude_none=True)
                elif isinstance(value, list):
                    serialized[key] = [
                        item.model_dump(exclude_none=True)
                        if hasattr(item, "model_dump") else item
                        for item in value
                    ]
                else:
                    serialized[key] = value
            return json.dumps(serialized)

        return json.dumps({"result": str(result)})
