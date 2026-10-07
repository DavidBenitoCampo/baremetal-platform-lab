# GitOps configuration planned

Week 6 adds Flux bootstrap under flux-system/ and separate infrastructure and
application Kustomizations. Use source-controller and kustomize-controller.
Apply dependencies and a scoped service account for application reconciliation.

Bootstrap through a temporary privately entered GitHub token.
Ongoing Git access uses a read only deploy key.
CI has no kubeconfig and no network connection to the Pi.
