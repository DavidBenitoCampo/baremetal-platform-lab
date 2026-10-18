# Flux operations

## Purpose

Flux makes Git the desired state for this single-node Pi cluster. The `flux-system`
source reads the `main` branch every minute. The `podinfo` and `ollama`
Kustomizations apply the two application paths and report deployment health.

## Routine checks

Run these commands from the workstation after exporting the Pi kubeconfig:

```bash
flux check
flux get sources git -A
flux get kustomizations -A
kubectl get pods -n flux-system
```

Expected state: four Flux controller Pods are Running, the Git source is Ready,
and `flux-system`, `podinfo`, and `ollama` are Ready.

## Reconcile after a Git change

Flux polls every minute. Use these commands when you need a result immediately:

```bash
flux reconcile source git flux-system -n flux-system
flux reconcile kustomization flux-system -n flux-system --with-source
flux reconcile kustomization podinfo -n flux-system --with-source
flux reconcile kustomization ollama -n flux-system --with-source
flux get kustomizations -A
```

The first command fetches Git. The remaining commands apply the cluster folder,
then each application path. Record the commit SHA, command start time, Ready
time, and any failure message in the evidence record.

## Drift correction exercise

This exercise proves that Flux restores the desired Podinfo replica count from
Git. The Pi overlay declares two replicas.

```bash
kubectl scale deployment/podinfo -n platform-demo --replicas=1
kubectl get deployment/podinfo -n platform-demo

flux reconcile kustomization podinfo -n flux-system --with-source
kubectl rollout status deployment/podinfo -n platform-demo --timeout=180s
kubectl get deployment/podinfo -n platform-demo
flux get kustomizations -A
```

Expected result: the deployment first shows one desired replica. Flux restores
the declared replica count of two. The Podinfo Kustomization returns Ready.
Record the observed times. One Pi does not provide host-level availability.

## Failed release and Git recovery

The [18 October exercise](../incidents/2026-10-18-podinfo-failed-release.md)
records a readiness probe set to unused port 9990 through Git. The new Pod
stayed unready, the Deployment reported `ProgressDeadlineExceeded`, and
Flux reported a failed health check. Restoring the working readiness port
in Git returned the Deployment and Flux to a healthy state.

The first HTTP capture recorded 1,800 successful requests. The recovery
capture recorded 1,194 successful requests and six timeouts after the
Deployment had recovered. The timeout cause is unconfirmed. The report
also records the gap between the two captures.

For another exercise, use the [workstation helpers](workstation-access.md)
to select the Pi kubeconfig. Keep one HTTP capture running from before the
fault merge until after recovery. Verify fresh timestamps and increasing
sample indices before each merge.

Save the Kustomization JSON when reconciliation fails. Compare
`lastAppliedRevision` with `lastAttemptedRevision`. The revision column in
`flux get kustomization` shows the last successful revision during this
failed health check.

## Troubleshooting

```bash
flux get all -A
flux logs -n flux-system --all-containers --since=10m
kubectl describe kustomization podinfo -n flux-system
kubectl describe kustomization ollama -n flux-system
```

Start with the Ready condition and message. Check the Git source before changing
the application manifests. Do not edit generated files under `clusters/pi/flux-system/`.
