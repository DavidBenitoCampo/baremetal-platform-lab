# Flux bootstrap evidence

Date: 2026-10-08
Cluster: pi-lab
Repository: DavidBenitoCampo/baremetal-platform-lab

## Observed bootstrap

- Flux version: v2.9.6.
- Controllers: source-controller, kustomize-controller, helm-controller, and notification-controller.
- Controller Pods: Running after bootstrap.
- GitHub bootstrap commit: `71013bc5afa7cb2c57b4bba342a5be165407c30f`.
- Bootstrap commit message: `Add Flux sync manifests`.
- CI result for the bootstrap commit: passed.
- Git source URL: `ssh://git@github.com/DavidBenitoCampo/baremetal-platform-lab`.
- Sync path: `./clusters/pi` on branch `main`.
- Git authentication: Flux-created read-only GitHub deploy key.

Bootstrap first installed controller manifests, then created the GitRepository and
root Flux Kustomization. The initial token lacked write access for GitHub
Administration, which prevented deploy-key setup. A replacement fine-grained
token with the required permission completed bootstrap. Remove the first token
from GitHub after verifying the deploy key exists and Flux remains Ready.

## Application reconciliation

Pending after `clusters/pi/apps.yaml` is committed:

- Podinfo Kustomization Ready state.
- Ollama Kustomization Ready state.
- Git commit reconciliation evidence.
- Manual scale drift correction evidence.

## Limits

Flux runs on the same Pi as the applications. A host, power, USB SSD, or network
failure stops the controllers and workloads together. This test shows desired-state
reconciliation after the Pi is running. It does not test host recovery or backup
restore.
