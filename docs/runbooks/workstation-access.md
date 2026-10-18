# Persistent workstation access

This setup runs on the Linux workstation. A systemd user service starts
at login and owns both SSH tunnels. Closing a terminal leaves the service
running. When SSH exits, systemd retries after five seconds, including
while the VPN or Pi is unavailable.

| Local listener | Destination reached from the Pi |
| --- | --- |
| `127.0.0.1:16443` | Kubernetes API, `127.0.0.1:6443` |
| `127.0.0.1:18082` | Traefik Ingress, `10.0.1.16:80` |

Both listeners stay on workstation loopback. The Tailscale rule still needs
only SSH port 22. The existing SSH key and VPN kubeconfig stay outside Git.

## Install once

Use your normal workstation account. Required commands are OpenSSH at
`/usr/bin/ssh`, a systemd user manager, `ss`, `kubectl`, and `curl`.
Install Flux separately if you use `pi-flux`.

Keep the existing key at `~/.ssh/pi_lab_ed25519` and the existing kubeconfig
at `~/.kube/pi-lab-vpn.yaml`. The kubeconfig must use server
`https://127.0.0.1:16443`, with its configured TLS server name `10.0.1.16`
and certificate verification enabled.

For an encrypted key, load the key into your desktop SSH agent first:

```bash
ssh-add "$HOME/.ssh/pi_lab_ed25519"
```

Stop the earlier manual tunnels with Ctrl+C in their own terminals. The
installer refuses to take over occupied ports unless the managed service
is already active. Other SSH sessions do not need stopping.

From the repository root:

```bash
sudo systemctl enable --now tailscaled
bash scripts/install-workstation-access.sh
```

The installer checks noninteractive SSH using the known host key, copies
the service into the user systemd directory, installs three helpers into
`~/.local/bin`, and enables and starts the service. The default kubeconfig
and shell startup files keep their contents.

Rerunning the installer replaces these managed files and restarts the
service. Run installation outside an HTTP evidence capture.

If `~/.local/bin` is missing from your PATH, add this line once to
`~/.bashrc` and run the same line in the current Bash shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

After SSH connects:

```bash
pi-lab-check
pi-kubectl get nodes
pi-flux get kustomizations -A
```

## Daily use

Use `pi-kubectl` and `pi-flux` for the Pi. Each helper passes the VPN
kubeconfig explicitly. Another terminal's `KUBECONFIG` value does not
select a different cluster. Optional `PI_LAB_KUBECONFIG` selects another
local copy of the Pi config for these helpers and the check.

Run `pi-lab-check` before an evidence capture. The check requires an active
tunnel service, the expected API endpoint, a reachable API, a Ready
`pi-lab` node, and Podinfo HTTP 200 through port 18082. Failure returns a
nonzero exit status.

Keep the HTTP logger running during the exercise. Verify fresh timestamps
and increasing indices before introducing a fault and before recovery.
A successful preflight describes the check time.

## Diagnose a connection failure

```bash
systemctl --user status pi-lab-tunnels.service --no-pager
journalctl --user -u pi-lab-tunnels.service -n 50 --no-pager
ss -ltnp '( sport = :16443 or sport = :18082 )'
```

SSH stderr and process exits appear in the journal. `Restart=always`
restarts an exited SSH process. Keepalive settings detect an unresponsive
peer after roughly 45 seconds without replies. An unavailable API or HTTP
backend still fails its own check while SSH is connected.

For an encrypted key, automatic access also depends on your desktop agent
loading the key at login. The installer imports the current
`SSH_AUTH_SOCK`. If the agent changes sockets, load the key and refresh the
service environment:

```bash
ssh-add "$HOME/.ssh/pi_lab_ed25519"
systemctl --user import-environment SSH_AUTH_SOCK
systemctl --user restart pi-lab-tunnels.service
```

No key passphrase is stored. To stop automatic access deliberately:

```bash
systemctl --user disable --now pi-lab-tunnels.service
```

## Verify persistence on the workstation

On 18 October, I verified installation and automatic restart after terminating
SSH. The service reported enabled and active. Its main process changed from
PID 40318 to PID 108576, and the restart counter increased from zero to one.
After restart, the API, node, and Podinfo checks passed.

The [operator-provided transcript](../evidence/2026-10-18-workstation-access.txt)
records the outputs pasted in chat. Exact restart duration, workstation reboot,
terminal closure, and network disconnect checks have not been recorded.
CI checks syntax and helper behavior without contacting the Pi or starting
a user service.

1. Run `pi-lab-check`, close the terminal, open a new terminal, and repeat
   the check and `pi-kubectl get nodes`.
2. Reboot the workstation, log in, and repeat both checks after Tailscale
   and SSH reconnect.
3. Outside an evidence capture, test automatic SSH restart:

   ```bash
   systemctl --user kill --kill-whom=main --signal=TERM pi-lab-tunnels.service
   ```

   After SSH reconnects, run `pi-lab-check` and inspect the journal. Save
   timestamps, the replacement SSH process ID, and the successful checks.
   An intentional `systemctl stop` leaves the service stopped.
4. In a separate access test, disconnect and reconnect the workstation's
   network, then verify automatic recovery with the same checks.

Save the observed results before marking reboot persistence or reconnect
behavior as tested. The service starts at login.

## References

- [OpenSSH forwarding and keepalives](https://man.openbsd.org/ssh_config)
- [systemd service configuration](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
- [Kubernetes kubeconfig selection](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
