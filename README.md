# baremetal-platform-lab

I'm building an AI homelab on a Raspberry Pi 5. Ollama serves a small language model, K3s runs the workloads, and Flux keeps the cluster in sync with this repository.

My focus is operating the service: making repeatable changes, watching resource use, keeping model files across restarts, and recovering after a failure. I started with Podinfo to test Kubernetes releases before adding inference. Both applications still run in the lab.

## Current setup

| Component | Running setup |
| --- | --- |
| Host | Ubuntu Server 24.04.5 LTS, ARM64 |
| Kubernetes | K3s `v1.36.5+k3s1`, one server with SQLite |
| Host automation | Ansible |
| Test application | Podinfo 6.15.0, two replicas in `platform-demo` |
| Inference server | Ollama 0.40.0, one replica in `ai-lab` |
| Model | `qwen2.5:0.5b`, CPU inference, about 397 MB in the model list |
| GitOps | Flux 2.9.6, following `main` |
| Metrics | Prometheus 3.15.0 and kube-state-metrics 2.20.0 |
| Dashboard | Grafana 13.2.2, provisioned from repository files |
| Remote access | Tailscale with regular SSH and SSH tunnels |
| Validation | GitHub Actions checks configuration, manifests, scripts, and JSONL evidence |
| Backup | Encrypted K3s archive on a separate workstation disk |

The hardware is a Raspberry Pi 5 with 8 GB RAM, active cooling, and an ADATA SU650 512 GB SATA SSD connected through USB. Ubuntu boots from the SSD. The root filesystem is `/dev/sda2`, formatted as ext4.

All persistent volumes use `local-path` storage on the same SSD:

| Claim | Namespace | Requested size |
| --- | --- | ---: |
| `ollama-cache` | `ai-lab` | 20 GiB |
| `prometheus-data` | `monitoring` | 5 GiB |
| `grafana-data` | `monitoring` | 2 GiB |

A spare 512 GB microSD card is available, but the running cluster does not use the card. The lab has no dedicated inference GPU. There is no agent deployed yet.

## What I've tested

### Host setup and releases

The first Ansible run reported 23 successful tasks, nine changes, and no failures. The second reported 22 successful tasks and zero changes. After rebooting the Pi, K3s returned to `active` and the node returned to `Ready`.

For Podinfo, I tested a rolling update from 6.14.1 to 6.15.0, then deliberately broke the readiness path. The new Pod stayed unready while two previous Pods stayed Ready. Kubernetes reported `ProgressDeadlineExceeded`, and an Ingress check still returned HTTP 200.

I restored the working manifest from Git and applied the change. This happened before Flux was installed. I also deleted a Pod and checked its replacement.

These earlier release checks used individual HTTP requests.

[Cluster and release evidence](docs/evidence/2026-10-07-initial-cluster.md)

On 18 October, I tested a failed readiness release through Git and Flux. The
failed snapshot showed one new Pod unready and two previous Pods Ready.
Flux reported a failed Deployment health check. Restoring the working
readiness port in Git returned the Deployment and Flux to a healthy state.

The first HTTP capture recorded 1,800 HTTP 200 responses with no failures.
The recovery capture recorded 1,194 HTTP 200 responses and six consecutive
timeouts. The recorded timestamps place those timeouts about three minutes
after the Deployment recovered. Their cause is still unknown. The two logs
have 40.635 seconds between their boundary sample starts.

[Failed release and Git recovery evidence](docs/incidents/2026-10-18-podinfo-failed-release.md)

I have not measured a successful version update with continuous HTTP requests.

### Inference and model persistence

The inference probe records the response, model digest, request settings, and timings as JSONL. The tests used one short prompt, a 2,048-token context, a 64-token output limit, and two CPU threads. Requests ran sequentially with streaming disabled, temperature `0`, seed `7`, and a five-minute model keep-alive.

| Request | Model already loaded | Complete response time | Generated tokens |
| --- | --- | ---: | ---: |
| First request | No | 4.4195 s | 27 |
| Follow-up request | Yes | 1.7685 s | 37 |
| Next follow-up | Yes | 1.7113 s | 37 |
| After Pod replacement | No | 4.3745 s | 27 |
| After Pi reboot | No | 5.3925 s | 27 |
| Through the VPN and SSH tunnel | No | 6.1982 s | 27 |

These are individual requests with different output lengths. They don't measure concurrent throughput or time to first token. The VPN result includes the full request path and model loading.

