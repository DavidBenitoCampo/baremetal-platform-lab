# CLAUDE.md

## Commit conventions

Author commits as `DavidBenitoCampo <davbecam14@gmail.com>`.

Do not add `Co-Authored-By` or `Claude-Session` trailers to commit messages.

## Repository

A bare metal homelab: Talos Linux on a Raspberry Pi 5, with Kubernetes,
GitOps, and the supporting infrastructure documented as it gets built.
See [README.md](README.md) for the layout and [ROADMAP.md](ROADMAP.md) for
what's done and what's next.

Architecture decisions go in `docs/adr/` and are amended rather than
rewritten, so a reversed decision keeps both entries. Operational
procedures go in `docs/runbooks/`.

## Secrets

`talos/secrets/` and `kubeconfig` hold the cluster's PKI and admin
credentials. Both are gitignored and must never be committed. Only the
non-secret patches in `talos/patches/` belong in the repository.
