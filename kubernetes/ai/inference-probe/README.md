# Scheduled Ollama checks

This probe asks `qwen2.5:0.5b` a short question once a minute and exposes the
result on `/metrics`. Prometheus scrapes those metrics every 30 seconds.

The request asks for the word “ready”, allows 16 output tokens, and uses two CPU
threads. A successful check needs HTTP 200 and a completed, non-empty response.
Answer quality needs a separate test.

The probe uses Python's standard library. Kustomize puts the script in a hashed
ConfigMap and mounts the file read-only. A script change updates the Pod
template. The runtime uses the exact Docker Official Image tag
`python:3.12.15-slim-bookworm`, which supports ARM64.

| Metric | Meaning |
| --- | --- |
| `ollama_probe_success` | Last result: 1 passed, 0 failed, -1 no completed check |
| `ollama_probe_requests_total` | Completed checks, split into five fixed result categories |
| `ollama_probe_duration_seconds` | Duration of the last check, including failures |
| `ollama_probe_request_duration_seconds` | Histogram of all completed check durations |
| `ollama_probe_http_status` | Last HTTP status, or 0 without an HTTP response |
| `ollama_probe_last_check_timestamp_seconds` | Last completion time, or 0 before the first check |
| `ollama_probe_started_timestamp_seconds` | Probe process start time |
| `ollama_probe_generated_tokens_total` | Tokens from successful scheduled checks |

Result categories are `success`, `http_error`, `timeout`, `transport_error`,
and `invalid_response`. Metric labels contain no prompts, replies, or error
messages. Counters reset when the probe restarts. Prometheus retains their
scraped history on its existing volume.

These metrics cover scheduled test requests. They do not count requests from
other Ollama clients. Regular checks keep the model loaded with a five-minute
keep-alive, so expect more idle model memory use than with no requests.

The 15-second limit is a socket timeout. A timed-out client does not establish
when server-side generation stopped. A separate alert catches results which
stop updating.

The HTTP metrics server runs separately from the model check. Its readiness
and liveness endpoints check the worker thread, not the model result. A missing
model therefore produces a failure metric while Prometheus keeps scraping.

NetworkPolicies allow this probe to reach Ollama and CoreDNS. Only Prometheus
Pods in `monitoring` have Pod-network access to the metrics port. The Ollama
allow rule adds to its existing deny policy. These rules use Pod labels and
depend on the cluster's NetworkPolicy implementation. The runbook includes a
check from an unapproved Pod.

Flux manages the component through `clusters/pi/inference-probe.yaml`, after
the existing `ollama` Kustomization reports Ready.

Follow [the deployment and alert test](../../../docs/runbooks/inference-monitoring.md).
Live deployment, policy enforcement, and the alert test need evidence from
the Pi.
