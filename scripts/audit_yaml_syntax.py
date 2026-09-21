"""Validate tracked YAML files with a bounded duplicate-safe loader."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from yaml.constructor import ConstructorError

from scripts.audit_common import print_failures, require_root, tracked_files

_MAX_YAML_BYTES = 2 * 1024 * 1024


class _StrictSafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate mapping keys."""

    def construct_mapping(self, node, deep: bool = False):
        self.flatten_mapping(node)
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable mapping key",
                    key_node.start_mark,
                ) from exc
            if key in mapping:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def audit_file(path: Path) -> list[str]:
    if path.is_symlink():
        return [f"invalid YAML: {path.name}: symbolic links are not accepted"]
    if not path.is_file():
        return [f"invalid YAML: {path.name}: expected a regular file"]
    try:
        if path.stat().st_size > _MAX_YAML_BYTES:
            return [f"invalid YAML: {path.name}: file exceeds {_MAX_YAML_BYTES} byte audit limit"]
        text = path.read_text(encoding="utf-8")
        yaml.load(text, Loader=_StrictSafeLoader)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return [f"invalid YAML: {path.name}: {exc}"]
    return []


def audit(root: Path) -> list[str]:
    root = require_root(root)
    failures: list[str] = []
    for rel in tracked_files(root):
        if rel.suffix.lower() in {".yaml", ".yml"}:
            failures.extend(f"{rel}: {item}" for item in audit_file(root / rel))
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    return print_failures(audit(Path(parser.parse_args(argv).root)))


if __name__ == "__main__":
    raise SystemExit(main())
