# Prometheus first install

This adds two workloads to the Pi:

- Prometheus reads and stores measurements every 30 seconds.
- kube-state-metrics reads Kubernetes objects and reports Pod readiness,
  container restarts, Deployment replicas, and PVC status.

The first useful check is whether Ollama has an available replica. A ready Pod
does not prove a model produces a correct answer or accepts an inference request.

Grafana, alerts, node metrics, container CPU history, and inference latency
collection come after this installation works. `kubectl top` still provides
current CPU and memory readings through the existing metrics-server.

## Files

| File | Purpose |
| --- | --- |
| `kustomization.yaml` | Assembles the Kubernetes resources and configuration. |
| `prometheus.yml` | Lists the three scrape targets and the scrape interval. |
| `prometheus.yaml` | Runs one Prometheus Pod and its internal Service. |
| `kube-state-metrics.yaml` | Runs the exporter and its internal Service. |
| `rbac.yaml` | Grants read access to the selected object types in three namespaces. |
| `pvc.yaml` | Requests SSD-backed storage for measurements. |
| `networkpolicy.yaml` | Restricts incoming Pod traffic to the metrics services. |
| `namespace.yaml` | Creates the monitoring namespace with restricted Pod security. |
| `../../clusters/pi/monitoring.yaml` | Tells Flux where to find these resources. |

## Resource settings

| Workload | CPU request | CPU limit | Memory request | Memory limit |
| --- | --- | --- | --- | --- |
| Prometheus | 100m | 500m | 256Mi | 512Mi |
| kube-state-metrics | 50m | 500m | 128Mi | 256Mi |
| Total | 150m | 1000m | 384Mi | 768Mi |

These are starting settings, not observed usage. The totals cover steady state.
An exporter rolling update temporarily permits a second exporter Pod. The limits
apply to the containers, not the entire host. Check usage again during inference,
after the model loads into memory.

Prometheus requests a 5Gi PVC. Retention is seven days or 4GB, whichever removes
old samples first. `local-path` uses a directory on the same USB SSD. The PVC
request is not a filesystem quota. WAL files and compaction also need room.

Use one Prometheus writer. The Deployment uses `Recreate`, so configuration
updates briefly stop collection. Kustomize generates a new configuration name
when `prometheus.yml` changes, which triggers a Deployment update through Flux.

## Access and permissions

Both Services use `ClusterIP`. There is no Ingress, NodePort, or host port.
Use a loopback port-forward from your workstation to open Prometheus.

Prometheus has no Kubernetes API token. Its scrape targets are fixed Service
addresses. kube-state-metrics has a read-only ServiceAccount, limited through
RoleBindings to `ai-lab`, `platform-demo`, and `monitoring`. Its allowed resources
are Pods, Deployments, and PVCs. It has no Secret access or write permissions.

The containers use numeric non-root users, a read-only root filesystem,
RuntimeDefault seccomp, dropped capabilities, and no privilege escalation.
NetworkPolicies allow Prometheus to read the exporter and reserve access to
Prometheus for a future Grafana Pod in the same namespace. Egress is unchanged.
NetworkPolicy enforcement depends on the cluster network-policy controller.

The monitoring namespace and PVC have Flux prune protection. Removing their
manifests does not automatically delete them. Explicitly deleting the namespace
still deletes its PVC, and the `local-path` reclaim policy is `Delete`.

## Before deployment

Run commands from the repository root. The namespaces `ai-lab` and
`platform-demo` must already exist for the RoleBindings.

Render the configuration without deploying:

```bash
kubectl kustomize monitoring/prometheus > /tmp/pi-monitoring.yaml
```

Add this render path to the existing CI schema-validation step before merging.
Use the same pinned Kubernetes schema and validator as the existing app checks.
The generated ConfigMap needs a separate Prometheus configuration check.

With Docker already installed on your workstation, run:

```bash
docker run --rm --read-only --entrypoint=/bin/promtool \
  -v "$PWD/monitoring/prometheus:/work:ro" \
  ghcr.io/prometheus/prometheus:v3.15.0-distroless \
  check config /work/prometheus.yml
```

