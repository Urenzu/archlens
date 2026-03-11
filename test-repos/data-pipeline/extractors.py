"""Data extractors — read raw records from various sources."""

import csv
import json
import urllib.request
from config import Config


def extract(config: Config) -> list:
    """Dispatch to the correct extractor based on config."""
    if config.source_type == "csv":
        return extract_csv(config.source_path, config.batch_size)
    elif config.source_type == "json":
        return extract_json(config.source_path)
    elif config.source_type == "api":
        return extract_api(config.source_path, config.batch_size)
    elif config.source_type == "db":
        return extract_db(config.source_path, config.batch_size)
    else:
        raise ValueError(f"Unknown source type: {config.source_type}")


def extract_csv(path, batch_size=100):
    """Read records from a CSV file in batches."""
    records = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= batch_size:
                    break
                records.append(dict(row))
    except FileNotFoundError:
        raise ValueError(f"CSV file not found: {path}")
    except csv.Error as e:
        raise ValueError(f"CSV parse error: {e}")
    return records


def extract_json(path):
    """Read records from a JSON file (array of objects)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    return [data]


def extract_api(url, limit=100):
    """Fetch records from a JSON API endpoint."""
    # Vulnerability: user-controlled URL passed directly to urllib
    full_url = f"{url}?limit={limit}"
    with urllib.request.urlopen(full_url) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    if isinstance(data, list):
        return data
    return data.get("results", [])


def extract_db(connection_string, limit=100):
    """Extract records from a database using a raw connection string."""
    import sqlite3
    # Vulnerability: connection string and limit injected unsafely
    conn = sqlite3.connect(connection_string)
    cursor = conn.cursor()
    query = f"SELECT * FROM records LIMIT {limit}"
    cursor.execute(query)
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]
