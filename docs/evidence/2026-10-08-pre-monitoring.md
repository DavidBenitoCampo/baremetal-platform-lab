# Before installing monitoring

Date: 2026-10-08, Europe/Prague

I checked resource use after adding Flux and before deploying Prometheus.

Commands:

```bash
kubectl top nodes
kubectl top pods -A
kubectl get deployments,statefulsets -A
```

## Node snapshot

| Measurement | Observed value |
| --- | --- |
| Node | pi-lab |
| CPU | 114m, 2% |
| Memory | 1660Mi, 20% |

## Pod snapshots

| Namespace | Container workload | CPU | Memory |
| --- | --- | --- | --- |
| ai-lab | ollama | 1m | 58Mi |
| flux-system | helm-controller | 1m | 14Mi |
| flux-system | kustomize-controller | 1m | 38Mi |
| flux-system | notification-controller | 1m | 22Mi |
| flux-system | source-controller | 2m | 28Mi |
| kube-system | coredns | 3m | 69Mi |
| kube-system | local-path-provisioner | 1m | 45Mi |
| kube-system | metrics-server | 10m | 76Mi |
| kube-system | svclb-traefik | 0m | 2Mi |
| kube-system | traefik | 1m | 118Mi |
| platform-demo | podinfo replica 1 | 1m | 13Mi |
| platform-demo | podinfo replica 2 | 1m | 25Mi |

All listed Deployments had their requested replicas ready. Podinfo had two,
and the other Deployments had one each. The output listed no StatefulSets or
deployed Prometheus or Grafana workloads.

The node reading includes more than the sum of Pod memory. This snapshot does
not measure peak usage during inference or establish whether a model was
loaded at the time. Monitoring overhead has not been measured yet.
