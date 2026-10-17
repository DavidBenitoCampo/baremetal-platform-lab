#!/usr/bin/env bash
# Check the workstation access path before starting an evidence capture.
set -euo pipefail

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

config="${PI_LAB_KUBECONFIG:-$HOME/.kube/pi-lab-vpn.yaml}"
[[ -r "$config" ]] || fail "Pi kubeconfig is missing or unreadable: $config"
systemctl --user is-active --quiet pi-lab-tunnels.service || \
    fail 'Tunnel service is not active. Check: journalctl --user -u pi-lab-tunnels.service -n 30 --no-pager'

server="$(kubectl --kubeconfig "$config" config view --minify \
    -o 'jsonpath={.clusters[0].cluster.server}')"
[[ "$server" == 'https://127.0.0.1:16443' ]] || \
    fail "Unexpected Pi API endpoint in $config: $server"

kubectl --kubeconfig "$config" --request-timeout=10s get --raw=/readyz >/dev/null || \
    fail 'Pi API readiness check failed through port 16443.'
ready="$(kubectl --kubeconfig "$config" --request-timeout=10s get node pi-lab \
    -o 'jsonpath={.status.conditions[?(@.type=="Ready")].status}')"
[[ "$ready" == 'True' ]] || fail "Node pi-lab is not Ready: $ready"
printf 'Pi API reachable. Node pi-lab Ready.\n'

status="$(curl --noproxy 127.0.0.1 --connect-timeout 3 --max-time 5 \
    --fail --silent --show-error --output /dev/null --write-out '%{http_code}' \
    --header 'Host: podinfo.lab.test' http://127.0.0.1:18082/readyz)" || \
    fail 'Podinfo HTTP check failed through port 18082.'
[[ "$status" == '200' ]] || fail "Podinfo returned HTTP $status instead of 200."
printf 'Podinfo HTTP 200. Access checks passed.\n'
