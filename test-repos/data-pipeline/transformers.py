"""Data transformers — clean, reshape, and enrich records."""

import re
from validators import validate_record


def transform(records: list, transforms: list) -> list:
    """Apply a sequence of named transforms to all records."""
    result = []
    for record in records:
        r = record.copy()
        for t in transforms:
            if t == "normalize":
                r = normalize(r)
            elif t == "flatten":
                r = flatten(r)
            elif t == "drop_nulls":
                r = drop_nulls(r)
            elif t == "coerce_types":
                r = coerce_types(r)
            elif t.startswith("rename:"):
                mapping = parse_rename_spec(t[7:])
                r = rename_fields(r, mapping)
        if validate_record(r):
            result.append(r)
    return result


def normalize(record: dict) -> dict:
    """Normalize string fields: strip whitespace, lowercase keys."""
    return {
        k.strip().lower().replace(" ", "_"): (v.strip() if isinstance(v, str) else v)
        for k, v in record.items()
    }


def flatten(record: dict, prefix="", sep="_") -> dict:
    """Flatten a nested dict into a single level."""
    out = {}
    for key, value in record.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten(value, full_key, sep))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    out.update(flatten(item, f"{full_key}{sep}{i}", sep))
                else:
                    out[f"{full_key}{sep}{i}"] = item
        else:
            out[full_key] = value
    return out


def drop_nulls(record: dict) -> dict:
    """Remove keys with None or empty string values."""
    return {k: v for k, v in record.items() if v is not None and v != ""}


def coerce_types(record: dict) -> dict:
    """Best-effort type coercion: strings that look like numbers or bools."""
    out = {}
    for k, v in record.items():
        if not isinstance(v, str):
            out[k] = v
            continue
        if v.lower() in ("true", "yes"):
            out[k] = True
        elif v.lower() in ("false", "no"):
            out[k] = False
        else:
            try:
                out[k] = int(v)
            except ValueError:
                try:
                    out[k] = float(v)
                except ValueError:
                    out[k] = v
    return out


def rename_fields(record: dict, mapping: dict) -> dict:
    """Rename fields according to a mapping dict."""
    return {mapping.get(k, k): v for k, v in record.items()}


def parse_rename_spec(spec: str) -> dict:
    """Parse a rename spec like 'old1:new1,old2:new2' into a dict."""
    mapping = {}
    for pair in spec.split(","):
        pair = pair.strip()
        if ":" in pair:
            old, new = pair.split(":", 1)
            mapping[old.strip()] = new.strip()
    return mapping


def deduplicate(records: list, key_field: str) -> list:
    """Remove duplicate records by a key field."""
    seen = set()
    result = []
    for r in records:
        val = r.get(key_field)
        if val is None or val not in seen:
            if val is not None:
                seen.add(val)
            result.append(r)
    return result
