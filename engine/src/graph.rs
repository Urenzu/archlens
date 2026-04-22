use std::collections::{HashMap, HashSet};

use crate::models::{Caller, EdgeKind, GraphEdge, GraphNode, NodeKind, NodeMetrics};
use crate::parser::ModuleInfo;

/// Build graph nodes and edges from parsed modules.
/// Returns (nodes, edges, callers_map).
pub fn build_graph(
    modules: &[ModuleInfo],
) -> (Vec<GraphNode>, Vec<GraphEdge>, HashMap<String, Vec<Caller>>) {
    // Build lookup: function name -> qualified names
    let mut name_to_qnames: HashMap<&str, Vec<&str>> = HashMap::new();
    for module in modules {
        for func in &module.functions {
            name_to_qnames
                .entry(&func.name)
                .or_default()
                .push(&func.qualified_name);
        }
    }

    // Build nodes
    let mut nodes: Vec<GraphNode> = Vec::new();

    for module in modules {
        for func in &module.functions {
            let vuln = func.vulnerabilities.first().cloned();
            let mut node = GraphNode::new(
                func.qualified_name.clone(),
                func.name.clone(),
                NodeKind::Function,
            );
            node.file = Some(module.path.clone());
            node.metrics = NodeMetrics {
                cyclomatic: func.complexity,
                loc: func.loc,
                params: func.params,
                max_nesting: func.max_nesting,
                callers: 0,
                callees: 0,
            };
            node.vulnerability = vuln;
            nodes.push(node);
        }

        for cls in &module.classes {
            let mut node = GraphNode::new(
                cls.qualified_name.clone(),
                cls.name.clone(),
                NodeKind::Class,
            );
            node.file = Some(module.path.clone());
            node.metrics = NodeMetrics {
                cyclomatic: 0,
                loc: cls.end_lineno - cls.lineno + 1,
                params: 0,
                max_nesting: 0,
                callers: 0,
                callees: cls.methods.len() as i32,
            };
            nodes.push(node);
        }
    }

    let node_ids: HashSet<&str> = nodes.iter().map(|n| n.id.as_str()).collect();

    // Build edges from call relationships
    let mut edges: Vec<GraphEdge> = Vec::new();
    let mut callers_map: HashMap<String, Vec<Caller>> = HashMap::new();
    let mut seen_edges: HashSet<(String, String)> = HashSet::new();
    let mut edge_id = 0;

    for module in modules {
        for func in &module.functions {
            for call_name in &func.calls {
                let targets = match name_to_qnames.get(call_name.as_str()) {
                    Some(t) => t,
                    None => continue,
                };

                for &target_qname in targets {
                    if target_qname == func.qualified_name {
                        continue; // skip self-calls
                    }
                    if !node_ids.contains(target_qname) {
                        continue;
                    }

                    let pair = (func.qualified_name.clone(), target_qname.to_string());
                    if seen_edges.contains(&pair) {
                        continue;
                    }
                    seen_edges.insert(pair);

                    edge_id += 1;
                    edges.push(GraphEdge {
                        id: format!("e{}", edge_id),
                        source: func.qualified_name.clone(),
                        target: target_qname.to_string(),
                        kind: EdgeKind::Normal,
                    });

                    let caller_kind = if func.class_name.is_some() {
                        "class"
                    } else {
                        "function"
                    };
                    callers_map
                        .entry(target_qname.to_string())
                        .or_default()
                        .push(Caller {
                            name: func.qualified_name.clone(),
                            kind: caller_kind.to_string(),
                            depth: 1,
                        });
                }
            }
        }
    }

    // Compute caller/callee counts from edges
    let mut out_degree: HashMap<&str, i32> = HashMap::new();
    let mut in_degree: HashMap<&str, i32> = HashMap::new();

    for e in &edges {
        *out_degree.entry(e.source.as_str()).or_insert(0) += 1;
        *in_degree.entry(e.target.as_str()).or_insert(0) += 1;
    }

    for node in &mut nodes {
        node.metrics.callers = *in_degree.get(node.id.as_str()).unwrap_or(&0);
        node.metrics.callees = *out_degree.get(node.id.as_str()).unwrap_or(&0);
    }

    (nodes, edges, callers_map)
}
