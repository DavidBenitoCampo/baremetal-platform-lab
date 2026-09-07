# Runbook: Bootstrap the Talos Cluster (Milestone 1)

Bring up the single-node Talos Kubernetes cluster on the Raspberry Pi 5, from
bare hardware to a validated `kubectl get nodes`.

## Prerequisites

- `talosctl` and `kubectl` installed locally, matching versions (check
  `talosctl version --client` against the Talos version you flash).
- Raspberry Pi 5, 8 GB, with an NVMe drive (or SD card as a fallback) as boot
  media.
- A wired network connection with DHCP available, and either a way to read
  the router's DHCP lease table or an HDMI monitor for the first boot.
- A reserved/static IP (or DHCP reservation) for the node, decided *before*
  generating config — it goes into `machine.certSANs` in
  [`talos/patches/controlplane.yaml`](../../talos/patches/controlplane.yaml)
  and can't be added later without regenerating certificates.

## 1. Prepare Pi 5 boot firmware

The Pi 5 does not use a Talos SBC overlay the way the Pi 4 does. It boots
through UEFI firmware (the [pftf/RPi5](https://github.com/pftf/RPi5) project)
and then chain-loads a generic arm64 installer, same as a UEFI x86 box would.

1. Flash the RPi5 UEFI firmware release onto an SD card (or update the
   onboard EEPROM per that project's instructions) so the board can boot
   from NVMe/USB in UEFI mode.
2. Confirm in `raspi-config`/`rpi-eeprom-config` (or the UEFI firmware's own
   menu) that NVMe/USB boot order is enabled, if you're booting Talos from
   NVMe rather than the SD card.

Verify this section against the current
[Talos SBC install docs](https://www.talos.dev/latest/talos-guides/install/single-board-computers/)
before flashing — Pi 5 support has changed across Talos releases and this
runbook may lag behind it.

## 2. Build and flash the Talos installer image

1. Go to [Image Factory](https://factory.talos.dev), select **Metal**,
   **arm64**, no SBC overlay, and the Talos version you intend to run. Note
   the schematic ID it gives you.
2. Update `machine.install.image` in
   [`talos/patches/pi5.yaml`](../../talos/patches/pi5.yaml) with that
   schematic ID and version, and confirm `machine.install.disk` matches your
   target device (`/dev/nvme0n1` or `/dev/mmcblk0`).
3. Download the corresponding disk image (`metal-arm64.raw.xz`) from Image
   Factory and write it to the boot media:

   ```sh
   xz -d -c metal-arm64.raw.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
   ```

## 3. First boot — find the node

Insert the media, power on the Pi 5, and give it a minute to boot into Talos
maintenance mode (no OS installed yet, API-only). Find its IP one of:

- HDMI monitor: maintenance mode prints the DHCP-assigned IP directly to the
  console.
- Your router/OPNsense DHCP lease table, looking for the new client.

Confirm it's reachable and in maintenance mode:

```sh
talosctl -n <maintenance-ip> version
talosctl -n <maintenance-ip> get disks --insecure
```

The second command lists real disk paths — use it to double-check
`machine.install.disk` in `talos/patches/pi5.yaml` before applying config.

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
| Nothing on HDMI, no DHCP lease appears | UEFI firmware not installed correctly, or boot order doesn't include NVMe/USB — recheck step 1. |
| `talosctl -n <ip> version` times out in maintenance mode | Wrong IP, or the node hasn't reached the network stage yet — check the monitor for boot errors. |
| `apply-config` succeeds but node never comes back on the endpoint IP | Wrong `machine.install.disk` in `pi5.yaml` (install failed) — reconnect the monitor to see the install log, or re-check with `get disks --insecure` from a fresh maintenance boot. |
| `bootstrap` hangs or errors | Ran before the node finished installing/rebooting after `apply-config` — wait longer and retry; `bootstrap` is only ever run once per cluster. |
| `kubectl get nodes` shows `NotReady` indefinitely | CNI or kubelet issue — `talosctl -n <ip> dashboard` and `talosctl -n <ip> logs kubelet` for detail. |

## Recovery

To start over on the same hardware: `talosctl -n <ip> reset` wipes the node
back to maintenance mode. Delete `talos/secrets/` and `./kubeconfig` locally
and repeat from step 3 (or step 2 if you're also re-flashing).
