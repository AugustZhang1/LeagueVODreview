# Plan: Stage 1 build

Step-by-step plan for Stage 1 (win model + basic review), including the progress page. Later stages are outlined at the end and get their own plan when Stage 1 is done. See `Overview.md` for the what and why.

Reviewed with Antigravity (Gemini 3.8 Flash High); the changes from that review are agreed and included.

## Where things run

| Part | Runs on | Load |
|---|---|---|
| Crawler + progress page | Google Cloud free `e2-micro` VM, one process | low CPU, ~200 MB RAM |
| Training (pilot and real) | Kaggle notebook, started from the Kaggle website | a few minutes per run |
| Review app (backend + frontend) | Laptop | about one browser tab; nothing heavy |
| Data | VM + private Kaggle dataset | never in the repo |

## Inputs needed from you

- ~~Your rank and server~~ **Gold III, NA1.**
- ~~Servers to crawl~~ **NA1 (Americas), EUW1 (Europe), KR (Asia)**, one per regional cluster.
- **Accounts** (Step 1).

## Repo layout

```
LeagueVODreview/
  Overview.md  Plan.md  README.md
  pyproject.toml              # one Python package, pinned deps
  config.toml                 # servers, tier order, patch window, batch size
  lolreview/
    riot.py                   # Riot API client + rate limiter
    features.py               # match + timeline + tier -> rows (shared by crawler, training, review)
    state.py                  # SQLite crawl state
    crawler.py                # crawl loop, one thread per cluster
    status.py                 # progress page (built-in http.server, runs inside the crawler)
    upload.py                 # push the Parquet folder to Kaggle
    review.py                 # score one game -> review JSON
    api.py                    # review app backend (FastAPI, laptop)
  training/
    train.py                  # pasted into / attached to the Kaggle notebook
  frontend/                   # Vite + React + TypeScript
  deploy/
    setup_vm.sh  lolcrawler.service
  tests/
    fixtures/                 # 3 real match + timeline JSONs
    test_riot.py  test_features.py
```

Python 3.12, venv + pip.
- **VM:** `requests`, `pyarrow`, `kaggle`.
- **Kaggle:** `pandas`, `lightgbm`, `scikit-learn`, `matplotlib` (preinstalled).
- **Laptop:** `fastapi`, `uvicorn`, `lightgbm` (only to load the model).

---

## Step 1 — Accounts and keys (you, ~30 min)

1. **Riot:** log in to developer.riotgames.com, copy the dev key, and register a personal API key (description: private research project, no public users). Use the dev key until it's approved.
2. **Google Cloud:** create an account (card required); free trial, so no budget alert. The VM itself is made in Step 7.
3. **Kaggle:** create an account, verify your phone (needed for private datasets and notebook internet), and generate an API token (`KGAT_…`).

**Done when:** you have a working dev key, a GCP project, and a Kaggle token, with both keys in `.env` (gitignored; see `.env.example`).

## Step 2 — Riot client and rate limiter (`riot.py`)

- `requests.Session`; API key read from `RIOT_API_KEY` in `.env`. On 401/403 the key is treated as expired: the client re-reads `.env` every 60 s until a working key appears, and the progress page shows "key expired".
- **Rate limiter: one per regional cluster** (`americas`, `europe`, `asia`), shared by that cluster's platform calls (`na1` uses the `americas` limiter). Two sliding windows, 20 per 1 s and 100 per 120 s, run with a safety margin (18 and 95). It switches to the `X-App-Rate-Limit` header values once seen, so a personal key needs no code change. The margin matters because Riot can disable keys that keep hitting 429s.
- **Errors:**
  - 429 → sleep `Retry-After` seconds (10 s if missing), retry.
  - 5xx → retry with backoff 2, 4, 8 … 60 s, up to 5 tries, then mark the item failed.
  - 404 → skip the item.
- **Routing:** a `PLATFORM_TO_CLUSTER` map (`na1 → americas`, `euw1 → europe`, `kr → asia`). account-v1 and match-v5 use the cluster; league-v4 uses the platform.
- **Functions:**
  - `apex_league(platform, tier)`: Challenger / Grandmaster / Master each have their own endpoint (`challengerleagues`, `grandmasterleagues`, `masterleagues` `/by-queue/RANKED_SOLO_5x5`).
  - `league_entries(platform, tier, division, page)`: `/entries/RANKED_SOLO_5x5/{tier}/{division}` for Diamond and below.
  - `match_ids(cluster, puuid, queue=420, start_time, count)`, `match(cluster, id)`, `timeline(cluster, id)`.
  - `account_by_riot_id(cluster, name, tag)`, `rank_by_puuid(platform, puuid)`.

