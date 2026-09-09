# Runbook: Bootstrap the Talos Cluster (Milestone 1)

Bring up the single-node Talos Kubernetes cluster on an x86_64 UEFI mini PC,
from bare hardware to a validated `kubectl get nodes`.

This runbook originally targeted a Raspberry Pi 5. That attempt hit an
unresolved upstream limitation (stock Talos images can't bring up Ethernet
on the Pi 5's RP1 southbridge) — see
[ADR-002's 2026-09-09 update](../adr/0002-use-talos-linux.md#update--2026-09-09-first-target-changed-to-x86-mini-pc)
for details. The Pi 5 is being repurposed as an Ubuntu + kubeadm node for
CKA practice instead.

## Prerequisites

- `talosctl` and `kubectl` installed locally, matching versions (check
  `talosctl version --client` against the Talos version you flash).
- An x86_64 mini PC with UEFI firmware (most business desktops/mini PCs from
  the last decade qualify — Intel NUCs, Dell OptiPlex Micro, HP
  EliteDesk/ProDesk SFF, etc.) and an internal disk (NVMe/SATA) to install
  onto.
- A USB drive (2 GB+) to boot the installer from.
- A wired network connection with DHCP available, and either a way to read
  the router's DHCP lease table or a monitor for the first boot.
- A reserved/static IP (or DHCP reservation) for the node, decided *before*
  generating config — it goes into `machine.certSANs` in
  [`talos/patches/controlplane.yaml`](../../talos/patches/controlplane.yaml)
  and can't be added later without regenerating certificates.

## 1. Prepare BIOS/UEFI settings

1. Enter BIOS/UEFI setup on the mini PC.
2. Confirm the boot mode is **UEFI**, not Legacy/CSM — Talos' Metal installer
   is a UEFI-only boot path.
3. Disable **Secure Boot** for now. Talos supports Secure Boot via signed UKI
   images, but that's an added-complexity path worth revisiting later, not
   for first bring-up.
4. Set the boot order to prioritize USB so the installer media boots first.
5. Confirm the wired NIC is enabled (Talos doesn't do anything with Wi-Fi).

## 2. Build and flash the Talos installer image

1. Go to [Image Factory](https://factory.talos.dev), select **Metal**,
   **amd64**, no overlay, and the Talos version you intend to run. Note the
   schematic ID it gives you.
2. Update `machine.install.image` in
   [`talos/patches/minipc.yaml`](../../talos/patches/minipc.yaml) with that
   schematic ID and version, and confirm `machine.install.disk` matches your
   target device (`/dev/nvme0n1` or `/dev/sda`).
3. Download the ISO (`metal-amd64.iso`) from Image Factory and write it to
   the USB drive:

   ```sh
   sudo dd if=metal-amd64.iso of=/dev/sdX bs=4M status=progress conv=fsync
   ```

   (Rufus or balenaEtcher work fine too if you're doing this from a desktop
   OS with a GUI.)

## 3. First boot — find the node

Insert the USB drive, power on the mini PC, and give it a minute to boot
into Talos maintenance mode (no OS installed yet, API-only). Find its IP one
of:

- Monitor: maintenance mode prints the DHCP-assigned IP directly to the
  console.
- Your router/OPNsense DHCP lease table, looking for the new client.

Confirm it's reachable and in maintenance mode:

```sh
talosctl -n <maintenance-ip> version
talosctl -n <maintenance-ip> get disks --insecure
```

The second command lists real disk paths — use it to double-check
`machine.install.disk` in `talos/patches/minipc.yaml` before applying
config.

## 4. Generate, apply, and bootstrap

From the repo root, using the endpoint IP you reserved in the prerequisites:

```sh
scripts/bootstrap-talos.sh generate <endpoint-ip>
scripts/bootstrap-talos.sh apply <maintenance-ip>
# wait for the node to install and reboot (watch the monitor, or poll):
talosctl -n <endpoint-ip> version
scripts/bootstrap-talos.sh bootstrap <endpoint-ip>
scripts/bootstrap-talos.sh kubeconfig <endpoint-ip>
```

Or run all four in sequence with `scripts/bootstrap-talos.sh all <endpoint-ip>`.

This writes generated secrets to `talos/secrets/` and a kubeconfig to
`./kubeconfig` — both gitignored. Never commit them.

Once installed, remove the USB drive so subsequent boots go straight to the
internal disk.

## 5. Validate

```sh
export KUBECONFIG=$(pwd)/kubeconfig
kubectl get nodes -o wide
talosctl --talosconfig talos/secrets/talosconfig -n <endpoint-ip> health
talosctl --talosconfig talos/secrets/talosconfig -n <endpoint-ip> dashboard
```

Milestone 1 is done when `kubectl get nodes` shows the node `Ready` and
`talosctl health` reports no errors.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| USB drive not offered as a boot option | BIOS still in Legacy/CSM mode — recheck step 1. |
| "Secure Boot violation" or similar at boot | Secure Boot still enabled — disable it in BIOS, or switch to a Secure-Boot-signed Image Factory schematic. |
| Boots to USB but nothing happens on the network | Wrong DHCP assumptions, or a NIC without in-kernel driver support (rare on standard onboard NICs, more common with add-in Realtek cards) — check the monitor for boot errors. |
| `apply-config` succeeds but node never comes back on the endpoint IP | Wrong `machine.install.disk` in `minipc.yaml` (install failed) — reconnect the monitor to see the install log, or re-check with `get disks --insecure` from a fresh maintenance boot. |
| `bootstrap` hangs or errors | Ran before the node finished installing/rebooting after `apply-config` — wait longer and retry; `bootstrap` is only ever run once per cluster. |
| `kubectl get nodes` shows `NotReady` indefinitely | CNI or kubelet issue — `talosctl -n <ip> dashboard` and `talosctl -n <ip> logs kubelet` for detail. |

## Recovery

To start over on the same hardware: `talosctl -n <ip> reset` wipes the node
back to maintenance mode. Delete `talos/secrets/` and `./kubeconfig` locally
and repeat from step 3 (or step 2 if you're also re-flashing).