Podman supports the same invocation. If using an installed `promtool`, match
the server version before running `promtool check config`.

## Deploy through Flux

`clusters/pi/monitoring.yaml` adds a separate Flux Kustomization. Monitoring has
no dependency on healthy application Deployments, so a failed app rollout does
not block a monitoring configuration update.

If `clusters/pi/kustomization.yaml` exists with an explicit resource list, add
`monitoring.yaml` to that list. If Flux generates the root Kustomization from
the directory, the new file is included automatically.

Once the new configuration passes CI and reaches `main`, run:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"
flux reconcile kustomization flux-system -n flux-system --with-source
flux get kustomizations -A
```

Check that a Flux Kustomization named `monitoring` now exists. Then run:

```bash
flux reconcile kustomization monitoring -n flux-system --with-source
kubectl get deployment,pods,pvc,service -n monitoring
```

Expected: both Deployments have one ready replica, and `prometheus-data` is
Bound. Image downloads and local storage provisioning take additional time.

## Read the first measurements

Keep this command running in one workstation terminal:

```bash
kubectl port-forward -n monitoring service/prometheus 19090:9090 \
  --address=127.0.0.1
```

Open `http://127.0.0.1:19090`. Wait for at least two 30-second scrapes. Run `up`
in the query page. The expected result is three targets with value `1`.

Then query the available Ollama replicas:

```promql
kube_deployment_status_replicas_available{namespace="ai-lab",deployment="ollama"}
```

Expected: `1`, provided Ollama still has one healthy replica. An empty result
is different from zero. Check the scrape target and exporter permissions.

To view the recorded restart count:

```promql
kube_pod_container_status_restarts_total{namespace="ai-lab",container="ollama"}
```

To check the exporter's Kubernetes API list errors:

```promql
kube_state_metrics_list_total{result="error"}
```

Expected: no positive error counters. Retain the actual query output and logs.

## Completion checks

- Flux reports `monitoring` Ready at the intended commit.
- Both monitoring Pods are Ready, and the PVC is Bound.
- `up` returns three targets with value `1`.
- Ollama available replicas appear with the expected value.
- The exporter logs show no forbidden list or watch errors.
- CPU and memory snapshots have been recorded after installation.
- Monitoring CPU and memory have also been sampled during a repeat inference.
- The existing Ollama inference probe still succeeds.

This package has not been deployed on the Pi yet. Record observed results after
these checks, including failures. Monitoring shares the application's node and
SSD, so host failure stops both. This installation does not add an independent
observer or an off-host backup.

## Troubleshooting

For a pending Pod, inspect `kubectl describe pods -n monitoring` and namespace
events. For a failed container, read its Deployment logs.

If Prometheus reports permission errors under `/prometheus`, inspect volume
ownership and fsGroup handling. Keep the non-root security settings while
diagnosing the storage issue.

If the exporter reports forbidden API calls, compare its `--resources` and
`--namespaces` with the RoleBindings. Do not replace the read-only role with
cluster-admin.

If Pods restart with `OOMKilled`, record their last state and recent usage.
Increase only the affected workload's budget after reviewing host memory under
inference load. For an invalid configuration, correct Git and reconcile Flux.

## Sources

Official references checked on 2026-10-08:

- [Prometheus release 3.15.0](https://github.com/prometheus/prometheus/releases/tag/v3.15.0).
- [Prometheus image variants and architectures](https://github.com/prometheus/prometheus/pkgs/container/prometheus).
- [Prometheus local storage and retention](https://prometheus.io/docs/prometheus/latest/storage/).
- [kube-state-metrics images and Kubernetes compatibility](https://github.com/kubernetes/kube-state-metrics).
- [kube-state-metrics health probes](https://github.com/kubernetes/kube-state-metrics/blob/main/examples/standard/deployment.yaml).
- [kube-state-metrics command arguments](https://github.com/kubernetes/kube-state-metrics/blob/main/docs/developer/cli-arguments.md).

The published images include ARM64. kube-state-metrics 2.20.0 uses the
Kubernetes 1.36 client. Successful runtime checks on the Pi are still required.
