# Monitoring verification

Date: 2026-10-09
Host: pi-lab
Kubernetes: K3s v1.36.5

Prometheus and kube-state-metrics were deployed through Flux.

## Available replicas

| Deployment | Namespace | Available replicas |
| --- | --- | ---: |
| ollama | ai-lab | 1 |
| podinfo | platform-demo | 2 |
| prometheus | monitoring | 1 |
| kube-state-metrics | monitoring | 1 |

## Scrape targets

The Prometheus query `up` returned three targets, all with value `1`:

- Prometheus
- kube-state-metrics metrics
- kube-state-metrics self metrics

## Exporter errors

The query `kube_state_metrics_list_total{result="error"}` returned no data.

No Kubernetes API read errors appeared.

## Ollama restarts

The query `kube_pod_container_status_restarts_total{namespace="ai-lab",container="ollama"}` returned `1`.

This value is cumulative. The restart matches the earlier Pi reboot history.

## Limits

This check confirms metric collection and workload state. It does not measure high availability, inference latency, node failure recovery, or independent monitoring.
