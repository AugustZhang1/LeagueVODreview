# LeagueVODreview — Overview

A post-game "Game Review" for League of Legends, modeled on chess.com's game review. Enter a Riot ID, pick a match, and see how each moment moved your team's chance of winning.

**Post-game only.** Riot's third-party policy forbids software that interferes between pressing "Play" and the end-of-game screen, so there is no live advice.

## What the review shows

- A win % graph over the whole game
- A timeline scrubber with the minimap and scoreboard at any moment
- Key moments labeled ?? / ? / ! / !! by how much they moved win %
- "Missed windows" (e.g. the enemy jungler died and we took nothing)
- Ranked "best plays" at key moments

```
┌─ Game Review · Ahri mid · Victory · 31:42 ─────────────────────┐
│ Win % graph over time, with ?? and !! markers                   │
│ ◀ ━━━━━━━━━━━━━━━━━━━●━━━━━━━━━━━━━━━━━ ▶  22:10 [Open replay]  │
├──────── Minimap @ 22:10 ──────┬──── Scoreboard @ 22:10 ─────────┤
├──────── Key moments ──────────┴─────────────────────────────────┤
│ ??  14:32  Died to Lee Sin + Darius gank top side   -11% Blunder│
│ !!  22:10  Won 4v5 fight at mid tower               +18% Great  │
├──────── Best plays at 12:40 ────────────────────────────────────┤
│ Enemy Lee Sin died bot side (respawn 0:31), topside camps empty │
│ 1. Take Dragon +7% (seen 4,120) · 2. Invade +4% (610)           │
│ –  Recall (what you did) 0%                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Why build it

Existing free tools (iTero, Replays.lol, MetaBot, Mobalytics, Blitz, OP.GG) give post-game stats, recordings and AI coaching, but none of them grade moments in your own solo-queue games by how much they swung win %. Riot's own Win Probability graph (built with AWS) exists only on pro esports broadcasts.

## Core idea

1. Train a win-probability model on as many recent games as possible, starting at the top and moving down: pro games (later, see below), then Challenger, Grandmaster, Master, Diamond and lower, across Americas, Europe and Asia. A `tier` feature lets one model learn how each tier converts leads; a review uses the reviewed player's tier. Only recent patches are kept, because the meta changes.
2. Score my game by running the model at each moment to get win %. The change from just before to just after an event is that event's value.

## Data: Riot API

**Key.** Use a personal API key (register the project on the developer portal). It has the same limits as the dev key (20 requests/1s, 100 requests/2min) but doesn't expire every 24h. It is for personal use only; a public site would need a production key, which takes months to approve.

**Crawl.** league-v4 players by tier → match-v5 match IDs by puuid (ranked solo, queue 420) → match + timeline (~2 calls per game). Challenger, Grandmaster and Master have their own league-v4 endpoints; Diamond and below use the paged `entries` endpoint. De-duplicate match IDs, since each game has 10 players. Match data has no rank, so each game is tagged with the tier of the player it was found through.

**Throughput.** About 1,000–1,400 games per hour per regional cluster (Americas, Europe, Asia each have their own rate limit), so ~90k games a day with all three running. The crawler runs continuously and keeps a rolling window of the last ~3 patches. It works top-down in passes, taking up to 20k games per tier per pass, so it reaches Gold (my tier, Gold III NA) within a few days of each patch instead of getting stuck in Diamond. The bottom tier is Silver.

**Pro games** are not in the public Riot API. The only full-timeline source is the unofficial lolesports livestats feed (10 s frames, no positions), which is undocumented and can break. They are added as a separate step once solo queue works, and skipped if the feed is unusable.

**What the timeline has:**
- Per-minute participantFrames: gold, XP, level, CS, jungle CS, position
- Events, with ms timestamps:
  - CHAMPION_KILL (killer, victim, assists, position)
  - ELITE_MONSTER_KILL (with position)
  - BUILDING_KILL, TURRET_PLATE_DESTROYED
  - ITEM_PURCHASED / SOLD / UNDO (a purchase also means that player recalled)
  - WARD_PLACED / WARD_KILL (no position)
- Match data includes each player's role (teamPosition).

**Not available:** summoner spell cooldowns, ward locations, individual jungle camp kills, positions between minutes.

**Storage.** Save only extracted features to Parquet, not raw timeline JSON (roughly 0.5–1 MB per game). The data stays on the VM and in Kaggle, never in the repo (gitignored).

**Kaggle quick check.** The "League of Legends Diamond Ranked Games (10 min)" dataset can validate the training script and the ~70% accuracy at 10 minutes. It is a single snapshot per game, not a timeline, so it can't validate win % over time. No public full-timeline solo-queue dataset exists, so the crawler is required.

**Replay API.** Set `EnableReplayApi=1` in game.cfg; the `/replay/playback` endpoint can jump the in-client replay to a timestamp, for an "Open replay at this moment" button. Replays only work on the current patch.

## Model

- Training rows: one per minute plus one right after each event. (A review still scores every 15 s, since features are rebuilt from the timeline.)
- Between minute frames, carry the last frame's gold and CS forward and add kill bounties at the moment they happen. Don't interpolate: that uses the next frame, which leaks the future into training.
- Label: `blue_won`. Features are diffs (blue minus red), except dragon counts. From red's side, win % = 1 − p.
- Model: LightGBM classifier, with LogisticRegression as a baseline.
- Split train/test by `match_id` (GroupShuffleSplit), never by row, or the answer leaks.
- Metrics: accuracy by minute (expect ~70% at 10 min, rising later), log loss, and a calibration curve. Calibration matters most.
- Only use features that can be rebuilt the same way at scoring time.

## Compute

- **Crawler: Google Cloud free `e2-micro` VM**, so the laptop doesn't stay on overnight. It must be in `us-west1`, `us-central1` or `us-east1` to stay free (1 GB RAM). Crawling is limited by the rate limit, not the CPU (~1–3% of a core per region). It runs in the background, writes one Parquet file per ~500 games so a crash only loses the current batch, and resumes from the match IDs already saved. It also serves a small progress page, viewed through an SSH tunnel. Only ~1 GB/month of outbound traffic is free, so data is uploaded to Kaggle only when retraining (worst case a few cents over).
- **Training: Kaggle notebook (free, no card).** The VM uploads its Parquet folder straight to a private Kaggle dataset with the Kaggle CLI. Training runs from the Kaggle website (Save & Run All) on a CPU notebook (~30 GB RAM), and `model.txt` + `metrics.json` are downloaded from the Output tab. Nothing trains on the laptop, not even the pilot. The VM is too small to train on.
- **Laptop:** only the review app, which uses about as much as a browser tab.
- **GPU:** only Stage 5 needs one, via Kaggle Notebooks (~30 free GPU hours a week).

## Stages

Each stage works on its own.

1. **Win model + basic review.**
   Features: tier, minute, gold_diff, kill_diff, tower_diff, inhibs_down_diff, baron_active, elder_active, grub_diff, blue_dragons, red_dragons, soul_diff, soul_type, level_diff, cs_diff.
   - Dragons are counted per team, not as a diff: 4–3 and 1–0 are both +1, but 4–3 means blue has soul.
   - `soul_type` (Infernal, Mountain, Ocean, Cloud, Hextech, Chemtech) is the 3rd dragon's type, since the map transforms after the 2nd. LightGBM treats it as a category, so each soul learns its own effect on win %. `soul_diff` is +1 if blue has soul, −1 if red, 0 if nobody.
   - Baron, Elder and inhibitors are "right now" states (buff active, inhibitor currently down), not running totals, because buffs expire and inhibitors respawn.
   - `tier`: Iron = 0 … Challenger = 9, Pro = 10.
   Later additions: item value.
2. **Windows.**
   - Alive count per team
   - Which roles are dead and seconds until respawn (formula from level + game time)
   - Enemy jungler's last known location (from kill/objective event positions) and how long ago
   - Whether each objective is up, or its spawn timer
   - Wards placed / killed per team in the last 2–3 min
   - Position-snapshot features (players in the enemy jungle, players grouped)
3. **Best plays.**
   - Label the play taken in each window: objective, tower/plates, gank top/mid/bot (kill involving the jungler in that lane), invade (jungler in enemy jungle + CS jump, or a kill there), recall (item purchase), farm/nothing.
   - Train with the play as a feature.
   - At each key moment, score every play swapped in, rank them, and show how many times each was seen in the data.
   - Wording must be "teams that did X here won Y% more", not "the correct move". Selection bias: invades look better than they are because vision isn't in the data.
4. **Enemy camp estimates.** Use jungle-CS jumps, position snapshots and fixed camp respawn timers to estimate which enemy camps are up, and whether their jungle is invadable.
5. **Optional: replay minimap computer vision.** Detect champion and camp icons on the minimap with YOLO (like the DeepLeague project) to get per-second positions. Own games only, so use it for explanations, not training.

## App

- **Backend:** FastAPI. Fetches and caches matches, builds features, runs the model, returns the review as one JSON.
- **Frontend:** React.
  - Recharts win % graph
  - Timeline scrubber
  - Canvas minimap using the Data Dragon map image
  - Scoreboard at the selected time
  - Key moments list, missed windows, best plays

## Dropped

- **Live in-game win % page** (Live Client Data API). Even a passive win % during the game is too close to Riot's in-game rule.

## First task: Stage 1 only

1. A Python project with a rate-limited Riot API crawler.
2. Feature extraction to Parquet.
3. A training script that prints accuracy by minute, log loss and calibration.

Optionally validate the training script on the Kaggle dataset first.
