# Handoff (2026-10-02)

## Where things stand

- **Stage 1 code** is done and merged to `main`; 373 Python, 103 frontend and 25 end-to-end tests pass.
- **Step 3** (real data) is done. Findings, including the 2026 role quests, are under Step 3 in `Plan.md`.
- **Crawler** runs 24/7 on the Google Cloud VM `lol-crawler` (e2-micro, `us-central1-a`) with the personal Riot key.
  - It covers NA, EUW, KR and VN (one per regional rate limit) and goes top down from Challenger, 20,000 games per tier per region.
  - It spends one request per game when the patch is known from the game id (deployed today; speed not measured yet).
- **Model:** a pilot model is in `models/`: 2,936 Challenger games, 76% accuracy.
  - Training builds a model per rank and keeps one only if it beats the overall model on that rank.
  - Retraining isn't automatic yet.
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

1. Measure the crawler's speed with the new one-request path: games per hour on the progress page, about 1,100 per region before.
2. Retrain on the larger data set; check the report's "Rank models" table.
3. Optional: automate retraining (weekly upload + Kaggle run from the VM, and the app fetching the newest model).
4. You: review a few of your own games and note anything that looks wrong (Step 15).

## Gotchas

- Rate limit: 100 requests / 2 min per region. Using several keys to get around it breaks Riot's policy.
- In PowerShell, `gcloud ... -- args` loses the `--`; use `--command` / `--ssh-flag`. `gcloud compute scp` on Windows wants `lol-crawler:.`, not `~`.
- Shell scripts and the systemd unit must stay LF (`.gitattributes` enforces it).
- Real patches are `16.x`; the synthetic test data uses `26.x`.
