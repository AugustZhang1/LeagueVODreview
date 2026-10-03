# Handoff (2026-10-03)

## Where things stand

- **Stage 1 code** is done and merged to `main`; 373 Python, 103 frontend and 25 end-to-end tests pass.
- **Step 3** (real data) is done. Findings, including the 2026 role quests, are under Step 3 in `Plan.md`.
- **Crawler** runs 24/7 on the Google Cloud VM `lol-crawler` (e2-micro, `us-central1-a`) with the personal Riot key.
  - It covers NA, EUW, KR and VN (one per regional rate limit) and goes top down from Challenger, 20,000 games per tier per region.
  - It spends one request per game when the patch is known from the game id. Measured: about 2,700 games/hour each for EUW, KR and VN and about 2,150 for NA (NA keeps 15 requests per 2 min free for the review app). That is the rate limit's ceiling, up from about 1,100.
  - A stop waits up to 150 s so every region saves its games (it used to give up after 30 s and NA, often waiting on the limiter, lost up to 500 games per restart).
- **Model:** `models/` has the 2026-10-02 model: 34,580 games (almost all Challenger), 75.5% accuracy, calibration within 2 points, plus a Challenger rank model.
  - After `datasets version`, wait a few minutes before `kernels push`: a run started right away read the previous dataset version.
  - Training builds a model per rank and keeps one only if it beats the overall model on that rank.
  - Retraining isn't automatic yet.
- **Features version 2** (Step 17, branch `claude/gallant-johnson-aatony`, not on the VM yet; 399 Python tests pass) adds who is dead and for how long, the Baron and Dragon pit timers, players setting up near a pit before its monster is up, split pushers, grouping, enemy-jungle presence and recent wards. Details in `training/README.md` and under Step 17 in `Plan.md`.
  - Old rows can't be rebuilt (raw timelines aren't kept), so only games crawled after the deploy have them. They go to `v2` folders next to the `v1` ones.
  - Training uses version 2 once it has 10,000 games, and its report then compares it with version 1's features on the same games, overall and around Baron setups, Dragon setups and split pushes.
  - Training now also tries 4 LightGBM settings and keeps the best on validation, so a run takes a few times longer.
  - The current model keeps working in the app: it reads only the columns it was trained on.
- Free GCP trial ends **2026-12-30**. After that the VM's IP costs about $3.65/month on a paid account.

## Commands (PowerShell, from the repo folder)

Review app (stops when the terminal closes):
```
.venv\Scripts\python -m lolreview.app
```
Then open http://127.0.0.1:8000.

Crawler progress page (Ctrl+C to close):
```
gcloud compute ssh lol-crawler --zone us-central1-a --ssh-flag="-N" --ssh-flag="-L 8080:localhost:8080"
```
Then open http://localhost:8080.

Retrain:
```
gcloud compute ssh lol-crawler --zone us-central1-a --command "cd LeagueVODreview && .venv/bin/python -m lolreview.upload"
$env:KAGGLE_API_TOKEN = ((Get-Content .env) -match '^KAGGLE_API_TOKEN=' -replace '^KAGGLE_API_TOKEN=', '')
.venv\Scripts\kaggle.exe kernels push -p training
.venv\Scripts\kaggle.exe kernels status augustzhang1/lol-winprob-train   # repeat until COMPLETE
.venv\Scripts\kaggle.exe kernels output augustzhang1/lol-winprob-train -p out
```
Then copy `out\model.txt`, `out\metrics.json` and `out\tiers\` (if any) into `models\`. The running app picks them up on its own.

Deploy code changes to the VM:
```
gcloud compute ssh lol-crawler --zone us-central1-a --command "cd LeagueVODreview && git pull --ff-only && sudo systemctl restart lolcrawler"
```

## Next

1. Merge `claude/gallant-johnson-aatony` into `main`, then deploy it to the VM (command above) so new games get version 2 features.
2. After 3-4 hours (about 35,000 version 2 games, as many as the current model has, at about 10,000 games/hour across the four regions), retrain. In `out\report.md`, read "Features version 2 against version 1" and "What positions and vision are worth": they answer whether setups before Baron and Dragon and split pushing change the prediction. Copy the model in if version 2 has the lower log loss in that table. Don't compare it with the current model's numbers: those are on other games, mostly Challenger.
3. With the version 2 model, check the grades on a few games: a kill now also counts the dead player's respawn time, so fight swings may get bigger and the 5% / 10% thresholds may need a change.
4. Retrain once the crawler has reached lower tiers (Diamond and below), so lower ranks get their own models.
5. Optional: automate retraining (weekly upload + Kaggle run from the VM, and the app fetching the newest model).
6. You: review a few of your own games and note anything that looks wrong (Step 15).

## Gotchas

- Rate limit: 100 requests / 2 min per region. Using several keys to get around it breaks Riot's policy.
- In PowerShell, `gcloud ... -- args` loses the `--`; use `--command` / `--ssh-flag`. `gcloud compute scp` on Windows wants `lol-crawler:.`, not `~`.
- Shell scripts and the systemd unit must stay LF (`.gitattributes` enforces it).
- Real patches are `16.x`; the synthetic test data uses `26.x`.
