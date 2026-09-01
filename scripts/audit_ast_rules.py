"""Shared AST helpers for small, deterministic repository-maintenance rules."""
from __future__ import annotations

import ast
from collections.abc import Iterator


def parse_source(source: str) -> ast.AST | None:
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


def dotted_name(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def iter_calls(source: str) -> Iterator[ast.Call]:
    tree = parse_source(source)
    if tree is None:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node


def iter_assignments(source: str) -> Iterator[ast.Assign | ast.AnnAssign | ast.AugAssign]:
    tree = parse_source(source)
    if tree is None:
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            yield node


def call_name(call: ast.Call) -> str | None:
    return dotted_name(call.func)


def has_keyword(call: ast.Call, name: str) -> bool:
    return any(keyword.arg == name for keyword in call.keywords)


def assignment_targets(node: ast.Assign | ast.AnnAssign | ast.AugAssign) -> list[str]:
    raw_targets: list[ast.AST]
    if isinstance(node, ast.Assign):
        raw_targets = list(node.targets)
    else:
        raw_targets = [node.target]
    names: list[str] = []
    for target in raw_targets:
        name = dotted_name(target)
        if name:
            names.append(name)
    return names
