# Repository checks

[Validate](validate.yml) checks the lab files on GitHub. Runs trigger after a push
to `main`, for pull requests, and from the Actions page.

The job uses an Ubuntu 24.04 runner with Python 3.12. Ansible checks the playbook
syntax using the example inventory. Kustomize renders the manifests as files.
No Pi connection is part of the job.

## Checks

| Check | What gets checked |
| --- | --- |
| YAML | Syntax, duplicate keys, indentation, and whitespace |
| Ansible | `ansible/host.yml` with the public example inventory |
| Kustomize | The Podinfo Pi overlay and the Ollama configuration |
| Kubernetes schemas | Required fields, field names, and value types in the rendered resources |
| Python | Syntax of the scripts in `scripts/` |
| Shell | Syntax of `scripts/preflight.sh` |
| Evidence | Each line in the JSONL files parses as JSON |

The schema check targets Kubernetes 1.36.0, matching the lab's 1.36 minor
version. The schema repository revision is pinned. Missing schemas fail the check.

These checks cover file structure. Probe endpoints, image startup on ARM64,
storage behavior, and model answers need tests on the Pi.

A failing workflow reports a failed check. Requiring a passing check before a
merge needs a separate repository rule.

## Tool versions

| Tool | Version |
| --- | --- |
| Checkout action | v7.0.1, pinned to a full commit SHA |
| kubectl | v1.36.5 |
| Embedded Kustomize | v5.8.1 |
| Kubeconform | v0.8.0 |
| Ansible Core | 2.21.5 |
| yamllint | 1.38.0 |
| Python | 3.12 |

The workflow contains the binary SHA256 values. Downloads must match before
execution. [ci/requirements.txt](../../ci/requirements.txt) pins the Python tools
and their dependencies.

The job has `contents: read` permission. Checkout does not retain Git
credentials. The workflow uses no kubeconfig, SSH key, or model credentials.

## First run

Push the workflow and open the repository's
[Actions page](https://github.com/DavidBenitoCampo/baremetal-platform-lab/actions).

Open the Validate run for the new commit. Each named step should pass. If a step
fails, open its log and fix the reported file or dependency problem.

The local validation result is recorded in
[the CI evidence file](../../docs/evidence/2026-10-08-ci-local-validation.md).
A GitHub run has not been observed yet.

## Check an invalid change

Use a separate branch for this exercise.

1. Add `replicaz: 2` under `spec` in `kubernetes/base/deployment.yaml`.
2. Keep the existing `replicas` field.
3. Commit the change, push the branch, and open a pull request.
4. Expect Validate Kubernetes fields to fail with `replicaz` in the error.
5. Remove the misspelled field and push the fix to the same branch.
6. Expect the next run to pass.

Keep the pull request URL and both workflow run URLs as evidence. The error
exercise changes Git files only. Leave the Pi's running configuration alone.

## Updating the tools

Change a tool version and its checksum together. Obtain checksums from the
upstream release. Review the checkout action's resolved commit when updating
the action.

Update the schema version and revision when changing the lab's Kubernetes
minor version. Future GitOps and monitoring custom resources need their own
schema handling.

## Sources

Checked on 8 October 2026, Europe/Prague.

- [Kubernetes Kustomize guide](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
- [kubectl installation and checksum verification](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/)
- [Kubeconform documentation](https://github.com/yannh/kubeconform)
- [Kubeconform v0.8.0](https://github.com/yannh/kubeconform/releases/tag/v0.8.0)
- [Pinned Kubernetes schemas](https://github.com/yannh/kubernetes-json-schema/tree/39a87cd29966bc0b3434e8cfbc2061782c8cb69a)
- [Ansible syntax-check option](https://docs.ansible.com/projects/ansible/latest/cli/ansible-playbook.html)
- [Ansible Python support](https://docs.ansible.com/projects/ansible/latest/reference_appendices/release_and_maintenance.html)
- [yamllint configuration](https://yamllint.readthedocs.io/en/stable/configuration.html)
- [Checkout v7.0.1](https://github.com/actions/checkout/tree/3d3c42e5aac5ba805825da76410c181273ba90b1)
- [GitHub Actions security guidance](https://docs.github.com/en/actions/reference/security/secure-use)
