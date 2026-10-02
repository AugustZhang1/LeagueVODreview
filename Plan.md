# Plan

Everything that needs to be done, in order: Stage 1 step by step (Steps 1–16), then Stages 2–5 (Steps 17–29). What the UI looks like and how it's built is in `UI.md`. See `Overview.md` for the what and why, and `TODO.md` for the steps only you can do.

Reviewed with Antigravity (Gemini 3.8 Flash High); the changes from that review are agreed and included.

## Changes in this revision

- The plan now covers every stage in detail, not just Stage 1, and the UI has its own plan in `UI.md`.
- **Build order:** the review app is built on the fixtures and a placeholder model while the crawl runs, instead of after it (see "Build order").
- **One key, one rate limit:** the laptop app and the VM crawler use the same Riot key, so they share its limits. The crawler leaves room on Americas and follows Riot's `X-App-Rate-Limit-Count` header (Steps 2 and 13).
- **The review endpoint names the player** (`?p=<participantId>`). Before, it couldn't tell whose side to show.
- **Snapshots every 15 s** (was once a minute), so the scoreboard and minimap match the graph at any time, and the frontend needs no game logic.
- **Step 3 checks more:** Rift Herald, Atakhan, Feats of Strength, `DRAGON_SOUL_GIVEN`, `GAME_END`, item events, map bounds and objective timers.
- **Smaller fixes:** reviews are cached per model version; the graph ends at 100% or 0% at `GAME_END`; a tier fallback for unranked players; any server can be reviewed; `FEATURES_VERSION` so later stages' features don't mix with older batches.
- **New pieces:** `map_data.py`, `schemas.py`, `model.py`, `describe.py`, `app.py`, README, `.env.example`, CI, Riot's legal line in the footer, and Step 16 (Open replay button).

## Where things run

| Part | Runs on | Load |
|---|---|---|
| Crawler + progress page | Google Cloud free `e2-micro` VM, one process | low CPU, ~200 MB RAM |
| Training (pilot and real) | Kaggle notebook, started from the Kaggle website | a few minutes per run |
| Review app (backend + frontend) | Laptop, one command, `http://localhost:8000` | about one browser tab; nothing heavy |
| Data | VM + private Kaggle dataset | never in the repo |

## Inputs needed from you

- ~~Your rank and server~~ **Gold III, NA1.**
- ~~Servers to crawl~~ **NA1 (Americas), EUW1 (Europe), KR (Asia)**, one per regional cluster.
- **Accounts** (Step 1).

## Repo layout

```
LeagueVODreview/
  Overview.md  Plan.md  UI.md  TODO.md  README.md
  .env.example                # RIOT_API_KEY=, KAGGLE_API_TOKEN= (the real .env is gitignored)
  pyproject.toml              # one Python package, pinned deps, ruff + pytest settings
  config.toml                 # servers, tier order, patch window, batch size, timers, grade thresholds
  lolreview/
    riot.py                   # Riot API client + rate limiter
    map_data.py               # map bounds, zones, building and camp positions
    features.py               # match + timeline + tier -> rows (shared by crawler, training, review)
    state.py                  # SQLite crawl state
    crawler.py                # crawl loop, one thread per cluster
    status.py                 # progress page (built-in http.server, runs inside the crawler)
    upload.py                 # push the Parquet folder to Kaggle
    model.py                  # load model.txt (or the placeholder) and predict
    schemas.py                # pydantic types for the API; the UI's types are generated from these
    describe.py               # moment titles from templates
    review.py                 # score one game -> review JSON
    api.py                    # review app backend (FastAPI, laptop)
    app.py                    # `python -m lolreview.app`: API + built UI on :8000
    replay.py                 # Step 16: local Replay API
    windows.py                # Stage 2
    plays.py                  # Stage 3
    camps.py                  # Stage 4
  training/
    train.py                  # pasted into / attached to the Kaggle notebook
  frontend/                   # Vite + React + TypeScript (files listed in UI.md)
  cv/                         # Stage 5 (optional)
  deploy/
    setup_vm.sh  lolcrawler.service
  tests/
    fixtures/                 # 3 real match + timeline JSONs
    test_riot.py  test_features.py  test_review.py  test_api.py
  .github/workflows/ci.yml    # ruff + pytest; frontend lint, typecheck, test, build, e2e on mocks
```

