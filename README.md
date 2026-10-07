# baremetal-platform-lab

My Kubernetes lab on a Raspberry Pi 5. I'm building toward a small local AI service, with repeatable deployment, monitoring, and recovery tests.

I started with Podinfo to check the cluster, networking, and rollout behavior. Those tests now work. The next step is running a small language model on the same cluster and measuring how the Pi handles inference.

## What runs today

- Ubuntu Server 24.04.5 LTS on an ADATA SU650 USB SSD.
- K3s `v1.36.5+k3s1`, installed through Ansible.
- Two Podinfo replicas with health probes and resource limits.
- A ClusterIP Service and Traefik Ingress at `podinfo.lab.test`.
- Kubernetes Secrets encryption enabled.

The second Ansible run reported zero changes. K3s and the node recovered after a reboot.

Ollama, AI workloads, GitOps, CI, and the monitoring stack are still planned. The files and results in this repository describe the Kubernetes baseline so far.

## The next workload: local inference

I'll start with Ollama and `qwen2.5:0.5b`, running on the Pi's CPU. Ollama publishes ARM64 builds and a container image with CPU support. This model's listed download size is about 398 MB. Runtime memory will be higher and needs measuring.

The first deployment will have:

- One inference Pod in a separate namespace.
- A pinned Ollama image and a recorded model digest.
- An SSD-backed persistent volume for downloaded model files.
- A ClusterIP Service, accessed from my workstation through port-forwarding.
- Startup and health checks, plus a separate test proving the model answers a request.
- Explicit CPU and memory settings.

I'll begin with one loaded model, one request at a time, and a 2,048-token context. A 1 GiB memory request and 2 GiB limit are starting estimates. I'll adjust them using measurements and aim to keep at least 2 GiB available on the node. I'll budget 20 GiB of SSD space for the runtime image and model cache.

These are initial settings, not measured requirements. The Pi has no dedicated AI accelerator in this setup. I'll record inference speed before trying a larger model.

### What I'll test

1. Send a fixed prompt and receive a complete response.
2. Record the first request after loading the model, then repeat with the model already loaded.
3. Record response time, generated tokens per second, CPU use, and memory use.
4. Delete the inference Pod and confirm the replacement reuses the downloaded model files.
5. Introduce a bad deployment change and recover through version-controlled configuration.
6. Test a missing model and a request timeout, with clear errors in the client.
7. Add monitoring and an alert for a failed inference check.

I'll use a short Python client for the POST requests and results. The existing HTTP probe uses GET requests and will stay useful for the Podinfo tests.

Ollama returns token counts and timing fields in API responses. Those fields will support the benchmark. Prometheus collection still needs a separate implementation.

### A small assistant after inference works

The next extension is a read-only lab assistant. A small script will fetch workload status using a namespace-scoped, read-only identity, send a filtered summary to the local model, and return an explanation.

The first version will follow a fixed flow with one approved tool. I'll test with saved workload-status fixtures before connecting the live cluster. Cluster credentials and secrets stay out of the prompts. Any operational change stays manual.

This adds tool use, request handling, and failure cases without introducing an agent framework before the model service works.

## Hardware

| Component | Current setup |
| --- | --- |
| Computer | Raspberry Pi 5, 8 GB RAM |
| Storage | ADATA SU650 512 GB SATA SSD over USB |
| Cooling | Active cooling case |
| Network | Ethernet |
| Operating system | Ubuntu Server 24.04.5 LTS, ARM64 |
| Spare storage | 512 GB microSD card |

Ubuntu and K3s run from the SSD. The root filesystem is `/dev/sda2`, formatted as ext4.

## Tests completed so far

On 7 October 2026, I tested:

- Host preparation with Ansible. First run: `ok=23`, `changed=9`, `failed=0`. Second run: `ok=22`, `changed=0`, `failed=0`.
- Reboot recovery. K3s returned to `active` and `pi-lab` returned to `Ready`.
- A Podinfo update from 6.14.1 to 6.15.0.
- A failed rollout using `/not-ready` as the readiness path. The new Pod stayed unready while two previous Pods stayed Ready. The Deployment reported `ProgressDeadlineExceeded`, and an HTTP check returned 200.
- Recovery by restoring the working manifest from Git and running `kubectl apply`.
- Pod replacement. Kubernetes recreated a deleted Pod, and the HTTP check after replacement returned 200.

The rolling update used `maxUnavailable: 0` and `maxSurge: 1`. Readiness kept the broken new Pod out of the Service's ready endpoints.

I haven't measured deployment time, recovery time, or continuous HTTP failures yet. The successful curl checks are individual observations, not a zero-downtime result. Git recovery was manual. A controller has not reconciled the deployment yet.

The full record is in [initial cluster evidence](docs/evidence/2026-10-07-initial-cluster.md).

## Reproducing the current Kubernetes setup

The commands below reproduce the existing Podinfo baseline. AI deployment manifests will follow in a separate change.

Start with Ubuntu Server 24.04 LTS ARM64 booting from the SSD, SSH key access, and sudo access. The workstation needs Ansible and kubectl. Read [the bootstrap runbook](docs/runbooks/bootstrap.md) before running the playbook.

### Prepare the host

From the repository root, create an inventory for a new setup:

```bash
cp ansible/inventory.example.ini ansible/inventory.ini
```

Edit the Pi address, user, and SSH key path. Keep an existing working inventory rather than copying over the file.

```bash
ansible-playbook -i ansible/inventory.ini ansible/host.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/host.yml
```

