"""Pipeline configuration and environment loading."""

import os
import json


class Config:
    """Holds all pipeline configuration."""

    def __init__(self, path=None):
        self.source_type = "csv"
        self.source_path = ""
        self.destination = "stdout"
        self.batch_size = 100
        self.max_retries = 3
        self.validate = True
        self.transforms = []
        if path:
            self.load_file(path)

    def load_file(self, path):
        """Load config from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        for key, value in data.items():
            setattr(self, key, value)

    def load_env(self):
        """Override config values from environment variables."""
        if os.getenv("PIPELINE_SOURCE"):
            self.source_path = os.getenv("PIPELINE_SOURCE")
        if os.getenv("PIPELINE_DEST"):
            self.destination = os.getenv("PIPELINE_DEST")
        if os.getenv("BATCH_SIZE"):
            self.batch_size = int(os.getenv("BATCH_SIZE"))
        return self

    def validate_config(self):
        """Validate the configuration is usable."""
        errors = []
        if not self.source_path:
            errors.append("source_path is required")
        if self.batch_size < 1:
            errors.append("batch_size must be positive")
        if self.max_retries < 0:
            errors.append("max_retries cannot be negative")
        if self.source_type not in ("csv", "json", "api", "db"):
            errors.append(f"unknown source_type: {self.source_type}")
        return errors
