# Training

`train.py` is one standalone file (pandas, numpy, pyarrow, lightgbm, scikit-learn, matplotlib).
It reads the crawler's Parquet folder (`<platform>/<patch>/v<N>/part-*.parquet`), splits by
`match_id` 70/10/20, trains a logistic-regression baseline and a monotone LightGBM model, and
writes `model.txt`, `metrics.json`, `calibration.png`, `accuracy_by_minute.png` and `report.md`
(plus `isotonic.json` with `--isotonic`, and `champions.json` on version 3).

It also trains one model per rank that has at least 1,000 training games and saves it to
`tiers/<RANK>/` only if it beats the overall model on that rank's test games; the report's "Rank
models" table shows the comparison for every rank. Copy the whole output, `tiers/` and
`champions.json` included, into `models/` (delete `models/tiers/` first): the app reviews a game
with its rank's model when there is one, else the overall model.

## Features versions

The crawler writes each version's rows to its own `v<N>` folder, and a run trains on one version.
By default that is the newest version with at least 10,000 games, else the one with the most
games, so a retrain right after a new version ships still uses the older, bigger set. The log
prints the games per version.

- **Version 1:** gold, kills, towers, levels, CS, objectives taken, buffs and souls.
- **Version 2** adds who is alive and for how long, when the Baron pit (grubs, Herald, Baron) and
  the Dragon pit (dragons, Elder) are next up, and where players stand at the last minute frame
  or event:
  - `baron_setup_diff`, `dragon_setup_diff`: players near the pit (3,000 units) while its monster
    is up or less than 90 s away, blue minus red.
  - `split_diff`: players alone in a side lane on the enemy's half of the map from 14:00 (no
    living teammate within 4,000 units), blue minus red.
  - `grouped_diff` (the biggest group within 2,000 units), `enemy_jungle_diff`, and wards placed
    and killed in the last 3 minutes (traps like Teemo's don't count; the timeline has no ward
    positions, so vision near a pit can't be told apart).

- **Version 3** adds each team's champions (`blue_champs`, `red_champs`: sorted names, read
  from the kill events since the crawler only downloads timelines). Training turns them into two
  columns with a per-champion table built on the training games only, saved as `champions.json`
  (the app uses it the same way):
  - `champ_wr_diff`: the sum of the team's champion win rates above 50%, blue minus red.
  - `scaling_diff`: the sum of how much each champion's win rate rises per minute of game length
    (a least-squares slope; Bel'Veth or Aurelion Sol should be positive), blue minus red. The
    model combines it with the minute and the gold, so a lead means less against a team that
    outscales.
  - Both are shrunk toward 50% and 0 by games / (games + 600), so a rarely played champion doesn't
    get extreme numbers from luck. Each training game gets its numbers from the other 4 folds'
    games (out of fold), so its own result never feeds its own features.
  - The two columns are kept only if they lower the validation log loss against the same model
    without them; the report says which.

A version 2 or 3 run also trains the same LightGBM on each older version's columns, on the same
games, and the report shows them side by side:
- **Features version N against older versions:** log loss overall, by minute and in situations
  like "Baron pit up, one team has more players near it" or "a team is split pushing". If the
  newest version isn't lower, its new features don't help yet.
- **Champions** (version 3): the champions whose win rate rises and falls most with game length.
- **What the newer features are worth:** for each position, vision or champion feature, how much
  it moves the win chance on the test rows where it isn't 0, for the team with more of it. It is
  what the model learned, not proof of cause: teams that are ahead are also the ones that can
  stand at Baron.

## LightGBM settings

Each run tries the settings in `PARAM_GRID` with early stopping and keeps the one with the lowest
validation log loss (the first is the original: 31 leaves, 20 rows per leaf). A game's rows share
one label, so larger leaves keep the model from learning a few games by heart, and the
"intermediate" monotone method is less strict than "basic" while staying monotone. The rank models
and the older-version comparison use the kept setting. The report lists every setting tried;
`--no-tune` uses only the first.

## On Kaggle, through the API

`kernel-metadata.json` makes this folder a private Kaggle script (`augustzhang1/lol-winprob-train`)
attached to the `augustzhang1/lol-winprob` dataset. With `KAGGLE_API_TOKEN` set:

```
kaggle kernels push -p training                                  # uploads train.py and runs it
kaggle kernels status augustzhang1/lol-winprob-train             # until COMPLETE
kaggle kernels output augustzhang1/lol-winprob-train -p out       # then copy model.txt, metrics.json to models/
```

## On Kaggle, by hand

1. Upload the crawler's data as a Kaggle dataset and create a notebook attached to it.
2. Put `train.py` in the notebook (or attach it as a script) and run it with no arguments:
   it uses the first folder under `/kaggle/input/` and writes to `/kaggle/working`.
   For options, use `!python train.py --patches 16.18,16.19 --weight game --isotonic`.
3. Click **Save & Run All**. The log updates live.
4. When it finishes, download `model.txt` and `metrics.json` from the Output tab into `models/`.

## Locally, on synthetic data

```
python training/make_synthetic_dataset.py --out /tmp/synth --games 3000 [--version 1]
python training/train.py --data /tmp/synth --out /tmp/synth_out --patches 26.18,26.19
```

## Options

| Flag | Meaning |
|---|---|
| `--data DIR` / `--out DIR` | input Parquet folder (searched recursively) / output folder |
| `--patches 16.18,16.19` | patch window (default: all patches found) |
| `--features-version N` | which `v<N>` folder (or `features_version` column) to use; default: see "Features versions" |
| `--weight none\|game` | `game` weights each row by 1 / rows in its game; compare the printed validation log loss |
| `--isotonic` | calibrate on the validation set; used for the test metrics |
| `--no-tune` | only the first LightGBM setting (faster) |
| `--seed 42` | split and model seed |
| `--max-rows N` | keep whole games until about N rows (quick runs) |
| `--tiers CHALLENGER` | only these ranks' games (default: all) |
| `--old-version 1` | also train on version 1's games (same ranks, without this run's validation and test games, since a re-crawled game is in both) and compare that model with the new one on the test games: the report's "Old model against the new one" |

The maximum calibration gap ignores bins with fewer than 20 rows.

## Dataset report and drift evaluation

`scripts/dataset_report.py --data data` prints the games and rows by platform, patch, rank and
features version, the Parquet size on disk, games stored in more than one file, and each
platform's crawl state (`state-<platform>.sqlite`, read-only, if present).

`scripts/drift_eval.py --data data [--max-rows N] [--out drift.json]` scores the model on games it
wasn't trained on, using the first LightGBM setting and the version's columns without the champion
columns. Unseen patch: train on the older patches, test on held-out older games and on the newest
patch. Unseen rank: train on Master to Challenger, test on held-out games from those ranks and on
Diamond. A group with under 200 games is skipped. Both scripts read only the
`<platform>/<patch>/v<N>` layout, so the copies under `data/kaggle_*` are left out.
