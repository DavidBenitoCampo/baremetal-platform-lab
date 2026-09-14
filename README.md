# Bare Metal Platform Lab

A modular bare-metal homelab built to learn and demonstrate Kubernetes, GitOps, networking, observability, storage, automation, and infrastructure operations on real hardware.

The project starts with a single Raspberry Pi 5 and evolves incrementally into a multi-node ARM64/x86 Kubernetes platform mounted in a custom 3D-printed 10-inch rack.

## Goals

- Build a reproducible bare-metal Kubernetes platform.
- Treat infrastructure configuration as code.
- Use GitOps as the primary deployment workflow.
- Design realistic network segmentation and service exposure.
- Add observability, persistent storage, backups, and recovery procedures.
- Document architecture decisions and operational runbooks.
- Design and 3D-print a modular rack for the physical infrastructure.

## Target Architecture

```text
                         Internet
                            |
                     +------+------+
                     | Router / FW |
                     |   OPNsense  |
                     +------+------+
                            |
                       VLAN trunk
                            |
                     +------+------+
                     | Managed 2.5G|
                     |    Switch   |
                     +--+---+---+--+
                        |   |   |
             +----------+   |   +-----------+
             |              |               |
        +----+----+     +---+----+      +---+---+
        | Pi 5    |     | x86    |      |  NAS  |
        | ARM64   |     | Worker |      |Storage|
        +----+----+     +---+----+      +-------+
             |
          Talos
             |
        Kubernetes
             |
           Flux
             |
          GitHub
```

## Initial Hardware

- Raspberry Pi 5, 8 GB
- External USB SSD (boot/install media for the Pi 5)
- 10-inch modular 3D-printed rack
- Managed switch (planned)
- OPNsense firewall appliance (planned)
- Additional ARM64/x86 Kubernetes workers (future)
- NAS / shared storage (future)

## Technology Stack

| Layer | Technology |
|---|---|
| Node OS | Talos Linux |
| Orchestration | Kubernetes |
| GitOps | Flux CD |
| Package management | Helm |
| Load balancing | MetalLB |
| Ingress | Traefik or ingress-nginx |
| TLS | cert-manager |
| Metrics | Prometheus |
| Dashboards | Grafana |
| Logs | Loki |
| Alerting | Alertmanager |
| Firewall / Routing | OPNsense |
| Rack | Custom 10-inch 3D-printed modular rack |

## Repository Layout

```text
.
├── clusters/              # Cluster-specific GitOps configuration
├── docs/
│   ├── adr/               # Architecture Decision Records
│   ├── architecture/      # Platform architecture documentation
│   └── runbooks/          # Operational procedures
├── hardware/
│   └── rack/              # CAD, STL, drawings and BOM
├── kubernetes/
│   ├── apps/              # Workloads
│   └── infrastructure/    # Platform services
├── scripts/               # Helper tooling
├── talos/                 # Talos configuration and patches
└── .github/workflows/     # CI validation
```

## Roadmap

See [ROADMAP.md](ROADMAP.md).

## Architecture Decisions

- [ADR-001: Use Kubernetes as the orchestration platform](docs/adr/0001-use-kubernetes.md)
- [ADR-002: Use Talos Linux for Kubernetes nodes](docs/adr/0002-use-talos-linux.md)

## Current Status

**Milestone 1 — Single-node Kubernetes: complete (2026-09-13)**

A single-node cluster runs on the Raspberry Pi 5: Kubernetes v1.37.0 on
Talos v1.14.0 (arm64), booting from microSD with `/var` and etcd on an
external USB SSD. Rebuildable from [the runbook](docs/runbooks/bootstrap-talos.md)
and the patches in [`talos/patches/`](talos/patches/).

Milestone 2 is underway: Flux CD v2.9.5 is bootstrapped and reconciling
[`clusters/homelab/`](clusters/homelab/) from this repository. Next is
deploying an application through Git alone.

## Principles

1. Reproducibility over manual configuration.
2. Small, understandable changes over large one-off deployments.
3. Git is the source of truth wherever practical.
4. Document decisions, not only implementation.
5. Design for incremental growth instead of premature high availability.
6. Prefer operational learning over unnecessary complexity.

## License

This project is intended as a personal infrastructure and learning lab. A formal open-source license can be added once the project reaches its first stable milestone.
