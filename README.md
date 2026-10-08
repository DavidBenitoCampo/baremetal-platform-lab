# baremetal-platform-lab

I run a small language model on a Raspberry Pi 5 and use this repository to manage the infrastructure around the service. The lab uses K3s, Ansible, Ollama, and Flux, with configuration checks in GitHub Actions.

I started with Podinfo to learn how Kubernetes handles releases and failed changes. Podinfo stays in the lab as a simple test application. Ollama is the AI workload, running Qwen2.5 0.5B on the Pi's CPU.

## Current setup

Status recorded on 8 October 2026.

| Component | Running configuration |
| --- | --- |
| Host | Ubuntu Server 24.04.5 LTS, ARM64 |
| Kubernetes | K3s `v1.36.5+k3s1`, one server using SQLite |
| Host automation | Ansible playbook in `ansible/host.yml` |
| Test application | Podinfo 6.15.0, two replicas in `platform-demo` |
| Inference server | Ollama 0.40.0, one replica in `ai-lab` |
| Model | `qwen2.5:0.5b`, 397 MB in the model list |
| Model storage | `ollama-cache` PVC using `local-path`, requesting 20 GiB |
| GitOps | Flux 2.9.6, tracking `main` |
| CI | YAML, Ansible, Kustomize, Kubernetes schemas, script syntax, and JSONL checks |

The hardware is a Raspberry Pi 5 with 8 GB RAM, active cooling, and an ADATA SU650 512 GB SATA SSD connected through a USB adapter. Ubuntu and K3s run from the SSD. The root filesystem is `/dev/sda2`, formatted as ext4. A 512 GB microSD card is spare storage.

Prometheus, Grafana, alerting, backup restore, and the read-only assistant are still pending.

## Tests completed

### Cluster and releases

- The first Ansible run reported `ok=23`, `changed=9`, and `failed=0`. The second reported `ok=22`, `changed=0`, and `failed=0`.
- After a reboot, K3s returned to `active` and the node returned to `Ready`.
- Podinfo updated from 6.14.1 to 6.15.0 with a rolling update.
- An invalid readiness path left the new Pod unready while two previous Pods stayed Ready. The Deployment reported `ProgressDeadlineExceeded`, and an Ingress check returned HTTP 200.
- I restored the working manifest from Git and applied the change manually. This test happened before Flux installation.
- Kubernetes replaced a deleted Podinfo Pod. The HTTP check after replacement returned 200.

The Podinfo rollout uses `maxUnavailable: 0` and `maxSurge: 1`. I have not recorded continuous HTTP traffic during these tests, so the successful checks do not establish zero downtime.

[Initial cluster and release evidence](docs/evidence/2026-10-07-initial-cluster.md).

### Local inference and model persistence

Ollama answered requests through a workstation port-forward. The probe used a 2,048-token context, a 64-token output limit, two CPU threads, and no GPU. Requests ran sequentially with streaming disabled, temperature `0`, seed `7`, and a five-minute model keep-alive.

| Request | Model loaded before request | Complete response time | Output tokens | Generation tokens/second |
| --- | --- | --- | --- | --- |
| First request | No | 4.4195 s | 27 | 24.387 |
| Loaded-model request 1 | Yes | 1.7685 s | 37 | 23.200 |
| Loaded-model request 2 | Yes | 1.7113 s | 37 | 23.147 |
| After Pod replacement | No | 4.3745 s | 27 | 25.045 |
| After reboot | No | 5.3925 s | 27 | 23.491 |

These are individual measurements from one short prompt. Response time covers the complete generation request. Generation speed excludes model loading. I have not measured time to first token or concurrent throughput.

The first answer incorrectly described readiness as a check of the whole cluster. I kept the original responses in the evidence files. Successful inference proves the serving path works, not answer accuracy.

After deleting the Ollama Pod, the replacement listed the same model and completed another inference request without a new model pull. The model also remained available after restarting the Pi. The recorded digest was:

