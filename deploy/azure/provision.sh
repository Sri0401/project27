#!/usr/bin/env bash
# Creates one small Ubuntu VM that runs the whole UrbanPulse stack with Docker Compose.
# Run this in Azure Cloud Shell (Bash), which has the az CLI already signed in:
#   git clone <your-repo-url> && cd <repo>/deploy/azure && bash provision.sh <your-repo-url>
set -euo pipefail

REPO_URL="${1:?Usage: bash provision.sh <public git repo URL>}"
RG="${RG:-urbanpulse-rg}"
LOCATION="${LOCATION:-australiaeast}"
VM="${VM:-urbanpulse-vm}"
SIZE="${SIZE:-Standard_B1s}"
IMAGE="Canonical:ubuntu-24_04-lts:server:latest"

cd "$(dirname "$0")"
rendered="$(mktemp)"
trap 'rm -f "$rendered"' EXIT
sed "s#__REPO_URL__#${REPO_URL}#" cloud-init.yaml > "$rendered"

echo ">> Creating resource group $RG in $LOCATION"
az group create --name "$RG" --location "$LOCATION" --tags project=urbanpulse --output none

echo ">> Creating VM $VM ($SIZE). This takes 1-2 minutes."
az vm create \
  --resource-group "$RG" \
  --name "$VM" \
  --image "$IMAGE" \
  --size "$SIZE" \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard \
  --os-disk-size-gb 64 \
  --storage-sku Premium_LRS \
  --custom-data "$rendered" \
  --output none

echo ">> Opening port 80 (HTTP)"
az vm open-port --resource-group "$RG" --name "$VM" --port 80 --priority 1010 --output none

IP="$(az vm show --resource-group "$RG" --name "$VM" --show-details --query publicIps --output tsv)"
cat <<EOF

Done. The VM is now installing Docker and building the containers. This takes 5-10 minutes on a B1s.

  Website:   http://$IP
  API docs:  http://$IP/api/docs
  SSH:       ssh azureuser@$IP
  Progress:  ssh azureuser@$IP 'sudo tail -f /var/log/cloud-init-output.log'
  API key:   ssh azureuser@$IP 'grep API_KEY ~/urbanpulse/.env'

Delete everything when you are finished:  bash teardown.sh
EOF
