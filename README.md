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
