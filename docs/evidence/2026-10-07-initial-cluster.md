# Initial cluster evidence

Date: 2026-10-07
Location: Prague
Hardware: Raspberry Pi 5 8 GB with ADATA SU650 512 GB SATA SSD over USB

## Host

- Ubuntu 24.04.5 LTS
- Architecture: aarch64
- Root filesystem: /dev/sda2, ext4, USB SSD
- Available memory after boot: 7.4 GiB
- Available root storage: 448 GiB
- Required cgroups: present

## Bootstrap

- K3s: v1.36.5+k3s1
- Node: pi-lab
- Node status: Ready
- Secrets encryption: Enabled
- Encryption hashes: All hashes match
- First Ansible run: 23 successful tasks, 9 changes, 0 failures
- Second Ansible run: 22 successful tasks, 0 changes, 0 failures
- Reboot test: K3s active and node Ready after reboot

## Application

- Application: Podinfo
- Initial version: 6.14.1
- Updated version: 6.15.0
- Replicas: 2
- Service: ClusterIP on port 9898
- Ingress host: podinfo.lab.test
- Readiness endpoint: HTTP 200
- Metrics endpoint: available

## Rolling update

The application was updated from Podinfo 6.14.1 to 6.15.0. Both replicas became Ready after the update.

## Failed rollout

The readiness path was intentionally changed from `/readyz` to `/not-ready`.

Observed behavior:

- One new replica was created.
- The new replica stayed unready.
- Two previous replicas remained Ready.
- Deployment condition became `ProgressDeadlineExceeded`.
- Ingress continued returning HTTP 200.

The readiness path was restored through Git with:

```bash
git restore kubernetes/base/deployment.yaml
