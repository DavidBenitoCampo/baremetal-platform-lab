# First Ollama deployment

This adds a small CPU inference service to the existing Pi cluster. Podinfo,
Traefik and the host configuration stay unchanged.

The manifests create a namespace, a model-cache volume, one Deployment, a private
Service and an ingress NetworkPolicy. The Python client sends three short
requests and records the responses and timing fields.

These files have not run on the Pi yet. Server-side validation, image startup,
volume permissions and inference still need checking on the real cluster.

## Starting settings

| Setting | First value |
| --- | --- |
| Namespace | ai-lab |
| Ollama image | ollama/ollama:0.40.0 |
| Model | qwen2.5:0.5b |
| Replicas | 1 |
| Update strategy | Recreate, with downtime |
| CPU request and limit | 1 core and 2 cores |
| Memory request and limit | 1 GiB and 2 GiB |
| Context | 2,048 tokens |
| Loaded models and parallel requests | 1 each |
| PVC request | 20 GiB, local-path |
| Access | Local kubectl port-forward |

The official image tag includes linux/arm64. The ARM64 image download is roughly
2.6 GB, separately from the model's roughly 398 MB download. The memory settings
are estimates. Check the [baseline](../../../docs/evidence/2026-10-07-pre-inference-baseline.md)
and watch available memory during the first request.

The local-path provisioner does not enforce the 20 GiB request as a disk quota.
The cache shares the SSD with Ubuntu and K3s. PVC deletion removes the local
volume under the current Delete reclaim policy. Keep the PVC during Pod tests.

## Add the files

Extract the supplied archive into your repository root. The archive adds only
new paths under kubernetes/ai/ollama, scripts and docs/evidence. The unzip -n
option skips existing files rather than overwriting your work.

From your workstation:

```bash
cd /home/badbeny/Downloads/baremetal-platform-lab
unzip -n /home/badbeny/Downloads/ollama-lab-starter.zip -d .
export KUBECONFIG="$HOME/.kube/pi-lab.yaml"
```

Read deployment.yaml before applying. The model server runs as UID/GID 1000.
Its container home and model directory use the writable PVC. The root filesystem
stays read-only and /tmp uses a bounded temporary volume. The Pod receives no
Kubernetes API token and drops all Linux capabilities. The container HOME setting
does not change the workstation or host account.

## Start the server

First check for an existing ai-lab namespace. If an unrelated application already
uses these names, choose different names before applying the module.

```bash
kubectl get namespace ai-lab
```

NotFound is expected for this first deployment. Create the namespace before the
server dry run, since a dry-run Namespace is not stored for other resources.
Render the configuration, validate against the API, then apply.

```bash
kubectl kustomize kubernetes/ai/ollama
kubectl apply -f kubernetes/ai/ollama/namespace.yaml
kubectl apply --dry-run=server -k kubernetes/ai/ollama
kubectl apply -k kubernetes/ai/ollama
kubectl rollout status deployment/ollama -n ai-lab --timeout=1200s
kubectl get pods,pvc,service,networkpolicy -n ai-lab
```

The first image pull needs time. ContainerCreating during the download is not
proof of failure. Use describe and Events for the cause of a stalled startup.
The PVC waits for a consuming Pod before binding, matching WaitForFirstConsumer.

Expected checkpoint: one 1/1 Running Pod, a Bound PVC and a ClusterIP Service.
All three probes check /api/version. They prove the HTTP server responds, not
whether the model is installed or inference works.

Verify the volume path before calling the cache SSD-backed. The PV output gives
the actual host path. Check this path on the Pi with findmnt -T, rather than
assuming every node-local path belongs to the SSD.

```bash
AI_CACHE_PV=$(kubectl get pvc ollama-cache -n ai-lab -o jsonpath='{.spec.volumeName}')
kubectl get pv "$AI_CACHE_PV" -o yaml
```

For the usual K3s storage directory, the mount check is:

```bash
ssh -i ~/.ssh/pi_lab_ed25519 lab@10.0.1.16 'findmnt -T /var/lib/rancher/k3s/storage'
```

Expected backing filesystem for this Pi: /dev/sda2. Use the actual PV path if the
provisioner chose another location.

## Open a local connection

Keep this command running in terminal A. The explicit address limits the local
listener to your workstation's loopback interface. No Ingress, NodePort or router
port forwarding belongs in this first deployment.

```bash
kubectl port-forward -n ai-lab service/ollama 11434:11434 --address=127.0.0.1
```

In terminal B, check the server version and available models:

```bash
curl --fail --max-time 10 http://127.0.0.1:11434/api/version
curl --fail --max-time 10 http://127.0.0.1:11434/api/tags
```

An empty models list is expected before the first pull. Port-forward uses your
administrative Kubernetes access. The NetworkPolicy denies Pod-network ingress
when the cluster's policy controller enforces the rule. Node traffic has
Kubernetes policy exceptions. This is not an authenticated public inference API.
Leave egress open for DNS and HTTPS during the public model download.

The installed K3s configuration does not disable its network-policy controller.
Actual blocking still needs a test before recording network isolation as proven.

## Download one model

The exec command runs the CLI inside the server Pod. No Ollama installation on
the Pi host or workstation is required. The PVC stores the model files.

```bash
kubectl exec -n ai-lab deployment/ollama -- ollama pull qwen2.5:0.5b
kubectl exec -n ai-lab deployment/ollama -- ollama list
```

