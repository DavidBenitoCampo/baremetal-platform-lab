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
set -o pipefail
curl --connect-timeout 5 --max-time 15 --fail --silent --show-error --get http://127.0.0.1:19190/api/v1/query --data-urlencode 'query=ollama_probe_success{job="ollama-inference-probe"}' | tee docs/evidence/ollama-inference-monitoring-baseline.json

kubectl logs -n ai-lab deployment/ollama-inference-probe --container=probe --tail=10 > docs/evidence/ollama-inference-monitoring-baseline.jsonl
```

The Prometheus response should contain a nonempty result with a sample value
of `"1"`. An empty result does not establish a successful check. Keep the
Prometheus port-forward terminal open while running these requests.

## Check denied access

Run this after the approved probe has reported a successful request and the
Ollama Deployment is Ready. The test Job first resolves the Service name,
then tries the same Service from a Pod without the approved label.

The original test accepts only a timeout. The K3s network-policy controller
uses kube-router, whose iptables implementation rejects denied traffic.
An unauthorized request sometimes returns `ConnectionRefusedError`.
Connection refusal alone is not proof of a policy restriction: a Service
without a working backend produces a similar result. Require successful
approved requests to the same URL immediately before and after the test.

Update the current timeout-only test from the repository root:

```bash
sed -i -e 's/except (TimeoutError, urllib.error.URLError)/except (TimeoutError, ConnectionRefusedError, urllib.error.URLError)/' -e 's/isinstance(reason, TimeoutError)/isinstance(reason, (TimeoutError, ConnectionRefusedError))/' -e 's/print("DNS resolved.*")/print("DNS resolved, unapproved connection failed:", repr(reason))/' ci/inference-network-denied-job.yaml
git diff -- ci/inference-network-denied-job.yaml
```

This changes only the test's accepted network errors and its log message.
HTTP responses, DNS failures, and other network errors still fail the test.
No NetworkPolicy changes are required for this correction.

Check approved access immediately before creating the denied Job:

```bash
mkdir -p docs/evidence
set -o pipefail
kubectl exec -n ai-lab deployment/ollama-inference-probe -c probe -- python -c $'from urllib.request import build_opener, ProxyHandler\nresponse = build_opener(ProxyHandler({})).open("http://ollama.ai-lab.svc.cluster.local:11434/api/version", timeout=5)\nprint(response.status)\nprint(response.read().decode())' | tee docs/evidence/ollama-inference-network-approved-before.txt
```

Expect `200` and JSON containing the Ollama version. Continue only after
this succeeds. An approved-client error requires Service or policy diagnosis.

```bash
kubectl get deployment ollama -n ai-lab
kubectl delete job inference-network-denied -n ai-lab --ignore-not-found
kubectl apply -f ci/inference-network-denied-job.yaml
if kubectl wait --for=condition=Complete job/inference-network-denied -n ai-lab --timeout=90s
then
  printf '%s\n' 'Job completed. Check its logs before recording a pass.'
else
  printf '%s\n' 'Job did not complete. Collect status, events, and logs below.'
fi
kubectl get job inference-network-denied -n ai-lab -o yaml | tee docs/evidence/ollama-inference-network-denied-job-status.yaml
kubectl get pods -n ai-lab -l job-name=inference-network-denied -o wide
kubectl describe pods -n ai-lab -l job-name=inference-network-denied | tee docs/evidence/ollama-inference-network-denied-pod-status.txt
kubectl logs -n ai-lab job/inference-network-denied --container=check --pod-running-timeout=10s | tee docs/evidence/ollama-inference-network-denied.txt
```

Check approved access again immediately after collecting the denied result:

```bash
kubectl exec -n ai-lab deployment/ollama-inference-probe -c probe -- python -c $'from urllib.request import build_opener, ProxyHandler\nresponse = build_opener(ProxyHandler({})).open("http://ollama.ai-lab.svc.cluster.local:11434/api/version", timeout=5)\nprint(response.status)\nprint(response.read().decode())' | tee docs/evidence/ollama-inference-network-approved-after.txt
```

A passing result requires all three observations: approved HTTP 200 before
the denied run, a completed denied Job whose log reports DNS resolution
and `ConnectionRefusedError` or `TimeoutError`, and approved HTTP 200 after
the denied run. Keep the actual refusal or timeout in the evidence.
A completed Job alone is not proof of policy enforcement. DNS failures,
unexpected errors, or either approved-client failure need investigation.
Any HTTP response to the denied Pod, including an HTTP error response,
means the restriction did not block its HTTP connection.

A timeout from `kubectl wait` is not a passing denial test. Waiting for
`Complete` also times out when the Job has entered `Failed`. The current
test manifest sets `activeDeadlineSeconds: 60` and `backoffLimit: 0`.
`DeadlineExceeded` means the Job reached its deadline. Pod events identify
image-pull and scheduling problems. Require the approved requests and the
completed denied result described above before recording a pass.

Keep the Job until you have reviewed and saved the evidence. Its automatic
cleanup runs 600 seconds after completion or failure. Deleting the Job also
deletes its Pods. After recording a pass, clean up with:

```bash
kubectl delete job inference-network-denied -n ai-lab
```

## Test the model-request alert

Keep Prometheus open. Suspend only the probe's Flux Kustomization, then give
the probe a model name which is not installed:

```bash
flux suspend kustomization ollama-inference-probe -n flux-system
kubectl set env deployment/ollama-inference-probe -n ai-lab OLLAMA_MODEL=lab-missing-model:never-pulled
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
curl --connect-timeout 5 --max-time 15 --fail --silent --show-error 'http://127.0.0.1:19190/api/v1/rules?type=alert' | tee docs/evidence/ollama-inference-alert-firing.json
kubectl logs -n ai-lab deployment/ollama-inference-probe --container=probe --tail=10 > docs/evidence/ollama-inference-alert-failures.jsonl
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
curl --connect-timeout 5 --max-time 15 --fail --silent --show-error 'http://127.0.0.1:19190/api/v1/rules?type=alert' | tee docs/evidence/ollama-inference-alert-recovered.json
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
- [K3s network-policy controller](https://docs.k3s.io/networking/networking-services#network-policy-controller)
- [kube-router Pod firewall implementation](https://github.com/cloudnativelabs/kube-router/blob/master/pkg/controllers/netpol/pod.go)
- [Prometheus rule tests](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/)
- [Docker Official Python image definitions](https://github.com/docker-library/official-images/blob/master/library/python)
