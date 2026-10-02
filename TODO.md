# TODO

## Step 1: accounts and keys (you, ~30 min)

Keep every key out of the repo and out of chat.

### Riot
- [x] **Do now:** register a **personal API key**: "Register Product" → Personal API Key. Description: private research project, post-game win-probability analysis of my own games, no public users. Approval takes a while, so start it early.
- [ ] **Later**, when Claude reaches Step 3: log in at https://developer.riotgames.com, regenerate the **dev key** (it expires 24 h after it's generated), and paste it after `RIOT_API_KEY=` in `.env`.

### Google Cloud
- [x] Create an account at https://cloud.google.com (card required). You're on the free trial: $300 for 90 days.
- [x] Create a project, e.g. `lol-crawler`.
- [x] ~~$1 budget alert~~: skipped. Nothing can be charged on the free trial; set one if you ever upgrade.
- [x] ☰ menu → Compute Engine → VM instances → click **Enable** (turns on the Compute Engine API). This is the only API to turn on. No API key or credentials are needed from Google Cloud.
- [x] Install the gcloud CLI (installed: Google Cloud SDK 587.0.0).
- [x] `gcloud init`: logged in; project `web-crawler-510403`, zone `us-central1-a`.
- [ ] Don't create the VM yet; that's Step 7.
- [ ] Skip the **Gemini API key**: it's for Google's Gemini AI and this project doesn't use it.
- [ ] Note the trial end date (Billing → Overview). Before then, decide whether to upgrade to a paid account, which is needed to keep the VM running after the trial.

### Kaggle
- [x] Create an account at https://www.kaggle.com.
- [x] Settings → **verify your phone number** (needed for private datasets and notebook internet).
- [x] Settings → API → **revoke the token that was pasted in chat**, then **Generate New Token** (format `KGAT_…`).
- [x] Paste the new token after `KAGGLE_API_TOKEN=` in `.env`.

## After Step 1

- [ ] Tell Claude it's done. Next up: Steps 2–4 (Riot client, checking real data, feature extraction).

## Later steps that need you

Claude does the rest (see `Plan.md` for every step, `UI.md` for the app).

### Laptop setup (before Step 13)
- [ ] Install Python 3.12 and Node.js 20 or newer (LTS).
- [ ] Put a `.env` with the Riot key in the repo folder on the laptop too. Until the personal key arrives, a new dev key goes in **both** places (laptop and VM).

### Step 7: the VM
- [ ] Run the `gcloud compute instances create …` command Claude gives you (it runs in your Google account), then the setup script over SSH.

### Steps 9–10: training
- [ ] Run `upload.py` over SSH when Claude asks.
- [ ] On kaggle.com, open the notebook → **Save & Run All**. When it's done, download `model.txt` and `metrics.json` from the Output tab into `models/` on the laptop.

### Step 15: check the reviews
- [ ] Review 5 of your own games. Write down anything that looks wrong (the time and what you expected).

### Step 16: replay button
- [ ] In the League install's `Config/game.cfg`, add `EnableReplayApi=1` under `[General]`.

### Stages 2–5
- [ ] Steps 20, 23 and 25: check the windows, best plays and camp estimates against your replays.
- [ ] Stage 5 (optional): play replays of your games so their minimaps can be captured.
