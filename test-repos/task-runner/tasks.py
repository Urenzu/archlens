"""Task definitions and task graph resolution."""

from dataclasses import dataclass, field
from typing import Callable, Optional
import time


@dataclass
class Task:
    """A single unit of work with dependencies."""

    name: str
    fn: Callable
    deps: list = field(default_factory=list)
    timeout: int = 60
    retries: int = 0
    tags: list = field(default_factory=list)


@dataclass
class TaskResult:
    """Outcome of a single task execution."""

    name: str
    status: str  # "ok" | "failed" | "skipped" | "timeout"
    output: object = None
    error: str = ""
    duration_ms: int = 0


class TaskRegistry:
    """Holds all registered tasks and resolves dependency order."""

    def __init__(self):
        self._tasks: dict[str, Task] = {}

    def register(self, task: Task):
        if task.name in self._tasks:
            raise ValueError(f"Task already registered: {task.name}")
        self._tasks[task.name] = task

    def get(self, name: str) -> Optional[Task]:
        return self._tasks.get(name)

    def all_names(self) -> list:
        return list(self._tasks.keys())

    def resolve_order(self, targets: list) -> list:
        """Topological sort of tasks needed to satisfy targets."""
        visited = set()
        order = []

        def visit(name: str, chain: list):
            if name in chain:
                raise ValueError(f"Circular dependency: {' -> '.join(chain + [name])}")
            if name in visited:
                return
            task = self._tasks.get(name)
            if task is None:
                raise ValueError(f"Unknown task: {name}")
            for dep in task.deps:
                visit(dep, chain + [name])
            visited.add(name)
            order.append(name)

        for t in targets:
            visit(t, [])
        return order

    def tasks_by_tag(self, tag: str) -> list:
        return [t for t in self._tasks.values() if tag in t.tags]

    def dependency_count(self, name: str) -> int:
        """Recursively count total transitive dependencies."""
        task = self._tasks.get(name)
        if not task:
            return 0
        total = len(task.deps)
        for dep in task.deps:
            total += self.dependency_count(dep)
        return total
