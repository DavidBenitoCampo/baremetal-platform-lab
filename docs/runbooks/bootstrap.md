# Setting up the Pi

This is the setup I used for the Raspberry Pi 5: Ubuntu Server on the USB SSD, SSH key access, and K3s installed through Ansible.

The playbook prepares the host and installs K3s. Application deployments, the planned LLM service, GitOps, and monitoring are separate steps.

If the cluster already works, go straight to [Check the cluster](#check-the-cluster). Keep the existing installation.

## Before starting

The Pi needs Ubuntu Server 24.04 LTS ARM64, SSD storage, cooling, a suitable power supply, and a network connection. Back up any files needed from the SSD before writing the Ubuntu image.

On the workstation, have Ansible installed and verify SSH key access to a Pi user with sudo access. For this lab, the user is `lab` and the address is `10.0.1.16`. Change the address and key path for another setup.

Run the workstation commands from the repository root:

```bash
PI_ADDRESS=10.0.1.16
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo cloud-init status --wait'
```

Cloud-init should finish before host preparation. Use a DHCP reservation or another stable address so workstation access keeps working after a reboot.

## Check the host

Copy and run the preflight script:

```bash
scp -i ~/.ssh/pi_lab_ed25519 scripts/preflight.sh lab@"${PI_ADDRESS}":/tmp/preflight.sh
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'bash /tmp/preflight.sh'
```

Look for `aarch64`, an SSD-backed root filesystem, and the memory cgroup controller. In this lab, root is `/dev/sda2`. Record available memory and disk space before adding workloads.

## Run Ansible

For a new setup, create the local inventory:

```bash
cp ansible/inventory.example.ini ansible/inventory.ini
```

Edit the address, user, and SSH key path in `ansible/inventory.ini`. Keep an existing working inventory unchanged. Git ignores this file.

Read [the playbook](../../ansible/host.yml), then check its syntax and run the host preparation:

```bash
ansible-playbook -i ansible/inventory.ini ansible/host.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/host.yml
```

The `lab` user in this setup has passwordless sudo. Add `--ask-become-pass` to the execution command when the chosen user needs a sudo password.

The playbook checks the OS, root storage, cgroups, and existing K3s state before installing anything. The host tasks load the required kernel modules, configure forwarding, and write the K3s configuration before starting the service.

The current pinned release is `v1.36.5+k3s1`. This single-server setup uses SQLite and enables Kubernetes Secrets encryption. The playbook refuses an unrelated existing cluster or a different installed K3s version.

## Check the cluster

Set the address again if using a new terminal:

```bash
PI_ADDRESS=10.0.1.16
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo k3s kubectl get nodes -o wide'
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo k3s kubectl get pods -A'
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo k3s secrets-encrypt status'
```

The node should report `Ready`. The running system Pods should be healthy. Completed Traefik installation Jobs are expected. Secrets encryption should report `Enabled`.

Run the playbook a second time:

```bash
ansible-playbook -i ansible/inventory.ini ansible/host.yml
```

For an unchanged host, expect zero changes and zero failures. The recorded second run in this lab matched both checks.

## Test a reboot

Once the cluster is healthy, reboot the Pi:

```bash
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo reboot'
```

The SSH connection will close. Wait for SSH access to return, then check the service and node:

```bash
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo systemctl is-active k3s'
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo k3s kubectl wait --for=condition=Ready node/pi-lab --timeout=120s'
ssh -i ~/.ssh/pi_lab_ed25519 lab@"${PI_ADDRESS}" 'sudo k3s kubectl get pods -A'
```

Save the results in [the cluster evidence record](../evidence/2026-10-07-initial-cluster.md). The reboot test passed on 7 October 2026.

## Keep access local

Use SSH keys and verify key access before disabling SSH password authentication or root SSH access. Keep the private key, kubeconfig, and real inventory outside Git.

Keep SSH and Kubernetes administration on the trusted lab network. Use port-forwarding or SSH tunnels for admin interfaces, with no router forwarding from the internet.

Firewall rules depend on the actual network. Allow the chosen admin source and preserve Kubernetes Pod, Service, and forwarding traffic. Keep an SSH session open while changing rules, then test Pod DNS, image pulls, and application routing. The host playbook does not configure these source restrictions.

## If K3s does not start

SSH into the Pi and check the service, logs, and storage:

```bash
sudo systemctl status k3s --no-pager
sudo journalctl -u k3s -n 100 --no-pager
findmnt -no SOURCE,FSTYPE /
df -h /
cat /sys/fs/cgroup/cgroup.controllers
```

Check power and the USB connection if the SSD disappears or disconnects. For image-pull errors, check DNS and registry access. Fix the reported cause before considering a reinstall.

K3s upgrades need their own procedure and a backup stored on another computer. The backup and restore exercise is still planned.