The tested `lab` user has passwordless sudo. Add `--ask-become-pass` when the chosen user needs a sudo password.

The playbook pins the K3s release, prepares host networking, and enables Secrets encryption. The server uses SQLite. The playbook checks for an existing installation and refuses to adopt an unrelated cluster or change the installed version.

Keep `ansible/inventory.ini` outside Git. The repository includes an example inventory.

### Connect from the workstation

These examples use the lab's current address. Change the address and SSH key path for another setup.

```bash
PI_ADDRESS=10.0.1.16
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo k3s kubectl get nodes -o wide'
```

For first-time kubectl access, copy the kubeconfig outside the repository. Keep an existing working copy unchanged.

```bash
PI_ADDRESS=10.0.1.16
mkdir -p ~/.kube
(
  umask 077
  ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo cat /etc/rancher/k3s/k3s.yaml' > ~/.kube/pi-lab.yaml
)
sed -i "s/127.0.0.1/${PI_ADDRESS}/g" ~/.kube/pi-lab.yaml
chmod 600 ~/.kube/pi-lab.yaml
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"
kubectl get nodes -o wide
```

This kubeconfig grants cluster admin access. Keep the file and private SSH key out of Git.

### Deploy and check Podinfo

Create the namespace before the server-side dry run. A dry-run namespace is not saved for the other resources.

```bash
kubectl apply -f kubernetes/base/namespace.yaml
kubectl apply --dry-run=server -k kubernetes/overlays/pi
kubectl apply -k kubernetes/overlays/pi
kubectl rollout status deployment/podinfo -n platform-demo --timeout=180s
```

Add the following entry to the workstation's `/etc/hosts` file:

```text
10.0.1.16 podinfo.lab.test
```

Then check the workload and endpoints:

```bash
kubectl get deployment,service,pdb -n platform-demo
kubectl get pods -n platform-demo -o wide
curl -i http://podinfo.lab.test/readyz
curl -s http://podinfo.lab.test/version
curl -s http://podinfo.lab.test/metrics | head
```

The expected baseline is two Ready Pods, HTTP 200 from `/readyz`, and version 6.15.0. This endpoint currently uses HTTP on the lab network.

## Measuring the next rollout

I'll run the existing probe from my workstation during the next Podinfo rollout. This example makes 600 requests at one-second intervals with a 0.8-second timeout:

```bash
python3 scripts/http_probe.py http://10.0.1.16/version --host podinfo.lab.test --count 600 --interval 1 --timeout 0.8 > docs/evidence/release-probe.jsonl
```

The log includes HTTP status, errors, latency, and timestamps. I'll retain the full log and record when the change starts and when recovery finishes. No results exist for this measurement yet.

For inference, I'll record the prompt, model digest, context size, output limit, and whether the model was already loaded. Comparing requests under the same conditions will make the results useful.

## Limits and recovery

Everything runs on one Pi. A host, power, or USB SSD failure stops the cluster. Two Podinfo replicas handle some Pod-level failures, but both depend on the same machine. The inference service will start with one replica and accept downtime during updates.

The model volume survives Pod replacement while the underlying SSD and volume remain intact. Local storage provides no copy on another machine. Monitoring on the Pi will share the same host failure.

The first backup exercise will cover K3s state, required credentials, and configuration. The destination needs independent storage on an existing computer. I'll document how to download and verify the chosen model again. Model weights will be treated as a cache rather than included in the first backup.

GPU scheduling, model training, distributed inference, and production high availability are outside this version. A production service would need separate failure domains, suitable compute, independent monitoring, and tested off-host recovery.

## Repository layout

- `ansible/`: host preparation and K3s configuration.
- `kubernetes/`: current Podinfo manifests and Pi overlay.
- `clusters/pi/`: GitOps resources once added.
- `monitoring/`: monitoring notes, with configuration still to follow.
- `scripts/`: preflight and HTTP checks. The inference client will live here too.
- `.github/workflows/`: CI notes. Executable validation still needs adding.
- `docs/`: decisions, runbooks, incident reports, and test results.
- `versions.yaml`: component version reference.

AI manifests will be added under `kubernetes/` in a separate namespace.

Useful records:

- [Bootstrap runbook](docs/runbooks/bootstrap.md)
- [Single-node decision](docs/adr/001-single-node.md)
- [SSD decision](docs/adr/002-ssd.md)
- [Initial test results](docs/evidence/2026-10-07-initial-cluster.md)
- [Incident template](docs/incidents/failed-rollout-template.md)
- [Measurement template](docs/evidence/result-template.md)

## Next changes

I have four hours a week for this project, so I'll add one working piece at a time.

1. Measure current node memory, CPU use, and free SSD space.
2. Deploy Ollama and the small model, then complete the inference and Pod replacement tests.
3. Add CI and one GitOps controller. Test correction of a manual configuration change.
4. Add Prometheus and Grafana, then test an inference failure alert.
5. Run the independent backup and restore exercise.
6. Add the read-only assistant once the serving and recovery work is documented.

## References

The Kubernetes sources are collected in [sources.md](docs/sources.md).

AI references checked on 7 October 2026:

- [Ollama ARM64 installation](https://docs.ollama.com/linux)
- [Ollama CPU container setup](https://docs.ollama.com/docker)
- [Official container tags and architectures](https://hub.docker.com/r/ollama/ollama/tags)
- [Qwen2.5 0.5B model](https://ollama.com/library/qwen2.5:0.5b)
- [Ollama context and concurrency settings](https://docs.ollama.com/faq)
- [Ollama API timing and token counts](https://docs.ollama.com/api/usage)
