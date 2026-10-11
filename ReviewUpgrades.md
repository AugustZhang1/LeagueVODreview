# Review upgrades (branch `review-upgrades`, 2026-10-11)

Twenty ideas came out of a review of competitors, player requests, adjacent products (chess.com,
Lichess, Leetify, sports win probability) and this repo. This file says which are buildable now,
and specifies the ones being built in this round.

## Viability

| # | Idea | Verdict | Why |
|---|------|---------|-----|
| 1 | "How to read this" guide | **Build** (task A) | Frontend only |
| 2 | "Your biggest mistakes" card | **Build** (task A) | Frontend only, from `review.moments` |
| 3 | Objective timers and counts | **Build** (task D1) | `GameState.dragon_pit_in_ms` / `baron_pit_in_ms` exist; grub/Herald/Baron counts are already in `TeamState` but hidden |
| 4 | Finish the Miss detail, show used windows | **Build** (task C) | Frontend only; `window.taken` and `review.moments` have the data |
| 5 | Smarter grading | **Partly** (task D2) | Early-game caution note: yes. "Don't flag the common play" needs Stage 3 data: later. Suppressing grades in decided games isn't needed: swings are already in win-chance space, so they're small there, and a real throw from 95% should still be flagged |
| 6 | Comeback / thrown-lead tag | **Build** (task A) | From `review.curve` |
| 7 | Lane-diff chart | **Build** (task B) | Snapshots every 15 s already carry each player's gold and CS |
| 8 | Stats vs your rank (percentiles) | Later | The crawler stores team-level feature rows, not per-player CS/vision, so there's no baseline yet; needs a crawler change and a re-crawl |
| 9 | "Why" drivers per moment | **Build** (task D2) | LightGBM `pred_contrib=True`; linear terms for the placeholder model |
| 10 | Enemy jungler last seen | Skip | Windows open when the enemy jungler is *dead*, so where he was seen adds little; timeline positions are true positions, not vision |
| 11 | Patterns across your games | Next round | Needs a new endpoint and stored reviews per player; worth doing once this round is merged |
| 12 | Stage 3 best plays | Later | Large; needs a retrain (Plan.md Steps 21-23) |
| 13 | Retry this moment | Later | Builds on 12 |
| 14 | Notes on a game | **Build** (task B) | Saved in the browser (localStorage). Sharing needs hosting: later |
| 15 | Unseen-patch and unseen-rank evaluation | **Build** (task E) | `data/<platform>/16.17-16.19/v3` is on the laptop; reuse `training/train.py` helpers like `scripts/compare_models.py` does |
| 16 | Check grades against real outcomes | You | Needs you to watch replays (TODO Step 15, Handoff "Next" 2-3) |
| 17 | Automatic retraining | Later | Ops work on the VM and Kaggle |
| 18 | Latency and dataset numbers | **Build** (task E, F) | A benchmark script and a dataset report script |
| 19 | Shareable links with preview cards | After the production key | Riot forbids public use on a personal key |
| 20 | Discord bot | After the production key | Same |
| - | Hosted app limited to your own games | **Build** (task F) | Off unless `LOLREVIEW_ALLOWED_PLAYERS` is set; keeps the hosted app within the personal key's terms until a production key is approved |
| - | Apply for a Riot production key | You | developer.riotgames.com, Register Product. Approval can take months |

## Rules for every task

- Work only in the files your task lists. Other tasks run at the same time in the same folder, so
  a failing test or type error in a file you don't own is someone else's, not yours: ignore it.
- Don't commit, don't switch branches, don't run `git stash`, `git checkout` or `git reset`.
- Match the code around you: same naming, comment density, CSS-module style, test style. Read the
  neighbouring files first. Keep it simple; no new dependencies.
