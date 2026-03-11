"""Record validation — enforce schema and business rules."""

import re


REQUIRED_FIELDS = ["id", "name"]
MAX_FIELD_LENGTH = 1024


def validate_record(record: dict) -> bool:
    """Return True if the record passes all validation checks."""
    if not check_required(record):
        return False
    if not check_types(record):
        return False
    if not check_lengths(record):
        return False
    return True


def check_required(record: dict) -> bool:
    """Ensure all required fields are present and non-empty."""
    for field in REQUIRED_FIELDS:
        if field not in record:
            return False
        if record[field] is None or record[field] == "":
            return False
    return True


def check_types(record: dict) -> bool:
    """Ensure known fields have expected types."""
    if "id" in record:
        try:
            int(record["id"])
        except (ValueError, TypeError):
            return False
    if "email" in record and record["email"]:
        if not re.match(r"[^@]+@[^@]+\.[^@]+", str(record["email"])):
            return False
    if "age" in record and record["age"] is not None:
        try:
            age = int(record["age"])
            if age < 0 or age > 150:
                return False
        except (ValueError, TypeError):
            return False
    return True


def check_lengths(record: dict) -> bool:
    """Ensure string fields don't exceed maximum length."""
    for k, v in record.items():
        if isinstance(v, str) and len(v) > MAX_FIELD_LENGTH:
            return False
    return True


def validate_batch(records: list) -> tuple:
    """Validate a batch of records. Returns (valid, invalid) lists."""
    valid = []
    invalid = []
    for r in records:
        if validate_record(r):
            valid.append(r)
        else:
            invalid.append(r)
    return valid, invalid


def validate_schema(record: dict, schema: dict) -> list:
    """Validate a record against a schema definition. Returns list of errors."""
    errors = []
    for field, rules in schema.items():
        value = record.get(field)
        if rules.get("required") and (value is None or value == ""):
            errors.append(f"{field} is required")
            continue
        if value is None:
            continue
        if "type" in rules:
            expected = rules["type"]
            if expected == "int":
                try:
                    int(value)
                except (ValueError, TypeError):
                    errors.append(f"{field} must be an integer")
            elif expected == "float":
                try:
                    float(value)
                except (ValueError, TypeError):
                    errors.append(f"{field} must be a float")
            elif expected == "str" and not isinstance(value, str):
                errors.append(f"{field} must be a string")
        if "max_length" in rules and isinstance(value, str):
            if len(value) > rules["max_length"]:
                errors.append(f"{field} exceeds max length {rules['max_length']}")
        if "pattern" in rules and isinstance(value, str):
            if not re.match(rules["pattern"], value):
                errors.append(f"{field} does not match pattern")
    return errors
