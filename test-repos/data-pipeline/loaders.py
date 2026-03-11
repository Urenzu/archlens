"""Data loaders — write transformed records to a destination."""

import csv
import json
import os
from config import Config


def load(records: list, config: Config) -> int:
    """Dispatch to the correct loader. Returns number of records written."""
    if config.destination == "stdout":
        return load_stdout(records)
    elif config.destination.endswith(".csv"):
        return load_csv(records, config.destination)
    elif config.destination.endswith(".json") or config.destination.endswith(".jsonl"):
        return load_json(records, config.destination)
    elif config.destination.startswith("db:"):
        return load_db(records, config.destination[3:])
    else:
        raise ValueError(f"Unknown destination: {config.destination}")


def load_stdout(records: list) -> int:
    """Print records as JSON to stdout."""
    for record in records:
        print(json.dumps(record))
    return len(records)


def load_csv(records: list, path: str) -> int:
    """Write records to a CSV file."""
    if not records:
        return 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fields = list(records[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return len(records)


def load_json(records: list, path: str) -> int:
    """Write records to a JSON or JSONL file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if path.endswith(".jsonl"):
            for r in records:
                f.write(json.dumps(r) + "\n")
        else:
            json.dump(records, f, indent=2)
    return len(records)


def load_db(records: list, connection_string: str) -> int:
    """Insert records into a SQLite database table."""
    import sqlite3
    if not records:
        return 0
    conn = sqlite3.connect(connection_string)
    cursor = conn.cursor()
    fields = list(records[0].keys())
    placeholders = ", ".join("?" for _ in fields)
    # Vulnerability: table name not sanitized
    table = os.getenv("OUTPUT_TABLE", "records")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(fields)})")
    for record in records:
        values = [record.get(f) for f in fields]
        cursor.execute(f"INSERT INTO {table} VALUES ({placeholders})", values)
    conn.commit()
    conn.close()
    return len(records)
