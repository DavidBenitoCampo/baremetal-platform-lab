#!/usr/bin/env bash
set -euo pipefail

config="${PI_LAB_KUBECONFIG:-$HOME/.kube/pi-lab-vpn.yaml}"
if [[ ! -r "$config" ]]; then
    printf 'Pi kubeconfig is missing or unreadable: %s\n' "$config" >&2
    exit 1
fi
exec kubectl --kubeconfig "$config" "$@"