```text
a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67
```

A snapshot after the first request showed 656 MiB for the Ollama container and 6.0 GiB available on the host. This reading predates Flux installation and does not measure peak inference memory.

[Inference and Pod replacement evidence](docs/evidence/2026-10-07-ollama.md). [Request after reboot](docs/evidence/ollama-after-reboot.jsonl).

### CI failure and recovery

I added an unsupported `replicaz` field to a Podinfo Deployment on a test branch. The pull request failed Kubernetes schema validation. After removing the field, the next run passed. I closed the test PR without merging.

- [Failed validation](https://github.com/DavidBenitoCampo/baremetal-platform-lab/actions/runs/37781585707).
- [Validation after the fix](https://github.com/DavidBenitoCampo/baremetal-platform-lab/actions/runs/37782406906).
- [Passing GitOps configuration commit](https://github.com/DavidBenitoCampo/baremetal-platform-lab/actions/runs/37823383476).

The current workflow validates both application paths. Flux CRD schemas and the `clusters/` configuration are not included in these CI checks yet. CI uses no Pi credentials and makes no connection to the cluster.

### Flux reconciliation

Flux fetched and applied commit `16f31794b8844fdf240eb301fdfc8c39e3f03047`. The `flux-system`, `podinfo`, and `ollama` Kustomizations all reported `READY=True`, with no suspension.

Podinfo and Ollama each passed their Deployment health check. Ollama's health probe checks the HTTP server. The separate inference probe verifies a model response.

The manual drift correction exercise is the next test. Recovery from a bad release through Flux has not been tested yet.

## How Git controls the cluster

Flux reads this repository using a GitHub deploy key with read-only access. The bootstrap credentials stay outside Git.

| Flux Kustomization | Repository path | Purpose |
| --- | --- | --- |
| `flux-system` | `clusters/pi` | Flux configuration and application reconciliation definitions |
| `podinfo` | `kubernetes/overlays/pi` | Podinfo manifests and Pi replica patch |
| `ollama` | `kubernetes/ai/ollama` | Inference Deployment, Service, model volume, and network policy |

The Git source polls once per minute. Each application reconciliation also has a one-minute interval. The root `flux-system` reconciliation has a ten-minute interval and also reacts to new Git revisions.

Kustomize builds the application YAML from each folder's `kustomization.yaml`. Flux then applies the result and checks the named Deployment. Pruning is enabled, so removing a managed resource from Git also removes the resource from the cluster. The Ollama PVC and namespace need care because deleting either would affect stored models.

CI and Flux run independently. Flux does not wait for a green GitHub Actions run before applying changes on `main`. Adding a required-check pull request workflow is future work.

## Checking the running lab

Run these commands on the workstation. The kubeconfig lives outside the repository and grants admin access to the Pi cluster.

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"

kubectl get nodes
flux get sources git -A
flux get kustomizations -A
kubectl get deployment,pods -n platform-demo
kubectl get deployment,pods,pvc -n ai-lab
```

Podinfo uses Traefik Ingress. The workstation's `/etc/hosts` contains `10.0.1.16 podinfo.lab.test`.

```bash
curl -i http://podinfo.lab.test/readyz
curl -s http://podinfo.lab.test/version
```

Ollama uses a ClusterIP Service. Open a second terminal and keep this port-forward running:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"
kubectl port-forward -n ai-lab service/ollama 11435:11434 --address=127.0.0.1
```

Back in the repository terminal, check the model list and send a request:

```bash
kubectl exec -n ai-lab deployment/ollama -- ollama list
python3 scripts/inference_probe.py --url http://127.0.0.1:11435 --count 1
```

The client prints one JSON record per request. Review `ok`, `http_status`, the response text, model digest, and timings. Restart the port-forward after a Pod replacement.

## Setup and operating procedures

For a fresh build, start with [host bootstrap](docs/runbooks/bootstrap.md), then read the [Ollama setup](kubernetes/ai/ollama/README.md) and [official Flux GitHub bootstrap procedure](https://fluxcd.io/flux/installation/bootstrap/github/). The local Ansible inventory contains the Pi address, user, and SSH key path and stays untracked.

For the running cluster, change the manifests in Git. Use the [Flux runbook](docs/runbooks/flux.md) for reconciliation, status checks, and the planned drift exercise.

## Access and resource settings

- SSH uses key authentication. The admin kubeconfig stays outside Git with mode `600`.
- K3s encrypts Kubernetes Secrets at rest.
- Ollama runs as UID 1000, with no service account token mounted, a read-only root filesystem, dropped Linux capabilities, and privilege escalation disabled.
- Ollama requests one CPU and 1 GiB memory, with limits of two CPUs and 2 GiB. The server permits one loaded model and one parallel request.
- The network policy declares denied Pod-network ingress to Ollama. Its enforcement test is pending. Administrative access currently uses the localhost port-forward.
- Container images use version tags. Immutable image digest pinning is pending. The inference logs record the model digest.

Flux currently uses the cluster permissions created by bootstrap. Namespace-scoped reconciliation identities are pending. Repository write access therefore matters: changes on `main` become cluster configuration.

## Storage and reliability limits

All workloads and Flux run on one Pi. Two Podinfo replicas help with Pod replacement and rolling updates, but both depend on the same host. Ollama has one replica and uses `Recreate`, accepting interruption during updates.

The local model volume survived Pod replacement and reboot. This provides no independent copy of the data. A Pi, power, or USB SSD failure stops the cluster. The `20Gi` PVC request does not enforce a disk quota with this local-path provisioner.

The first backup exercise will cover K3s state, required credentials, and configuration on an existing computer with independent storage. The backup destination and restore procedure still need verification. Model files will be treated as a cache and downloaded again. Application data, monitoring history, and OS reimaging are outside this first restore scope.

Monitoring installed on the Pi will share the same failure point. A production design would need compute sized for the models, separate failure domains, independent monitoring, restricted identities, and tested external backups.

## Repository guide

- `ansible/`: host preparation and K3s configuration.
- `kubernetes/base/` and `kubernetes/overlays/pi/`: Podinfo and the Pi overlay.
- `kubernetes/ai/ollama/`: inference server and model cache manifests.
- `clusters/pi/`: Flux bootstrap files and application reconciliations.
- `.github/workflows/` and `ci/`: validation workflow and tool settings.
- `scripts/`: host preflight, HTTP checks, and the inference probe.
- `docs/`: evidence, decisions, runbooks, and incident templates.
- `monitoring/`: notes for the next monitoring milestone.
- `versions.yaml`: version reference, including proposed components. This file is not a list of everything deployed.

## Next work

I have four hours a week for the lab. The next pieces are:

1. Record Flux drift correction and a failed rollout recovered through Git, including elapsed time and HTTP checks.
2. Extend CI to validate Flux resources and require passing checks before merging.
3. Measure peak inference CPU and memory, record container image digests, and test missing-model and timeout errors.
4. Add Prometheus and Grafana, then test an alert for a failed inference request.
5. Complete the backup and restore exercise using independent storage.
6. Build a small read-only assistant with one approved status-reading tool, a scoped identity, and saved test fixtures. Operational changes stay manual.

## References

- [Single-node decision](docs/adr/001-single-node.md) and [SSD decision](docs/adr/002-ssd.md).
- [Technical sources](docs/sources.md).
- [Flux Kustomizations](https://fluxcd.io/flux/components/kustomize/kustomizations/) and [Git sources](https://fluxcd.io/flux/components/source/gitrepositories/), checked 8 October 2026.
- [Ollama API timings](https://docs.ollama.com/api/usage), checked 8 October 2026.