The model files survived Pod replacement and a Pi reboot. I checked the model list and ran inference again without another download.

The first answer incorrectly described a readiness probe as checking the whole cluster. I kept the response in the evidence. HTTP success proves the request completed. Answer quality needs separate evaluation.

[Inference evidence](docs/evidence/2026-10-07-ollama.md) · [Follow-up requests](docs/evidence/ollama-followup-requests.jsonl) · [Request after reboot](docs/evidence/ollama-after-reboot.jsonl) · [Request over VPN](docs/evidence/ollama-over-vpn.jsonl)

The later resource check recorded 1.485 cores as the highest sampled CPU
reading and 620 MiB as the highest sampled memory. One cold request took
4.517 seconds, and ten warm requests had a median of 2.021 seconds.
Missing-model and socket-timeout tests recorded errors and exit code 1.
A later normal request succeeded after reopening the SSH tunnel.

[Resource and error-test results](docs/evidence/2026-10-14-ollama-resources.md)

### Flux drift correction

Git declares two Podinfo replicas. I scaled the running Deployment down to one without changing Git. After reconciliation, the Deployment returned to two Ready replicas.

The saved observations show `2/2 → 1/1 → 2/2`. Correction time and HTTP failures were not measured during this exercise.

[Drift correction evidence](docs/evidence/2026-10-8-flux-drift-correction.md)

### CI rejection of a bad manifest

I added an unsupported `replicaz` field to the Podinfo Deployment on a test branch. Kubernetes schema validation failed. Removing the field allowed the check to pass.

The [workflow](.github/workflows/validate.yml) now checks:

- YAML and Ansible syntax.
- Kustomize rendering and strict Kubernetes schemas for Podinfo, Ollama, the inference probe, and monitoring.
- Prometheus configuration and referenced alert rules with `promtool`.
- Python and shell syntax.
- Local HTTP tests for the scheduled inference probe and alert-state fixtures.
- JSONL evidence files.

CI runs without Pi credentials or a connection to the cluster. Flux custom-resource schema validation still needs adding.

### Monitoring and an outage alert

Prometheus is configured to scrape four targets every 30 seconds: Prometheus itself, kube-state-metrics, kube-state-metrics telemetry, and the Ollama inference probe. The original monitoring check recorded the first three targets with `up = 1`. The inference exercise later confirmed `up = 1` for the new probe.

The Grafana dashboard shows scrape health, available replicas, container restarts, and Bound PVCs. Its datasource and dashboard configuration live in Git.

The scheduled inference probe runs in `ai-lab` from
`kubernetes/ai/inference-probe/`. A small Python service asks `qwen2.5:0.5b`
a short question once a minute and exports the result, duration, and counters.
The additional **Ollama Inference Checks** dashboard shows those scheduled
requests. Alerts cover failed requests, an unavailable exporter, and stale
results.

On 15 October 2026, Prague time, I recorded ten successful scheduled requests.
Each returned HTTP 200 and generated 16 tokens, with durations from 1.426 to
1.877 seconds. These checks use a 16-token output limit, separate from the
earlier manual inference benchmark.

I then selected a missing model. The probe recorded HTTP 404 and
`ollama_probe_success = 0`. `OllamaInferenceCheckFailing` moved from pending
to firing after holding the condition for two minutes. Resuming Flux restored the working model.
The final checks showed successful inference, `up = 1`, and all three Ollama
alerts inactive. An earlier recovery snapshot captured the probe-unavailable
alert pending before scrape recovery was confirmed.

[Inference monitoring evidence](docs/evidence/2026-10-15-ollama-inference-monitoring.md)
and [runbook](docs/runbooks/inference-monitoring.md). Follow-up captures
include the dashboard history and a normal-operation resource snapshot from
15 October 2026. The probe reported 1m CPU and 56 MiB memory. Ollama reported
1m CPU and 678 MiB memory. These readings describe one point in normal
operation.

I tested `PodinfoUnavailable` by suspending Podinfo reconciliation and scaling the Deployment to zero. The alert moved through pending and firing. After resuming reconciliation, Podinfo returned to two replicas, HTTP requests succeeded, and the alert returned to inactive.

