"""Strict YAML loading for eval definitions."""
from __future__ import annotations

import yaml

from dm.eval.schema import EvalCaseError, validate_cases


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise EvalCaseError("eval YAML mapping keys must be hashable") from exc
        if duplicate:
            raise EvalCaseError(f"duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def load_eval_cases(text: object):
    if not isinstance(text, str):
        raise EvalCaseError("eval YAML must be text")
    if len(text) > 2_000_000:
        raise EvalCaseError("eval YAML is too large")
    try:
        raw = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise EvalCaseError("eval YAML is invalid") from exc
    return validate_cases(raw)