**Done when:** a unit test with a fake clock shows the limiter never exceeds either window, and a live call fetches one match and its timeline.

## Step 3 — Look at real data before writing features

- A small script fetches ~20 recent ranked solo games from Challenger. Three are saved to `tests/fixtures/` as test data.
- Confirm from real JSON:
  - event names and fields (`bounty`, `shutdownBounty` on kills),
  - `BUILDING_KILL.teamId` (the team that **lost** the building),
  - `monsterSubType` values for each dragon, Elder and Void Grubs,
  - any objective new in 2026,
  - Baron and Elder buff durations and the inhibitor respawn time for this patch,
  - the `gameVersion` format, for patch filtering.

**Done when:** field names are confirmed and the fixtures are saved.

## Step 4 — Feature extraction (`features.py`)

`extract_rows(match, timeline, tier)` → rows. The match data has no rank, so `tier` is passed in: the crawler passes the tier of the player the game was found through; a review passes the reviewed player's tier.

- **Skip** non-ranked-solo games (`queueId != 420`) and remakes (`gameDuration < 300`). Check this on the match data, before fetching the timeline.
- **Training rows:** one per minute frame plus one right after each kill, elite monster, building or plate event.
- **State** is built by walking events in time order:
  - Gold per team = sum of `totalGold` at the last minute frame + kill bounties since that frame. No interpolation, no passive-gold simulation.
  - CS and level: carried forward from the last minute frame.
  - Towers: credited to the team that did **not** own the building (`teamId` is the owner).
- **Features:**
  - `tier`: Iron = 0 … Challenger = 9, Pro = 10
  - `minute`
  - `gold_diff, kill_diff, tower_diff, level_diff, cs_diff, grub_diff` (blue − red)
  - `inhibs_down_diff`: red inhibitors currently down − blue inhibitors currently down
  - `baron_active`, `elder_active`: +1 if blue has the buff right now, −1 if red, 0 if nobody
  - `blue_dragons`, `red_dragons`: elemental dragon counts
  - `soul_diff`: +1 if blue has soul, −1 if red, 0 if nobody
  - `soul_type`: the 3rd dragon's type, `none` before that; categorical
- **Extra columns:** `match_id, platform, patch, duration_s, t, blue_won`.
- Small dtypes (`float32`, `int16`, `dictionary`) to keep files small.
- A review uses the same `state_at(…, t)` code at every 15 s, so features are built the same way at scoring time.

**Tests (on the fixtures):**
- Final-row kills, towers, dragons and barons per team match the totals in the match data.
- At each minute frame, team gold equals the sum of `totalGold`.
- No future leak: rows built from a timeline cut off at time `t` are identical to rows built from the full timeline.

**Done when:** all tests pass on the 3 fixtures.

## Step 5 — Crawler (`crawler.py`, `state.py`)

One process with one thread per cluster (NA1, EUW1, KR). Each thread has its own SQLite file, so there's no locking.

