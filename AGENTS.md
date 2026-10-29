# Coding Assistant Instructions: python-hilo Library

This repository contains `pyhilo`, a standalone asynchronous Python client library for Hilo energy services (SignalR WebSocket, GraphQL, and REST APIs).

## Git Commit Guidelines

- **First line**: Short, specific imperative sentence (e.g. "Add abstract auth interface for token provider"). No emojis in titles.
- **Commit description**: Focus on the **WHY** (problem, context, and architectural rationale). Keep it concise, factual, and proportional.
- **Do NOT amend, squash, or rebase commits that have already been pushed to the PR branch after the PR is opened**: Reviewers need to follow the commit history and see what changed since their last review.

## Development Commands

- Install dependencies: `uv sync`
- Run test suite: `uv run pytest`
- Run a specific test: `uv run pytest tests/test_device.py`
- Check linting and formatting: `uv run ruff check .` and `uv run ruff format --check .`

## Architecture & Boundaries

- **Strict Decoupling from Home Assistant**:
  - This library MUST NEVER import `homeassistant` or depend on Home Assistant Core modules, constants, or types.
  - The library must be 100% installable, testable, and runnable independently in any standard Python 3.13+ environment.
- **Authentication Contract**:
  - Expose an abstract base class `AbstractAuth` (`pyhilo.auth`):
    ```python
    class AbstractAuth(ABC):
        @abstractmethod
        async def async_get_access_token(self) -> str:
            """Return a valid access token, refreshing if necessary."""
    ```
  - The library calls this method whenever it needs a valid token, leaving token storage and refresh mechanisms to the consumer (such as the Hilo Home Assistant integration or CLI tools).
- **Backwards Compatibility**: When modifying public API signatures, provide temporary shims with deprecation warnings for at least 1–2 minor versions to prevent breaking downstream consumers.
- **Credential Protection**: Never log raw access tokens, refresh tokens, passwords, or decoded JWT claims in `DEBUG` or `INFO` logs.

## Testing Standards

- Verify library protocol behavior, event decoding, device mapping, and error handling.
- When writing tests or implementation code, ensure all parameters have precise type annotations. **The use of `Any` is strictly forbidden in new code.**
- **Single purpose tests**: Each test function must verify only one specific behavior or outcome. Avoid testing multiple unrelated scenarios in a single test; split them into focused tests or use parametrization.
- Prefer standard library `unittest.mock` (`AsyncMock`, `MagicMock`) over large bespoke stub classes.
- Prefer `@pytest.mark.usefixtures` over unused fixture arguments.
- Avoid branching (`if`/`else`) in tests; use `@pytest.mark.parametrize` with `pytest.param(..., id="...")` for table-driven testing.
- Tests must execute cleanly with `uv run pytest` without requiring network access.

## Good practices

- Built with `asyncio`, `aiohttp`, `pysignalr`, and `gql`.
- Non-blocking I/O: avoid any synchronous disk reads/writes on active event loops. Accept explicit file paths when managing state.
- Keep `try` clauses as small as possible.
- When validation guarantees a dict key exists, prefer direct key access (`data["key"]`) instead of `.get("key")`.
- Keep comments concise and explain only the WHY. Do not restate code or use divider comments (`# --- XYZ ---`).
- CalVer format: Versions follow `vYYYY.MM.MICRO` (e.g. `v2026.10.1`).

## AI policy

Autonomous contributions are not accepted. Every change must be reviewed and understood by a human contributor before submission. Never open pull requests, create release tags, or post comments autonomously without explicit contributor instruction.
