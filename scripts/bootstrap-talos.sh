#!/usr/bin/env bash
# Wraps talosctl to generate, apply, and bootstrap the Milestone 1 single-node
# Talos cluster from the patches in talos/patches/. See
# docs/runbooks/bootstrap-talos.md for the full procedure this supports.
#
# Generated config and secrets are written to talos/secrets/ and ./kubeconfig,
# both gitignored. Never commit their contents.
set -euo pipefail

CLUSTER_NAME="homelab"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRETS_DIR="${REPO_ROOT}/talos/secrets"
PATCHES_DIR="${REPO_ROOT}/talos/patches"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [args]

Commands:
  generate <endpoint-ip>   Generate controlplane.yaml/worker.yaml/talosconfig into talos/secrets/
  apply <node-ip>          Apply the generated controlplane.yaml to a node in maintenance mode
  bootstrap <node-ip>      Bootstrap etcd on the node (run exactly once, on the first control plane node)
  kubeconfig <node-ip>     Fetch the admin kubeconfig to ./kubeconfig
  all <endpoint-ip>        Run generate, apply, bootstrap, kubeconfig in sequence

Requires talosctl on PATH. Run from the repo root or anywhere; paths are resolved relative to this script.
EOF
}

require_talosctl() {
  command -v talosctl >/dev/null 2>&1 || { echo "error: talosctl not found on PATH" >&2; exit 1; }
}

cmd_generate() {
  local endpoint_ip="$1"
  mkdir -p "${SECRETS_DIR}"
  talosctl gen config "${CLUSTER_NAME}" "https://${endpoint_ip}:6443" \
    --config-patch "@${PATCHES_DIR}/pi5.yaml" \
    --config-patch "@${PATCHES_DIR}/install.yaml" \
    --config-patch "@${PATCHES_DIR}/ephemeral-ssd.yaml" \
    --config-patch-control-plane "@${PATCHES_DIR}/controlplane.yaml" \
    --output-dir "${SECRETS_DIR}" \
    --force
  echo "Generated config in ${SECRETS_DIR}/ (gitignored — do not commit)"
}

cmd_apply() {
  local node_ip="$1"
  talosctl apply-config --insecure -n "${node_ip}" -f "${SECRETS_DIR}/controlplane.yaml"
}

cmd_bootstrap() {
  local node_ip="$1"
  talosctl --talosconfig "${SECRETS_DIR}/talosconfig" bootstrap -n "${node_ip}" -e "${node_ip}"
}

cmd_kubeconfig() {
  local node_ip="$1"
  talosctl --talosconfig "${SECRETS_DIR}/talosconfig" kubeconfig -n "${node_ip}" -e "${node_ip}" "${REPO_ROOT}/kubeconfig"
  echo "Wrote ${REPO_ROOT}/kubeconfig (gitignored — do not commit)"
  echo "export KUBECONFIG=${REPO_ROOT}/kubeconfig"
}

require_talosctl

cmd="${1:-}"
[ $# -gt 0 ] && shift

case "${cmd}" in
  generate) cmd_generate "$@" ;;
  apply) cmd_apply "$@" ;;
  bootstrap) cmd_bootstrap "$@" ;;
  kubeconfig) cmd_kubeconfig "$@" ;;
  all)
    ip="${1:?endpoint-ip required}"
    cmd_generate "${ip}"
    cmd_apply "${ip}"
    echo "Waiting for the node to install Talos and reboot (this can take a couple of minutes)..."
    echo "Re-run '$(basename "$0") bootstrap ${ip}' by hand if this times out."
    sleep 60
    cmd_bootstrap "${ip}"
    cmd_kubeconfig "${ip}"
    ;;
  *)
    usage
    exit 1
    ;;
esac
