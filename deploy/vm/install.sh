#!/usr/bin/env bash
# Installs the pull-based deployment timer on the VM. Safe to run more than once.
#   sudo bash /home/azureuser/urbanpulse/deploy/vm/install.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v jq >/dev/null || { apt-get update -qq && apt-get install -y -qq jq; }
chmod +x "$HERE/deploy.sh"
install -m 0644 "$HERE/urbanpulse-deploy.service" /etc/systemd/system/urbanpulse-deploy.service
install -m 0644 "$HERE/urbanpulse-deploy.timer" /etc/systemd/system/urbanpulse-deploy.timer
systemctl daemon-reload
systemctl enable --now urbanpulse-deploy.timer
systemctl list-timers urbanpulse-deploy.timer --no-pager