Keep the model tag fixed for the first test. The request logger also records the
model digest from /api/tags. The image uses a version tag, not a digest pin. Record
the actual imageID after startup before choosing an immutable image pin:

```bash
kubectl get pods -n ai-lab -l app.kubernetes.io/name=ollama -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

## Measure three requests

Run the client in terminal B from the repository root while port-forward stays
open. The client uses Python's standard library. Each request uses the same
prompt, a 2,048-token context, at most 64 generated tokens, two CPU threads and
CPU inference. Requests run sequentially with a 180-second socket timeout.

Check /api/ps first. An empty list means no model is resident. The logger records
loaded_before for each request, so do not call a result cold or warm from its
sample number alone. Cold here refers to an unloaded model, not an empty OS page
cache or a rebooted host.

```bash
curl --fail --max-time 10 http://127.0.0.1:11434/api/ps
python3 scripts/inference_probe.py | tee docs/evidence/ollama-first-run.jsonl
```

Every successful record contains a completed non-empty answer, client wall time,
server loading time, generation time, token count, generation tokens per second,
server version and model digest. A failed record sets ok to false and stops the
client. Generation tokens per second excludes model loading. Wall time covers
the full non-streaming generation request, not time to the first token.

Sample memory and CPU in another terminal during the test. Save observations
with timestamps. Metrics-server samples are not a process-level peak measurement.

```bash
kubectl top pod -n ai-lab --containers
kubectl top nodes
ssh -i ~/.ssh/pi_lab_ed25519 lab@10.0.1.16 'free -h'
```

Keep at least 2 GiB available on the host. If memory pressure, OOMKilled or a
repeated timeout appears, stop the workload and inspect the cause. Do not add a
larger model or raise limits without reviewing remaining host capacity.

Stopping without deleting the cache:

```bash
kubectl scale deployment/ollama -n ai-lab --replicas=0
```

This changes live state only. An apply restores the one replica declared in Git.

## Replace the Pod and check the cache

Only run this after a successful inference test. Retain the current model listing
and Pod name. Deleting the Ollama Pod accepts an interruption of this service.
Podinfo stays separate. Do not delete the PVC or namespace.

```bash
curl --fail --max-time 10 http://127.0.0.1:11434/api/tags > docs/evidence/ollama-models-before.json
kubectl get pods -n ai-lab -l app.kubernetes.io/name=ollama
kubectl delete pod -n ai-lab -l app.kubernetes.io/name=ollama
kubectl get pods -n ai-lab -l app.kubernetes.io/name=ollama -w
```

When the replacement has a new name and reports 1/1 Running, press Ctrl+C to
stop the watch. The old port-forward connection ends with its Pod. Restart the
terminal A command against the Service, then check from terminal B:

```bash
curl --fail --max-time 10 http://127.0.0.1:11434/api/tags > docs/evidence/ollama-models-after.json
diff -u docs/evidence/ollama-models-before.json docs/evidence/ollama-models-after.json
python3 scripts/inference_probe.py --count 1 | tee docs/evidence/ollama-after-replacement.jsonl
```

Expected: the same model digest remains without another pull, and a request
returns a completed answer. The result demonstrates persistence across Pod
replacement on the same healthy SSD. Host or SSD loss still stops the service.

## Troubleshooting

Read status and Events first:

```bash
kubectl describe pods -n ai-lab
kubectl describe pvc ollama-cache -n ai-lab
kubectl get events -n ai-lab --sort-by=.lastTimestamp
kubectl logs -n ai-lab deployment/ollama --tail=100
```

For a restarted container, add --previous to the logs command.

ImagePullBackOff points to the registry, version or download path. Pending with
an unbound PVC points to provisioning or scheduling. Permission denied points
to the writable cache path and provisioner setup permissions. Inspect these
before changing UID or disabling read-only protection. Do not reinstall K3s.

If localhost refuses the connection, check terminal A before changing the
Service. A missing-model response needs a successful model pull. An OOMKilled
exit needs memory review, not a probe restart loop.

## Record and commit

Before marking inference complete, retain the real imageID, model digest,
Pod/PVC states, JSONL responses, memory samples and replacement result. Keep
cloud, timing and recovery claims limited to these observations. No agent,
GitOps reconciliation, Prometheus scrape or restore test runs in this module.

Review the staged paths before committing only this addition and its results:

```bash
git add kubernetes/ai/ollama scripts/inference_probe.py docs/evidence
git diff --cached --name-only
git diff --cached
```

After reviewing:

```bash
git commit -m "Add private Ollama service and first inference evidence"
git push
```

## References

Official sources checked on 7 October 2026:

- [Ollama CPU container setup](https://docs.ollama.com/docker)
- [Official ARM64 image tags](https://hub.docker.com/r/ollama/ollama/tags)
- [Qwen2.5 0.5B model](https://ollama.com/library/qwen2.5:0.5b)
- [Context, concurrency and local-only settings](https://docs.ollama.com/faq)
- [Version API](https://docs.ollama.com/api-reference/get-version)
- [Generation API](https://docs.ollama.com/api/generate)
- [API timing units](https://docs.ollama.com/api/usage)
- [Model digests](https://docs.ollama.com/api/tags)
- [Resident models](https://docs.ollama.com/api/ps)
- [Local-path provisioning and capacity limits](https://github.com/rancher/local-path-provisioner)
- [NetworkPolicy behavior](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
