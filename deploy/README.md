# Deploy the crawler to the VM

Run these on your laptop unless a step says "on the VM". To deploy your own fork, set `REPO_URL`
when running `setup_vm.sh` (it defaults to this repo).

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
gcloud compute scp deploy/setup_vm.sh .env lol-crawler:. --zone us-central1-a
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
.venv/bin/python -m lolreview.upload --dry-run
.venv/bin/python -m lolreview.upload
```

`--dry-run` only prints what would be uploaded. The first real run creates the private dataset;
later runs add a new version. It uploads the last 3 patches and writes `data/last_upload.json`
for the progress page. `KAGGLE_API_TOKEN` must be in the VM's `.env`.

Each upload counts against the VM's free 1 GB/month of outbound traffic. Upload when you are about
to retrain, not on a timer; going over costs a few cents.

## 7. Host the review app

The app runs next to the crawler, on `127.0.0.1:8000`, with Caddy in front for HTTPS. The address
is the VM's external IP with dashes plus `.sslip.io` (now `https://35-255-204-93.sslip.io`), a free
hostname, so no domain is needed. It changes if the VM is stopped and started (a reboot keeps it).

```
gcloud compute scp models/model.txt models/metrics.json models/champions.json lol-crawler:LeagueVODreview/models/ --zone us-central1-a
gcloud compute scp deploy/lolreview-app.service deploy/Caddyfile lol-crawler:. --zone us-central1-a
gcloud compute firewall-rules create allow-lolreview-https --allow tcp:80,tcp:443 --target-tags lolreview-https
gcloud compute instances add-tags lol-crawler --zone us-central1-a --tags lolreview-https
```

On the VM:

```
cd ~/LeagueVODreview && ~/.local/bin/uv pip install -p .venv -e ".[vm,app]"
sed -e "s|@USER@|$USER|g" -e "s|@REPO@|$HOME/LeagueVODreview|g" ~/lolreview-app.service | sudo tee /etc/systemd/system/lolreview-app.service
sudo systemctl daemon-reload && sudo systemctl enable --now lolreview-app
sudo apt-get install -y caddy
IP=$(curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
sed -e "s|@HOST@|${IP//./-}.sslip.io|g" ~/Caddyfile | sudo tee /etc/caddy/Caddyfile && sudo systemctl reload caddy
```

Check it: `curl https://<host>/api/health`. After retraining, copy the new `models/` files the same
way and `sudo systemctl restart lolreview-app`.

To use the whole app at that address, build the UI on the laptop and copy it over (again after UI
changes): `cd frontend && npm run build`, then
`gcloud compute scp --recurse dist lol-crawler:LeagueVODreview/frontend/ --zone us-central1-a`.

The app shares the Riot key with the crawler, which leaves 15 requests per 2 minutes on NA for it:
about one new player every 2 minutes. To point the GitHub Pages site at it:

```
gh variable set API_BASE --body "https://35-255-204-93.sslip.io"
gh workflow run pages.yml
```

`gh variable delete API_BASE` and another run go back to the saved games.
