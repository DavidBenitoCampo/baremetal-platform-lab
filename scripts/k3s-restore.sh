#!/usr/bin/env bash
# Workstation usage: bash k3s-restore.sh lab@PI_TAILSCALE_IP /path/to/verified-backup.tar.gz.gpg MARKER_UID
# For this same-Pi lab test only. Existing application volumes are not restored.
set -euo pipefail
umask 077

if [[ $# -ne 3 ]]; then
  printf 'Usage: bash %s lab@PI_TAILSCALE_IP /path/to/verified-backup.tar.gz.gpg MARKER_UID\n' "$0" >&2
  exit 2
fi
pi_target="$1"
backup_file="$2"
expected_uid="$3"
[[ "$expected_uid" =~ ^[[:xdigit:]]{8}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{4}-[[:xdigit:]]{12}$ ]] || {
  printf 'Expected marker UID is not a UUID.\n' >&2
  exit 2
}
ssh_key="${PI_LAB_SSH_KEY:-$HOME/.ssh/pi_lab_ed25519}"
test -r "$ssh_key"
test -s "$backup_file"
backup_dir="$(cd -- "$(dirname -- "$backup_file")" && pwd -P)"
archive_name="$(basename -- "$backup_file")"
backup_file="$backup_dir/$archive_name"
[[ "$archive_name" =~ ^k3s-[0-9]{8}T[0-9]{6}Z\.tar\.gz\.gpg$ ]] || {
  printf 'This lab test expects a verified before-backup archive named k3s-UTC_TIMESTAMP.tar.gz.gpg.\n' >&2
  exit 1
}
ssh_options=(-T -i "$ssh_key" -o BatchMode=yes -o ConnectTimeout=15
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3)
(
  cd "$backup_dir"
  sha256sum --check "$archive_name.sha256"
)

# Stage the entire decrypted archive before stopping any service.
# Only root on the Pi can read this mktemp directory.
restore_dir="$(ssh "${ssh_options[@]}" "$pi_target" \
  'sudo -n mktemp -d /var/lib/rancher/pi-lab-restore-XXXXXXXX')"
[[ "$restore_dir" =~ ^/var/lib/rancher/pi-lab-restore-[[:alnum:]]{8}$ ]] || {
  printf 'Unexpected staging directory. Restore refused.\n' >&2
  exit 1
}
printf 'Private staging directory on Pi: %s\n' "$restore_dir"
ssh "${ssh_options[@]}" "$pi_target" "sudo -n mkdir -- $restore_dir/incoming"
if ! gpg --decrypt "$backup_file" \
  | ssh "${ssh_options[@]}" "$pi_target" \
      "sudo -n tar --extract --gzip --file=- --directory=$restore_dir/incoming --numeric-owner"; then
  printf 'Staging failed. K3s has not been stopped. Private files are under %s.\n' "$restore_dir" >&2
  exit 1
fi
printf 'Full archive staged successfully.\n'

# Both command timestamps and elapsed time come from the workstation.
# This interval excludes the decryption and upload above.
restore_start="$(date -u +'%Y-%m-%dT%H:%M:%S.%NZ')"
start_ns="$(python3 -c 'import time; print(time.monotonic_ns())')"
printf 'RESTORE_COMMAND_START_UTC=%s\n' "$restore_start"
if ! ssh "${ssh_options[@]}" "$pi_target" \
  "sudo -n bash -s -- $restore_dir $expected_uid" <<'REMOTE'; then
set -euo pipefail
umask 077
restore_dir="$1"
expected_uid="$2"
[[ "$restore_dir" =~ ^/var/lib/rancher/pi-lab-restore-[[:alnum:]]{8}$ ]]
test -d "$restore_dir"
test ! -L "$restore_dir"
test "$(stat -c %u "$restore_dir")" = 0
test "$(stat -c %a "$restore_dir")" = 700
live_root=''
incoming="$restore_dir/incoming"
previous="$restore_dir/previous"
failed="$restore_dir/failed"
targets=(etc/rancher/k3s var/lib/rancher/k3s/server/db
  var/lib/rancher/k3s/server/token var/lib/rancher/k3s/server/cred
  var/lib/rancher/k3s/server/tls)

# Refuse an unexpected host or archive before starting the outage.
systemctl is-active --quiet k3s
test -x /usr/local/bin/k3s-killall.sh
version="$(k3s --version | awk '$1 == "k3s" && $2 == "version" {print $3}')"
test "$version" = v1.36.5+k3s1
marker="$(k3s kubectl get configmap restore-test-marker -n default -o jsonpath='{.data.state}')"
test "$marker" = after-backup
marker_uid="$(k3s kubectl get configmap restore-test-marker -n default -o jsonpath='{.metadata.uid}')"
test "$marker_uid" = "$expected_uid"
for relative in "${targets[@]}"; do
  test -e "$live_root/$relative"
  test ! -L "$live_root/$relative"
  test -e "$incoming/$relative"
  test ! -L "$incoming/$relative"
  test "$(stat -c %d "$live_root/$relative")" = "$(stat -c %d "$restore_dir")"
  mkdir -p -- "$(dirname -- "$previous/$relative")"
  mkdir -p -- "$(dirname -- "$failed/$relative")"
done
test -s "$incoming/var/lib/rancher/k3s/server/db/state.db"
test -s "$incoming/var/lib/rancher/k3s/server/cred/encryption-config.json"
cmp -s "$incoming/var/lib/rancher/k3s/server/token" "$live_root/var/lib/rancher/k3s/server/token"
cmp -s "$incoming/var/lib/rancher/k3s/server/tls/server-ca.crt" "$live_root/var/lib/rancher/k3s/server/tls/server-ca.crt"

# Retain the current files by moving them, rather than deleting them.
# If an ordinary command fails, move the retained files back and start K3s.
stopped=0
moved=()
recover_on_error() {
  failure_status=$?
  trap - EXIT HUP INT TERM
  if [[ "$failure_status" -ne 0 && "$stopped" -eq 1 ]]; then
    printf 'Restore failed. Attempting rollback using retained files.\n' >&2
    set +e
    rollback_ok=1
    systemctl stop k3s || rollback_ok=0
    if [[ "$rollback_ok" -eq 1 ]]; then
      /usr/local/bin/k3s-killall.sh >&2 || rollback_ok=0
    fi
    if [[ "$rollback_ok" -eq 1 ]]; then
      for relative in "${moved[@]}"; do
        if [[ -e "$live_root/$relative" || -L "$live_root/$relative" ]]; then
          mv -- "$live_root/$relative" "$failed/$relative" || { rollback_ok=0; break; }
        fi
        mv -- "$previous/$relative" "$live_root/$relative" || { rollback_ok=0; break; }
      done
    fi
    if [[ "$rollback_ok" -eq 1 ]]; then
      systemctl start k3s >&2 || rollback_ok=0
    fi
    if [[ "$rollback_ok" -eq 1 ]]; then
      printf 'Retained files restored and K3s started. Check the node and applications.\n' >&2
    else
      printf 'Automatic rollback failed. Retained files: %s. Use SSH to investigate.\n' "$previous" >&2
    fi
  fi
  exit "$failure_status"
}
trap recover_on_error EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'Stopping K3s and its containers.\n'
# Set stopped first so a failed stop also triggers a recovery attempt.
stopped=1
systemctl stop k3s
/usr/local/bin/k3s-killall.sh >&2
for relative in "${targets[@]}"; do
  mv -- "$live_root/$relative" "$previous/$relative"
  moved+=("$relative")
  mv -- "$incoming/$relative" "$live_root/$relative"
done
printf 'Backup state installed. Starting K3s.\n'
systemctl start k3s

# Wait for actual API responses before querying restored state.
api_ready=0
for attempt in {1..60}; do
  if k3s kubectl --request-timeout=3s get --raw=/readyz >/dev/null 2>&1; then
    api_ready=1
    break
  fi
  sleep 2
done
test "$api_ready" -eq 1
k3s kubectl wait --for=condition=Ready node/pi-lab --timeout=180s
restored_marker="$(k3s kubectl get configmap restore-test-marker -n default -o jsonpath='{.data.state}')"
restored_uid="$(k3s kubectl get configmap restore-test-marker -n default -o jsonpath='{.metadata.uid}')"
test "$restored_marker" = before-backup
test "$restored_uid" = "$expected_uid"
printf 'RESTORED_MARKER_STATE=%s\n' "$restored_marker"
printf 'RESTORED_MARKER_UID=%s\n' "$restored_uid"
printf 'Retained pre-restore files on Pi: %s\n' "$previous"
# Filesystem restore and API marker checks passed. Verify workloads separately.
stopped=0
REMOTE
  printf 'Restore command failed. Keep both encrypted backups and check the Pi through SSH.\n' >&2
  exit 1
fi

printf 'CONTROL_PLANE_CHECKS_COMPLETE_UTC=%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%S.%NZ')"
python3 - "$start_ns" <<'PY'
import sys
import time
elapsed = (time.monotonic_ns() - int(sys.argv[1])) / 1_000_000_000
print(f"CONTROL_PLANE_CHECK_SECONDS={elapsed:.3f}")
PY
printf 'Next: verify Podinfo HTTP, an Ollama request, and fresh Flux reconciliation.\n'
