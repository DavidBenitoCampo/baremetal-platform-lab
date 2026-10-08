# Flux drift correction

Date: 2026-10-08, Europe/Prague

## What I tested

I changed Podinfo from two replicas to one directly through Kubernetes, leaving
the configuration in Git unchanged. The Deployment later returned to two ready
replicas, matching the Git configuration.

The goal was to check whether Flux corrects a manual change to a workload under
GitOps management.

## Starting point

- Node: `pi-lab`, Ready.
- Kubernetes: K3s `v1.36.5+k3s1`.
- Application: `podinfo`, namespace `platform-demo`.
- Desired replica count in Git: two.
- Flux Kustomizations: `flux-system`, `podinfo`, and `ollama`, all Ready and not suspended.
- Revision reported before the test: `main@sha1:839dd339`.

The initial Deployment check showed:

```text
NAME      READY   UP-TO-DATE   AVAILABLE   AGE
podinfo   2/2     2            2           29h
```

## Manual change

I reduced the running Deployment to one replica:

```bash
kubectl scale deployment podinfo -n platform-demo --replicas=1
kubectl get deployment podinfo -n platform-demo
```

Observed output:

```text
deployment.apps/podinfo scaled

NAME      READY   UP-TO-DATE   AVAILABLE   AGE
podinfo   1/1     1            1           29h
```

This created a difference between the live Deployment and the configuration
in Git. The Git configuration still requested two replicas.

## Reconciliation and result

The reconciliation step in the test procedure was:

```bash
flux reconcile kustomization podinfo -n flux-system --with-source
kubectl get deployment podinfo -n platform-demo
```

The final Deployment output showed:

```text
NAME      READY   UP-TO-DATE   AVAILABLE
podinfo   2/2     2            2
```

The replica count returned to two, with both replicas ready and available.
The Flux command output was not retained in this record. Flux also reconciles
on a schedule, so these snapshots do not distinguish the scheduled check from
the manual reconciliation request.

## Measurements

| Check | Observed result |
| --- | --- |
| Starting ready replicas | 2 |
| Ready replicas after manual scaling | 1 |
| Final ready replicas | 2 |
| Detection delay | Not measured |
| Correction time | Not measured |
| HTTP failures during the test | Not measured |

No continuous HTTP probe output was retained for this test. The replica counts
alone do not establish uninterrupted service.

## What I learned

Flux keeps the running configuration aligned with Git. A direct change through
`kubectl` is temporary when Flux manages the same field.

For a permanent replica change, I need to edit the repository configuration,
commit the change, and push to the branch Flux follows.

This test covers replica-count drift. Host failure, storage recovery, and
backup restore require separate tests.