Python 3.12, venv + pip.
- **VM:** `requests`, `pyarrow`, `kaggle`.
- **Kaggle:** `pandas`, `lightgbm`, `scikit-learn`, `matplotlib` (preinstalled).
- **Laptop:** `fastapi`, `uvicorn`, `pydantic`, `requests`, `lightgbm` (only to load the model). Node.js 20+ to build the UI.

## Build order

Two tracks. The data track is slow because the crawl takes days. The app track only needs the fixtures and *some* model, so it runs alongside instead of waiting.

| # | Track | Steps | Needs | Result |
|---|---|---|---|---|
| 1 | You | 1 | — | Keys |
| 2 | Data | 2–4 | dev key | Features from real games, tested (**M1**) |
| 3 | Data | 5–6 | 2–4 | Crawler + progress page, short local test (**M2**) |
| 4 | App | 13, with the placeholder model | 4 | Review JSON for the fixture games and your own games |
| 5 | App | 14 (`UI.md` U1–U11) | U1–U3 need nothing; U4+ need 13 | The review app working, with placeholder numbers |
| 6 | Data | 7–10 | 5–6 | Crawler on the VM, pilot model (**M3**) |
| 7 | App | drop in the pilot model | 10 | Real, rough numbers in the app |
| 8 | Data | 11 (runs for days) | 10 | The real model (**M4**) |
| 9 | Both | 15 | 11 | End-to-end check (**M5**) |
| 10 | App | 16 | 15 | Open replay button (**M6**) |
| 11 | Data | 12 (optional) | 11 | Pro games |
| 12 | Both | 17–29 | M5 | Stages 2–5 (**M7–M10**) |

Rows 4–5 and 6 overlap: the UI gets built while the VM pilot crawls.

**Before a dev key is available**, code is built and tested on **synthetic fixtures**: three made-up games shaped exactly like Riot's documented match-v5 match and timeline JSON (`tests/fixtures/synthetic/`, written by a small generator). They are labelled as synthetic everywhere. Step 3 adds the real fixtures next to them, every test then runs on both, and any field the synthetic games got wrong is fixed in the code.

---

# Stage 1 — Win model + basic review

## Step 1 — Accounts and keys (you, ~30 min)

1. **Riot:** log in to developer.riotgames.com, copy the dev key, and register a personal API key (description: private research project, no public users). Use the dev key until it's approved.
2. **Google Cloud:** create an account (card required); free trial, so no budget alert. The VM itself is made in Step 7.
3. **Kaggle:** create an account, verify your phone (needed for private datasets and notebook internet), and generate an API token (`KGAT_…`).

**Done when:** you have a working dev key, a GCP project, and a Kaggle token, with both keys in `.env` (gitignored; copy `.env.example`).

## Step 2 — Riot client and rate limiter (`riot.py`)

- **Project setup first:** `pyproject.toml` (pinned deps, ruff, pytest), `config.toml`, `.env.example`, a short `README.md` (what this is and how to run each part), and `.github/workflows/ci.yml` running ruff + pytest on every push. The frontend jobs join it in `UI.md` U1.
- `requests.Session`; API key read from `RIOT_API_KEY` in `.env`. On 401/403 the key is treated as expired: the client re-reads `.env` every 60 s until a working key appears, and the progress page shows "key expired".
- **Rate limiter: one per regional cluster** (`americas`, `europe`, `asia`), shared by that cluster's platform calls (`na1` uses the `americas` limiter). Two sliding windows, 20 per 1 s and 100 per 120 s, run with a safety margin (18 and 95). It switches to the `X-App-Rate-Limit` header values once seen, so a personal key needs no code change. The margin matters because Riot can disable keys that keep hitting 429s. (Riot actually counts `na1` and `americas` separately, so sharing is on the safe side; league-v4 calls are few, so little is lost.)
- **Shared key.** The review app on the laptop (Step 13) uses the same key, so it draws on the same limits. Riot reports the key's real usage in `X-App-Rate-Limit-Count`; after each response the limiter takes the larger of its own count and Riot's, so the crawler slows down by itself while the app is busy. The Americas crawler also runs at 80 per 120 s instead of 95, leaving ~15 calls per 2 minutes for the app: enough to load your last 10 games in one go.
- **Errors:**
  - 429 → sleep `Retry-After` seconds (10 s if missing), retry.
  - 5xx → retry with backoff 2, 4, 8 … 60 s, up to 5 tries, then mark the item failed.
  - 404 → skip the item.
