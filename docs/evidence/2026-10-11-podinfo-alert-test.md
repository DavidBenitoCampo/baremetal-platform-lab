# Podinfo availability alert test

Date: 2026-10-11  
Cluster: pi-lab  
Timestamp timezone: UTC

## Goal

Verify that Prometheus detects a complete Podinfo outage, moves the alert through pending and firing states, and returns the alert to inactive after recovery.

## Test conditions

- Podinfo normally runs with two replicas.
- Flux manages the Podinfo manifests.
- Prometheus scrape interval: 30 seconds.
- Prometheus evaluation interval: 30 seconds.
- Alert hold time: 1 minute.
- HTTP probe interval: 1 second.
- HTTP probe attempts: 240.
- HTTP timeout: 0.8 seconds.
- This is a single-node Raspberry Pi lab.

## Alert rule

The `PodinfoUnavailable` alert checks:

```promql
kube_deployment_status_replicas_available{
  namespace="platform-demo",
  deployment="podinfo"
} == 0
