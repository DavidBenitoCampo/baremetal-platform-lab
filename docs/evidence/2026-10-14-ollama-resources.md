# Ollama on the Pi: a first resource test

14 October 2026, Prague. The logs use UTC, so their timestamps show 13 October.

I checked how much CPU and memory Ollama used when loading a model and answering requests. I started with no model loaded, sent one request, then sent ten more. All eleven returned HTTP 200.

Before the requests, Ollama used 13 MiB. With the model loaded, the highest memory reading was 620 MiB. The highest CPU reading was 1,485m, or about one and a half cores.

| Measurement | Result |
| --- | --- |
| First response | 4.517 seconds |
| Time spent loading the model | 2.389 seconds |
| Median of the ten warm responses | 2.021 seconds |
| Warm response range | 1.798–2.322 seconds |
| Highest sampled CPU | 1.485 cores |
| Memory before loading | 13 MiB |
| Highest sampled memory | 620 MiB |

CPU returned to 1m after the requests. Memory stayed at 620 MiB through the last reading because the model was still loaded.

I used Ollama 0.40.0 with `qwen2.5:0.5b`, two CPU threads, a 2,048-token context, and a 64-token output limit. Requests ran one at a time through my Tailscale and SSH connection. The JSONL files contain the remaining settings, model digest, and responses.

The first request spent 2.389 seconds loading the model. The warm requests reused the model in memory. They also produced longer answers: 37 tokens each, compared with 27 on the first request.

I sampled `kubectl top` in a second SSH session, waiting five seconds between queries. The log covers 22:26:54–22:28:54 UTC and includes the request run. These are sampled values. Kubernetes averages CPU over a time window, so 1.485 cores is the highest reading I saw during this short test.

“Cold” means the model was not loaded in Ollama. I did not clear the OS filesystem cache.

The first answer was wrong about readiness probes. I kept the response in the log. Successful HTTP requests are one check. The quality of the answers needs another.

## Files from the run

- [Idle baseline](2026-10-14-ollama-baseline.txt)
- [CPU and memory readings](2026-10-14-ollama-resources.txt)
- [First request](2026-10-14-ollama-cold.jsonl)
- [Ten warm requests](2026-10-14-ollama-warm.jsonl)

Metric definitions: [Kubernetes resource metrics](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/#measuring-resource-usage). API fields: [Ollama generation](https://docs.ollama.com/api/generate) and [running models](https://docs.ollama.com/api/ps).

## Error tests

I requested a model I had not installed. Ollama returned HTTP 404 with a model-not-found message. The probe recorded the error and exited with code 1.

I then requested the installed model with a one-second socket timeout. The probe recorded `timed out` after 1.0008 seconds and exited with code 1. This measures the client's wait for a response.

A later request failed with `Connection refused` at my workstation's local port 11435. I reopened the SSH tunnel and retried. At 15:24 UTC on 14 October, the request returned HTTP 200 in 6.1051 seconds, including 4.1569 seconds loading the model. The probe exited with code 0.

- [Missing model](2026-10-14-ollama-missing-model.jsonl)
- [Socket timeout](2026-10-14-ollama-timeout.jsonl)
- [Closed tunnel](2026-10-14-ollama-after-errors.jsonl)
- [Successful retry](2026-10-14-ollama-after-errors-retry.jsonl)