| Measurement | Observed result |
| --- | --- |
| Scrape and rule evaluation intervals | 30 seconds each |
| Alert hold time | 1 minute |
| First sampled firing state after the outage command | 108 seconds |
| First successful HTTP sample after recovery started | About 7.7 seconds |
| HTTP probe | 240 attempts, one per second, 0.8-second timeout |
| HTTP results | 87 responses with HTTP 200, 153 with HTTP 503 |

The alert history uses five-second query steps. The times describe sampled observations from this controlled outage, rather than exact state-transition times or production availability.

The alert exercises were observed in Prometheus. Alertmanager and notification delivery have not been added.

[HTTP samples](docs/evidence/podinfo-alert-http.jsonl) · [Alert history](docs/evidence/podinfo-alert-history.json) · [Cleared alert](docs/evidence/podinfo-alert-recovered.json) · [Final workload state](docs/evidence/podinfo-alert-final-state.txt)

### Remote access through Tailscale

Tailscale runs on the workstation and Pi. The configured access rule permits TCP port 22 from the workstation to the Pi. Login uses my existing OpenSSH key.

Grafana, Ollama, and Prometheus worked through SSH tunnels. The final Prometheus check used my phone's hotspot and returned three healthy scrape targets.

During testing, an old port-forward occupied a port on the Pi. Another attempt failed after its destination listener stopped. For Prometheus, I switched to forwarding directly to the internal Kubernetes Service IP through SSH.

I also tested workstation `kubectl` and `flux` access from outside my home network through an SSH tunnel to the Kubernetes API. The VPN kubeconfig uses local port 16443 and verifies the Pi's certificate using its LAN identity.

The [workstation access runbook](docs/runbooks/workstation-access.md) installs
a user service for the API and Podinfo HTTP tunnels. The service starts at
login and restarts SSH after a disconnect. `pi-kubectl` and `pi-flux` select
the Pi kubeconfig for each command. On 18 October, I verified installation
and automatic restart after terminating SSH. The restart counter increased
from zero to one, and the API, node, and Podinfo checks passed again.
Workstation reboot and network disconnect checks have not been recorded.

[Operator-provided access check transcript](docs/evidence/2026-10-18-workstation-access.txt)

VPN reboot persistence and denied-access tests have not been recorded.

[VPN access evidence](docs/evidence/2026-10-11-vpn-access.md) · [Prometheus result over VPN](docs/evidence/prometheus-over-vpn.json)

### K3s backup and restore

On 13 October, I restored K3s from an encrypted SQLite backup stored on my workstation. The source backup and a separate rollback archive passed SHA256 verification, full extraction, required-file checks, and SQLite `quick_check`.

I used a ConfigMap outside Flux to prove the database restore. Its state changed from `before-backup` to `after-backup` after the backup. Restoring the earlier database returned the state to `before-backup` with the original UID.

The helper stopped K3s and its containers, retained the current cluster files on the Pi, installed the backup, and restarted K3s. The node returned to Ready and all deployments recovered.

| Measurement | Observed result |
| --- | --- |
| Restore command and control-plane checks | 17.265 seconds |
| HTTP test | 600 sequential requests, one per second, 0.8-second timeout |
| HTTP results | 578 HTTP 200 responses, 20 transport errors, 2 HTTP 503 responses |
| First failed request | 2026-10-13 21:35:48.829181 UTC |
| Last failed request | 2026-10-13 21:36:09.829208 UTC |
| First success after the outage | 2026-10-13 21:36:10.829209 UTC |
| First failure to first success after the outage | About 22 seconds, sampled once per second |
| p95 HTTP attempt latency | 28.75 ms |
| Post-restore inference | HTTP 200, 4.6047 seconds, 27 generated tokens |
| Model | `qwen2.5:0.5b`, same digest as before the restore |

The HTTP probe ran on the workstation through an SSH tunnel over Tailscale to the Pi's Traefik Ingress. The 17.265-second helper measurement ends at API, node, and marker checks. The HTTP samples measure application recovery separately.

The Git source and all four Flux Kustomizations later reported Ready at `main@sha1:ef96a903ecb89386500099e1f8225f87c9577fab`. The [post-restore checks](docs/runbooks/post-restore-checks.md) include a request acknowledgement check for proving a fresh reconciliation.

The first attempt stopped at a precondition because the marker was already `before-backup`. K3s kept running. Its 900 successful requests measured service health before the live restore. The measurements above come from the second attempt, after preparing the marker.

