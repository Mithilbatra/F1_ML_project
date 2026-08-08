#!/usr/bin/env bash
#
# Pit Wall — one-shot deploy on an Oracle Cloud Always Free VM.
# Works on the Ubuntu or Oracle Linux images Oracle offers.
#
# On the VM, run:
#   curl -fsSL https://raw.githubusercontent.com/Mithilbatra/F1_ML_project/main/deploy/oracle-setup.sh | bash
# or, after cloning the repo:
#   bash deploy/oracle-setup.sh
#
# Re-run it any time to update — it pulls the latest code, rebuilds, and
# restarts the container. Idempotent and safe.
#
set -euo pipefail

REPO="https://github.com/Mithilbatra/F1_ML_project.git"
DIR="${PITWALL_DIR:-$HOME/F1_ML_project}"
PORT="${PORT:-80}"      # public HTTP port
NAME="pitwall"

echo "==> Pit Wall deploy on $(hostname) — public port ${PORT}"

# 1) Docker + git ----------------------------------------------------------
install_pkg() {
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y && sudo apt-get install -y "$@"
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y "$@"
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y "$@"
  fi
}
command -v git >/dev/null 2>&1 || install_pkg git
if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker…"
  install_pkg docker.io || install_pkg docker || curl -fsSL https://get.docker.com | sudo sh
  sudo systemctl enable --now docker
fi

# 2) Code ------------------------------------------------------------------
if [ -d "$DIR/.git" ]; then
  echo "==> Updating repo in $DIR…"
  git -C "$DIR" pull --ff-only
else
  echo "==> Cloning repo into $DIR…"
  git clone "$REPO" "$DIR"
fi

# 3) Build -----------------------------------------------------------------
echo "==> Building image (first build takes a few minutes)…"
sudo docker build -t "${NAME}:latest" "$DIR"

# 4) Run -------------------------------------------------------------------
# --restart unless-stopped survives reboots; the console runner is disabled
# because this is public. The named volumes persist the FastF1 cache, the data
# the auto-refresh accumulates through the season, and the retrained models —
# so a redeploy keeps everything the model has learned (they seed from the
# image's bundled 2024–25 data the first time).
echo "==> (Re)starting container…"
sudo docker rm -f "${NAME}" >/dev/null 2>&1 || true
sudo docker run -d --name "${NAME}" --restart unless-stopped \
  -p "${PORT}:5173" -e PITWALL_DISABLE_CONSOLE=1 \
  -v pitwall_cache:/app/fastf1_cache_dir \
  -v pitwall_data:/app/data \
  -v pitwall_models:/app/models \
  "${NAME}:latest"

# 5) Host firewall ---------------------------------------------------------
# Oracle's images ship blocking everything but SSH; open the port at the OS
# level too (the VCN Security List is the other layer — do that in the console).
echo "==> Opening port ${PORT} in the OS firewall…"
if command -v firewall-cmd >/dev/null 2>&1; then
  sudo firewall-cmd --permanent --add-port="${PORT}/tcp" && sudo firewall-cmd --reload
else
  sudo iptables -I INPUT -p tcp --dport "${PORT}" -j ACCEPT || true
  if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save || true
  else
    sudo mkdir -p /etc/iptables && sudo sh -c "iptables-save > /etc/iptables/rules.v4" || true
  fi
fi

IP="$(curl -s https://api.ipify.org 2>/dev/null || echo '<your-vm-public-ip>')"
echo
echo "============================================================"
echo "  Pit Wall is live:   http://${IP}/"
echo
echo "  If it doesn't load, the VCN Security List ingress rule is"
echo "  almost always the reason — add TCP ${PORT} from 0.0.0.0/0"
echo "  in the Oracle console (see deploy/ORACLE.md)."
echo "============================================================"
