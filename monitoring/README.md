# Monitoring configuration planned

Weeks 8 and 9 add focused Prometheus jobs/rules, Grafana provisioning and dashboard
JSON, Alertmanager, a blackbox HTTP probe, and host metrics.

Set 15 second scrape/evaluation intervals for the HTTP alert exercise.
Use probe_success == 0 with for=30s and Alertmanager group_wait=5s.
Retain actual detection and routing times.

Monitoring shares the application host. Pi failure also stops the local monitor.
The laptop HTTP log supplies independent evidence during the test window.
