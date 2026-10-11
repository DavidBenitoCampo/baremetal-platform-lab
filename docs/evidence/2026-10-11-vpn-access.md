# VPN access test

Date: 2026-10-11

I added Tailscale to my workstation and Raspberry Pi so I could
reach the lab from outside my home network.

The access rule permits TCP port 22 from my workstation to the Pi.
I use my existing SSH key for login and SSH tunnels for the services.

## Results

- SSH login through the Pi's Tailscale address worked.
- Grafana loaded through an SSH tunnel.
- Ollama returned a successful inference response through an SSH tunnel.
- Prometheus returned `Prometheus Server is Ready`.
- The Prometheus `up` query returned three targets, each with value 1.
- The final Prometheus check used my phone's hotspot.

## Tunnel troubleshooting

Some earlier port-forward processes occupied ports on the Pi.
A later connection failed because its destination listener had stopped.

For Prometheus, I switched to an SSH tunnel targeting the Kubernetes
Service IP directly. This removed the separate port-forward process.

## Evidence

- [Ollama request](ollama-over-vpn.jsonl)
- [Prometheus targets](prometheus-over-vpn.json)

## Limits

This test demonstrates remote access through Tailscale and SSH.
Reboot persistence and denied-access tests have not been recorded.
The VPN does not protect the lab from Pi or SSD failure.
