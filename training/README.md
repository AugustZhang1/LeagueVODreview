# Training

`train.py` is one standalone file (pandas, numpy, pyarrow, lightgbm, scikit-learn, matplotlib).
It reads the crawler's Parquet folder (`<platform>/<patch>/v<N>/part-*.parquet`), splits by
`match_id` 70/10/20, trains a logistic-regression baseline and a monotone LightGBM model, and
writes `model.txt`, `metrics.json`, `calibration.png`, `accuracy_by_minute.png` and `report.md`
(plus `isotonic.json` with `--isotonic`).

It also trains one model per rank that has at least 1,000 training games and saves it to
`tiers/<RANK>/` only if it beats the overall model on that rank's test games; the report's "Rank
models" table shows the comparison for every rank. Copy the whole output, `tiers/` included, into
`models/`: the app reviews a game with its rank's model when there is one, else the overall model.

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
python training/make_synthetic_dataset.py --out /tmp/synth --games 3000
python training/train.py --data /tmp/synth --out /tmp/synth_out --patches 26.18,26.19
```

## Options

| Flag | Meaning |
|---|---|
| `--data DIR` / `--out DIR` | input Parquet folder (searched recursively) / output folder |
| `--patches 16.18,16.19` | patch window (default: all patches found) |
| `--features-version 1` | which `v<N>` folder (or `features_version` column) to use |
| `--weight none\|game` | `game` weights each row by 1 / rows in its game; compare the printed validation log loss |
| `--isotonic` | calibrate on the validation set; used for the test metrics |
| `--seed 42` | split and model seed |
| `--max-rows N` | keep whole games until about N rows (quick runs) |

The maximum calibration gap ignores bins with fewer than 20 rows.
