# baremetal-platform-lab

Kubernetes release and recovery lab on one Raspberry Pi 5 with SSD storage.

The project models a small team releasing an internal web service, diagnosing a
failed change, and restoring a defined set of cluster state.

## Status

This starter package supplies first setup automation, a read only preflight,
an HTTP measurement script, and documentation templates. No Pi deployment,
release, alert, or restore result has been observed in this session.

| Area | Status |
| --- | --- |
| Fresh host and K3s automation | Prepared, execution on Pi pending |
| Application and Ingress | Planned for weeks 3 and 4 |
| CI and Flux | Planned for weeks 5 and 6 |
| Release and recovery evidence | Pending |
| Monitoring and alerting | Planned for weeks 8 and 9 |
| Independent backup and restore | Planned for weeks 11 and 12 |

## Hardware and scope

One Raspberry Pi 5, 8 GB RAM, existing 512 GB SATA SSD with a USB adapter, active
cooling, and spare microSD. Use Ubuntu Server 24.04 LTS ARM64 on the SSD.

Two application Pods demonstrate rolling updates and Pod replacement.
Pi failure stops all workloads and monitoring. The restore exercise covers K3s
control plane state, credentials, and configuration. Persistent application
data, monitoring history, OS reimaging, and hardware replacement are excluded.

The backup destination needs an existing computer with independent storage.
Access to this destination is a prerequisite to verify.

## First setup

Read [the bootstrap procedure](docs/runbooks/bootstrap.md), inspect
[the host playbook](ansible/host.yml), and run the preflight on the Pi.

The playbook uses a pinned K3s release, enables encryption of Kubernetes Secrets,
and keeps kubeconfig permissions restricted. The playbook refuses an unrelated
existing K3s installation or a version mismatch. Version upgrades need a separate
reviewed backup and change procedure.

The initial host uses the default SQLite datastore. No `cluster-init` flag is set.

```bash
cp ansible/inventory.example.ini ansible/inventory.ini
ansible-playbook -i ansible/inventory.ini ansible/host.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/host.yml --ask-become-pass
ssh lab@PI_ADDRESS sudo k3s kubectl get nodes -o wide
ssh lab@PI_ADDRESS sudo k3s kubectl get pods -A
ansible-playbook -i ansible/inventory.ini ansible/host.yml --ask-become-pass
```

Keep `inventory.ini` untracked. Replace the example address and user.

## Measurements

Run the logger from another computer so host failure does not erase the test log.
The script uses Python's standard library and writes JSON lines.

```bash
python3 scripts/http_probe.py http://PI_ADDRESS/version \
  --host app.lab.test --count 600 --interval 1 --timeout 0.8 \
  > docs/evidence/release-probe.jsonl
```

Each sample records status, transport error, latency, schedule delay, and UTC time.
The last record contains totals. These are synthetic low load measurements.
Do not infer production availability from this exercise.

## Evidence and decisions

Use [the evidence template](docs/evidence/result-template.md),
[the incident template](docs/incidents/failed-rollout-template.md), and
[the job tracker](career/job-tracker.md).

Read [ADR 001](docs/adr/001-single-node.md) and
[ADR 002](docs/adr/002-ssd.md). Add a decision when a specific constraint or
observed failure changes the implementation.

## Planned repository areas

`kubernetes/` holds app bases, Pi overlays, namespace RBAC, and access policies.
`clusters/pi/` holds Flux bootstrap and Kustomization resources.
`monitoring/` holds metrics, alerts, and dashboard provisioning.
`.github/workflows/` holds validation. These areas start as design descriptions.

## Sources

Official documentation checks, retrieved 2 October 2026, appear in
[sources.md](docs/sources.md). Runtime verification on the Pi is still required.
