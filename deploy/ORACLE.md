# Deploy Pit Wall on Oracle Cloud (Always Free, no charge)

The full app — including live telemetry, strategy, and the racing-line analyzer —
running 24/7 on a free Oracle VM. The card Oracle asks for at sign-up is for
**identity verification only**; Always Free resources never auto-charge unless
you deliberately upgrade to "Pay As You Go".

You do the console steps (only you can — account, card, VM). The single script
[`oracle-setup.sh`](oracle-setup.sh) does everything on the server.

---

## 1. Create the account

<https://www.oracle.com/cloud/free/> → **Start for free**. Email, phone, and a
card for verification. Pick a home region close to you (it can't be changed
later).

## 2. Create the VM

Console → **☰ Menu → Compute → Instances → Create instance**.

- **Name:** `pitwall`
- **Image:** click *Edit* → *Change image* → **Canonical Ubuntu 22.04**
- **Shape:** *Change shape* → **Ampere** → `VM.Standard.A1.Flex` →
  **2 OCPUs, 12 GB** memory. This is ARM (same as an Apple-Silicon Mac) and well
  within the Always Free limit (4 OCPU / 24 GB total).
  - If you get **"Out of host capacity"**, try 1 OCPU / 6 GB, a different
    Availability Domain, or retry later — A1 capacity is regional and comes and
    goes. Last resort: `VM.Standard.E2.1.Micro` (x86, Always Free) — but it has
    only 1 GB RAM, so live-telemetry loads may be shaky.
- **SSH keys:** *Generate a key pair* and **download the private key** (or paste
  your own public key). You need this to log in.
- **Networking:** leave the defaults (it creates a VCN and gives you a public
  IPv4). Make sure **"Assign a public IPv4 address"** is on.
- **Create.** Note the **Public IP address** once it's running.

## 3. Open port 80 (cloud firewall)

This is the step everyone forgets. On the instance page:

- Click the **Virtual Cloud Network** link → **Security Lists** → **Default
  Security List**.
- **Add Ingress Rules**:
  - Source CIDR: `0.0.0.0/0`
  - IP Protocol: **TCP**
  - Destination Port Range: **80**
- **Add**.

## 4. Deploy

SSH in (user is `ubuntu` on the Ubuntu image; `opc` on Oracle Linux):

```bash
chmod 400 /path/to/your-private-key.key
ssh -i /path/to/your-private-key.key ubuntu@<PUBLIC_IP>
```

Then run the one-liner:

```bash
curl -fsSL https://raw.githubusercontent.com/Mithilbatra/F1_ML_project/main/deploy/oracle-setup.sh | bash
```

It installs Docker, clones the repo, builds the image, opens the OS firewall,
and starts the container with auto-restart. First build takes a few minutes.

When it finishes it prints your URL:

```
Pit Wall is live:  http://<PUBLIC_IP>/
```

## 5. It keeps itself current

You don't have to do anything to track the 2026 season. The container runs with
`PITWALL_AUTO_REFRESH=24`, so once a day it pulls the latest results and retrains
— as each race runs, the live site fetches it and the model learns from it.
Each deploy starts from the data and models built into the image; the first
refresh, about a minute after start, catches the current season up. The FastF1
download cache lives on a Docker volume (`pitwall_cache`), so that catch-up
rarely needs to re-download anything.

To force a refresh immediately instead of waiting for the daily one:

```bash
sudo docker exec pitwall /app/.venv/bin/python -m f1_ml.cli refresh
```

### Updating the code later

SSH back in and re-run the deploy one-liner — it pulls the latest code, rebuilds,
and restarts; the auto-refresh then brings the current season up to date.

## 6. (Optional) A real domain + HTTPS

With `http://<ip>/` working, point a domain's **A record** at the public IP,
then put [Caddy](https://caddyserver.com) in front for automatic HTTPS:

```bash
sudo docker run -d --name caddy --restart unless-stopped \
  -p 443:443 -p 8080:80 -v caddy_data:/data \
  caddy caddy reverse-proxy --from yourdomain.com --to localhost:80
```

(Also add an ingress rule for TCP 443, and re-point the container to a non-80
port if Caddy takes 80.)

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| Page won't load at all | The **VCN Security List** ingress rule for TCP 80 (step 3) is missing. |
| Loads then times out on Telemetry | First FastF1 download for that session — give it 20–30 s; it caches after. |
| `docker: permission denied` | Re-run with the script (it uses `sudo`), or `sudo usermod -aG docker $USER` then re-login. |
| Container not running | `sudo docker logs pitwall` to see why; `sudo docker ps -a` for status. |
