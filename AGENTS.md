# Repository Guidelines

## Project Structure & Module Organization
- `app/` — core Python modules: `bolt_listeners.py` (Slack Bolt handlers), `openai_ops.py`/`openai_image_ops.py` (OpenAI/Azure APIs), `slack_ui.py`/`slack_ops.py` (Slack UI/actions), `markdown_conversion.py`, `env.py`.
- `app/openai_constants.py` — model IDs, fallbacks, and token/context tables.
- `app/i18n.py` — translation helper for Slack locale.
- `main.py` — local runner (Socket Mode). `main_prod.py` — AWS Lambda handler.
- `tests/` — pytest-based unit tests (e.g., `openai_ops_test.py`, `markdown_conversion_test.py`).
- Root: `requirements.txt`, `Dockerfile`, `serverless.yml`, `.env.example`, `validate.sh`.
- Slack manifests: `manifest-dev.yml`, `manifest-prod.yml`.
- CI: `.github/workflows/tests.yml`, `.github/workflows/flake8.yml`, `.github/workflows/pytype.yml`.

## Build, Test, and Development Commands
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run locally: `python main.py` (requires `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `OPENAI_API_KEY`).
- Quick syntax check (no deps): `python3 -m py_compile app/openai_ops.py`
- Optional environment variables (commonly used): `OPENAI_MODEL`, `OPENAI_TEMPERATURE`,
  `OPENAI_TIMEOUT_SECONDS`, `USE_SLACK_LANGUAGE`, `SLACK_APP_LOG_LEVEL`,
  `TRANSLATE_MARKDOWN`, `REDACTION_ENABLED`, `IMAGE_FILE_ACCESS_ENABLED` (and Azure vars).
- One-shot validation: `./validate.sh` (formats with Black, runs pytest, flake8, pytype).
- Individually: `black ./app ./tests *.py`, `pytest -q`, `flake8 ./*.py ./app/*.py ./tests/*.py`, `pytype ./*.py ./app/*.py ./tests/*.py`.
- Pytest examples: `pytest tests/openai_ops_test.py::test_format_assistant_reply`
- Docker (optional): `docker build -t chatgpt-in-slack .`
- Serverless (optional): `serverless deploy` (Python 3.9 runtime).

## Coding Style & Naming Conventions
- Python 3.9+, 4-space indentation, UTF-8.
- Formatting: Black; Lint: flake8 (`max-line-length=125`, ignores in `.flake8`).
- Names: modules/files `snake_case.py`; functions/vars `snake_case`; classes `PascalCase`.
- Keep functions small; pure helpers in `app/` and Slack/OpenAI wiring separate.
- Reuse helpers in `app/` (e.g., `markdown_conversion.py`, `openai_ops.py`) instead of reimplementing.
- Type hints encouraged in utility modules.
- Imports: group standard library, third-party, then local; avoid large reorders.
- Constants should be `UPPER_CASE` (see `openai_constants.py`).
- Env/config: import from `app/env.py` and `app/openai_constants.py`; avoid re-reading `os.environ` in modules.
- Keep diffs minimal; format only touched files when feasible.
- Comments/docstrings should remain English (en-US).

## Testing Guidelines
- Framework: pytest; tests under `tests/` named `*_test.py`.
- Prefer fast, deterministic unit tests (no network). Use fakes/mocks (see `tests/openai_ops_test.py`).
- Run `pytest -q` locally; ensure `./validate.sh` passes before PRs.
- Test function names start with `test_`; prefer file-scoped/targeted runs for changed utilities.
- Avoid external calls; use `monkeypatch` or fakes for time/token accounting.

## Commit & Pull Request Guidelines
- Commits: concise, imperative mood. Examples: "Add reasoning models support", "Refactor: Centralize model settings", "Fix markdown spacing". Reference PRs/issues when relevant.
- PRs: clear description, rationale, and scope; link issues; include screenshots of Slack UI when applicable; note config changes. All checks must pass (`./validate.sh`).
- Run `./validate.sh` locally before committing; fix reported issues.
- Keep changes small and reviewable; group related edits per commit.
- When uncertain, propose a short plan or ask a brief clarification before large changes
- Avoid breaking changes; open a GitHub Issue for discussion when necessary.
- Allowed without asking: read/list files; run tests/lint/typing/format; small, focused patches
- Ask first: adding dependencies; deleting/renaming files; changing CI, `serverless.yml`, `Dockerfile`, manifests, or environment variable semantics

## Security & Configuration Tips
- Never perform production-impacting destructive operations
- Never commit secrets. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` (and Azure vars if used).
- Prefer Socket Mode locally; production via Docker or `serverless.yml`.
- Use `.env` for local development; `.env*` is git-ignored.
- Production note: `main_prod.py` stores OpenAI keys per team in S3; avoid logging secrets.
