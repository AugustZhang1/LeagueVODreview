# LeagueVODreview

Reviews a ranked solo League of Legends game by scoring the win chance every few seconds, grouping kills and objectives into moments, and grading each one. A crawler collects training games, a model learns win chance from them, and a local web app shows the review. See `Overview.md` for the idea, `Plan.md` for the build plan and `UI.md` for the app's design.

## Layout

- `lolreview/` the Python package (Riot client, features, model, review, API)
- `training/` Kaggle training script
- `frontend/` the review UI (Vite + React + TypeScript)
- `deploy/` crawler VM setup
- `tests/` tests; `tests/fixtures/synthetic/` holds generated match-v5 games
- `config.toml` servers, timers, grade thresholds; `.env` (from `.env.example`) holds the keys

## Development

```
uv venv -p 3.12 .venv
uv pip install -p .venv -e ".[dev]"
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Regenerate the synthetic games with `.venv/bin/python tests/fixtures/make_synthetic.py` and the API schema with `.venv/bin/python scripts/export_openapi.py`.

## Review app

`python -m lolreview.app [--port 8000]` serves the API and the built UI (`frontend/dist`) at
`http://127.0.0.1:8000`; build the UI once with `cd frontend && npm ci && npm run build`. It needs a
Riot key after `RIOT_API_KEY=` in `.env`. Everything fetched is cached in `cache.db`.

Demo mode (`--demo` or `LOLREVIEW_DEMO=1`) needs no key and no network: it serves the synthetic
games for `Me#NA1` on `na1`.
