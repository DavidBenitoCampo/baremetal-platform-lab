# Checks after a K3s restore

Use this procedure after restoring K3s control-plane state on the same Pi.
The K3s service should already be running. Backup extraction belongs to a
separate restore procedure.

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

## Recorded test

[11 October 2026 restore results](../evidence/2026-10-11-k3s-restore.md)
record the observed failure and successful reconciliation after the restarts.

## References

- [K3s backup and restore](https://docs.k3s.io/datastore/backup-restore)
- [K3s service and container behavior](https://docs.k3s.io/upgrades/killall)
- [Flux troubleshooting](https://fluxcd.io/flux/cheatsheets/troubleshooting/)