1. **Seed players, top-down, in passes:** Challenger → Grandmaster → Master → Diamond → Emerald → Platinum → Gold → Silver, taking up to 20,000 games per tier per cluster each pass (spread across the tier's divisions). When a pass reaches Silver, the next pass adds another 20,000 per tier, until the next patch.
   Without the cap, Diamond alone would take weeks and the crawl would never reach Gold (your tier) before the patch changes. With it, NA reaches Gold about 4 days into a patch. Silver is the bottom because it's one tier below yours; this is a single setting in `config.toml`.
2. **Match IDs:** for each player, `match_ids(queue=420, startTime=<start of patch window>, count=100)`. New IDs go into `matches` (primary key, so duplicates are dropped), tagged with that player's tier.
3. **Games:** for each pending match: fetch match → skip if remake or outside the patch window → fetch timeline → `features.py` → add rows to an in-memory buffer.
4. **Batches:** every 500 games, write `data/<platform>/<patch>/part-00001.parquet` (zstd), then mark those matches done and record the batch in one transaction. After a crash, unflushed games are simply fetched again.
5. **Rolling window:** batch folders older than the last ~3 patches are deleted to fit the 30 GB disk. When a new patch appears, players are re-crawled from the top for new games.

- **SQLite tables:** `players (puuid, tier, crawled_at)`, `matches (match_id PK, tier, status)`, `batches (file, patch, games, rows, written_at)`, `counters (minute, requests, http_429, http_5xx)`, `errors (last 50)`.
- **Memory:** pyarrow only, no pandas.
- **Throughput:** ~1,300 games/hour per cluster, ~90k games/day with all three.

**Done when:** a short local test run (a few minutes, dev key) writes a batch of Parquet, and stopping and restarting resumes with no duplicates.

## Step 6 — Progress page (`status.py`)

A small page served by Python's built-in `http.server`, running in a thread inside the crawler process, so there's no extra service or framework. It listens only on `127.0.0.1:8080`, so it isn't exposed to the internet and needs no login. The page reloads itself every 5 minutes.

To open it from the laptop:

```
gcloud compute ssh lol-crawler --zone us-central1-a -- -L 8080:localhost:8080
```

then browse to `http://localhost:8080`.

```
┌─ Crawl progress ─────────────────────────────── updated 21:04 ─┐
│ Key: OK            429s last hour: 0       Last batch: 2 min ago │
├─ Per cluster ──────────────────────────────────────────────────┤
│ NA1   Now crawling: Master      41,200 games   1,302/h          │
│ EUW1  Now crawling: Diamond I   44,950 games   1,288/h          │
│ KR    Now crawling: Master      39,870 games   1,310/h          │
├─ By tier ──────────────────────────────────────────────────────┤
│ Challenger ██████████ done   Grandmaster ██████████ done        │
│ Master     ██████░░░░ 61%    Diamond I   █░░░░░░░░░ 8%          │
├─ Data ─────────────────────────────────────────────────────────┤
│ Patches kept: 26.19 (58%) 26.18 (42%)   Rows 19.2M   Disk 1.4 GB│
│ Blue win rate 50.6%   Avg length 29:12                          │
├─ Kaggle ───────────────────────────────────────────────────────┤
│ Last upload: 98,000 games, 3 days ago                           │
├─ Recent errors ────────────────────────────────────────────────┤
│ 20:41 503 on timeline KR_712... retried OK                      │
└────────────────────────────────────────────────────────────────┘
```

- **Progress:** games per cluster, games per hour, current tier, how far through each tier.
- **Health:** key status (a red "KEY EXPIRED" banner with the update command when it's dead), 429 and 5xx counts, last error, time since last batch.
- **Data sanity:** blue win rate (should be ~50%), average game length, patch mix, rows, disk used. These catch extraction bugs early.
- **Kaggle:** time and size of the last upload.

**Done when:** the page shows live numbers during the local test run.

## Step 7 — Deploy the crawler to the VM

- **VM:** `e2-micro`, `us-central1` (must be `us-west1`, `us-central1` or `us-east1` to stay free), Debian 12, 30 GB standard disk, no open ports besides SSH.
- **`deploy/setup_vm.sh`**, in this order:
  1. create and turn on a 2 GB swap file first, so installs don't run out of memory,
  2. install Python, create a venv, get the code (`git clone`, using a deploy key if the repo is private), `pip install`,
  3. copy `.env` (Riot key + Kaggle token) into the repo folder on the VM, `chmod 600`,
  4. install `lolcrawler.service` (systemd, `Restart=always`, starts on boot).
- **Updating the dev key** (until the personal key arrives), from the laptop:
  ```
  gcloud compute ssh lol-crawler -- "sed -i 's/^RIOT_API_KEY=.*/RIOT_API_KEY=NEW_KEY/' ~/LeagueVODreview/.env"
  ```
  The crawler picks it up within a minute.

**Done when:** the service survives `sudo reboot`, and the progress page shows the game count rising.

## Step 8 — Pilot crawl on the VM

Let the VM crawl for ~1 hour (~4,000 games across 3 clusters).

**Check:**
- the size per game on disk, to confirm the upload sizes,
- blue win rate, game lengths and tiers on the progress page look sane,
- no repeated 429s.

## Step 9 — Upload to Kaggle (`upload.py`)

- Runs `kaggle datasets create -p ~/data` the first time and `kaggle datasets version -p ~/data --dir-mode zip -m "<n> games"` after that, with a private `dataset-metadata.json`.
- Uploads the batch folders as they are (no merging), recent patches only.
- Run it by hand over SSH when you want to train (the pilot, then per patch or weekly). Each upload counts against the VM's 1 GB/month of free outbound traffic; worst case is a few cents over.

**Done when:** the dataset appears, private, on Kaggle.

## Step 10 — Train on Kaggle (`training/train.py`)

A Kaggle notebook attached to the dataset, run with **Save & Run All** on the Kaggle website. The log updates live while it runs. When it finishes, download `model.txt` and `metrics.json` from the Output tab into `models/` on the laptop.

1. Load the Parquet folder. Keep the configured patch window.
2. Split by `match_id`: 70% train / 10% validation / 20% test.
3. **Baseline:** LogisticRegression (standardized numbers, one-hot `soul_type`).
4. **LightGBM:**
   - binary objective, learning rate 0.05, 31 leaves,
   - early stopping on validation log loss,
   - `soul_type` as a categorical feature,
   - **monotone constraints:** +1 on `gold_diff, kill_diff, tower_diff, inhibs_down_diff, baron_active, elder_active, grub_diff, soul_diff, level_diff, cs_diff, blue_dragons`, −1 on `red_dragons`; none on `tier`, `minute`, `soul_type`. Taking an objective can then never lower your win %, which keeps the review graph sensible.
5. **Evaluate on the test set, for both models:**
   - accuracy, log loss and Brier score per minute bucket (0–5, 5–10, …, 40+), overall, and per tier,
   - calibration table and plot (10 bins).
6. **Only if needed:** if the calibration plot bends away from the diagonal, fit isotonic calibration on the validation set and check again.
7. Feature importance.
8. **Saves:** `model.txt`, `metrics.json`, `calibration.png`, `accuracy_by_minute.png`, `report.md`.

**First run is the pilot** (~4,000 games), just to prove the pipeline works. Optionally also run the model code on the Kaggle "Diamond Ranked Games (10 min)" dataset (expect ~72% accuracy) to check the metric code against a known result.

**Done when** (on the full data):
- test accuracy at 10 minutes is about 70% or better,
- each calibration bin is within about ±3 points of the diagonal,
- LightGBM beats the LogisticRegression baseline on log loss.

## Step 11 — Full crawl and retraining

The crawler keeps running. Retrain (Step 9 upload, then Step 10) when a new patch has enough games, or weekly.

## Step 12 — Pro games (optional, after Step 11 works)

Pro esports games aren't in the public Riot API. The only full-timeline source is the unofficial lolesports livestats feed (10 s frames: team gold, kills, towers, dragons, barons, inhibitors; player level and CS; no positions).
- A small separate extractor maps it to the same features with `tier = 10`.
- The feed is undocumented, changes often and can go down, so this step is skipped if it isn't usable. High-elo solo queue alone is enough to train a good model.

## Step 13 — Review backend (`review.py`, `api.py`, laptop)

**Endpoints:**
- `GET /api/player/{platform}/{name}/{tag}` → puuid, rank, and the last 10 ranked solo games (champion, result, KDA, length, date).
- `GET /api/review/{match_id}` → the review JSON.
- `GET /api/model` → `metrics.json`, for the Model page.

**Cache:** `cache.db` (SQLite) stores raw match + timeline JSON, match summaries and computed reviews, so reloading a player's history or a review costs no API calls.

**Building a review:**
1. Rows from `features.py` every 15 s, plus just before and just after each event. `tier` = the player's current rank.
2. Run the model. Flip to your team's side (1 − p if you're red).
3. **Group events into moments:** kills and objectives within 20 s of each other become one moment. Its value = win % after the group − win % before.
4. **Grades** (thresholds are adjustable):

   | Swing for your team | Grade |
   |---|---|
   | +10% or more | `!!` |
   | +5% to +10% | `!` |
   | −5% to −10% | `?` |
   | −10% or worse | `??` |
   | under 5% either way | listed, no grade |

5. **Description** from a template: who killed whom (champions), where (map zone from x, y), and the objective taken. Moments you were involved in are marked.
6. **Per-minute snapshots** for the scoreboard and minimap: each player's position, level, K/D/A, CS, gold, and items.

**Done when:** reviewing one of your games takes under 3 s the first time, and the win % ends near 100% or 0% to match the result.

## Step 14 — Review frontend (`frontend/`)

**Search page:** Riot ID + server → your last 10 ranked games. Click one to open its review.

**Review page** (the mock in `Overview.md`):
- **Win % graph:** Recharts area chart from your team's side, with a 50% line and markers at graded moments. Clicking the graph moves the scrubber there.
- **Scrubber:** slider from 0 to the end of the game, ◀ ▶ to jump to the previous/next event, arrow keys.
- **Minimap:** canvas over Data Dragon's `map11.png`.
  - Game coordinates have y pointing up and canvas y points down, so `canvas_y = (1 − y / 15000) × height`.
  - Positions exist only once a minute, so icons show the last known position and fade as it gets older.
  - Dead players are greyed out; recent kills show as ✕ marks.
- **Scoreboard at the selected time:** 10 players with level, K/D/A, CS, gold, items.
- **Key moments list:** grade, time, description, Δ%. Clicking one jumps to it.

**Model page:** accuracy by minute and by tier, calibration chart, log loss, games trained on, patches (from `/api/model`). This shows how much to trust the numbers.

- Champion and item icons come from Data Dragon.
- **Not in Stage 1:** the "Open replay" button.

**Done when:** you can search your Riot ID and review your last game end to end.

## Step 15 — End-to-end check

Review 5 of your own games. Check that:
- big swings line up with barons, aces and inhibitors,
- the graph ends at about 0% or 100%,
- the moment descriptions match what happened.

Anything off becomes a fix to the features or the grade thresholds.

---

## Where to see what

| What | Where | How to open |
|---|---|---|
| Crawl progress | Progress page on the VM | SSH tunnel → `http://localhost:8080` |
| Training while it runs | Kaggle notebook log | Kaggle website |
| Training results | Model page in the review app (+ `report.md`) | `http://localhost:5173/model` |
| Game reviews | Review app | `http://localhost:5173` |

## Milestones

Each one works on its own:

| # | Steps | Result |
|---|---|---|
| M1 | 1–4 | Features extracted from real games, tested |
| M2 | 5–6 | Crawler + progress page working (short local test) |
| M3 | 7–10 | Crawler on the VM; pilot data trained on Kaggle |
| M4 | 11 | Full crawl running; real model + metrics |
| M5 | 13–15 | Review app working on your games |
| (opt) | 12 | Pro games added |

## Later stages (outline only)

Each reuses `features.py`, the crawler, and the review app. Each gets a detailed plan when Stage 1 is done.

- **Stage 2, windows:** alive counts, death timers, enemy jungler last seen, objective timers, recent wards, position snapshots. Shown as a "missed windows" panel.
- **Stage 3, best plays:** label the play taken in each window, train with the play as a feature, rank swapped-in plays with how often each was seen.
- **Stage 4, enemy camp estimates.**
- **Stage 5 (optional), minimap computer vision** on your own replays, trained with Kaggle's free GPU.

## Risks

| Risk | Handling |
|---|---|
| Repeated 429s can get the key disabled | One limiter per cluster with a safety margin; honor `Retry-After` |
| Dev key expires daily until the personal key is approved | Crawler pauses; progress page shows a banner and the update command |
| New objectives or season changes | Step 3 checks real data before features are written |
| Patch drift | Rolling window of recent patches; retrain per patch |
| Data volume (~90k games/day) | Training rows per minute + per event; old patches deleted; uploads only when retraining |
| 1 GB RAM on the VM | Swap file first; pyarrow only; one process |
| High elo dominates the data while you're Gold | Per-tier cap per pass so Gold is reached in days; `tier` feature; Model page shows accuracy per tier |
| Better teams get early kills (skill confounding) | "Teams that did X won Y% more" wording |
| Pro feed is unofficial | Optional step; skipped if unusable |
| Personal key = private use only | App stays private |
| After the 90-day GCP trial, the VM's external IPv4 may cost ~$3.65/month (Google lists $0.005/h, with no free-tier exception) | Free during the trial; check Billing → Reports in the first week to see the real cost lines, then decide before the trial ends |
