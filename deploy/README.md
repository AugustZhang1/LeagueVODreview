# Deploy the crawler to the VM

Run these on your laptop unless a step says "on the VM". The repo is private, so the first run of
`setup_vm.sh` prints a deploy key to add under the repo's Settings -> Deploy keys (read-only);
then run it again.

## 1. Create the VM

```
gcloud compute instances create lol-crawler \
  --zone us-central1-a \
  --machine-type e2-micro \
  --image-family debian-12 --image-project debian-cloud \
  --boot-disk-size 30GB --boot-disk-type pd-standard
```

The region matters: only `us-west1`, `us-central1` and `us-east1` have a free `e2-micro`. No
firewall rules are added, so only SSH (port 22) is reachable.

## 2. Copy the files and run the script

```
gcloud compute scp deploy/setup_vm.sh .env lol-crawler:~ --zone us-central1-a
gcloud compute ssh lol-crawler --zone us-central1-a --command "bash setup_vm.sh"
```

The script adds a 2 GB swap file, installs Python and git, clones the repo to
`~/LeagueVODreview`, builds the venv, moves `.env` into the repo (mode 600) and starts the
`lolcrawler` service. It is safe to run again; it pulls the latest code and restarts the service.

## 3. Check it

On the VM (`gcloud compute ssh lol-crawler --zone us-central1-a`):

```
systemctl status lolcrawler
journalctl -u lolcrawler -f
```

## 4. Open the progress page

The page listens on `127.0.0.1:8080` on the VM only. Tunnel it:

```
gcloud compute ssh lol-crawler --zone us-central1-a --ssh-flag="-N" --ssh-flag="-L 8080:localhost:8080"
```

Then open <http://localhost:8080> while it runs (Ctrl+C ends it). Use `--ssh-flag` and
`--command` rather than `-- ...`: PowerShell drops the `--`.

## 5. Update the dev key

The dev key expires daily. From the laptop:

```
gcloud compute ssh lol-crawler --zone us-central1-a --command "sed -i 's/^RIOT_API_KEY=.*/RIOT_API_KEY=NEW_KEY/' ~/LeagueVODreview/.env"
```

The crawler picks it up within a minute. Update the laptop's `.env` too.

## 6. Upload to Kaggle

On the VM, when you want to train:

```
cd ~/LeagueVODreview
.venv/bin/python -m lolreview.upload --dataset-id YOUR_KAGGLE_NAME/lol-winprob --dry-run
.venv/bin/python -m lolreview.upload --dataset-id YOUR_KAGGLE_NAME/lol-winprob
```

`--dry-run` only prints what would be uploaded. The first real run creates the private dataset;
later runs add a new version. It uploads the last 3 patches and writes `data/last_upload.json`
for the progress page. `KAGGLE_API_TOKEN` must be in the VM's `.env`.

Each upload counts against the VM's free 1 GB/month of outbound traffic. Upload when you are about
to retrain, not on a timer; going over costs a few cents.
