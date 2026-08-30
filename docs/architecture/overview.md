# Architecture Overview

## Purpose

Bare Metal Platform Lab is an incremental homelab platform designed to explore the operational concerns behind modern Kubernetes platforms on physical infrastructure.

The project deliberately begins with one Raspberry Pi 5 rather than attempting high availability immediately. Each new capability is introduced only when the previous layer is reproducible and understood.

## Evolution

### Stage 1

```text
Raspberry Pi 5
      |
    Talos
      |
 Kubernetes
```

### Stage 2

```text
GitHub
   |
  Flux
   |
Kubernetes
```

### Stage 3

```text
Internet
   |
OPNsense
   |
Managed Switch
   |
   +-- Raspberry Pi 5
   +-- x86 worker
   +-- x86 worker
   +-- NAS
```

## Logical Networks

Planned segmentation:

| VLAN | CIDR | Purpose |
|---|---|---|
| 10 | 10.10.10.0/24 | Management |
| 20 | 10.10.20.0/24 | Kubernetes nodes |
| 30 | 10.10.30.0/24 | Storage |
| 40 | 10.10.40.0/24 | Services / LoadBalancer addresses |

These networks are design targets and will be introduced gradually.

## Design Principles

### Declarative infrastructure

Nodes and workloads should be reproducible from version-controlled configuration wherever possible.

### GitOps

Once Flux is introduced, application and platform changes should flow through Git rather than manual `kubectl apply` operations.

### Mixed architecture

The project may combine ARM64 Raspberry Pi nodes with x86-64 mini PCs. Workload compatibility and scheduling behavior will be documented explicitly.

### Modular hardware

The physical rack is device-independent. Devices mount through replaceable trays so individual components can change without redesigning the entire rack.

### Failure as a feature

The lab is intended not only to deploy workloads but also to deliberately break and recover them.
