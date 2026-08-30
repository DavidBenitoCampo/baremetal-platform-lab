# ADR-002: Use Talos Linux for Kubernetes Nodes

- Status: Accepted
- Date: 2026-08-30

## Context

The Kubernetes nodes require an operating system. A conventional Ubuntu-based installation would be familiar and flexible, but would also introduce manual OS administration that is not central to the goals of this project.

The lab should encourage reproducibility, immutability, and infrastructure-as-code practices.

## Decision

Talos Linux will be used as the operating system for Kubernetes nodes where hardware support permits it.

The Raspberry Pi 5 will be the first target.

## Reasons

- Talos is designed specifically for Kubernetes.
- Node configuration is API-driven and declarative.
- The operating system is minimal and immutable.
- There is no SSH-based administration model.
- Configuration can be version-controlled and recreated.
- It encourages replacement/reconciliation rather than manual server repair.

## Consequences

### Positive

- Reduced configuration drift.
- Clear separation between node configuration and workloads.
- Strong alignment with declarative infrastructure principles.
- Rebuilding a node becomes a core operational workflow.

### Negative

- Less familiar than Ubuntu.
- Traditional SSH troubleshooting is unavailable.
- Hardware compatibility must be checked carefully.
- Raspberry Pi bootstrapping requires additional platform-specific work.

## Alternatives Considered

### Ubuntu + kubeadm

Very flexible and familiar, but increases host-level configuration and maintenance. It remains a useful fallback for unsupported hardware.

### NixOS

Provides excellent declarative host configuration and is valuable for general-purpose infrastructure, but Talos is more narrowly optimized for Kubernetes and better supports the desired immutable-node operating model.

## Revisit Conditions

This decision should be revisited if:

- Talos does not support required hardware reliably.
- A future node must run non-Kubernetes workloads.
- The project expands into host-level configuration experiments where NixOS provides greater learning value.
