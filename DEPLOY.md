# Deploying Pit Wall to a public URL

The live site runs on an Oracle Cloud Always Free VM — see
[deploy/ORACLE.md](deploy/ORACLE.md) for the one-command setup. Fly.io (below)
works too if you'd rather use a managed host.

## Run it locally in a container (optional sanity check)

```bash
colima start                 # if not already running
docker build -t pitwall .
docker run --rm -p 5173:5173 pitwall
# open http://localhost:5173
```

## Deploy to Fly.io (deploys the Dockerfile directly)

1. **Create an account / log in** (opens a browser):
   ```bash
   fly auth signup      # or: fly auth login
   ```
   > Fly requires a payment card on file even for small apps. The config uses
   > `auto_stop_machines`, so the app scales to **zero when idle** — you're only
   > billed for actual use (a 1 GB shared VM is a few dollars a month at most,
   > often pennies if it's mostly idle).

2. **Pick a globally-unique app name** — edit `app = "pitwall"` in `fly.toml`
   (e.g. `pitwall-mithil`), and set `primary_region` to one near you
   (`lhr` London, `ams` Amsterdam, `fra` Frankfurt, `sin` Singapore, `iad` US-east…).

3. **Create the app + deploy:**
   ```bash
   fly launch --copy-config --no-deploy   # registers the app from fly.toml
   fly deploy                             # builds the image & ships it
   ```

4. **Open your live site:**
   ```bash
   fly open
   ```

## Good to know

- **First launch is instant for the core tabs** — the image bakes in the trained
  models (`f1ml setup` runs at build time).
- **Telemetry/Strategy/Weekend tabs fetch from FastF1 on demand.** On a fresh
  cloud instance that data isn't cached, so the *first* load of a given session
  is slow (~20–40 s) and the cache is lost on redeploy / scale-to-zero. That's
  fine for a demo; a persistent volume would speed repeat loads if you want it.
- **Live telemetry often fails from cloud servers.** The official F1 timing feed
  tends to refuse datacenter IPs, so the Telemetry and Strategy tabs can error on
  a VM while everything else works. Run `f1ml serve` locally for those.
- **Memory:** this app pulls in scikit-learn, FastF1, OpenCV and scikit-image, so
  give it **≥ 1 GB**. 256 MB will OOM on startup.
