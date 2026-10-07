# LeagueVODreview

Reviews a ranked solo League of Legends game by scoring the win chance every few seconds, grouping kills and objectives into moments, and grading each one. A crawler collects training games, a model learns win chance from them, and a local web app shows the review. See `Overview.md` for the idea and design.

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

## Running the app

1. Build the UI once: `cd frontend && npm ci && npm run build`.
2. From the repo root: `python -m lolreview.app [--port 8000]` serves the API and the built UI at
   `http://127.0.0.1:8000`. It needs a Riot key after `RIOT_API_KEY=` in `.env`; everything fetched
   is cached in `cache.db`.
3. Open the page, enter your Riot ID and pick the game to review. Keys on the review page: ← → step
   through moments, Shift + ← → move 15 s, Home / End, Space plays, `O` opens the replay.

Demo mode (`--demo` or `LOLREVIEW_DEMO=1`) needs no key and no network: it serves the synthetic
games for `Me#NA1` on `na1`, so search for `Me#NA1` to try the app. It keeps its own cache
(`cache-demo.db`), so made-up games never mix with real ones.

**Open replay** jumps the League client's replay to 5 s before the selected time. Set
`EnableReplayApi=1` under `[General]` in the client's `game.cfg`, open the game's replay, and the
button on the review page turns on. Replays only exist for the current patch.

## Frontend

```
cd frontend
npm ci
npm run dev:mock    # UI on mock data, no backend; add ?mock=key_expired, rate_limited, unavailable,
                    # unsupported_queue, server_error, empty or replay_open
npm run dev         # UI on :5173, proxies /api to the backend on :8000
npm run lint && npm run typecheck && npm run test && npm run build
npm run e2e         # Playwright: the mocks, plus the demo backend when .venv and dist/ exist
npm run gen:api     # regenerate src/api/types.ts from openapi.json
```

`npm run e2e` needs a Chromium: CI installs one with `npx playwright install chromium`; the config
also finds one under `PLAYWRIGHT_BROWSERS_PATH`. Set `E2E_DEMO=0` to skip the demo-backend run.

In a dev build, `/dev/components` shows every shared component on the real tokens.

## License

MIT, see `LICENSE`. LeagueVODreview isn't endorsed by Riot Games and doesn't reflect the views or
opinions of Riot Games or anyone officially involved in producing or managing Riot Games
properties. Riot Games and all associated properties are trademarks or registered trademarks of
Riot Games, Inc.
