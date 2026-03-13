use std::collections::HashSet;

use crate::models::{EdgeKind, GraphEdge, GraphNode, NodeKind};

/// Mark hot (high callers) and complex (high cyclomatic) nodes,
/// then mark edges touching flagged nodes as critical.
pub fn flag_hotpaths(nodes: &mut [GraphNode], edges: &mut [GraphEdge]) {
    let fn_nodes: Vec<usize> = nodes
        .iter()
        .enumerate()
        .filter(|(_, n)| n.kind == NodeKind::Function)
        .map(|(i, _)| i)
        .collect();

    if fn_nodes.is_empty() {
        return;
    }

    // Hot = top 20% by callers, minimum 2 callers
    let mut caller_counts: Vec<i32> = fn_nodes.iter().map(|&i| nodes[i].metrics.callers).collect();
    caller_counts.sort_unstable_by(|a, b| b.cmp(a));
    let hot_threshold = caller_counts[0.max(caller_counts.len() / 5)];

    for &i in &fn_nodes {
        if nodes[i].metrics.callers >= hot_threshold && nodes[i].metrics.callers >= 2 {
            nodes[i].is_hot = Some(true);
        }
    }

    // Complex = top 20% by cyclomatic complexity, minimum score > 5
    let mut cyclo_counts: Vec<i32> = fn_nodes
        .iter()
        .map(|&i| nodes[i].metrics.cyclomatic)
        .collect();
    cyclo_counts.sort_unstable_by(|a, b| b.cmp(a));
    let cx_threshold = cyclo_counts[0.max(cyclo_counts.len() / 5)];

    for &i in &fn_nodes {
        if nodes[i].metrics.cyclomatic >= cx_threshold && nodes[i].metrics.cyclomatic > 5 {
            nodes[i].is_complex = Some(true);
        }
    }

    // Mark edges as critical if either endpoint is hot or complex
    let flagged_ids: HashSet<&str> = nodes
        .iter()
        .filter(|n| n.is_hot.is_some() || n.is_complex.is_some())
        .map(|n| n.id.as_str())
        .collect();

    for edge in edges.iter_mut() {
        if flagged_ids.contains(edge.source.as_str())
            || flagged_ids.contains(edge.target.as_str())
        {
            edge.kind = EdgeKind::Critical;
        }
    }
}
