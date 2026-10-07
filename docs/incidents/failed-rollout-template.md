# Failed readiness rollout

Status: exercise planned, results pending.

## Trigger

Proposed fault: set the readiness probe to unused port 9990 while leaving the
application serving port unchanged. Use maxSurge=1 and maxUnavailable=0.

## Observed impact

Fill the actual HTTP failed attempt count, sample count, and time window.
No business outage or customer count is assumed.

## Detection and timeline

Record the merge, first unready Pod, stalled Deployment condition, Flux status,
Git revert, ready state, and stable HTTP recovery times.

## Cause and recovery

Explain the observed cause using the manifest diff and events.
Record the Git revert and CI result. Kubernetes reports a stalled rollout and
does not choose an automatic rollback.

## Prevention and limits

Explain which validation or release check addresses the error.
State the one host boundary and low load test conditions.
