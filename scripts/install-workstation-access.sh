#!/usr/bin/env bash
# Run as the normal workstation user, from a reviewed repository checkout.
set -euo pipefail

fail() {
    printf '%s\n' "$*" >&2
    exit 1
}

[[ "$(id -u)" != '0' ]] || fail 'Run this installer as your workstation user, without sudo.'
for tool in ssh systemctl ss kubectl curl install; do
    command -v "$tool" >/dev/null || fail "Required command is missing: $tool"
done
[[ -x /usr/bin/ssh ]] || fail 'The service expects OpenSSH at /usr/bin/ssh.'

repository_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
config="$HOME/.kube/pi-lab-vpn.yaml"
key="$HOME/.ssh/pi_lab_ed25519"
service=pi-lab-tunnels.service
unit_directory="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
bin_directory="$HOME/.local/bin"
[[ -r "$config" ]] || fail "Pi kubeconfig is missing or unreadable: $config"
[[ -r "$key" ]] || fail "SSH key is missing or unreadable: $key"

server="$(kubectl --kubeconfig "$config" config view --minify \
    -o 'jsonpath={.clusters[0].cluster.server}')"
[[ "$server" == 'https://127.0.0.1:16443' ]] || \
    fail "Expected https://127.0.0.1:16443 in $config, found: $server"

if ! systemctl --user is-active --quiet "$service"; then
    for port in 16443 18082; do
        listeners="$(ss -H -ltn "sport = :$port")"
        [[ -z "$listeners" ]] || \
            fail "Port $port already has a listener. Stop its manual tunnel before installing $service."
    done
fi

# This must work without a password or host-key prompt before systemd takes over.
ssh -nT -o BatchMode=yes -o IdentitiesOnly=yes -o ControlPath=none \
    -o StrictHostKeyChecking=yes -o ConnectTimeout=10 -o ConnectionAttempts=1 \
    -i "$key" lab@100.90.135.106 true || \
    fail 'Noninteractive SSH failed. Check Tailscale, the known host key, and your loaded SSH key.'

install -d "$unit_directory" "$bin_directory"
install -m 0644 "$repository_root/workstation/systemd/$service" "$unit_directory/$service"
for helper in pi-kubectl pi-flux pi-lab-check; do
    install -m 0755 "$repository_root/scripts/$helper.sh" "$bin_directory/$helper"
done

# Make an already loaded desktop SSH agent available to the user service.
if [[ -n "${SSH_AUTH_SOCK:-}" ]]; then
    systemctl --user import-environment SSH_AUTH_SOCK
fi
systemctl --user daemon-reload
systemctl --user enable "$service"
systemctl --user restart "$service"

printf 'Installed %s and the Pi command helpers.\n' "$service"
printf 'After SSH connects, run: %s/pi-lab-check\n' "$bin_directory"
printf 'Logs: journalctl --user -u %s -n 30 --no-pager\n' "$service"
