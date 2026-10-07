#!/usr/bin/env bash
# Read host facts. This script installs nothing and changes no configuration.
set -eu
uname -m
cat /etc/os-release
findmnt -no SOURCE,FSTYPE,TARGET /
lsblk -o NAME,SIZE,TRAN,FSTYPE,MOUNTPOINTS
free -h
df -h /
if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
    cat /sys/fs/cgroup/cgroup.controllers
fi
if command -v k3s >/dev/null 2>&1; then
    k3s --version
fi
if [ "$(systemctl show k3s.service --property=LoadState --value 2>/dev/null)" = 'loaded' ]; then
    systemctl is-active k3s.service || true
fi
