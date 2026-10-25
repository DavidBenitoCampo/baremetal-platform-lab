# Podinfo rollout with workstation and internal HTTP probes

Date: 24 October 2026. Analysis: 25 October 2026.

I triggered a Podinfo rollout through Git and Flux by changing one Pod template
annotation. Both recordings covered the rollout. The workstation recorded
1,800 HTTP 200 responses. The internal Service probe recorded 1,799 HTTP 200
responses and one HTTP 503. The Deployment completed its rollout.

## Change and setup

[PR #37](https://github.com/DavidBenitoCampo/baremetal-platform-lab/pull/37)
added `lab.example.com/rollout-test: "2026-10-24-01"` to the Pod template.
It merged at 20:26:39 UTC as `1f1d5ebe`. Flux fetched and applied that revision.

This was a same-version rollout, not an application version upgrade. Both
Deployment snapshots reference Podinfo 6.15.0 with image index digest
`sha256:ec73780a8425f59ea49f5bc8cdff0d598805a224fbaa1f86c67a244f250fa9da`.
The Deployment requested two replicas, `maxUnavailable: 0`, and `maxSurge: 1`
on the single Pi. Generation advanced from 19 to 20. The saved after-state
reported two updated, Ready, and available replicas.

The workstation requested `http://127.0.0.1:18082/readyz` with Host
`podinfo.lab.test`, through Tailscale, the managed SSH tunnel, and Traefik.
A separate Job requested
`http://podinfo.platform-demo.svc.cluster.local:9898/readyz` directly through
the internal Service. Both used the repository's HTTP probe with one sequential
attempt per second, 1,800 attempts, and a 0.8-second timeout.

The Job used the pinned Python 3.12.15 image and a ConfigMap containing the probe
script. It ran outside Flux as temporary test equipment. Its saved status
reports one successful Pod and completion at 20:53:15 UTC. Job completion means
the script finished; HTTP failures are counted in its JSONL summary.

## Measurements

| Capture | Attempts | HTTP 200 | HTTP 503 | Transport errors | p95 attempt latency | Maximum scheduling delay |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Workstation | 1,800 | 1,800 | 0 | 0 | 66.85 ms | 3.26 ms |
| Internal Service | 1,800 | 1,799 | 1 | 0 | 11.73 ms | 18.75 ms |

Each log has 1,800 consecutively indexed samples and one final summary.
Recounted status totals, failure counts, and p95 values match both summaries.
The workstation stderr file is empty.

The workstation recording ran from 20:22:58.908328 to 20:52:57.908398 UTC.
The internal recording ran from 20:23:13.055378 to 20:53:12.055395 UTC.
They overlap throughout the rollout, but start about 14.147 seconds apart.
Within each second, the internal probe ran about 0.853 seconds before the
workstation probe. These are separate requests over different paths.

## Timeline

All times below are UTC on 24 October. Prague was UTC+2 on this date.

| UTC | Observation |
| --- | --- |
| 20:22:58.908 | First workstation sample |
| 20:23:13.055 | First internal sample |
| 20:26:26 | Saved pre-merge timestamp |
| 20:26:39 | PR #37 merged |
| 20:27:48.055 | Internal sample 275 returned HTTP 200 |
| 20:27:49.055 | Internal sample 276 returned HTTP 503 in 8.29 ms |
| 20:27:49.908 | Workstation sample 291 returned HTTP 200 in 68.61 ms |
| 20:27:50.055 | Internal sample 277 returned HTTP 200 |
| 20:27:59 | Deployment Progressing condition last updated with NewReplicaSetAvailable |
| 20:52:57.908 | Last workstation sample |
| 20:53:12.055 | Last internal sample |

The Progressing condition's `lastTransitionTime` remains 18 October because its
boolean value stayed True. The 24 October `lastUpdateTime` records the new
ReplicaSet progress update. Available=True has the same timestamp in both
snapshots. These snapshots do not provide a continuous condition history or
prove every request succeeded.

## Interpretation and limits

Saved events show the old ReplicaSet scaling down, containers stopping, and
old Pods returning readiness HTTP 503. A request reaching a terminating Pod
while endpoint updates propagate is a plausible explanation for the internal
503. The event table has relative ages rather than absolute timestamps, and the
HTTP probe did not record the serving Pod or response body. EndpointSlice
transitions and old-Pod application logs were not captured. The precise cause
therefore remains unconfirmed.

The workstation's successful sample about 0.853 seconds later does not conflict
with the internal failure. The probes used different paths and sampled at
different instants. A single failed sample does not establish an exact outage
duration. No transport timeouts occurred in these captures.

Traefik arguments inspected before the test showed INFO logging without an
explicit access-log flag. No per-request Ingress log is included in this
evidence. The earlier six transport timeouts after the 18 October recovery
remain unexplained; this HTTP 503 is a different observation.

The result demonstrates a completed same-version rollout with a measured
internal request failure. It does not support a claim of uninterrupted request
success or a continuously measured version upgrade. One Pi and one request per
second per probe do not establish production availability.

## Evidence

All raw files are in [the capture directory](20261024T202258Z-podinfo-rollout/).

- [Workstation samples](20261024T202258Z-podinfo-rollout/workstation-http.jsonl)
  and [stderr](20261024T202258Z-podinfo-rollout/workstation-http.stderr.txt).
- [Internal samples](20261024T202258Z-podinfo-rollout/internal-http.jsonl)
  and [probe Job snapshot](20261024T202258Z-podinfo-rollout/probe-job.json).
- Deployment [before](20261024T202258Z-podinfo-rollout/deployment-before.json)
  and [after](20261024T202258Z-podinfo-rollout/deployment-after.json).
- [Events](20261024T202258Z-podinfo-rollout/events.txt),
  [reconciliation](20261024T202258Z-podinfo-rollout/reconcile.txt),
  [rollout result](20261024T202258Z-podinfo-rollout/rollout.txt),
  and [pre-merge timestamp](20261024T202258Z-podinfo-rollout/pre-merge-utc.txt).

The files were captured on the workstation and pushed by the operator. This
analysis validates their contents without a new live cluster inspection.
The generic CI JSONL step currently scans only files directly under
`docs/evidence`; the nested captures above were parsed explicitly for this review.

## Follow-up

Inspect Podinfo's shutdown behavior before choosing a lifecycle change. For a
repeat test, retain serving-Pod identity where possible, timestamped endpoint
and Pod transitions, application logs, and both HTTP paths. Test any shutdown
change separately and compare the recordings. Preserve the earlier timeout
investigation as a separate open item.
