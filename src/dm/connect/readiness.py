"""Pure helpers for connector onboarding readiness reports."""
from __future__ import annotations


def _materialize_iterable(value, *, field: str) -> list:
    if value is None:
        raise ValueError(f"{field} must be provided")
    if isinstance(value, (str, bytes, bytearray, dict)):
        raise ValueError(f"{field} must be a collection, not a scalar mapping/string")
    try:
        return list(value)
    except TypeError as exc:
        raise ValueError(f"{field} must be iterable") from exc


def _clean_name(value, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{field} must be non-empty unpadded text")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{field} contains control characters")
    return value


def build_readiness_report(source_name: str, datasets, known_object_types) -> dict:
    """Build a stable report from introspected dataset definitions."""
    source_name = _clean_name(source_name, field="source_name")
    datasets = _materialize_iterable(datasets, field="introspect result")
    known_values = _materialize_iterable(known_object_types, field="known_object_types")
    known = {_clean_name(name, field="known object type") for name in known_values}

    rows = []
    seen: set[str] = set()
    for dataset in datasets:
        name = _clean_name(getattr(dataset, "name", None), field="dataset name")
        columns_value = getattr(dataset, "columns", None)
        primary_key = getattr(dataset, "primary_key", None)
        if name in seen:
            raise ValueError(f"duplicate dataset name: {name}")
        seen.add(name)

        column_values = _materialize_iterable(columns_value, field=f"dataset {name} columns")
        columns = [_clean_name(column, field=f"dataset {name} column") for column in column_values]
        if len(columns) != len(set(columns)):
            raise ValueError(f"dataset {name} columns contain duplicate names")

        if primary_key is None:
            pk = []
        else:
            pk_values = _materialize_iterable(primary_key, field=f"dataset {name} primary_key")
            pk = [_clean_name(column, field=f"dataset {name} primary key column") for column in pk_values]
            if len(pk) != len(set(pk)):
                raise ValueError(f"dataset {name} primary key contains duplicate columns")
            missing = [column for column in pk if column not in columns]
            if missing:
                raise ValueError(f"dataset {name} primary key references unknown columns: {missing}")
        rows.append({"name": name, "columns": len(columns), "pk": pk, "mapped": name in known})

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
