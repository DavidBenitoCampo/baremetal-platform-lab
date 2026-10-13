#!/usr/bin/env bash
# Run on the workstation: bash k3s-verify-backup.sh /path/to/backup.tar.gz.gpg
# This reads a backup, checks it locally, and removes the temporary plaintext.
set -euo pipefail
umask 077

if [[ $# -ne 1 ]]; then
  printf 'Usage: bash %s /path/to/backup.tar.gz.gpg\n' "$0" >&2
  exit 2
fi

for utility in gpg tar python3 sha256sum; do
  command -v "$utility" >/dev/null || {
    printf 'Missing workstation command: %s\n' "$utility" >&2
    exit 1
  }
done

backup_file="$1"
test -s "$backup_file"
backup_dir="$(cd -- "$(dirname -- "$backup_file")" && pwd -P)"
archive_name="$(basename -- "$backup_file")"
backup_file="$backup_dir/$archive_name"

# Verify the saved checksum before decrypting anything.
(
  cd "$backup_dir"
  sha256sum --check "$archive_name.sha256"
)

# mktemp creates a private directory. Only this new directory is removed.
verify_dir="$(mktemp -d "$backup_dir/verify-XXXXXXXX")"
cleanup() {
  verification_status=$?
  trap - EXIT HUP INT TERM
  case "$verify_dir" in
    "$backup_dir"/verify-????????)
      if [[ -d "$verify_dir" && ! -L "$verify_dir" ]]; then
        rm --recursive --force --one-file-system -- "$verify_dir"
        printf 'Temporary plaintext removed.\n'
      fi
      ;;
    *)
      printf 'Unexpected temporary directory. Cleanup refused.\n' >&2
      exit 1
      ;;
  esac
  exit "$verification_status"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

printf 'Decrypting and extracting the complete archive on this workstation.\n'
gpg --decrypt "$backup_file" \
  | tar --extract --gzip --file=- --directory="$verify_dir" \
      --no-same-owner --no-same-permissions
printf 'Full archive extraction: OK\n'

# Python's standard library checks the files and opens SQLite read-only.
# Copying the whole db directory retains any SQLite WAL sidecar files.
python3 - "$verify_dir" <<'PY'
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1])
required = [
    "etc/rancher/k3s/config.yaml",
    "var/lib/rancher/k3s/server/db/state.db",
    "var/lib/rancher/k3s/server/token",
    "var/lib/rancher/k3s/server/cred/encryption-config.json",
]
for relative in required:
    path = root / relative
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"Missing or empty backup file: {relative}")
if not (root / "var/lib/rancher/k3s/server/tls").is_dir():
    raise SystemExit("Missing TLS directory")
print("Required backup files: OK")

database = root / "var/lib/rancher/k3s/server/db/state.db"
connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
try:
    results = connection.execute("PRAGMA quick_check").fetchall()
finally:
    connection.close()
if results != [("ok",)]:
    raise SystemExit("SQLite quick_check failed")
print("SQLite quick_check: OK")
PY

printf 'Backup verification passed. Live restore has not been tested yet for this archive.\n'
