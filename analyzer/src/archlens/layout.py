"""Hierarchical layout engine — positions nodes in layers by call depth."""

from __future__ import annotations

from collections import defaultdict

from .models import GraphNode, GraphEdge

NODE_W = 110
NODE_H = 34
ROOT_W = 130
X_GAP = 40
Y_GAP = 100
PADDING_X = 60
PADDING_Y = 60


def compute_layout(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> tuple[int, int]:
    """Assign x/y positions to nodes. Returns (viewbox_width, viewbox_height)."""
    if not nodes:
        return (900, 420)

    # Build adjacency
    children: dict[str, list[str]] = defaultdict(list)
    parents: dict[str, list[str]] = defaultdict(list)
    node_map = {n.id: n for n in nodes}

    for e in edges:
        children[e.source].append(e.target)
        parents[e.target].append(e.source)

    # Find roots (no parents)
    roots = [n.id for n in nodes if n.id not in parents]
    if not roots:
        roots = [nodes[0].id]

    # BFS to assign layers
    layer: dict[str, int] = {}
    queue = list(roots)
    for r in roots:
        layer[r] = 0
    visited = set(roots)

    while queue:
        nid = queue.pop(0)
        for child in children[nid]:
            new_depth = layer[nid] + 1
            if child not in layer or new_depth > layer[child]:
                layer[child] = new_depth
            if child not in visited:
                visited.add(child)
                queue.append(child)

    # Nodes not reachable from roots get their own layer
    max_layer = max(layer.values()) if layer else 0
    for n in nodes:
        if n.id not in layer:
            max_layer += 1
            layer[n.id] = max_layer

    # Group by layer
    layers: dict[int, list[str]] = defaultdict(list)
    for nid, lyr in layer.items():
        layers[lyr].append(nid)

    # Sort within each layer: group by file first, then by name for stability
    for lyr in layers:
        layers[lyr].sort(key=lambda nid: (node_map[nid].file, nid))

    num_layers = max(layers.keys()) + 1 if layers else 1

    # Position nodes
    max_width = 0
    for lyr_idx in range(num_layers):
        lyr_nodes = layers.get(lyr_idx, [])
        if not lyr_nodes:
            continue

        total_w = sum(
            (ROOT_W if len(parents.get(nid, [])) == 0 and lyr_idx == 0 else NODE_W)
            for nid in lyr_nodes
        )
        total_w += X_GAP * (len(lyr_nodes) - 1)
        start_x = PADDING_X

        for i, nid in enumerate(lyr_nodes):
            node = node_map[nid]
            w = ROOT_W if lyr_idx == 0 and nid in roots else NODE_W
            node.width = w
            node.x = start_x
            node.y = PADDING_Y + lyr_idx * (NODE_H + Y_GAP)
            start_x += w + X_GAP

        max_width = max(max_width, start_x + PADDING_X)

    vw = max(900, int(max_width))
    vh = max(420, PADDING_Y * 2 + num_layers * (NODE_H + Y_GAP))
    return (vw, vh)
