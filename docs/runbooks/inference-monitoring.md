# Ollama inference monitoring

Run these commands on your workstation from the repository root. Keep your
Kubernetes API SSH tunnel open and use the VPN kubeconfig. The existing
[post-restore checks](post-restore-checks.md) cover remote API access.

This step adds one small probe Pod. The probe checks the installed model once
a minute. Prometheus reads its metrics, and Grafana shows the check history.

## Deploy after the PR merges

```bash
cd "$HOME/repos/baremetal-platform-lab"
git switch main
git pull --ff-only origin main
export KUBECONFIG="$HOME/.kube/pi-lab-vpn.yaml"
kubectl get nodes

flux reconcile kustomization flux-system -n flux-system --with-source
flux reconcile kustomization ollama-inference-probe -n flux-system --with-source
flux reconcile kustomization monitoring -n flux-system --with-source

kubectl rollout status deployment/ollama-inference-probe -n ai-lab --timeout=180s
kubectl rollout status deployment/prometheus -n monitoring --timeout=180s
kubectl rollout status deployment/grafana -n monitoring --timeout=180s
flux get kustomizations -A
kubectl logs -n ai-lab deployment/ollama-inference-probe --tail=5
```

Expect a `success` result with HTTP 200 in the probe log. A Ready probe Pod
means its worker and metrics server are running. The model check result
comes from the log and `ollama_probe_success`.

## Open Prometheus and Grafana

Start these after the monitoring rollouts. Each command needs its own
workstation terminal and the same VPN kubeconfig:

```bash
export KUBECONFIG="$HOME/.kube/pi-lab-vpn.yaml"
kubectl port-forward -n monitoring service/prometheus 19190:9090 --address=127.0.0.1
```

```bash
export KUBECONFIG="$HOME/.kube/pi-lab-vpn.yaml"
kubectl port-forward -n monitoring service/grafana 13100:3000 --address=127.0.0.1
```

Open Prometheus at `http://127.0.0.1:19190` and Grafana at
`http://127.0.0.1:13100`. These local ports differ from the earlier tunnels.
In Grafana, open **Platform Lab / Ollama Inference Checks**.

Query:

```promql
up{job="ollama-inference-probe"}
```

```promql
ollama_probe_success{job="ollama-inference-probe"}
```

Both should return 1 after a successful model request. The first query checks
Prometheus's scrape. The second checks the model request.

Save the baseline:

```bash
mkdir -p docs/evidence
curl --fail --silent --show-error --get +  http://127.0.0.1:19190/api/v1/query +  --data-urlencode 'query=ollama_probe_success{job="ollama-inference-probe"}' +  | tee docs/evidence/ollama-inference-monitoring-baseline.json

kubectl logs -n ai-lab deployment/ollama-inference-probe --tail=10 +  > docs/evidence/ollama-inference-monitoring-baseline.jsonl
```

## Check denied access

Run this after the approved probe has reported a successful request and the
Ollama Deployment is Ready. The test Job first resolves the Service name,
then tries the same Service from a Pod without the approved label.

```bash
kubectl get deployment ollama -n ai-lab
kubectl delete job inference-network-denied -n ai-lab --ignore-not-found
kubectl apply -f ci/inference-network-denied-job.yaml
kubectl wait --for=condition=Complete job/inference-network-denied -n ai-lab --timeout=90s
kubectl logs -n ai-lab job/inference-network-denied +  | tee docs/evidence/ollama-inference-network-denied.txt
kubectl delete job inference-network-denied -n ai-lab
```

The expected log says DNS resolved and the unapproved request timed out.
A DNS failure, connection refusal, or failed Job needs investigation. A
successful HTTP request from this Pod means the intended restriction did
not hold.

## Test the model-request alert

Keep Prometheus open. Suspend only the probe's Flux Kustomization, then give
the probe a model name which is not installed:

```bash
flux suspend kustomization ollama-inference-probe -n flux-system
kubectl set env deployment/ollama-inference-probe -n ai-lab +  OLLAMA_MODEL=lab-missing-model:never-pulled
kubectl rollout status deployment/ollama-inference-probe -n ai-lab --timeout=180s
kubectl logs -n ai-lab deployment/ollama-inference-probe --tail=5
```

Expect HTTP 404 and `http_error`. The exporter should stay Ready:
`up{job="ollama-inference-probe"}` stays 1, while
`ollama_probe_success{job="ollama-inference-probe"}` becomes 0.

In Prometheus's Alerts page, watch `OllamaInferenceCheckFailing` move from
inactive to pending and then firing. The rule has a two-minute hold.
Scrape and evaluation timing add delay, so allow about three minutes after
the first failed check.

Capture the firing state and logs:

```bash
curl --fail --silent --show-error +  'http://127.0.0.1:19190/api/v1/rules?type=alert' +  | tee docs/evidence/ollama-inference-alert-firing.json
kubectl logs -n ai-lab deployment/ollama-inference-probe --tail=10 +  > docs/evidence/ollama-inference-alert-failures.jsonl
```

Resume Flux and restore the repository configuration, even if an earlier
test command failed:

```bash
flux resume kustomization ollama-inference-probe -n flux-system
flux reconcile kustomization ollama-inference-probe -n flux-system --with-source
kubectl rollout status deployment/ollama-inference-probe -n ai-lab --timeout=180s
kubectl logs -n ai-lab deployment/ollama-inference-probe --tail=5
flux get kustomization ollama-inference-probe -n flux-system
```

After a successful request and the next scrape/evaluation, the alert should
return to inactive. Save the rules again:

```bash
curl --fail --silent --show-error +  'http://127.0.0.1:19190/api/v1/rules?type=alert' +  | tee docs/evidence/ollama-inference-alert-recovered.json
```

For a separate timeout test, repeat the suspension step and set
`PROBE_TIMEOUT_SECONDS=0.001` while keeping the installed model. A very
short limit might still allow a request to complete. Confirm `timeout`
in the probe log before describing the result as a timeout test. Resume
and reconcile the probe afterward.

## Other alert states

`OllamaInferenceProbeUnavailable` detects a failed or missing scrape for
two minutes. `OllamaInferenceProbeStale` detects no completed checks for
over three minutes, followed by a one-minute hold. These cover a missing
exporter and a worker which stops producing fresh results.

The alerts live in Prometheus. This change adds no notification receiver.

## Record the result

Use [the evidence template](../evidence/result-template.md). Include the
deployed Git revision, first successful check, observed firing and recovery
times, denied-Pod result, and a dashboard screenshot. Keep actual logs.

The scheduled checks keep the model warm. Their timings are not the same
test as the earlier cold and warm benchmark, which requested up to 64
tokens. Record probe CPU and memory with `kubectl top pods -n ai-lab`.

Metric counters reset after a probe restart. The duration histogram includes
failed requests. These results describe scheduled checks and do not count
other clients' inference traffic.

## Remove the component

Revert the monitoring PR through Git. Removing
`clusters/pi/inference-probe.yaml` lets Flux prune the probe and its
additional policies. The PR revert also removes its scrape, dashboard,
and alert rules. Keep the existing Ollama deployment and cache.

## References

- [Prometheus instrumentation](https://prometheus.io/docs/practices/instrumentation/)
- [Ollama generation API](https://docs.ollama.com/api/generate)
- [Kubernetes NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Prometheus rule tests](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/)
- [Docker Official Python image definitions](https://github.com/docker-library/official-images/blob/master/library/python)
