# TODO

## Step 1: accounts and keys (you, ~30 min)

Keep every key out of the repo and out of chat.

### Riot
- [x] **Do now:** register a **personal API key**: "Register Product" → Personal API Key. Description: private research project, post-game win-probability analysis of my own games, no public users. Approval takes a while, so start it early.
- [x] Personal API key approved and in `.env` on the laptop and the VM (2026-10-02). It doesn't expire.

### Google Cloud
- [x] Create an account at https://cloud.google.com (card required). You're on the free trial: $300 for 90 days.
- [x] Create a project, e.g. `lol-crawler`.
- [x] ~~$1 budget alert~~: skipped. Nothing can be charged on the free trial; set one if you ever upgrade.
- [x] ☰ menu → Compute Engine → VM instances → click **Enable** (turns on the Compute Engine API). This is the only API to turn on. No API key or credentials are needed from Google Cloud.
- [x] Install the gcloud CLI (installed: Google Cloud SDK 587.0.0).
- [x] `gcloud init`: logged in; project `web-crawler-510403`, zone `us-central1-a`.
- [x] VM `lol-crawler` created in Step 7.
- [ ] Skip the **Gemini API key**: it's for Google's Gemini AI and this project doesn't use it.
- [x] Trial end date: **2026-12-30** (90 days from 2026-10-01). Before then, decide whether to upgrade to a paid account, which is needed to keep the VM running after the trial.

### Kaggle
- [x] Create an account at https://www.kaggle.com.
- [x] Settings → **verify your phone number** (needed for private datasets and notebook internet).
- [x] Settings → API → **revoke the token that was pasted in chat**, then **Generate New Token** (format `KGAT_…`).
- [x] Paste the new token after `KAGGLE_API_TOKEN=` in `.env`.

## After Step 1

- [x] ~~Tell Claude it's done.~~ The Stage 1 code is written (Steps 2, 4–7, 9, 10, 13, 14, 16), and tested on made-up games, since there's no key here yet.

## Now

### Try the app without a key
- [x] Set up on the laptop (2026-10-02): `.venv`, `frontend/dist` and Playwright's Chromium are installed; all tests pass on Windows. On Windows the Python is `.venv\Scripts\python`. The commands, for reference:
  ```
  uv venv -p 3.12 .venv && uv pip install -p .venv -e ".[dev]"
  cd frontend && npm ci && npm run build && cd ..
  .venv/bin/python -m lolreview.app --demo
  ```
  Open `http://127.0.0.1:8000` and search `Me#NA1`. These are made-up games and a placeholder model, so the numbers mean nothing yet.

### Step 3: check real data
- [x] Done 2026-10-02: 3 real games in `tests/fixtures/real/`, `config.toml` timers checked against 100 games, role quests handled. Findings are under Step 3 in `Plan.md`.

### Replay button certificate (Step 16)
- [x] `lolreview/certs/riotgames.pem` downloaded.

### Leftover in the cloud sandbox
- [ ] Optional: a coding agent left 504 KB of made-up test data at `/s` in the cloud container (not in the repo). `rm -rf /s` clears it; it goes away with the container anyway.

## Later steps that need you

Claude does the rest (see `Plan.md` for every step, `UI.md` for the app).

### Laptop setup (before Step 13)
- [x] Install Python 3.12 and Node.js 20 or newer (LTS): uv supplies Python 3.12; Node is 24.
- [x] `.env` with the personal key on the laptop and the VM.

### Step 7: the VM
- [x] Done 2026-10-02: `lol-crawler` (e2-micro, us-central1-a) runs the crawler as a service and survives reboots. It clones the repo with a read-only deploy key. See the progress page with `gcloud compute ssh lol-crawler --zone us-central1-a --ssh-flag="-N" --ssh-flag="-L 8080:localhost:8080"`, then <http://localhost:8080>.

### Steps 9–10: training
- [x] Pilot done 2026-10-02 (Steps 8-10): 2,936 Challenger games uploaded to the private dataset `augustzhang1/lol-winprob`, trained by the private Kaggle script `augustzhang1/lol-winprob-train` through the API (no clicking needed), and the model is in `models/`: 76% accuracy, calibration within 6 points. Retrain the same way once the crawl reaches the lower tiers (Step 11).

### Step 15: check the reviews
- [ ] Review 5 of your own games. Write down anything that looks wrong (the time and what you expected).

### Step 16: replay button
- [ ] In the League install's `Config/game.cfg`, add `EnableReplayApi=1` under `[General]`.

### Stages 2–5
- [ ] Steps 20, 23 and 25: check the windows, best plays and camp estimates against your replays.
- [ ] Stage 5 (optional): play replays of your games so their minimaps can be captured.
