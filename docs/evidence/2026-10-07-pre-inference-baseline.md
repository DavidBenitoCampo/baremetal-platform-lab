# Before the first inference deployment

Date: 7 October 2026.
Source: operator-provided command output from the running Pi.
No Ollama deployment or inference result accompanies this baseline.

| Check | Observed value |
| --- | --- |
| Node | pi-lab |
| Node CPU, from kubectl top | 83m, 2% |
| Node memory, from kubectl top | 1392 MiB, 17% |
| Host total memory, from free | 7.7 GiB |
| Host available memory, from free | 6.7 GiB |
| Swap | 0 |
| Root filesystem | /dev/sda2 |
| Root capacity, used, available | 469 GiB, 3.8 GiB, 447 GiB |
| Default StorageClass | local-path |
| Provisioner | rancher.io/local-path |
| Volume binding | WaitForFirstConsumer |
| Reclaim policy | Delete |
| Volume expansion | false |

The host and Kubernetes memory readings use different accounting. They are
snapshots, not a peak-memory measurement or a capacity guarantee.

The first proposed inference settings are one Ollama Pod, a 1 GiB memory request,
a 2 GiB memory limit, a one-core CPU request and a two-core CPU limit. The model
starts at Qwen2.5 0.5B with a 2,048-token context and one concurrent request.

Keep at least 2 GiB of host memory available during the test. Record actual
readings after loading the model and during generation. If this condition fails,
stop the test workload and review the settings before adding more services.
