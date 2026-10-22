import re
import sys
from pathlib import Path

import yaml

PINNED = re.compile(r"[^@\s]+@sha256:[0-9a-f]{64}")


def containers_in(value, location=""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}" if location else key
            if key in ("containers", "initContainers", "ephemeralContainers"):
                if not isinstance(child, list):
                    raise ValueError(f"{child_location}: expected a list")
                for index, container in enumerate(child):
                    yield f"{child_location}[{index}]", container
            else:
                yield from containers_in(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from containers_in(child, f"{location}[{index}]")


def main(paths):
    failures = []
    total = 0

    if not paths:
        raise ValueError("Supply at least one manifest file")

    for filename in paths:
        count = 0
        for document in yaml.safe_load_all(Path(filename).read_text()):
            for location, container in containers_in(document):
                count += 1
                image = container.get("image")
                if not isinstance(image, str) or not PINNED.fullmatch(image):
                    failures.append(
                        f"{filename}: {location}: unpinned image {image!r}"
                    )
        if count == 0:
            failures.append(f"{filename}: no containers found")
        total += count

    for failure in failures:
        print(f"FAIL {failure}", file=sys.stderr)

    print(f"{total} container references checked, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f"FAIL {error}", file=sys.stderr)
        sys.exit(1)
