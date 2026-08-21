"""Pure helpers for connector onboarding readiness reports."""
from __future__ import annotations


def build_readiness_report(source_name: str, datasets, known_object_types) -> dict:
    """Build a stable report from introspected dataset definitions."""
    if not isinstance(source_name, str) or not source_name or source_name != source_name.strip():
        raise ValueError("source_name must be a non-empty unpadded string")
    if datasets is None:
        raise ValueError("introspect returned no dataset list")
    try:
        datasets = list(datasets)
    except TypeError as exc:
        raise ValueError("introspect result must be iterable") from exc

    known = set(known_object_types)
    rows = []
    seen: set[str] = set()
    for dataset in datasets:
        name = getattr(dataset, "name", None)
        columns = getattr(dataset, "columns", None)
        primary_key = getattr(dataset, "primary_key", None)
        if not isinstance(name, str) or not name or name != name.strip():
            raise ValueError(f"invalid dataset name: {name!r}")
        if name in seen:
            raise ValueError(f"duplicate dataset name: {name}")
        seen.add(name)
        if columns is None:
            raise ValueError(f"dataset {name} has no columns collection")
        try:
            column_count = len(columns)
        except TypeError as exc:
            raise ValueError(f"dataset {name} columns are not sized") from exc
        pk = list(primary_key or [])
        rows.append({"name": name, "columns": column_count, "pk": pk, "mapped": name in known})

    mapped = [row["name"] for row in rows if row["mapped"]]
    unmapped = [row["name"] for row in rows if not row["mapped"]]
    return {
        "source": source_name,
        "ok": True,
        "n_tables": len(rows),
        "mapped_object_types": mapped,
        "unmapped_tables": unmapped,
        "readiness": f"{len(mapped)}/{len(rows)} 表已有对象模型，{len(unmapped)} 表待建模",
        "datasets": rows,
    }
