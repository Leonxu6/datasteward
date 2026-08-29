"""Data lineage helpers built from the live source/dataset/transform registries.

Lineage is derived state. Runtime source and dataset registration must therefore be
visible immediately rather than being frozen at import time. Security markings use
the same live graph so access-control decisions cannot lag behind registry changes.
"""
from __future__ import annotations

from dm.connect.catalog import SOURCES
from dm.datasets.model import DATASETS, TRANSFORMS


def _clean_name(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty unpadded text")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field} contains control characters")
    return value


def _require_dataset(name: object) -> str:
    clean = _clean_name(name, field="dataset_name")
    if clean not in DATASETS:
        raise KeyError(f"unknown dataset: {clean}")
    return clean


def _build_graph() -> tuple[dict[str, dict], list[tuple[str, str, str]]]:
    nodes: dict[str, dict] = {}
    edges: list[tuple[str, str, str]] = []
    for source in SOURCES.values():
        node_id = f"source:{source.name}"
        nodes[node_id] = {"id": node_id, "type": "source", "label": source.name}
    for dataset in DATASETS.values():
        node_id = f"dataset:{dataset.name}"
        nodes[node_id] = {
            "id": node_id,
            "type": "dataset",
            "tier": dataset.tier,
            "label": dataset.name,
        }
        source_id = f"source:{dataset.source}" if dataset.source else None
        if source_id and source_id in nodes:
            edges.append((source_id, node_id, "sync"))
    for transform in TRANSFORMS.values():
        transform_id = f"transform:{transform.name}"
        nodes[transform_id] = {
            "id": transform_id,
            "type": "transform",
            "kind": transform.kind,
            "label": transform.name,
        }
        for input_name in transform.inputs:
            input_id = f"dataset:{input_name}"
            if input_id in nodes:
                edges.append((input_id, transform_id, "input"))
        for output_name in transform.outputs:
            output_id = f"dataset:{output_name}"
            if output_id in nodes:
                edges.append((transform_id, output_id, "output"))
    return nodes, edges


def lineage_graph() -> dict:
    """Return a fresh deterministic graph for the current registries."""
    nodes, edges = _build_graph()
    ordered_nodes = [nodes[node_id] for node_id in sorted(nodes)]
    ordered_edges = sorted(edges, key=lambda edge: (edge[0], edge[1], edge[2]))
    return {
        "nodes": ordered_nodes,
        "edges": [{"from": source, "to": target, "kind": kind} for source, target, kind in ordered_edges],
    }


def _walk(start_id: str, upstream: bool) -> list[dict]:
    """Breadth-first traversal with stable shortest-distance ordering."""
    nodes, edges = _build_graph()
    if start_id not in nodes:
        return []
    seen = {start_id}
    frontier = [start_id]
    result: list[dict] = []
    while frontier:
        next_frontier: list[str] = []
        for node_id in frontier:
            neighbours = {
                source if upstream and target == node_id else target
                for source, target, _ in edges
                if (upstream and target == node_id) or (not upstream and source == node_id)
            }
            for neighbour in sorted(neighbours):
                if neighbour in seen or neighbour not in nodes:
                    continue
                seen.add(neighbour)
                next_frontier.append(neighbour)
                result.append(nodes[neighbour])
        frontier = next_frontier
    return result


def ancestry(dataset_name: str) -> list[dict]:
    """Return all upstream nodes for a known dataset."""
    name = _require_dataset(dataset_name)
    return _walk(f"dataset:{name}", upstream=True)


def impact(dataset_name: str) -> list[dict]:
    """Return all downstream nodes for a known dataset."""
    name = _require_dataset(dataset_name)
    return _walk(f"dataset:{name}", upstream=False)


def column_lineage(dataset_name: str, column: str) -> list[dict]:
    """Trace one column backwards while refusing ambiguous transform mappings."""
    current_dataset = _require_dataset(dataset_name)
    current_column = _clean_name(column, field="column")
    chain: list[dict] = [{"dataset": current_dataset, "column": current_column}]
    seen: set[tuple[str, str]] = set()

    while True:
        key = (current_dataset, current_column)
        if key in seen:
            raise ValueError(f"cyclic column lineage detected at {current_dataset}.{current_column}")
        seen.add(key)

        producers = [transform for transform in TRANSFORMS.values() if current_dataset in transform.outputs]
        if len(producers) > 1:
            names = ", ".join(sorted(transform.name for transform in producers))
            raise ValueError(f"ambiguous producers for {current_dataset}: {names}")
        if not producers:
            dataset = DATASETS.get(current_dataset)
            if dataset and dataset.source:
                chain.append({"source": dataset.source, "column": current_column})
            return chain

        producer = producers[0]
        source_columns = producer.column_map.get(current_column, [])
        if not source_columns:
            return chain
        if len(source_columns) != 1:
            raise ValueError(
                f"ambiguous source columns for {current_dataset}.{current_column} via {producer.name}"
            )
        if len(producer.inputs) != 1:
            raise ValueError(
                f"column lineage for {producer.name} requires exactly one input dataset"
            )

        source_column = _clean_name(source_columns[0], field="source column")
        source_dataset = _clean_name(producer.inputs[0], field="source dataset")
        if source_dataset not in DATASETS:
            raise ValueError(f"transform {producer.name} references unknown input dataset: {source_dataset}")
        current_dataset, current_column = source_dataset, source_column
        chain.append({"dataset": current_dataset, "column": current_column, "via": producer.name})


def _live_markings(node_id: str) -> list:
    kind, _, name = node_id.partition(":")
    if kind == "source":
        source = SOURCES.get(name)
        return list(source.markings) if source else []
    if kind == "dataset":
        dataset = DATASETS.get(name)
        return list(dataset.markings) if dataset else []
    return []


def effective_markings(dataset_name: str) -> list:
    """Return the union of markings on a dataset and every live upstream node."""
    name = _require_dataset(dataset_name)
    node_id = f"dataset:{name}"
    node_ids = {node["id"] for node in _walk(node_id, upstream=True)} | {node_id}
    markings: set[str] = set()
    for upstream_id in node_ids:
        markings.update(_live_markings(upstream_id))
    return sorted(markings)
