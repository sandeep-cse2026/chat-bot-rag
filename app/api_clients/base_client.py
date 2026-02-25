"""Abstract base API client with retry, rate limiting, caching, and structured logging.

All external API clients (Jikan, TV Maze, Open Library) inherit from this
class to get production-grade HTTP handling for free.

Features:
- Persistent connection pooling via httpx.Client
- Automatic retry with exponential backoff (429, 5xx)
- Per-client rate limiting (configurable delay between requests)
- TTL response caching (via app.utils.cache.TTLCache)
- Structured logging for every request/response
- Custom exception mapping
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
import structlog

from app.utils.cache import TTLCache
from app.utils.exceptions import (
    APIClientError,
    APIRateLimitError,
    APITimeoutError,
)

logger = structlog.get_logger(__name__)

# HTTP status codes that trigger automatic retry
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class BaseAPIClient(ABC):
    """Abstract base class for external API clients.

    Args:
        base_url: The API's base URL (no trailing slash).
        rate_limit: Minimum seconds between consecutive requests.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of retry attempts.
        cache_ttl: Cache time-to-live in seconds (0 disables caching).
        cache_max_size: Maximum number of cached entries.
        headers: Additional default headers to send with every request.
    """

    def __init__(
        self,
        base_url: str,
        rate_limit: float = 1.0,
        timeout: int = 30,
        max_retries: int = 3,
        cache_ttl: int = 300,
        cache_max_size: int = 256,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._rate_limit = rate_limit
        self._max_retries = max_retries
        self._last_request_time: float = 0.0
        self._client_name = self.__class__.__name__

        # Persistent HTTP client with connection pooling
        default_headers = {
            "Accept": "application/json",
            "User-Agent": "ChatBotRAG/1.0 (entertainment-chatbot)",
        }
        if headers:
            default_headers.update(headers)

        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=httpx.Timeout(timeout, connect=10),
            headers=default_headers,
            follow_redirects=True,
        )

        # Response cache
        self._cache = TTLCache(ttl_seconds=cache_ttl, max_size=cache_max_size)

    def close(self) -> None:
        """Close the underlying HTTP client and release connections."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Public API ────────────────────────────────────────────────────

    def get(self, endpoint: str, params: dict[str, Any] | None = None, use_cache: bool = True) -> dict:
        """Make a cached, rate-limited GET request with retry.

        Args:
            endpoint: API endpoint path (e.g., "/anime").
            params: Query parameters.
            use_cache: Whether to use the response cache.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            APIClientError: On non-retryable HTTP errors.
            APIRateLimitError: When rate limited after all retries.
            APITimeoutError: On request timeout.
        """
        params = params or {}

        # Check cache first
        if use_cache:
            cache_key = TTLCache.make_key(
                f"{self._client_name}:GET:{endpoint}",
                **{k: v for k, v in params.items() if v is not None},
            )
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug("cache_hit", client=self._client_name, endpoint=endpoint)
                return cached

        # Make the request with retry
        result = self._request_with_retry("GET", endpoint, params)

        # Cache the response
        if use_cache:
            self._cache.set(cache_key, result)

        return result

    # ── Internal Methods ──────────────────────────────────────────────

    def _request_with_retry(
        self, method: str, endpoint: str, params: dict[str, Any]
    ) -> dict:
        """Execute an HTTP request with exponential backoff retry.

        Args:
            method: HTTP method ("GET").
            endpoint: API endpoint path.
            params: Query parameters.

        Returns:
            Parsed JSON response dict.
        """
        last_exception: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                # Enforce rate limit
                self._rate_limit_wait()

                # Log the request
                logger.info(
                    "api_request",
                    client=self._client_name,
                    method=method,
                    endpoint=endpoint,
                    attempt=attempt,
                )

                start = time.monotonic()
                response = self._client.request(method, endpoint, params=params)
                duration_ms = round((time.monotonic() - start) * 1000)

                # Log the response
                logger.info(
                    "api_response",
                    client=self._client_name,
                    endpoint=endpoint,
                    status=response.status_code,
                    duration_ms=duration_ms,
                )

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 2))
                    if attempt < self._max_retries:
                        logger.warning(
                            "rate_limited",
                            client=self._client_name,
                            retry_after=retry_after,
                            attempt=attempt,
                        )
                        time.sleep(retry_after)
                        continue
                    raise APIRateLimitError(
                        client_name=self._client_name, retry_after=retry_after
                    )

                # Handle server errors (5xx) with retry
                if response.status_code in RETRYABLE_STATUS_CODES:
                    if attempt < self._max_retries:
                        backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s
                        logger.warning(
                            "retryable_error",
                            client=self._client_name,
                            status=response.status_code,
                            backoff=backoff,
                            attempt=attempt,
                        )
                        time.sleep(backoff)
                        continue

                # Handle client errors (4xx)
                if response.status_code >= 400:
                    raise APIClientError(
                        message=f"{self._client_name}: HTTP {response.status_code} for {endpoint}",
                        client_name=self._client_name,
                        upstream_status=response.status_code,
                    )

                # Success
                return response.json()

            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self._max_retries:
                    backoff = 2 ** (attempt - 1)
                    logger.warning(
                        "timeout_retry",
                        client=self._client_name,
                        endpoint=endpoint,
                        backoff=backoff,
                        attempt=attempt,
                    )
                    time.sleep(backoff)
                    continue
                raise APITimeoutError(
                    client_name=self._client_name,
                    timeout=self._client.timeout.read or 30,
                ) from e

            except (APIClientError, APIRateLimitError, APITimeoutError):
                raise  # Don't wrap our own exceptions

            except httpx.HTTPError as e:
                last_exception = e
                if attempt < self._max_retries:
                    backoff = 2 ** (attempt - 1)
                    logger.warning(
                        "http_error_retry",
                        client=self._client_name,
                        error=str(e),
                        backoff=backoff,
                        attempt=attempt,
                    )
                    time.sleep(backoff)
                    continue

        # All retries exhausted
        raise APIClientError(
            message=f"{self._client_name}: All {self._max_retries} retries exhausted for {endpoint}",
            client_name=self._client_name,
        )

    def _rate_limit_wait(self) -> None:
        """Enforce minimum delay between consecutive requests."""
        if self._rate_limit <= 0:
            return

        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit:
            sleep_time = self._rate_limit - elapsed
            logger.debug(
                "rate_limit_wait",
                client=self._client_name,
                sleep_seconds=round(sleep_time, 3),
            )
            time.sleep(sleep_time)

        self._last_request_time = time.monotonic()

    @abstractmethod
    def health_check(self) -> bool:
        """Verify the API is reachable. Used by /health endpoint.

        Returns:
            True if API is healthy, False otherwise.
        """
        ...