The backup covers K3s configuration, SQLite state, the server token, credentials, encryption configuration, and TLS files. This was a restore on the same Pi and SSD. Model files, Prometheus history, Grafana data, other application volume data, and the operating system are outside the backup scope. These measurements describe one controlled lab test.

[Backup and restore runbook](docs/runbooks/backup-restore.md) · [Restore output](docs/evidence/2026-10-13-live-restore-attempt-2.txt) · [HTTP samples](docs/evidence/2026-10-13-live-restore-http.jsonl) · [Inference after restore](docs/evidence/ollama-after-live-restore.jsonl)

The [11 October restore](docs/evidence/2026-10-11-k3s-restore.md) also documents the earlier Flux cache problem and controller restart.

## How changes reach the Pi

Ansible prepares the host. Kustomize builds the manifests. Flux fetches the repository and applies the configuration.

| Flux Kustomization | Repository path |
| --- | --- |
| `flux-system` | `clusters/pi` |
| `podinfo` | `kubernetes/overlays/pi` |
| `ollama` | `kubernetes/ai/ollama` |
| `monitoring` | `monitoring/prometheus` |

For normal changes, I work on a branch, review CI, and merge into `main`. Flux then reconciles the cluster. Manual changes are temporary when Flux manages the same fields.

CI and Flux run independently. A failing Actions run does not stop Flux from applying a commit already on `main`. Required checks and branch protection need verification.

Monitoring ConfigMaps use content-based name suffixes. A configuration change updates the Deployment's ConfigMap reference and triggers a rollout. This fixed the earlier problem of Prometheus continuing to use its old configuration.

[Flux runbook](docs/runbooks/flux.md)

## Checking the lab

Run these commands on the workstation while connected to the home LAN:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"

kubectl get nodes
flux get kustomizations -A
kubectl get deployments,pvc -A
```

The LAN kubeconfig points to `10.0.1.16:6443`. Tailscale does not route the home LAN in this setup. From another network, use SSH to run the checks on the Pi:

```bash
ssh -i ~/.ssh/pi_lab_ed25519 lab@100.90.135.106 \
  'sudo -n k3s kubectl get nodes'

ssh -i ~/.ssh/pi_lab_ed25519 lab@100.90.135.106 \
  'sudo -n k3s kubectl get deployments,pvc -A'

ssh -i ~/.ssh/pi_lab_ed25519 lab@100.90.135.106 \
  'sudo -n k3s kubectl get gitrepositories,kustomizations -A'
```

For workstation access through Tailscale, install the managed tunnels once
using the [workstation access runbook](docs/runbooks/workstation-access.md).
Then run:

```bash
pi-lab-check
pi-kubectl get nodes
pi-flux get kustomizations -A
```

The service owns the tunnels independently of your terminals. The VPN
kubeconfig stays outside the repository. Use the [post-restore checks](docs/runbooks/post-restore-checks.md)
after a K3s restore.

For Podinfo on the home LAN, the workstation resolves `podinfo.lab.test` to the Pi's LAN address:

```bash
curl -i http://podinfo.lab.test/readyz
curl -s http://podinfo.lab.test/version
```

For Ollama on the home LAN, keep this command running in a separate terminal:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"
kubectl port-forward -n ai-lab service/ollama 11435:11434 --address=127.0.0.1
```

From the repository root in another terminal:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"

