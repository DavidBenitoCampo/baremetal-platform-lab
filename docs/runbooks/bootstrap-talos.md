# Runbook: Bootstrap the Talos Cluster (Milestone 1)

Bring up the single-node Talos Kubernetes cluster on the Raspberry Pi 5,
from bare hardware to a validated `kubectl get nodes`.

This runbook briefly pivoted to an x86 mini PC after the Pi 5 hit a boot
issue, then reverted once it turned out the issue had already been fixed
upstream — see
[ADR-002's update history](../adr/0002-use-talos-linux.md#update--2026-09-09-revised-pi-5-reinstated-as-first-target).
The mini PC guidance is still useful for later multi-node work (Milestone 6)
but isn't needed here.

**The one thing that actually matters for Pi 5 boot to work:** build the
image at Image Factory with the **`rpi_5`** overlay/profile
(`siderolabs/sbc-raspberrypi`) — not `rpi_generic` (that's for the Pi 4)
and not a no-overlay image. The wrong overlay produces a boot that gets
stuck at the U-Boot logo with a black screen and no network, which is
exactly what this project hit before finding the fix
([siderolabs/sbc-raspberrypi#71](https://github.com/siderolabs/sbc-raspberrypi/pull/71),
merged 2026-01-24).

## Prerequisites

- `talosctl` and `kubectl` installed locally, matching versions (check
  `talosctl version --client` against the Talos version you flash).
- Raspberry Pi 5, an external USB SSD as boot/install media, and a wired
  Ethernet connection.
- Strongly recommended: a USB-to-serial (UART) adapter on the GPIO pins.
  Given this exact hardware's history of silently failing past the U-Boot
  stage, don't rely on HDMI alone — serial is the only view into what's
  actually happening if something goes wrong again.
- A way to read the router's DHCP lease table (or the monitor/serial output)
  to find the node's IP on first boot.
- A reserved/static IP (or DHCP reservation) for the node, decided *before*
  generating config — it goes into `machine.certSANs` in
  [`talos/patches/controlplane.yaml`](../../talos/patches/controlplane.yaml)
  and can't be added later without regenerating certificates.

## 1. Update the Pi 5 bootloader EEPROM

This is a Raspberry Pi firmware concern, independent of Talos, but it's
worth doing before flashing anything: an outdated EEPROM has been linked to
boot failures on this board, and it also controls whether USB-attached
storage is even in the boot order.

Using `rpi-eeprom-update` (from an existing Raspberry Pi OS install, or the
Raspberry Pi Imager's bootloader-flashing option on a spare SD card), update
to the latest stable bootloader and confirm the boot order includes USB
mass-storage devices, since the external SSD is USB-attached.

## 2. Build and flash the Talos image

1. Go to [Image Factory](https://factory.talos.dev), select **Metal**,
   **arm64**, overlay **`rpi_5`** (`siderolabs/sbc-raspberrypi`), and the
   Talos version you intend to run — pick something reasonably current,
   since the Pi 5 fix and follow-on driver work landed across recent
   releases. Note the schematic ID it gives you.
2. Update `machine.install.image` in
   [`talos/patches/pi5.yaml`](../../talos/patches/pi5.yaml) with that
   schematic ID and version.
3. Download the disk image (`metal-arm64.raw.xz`) and write it directly to
   the external USB SSD — for the Pi 5's prebuilt SBC image there's no
   separate "install to a different disk" step; the media you flash is the
   media it boots and (re)installs onto:

   ```sh
   xz -d -c metal-arm64.raw.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync
   ```

4. Confirm `machine.install.disk` in `talos/patches/pi5.yaml` matches how
   that same SSD will enumerate from the Pi's own point of view (commonly
   `/dev/sda` for a single USB SSD) — verify with the `get disks` command in
   step 3 below rather than assuming.

## 3. First boot — find the node

Connect the Ethernet cable, insert the SSD, and power on. Give it a minute
to reach Talos maintenance mode (no OS installed yet, API-only). Find its
IP one of:

- Serial console: prints the DHCP-assigned IP directly.
- Your router/OPNsense DHCP lease table, looking for the new client.

Confirm it's reachable and in maintenance mode:

```sh
talosctl -n <maintenance-ip> version
talosctl -n <maintenance-ip> get disks --insecure
```

The second command lists real disk paths — use it to double-check
`machine.install.disk` in `talos/patches/pi5.yaml` before applying config.

If you don't get this far — no DHCP lease, nothing on serial past the
U-Boot banner — the most likely cause is the wrong overlay (recheck step 2)
or the EEPROM boot order not including USB (recheck step 1).

## 4. Generate, apply, and bootstrap

From the repo root, using the endpoint IP you reserved in the prerequisites:

```sh
scripts/bootstrap-talos.sh generate <endpoint-ip>
scripts/bootstrap-talos.sh apply <maintenance-ip>
# wait for the node to install and reboot (watch serial, or poll):
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
| Stuck at the U-Boot logo, black screen, nothing on serial after | Wrong overlay used when building the image — must be `rpi_5`, not `rpi_generic` or none. Rebuild the schematic at Image Factory and reflash. |
| No DHCP lease, no serial output past U-Boot | EEPROM boot order doesn't include USB — recheck step 1 — or the Ethernet cable/switch port isn't live. |
| `talosctl get disks --insecure` doesn't show the SSD | USB enumeration issue — try the Pi 5's USB3 (blue) port specifically. |
| `apply-config` succeeds but node never comes back on the endpoint IP | Wrong `machine.install.disk` in `pi5.yaml` (install failed) — recheck via serial, or `get disks --insecure` from a fresh maintenance boot. |
| `bootstrap` hangs or errors | Ran before the node finished installing/rebooting after `apply-config` — wait longer and retry; `bootstrap` is only ever run once per cluster. |
| `kubectl get nodes` shows `NotReady` indefinitely | CNI or kubelet issue — `talosctl -n <ip> dashboard` and `talosctl -n <ip> logs kubelet` for detail. |

## Recovery

To start over on the same hardware: `talosctl -n <ip> reset` wipes the node
back to maintenance mode. Delete `talos/secrets/` and `./kubeconfig` locally
and repeat from step 3 (or step 2 if you're also reflashing the SSD).
