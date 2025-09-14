# Repository Guidelines

## Project Structure & Module Organization
- `app/` — core Python modules: `bolt_listeners.py` (Slack Bolt handlers), `openai_ops.py`/`openai_image_ops.py` (OpenAI/Azure APIs), `slack_ui.py`/`slack_ops.py` (Slack UI/actions), `markdown_conversion.py`, `env.py`.
- `main.py` — local runner (Socket Mode). `main_prod.py` — AWS Lambda handler.
- `tests/` — pytest-based unit tests (e.g., `openai_ops_test.py`, `markdown_conversion_test.py`).
- Root: `requirements.txt`, `Dockerfile`, `serverless.yml`, `.env.example`, `validate.sh`.

## Build, Test, and Development Commands
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run locally: `python main.py` (requires `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `OPENAI_API_KEY`).
- One-shot validation: `./validate.sh` (formats with Black, runs pytest, flake8, pytype).
- Individually: `black ./app ./tests *.py`, `pytest -q`, `flake8 ./*.py ./app/*.py ./tests/*.py`, `pytype ./*.py ./app/*.py ./tests/*.py`.
- Docker (optional): `docker build -t chatgpt-in-slack .`
- Serverless (optional): `serverless deploy` (Python 3.9 runtime).

## Coding Style & Naming Conventions
- Python 3.9+, 4-space indentation, UTF-8.
- Formatting: Black; Lint: flake8 (`max-line-length=125`, ignores in `.flake8`).
- Names: modules/files `snake_case.py`; functions/vars `snake_case`; classes `PascalCase`.
- Keep functions small; pure helpers in `app/` and Slack/OpenAI wiring separate.

## Testing Guidelines
- Framework: pytest; tests under `tests/` named `*_test.py`.
- Prefer fast, deterministic unit tests (no network). Use fakes/mocks (see `tests/openai_ops_test.py`).
- Run `pytest -q` locally; ensure `./validate.sh` passes before PRs.

## Commit & Pull Request Guidelines
- Commits: concise, imperative mood. Examples: "Add reasoning models support", "Refactor: Centralize model settings", "Fix markdown spacing". Reference PRs/issues when relevant.
- PRs: clear description, rationale, and scope; link issues; include screenshots of Slack UI when applicable; note config changes. All checks must pass (`./validate.sh`).

## Security & Configuration Tips
- Never commit secrets. Copy `.env.example` to `.env` and set `OPENAI_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` (and Azure vars if used).
- Prefer Socket Mode locally; production via Docker or `serverless.yml`.