- Python is `.venv/Scripts/python.exe` (Windows, Git Bash). Run from the repo root:
  - tests: `.venv/Scripts/python.exe -m pytest -q tests/<your test files>`
  - lint: `.venv/Scripts/python.exe -m ruff check <your files>` and
    `.venv/Scripts/python.exe -m ruff format <your files>`
- Frontend, from `frontend/`:
  - tests: `npx vitest run <your test files>`
  - types: `npx tsc -b --noEmit` (errors in files you don't own: ignore)
  - lint: `npx eslint <your files>` and `npx prettier --write <your files>`
  - don't run Playwright (`npm run e2e`); it's run once at the end.
- New Review JSON fields always get a default (`= []`, `= None`), so old cached reviews and the
  saved games in `frontend/src/mocks/showcase.json` still load; the UI hides a feature whose data
  is missing.
- When you're done, reply with: files changed, what you built, the exact test/lint commands you
  ran and their results, and anything you weren't sure about.

## Task A: header (ideas 1, 2, 6)

Files: `frontend/src/pages/review/ReviewHeader.tsx`, `ReviewHeader.module.css`, new
`HowToRead.tsx` (+ `.module.css`), new `TopMistakes.tsx` (+ `.module.css`), new
`ReviewHeader.test.tsx`.

1. **How to read this.** A `<details>` with summary "How to read this", rendered at the end of the
   header body. Plain text:
   - Win chance is the model's estimate of your team's chance to win at that moment, from games
     at your rank. It's not a prediction of this game.
   - The four grades with their names from `lib/grades.ts`: !! Great (+10% or more), ! Good
     (+5%), ? Mistake (−5%), ?? Blunder (−10% or worse), measured from just before a moment to
     just after it.
   - "Miss" rows: a stretch when the enemy was weak (their jungler or 2+ players dead) and an
     objective or tower was up; "worth ~+7%" is how much your team's win chance would have gone
     up by taking the best option.
   - The model is least sure in the first 5 minutes.
2. **Your biggest mistakes.** `TopMistakes` lists up to 3 moments with `involves_me` and a grade of
   `?` or `??`, most negative `delta` first: time, title, `<Delta>`. Each is a link built like
   the "Biggest swing" link in `ReviewHeader.tsx` (real `href`, `onClick` calls `onJump`). With no
   such moment, show "No mistakes graded against you in this game." Rendered under the facts row.
3. **Comeback / thrown lead.** From `review.curve` (ignore the last point, which is the result):
   on a win whose lowest `p` is below 0.2, a fact "Comeback" with "from 12% at 18:40"; on a loss
   whose highest `p` is above 0.8, "Thrown lead" with "from 85% at 22:10". Put the logic in an
   exported pure function `comebackOf(review)` returning `{ kind: "comeback" | "thrown", p, t } |
   null`. Use `formatWinChance` and `formatTime` from `lib/format.ts`. No link.
4. Tests (Vitest + Testing Library, like `MomentDetail.test.tsx`): `comebackOf` on a made-up curve
   (comeback, thrown, neither); `TopMistakes` ordering, the 3-item cap and the empty text; the
   guide renders its summary. Use `src/mocks/review.fixture.json` or a small hand-made `Review`.

## Task B: lane chart and notes (ideas 7, 14)

Files: `frontend/src/pages/review/ReviewPage.tsx`, `ReviewPage.module.css`, new `LaneDiff.tsx`
(+ `.module.css`, `laneDiff.ts`, `laneDiff.test.ts`), new `GameNotes.tsx` (+ `.module.css`,
`GameNotes.test.tsx`), and `ReviewPage.test.tsx` if it needs updating.

1. **Lane diff.** A pure function in `laneDiff.ts`: `laneDiff(review)` finds my player
   (`is_me`) and the enemy player with the same `role`, and returns one point per snapshot:
   `{ t, gold, cs }`, each my value minus theirs (`snapshot.players` by `participant_id`). Return
   null when there's no opponent. Also export `diffAt(points, t)`: the point at or just before `t`.
   `LaneDiff` is a `Panel` titled "Lane vs <opponent champion_name>": a Recharts line chart of
   gold diff over time (see `src/pages/model/AccuracyChart.tsx` for chart style and tokens), a
   zero line, and a vertical line at the current `t`; under it "At 10:00: +450 gold, +8 CS" and
   the same at 15:00 (only for times inside the game). Gold with `formatGoldDelta`, time with
   `formatTime`.
2. **Notes.** `GameNotes` is a `Panel` titled "Notes" with a `<textarea>` (label "Your notes on
   this game") and a button "Add time" that appends the current time as `12:34 ` on a new line.
   Saved to `localStorage` under `lolreview:notes:<matchId>:<participantId>` on every change;
   loaded on mount. Wrap `localStorage` access in try/catch (private mode). The page's keyboard
   shortcuts already ignore textareas.
3. In `ReviewPage.tsx`, render both under the existing panels grid (lane chart, then notes), in a
   new row styled in `ReviewPage.module.css`. Don't touch the skeleton.
4. Tests: `laneDiff` on the mock fixture (opponent found, point count equals snapshot count, signs
   right), `diffAt`; `GameNotes` saves, loads and "Add time" inserts the time.

## Task C: missed windows (idea 4)

Files: `frontend/src/pages/review/WindowDetail.tsx`, `useReviewTime.ts`, `MomentList.tsx`,
`MomentList.module.css`, `MomentDetail.module.css` only if a new class is needed (add, don't
change existing ones), and new or updated tests for them.

1. `useReviewTime.ts` keeps every window (drop the `!w.used` filter), still sorted by `t_start`.
2. `MomentList.tsx`: a used window is a row with badge "Used" (a new `styles.used` class, in the
   good/blue colour tokens used by `!`) instead of "Miss", `aria-label="Used window"`. Filter
   "All" shows both; "Missed" shows only `!used` windows.
3. `WindowDetail.tsx` gets the moments too (`MomentList` passes its `moments` prop):
   - used: "Your team took: Dragon, bot outer tower" from `w.taken` (dedupe, keep order);
   - missed: heading "What happened instead", then the moments whose `t_end` lies in
     `[w.t_start, w.t_end + 10]`, each as time, title and `<Delta>`; with none, the current
     sentence "Your team didn't take an objective or tower in time."
4. Tests for both detail cases and the "Missed" filter. Check `src/pages/pages.test.tsx` and
   `ReviewPage.test.tsx` for assertions about Miss rows that now need "Used" rows too; update
   only what this change breaks.

## Task D1: objective timers and counts (idea 3)

Files: `lolreview/schemas.py`, `lolreview/review.py`, `lolreview/windows.py`,
`lolreview/api.py` (only the `REVIEW_FORMAT` line), `tests/test_review.py`,
`tests/test_windows.py`, `frontend/openapi.json`, `frontend/src/api/types.ts`,
`frontend/src/api/models.ts`, `frontend/src/mocks/review.fixture.json`,
`frontend/src/mocks/makeReview.ts`, `frontend/src/pages/review/board/boardModel.ts`,
`boardModel.test.ts`, `Scoreboard.tsx`, `Scoreboard.module.css`, `Scoreboard.test.tsx`.

1. Backend. In `windows.py`, move the "which monster is next in the Baron pit" logic out of
   `_monster_options` into `baron_pit_monster(state, cfg) -> Literal["grubs", "herald", "baron"]`
   and use it there (behaviour unchanged). In `schemas.py` add
   `class Objectives(BaseModel): dragon_in_s: float; dragon_kind: Literal["dragon", "elder"];
   baron_pit_in_s: float; baron_pit_kind: Literal["grubs", "herald", "baron"]` and
   `objectives: Objectives | None = None` on `Snapshot`. Fill it in `review._snapshot` from
   `state.dragon_pit_in_ms`, `state.baron_pit_in_ms` (seconds), `baron_pit_monster`, and
   `"elder"` when either team has a soul. Bump `REVIEW_FORMAT` in `api.py` to 3.
2. Regenerate, in order: `.venv/Scripts/python.exe scripts/export_openapi.py`, then in
   `frontend/` `npm run gen:api`, then `.venv/Scripts/python.exe scripts/make_mock_review.py`.
   Export `Objectives` from `models.ts`. Make `makeReview.ts` produce the field.
3. Tests: at 2:00 the Baron pit kind is grubs and `dragon_in_s` is 3:00 (300 − 120 s, see
   `config.toml [timers]`); after a soul, `dragon_kind` is elder; `_monster_options` unchanged
   (existing window tests still pass).
4. Frontend. `buildHeader` adds `grubs`, `heralds`, `barons` (numbers). `Scoreboard`'s team
   header shows "Grubs n", "Herald n", "Baron n" pairs only when n > 0. Above the table, one
   line: "Dragon 1:12 · Grubs 0:40", or "Dragon up" when 0; "Elder" / "Herald" / "Baron" by
   kind. The timers count down with `t` between snapshots the way death timers do
   (`snapshot value − (t − snapshot.t)`, floored at 0). Hidden when `snapshot.objectives` is
   missing. Tests in `boardModel.test.ts` and `Scoreboard.test.tsx`.

## Task D2: why each moment swung, early-game note (ideas 9, 5)

Runs after D1 is merged. Files: `lolreview/model.py`, `lolreview/review.py`,
`lolreview/schemas.py`, `lolreview/describe.py`, `lolreview/api.py` (`REVIEW_FORMAT` only),
`tests/test_model.py`, `tests/test_review.py`, the generated files as in D1,
`frontend/src/pages/review/MomentDetail.tsx`, `MomentDetail.module.css`,
`MomentDetail.test.tsx`.

1. `WinModel.contributions(rows) -> list[dict[str, float]]`: per row, each feature's
   contribution to the blue log-odds. `TrainedModel`: route rows by tier exactly like `predict`,
   then `booster.predict(x, pred_contrib=True)`; columns are `self.columns` plus a last bias
   column (drop it). `PlaceholderModel`: `w * value` for `WEIGHTS`, `factor * w * value` for
   `SCALED_WEIGHTS`. Champion columns (`champ_wr_diff`, `scaling_diff`) come out of `_encode`.
2. `describe.py`: `FEATURE_LABELS`, a plain-English label per feature in `features.py`'s
   `FEATURE_COLUMNS` and `CHAMPION_FEATURES` ("Gold lead", "Towers", "Players dead",
   "Baron buff", "Dragon soul", ...). Unknown names fall back to the raw name.
3. `schemas.py`: `class Driver(BaseModel): label: str; change: float` and
   `drivers: list[Driver] = []` on `Moment`. In `build_review`, one `contributions` call for the
   rows at `t_first − 1` and `t_last + 1` of every moment; a driver's `change` is after minus
   before, sign-flipped when my team is red (so positive = good for me), rounded to 3 places.
   Keep the 3 largest by absolute change, skipping `tier` and `minute` and changes under 0.01.
4. Bump `REVIEW_FORMAT` to 4, regenerate as in D1.
5. `MomentDetail.tsx`: under the win-chance line, "Why" and up to 3 rows: label and a small bar
   whose width is |change| relative to the largest, ally colour when positive, enemy when
   negative (reuse the damage-bar classes). Hidden when `drivers` is empty or missing. When
   `moment.t_end < 300`, a muted note: "Early game: the model is least sure in the first 5
   minutes."
6. Tests: contributions sum (plus bias) to the raw log-odds for the placeholder model; drivers
   present, at most 3, sign follows my side; MomentDetail shows/hides the "Why" block and the
   early note.

## Task E: model and dataset numbers (ideas 15, 18)

Files: new `scripts/drift_eval.py`, new `scripts/dataset_report.py`, new
`tests/test_drift_eval.py`, new `tests/test_dataset_report.py`, `training/README.md` (a short
section on both scripts).

1. `drift_eval.py --data data [--features-version 3] [--seed 42] [--max-rows N] [--out file.json]`,
   built like `scripts/compare_models.py` (import `train as T`). Use the version's columns minus
   the champion columns (say so in the output). Two experiments, each one LightGBM fit with the
   first setting of the tuning grid (no tuning), early stopping on a validation split by match:
   - **Unseen patch:** sort patches; train on all but the newest; test once on held-out games of
     the older patches ("seen patches") and once on the newest patch ("unseen patch").
   - **Unseen rank:** train on CHALLENGER, GRANDMASTER and MASTER games; test on held-out
     Challenger-Master games and on DIAMOND games. Skip with a message when a group has under
     200 games.
   For each test set print games, rows, accuracy, log loss, Brier and calibration gap
   (`T.scores`, `T.calibration_table`) as a markdown table, plus the difference. `--out` writes
   the same numbers as JSON.
2. `dataset_report.py --data data`: walks `data/<platform>/<patch>/v<N>/*.parquet` and prints
   games (unique `match_id`) and rows by platform, patch, tier and features version, total
   parquet size on disk, and the duplicate games across files (same `match_id` in more than one
   file). If `data/state-*.sqlite` files exist, also each one's game counts by status (read
   `lolreview/state.py` for the schema; skip quietly if absent).
3. Tests on tiny made-up parquet folders under `tmp_path` (see `tests/test_train.py` for how test
   data is built). Then run both scripts on the real `data` folder once and paste their output in
   your reply.

## Task F: hosted app limits and a latency benchmark (ideas 18, policy)

Files: `lolreview/api.py` (not the `REVIEW_FORMAT` line), `tests/test_api.py`,
`frontend/src/lib/errors.ts` (+ its test if there is one), new `scripts/bench_api.py`,
`deploy/README.md`, `README.md` (one line for the benchmark).

1. **Allow-list.** When the environment variable `LOLREVIEW_ALLOWED_PLAYERS` is set (comma
   separated Riot IDs, e.g. `Me#NA1,Duo#NA1`, compared case-insensitively), read once in
   `create_app`:
   - `/api/player/...` for anyone else answers `ApiError(403, "not_allowed", "This hosted app only
     shows its owner's games.")` before any Riot call;
   - `/api/review/{match_id}` serves a cached review as now, otherwise fetches the match and
     answers the same 403 unless participant `p`'s Riot ID (`riotIdGameName#riotIdTagline`) is
     allowed.
   Unset: no change. `errors.ts`: `not_allowed` shows the server's message, like `demo_only`.
   `deploy/README.md` section 7: how to set it in the systemd unit (`Environment=`), and why
   (a personal key can't serve the public).
2. **Benchmark.** `scripts/bench_api.py [--runs 20]`: builds the app with `create_app(demo=True,
   cache=Cache(<temp file>))` and FastAPI's `TestClient`, then times each demo game's
   `/api/review` cold (first call, builds the review) and warm (later calls, cached), plus
   `/api/player/na1/Me/NA1` warm. Prints p50/p95/max ms per endpoint as a markdown table. Read
   `lolreview/demo.py` for the demo player and games.
3. Tests: allow-list on (allowed player OK, other player 403, review of a non-allowed participant
   403, cached review still served) and off (unchanged), using the existing test helpers in
   `tests/test_api.py`. Run the benchmark once and paste its output.

## Verification (after each task)

Read the diff; run the full suites (`pytest -q`, `ruff check .`, `ruff format --check .`,
`npm run typecheck`, `npm run test`, `npx eslint .`, prettier on changed files, `npm run build`,
`npm run e2e`); open the demo app (`python -m lolreview.app --demo`, search `Me#NA1`) and check
the feature by eye. Commit each task separately once it passes.