- **Routing:** a `PLATFORM_TO_CLUSTER` map. account-v1 and match-v5 use the cluster; league-v4 uses the platform. The crawler only uses `na1 → americas`, `euw1 → europe` and `kr → asia`, but the map lists every platform (from Riot's routing docs, e.g. `br1, la1, la2 → americas`, `eun1, tr1 → europe`, `jp1 → asia`, `oc1, sg2, tw2, vn2 → sea`), so the app can review a game from any server.
- **Functions:**
  - `apex_league(platform, tier)`: Challenger / Grandmaster / Master each have their own endpoint (`challengerleagues`, `grandmasterleagues`, `masterleagues` `/by-queue/RANKED_SOLO_5x5`).
  - `league_entries(platform, tier, division, page)`: `/entries/RANKED_SOLO_5x5/{tier}/{division}` for Diamond and below.
  - `match_ids(cluster, puuid, queue=420, start_time, count)`, `match(cluster, id)`, `timeline(cluster, id)`.
  - `account_by_riot_id(cluster, name, tag)`, `rank_by_puuid(platform, puuid)`.

**Done when:** a unit test with a fake clock shows the limiter never exceeds either window (including when the header reports a higher count than its own), and a live call fetches one match and its timeline.

## Step 3 — Look at real data before writing features

- A small script fetches ~20 recent ranked solo games from Challenger. Three are saved to `tests/fixtures/` as test data.
- Confirm from real JSON:
  - event names and fields (`bounty`, `shutdownBounty` on kills),
  - `BUILDING_KILL.teamId` (the team that **lost** the building),
  - `monsterSubType` values for each dragon, Elder and Void Grubs,
  - any objective new in 2026; in particular whether Rift Herald (`RIFTHERALD`) and Atakhan (`ATAKHAN`) kills are in the events, and whether Feats of Strength (or whatever replaced them) show up,
  - `DRAGON_SOUL_GIVEN`: if present, it gives the soul's team and type directly, so use it instead of counting dragons,
  - `GAME_END` (`winningTeam` and the end time), for the graph's last point,
  - Baron and Elder buff durations and the inhibitor respawn time for this patch,
  - item events (`ITEM_PURCHASED`, `ITEM_SOLD`, `ITEM_DESTROYED`, `ITEM_UNDO` with `beforeId` / `afterId`), for the scoreboard's items,
  - the map's coordinate bounds (min and max of all positions), for the minimap,
  - first-spawn and respawn times of each objective, into `config.toml` (Stage 2 uses them; checking now is free),
  - the `gameVersion` format, for patch filtering.

**Done when:** field names are confirmed, the fixtures are saved, and `config.toml` has the timers.

## Step 4 — Feature extraction (`features.py`)

`extract_rows(match, timeline, tier)` → rows. The match data has no rank, so `tier` is passed in: the crawler passes the tier of the player the game was found through; a review passes the reviewed player's tier.

- **Skip** non-ranked-solo games (`queueId != 420`) and remakes (any participant's `gameEndedInEarlySurrender`, or `gameDuration < 300`). Check this on the match data, before fetching the timeline.
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
  - `herald_diff`, `atakhan_diff` (blue − red): only if Step 3 finds them in the events
- **Extra columns:** `match_id, platform, patch, duration_s, t, blue_won`.
- `FEATURES_VERSION = 1`. Later stages bump it (see Stage 2).
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
4. **Batches:** every 500 games, write `data/<platform>/<patch>/v<FEATURES_VERSION>/part-00001.parquet` (zstd), then mark those matches done and record the batch in one transaction. After a crash, unflushed games are simply fetched again.
5. **Rolling window:** batch folders older than the last ~3 patches are deleted to fit the 30 GB disk. When a new patch appears, players are re-crawled from the top for new games.

- **SQLite tables:** `players (puuid, tier, crawled_at)`, `matches (match_id PK, tier, status)`, `batches (file, patch, version, games, rows, written_at)`, `counters (minute, requests, http_429, http_5xx)`, `errors (last 50)`.
- **Memory:** pyarrow only, no pandas.
- **Throughput:** ~1,300 games/hour per cluster, ~90k games/day with all three (Americas a little lower, because of the room left for the app).

**Done when:** a short local test run (a few minutes, dev key) writes a batch of Parquet, and stopping and restarting resumes with no duplicates.

## Step 6 — Progress page (`status.py`)

A small page served by Python's built-in `http.server`, running in a thread inside the crawler process, so there's no extra service or framework. It listens only on `127.0.0.1:8080`, so it isn't exposed to the internet and needs no login. The page reloads itself every 5 minutes. It uses the review app's colors and fonts (`UI.md`) in an inline `<style>`, with plain tables and no JavaScript.

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
  The crawler picks it up within a minute. Update the laptop's `.env` too; the app re-reads it the same way.

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

1. Load the Parquet folder. Keep the configured patch window and one `FEATURES_VERSION`.
2. Split by `match_id`: 70% train / 10% validation / 20% test, with a fixed seed so later stages compare on the same games.
3. **Baseline:** LogisticRegression (standardized numbers, one-hot `soul_type`).
4. **LightGBM:**
   - binary objective, learning rate 0.05, 31 leaves,
   - early stopping on validation log loss,
   - `soul_type` as a categorical feature,
   - **monotone constraints:** +1 on `gold_diff, kill_diff, tower_diff, inhibs_down_diff, baron_active, elder_active, grub_diff, soul_diff, level_diff, cs_diff, blue_dragons` (and `herald_diff`, `atakhan_diff` if they exist), −1 on `red_dragons`; none on `tier`, `minute`, `soul_type`. Taking an objective can then never lower your win %, which keeps the review graph sensible.
   - **Try on the pilot:** weighting each row by 1 / (rows in its game), so long games and busy fights don't count extra. Keep it if validation log loss is better.
5. **Evaluate on the test set, for both models:**
   - accuracy, log loss and Brier score per minute bucket (0–5, 5–10, …, 40+), overall, and per tier,
   - calibration table and plot (10 bins).
6. **Only if needed:** if the calibration plot bends away from the diagonal, fit isotonic calibration on the validation set and check again.
7. Feature importance.
8. **Saves:** `model.txt`, `metrics.json`, `calibration.png`, `accuracy_by_minute.png`, `report.md`.
   - `metrics.json` holds what the Model page shows: `trained_at`, `games`, `rows`, `patches`, `features_version`, `features` (names, in order), accuracy / log loss / Brier per minute bucket for both models, per tier, the 10 calibration bins, and feature importance by gain.

**First run is the pilot** (~4,000 games), just to prove the pipeline works. Optionally also run the model code on the Kaggle "Diamond Ranked Games (10 min)" dataset (expect ~72% accuracy) to check the metric code against a known result.

**Done when** (on the full data):
- test accuracy at 10 minutes is about 70% or better,
- each calibration bin is within about ±3 points of the diagonal,
- LightGBM beats the LogisticRegression baseline on log loss.

## Step 11 — Full crawl and retraining

The crawler keeps running. Retrain (Step 9 upload, then Step 10) when a new patch has enough games, or weekly. Copy the new `model.txt` and `metrics.json` into `models/`; the app notices the new model version and recomputes reviews when they're opened.

## Step 12 — Pro games (optional, after Step 11 works)

Pro esports games aren't in the public Riot API. The only full-timeline source is the unofficial lolesports livestats feed (10 s frames: team gold, kills, towers, dragons, barons, inhibitors; player level and CS; no positions).
- A small separate extractor maps it to the same features with `tier = 10`.
- The feed is undocumented, changes often and can go down, so this step is skipped if it isn't usable. High-elo solo queue alone is enough to train a good model.

## Step 13 — Review backend (`review.py`, `api.py`, laptop)

**Endpoints** (types in `UI.md`, "Data the UI uses"):
- `GET /api/health` → key status (`ok` / `expired` / `missing`) and the model's kind and version.
- `GET /api/player/{platform}/{name}/{tag}?start=0&count=10` → puuid, rank, and ranked solo games (champion, result, KDA, CS, length, date, whether a review is cached).
- `GET /api/review/{match_id}?p={participantId}` → the review JSON from that player's side.
- `GET /api/model` → `metrics.json`, for the Model page.
- Errors are `{"error": {"code", "message", "retry_after_s"}}`; the codes and their messages are in `UI.md`.
- Listens on `127.0.0.1` only. Gzip on. CORS only for `localhost:5173`, in dev. The Riot key stays in the backend; it never reaches the browser.
- `app.py` serves the built UI (`frontend/dist`) from the same server, so daily use is one command. Any path that isn't `/api/…` or a file returns `index.html`, so the UI's own routes (`/review/…`) survive a reload.

**Riot calls from the laptop:** same key and limits as the crawler (Step 2). A first player lookup is about 12 Americas calls (account, match IDs, 10 match summaries) plus 1 NA1 rank call; a first review is 1 timeline call. Everything is cached, so opening it again costs nothing. A 429 is waited out once, then reported to the UI as `rate_limited`.

**Cache:** `cache.db` (SQLite) stores raw match + timeline JSON (kept; they never change), match summaries, each player's match list (refreshed on demand), and computed reviews keyed by `(match_id, participant_id, model_version)`, so a new model recomputes reviews automatically.

**Model (`model.py`):** loads `models/model.txt` and checks its feature list against `features.py`'s at startup, so a mismatch is an error rather than wrong numbers later. `model_version` is the start of the file's hash. With no model yet, a **placeholder** (a logistic formula on gold, kill and tower diffs with hand-set weights) lets the whole app run end to end; the UI labels it everywhere it's used.

**Champions:** each participant's numeric `championId` is mapped to its Data Dragon id and display name through `champion.json` (`key` → `id`, `name`) for the game's patch; the match's `championName` isn't used for images because it doesn't always match (Fiddlesticks). Data Dragon files are cached in `cache.db`.

**Tier:** the player's current solo rank (one league-v4 call). If they're unranked, the median rank of the other 9 players (9 calls, only then, cached); if nobody is ranked, Silver.

**Building a review:**
1. Fetch (or load) the match and timeline. Reject other queues (`unsupported_queue`) and remakes. `surrender` comes from the participants' `gameEndedInSurrender`.
2. Rows from `features.py` every 15 s, plus just before and just after each event.
3. Run the model. Flip to your team's side (1 − p if you're red). The last point is 100% or 0% at `GAME_END`.
4. **Group events into moments:** kills, objectives and buildings within 20 s of each other become one moment. Its value = win % after the group − win % before.
5. **Grades** (thresholds in `config.toml`):

   | Swing for your team | Grade | Name |
   |---|---|---|
   | +10% or more | `!!` | Great |
   | +5% to +10% | `!` | Good |
   | −5% to −10% | `?` | Mistake |
   | −10% or worse | `??` | Blunder |
   | under 5% either way | listed, no grade | |

6. **Titles** (`describe.py`), from templates:
   - one kill: "Ahri killed Zed", "Ahri + Vi killed Zed"; your deaths: "Died to Lee Sin + Darius",
   - fights (3+ kills): "Won fight 3 for 1", "Lost fight 1 for 4", "Ace",
   - objectives: "Took Infernal Dragon (3rd)", "Enemy took Baron",
   - buildings: "Destroyed mid outer tower", "Lost top inhibitor",
   - combined: "Won fight 3 for 0, then took Dragon",
   - plus where, from `map_data.py` zones: "mid lane", "top river", "enemy jungle (bot side)", "dragon pit", "near red mid outer tower".
   - `involves_me`: you got a kill or assist, died, or took the objective.
7. **Snapshots every 15 s**, for the scoreboard and minimap: each player's position (and how old it is), level, K/D/A, CS, gold, items and respawn timer; team totals; buildings down; kills in the last 10 s.
   - Items are rebuilt from item events: a purchase adds, a sale or destroy removes, an undo reverts. The trinket has its own slot.
   - Respawn time: the death-timer formula (level and game time; a table in `config.toml`). Stage 2 also uses it as a feature.
8. **Summary:** grade counts for you and for your team, and the biggest swing.

**`map_data.py`:** the map bounds (from Step 3), zone polygons in game coordinates (lanes, river halves, each jungle quadrant, dragon and baron pits, bases), and the fixed positions of towers, inhibitors and nexuses (and camps, for Stage 4). Checked with the minimap's `?debug=1` overlay.

**Tests (`test_review.py`, `test_api.py`, on the fixtures):**
- The review JSON validates against `schemas.py`.
- The curve ends at 0 or 1 to match the result.
- Every kill and objective in the match is in exactly one moment.
- Final K/D/A and items in the last snapshot match the match data (`item0`–`item6`).
- Asking for the same review twice makes no Riot calls the second time (mocked client).

**Done when:** reviewing one of your games takes under 3 s the first time and under 200 ms after, and the win % ends at 100% or 0% to match the result.

## Step 14 — Review frontend (`frontend/`)

Built as `UI.md` describes, in its build steps U1–U11. In short:
- Four pages: Search → Games → Review → Model. Dark slate theme in Barlow; blue means your team or good for you, red the enemy or bad for you, gold means you; everything else gray.
- The win chance graph is the one bold element, full width at the top of the review, like a broadcast gold-lead graph. Design checked against Anthropic's `frontend-design` skill (`UI.md`, "Design direction").
- **Review page:** a header with the grade summary, the win % graph with grade markers, a scrubber (← → step through moments), then the canvas minimap, the scoreboard and the moments list with inline detail side by side. Everything follows the selected time.
- Built against mock data first (MSW), then the real backend with the placeholder model, then the pilot and real models. No step waits for the crawl.
- Champion, item and map images come from Data Dragon, at the game's patch.
- Riot's legal line is in the footer.

**Done when:** you can search your Riot ID and review your last game end to end, also with the keyboard only, at 1440×900 without scrolling the page.

## Step 15 — End-to-end check

Review 5 of your own games. Check that:
- big swings line up with barons, aces and inhibitors,
- the graph ends at 0% or 100%,
- the moment descriptions match what happened,
- the scoreboard at 10:00 and 20:00 matches the replay's, and the minimap icons are where the replay shows them at minute marks.

Anything off becomes a fix to the features, the descriptions or the grade thresholds.

## Step 16 — Open replay button (`replay.py`)

- **You:** set `EnableReplayApi=1` under `[General]` in `game.cfg` (in the League install's `Config` folder).
- `GET /api/replay/status`: asks the client's local API (`https://127.0.0.1:2999`) whether a replay is open, and whether it's this game (its 10 champions match). The local API uses Riot's own certificate: verify it with Riot's published `riotgames.pem`, never by turning TLS checks off.
- `POST /api/replay/seek {t}` → `POST /replay/playback {"time": t − 5, "paused": false}`.
- Replays only exist for the current patch, so older games show the button disabled with that reason.
- UI: `UI.md`, "Open replay".

**Done when:** with a replay open, the button jumps it to 5 s before the selected time.

---

# Stage 2 — Windows

Goal: show **missed windows** (the enemy was weak, something was up, and your team took nothing), and make the model aware of these situations.

**Raw timelines aren't kept**, so new features only exist for games crawled after they're added. Each stage therefore bumps `FEATURES_VERSION`, the crawler writes the new version into the batch path, and training reads one version only. Thanks to the rolling window, the data is fully refreshed in about one patch. Add a stage's features to the crawler first, then build the rest of the stage while data piles up.

## Step 17 — Window features in `features.py` (`FEATURES_VERSION = 2`)

All built only from past events, so the no-future-leak test still applies.
- `alive_diff`: alive blue − alive red.
- Seconds until respawn per team and role, 0 if alive: `blue_top_dead_s` … `red_sup_dead_s` (10 columns), from the Step 13 formula.
- Each jungler's last known position and how long ago: `blue_jg_x`, `blue_jg_y`, `blue_jg_seen_s` (and red). Sources: minute positions, kills they were part of (the kill's position), and elite monsters they took.
- Objectives: for dragon, grubs, herald, baron (and atakhan if it exists): `*_up` (0/1) and `*_spawn_in_s`, from the `config.toml` timers (Step 3) and kill events. Elder takes the dragon's place after a soul.
- Vision: `wards_placed_diff_3m`, `wards_killed_diff_3m` (last 3 minutes).
- Positions (at minute frames, carried forward with their age): `in_enemy_jungle_diff` (players in the other team's jungle) and `grouped_diff` (largest group within 2,000 units).
- Monotone: +1 on `alive_diff` and `red_*_dead_s`, −1 on `blue_*_dead_s`; none on the rest.

**Done when:** the Step 4 tests still pass, and nobody dies while still marked dead on the fixtures (a too-long respawn timer would show up here).

## Step 18 — Retrain and compare

- Same split and seed as the Stage 1 model. The Stage 2 model must beat Stage 1 on test log loss, overall and in the 10–30 minute buckets, where windows matter.
- Drop features that don't help (importance, then removing one at a time).
- The Model page shows which features version the model uses.

## Step 19 — Window detection (`windows.py`)

- **A window opens** for your team when both are true:
  - the enemy is weak: their jungler is dead with 20 s or more to respawn, or 2 or more of them are dead;
  - something can be taken: an objective that's up (or spawns before they respawn), or a tower in a lane whose enemy laner is dead.
- **It closes** when the condition ends (the respawns).
- **Used** = your team took an objective, tower or plate during the window or within 10 s after it. Otherwise it's **missed**.
- **Value** of each option = model(state with that objective or tower credited to your team) − model(state). The best option is the window's value. Missed windows worth 3% or more are shown (threshold in `config.toml`).
- Review JSON: `windows: [{id, t_start, t_end, reason, options: [{what, value}], used, taken}]`.

## Step 20 — Windows in the review

- UI: `UI.md`, "Stage 2". Miss rows in the moments list, a Missed filter, and window bands on the graph.

**Done when:** on 5 of your games, every Miss holds up against the replay (the enemy really was down, the objective really was up), with no false alarms.

# Stage 3 — Best plays

## Step 21 — Label plays (`plays.py`, `FEATURES_VERSION = 3`)

For each window (and each key moment), what each team did in the next 60 s. The first rule that matches wins:

| Play | Rule |
|---|---|
| Objective (Dragon, Grubs, Herald, Baron, Atakhan) | its kill event |
| Tower / plates | a building or plate event |
| Gank top / mid / bot | a kill in that lane with the team's jungler involved |
| Invade | jungler in the enemy jungle at the next frame plus a jungle CS jump, or a kill in the enemy jungle |
| Recall | 2+ players buy items |
| Farm / nothing | none of the above |

## Step 22 — Train with the play

- Training rows at window starts, with the Stage 2 features plus `play` (categorical). The label is still `blue_won`. `play` describes the next 60 s on purpose, so it's the one column exempt from the no-leak test.
- At a review moment, swap in each play and predict; the value of a play = its prediction − the prediction for what your team actually did.
- **Seen:** how many training windows of the same kind (same reason, same 5-minute bucket) had each play. Plays seen fewer than 200 times are hidden by default.
- Check, per play: the model's effect against the raw win-rate gap in the data. A big difference means the model is guessing outside its data.
- Wording must be "teams that did X here won Y% more", never "the correct move" (selection bias: invades look better than they are, because vision isn't in the data).

## Step 23 — Best plays in the review

- Review JSON: `plays: [{play, delta, seen, is_actual}]` on moments and windows.
- UI: `UI.md`, "Stage 3".

**Done when:** on window rows, test log loss with `play` beats Stage 2, and on 5 of your games the top play reads as sensible to you.

# Stage 4 — Enemy camp estimates

## Step 24 — Estimate camps (`camps.py`, `FEATURES_VERSION = 4`)

- Camp positions in `map_data.py`; respawn timers and CS per camp in `config.toml` (checked like Step 3).
- Between two minute frames, the jungler's jungle-CS jump and the two positions say roughly which camps were taken: the CS is matched to camps near the path between the two positions.
- Each camp gets a chance of being up, which rises back to "up" as its respawn timer runs out.
- New feature: `enemy_camps_up` (expected count, top side and bot side), used by Stage 3's model for "Invade".

## Step 25 — Check against replays

On 3 of your replays, compare the estimate with the real camp state at 10 times each. Aim for 70% or better.

## Step 26 — Camps on the minimap

- Review JSON: `camps: [{id, team, p_up}]` in each snapshot.
- UI: `UI.md`, "Stage 4" (a Camps toggle on the minimap, and camp lines in window details).

**Done when:** Step 25 hits 70%, and the toggle shows the estimates.

# Stage 5 — Minimap computer vision (optional)

## Step 27 — Capture minimap frames (`cv/`)

- Play your game's replay in the client. The Replay API sets the speed (8×) and hides everything but the minimap (`/replay/render`); a script captures the minimap area (`mss`) at one frame per game second.
- Your own games on the current patch only, since replays expire with the patch.

## Step 28 — Train a detector (Kaggle GPU)

- **Training images:** Data Dragon champion icons (minimap size, with team rings) and camp icons pasted onto empty minimap captures, with random overlaps, fog and pings, so the labels are free. A few hundred real frames, checked by hand, for testing.
- **Model:** YOLO (`ultralytics`, nano size), trained on Kaggle's free GPU (~30 hours a week).
- **Running it:** on the laptop CPU, ~1,800 frames per 30-minute game takes a minute or two.

## Step 29 — Use the positions

- Per-second positions are saved per match in `cache.db`. The review uses them for the minimap and for the zones in titles; they're never used for training (own games only).
- UI: `UI.md`, "Stage 5".

**Done when:** at minute marks, the detected positions are within ~500 units of the timeline's 90% of the time.

---

## Where to see what

| What | Where | How to open |
|---|---|---|
| Crawl progress | Progress page on the VM | SSH tunnel → `http://localhost:8080` |
| Training while it runs | Kaggle notebook log | Kaggle website |
| Training results | Model page in the review app (+ `report.md`) | `http://localhost:8000/model` |
| Game reviews | Review app | `http://localhost:8000` (`5173` while building the UI) |

## Milestones

Each one works on its own:

| # | Steps | Result |
|---|---|---|
| M1 | 1–4 | Features extracted from real games, tested |
| M2 | 5–6 | Crawler + progress page working (short local test) |
| M3 | 7–10 | Crawler on the VM; pilot data trained on Kaggle |
| M4 | 11 | Full crawl running; real model + metrics |
| M5 | 13–15 | Review app working on your games (built from M1 on, see "Build order") |
| M6 | 16 | Open replay button |
| (opt) | 12 | Pro games added |
| M7 | 17–20 | Stage 2: missed windows |
| M8 | 21–23 | Stage 3: best plays |
| M9 | 24–26 | Stage 4: enemy camp estimates |
| (opt) M10 | 27–29 | Stage 5: positions from replays |

## Risks

| Risk | Handling |
|---|---|
| Repeated 429s can get the key disabled | One limiter per cluster with a safety margin; honor `Retry-After` |
| The laptop app and the crawler share one key's limits | The crawler leaves room on Americas and follows `X-App-Rate-Limit-Count`; the app caches everything |
| Dev key expires daily until the personal key is approved | Crawler pauses; progress page and app show a banner with the fix |
| New objectives or season changes | Step 3 checks real data before features are written |
| Patch drift | Rolling window of recent patches; retrain per patch |
| Data volume (~90k games/day) | Training rows per minute + per event; old patches deleted; uploads only when retraining |
| New features need data the crawl didn't keep (no raw timelines) | `FEATURES_VERSION` in batch paths; add each stage's features to the crawler first; the rolling window refills in about one patch |
| 1 GB RAM on the VM | Swap file first; pyarrow only; one process |
| High elo dominates the data while you're Gold | Per-tier cap per pass so Gold is reached in days; `tier` feature; Model page shows accuracy per tier |
| Better teams get early kills (skill confounding) | "Teams that did X won Y% more" wording |
| UI built before the real model shows made-up numbers | The placeholder model is labeled wherever it's used |
| Pro feed is unofficial | Optional step; skipped if unusable |
| The local Replay API is undocumented in places and can change | Optional button; disabled with a reason when it isn't reachable |
| Personal key = private use only | App stays private, on `127.0.0.1` |
| After the 90-day GCP trial, the VM's external IPv4 may cost ~$3.65/month (Google lists $0.005/h, with no free-tier exception) | Free during the trial; check Billing → Reports in the first week to see the real cost lines, then decide before the trial ends |

## Open questions

Each is answered by a step, not up front:
- Are Herald, Atakhan and Feats of Strength in 2026 timelines? (Step 3)
- Equal weight per game or per row? (Step 10, on the pilot)
- Do the default grade thresholds (5% and 10%) feel right on your games? (Step 15)
