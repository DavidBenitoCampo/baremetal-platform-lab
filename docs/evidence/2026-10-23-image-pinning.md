# Image pinning and CI enforcement

Repository review date: 23 October 2026.
Source revision: `5095365ba73d811d0350e04b5a673330614f5128`.

This note summarizes operator outputs pasted in chat during the image-pinning
work and a later read-only review of GitHub. It is not an independent live
cluster inspection. The full registry JSON and terminal transcripts were not
saved in this repository during the exercise.

## Repository configuration

Six application and monitoring Deployments, four Flux controller Deployments,
and the denial-test Job reference SHA256 image index digests. The full image
references are recorded in [versions.yaml](../../versions.yaml).

Flux controller overrides live in
[the bootstrap Kustomization](../../clusters/pi/flux-system/kustomization.yaml).
Its image transformer applies digests while rendering the upstream generated
controller manifest. Raw tags in `gotk-components.yaml` do not describe the
final rendered controller images.

The operator queried the running Pods' `imageID` values, then used
`docker manifest inspect repository@sha256:...` to inspect those indexes.
Each returned index included a Linux ARM64 manifest. The Python image index
also serves the denial-test Job.

These checks establish the inspected index references and advertised platform
support. They do not establish publisher signature verification, absence of
vulnerabilities, or indefinite registry availability. K3s-packaged system images
are outside this repository-managed pinning scope.

## Operator-reported runtime results

| Component | Reported result |
| --- | --- |
| Podinfo | Deployment used the pinned reference; rollout succeeded; HTTP 200 |
| Ollama | Flux applied `fc00e0a1`; rollout succeeded; `qwen2.5:0.5b` replied `OK.` |
| Inference probe | Flux applied `5d577636`; rollout succeeded; five checks returned HTTP 200 with 16 generated tokens |
| Probe durations | 1.528 to 1.576 seconds in the pasted five-request sample |
| Monitoring | Flux applied `383ca2f5`; Prometheus, Grafana, and kube-state-metrics rollouts succeeded |
| Scrape and UI health | Four `up` query values were 1; Grafana health reported database `ok`, version 13.2.2 |
| Flux controllers | All four Deployment image references included the expected digests; all five Kustomizations were Ready and unsuspended at `227b2e70` |
| Denial-test Job | Image reference pinned; the Job was not rerun as part of pinning |

The pasted monitoring response contains a transcription anomaly in one target
hostname. Its four reported values were 1. This note does not reproduce that
response as a pristine Prometheus capture.

## CI behavior

[The workflow](../../.github/workflows/validate.yml) renders Podinfo, Ollama,
the inference probe, monitoring, and Flux. The
[digest checker](../../ci/check_image_digests.py) reads those five files and
the denial-test Job. It checks regular, init, and ephemeral container lists.

The operator reported `11 container references checked, 0 failures` locally.
A temporary Pod using `python:3.12.15-slim-bookworm` without a digest reported
one failure and exited 1. That temporary Pod was not deployed. This negative
test was manual; it is not a retained automated test fixture.

The check enforces reference syntax with a 64-character lowercase hexadecimal
SHA256 suffix. Inputs with no containers fail. It performs no registry request.
The latest `validate` check on the reviewed main revision reported success.

Flux custom resources are checked against the CRD schemas committed in
`gotk-components.yaml`. The validator also verifies rejection of an injected
unknown `spec` field for each valid resource. This local schema check is separate
from Kubernetes admission and controller health checks.

## Merge controls

The GitHub API review on 23 October found `main-protection` active for the
default branch, with no bypass actors. It requires pull requests, zero review
approvals, resolved review threads, and the `validate` status check from GitHub
Actions (integration ID 15368). Branches must be up to date. Force pushes and
deletion are blocked.

[Ruleset](https://github.com/DavidBenitoCampo/baremetal-platform-lab/rules/25429356)

## Remaining work

The six timeouts in the earlier release exercise remain unexplained. Image
pinning does not resolve them or establish uninterrupted availability.
A successful version update still needs continuous HTTP measurement.
VPN persistence and denial checks, wider NetworkPolicy verification, independent
monitoring, notification delivery, and broader backup coverage remain open.
