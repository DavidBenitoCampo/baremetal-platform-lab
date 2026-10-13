# K3s backup and restore

This is the procedure I tested on 13 October 2026. Run the helpers on the workstation with the repository checked out. They connect to `lab@100.90.135.106` using `$HOME/.ssh/pi_lab_ed25519`.

The test restores K3s state on the existing Pi and SSD. The cluster uses K3s `v1.36.5+k3s1` with SQLite. Restoring interrupts all cluster workloads. Keep the workstation HTTP probe and SSH tunnel running during the exercise.

## What each script does

| Script | Purpose |
| --- | --- |
| `scripts/k3s-backup.sh` | Stops K3s, streams its configuration and database to GPG on the workstation, restarts K3s, and saves an encrypted archive with a checksum. |
| `scripts/k3s-verify-backup.sh` | Checks the checksum, decrypts and extracts the complete archive, checks required files, runs SQLite `quick_check`, and removes its temporary plaintext. |
| `scripts/k3s-restore.sh` | Stages the backup on the Pi, checks the lab identity and marker, stops K3s and its containers, retains the live files, installs the backup, restarts K3s, and verifies the restored marker and Ready node. |

Use the tested `k3s-backup-v2.sh` from Downloads as `scripts/k3s-backup.sh`. The filename change does not change its contents.

The workstation needs Bash, SSH, GPG, tar, sha256sum, and Python 3. The Pi needs working key login and passwordless sudo. `k3s-killall.sh` comes from the K3s installation.

Archives stay in `$HOME/pi-lab-backups`, outside Git. Store the GPG passphrase separately. This workstation disk is independent of the Pi's SSD. The source archive and rollback archive on the same workstation are two restore points, rather than two independent destinations.

## Backup scope

The archive contains:

- `/etc/rancher/k3s`
- `/var/lib/rancher/k3s/server/db`, including SQLite sidecar files
- `/var/lib/rancher/k3s/server/token`
- `/var/lib/rancher/k3s/server/cred`
- `/var/lib/rancher/k3s/server/tls`

The archive contains credentials and keys. Only the scripts and reviewed command results belong in the public repository.

Application volume data stays on the existing SSD. Model files, Prometheus history, Grafana data, the OS, and recovery onto an empty disk are outside this exercise.

## Prepare the marker and source backup

The `restore-test-marker` ConfigMap in `default` is outside Flux. Save its UID before the test. The source backup requires state `before-backup`.

For the existing marker:

```bash
ssh -i "$HOME/.ssh/pi_lab_ed25519" lab@100.90.135.106 'sudo -n k3s kubectl patch configmap restore-test-marker -n default --type=merge --patch="data: {state: before-backup}"'

ssh -i "$HOME/.ssh/pi_lab_ed25519" lab@100.90.135.106 'sudo -n k3s kubectl get configmap restore-test-marker -n default -o yaml'

bash scripts/k3s-backup.sh lab@100.90.135.106 before-backup
```

For a fresh lab with no marker, create `restore-test-marker` in `default` with `--from-literal=state=before-backup` before taking the backup.

The backup script prints the new archive path. Set `BACKUP_FILE` to that path and verify the archive. This example selects the source archive from the completed test:

```bash
BACKUP_FILE="$HOME/pi-lab-backups/k3s-20261012T221831Z.tar.gz.gpg"

bash scripts/k3s-verify-backup.sh "$BACKUP_FILE"
```

Require successful checksum, extraction, required-file, and SQLite checks before continuing. Confirm the node returns to Ready after the backup.

## Change the marker and create a rollback copy

Changing the marker after taking the source backup gives the restore a visible result to recover.

```bash
ssh -i "$HOME/.ssh/pi_lab_ed25519" lab@100.90.135.106 'sudo -n k3s kubectl patch configmap restore-test-marker -n default --type=merge --patch="data: {state: after-backup}"'

ssh -i "$HOME/.ssh/pi_lab_ed25519" lab@100.90.135.106 'sudo -n k3s kubectl get configmap restore-test-marker -n default -o yaml'

bash scripts/k3s-backup.sh lab@100.90.135.106 after-backup
```

Select the rollback path printed by this run. This example selects the verified rollback archive from the completed test:

```bash
ROLLBACK_FILE="$HOME/pi-lab-backups/k3s-rollback-20261012T225649Z.tar.gz.gpg"

bash scripts/k3s-verify-backup.sh "$ROLLBACK_FILE"
```

Before the restore, the live marker must be `after-backup` and its UID must match the saved UID. The restore helper refuses another marker state, K3s version, server token, or server CA.

## Record HTTP during the restore

Open a separate workstation terminal and keep this tunnel running:

```bash
ssh -N -i "$HOME/.ssh/pi_lab_ed25519" -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -L 127.0.0.1:18081:10.0.1.16:80 lab@100.90.135.106
```

From the repository terminal, confirm HTTP 200 before starting the test:

```bash
curl --fail --show-error --max-time 5 -i -H 'Host: podinfo.lab.test' http://127.0.0.1:18081/readyz
```

Use a fresh filename for each test. Start the logger and retain its PID in this terminal:

