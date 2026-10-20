#!/usr/bin/env bash
# Deletes the resource group and everything in it (VM, disk, IP address, network).
set -euo pipefail
RG="${RG:-urbanpulse-rg}"
read -r -p "Delete resource group '$RG' and ALL its resources? [y/N] " answer
[[ "$answer" == "y" || "$answer" == "Y" ]] || { echo "Cancelled."; exit 0; }
az group delete --name "$RG" --yes --no-wait
echo "Deletion started. Check its progress with: az group show --name $RG"
