"""Data models matching the frontend type system."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal
import json


@dataclass
class NodeMetrics:
    cyclomatic: int = 1
    loc: int = 0
    params: int = 0
    maxNesting: int = 0
    callers: int = 0
    callees: int = 0


@dataclass
class GraphNode:
    id: str
    label: str
    kind: Literal["function", "class", "module"]
    x: float = 0
    y: float = 0
    width: float = 110
    height: float = 34
    metrics: NodeMetrics = field(default_factory=NodeMetrics)
    isHot: bool | None = None
    isComplex: bool | None = None
    vulnerability: str | None = None
    file: str = ""


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    kind: Literal["normal", "critical"] = "normal"


@dataclass
class Module:
    name: str
    count: int


@dataclass
class Caller:
    name: str
    kind: Literal["function", "class"]
    depth: int


@dataclass
class RepoStats:
    name: str
    branch: str
    commit: str
    functions: int
    classes: int
    modules: int
    vulns: int


@dataclass
class FileEdge:
    source: str   # relative file path
    target: str   # relative file path
    callCount: int = 0


@dataclass
class AnalysisResult:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    fileEdges: list[FileEdge]
    modules: list[Module]
    callers: dict[str, list[Caller]]  # node_id -> callers
    stats: RepoStats

    def to_dict(self) -> dict:
        d = asdict(self)
        # Strip None values from nodes
        for node in d["nodes"]:
            if node["isHot"] is None:
                del node["isHot"]
            if node["isComplex"] is None:
                del node["isComplex"]
            if node["vulnerability"] is None:
                del node["vulnerability"]
            if not node["file"]:
                del node["file"]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