```bash
python3 scripts/http_probe.py http://127.0.0.1:18081/readyz --host podinfo.lab.test --count 600 --interval 1 --timeout 0.8 > docs/evidence/restore-http-new.jsonl &
RESTORE_PROBE_PID=$!

sleep 2
head -n 2 docs/evidence/restore-http-new.jsonl
```

Require healthy baseline samples. Connection refused at `127.0.0.1:18081` means the local connection failed before the request reached the application. Reopen the tunnel and restart the measurement in a new file.

## Restore and check the marker

The completed test used this ConfigMap UID. When repeating on a different marker, pass its recorded UID instead.

```bash
set -o pipefail

bash scripts/k3s-restore.sh lab@100.90.135.106 "$BACKUP_FILE" 1ca94ac5-a093-4b6f-8df1-84820b6a7e05 2>&1 | tee docs/evidence/restore-output-new.txt
```

GPG asks for the passphrase. The helper stages the complete archive before stopping K3s. During the restore, it moves the current files into a private `previous` directory and attempts to restore those files if an ordinary command fails after stopping K3s.

Successful output includes:

```text
RESTORED_MARKER_STATE=before-backup
RESTORED_MARKER_UID=1ca94ac5-a093-4b6f-8df1-84820b6a7e05
CONTROL_PLANE_CHECK_SECONDS=...
```

The retained directory contains plaintext credentials. Keep root-only access and record its exact path privately. Review recovery checks before removing the retained files.

## Verify applications and GitOps

Follow [the post-restore checks](post-restore-checks.md). Save node and Deployment output, an HTTP readiness response, a new Flux request acknowledgement, and an inference result.

The Ollama port-forward stops when its destination Pod exits. Reopen the tunnel after the restore:

```bash
ssh -i "$HOME/.ssh/pi_lab_ed25519" -o ExitOnForwardFailure=yes -L 127.0.0.1:11435:127.0.0.1:11436 lab@100.90.135.106 'sudo -n k3s kubectl port-forward -n ai-lab service/ollama 11436:11434 --address=127.0.0.1'
```

Keep this terminal open. From the repository terminal:

```bash
python3 scripts/inference_probe.py --url http://127.0.0.1:11435 --count 1 | tee docs/evidence/ollama-after-restore-new.jsonl

wait "$RESTORE_PROBE_PID"
tail -n 1 docs/evidence/restore-http-new.jsonl
```

HTTP 200 and `ok: true` verify the inference request completed. `loaded_before: false` means the model was not already loaded in memory. Compare the model digest with the pre-restore result.

Keep the raw HTTP samples as well as the summary. Measure the interval from the first failed request to the first success after the final failed request. Sampling once per second limits the precision. The helper's duration ends after API, node, and marker checks, so application recovery needs its own measurement.

## Results from 13 October

The successful run used `k3s-20261012T221831Z.tar.gz.gpg`. The verified rollback archive was `k3s-rollback-20261012T225649Z.tar.gz.gpg`.

| Check | Observed result |
| --- | --- |
| Marker | Restored to `before-backup` with original UID |
| Restore command and control-plane checks | 17.265 seconds |
| HTTP attempts | 600 at one-second intervals, 0.8-second timeout |
| HTTP results | 578 HTTP 200, 20 transport errors, 2 HTTP 503 |
| First failed sample | 21:35:48.829181 UTC |
| Last failed sample | 21:36:09.829208 UTC |
| First success after outage | 21:36:10.829209 UTC |
| Sampled interruption | About 22 seconds |
| p95 HTTP attempt latency | 28.75 ms |
| Deployments | All reported Ready |
| Flux | Source and four Kustomizations reported Ready at `ef96a903` |
| Inference | HTTP 200, 4.6047 seconds, 27 tokens, unchanged model digest |

The earlier attempt stopped before K3s because the live marker was already `before-backup`. No retained `previous` directory appeared and the K3s log showed no restart. Its 900 successful requests describe a baseline health check. They do not measure a restore.

The successful restore and application checks completed. Retaining matching Flux request and acknowledgement values is a follow-up check. A second independent backup destination and empty-disk recovery are still untested.

[Backup verification](../evidence/2026-10-13-backup-verification.txt) · [Rollback verification](../evidence/2026-10-13-rollback-verification.txt) · [Restore output](../evidence/2026-10-13-live-restore-attempt-2.txt) · [HTTP samples](../evidence/2026-10-13-live-restore-http.jsonl) · [Inference response](../evidence/ollama-after-live-restore.jsonl)

## Troubleshooting

If the helper reports a precondition failure, check K3s version and service state, marker state and UID, and the retained directory before another attempt. A failed message alone does not prove either a completed restore or a completed rollback.

If a failure happens after K3s stops, the helper attempts a rollback using the retained live files. Check the node and applications through SSH. Keep the encrypted source and rollback archives available.

If the tunnel reports a port conflict, inspect the listener before choosing another port. Keep forwarding bound to `127.0.0.1`.

## References

- [K3s SQLite backup and restore](https://docs.k3s.io/datastore/backup-restore)
- [Stopping K3s containers](https://docs.k3s.io/upgrades/killall)
- [Flux GitRepository request handling](https://fluxcd.io/flux/components/source/gitrepositories/#triggering-a-reconcile)
- [Flux Kustomization request handling](https://fluxcd.io/flux/components/kustomize/kustomizations/#triggering-a-reconcile)
