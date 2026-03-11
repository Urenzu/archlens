"""Main analysis orchestrator — ties parsing, graph building, and layout together."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from pathlib import Path

from .models import (
    AnalysisResult,
    Caller,
    FileEdge,
    GraphEdge,
    GraphNode,
    Module,
    NodeMetrics,
    RepoStats,
)
from .parser import ModuleInfo, parse_file
from .layout import compute_layout


def analyze_repo(repo_path: str | Path) -> AnalysisResult:
    """Analyze a Python repository and return the full graph."""
    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    # 1. Parse all Python files
    modules: list[ModuleInfo] = []
    py_files = sorted(root.rglob("*.py"))
    for py_file in py_files:
        # Skip hidden dirs, venvs, __pycache__
        parts = py_file.relative_to(root).parts
        if any(p.startswith(".") or p in ("__pycache__", "venv", ".venv", "node_modules") for p in parts):
            continue
        mod = parse_file(py_file, root)
        if mod:
            modules.append(mod)

    # 2. Build lookup: function name -> qualified names
    name_to_qnames: dict[str, list[str]] = defaultdict(list)
    qname_set: set[str] = set()
    for mod in modules:
        for fn in mod.functions:
            name_to_qnames[fn.name].append(fn.qualified_name)
            qname_set.add(fn.qualified_name)

    # 3. Build graph nodes and edges
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    edge_id = 0

    # Track callers for each node
    callers_map: dict[str, list[Caller]] = defaultdict(list)

    for mod in modules:
        for fn in mod.functions:
            vuln = fn.vulnerabilities[0] if fn.vulnerabilities else None
            node = GraphNode(
                id=fn.qualified_name,
                label=fn.name,
                kind="function",
                file=mod.path,
                metrics=NodeMetrics(
                    cyclomatic=fn.complexity,
                    loc=fn.loc,
                    params=fn.params,
                    maxNesting=fn.max_nesting,
                    callers=0,
                    callees=0,
                ),
                vulnerability=vuln,
            )
            nodes.append(node)

        for cls in mod.classes:
            node = GraphNode(
                id=cls.qualified_name,
                label=cls.name,
                kind="class",
                file=mod.path,
                metrics=NodeMetrics(
                    cyclomatic=0,
                    loc=cls.end_lineno - cls.lineno + 1,
                    callers=0,
                    callees=len(cls.methods),
                ),
            )
            nodes.append(node)

    node_ids = {n.id for n in nodes}

    # 4. Create edges from call relationships
    seen_edges: set[tuple[str, str]] = set()
    for mod in modules:
        for fn in mod.functions:
            for call_name in fn.calls:
                # Resolve call to qualified name(s)
                targets = name_to_qnames.get(call_name, [])
                for target_qname in targets:
                    if target_qname == fn.qualified_name:
                        continue  # skip self-calls
                    if target_qname not in node_ids:
                        continue
                    pair = (fn.qualified_name, target_qname)
                    if pair in seen_edges:
                        continue
                    seen_edges.add(pair)
                    edge_id += 1
                    edges.append(GraphEdge(
                        id=f"e{edge_id}",
                        source=fn.qualified_name,
                        target=target_qname,
                    ))
                    callers_map[target_qname].append(Caller(
                        name=fn.qualified_name,
                        kind="class" if fn.class_name else "function",
                        depth=1,
                    ))

    # 5. Compute caller/callee counts and call depth
    out_degree: dict[str, int] = defaultdict(int)
    in_degree: dict[str, int] = defaultdict(int)
    children: dict[str, list[str]] = defaultdict(list)

    for e in edges:
        out_degree[e.source] += 1
        in_degree[e.target] += 1
        children[e.source].append(e.target)

    node_map = {n.id: n for n in nodes}
    for n in nodes:
        n.metrics.callers = in_degree.get(n.id, 0)
        n.metrics.callees = out_degree.get(n.id, 0)

    # 6. Mark hot (high callers / traffic) and complex (high branches) separately
    fn_nodes = [n for n in nodes if n.kind == "function"]

    # Hot = top 20% by callers, minimum 2 callers
    caller_counts = sorted((n.metrics.callers for n in fn_nodes), reverse=True)
    if caller_counts:
        hot_threshold = caller_counts[max(0, len(caller_counts) // 5)]
        for n in fn_nodes:
            if n.metrics.callers >= hot_threshold and n.metrics.callers >= 2:
                n.isHot = True

    # Complex = top 20% by cyclomatic complexity, minimum score > 5
    cyclo_counts = sorted((n.metrics.cyclomatic for n in fn_nodes), reverse=True)
    if cyclo_counts:
        cx_threshold = cyclo_counts[max(0, len(cyclo_counts) // 5)]
        for n in fn_nodes:
            if n.metrics.cyclomatic >= cx_threshold and n.metrics.cyclomatic > 5:
                n.isComplex = True

    # Mark edges as critical if either endpoint is hot or complex
    flagged_ids = {n.id for n in nodes if n.isHot or n.isComplex}
    for e in edges:
        if e.source in flagged_ids or e.target in flagged_ids:
            e.kind = "critical"

    # 7. Compute file-level edges (import-based + augmented with call counts)
    module_to_file = {m.name: m.path for m in modules}
    file_edge_map: dict[tuple[str, str], int] = {}

    # Import-based edges first (captures dynamic dispatch, indirect calls, etc.)
    for mod in modules:
        for imported_module in mod.imports:
            target_file = module_to_file.get(imported_module)
            if target_file and target_file != mod.path:
                key = (mod.path, target_file)
                if key not in file_edge_map:
                    file_edge_map[key] = 0

    # Augment with call counts from detected function-level edges
    for e in edges:
        src_node = node_map.get(e.source)
        tgt_node = node_map.get(e.target)
        if src_node and tgt_node and src_node.file and tgt_node.file and src_node.file != tgt_node.file:
            key = (src_node.file, tgt_node.file)
            file_edge_map[key] = file_edge_map.get(key, 0) + 1

    file_edges = [
        FileEdge(source=s, target=t, callCount=c)
        for (s, t), c in file_edge_map.items()
    ]

    # 8. Layout
    compute_layout(nodes, edges)

    # 8. Build module list
    mod_counts: dict[str, int] = defaultdict(int)
    for mod in modules:
        # Use directory as module group
        parts = Path(mod.path).parts
        if len(parts) > 1:
            mod_name = str(Path(*parts[:-1])) + "/"
        else:
            mod_name = "./"
        mod_counts[mod_name] += len(mod.functions) + len(mod.classes)

    module_list = [Module(name=k, count=v) for k, v in sorted(mod_counts.items())]

    # 9. Repo stats
    total_fns = sum(len(m.functions) for m in modules)
    total_classes = sum(len(m.classes) for m in modules)
    total_vulns = sum(
        1 for n in nodes if n.vulnerability
    )

    # Try to get git info
    repo_name = root.name
    branch = "unknown"
    commit = "0000000"
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=root, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        # Try to get remote URL for name
        origin = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=root, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        if origin:
            # Extract org/repo from URL
            origin = origin.rstrip(".git").rstrip("/")
            parts = origin.split("/")
            if len(parts) >= 2:
                repo_name = "/".join(parts[-2:])
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    stats = RepoStats(
        name=repo_name,
        branch=branch,
        commit=commit,
        functions=total_fns,
        classes=total_classes,
        modules=len(modules),
        vulns=total_vulns,
    )

    return AnalysisResult(
        nodes=nodes,
        edges=edges,
        fileEdges=file_edges,
        modules=module_list,
        callers=callers_map,
        stats=stats,
    )
