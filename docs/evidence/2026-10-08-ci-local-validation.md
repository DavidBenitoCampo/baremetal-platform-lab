# Local CI validation

Date: 8 October 2026, Europe/Prague.

The checks ran against files fetched from repository commit
`2e3575744e9b896b1c9e2f48c73292c953c8533a`, with the new workflow added.

Validation ran in a separate Linux x86_64 environment with Python 3.12.14.
This records local command results. The GitHub-hosted workflow has not run yet.

## Tools

- kubectl v1.36.5, with embedded Kustomize v5.8.1.
- Kubeconform v0.8.0.
- Ansible Core 2.21.5.
- yamllint 1.38.0.
- Kubernetes 1.36.0 schemas at revision
  `39a87cd29966bc0b3434e8cfbc2061782c8cb69a`.

Both downloaded binary checksums matched the values in the workflow.

## Passing checks

| Check | Observed result |
| --- | --- |
| YAML | Exit 0 |
| Ansible syntax | Exit 0, playbook parsed |
| Kustomize rendering | Exit 0 for both application configurations |
| Kubernetes schemas | 10 resources valid, 0 invalid, 0 errors, 0 skipped |
| Python syntax | Exit 0 |
| Shell syntax | Exit 0 |
| Evidence JSONL | Five records parsed across three files |

The two rendered files contain the Podinfo and Ollama resources.

The JSONL check validates the file format. Answer accuracy is a separate check,
recorded in [the Ollama evidence](2026-10-07-ollama.md).

## Invalid field exercise

A temporary copy of the rendered Podinfo Deployment received an extra field:

```yaml
spec:
  replicaz: 2
```

The rest of the rendered Deployment stayed intact. Kubeconform ran with strict
validation and the same pinned schema source as the passing check.

Observed result:

```text
at '/spec': additional properties 'replicaz' not allowed
Summary: 1 resource found in 1 file - Valid: 0, Invalid: 1, Errors: 0, Skipped: 0
Exit code: 1
```

The fixture stayed outside the repository's application manifests. No test
configuration was applied to the Pi.

## GitHub acceptance

After pushing the workflow, retain the first passing run URL.

Use a separate pull request to repeat the invalid field exercise. Retain the
failed run URL, the corrected run URL, and the pull request URL. Add those links
here after observing the results.
