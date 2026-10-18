# Podinfo failed release and Git recovery

Date: 18 October 2026.

I tested a failed readiness release through Git and Flux, then restored the
working configuration in Git. The Deployment and Flux recovered. The HTTP
recordings contain six timeouts after the Deployment reported recovery.
Their cause is still unknown.

## Change and observed state

[PR #22](https://github.com/DavidBenitoCampo/baremetal-platform-lab/pull/22)
changed only the readiness probe port from `http` to unused port `9990`.
The application kept serving on port 9898. The image, liveness probe,
startup probe, and replica count kept their configuration.

The Pi Deployment requested two replicas with `maxUnavailable: 0` and
`maxSurge: 1`. The failed snapshot showed two previous Pods Ready and one
new Pod unready. The Deployment reported two available replicas and
`Progressing=False` with reason `ProgressDeadlineExceeded`.

Flux fetched fault revision `33b9066d`, but the health check failed.
The manual reconciliation command reached its four-minute timeout.
The saved Kustomization JSON separates the last successful revision,
`848901cb`, from the attempted revision, `33b9066d`.

[PR #23](https://github.com/DavidBenitoCampo/baremetal-platform-lab/pull/23)
restored readiness port `http`. The recovered Deployment snapshot showed
two updated, Ready, and available replicas, with
`Progressing=True` and reason `NewReplicaSetAvailable`. The saved Flux
status showed `Ready=True` at recovery revision `5b42bd0e`.

CI passed for the [fault change](https://github.com/DavidBenitoCampo/baremetal-platform-lab/actions/runs/39160811779)
and [recovery change](https://github.com/DavidBenitoCampo/baremetal-platform-lab/actions/runs/39162919767).
The unused readiness port is valid Kubernetes configuration. Runtime
health checks exposed the failure after deployment.

## HTTP measurements

The probe ran from the workstation through the SSH tunnel and Ingress to
`http://127.0.0.1:18082/readyz`, with Host `podinfo.lab.test`. Requests ran
once per second with a 0.8-second timeout. Both probe stderr files are empty.

| Capture | Attempts | HTTP 200 | Timeouts | p95 attempt latency | Maximum scheduling delay |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Failed release](../evidence/2026-10-18-podinfo-rollout-http.jsonl) | 1,800 | 1,800 | 0 | 28.05 ms | 2.17 ms |
| [Recovery](../evidence/2026-10-18-podinfo-recovery-http.jsonl) | 1,200 | 1,194 | 6 | 28.19 ms | 2.69 ms |

The first capture runs from 19:52:48.878092 to 20:22:47.878359 UTC.
The second runs from 20:23:28.513592 to 20:43:27.513906 UTC.
There are 40.635233 seconds between the last sample start in the first file
and the first sample start in the second. The recordings leave this gap
between their sampled windows.

The [six failed samples](../evidence/2026-10-18-podinfo-recovery-failed-samples.jsonl)
have consecutive indices 291 through 296. Their request start times run
from 20:28:19.513888 to 20:28:24.513618 UTC. Each reports `timed out`, with
attempt latency between 801.13 and 801.89 ms. Sample 290 returned HTTP 200
in 24.88 ms. Sample 297 returned HTTP 200 in 698.28 ms.

The recorded timestamps place the first timeout about three minutes and
12 seconds after the Deployment reported recovery. The
[SSH service journal](../evidence/2026-10-18-podinfo-recovery-tunnel-journal.txt)
contains no entries for 20:23 through 20:44 UTC. A later access check passed
for the API, Ready node, and Podinfo HTTP 200. These observations do not
identify the cause of the earlier timeouts.

## Timeline

Europe/Prague was UTC+2 on this date. Condition times come from the saved
cluster snapshots. HTTP times describe request starts.

| UTC | Europe/Prague | Recorded event |
| --- | --- | --- |
| 20:01:27 | 22:01:27 | Fault PR #22 merged as `33b9066d` |
| 20:04:09 | 22:04:09 | Deployment condition changed to `ProgressDeadlineExceeded` |
| 20:22:43 | 22:22:43 | Saved Flux conditions record another failed health check |
| 20:24:17 | 22:24:17 | Recovery PR #23 merged as `5b42bd0e` |
| 20:25:07 | 22:25:07 | Deployment condition changed to `NewReplicaSetAvailable` |
| 20:28:19.514 to 20:28:24.514 | 22:28:19.514 to 22:28:24.514 | Six consecutive requests started and reached their timeout |
| 20:30:14 | 22:30:14 | Operator started the saved manual recovery confirmation |

The manual recovery confirmation started after the Deployment had already
reported recovery. The brief duration in the later failed Flux health-check
message describes a retry against an already stalled Deployment.

## Saved evidence

| Observation | Files |
| --- | --- |
| Failed state | [Deployment](../evidence/2026-10-18-podinfo-fault-deployment.json), [Pods](../evidence/2026-10-18-podinfo-fault-pods.txt), [Flux JSON](../evidence/2026-10-18-podinfo-fault-kustomization.json), [Flux status](../evidence/2026-10-18-podinfo-fault-flux.txt), [reconcile](../evidence/2026-10-18-podinfo-fault-reconcile.txt) |
| Recovered state | [Deployment](../evidence/2026-10-18-podinfo-recovered-deployment.json), [Flux status](../evidence/2026-10-18-podinfo-recovered-flux.txt), [rollout](../evidence/2026-10-18-podinfo-recovered-rollout.txt), [reconcile](../evidence/2026-10-18-podinfo-recovered-reconcile.txt), [confirmation start](../evidence/2026-10-18-podinfo-recovery-start.txt) |
| Probe stderr | [First capture](../evidence/2026-10-18-podinfo-rollout-http.stderr.txt), [second capture](../evidence/2026-10-18-podinfo-recovery-http.stderr.txt) |
| Workstation checks | [Operator-provided transcript](../evidence/2026-10-18-workstation-access.txt) |

Before the release exercise, I verified the managed SSH service and tested
automatic restart by terminating SSH. The process changed from PID 40318
to PID 108576, and the restart counter increased from zero to one. API,
node, and Podinfo checks passed after restart. The transcript was assembled
from outputs pasted in chat. Exact restart duration, workstation reboot,
and network disconnect recovery have not been recorded.

## Limits and follow-up

This exercise used one Pi and one request per second. The results describe
sampled requests through the workstation access path. The six timeouts
and recording gap prevent a claim of uninterrupted successful requests
throughout the exercise.

For the next release exercise, keep one capture running from before the
fault merge until after recovery. Collect matching Ingress and host logs
when requests time out. A successful version update still needs a separate
continuous HTTP measurement.