kubectl exec -n ai-lab deployment/ollama -- ollama list
python3 scripts/inference_probe.py --url http://127.0.0.1:11435 --count 1
```

Prometheus and Grafana also use localhost port-forwards on the home LAN. Run each command in its own terminal with the Pi kubeconfig selected:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"
kubectl port-forward -n monitoring service/prometheus 19090:9090 --address=127.0.0.1
```

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"
kubectl port-forward -n monitoring service/grafana 13000:3000 --address=127.0.0.1
```

Open [Prometheus](http://127.0.0.1:19090) or [Grafana](http://127.0.0.1:13000). Keep the relevant terminal open. Stop an existing tunnel before reusing its local port.

## Access and resource settings

SSH uses keys. The local Ansible inventory, private keys, tokens, admin kubeconfig, and backup archives stay outside Git. The admin kubeconfig grants cluster access and uses mode `600`. Grafana reads its login credentials from the local `grafana-admin` Secret.

K3s Secrets encryption is enabled. Ollama and the monitoring containers declare non-root execution, read-only root filesystems, dropped capabilities, and disabled privilege escalation. kube-state-metrics has read access to selected Kubernetes object types in `ai-lab`, `platform-demo`, and `monitoring`.

| Workload | CPU request / limit | Memory request / limit |
| --- | --- | --- |
| Ollama | 1 / 2 cores | 1 GiB / 2 GiB |
| Prometheus | 100m / 500m | 256 MiB / 512 MiB |
| kube-state-metrics | 50m / 500m | 128 MiB / 256 MiB |
| Grafana | 100m / 500m | 256 MiB / 512 MiB |
| Inference probe | 25m / 100m | 32 MiB / 64 MiB |

These values come from the manifests. They are not observed peak usage. Ollama permits one loaded model and one parallel request.

The Ollama NetworkPolicy check used two clients in `ai-lab`. The approved
probe reached `/api/version` with HTTP 200 before and after an unapproved
Pod resolved DNS and received a connection refusal. The denied Job reached
`Complete`. This exercise covers these clients and Ollama's Service port
11434. Other NetworkPolicy paths and VPN denial checks still need evidence.

Runtime images use version tags. Immutable image digest pinning and narrower
Flux reconciliation identities are future work.

## Storage and reliability limits

Everything runs on one physical node. Two Podinfo replicas demonstrate rolling updates and Pod replacement. A Pi, power, or SSD failure affects both replicas and the rest of the cluster.

Ollama, Prometheus, and Grafana use one replica with `Recreate` updates. A change interrupts the affected service. Monitoring shares the application's host, so an external check is still needed to detect loss of the whole Pi.

Local-path PVC requests do not enforce filesystem quotas. The StorageClass uses a `Delete` reclaim policy. Removing a managed namespace or PVC through Git and Flux pruning risks deleting its stored data.

The workstation backup provides an independent copy of K3s state. There is no second backup destination recorded. Model files are treated as a cache and would need downloading again after SSD loss. Monitoring history and Grafana data are outside the tested backup scope.

A production deployment would need separate failure domains, independent monitoring, backups covering required application data, tighter access controls, and compute sized for the models and traffic.

## Repository guide

- `ansible/`: host preparation and K3s settings.
- `kubernetes/base/` and `kubernetes/overlays/pi/`: Podinfo and the Pi overlay.
- `kubernetes/ai/ollama/`: inference server and model storage.
- `kubernetes/ai/inference-probe/`: scheduled model checks and their metrics.
- `clusters/pi/`: Flux bootstrap and reconciliation definitions.
- `monitoring/prometheus/`: Prometheus, kube-state-metrics, Grafana, dashboards, and alert rules.
- `.github/workflows/` and `ci/`: validation and tool configuration.
- `scripts/`: preflight, HTTP checks, inference measurements, and K3s backup, verification, and restore helpers.
- `workstation/systemd/`: the workstation managed SSH tunnel service.
- `docs/`: evidence, runbooks, decisions, and incident templates.
- `versions.yaml`: version notes, including proposed components. The deployed manifests show the running choices.

For a fresh build, start with the [bootstrap runbook](docs/runbooks/bootstrap.md), [Ollama guide](kubernetes/ai/ollama/README.md), and [Flux runbook](docs/runbooks/flux.md).

## Next work

I'm keeping each step small enough for the existing hardware and a four-hour weekly budget.

1. Save Flux request acknowledgements after restore, add a second independent backup destination, and improve restore precondition error messages.
2. Investigate the six HTTP timeouts after Deployment recovery and measure a successful version update with continuous HTTP requests.
3. Extend VPN and NetworkPolicy restriction checks, add Flux schema validation, and pin runtime image digests.

After these checks, I'd like to add a small read-only assistant with one approved status-reading tool and a scoped identity. The current project covers model serving and operations. Agent execution is still future work.

## Decisions and references

- [Single-node decision](docs/adr/001-single-node.md).
- [SSD decision](docs/adr/002-ssd.md).
- [Evidence template](docs/evidence/result-template.md).
- [Incident template](docs/incidents/failed-rollout-template.md).
- [Technical sources](docs/sources.md).
- [Flux Kustomizations](https://fluxcd.io/flux/components/kustomize/kustomizations/) and [Git sources](https://fluxcd.io/flux/components/source/gitrepositories/).
- [Ollama API timings](https://docs.ollama.com/api/usage).
- [K3s backup and restore](https://docs.k3s.io/datastore/backup-restore).
- [Tailscale grants syntax](https://tailscale.com/docs/reference/syntax/grants).
