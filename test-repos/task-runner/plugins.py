"""Plugin loader — dynamically loads task modules from disk."""

import importlib.util
import importlib
import os
import sys
from tasks import Task, TaskRegistry


def load_plugin_file(path: str, registry: TaskRegistry):
    """Load a Python plugin file and register any Task objects it exports."""
    # Vulnerability: arbitrary file path loaded as module code
    spec = importlib.util.spec_from_file_location("_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _register_from_module(module, registry)


def load_plugin_dir(directory: str, registry: TaskRegistry):
    """Scan a directory for *.py plugin files and load each one."""
    if not os.path.isdir(directory):
        raise ValueError(f"Plugin directory not found: {directory}")
    for filename in sorted(os.listdir(directory)):
        if filename.startswith("_") or not filename.endswith(".py"):
            continue
        load_plugin_file(os.path.join(directory, filename), registry)


def load_builtin_plugins(registry: TaskRegistry):
    """Register the built-in default tasks."""
    from plugins_builtin import register_builtins
    register_builtins(registry)


def _register_from_module(module, registry: TaskRegistry):
    """Find all Task instances in a module's top-level namespace and register them."""
    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, Task):
            registry.register(obj)


def discover_plugins(search_paths: list) -> list:
    """Return all .py plugin files found under the given search paths."""
    found = []
    for base in search_paths:
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            for f in files:
                if f.endswith(".py") and not f.startswith("_"):
                    found.append(os.path.join(root, f))
    return found


def reload_plugin(path: str, registry: TaskRegistry):
    """Remove tasks from a previously loaded plugin and reload it."""
    spec = importlib.util.spec_from_file_location("_plugin_reload", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Remove existing tasks that came from this path (by tag convention)
    plugin_tag = os.path.splitext(os.path.basename(path))[0]
    current_tasks = registry.tasks_by_tag(plugin_tag)
    for t in current_tasks:
        del registry._tasks[t.name]
    _register_from_module(module, registry)
