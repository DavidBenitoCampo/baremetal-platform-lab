#!/usr/bin/env bash
# Run on the workstation: bash k3s-backup.sh lab@PI_TAILSCALE_IP [before-backup|after-backup]
# The encrypted archive stays outside the repository.
set -euo pipefail
umask 077

if [[ $# -lt 1 || $# -gt 2 ]]; then
  printf 'Usage: bash %s lab@PI_TAILSCALE_IP [before-backup|after-backup]\n' "$0" >&2
  exit 2
fi

pi_target="$1"
expected_marker="${2:-before-backup}"
case "$expected_marker" in
  before-backup) archive_prefix=k3s ;;
  after-backup) archive_prefix=k3s-rollback ;;
  *)
    printf 'Expected marker must be before-backup or after-backup.\n' >&2
    exit 2
    ;;
esac
ssh_key="${PI_LAB_SSH_KEY:-$HOME/.ssh/pi_lab_ed25519}"
backup_dir="${PI_LAB_BACKUP_DIR:-$HOME/pi-lab-backups}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive_name="${archive_prefix}-${stamp}.tar.gz.gpg"
backup_file="$backup_dir/$archive_name"
partial_file="$backup_file.partial"

for utility in ssh gpg sha256sum; do
  command -v "$utility" >/dev/null || {
    printf 'Missing workstation command: %s\n' "$utility" >&2
    exit 1
  }
done
[[ -r "$ssh_key" ]] || {
  printf 'SSH key is not readable: %s\n' "$ssh_key" >&2
  exit 1
}

mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
[[ ! -e "$backup_file" && ! -e "$partial_file" ]] || {
  printf 'This backup name already exists. Run again with a new timestamp.\n' >&2
  exit 1
}

printf 'Creating an encrypted backup from %s.\n' "$pi_target"
printf 'GPG will ask for a backup passphrase. Keep the passphrase outside Git.\n'

# The Pi sends a tar stream. The workstation encrypts it without writing a
# plaintext archive. pipefail catches SSH, copy, restart, or encryption errors.
if ! ssh -T -i "$ssh_key" -o BatchMode=yes -o ConnectTimeout=15 \
  -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  "$pi_target" "sudo -n bash -s -- $expected_marker" <<'REMOTE' \
  | gpg --symmetric --cipher-algo AES256 --output "$partial_file"; then
set -euo pipefail
expected_marker="$1"

# These checks run before stopping K3s.
systemctl is-active --quiet k3s
test -s /var/lib/rancher/k3s/server/db/state.db
test -s /var/lib/rancher/k3s/server/token
test -s /var/lib/rancher/k3s/server/cred/encryption-config.json
marker="$(k3s kubectl get configmap restore-test-marker -n default -o jsonpath='{.data.state}')"
[[ "$marker" == "$expected_marker" ]] || {
  printf 'The restore-test-marker must have state=%s.\n' "$expected_marker" >&2
  exit 1
}

# Restart K3s on normal exit and ordinary copy failures. A power loss or
# forcibly killed shell still requires checking the service through SSH.
restart_k3s() {
  copy_status=$?
  trap - EXIT HUP INT TERM
  if ! systemctl start k3s >&2; then
    printf 'K3s failed to start. Check the service through SSH.\n' >&2
    exit 1
  fi
  printf 'K3s service started.\n' >&2
  exit "$copy_status"
}
trap restart_k3s EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'Stopping K3s while copying SQLite state.\n' >&2
systemctl stop k3s
tar --numeric-owner --create --gzip --file=- --directory=/ \
  etc/rancher/k3s \
  var/lib/rancher/k3s/server/db \
  var/lib/rancher/k3s/server/token \
  var/lib/rancher/k3s/server/cred \
  var/lib/rancher/k3s/server/tls
REMOTE
  printf 'Backup failed. Do not use any .partial file as a backup.\n' >&2
  printf 'Check K3s through SSH before retrying.\n' >&2
  exit 1
fi

# Only label the archive complete after the entire pipeline succeeds.
mv "$partial_file" "$backup_file"
chmod 600 "$backup_file"
(
  cd "$backup_dir"
  sha256sum "$archive_name" > "$archive_name.sha256"
  sha256sum --check "$archive_name.sha256"
)

printf '\nEncrypted backup: %s\n' "$backup_file"
printf 'Checksum file: %s.sha256\n' "$backup_file"
printf 'Captured marker state: %s\n' "$expected_marker"
printf 'Next: verify archive extraction before using this backup.\n'
