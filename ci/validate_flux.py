from copy import deepcopy
from pathlib import Path
import sys

import yaml
from jsonschema import Draft7Validator

root = Path("clusters/pi")
crds = root / "flux-system/gotk-components.yaml"
schemas = {}


def strict(schema):
    if isinstance(schema, dict):
        for value in list(schema.values()):
            strict(value)
        if (
            "properties" in schema
            and not schema.get("x-kubernetes-preserve-unknown-fields")
        ):
            schema.setdefault("additionalProperties", False)
    elif isinstance(schema, list):
        for value in schema:
            strict(value)


for resource in yaml.safe_load_all(crds.read_text()):
    if not resource or resource.get("kind") != "CustomResourceDefinition":
        continue
    spec = resource["spec"]
    for version in spec["versions"]:
        if not version.get("served"):
            continue
        schema = deepcopy(version["schema"]["openAPIV3Schema"])
        strict(schema)
        key = (
            f'{spec["group"]}/{version["name"]}',
            spec["names"]["kind"],
        )
        schemas[key] = schema

checked = 0
failures = []

for path in sorted(root.rglob("*.yaml")):
    if path == crds:
        continue
    for resource in yaml.safe_load_all(path.read_text()):
        if not isinstance(resource, dict):
            continue
        api = resource.get("apiVersion", "")
        if ".toolkit.fluxcd.io/" not in api:
            continue

        key = (api, resource.get("kind"))
        if key not in schemas:
            failures.append(f"{path}: missing schema for {key}")
            continue

        validator = Draft7Validator(schemas[key])
        errors = list(validator.iter_errors(resource))
        for error in errors:
            location = ".".join(map(str, error.absolute_path))
            failures.append(f"{path}: {location}: {error.message}")

        if errors:
            continue

        invalid = deepcopy(resource)
        invalid.setdefault("spec", {})["invalidFluxField"] = True
        if validator.is_valid(invalid):
            failures.append(f"{path}: unknown-field rejection failed")
            continue

        checked += 1
        print(
            f'PASS {path}: '
            f'{resource["kind"]}/{resource["metadata"]["name"]}'
        )

for failure in failures:
    print(f"FAIL {failure}", file=sys.stderr)

print(f"{checked} resources passed, {len(failures)} failures")
sys.exit(1 if failures or checked == 0 else 0)
