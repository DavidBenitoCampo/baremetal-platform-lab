# Checks after a K3s restore

Use this procedure after restoring K3s control-plane state on the same Pi.
The K3s service should already be running. Backup extraction belongs to a
[backup and restore runbook](backup-restore.md).

The goal is to verify remote access, workload readiness, and Flux synchronization.

## Open the API tunnel

Run this on the workstation. Replace `PI_TAILSCALE_IP` with the Pi's Tailscale
address. Keep this terminal open while using Kubernetes commands.

```bash
ssh -N -i "$HOME/.ssh/pi_lab_ed25519" \
  -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:16443:127.0.0.1:6443 \
  lab@PI_TAILSCALE_IP
```

The tunnel listens on workstation port 16443 and forwards requests to the
Pi's Kubernetes API on port 6443. An open connection normally produces no output.

In a second workstation terminal, select the existing VPN kubeconfig:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab-vpn.yaml"
```

For this lab, the VPN kubeconfig uses server `https://127.0.0.1:16443` and
TLS server name `10.0.1.16`. Certificate verification stays enabled.
Keep this file outside the repository.

## Check Kubernetes

These commands read the node and workload state:

```bash
kubectl wait --for=condition=Ready node/pi-lab --timeout=180s
kubectl get nodes
kubectl get deployments -A
```

Expected state: node `pi-lab` is Ready, Podinfo has two ready replicas, and
Ollama, Prometheus, Grafana, kube-state-metrics, and the Flux controllers each
have one ready replica.

## Check Flux

The first command asks source-controller to fetch GitHub. The second asks
kustomize-controller to apply the root configuration from `clusters/pi`.

```bash
flux reconcile source git flux-system -n flux-system
flux reconcile kustomization flux-system -n flux-system
flux get sources git -A
flux get kustomizations -A
```

Compare the Git source revision with the current GitHub `main` commit.
The four Kustomizations should report the same revision, Ready True, and
Suspended False. Workload Kustomizations reconcile on their own intervals.

## Check Flux through SSH

Use this route when the workstation API tunnel is closed. Run from the repository root. The commands request a fresh Git fetch, wait for the controller to acknowledge the request, then reconcile each Kustomization.

`requestedAt` is the Flux annotation name. The earlier `reconcile.fluxcd.io/request` annotation does not request reconciliation.

```bash
set -o pipefail

ssh -i "$HOME/.ssh/pi_lab_ed25519" lab@100.90.135.106 '
set -e
restore_flux_request="$(date -u +%s%N)"

for resource in gitrepository/flux-system kustomization/flux-system kustomization/monitoring kustomization/ollama kustomization/podinfo; do
  sudo -n k3s kubectl annotate "$resource" -n flux-system --overwrite "reconcile.fluxcd.io/requestedAt=$restore_flux_request"
  sudo -n k3s kubectl wait "$resource" -n flux-system --for="jsonpath={.status.lastHandledReconcileAt}=$restore_flux_request" --timeout=180s
  sudo -n k3s kubectl wait "$resource" -n flux-system --for=condition=Ready --timeout=180s
done

sudo -n k3s kubectl get gitrepository,kustomizations -n flux-system -o custom-columns="KIND:.kind,NAME:.metadata.name,REQUESTED:.metadata.annotations.reconcile\\.fluxcd\\.io/requestedAt,HANDLED:.status.lastHandledReconcileAt"
sudo -n k3s kubectl get gitrepository,kustomizations -n flux-system
' | tee docs/evidence/flux-after-live-restore.txt
```

Every `HANDLED` value should equal its `REQUESTED` value. The source and all four Kustomizations should report Ready. Save this output to prove the controllers processed the new request. A Ready value alone also appears in restored status and does not prove a new request was handled.

## If reconciliation times out after the restore

Save the errors before restarting a controller:

```bash
kubectl get pods -n flux-system
kubectl logs -n flux-system deployment/source-controller --since=20m --tail=50
kubectl logs -n flux-system deployment/kustomize-controller --since=20m --tail=50
```

In the 11 October 2026 test, the controllers were running, but reconciliation
failed with `failed to update status: timed out waiting for the condition`.
They had not restarted after restoring the older database.

For this observed failure, restart the affected controllers one at a time:

```bash
kubectl rollout restart deployment/source-controller -n flux-system
kubectl rollout status deployment/source-controller -n flux-system --timeout=180s

kubectl rollout restart deployment/kustomize-controller -n flux-system
kubectl rollout status deployment/kustomize-controller -n flux-system --timeout=180s
```

`rollout restart` requests a replacement Pod. `rollout status` waits for the
replacement to become ready. Run the next stage after each rollout succeeds.

Then repeat the Flux reconciliation checks above. If the errors continue,
collect fresh controller logs and K3s service logs before choosing another fix.

```bash
ssh -i "$HOME/.ssh/pi_lab_ed25519" lab@PI_TAILSCALE_IP \
  'sudo -n journalctl -u k3s --since "20 minutes ago" --no-pager -n 80'
```

## Save the result

From the repository root on the workstation:

```bash
flux get kustomizations -A | tee docs/evidence/flux-after-restore.txt
```

Node and Deployment readiness verify Kubernetes state. Verify an inference
request and monitoring access separately before reporting application recovery.
These checks do not verify restoration of data inside application volumes.

## Recorded tests

[11 October 2026 restore results](../evidence/2026-10-11-k3s-restore.md)
record the observed failure and successful reconciliation after the restarts.

The 13 October restore stopped the K3s containers before replacing the database. The helper verified the restored marker and Ready node in 17.265 seconds. All deployments later reported Ready. The HTTP probe recorded 578 successes and 22 failures over 600 requests. One inference request returned HTTP 200 in 4.6047 seconds with the original model digest.

[Restore output](../evidence/2026-10-13-live-restore-attempt-2.txt) · [HTTP samples](../evidence/2026-10-13-live-restore-http.jsonl) · [Inference response](../evidence/ollama-after-live-restore.jsonl)

The displayed Flux source and all four Kustomizations reported Ready at commit `ef96a903`. Save matching `requestedAt` and `lastHandledReconcileAt` values using the SSH check above before reporting a confirmed manual refresh.

## References

- [K3s backup and restore](https://docs.k3s.io/datastore/backup-restore)
- [K3s service and container behavior](https://docs.k3s.io/upgrades/killall)
- [Flux troubleshooting](https://fluxcd.io/flux/cheatsheets/troubleshooting/)
