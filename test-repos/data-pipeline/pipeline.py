"""Main pipeline orchestrator."""

import time
from config import Config
from extractors import extract
from transformers import transform, deduplicate
from validators import validate_batch
from loaders import load


class Pipeline:
    """Orchestrates the full extract-transform-load process."""

    def __init__(self, config: Config):
        self.config = config
        self.stats = {"extracted": 0, "valid": 0, "invalid": 0, "loaded": 0}
        self.errors = []

    def run(self) -> dict:
        """Execute the full pipeline and return run statistics."""
        errors = self.config.validate_config()
        if errors:
            raise ValueError(f"Invalid config: {errors}")

        start = time.time()
        try:
            raw = self._extract()
            transformed = self._transform(raw)
            validated = self._validate(transformed)
            self._load(validated)
        except Exception as e:
            self.errors.append(str(e))
            raise
        finally:
            self.stats["duration_ms"] = int((time.time() - start) * 1000)

        return self.stats

    def _extract(self) -> list:
        records = extract(self.config)
        self.stats["extracted"] = len(records)
        return records

    def _transform(self, records: list) -> list:
        transformed = transform(records, self.config.transforms)
        if self.config.transforms:
            transformed = deduplicate(transformed, "id")
        return transformed

    def _validate(self, records: list) -> list:
        if not self.config.validate:
            return records
        valid, invalid = validate_batch(records)
        self.stats["valid"] = len(valid)
        self.stats["invalid"] = len(invalid)
        return valid

    def _load(self, records: list):
        n = load(records, self.config)
        self.stats["loaded"] = n


def run_pipeline(config_path=None, **overrides) -> dict:
    """Convenience function to build and run a pipeline."""
    config = Config(config_path).load_env()
    for key, value in overrides.items():
        setattr(config, key, value)
    pipeline = Pipeline(config)
    return pipeline.run()


def run_batch(config_paths: list) -> list:
    """Run multiple pipelines sequentially and collect results."""
    results = []
    for path in config_paths:
        try:
            stats = run_pipeline(path)
            results.append({"config": path, "status": "ok", "stats": stats})
        except Exception as e:
            results.append({"config": path, "status": "error", "error": str(e)})
    return results
