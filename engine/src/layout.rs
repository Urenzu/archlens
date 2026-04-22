use std::collections::{HashMap, HashSet, VecDeque};

use crate::models::{GraphEdge, GraphNode};

const NODE_W: f64 = 110.0;
const NODE_H: f64 = 34.0;
const ROOT_W: f64 = 130.0;
const X_GAP: f64 = 40.0;
const Y_GAP: f64 = 100.0;
const PADDING_X: f64 = 60.0;
const PADDING_Y: f64 = 60.0;

/// Assign x/y positions to nodes. Returns (viewbox_width, viewbox_height).
pub fn compute_layout(nodes: &mut [GraphNode], edges: &[GraphEdge]) -> (i32, i32) {
    if nodes.is_empty() {
        return (900, 420);
    }

    // Build adjacency using owned strings
    let mut children: HashMap<String, Vec<String>> = HashMap::new();
    let mut parents: HashMap<String, Vec<String>> = HashMap::new();

    for e in edges {
        children
            .entry(e.source.clone())
            .or_default()
            .push(e.target.clone());
        parents
            .entry(e.target.clone())
            .or_default()
            .push(e.source.clone());
    }

    // Find roots (no parents)
    let mut roots: Vec<String> = nodes
        .iter()
        .filter(|n| !parents.contains_key(&n.id))
        .map(|n| n.id.clone())
        .collect();
    if roots.is_empty() {
        roots.push(nodes[0].id.clone());
    }
    let root_set: HashSet<String> = roots.iter().cloned().collect();

    // BFS to assign layers
    let mut layer: HashMap<String, usize> = HashMap::new();
    let mut queue: VecDeque<String> = VecDeque::new();
    let mut visited: HashSet<String> = HashSet::new();

    for r in &roots {
        layer.insert(r.clone(), 0);
        queue.push_back(r.clone());
        visited.insert(r.clone());
    }

    while let Some(nid) = queue.pop_front() {
        let current_layer = layer[&nid];
        if let Some(ch) = children.get(&nid) {
            for child in ch {
                let new_depth = current_layer + 1;
                let existing = layer.get(child).copied();
                if existing.is_none() || new_depth > existing.unwrap() {
                    layer.insert(child.clone(), new_depth);
                }
                if !visited.contains(child) {
                    visited.insert(child.clone());
                    queue.push_back(child.clone());
                }
            }
        }
    }

    // Nodes not reachable from roots get their own layer
    let mut max_layer = layer.values().copied().max().unwrap_or(0);
    for n in nodes.iter() {
        if !layer.contains_key(&n.id) {
            max_layer += 1;
            layer.insert(n.id.clone(), max_layer);
        }
    }

    // Group by layer
    let mut layers: HashMap<usize, Vec<String>> = HashMap::new();
    for (nid, &lyr) in &layer {
        layers.entry(lyr).or_default().push(nid.clone());
    }

    // Build file lookup for sorting
    let file_map: HashMap<String, String> = nodes
        .iter()
        .map(|n| {
            (
                n.id.clone(),
                n.file.clone().unwrap_or_default(),
            )
        })
        .collect();

    // Sort within each layer: group by file first, then by id for stability
    for lyr_nodes in layers.values_mut() {
        lyr_nodes.sort_by(|a, b| {
            let file_a = file_map.get(a).map(|s| s.as_str()).unwrap_or("");
            let file_b = file_map.get(b).map(|s| s.as_str()).unwrap_or("");
            file_a.cmp(file_b).then_with(|| a.cmp(b))
        });
    }

    let num_layers = if layers.is_empty() {
        1
    } else {
        layers.keys().max().unwrap() + 1
    };

    // Build index map for mutation
    let node_idx: HashMap<String, usize> = nodes
        .iter()
        .enumerate()
        .map(|(i, n)| (n.id.clone(), i))
        .collect();

    // Position nodes
    let mut max_width: f64 = 0.0;
    for lyr_idx in 0..num_layers {
        let lyr_nodes = match layers.get(&lyr_idx) {
            Some(v) => v,
            None => continue,
        };

        let mut start_x = PADDING_X;

        for nid in lyr_nodes {
            let w = if lyr_idx == 0 && root_set.contains(nid) {
                ROOT_W
            } else {
                NODE_W
            };

            let idx = node_idx[nid];
            nodes[idx].width = w;
            nodes[idx].x = start_x;
            nodes[idx].y = PADDING_Y + (lyr_idx as f64) * (NODE_H + Y_GAP);

            start_x += w + X_GAP;
        }

        max_width = max_width.max(start_x + PADDING_X);
    }

    let vw = 900_i32.max(max_width as i32);
    let vh = 420_i32.max((PADDING_Y * 2.0 + (num_layers as f64) * (NODE_H + Y_GAP)) as i32);
    (vw, vh)
}
