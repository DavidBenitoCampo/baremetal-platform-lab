# ADR-002: Use Talos Linux for Kubernetes Nodes

- Status: Accepted
- Date: 2026-08-30

## Context

The Kubernetes nodes require an operating system. A conventional Ubuntu-based installation would be familiar and flexible, but would also introduce manual OS administration that is not central to the goals of this project.

The lab should encourage reproducibility, immutability, and infrastructure-as-code practices.

## Decision

Talos Linux will be used as the operating system for Kubernetes nodes where hardware support permits it.

The Raspberry Pi 5 will be the first target.

## Reasons

- Talos is designed specifically for Kubernetes.
- Node configuration is API-driven and declarative.
- The operating system is minimal and immutable.
- There is no SSH-based administration model.
- Configuration can be version-controlled and recreated.
- It encourages replacement/reconciliation rather than manual server repair.

## Consequences

### Positive

- Reduced configuration drift.
- Clear separation between node configuration and workloads.
- Strong alignment with declarative infrastructure principles.
- Rebuilding a node becomes a core operational workflow.

### Negative

- Less familiar than Ubuntu.
- Traditional SSH troubleshooting is unavailable.
- Hardware compatibility must be checked carefully.
- Raspberry Pi bootstrapping requires additional platform-specific work.

## Alternatives Considered

### Ubuntu + kubeadm

Very flexible and familiar, but increases host-level configuration and maintenance. It remains a useful fallback for unsupported hardware.

### NixOS

Provides excellent declarative host configuration and is valuable for general-purpose infrastructure, but Talos is more narrowly optimized for Kubernetes and better supports the desired immutable-node operating model.

## Revisit Conditions

This decision should be revisited if:

- Talos does not support required hardware reliably.
- A future node must run non-Kubernetes workloads.
- The project expands into host-level configuration experiments where NixOS provides greater learning value.

## Update — 2026-09-09: First Target Changed to x86 Mini PC

The Raspberry Pi 5 was the original first target named in this decision. In
practice it hit the "hardware compatibility must be checked carefully" risk
called out above: Talos support for the Pi 5 is community-maintained, not
part of Talos' officially tested platform list, and current images fail to
bring up Ethernet because the kernel lacks `CONFIG_FIRMWARE_RP1`, the driver
for the Pi 5's RP1 southbridge chip — see
[siderolabs/sbc-raspberrypi#23](https://github.com/siderolabs/sbc-raspberrypi/issues/23)
and [siderolabs/overlays#77](https://github.com/siderolabs/overlays/discussions/77).
Since Talos has no local console or SSH workflow, a node that can't reach the
network can't be administered at all.

This meets the revisit condition above without invalidating the underlying
decision to use Talos — the fix is a hardware substitution, not a change of
OS: Talos itself is still the right fit for the reasons already listed.

**New first target: a standard x86_64 UEFI mini PC**, using Talos' plain
Metal installer with no SBC overlay and no kernel fork. This is also the
platform the wider Talos homelab community defaults to, for the same
reason — it sidesteps SBC-specific hardware support gaps entirely.

The Raspberry Pi 5 remains part of the project: repurposed as an
Ubuntu + kubeadm node for CKA exam practice, and as a candidate to rejoin
the Talos cluster later once upstream RP1 support lands.

## Update — 2026-09-09 (revised): Pi 5 Reinstated as First Target

The mini PC pivot above was based on a Raspberry Pi 5 Ethernet/boot issue
that has since been fixed upstream: SideroLabs merged a dedicated `rpi_5`
Image Factory profile in
[siderolabs/sbc-raspberrypi#71](https://github.com/siderolabs/sbc-raspberrypi/pull/71)
(merged 2026-01-24), which replaces the Pi firmware repo's downstream DTBs
with upstream-kernel ones. This fixes Ethernet and closes the exact
"stuck at the U-Boot logo, black screen" issue this project hit
([#23](https://github.com/siderolabs/sbc-raspberrypi/issues/23)). The
previous update was written without checking whether a fix had already
landed — a process gap worth naming alongside the technical one.

**Reinstating the Raspberry Pi 5 as the Milestone 1 target**, using the
hardware already on hand (Pi 5, external USB SSD, Ethernet). The critical
change from the original attempt: build the image at Image Factory with
the **`rpi_5`** overlay/profile specifically — not `rpi_generic` (Pi 4) and
not a plain no-overlay image. Using the wrong overlay reproduces the exact
black-screen symptom this project hit the first time.

The x86 mini PC path from the update above remains good general guidance
for later nodes (Milestone 6, mixed ARM64/x86 workers) — it just isn't
needed to unblock Milestone 1 anymore.

## Update — 2026-09-10: Boot Media Must Be the microSD

Talos boots on the Pi 5 via Pi firmware → U-Boot → kernel, and **U-Boot
cannot read USB block devices** — USB only becomes available once Linux is
running. A USB SSD holding the boot partition therefore gets as far as the
U-Boot stage and stalls; confirmed directly by booting this node with the
microSD removed, which left the board sitting in U-Boot despite the SSD
carrying an identical, freshly written Talos partition layout.

Consequence for this node's disk layout:

- **microSD** — boot and system disk (`machine.install.disk: /dev/mmcblk0`).
- **External USB SSD** — the `EPHEMERAL` volume, which backs `/var`,
  including `/var/lib/etcd` and container images.

This keeps the original reason for buying an SSD intact: etcd's constant
small writes, which are what wear out SD cards and what benefit most from
the SSD's random I/O, land on the SSD rather than the card. The card holds
boot artifacts that are written rarely.

Two constraints this creates, both recorded here because they are easy to
trip over later:

1. Volume configuration only applies while a volume is unprovisioned, so
   the EPHEMERAL relocation must be present at the first `apply-config`.
   Changing it afterwards requires wiping the volume.
2. `/var` now depends on the USB SSD remaining attached. Losing the SSD
   costs the node its etcd data and container storage — relevant to the
   failure scenarios planned for Milestone 7.
