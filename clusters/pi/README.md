# Flux configuration for pi-lab

Flux watches the `main` branch of this repository and reconciles `clusters/pi`.
The generated `flux-system/` directory installs Flux and defines its Git source.

`apps.yaml` defines two application reconciliations:

- `podinfo` renders `kubernetes/overlays/pi`.
- `ollama` renders `kubernetes/ai/ollama`.

Both reconcile once per minute, prune resources removed from their declared path,
and wait for the named Deployment to become healthy. Flux runs with the cluster
permissions created during bootstrap. This is appropriate for one administrator
and one lab cluster. A shared production cluster would use scoped identities and
separate repositories or paths.

Use `flux get kustomizations -A` to inspect reconciliation state. See
`docs/runbooks/flux.md` for normal checks and the drift exercise.
