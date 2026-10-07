# Exercise result

Status: not measured.

Exercise and date:
Operator:
Git revision:
OS and kernel:
K3s and Flux versions:
App image digest:
Number of ready replicas:
Network path and client computer:
Cached or uncached image:
HTTP endpoint and Host header:
Requests, interval, and timeout:
Clock synchronization:
Pi resource and power baseline:

## Procedure

Record the actual commands, fault, and recovery action without credentials.

## Target and observations

| Measurement | Proposed target | Observed result |
| --- | --- | --- |
| Deployment time | 180 seconds | Not measured |
| Detection delay | 90 seconds | Not measured |
| Alertmanager routing delay | 30 seconds | Not measured |
| Git recovery time | 180 seconds | Not measured |
| Pod replacement time | 60 seconds | Not measured |
| Drift correction time | 120 seconds | Not measured |
| Control plane state restore | 20 minutes | Not measured |
| Failed HTTP attempts | Exercise specific | Not measured |

## Timeline

| Event | UTC time | Evidence |
| --- | --- | --- |
| Healthy baseline | | |
| Fault or release | | |
| Detection | | |
| Recovery action | | |
| Ready state | | |
| 30 consecutive HTTP successes | | |

## Interpretation

State the repeat count, deviations, limits, and next action.
The state restore excludes OS reimage, failed hardware, application volumes,
Prometheus history, and Grafana local database state.
