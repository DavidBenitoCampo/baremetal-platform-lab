# Validation workflow planned

Week 5 adds a pull_request workflow rendering Kustomize and validating standard
Kubernetes schemas with a pinned validator. Handle Flux CRD schemas separately.
Pin actions to reviewed commit SHAs, set contents:read permissions, and use short
timeouts. No Pi credentials belong in CI.

Retain one passing configuration check and one deliberate invalid field failure.
