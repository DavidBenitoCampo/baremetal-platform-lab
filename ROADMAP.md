# Roadmap

## Milestone 0 — Repository Foundation

Goal: establish the project structure, architecture documentation, and decision record process.

- [x] Define repository structure
- [x] Write project README
- [x] Write architecture overview
- [x] Create roadmap
- [x] ADR-001: Kubernetes
- [x] ADR-002: Talos Linux
- [ ] Create GitHub repository
- [ ] Push initial commit

## Milestone 1 — Single-Node Kubernetes

Goal: run Kubernetes reproducibly on the Raspberry Pi 5, using the `rpi_5`
Image Factory overlay (see ADR-002).

- [x] Boot Raspberry Pi 5 for Talos (microSD as boot disk — U-Boot can't read USB)
- [x] Attach external USB SSD as the `EPHEMERAL` volume (/var, etcd, images)
- [x] Generate Talos machine configuration
- [x] Bootstrap Kubernetes
- [x] Configure remote `talosctl`
- [x] Configure remote `kubectl`
- [x] Validate node health
- [x] Document bootstrap procedure
- [x] Create recovery notes

Exit criteria: a working single-node Kubernetes cluster that can be rebuilt from documented configuration. **Met 2026-09-13** — node `Ready`, Kubernetes v1.37.0 on Talos v1.14.0 (arm64).

No control-plane taint was applied, so workloads schedule on the node
without further work.

## Milestone 2 — GitOps

Goal: make Git the deployment source of truth.

- [x] Bootstrap Flux CD (v2.9.5, reconciling `clusters/homelab`)
- [ ] Define cluster reconciliation structure
- [ ] Deploy a test application through Git only
- [ ] Add HelmRepository / HelmRelease examples
- [ ] Add basic manifest validation in GitHub Actions

Exit criteria: workloads are deployed and changed through GitOps.

Image automation is out of scope here. Bootstrap installed four
controllers and no `image.toolkit.fluxcd.io` CRDs, so `ImagePolicy` and
`ImageUpdateAutomation` need a re-bootstrap with `--components-extra` and
a writable deploy key.

## Milestone 3 — Networking

- [ ] Select managed 2.5 GbE switch
- [ ] Deploy OPNsense router/firewall
- [ ] Define VLAN 10 - Management
- [ ] Define VLAN 20 - Kubernetes
- [ ] Define VLAN 30 - Storage
- [ ] Define VLAN 40 - Services
- [ ] Configure firewall policy
- [ ] Deploy MetalLB
- [ ] Deploy ingress controller
- [ ] Add internal DNS design

## Milestone 4 — Observability

- [ ] kube-prometheus-stack
- [ ] Grafana
- [ ] Loki
- [ ] Alertmanager
- [ ] Node / cluster dashboards
- [ ] Router / switch monitoring
- [ ] Raspberry Pi temperature monitoring
- [ ] Alert runbooks

## Milestone 5 — Storage

- [ ] Select NAS/storage platform
- [ ] Create dedicated storage network
- [ ] Test NFS
- [ ] Evaluate iSCSI
- [ ] Deploy Kubernetes CSI integration
- [ ] Define backup policy

## Milestone 6 — Multi-Node

- [ ] Add worker node 02
- [ ] Add worker node 03
- [ ] Support ARM64 and x86-64 workloads
- [ ] Define labels / taints / affinities
- [ ] Test node loss
- [ ] Document scheduling constraints

## Milestone 7 — Reliability

- [ ] Backup Kubernetes state/configuration
- [ ] Backup persistent workloads
- [ ] Simulate worker failure
- [ ] Rebuild failed node
- [ ] Restore application from backup
- [ ] Document RTO/RPO assumptions
- [ ] Write disaster recovery runbook

## Milestone 8 — Physical Rack

- [ ] Freeze 10-inch rack dimensions
- [ ] Design rack rails/frame
- [ ] Design Raspberry Pi tray
- [ ] Design switch tray
- [ ] Design firewall tray
- [ ] Design cable-management modules
- [ ] Add ventilation
- [ ] Publish STEP/STL files
- [ ] Write assembly guide and BOM

## Milestone 9 — Portfolio Release v1.0

- [ ] Architecture diagrams
- [ ] Final hardware photographs
- [ ] CI status badges
- [ ] Complete ADR index
- [ ] Complete runbooks
- [ ] Failure/recovery demo
- [ ] Clean README
- [ ] Tag `v1.0.0`
