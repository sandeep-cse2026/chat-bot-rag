# Code Review Checklist

> Apply this checklist before finalizing any file. Every item must pass.

---

## General

- [ ] File has a module-level docstring or clear header comment
- [ ] No hardcoded secrets, API keys, or credentials
- [ ] No `print()` statements — use `structlog` logger instead
- [ ] No commented-out code blocks left behind
- [ ] No unused imports
- [ ] No `TODO` or `FIXME` without an associated explanation

## Type Safety

- [ ] All function parameters have type hints
- [ ] All function return types are annotated
- [ ] No bare `dict` or `list` types — use `dict[str, X]` / `list[X]`
- [ ] No use of `Any` unless justified with a comment
- [ ] Pydantic models used for all structured data

## Error Handling

- [ ] No bare `except:` or `except Exception:` without re-raise
- [ ] Custom exceptions raised instead of generic ones
- [ ] HTTP errors from APIs are caught and wrapped in `APIClientError`
- [ ] Timeout errors are explicitly handled
- [ ] 404 from APIs returns `None` or empty — does not crash

## API Clients

- [ ] Uses the shared `BaseAPIClient` base class
- [ ] Rate limiting enforced between requests
- [ ] Retry logic for 429 / 5xx errors
- [ ] All responses parsed into Pydantic models
- [ ] Connection reuse via persistent `httpx.Client`
- [ ] User-Agent header is set

## LLM Integration

- [ ] Tool definitions have clear, specific descriptions
- [ ] Function calling loop has a max iteration guard (≤3)
- [ ] Tool results sent back as `tool` role messages
- [ ] Conversation history is bounded (max 20 messages)
- [ ] System prompt always included as first message

## Flask Routes

- [ ] Input validated with Pydantic before processing
- [ ] Response follows the standard `{success, data, error}` format
- [ ] Proper HTTP status codes returned (200, 400, 422, 500)
- [ ] No business logic in route handlers — delegated to services

## Security

- [ ] HTML stripped from API responses before LLM context
- [ ] User input sanitized/validated
- [ ] No sensitive data in logs
- [ ] SECRET_KEY loaded from environment

## Docker

- [ ] Multi-stage build used
- [ ] Non-root user configured
- [ ] `--no-cache-dir` used with pip
- [ ] HEALTHCHECK defined
- [ ] `.env` is NOT copied into image (use `.dockerignore`)
- [ ] gunicorn used (not Flask dev server)
