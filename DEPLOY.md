# Deploying Pit Wall to a public URL

Everything is prepped: the Docker image builds and runs, `fly.toml` is written,
and `flyctl` + Colima are installed. The only steps left are the ones that need
**your** account — I can't create logins or enter card details for you.

## Run it locally in a container (optional sanity check)

```bash
colima start                 # if not already running
docker build -t pitwall .
docker run --rm -p 5173:5173 pitwall
# open http://localhost:5173
```

## Deploy to Fly.io (recommended — deploys the Dockerfile directly)

1. **Create an account / log in** (opens a browser — this is yours to do):
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

Once you've done step 1 (`fly auth login`), I can run steps 3–4 for you — the
CLI uses your saved login token.

## Free & no card: Hugging Face Spaces (recommended — ~16 GB RAM)

HF Spaces runs Docker apps on a free CPU tier with far more RAM than Fly's paid
VM, and needs **only a free Hugging Face account (no card)**. The image was
tested running exactly as HF runs it (non-root UID 1000, `/tmp` cache) — it works.

1. Create a free account at https://huggingface.co, then
   **New → Space → SDK: Docker → Blank**. Give it a name.
2. In the Space's **Settings → Variables and secrets**, add:
   - `PITWALL_DISABLE_CONSOLE` = `1`   (turns off the terminal on the public site)
   - `F1ML_CACHE_DIR` = `/tmp/f1cache`  (writable FastF1 cache for the non-root user)
3. Put the code in the Space repo. Easiest:
   ```bash
   # from this project folder
   git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
   cp deploy/huggingface-README.md README.md   # HF needs this exact header (keep a backup of your own README)
   git add README.md && git commit -m "HF Space header"
   git push space main
   ```
   HF then builds the `Dockerfile` and gives you a permanent
   `https://<username>-<space>.hf.space` URL.
   > The HF header must live in the Space's `README.md`. If you don't want to
   > overwrite the project README on your main branch, push to the Space from a
   > separate branch or a copy.

## Recommended free / no-card host: Render

> Note: **Hugging Face Spaces now require a paid plan for Docker Spaces** (2026
> pricing change), so Render is the best remaining no-card option.

Render's free web service builds this repo's `Dockerfile`, **needs no credit
card**, and this repo ships a `render.yaml` blueprint so there's nothing to
configure by hand. Trade-offs on the free tier: **512 MB RAM** and it **sleeps
after 15 min idle** (first visit then takes ~50 s to wake). The core tabs
(standings, model, predictions, racing line, fantasy, weekend forecast) run fine;
the **live telemetry / strategy tabs may hit the memory limit** when FastF1 loads
a full session — those really want ~1 GB.

1. Push this repo to GitHub (create a free GitHub account if you don't have one).
   ```bash
   git remote add origin https://github.com/<you>/pitwall.git
   git push -u origin main
   ```
2. Create a free account at **render.com** (no card).
3. **New → Blueprint → connect your GitHub repo.** Render reads `render.yaml`,
   builds the Docker image, and deploys it.
4. You get a permanent `https://pitwall-*.onrender.com` URL.

The health check, port, and the `PITWALL_DISABLE_CONSOLE` / `F1ML_CACHE_DIR`
env vars are all set for you in `render.yaml`.

## Good to know

- **First launch is instant for the core tabs** — the image bakes in the trained
  models (`f1ml setup` runs at build time).
- **Telemetry/Strategy/Weekend tabs fetch from FastF1 on demand.** On a fresh
  cloud instance that data isn't cached, so the *first* load of a given session
  is slow (~20–40 s) and the cache is lost on redeploy / scale-to-zero. That's
  fine for a demo; a persistent volume would speed repeat loads if you want it.
- **Memory:** this app pulls in scikit-learn, FastF1, OpenCV and scikit-image, so
  give it **≥ 1 GB**. 256 MB will OOM on startup.
