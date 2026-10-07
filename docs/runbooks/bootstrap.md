# Fresh cluster bootstrap

## Purpose

Install one pinned ARM64 K3s server on a fresh SSD based Ubuntu Server host.
This starter does not install the application, Flux, or monitoring.

## Prerequisites

Use Ubuntu Server 24.04 LTS ARM64, a stable PSU, cooling, SSD, and a trusted LAN.
Use an existing computer with Ansible, an SSH key, and sudo access to the Pi.
Use key login before disabling password or root SSH login. Store the inventory
locally. Keep a second existing computer disk available for the later backup test.

## OS and access

1. Preserve wanted old files and write the official Ubuntu ARM64 image to the
   selected SSD. Verify the selected disk before the write.
2. Boot the Pi, set a stable LAN address or DHCP reservation, and verify key SSH.
3. On the Pi, run `uname -m`, `findmnt -no SOURCE,FSTYPE /`, and `free -h`.
4. Copy `scripts/preflight.sh` to the Pi and run `bash preflight.sh`.

Expected architecture: aarch64. Root storage resolves to the SSD.
Record cgroup support and available memory.

## Explain and run Ansible

Read each task in `ansible/host.yml`. The prechecks refuse an unexpected OS,
microSD root, missing memory cgroups, unrelated K3s state, or a version mismatch.
The tasks install prerequisites, enable network forwarding, and write restricted
K3s settings. The pinned official installer validates the released binary.
The service starts only after configuration exists.

Inspect the installer at the pinned upstream tag before running the playbook.
Read release notes and record checksums during implementation.

```bash
cp ansible/inventory.example.ini ansible/inventory.ini
ansible-playbook -i ansible/inventory.ini ansible/host.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/host.yml --ask-become-pass
```

Change `YOUR_PI_IP`, the user, and private key path in the untracked inventory.
Use the actual sudo password when prompted. Use your existing Ansible installation
and record the version. No community collection is needed by this playbook.

## Verify

```bash
ssh lab@PI_ADDRESS sudo k3s kubectl get nodes -o wide
ssh lab@PI_ADDRESS sudo k3s kubectl get pods -A
ssh lab@PI_ADDRESS sudo k3s secrets-encrypt status
ansible-playbook -i ansible/inventory.ini ansible/host.yml --ask-become-pass
```

Expect one Ready ARM64 node, healthy packaged components, encryption enabled,
and zero changes on the repeated playbook run. Then reboot and check readiness.
Save actual outputs in a sanitized environment record.

## Access restrictions

Complete source restrictions before treating the lab as a finished security demo.
Use SSH keys, deny root login, and disable password SSH after verifying key access.
No WAN port forwarding belongs in this lab. Use SSH access for administrative tools.

A host firewall should allow your operator source to SSH and app HTTP, while
preserving the K3s Pod and Service CIDR paths and required forwarding. Follow the
K3s official networking requirements and test Pod DNS, registry access, and routing
after enabling the firewall. Record actual source IPs privately and retain a
rollback connection while changing access.

Use SSH tunnels for monitoring interfaces. Restrict the API to the chosen admin
path. The starter playbook does not silently choose your LAN trust range or
enable a firewall with guessed source addresses.

## Failure handling

Read `journalctl -u k3s` locally. Check cgroups, power, SSD mount, disk space,
and registry DNS. Repair the observed cause before reinstalling.
The playbook does not erase disks, delete cluster state, adopt an unrelated
cluster, or upgrade an existing version.
