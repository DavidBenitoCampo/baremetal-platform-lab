# ADR-001: Use Kubernetes as the Orchestration Platform

- Status: Accepted
- Date: 2026-08-30

## Context

The purpose of the lab is to develop practical skills in modern infrastructure and platform engineering while retaining a strong focus on Linux, networking, storage, automation, reliability, and operations.

A container orchestrator is required to provide a realistic environment for service deployment, networking, persistent storage, observability, scheduling, and failure recovery.

## Decision

Kubernetes will be used as the primary orchestration platform.

The first implementation will be intentionally small and will initially run as a single-node cluster on a Raspberry Pi 5. Additional nodes will be introduced later.

## Reasons

- Kubernetes is widely used for platform and infrastructure engineering.
- It exposes realistic operational concerns such as scheduling, networking, storage, certificates, upgrades, and failure handling.
- It integrates well with GitOps tooling such as Flux.
- It provides a useful environment for experimenting with ARM64 and x86-64 nodes.
- The ecosystem supports the observability and storage tools planned for this lab.

## Consequences

### Positive

- Strong practical learning value.
- Large ecosystem of integrations.
- The cluster can evolve incrementally.
- Skills transfer well to managed and bare-metal Kubernetes environments.

### Negative

- Kubernetes introduces substantial complexity.
- A single-node cluster is not highly available.
- Some applications may not publish ARM64 images.
- The platform requires disciplined documentation to avoid becoming an unmaintainable collection of YAML.

## Alternatives Considered

### Docker Compose

Simpler and suitable for a single machine, but it does not expose the orchestration, scheduling, and platform concepts targeted by this project.

### Nomad

A capable and simpler orchestrator, but Kubernetes is a better fit for the learning and portfolio objectives of this project.
