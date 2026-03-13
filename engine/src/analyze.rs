use std::collections::HashMap;
use std::path::Path;

use crate::graph::build_graph;
use crate::hotpath::flag_hotpaths;
use crate::layout::compute_layout;
use crate::models::{AnalysisResult, FileEdge, Module, RepoStats};
use crate::parser::python;
use crate::parser::ModuleInfo;

/// Input file for analysis: relative path and source content.
#[derive(Debug, Clone, serde::Deserialize)]
pub struct InputFile {
    pub path: String,
    pub content: String,
}

/// Analyze a set of files and return the full graph.
pub fn analyze_files(files: Vec<InputFile>) -> AnalysisResult {
    // 1. Parse all Python files
    let mut modules: Vec<ModuleInfo> = Vec::new();

    let mut sorted_files = files;
    sorted_files.sort_by(|a, b| a.path.cmp(&b.path));

    for file in &sorted_files {
        // Skip hidden dirs, venvs, __pycache__, node_modules
        let should_skip = file.path.split('/').any(|part| {
            part.starts_with('.')
                || part == "__pycache__"
                || part == "venv"
                || part == ".venv"
                || part == "node_modules"
        });
        if should_skip {
            continue;
        }

        // Only parse .py files
        if !file.path.ends_with(".py") {
            continue;
        }

        if let Some(module) = python::parse_file(&file.content, &file.path) {
            modules.push(module);
        }
    }

    // 2-5. Build graph nodes, edges, compute degrees
    let (mut nodes, mut edges, callers_map) = build_graph(&modules);

    // 6. Mark hot/complex nodes and critical edges
    flag_hotpaths(&mut nodes, &mut edges);

    // 7. Compute file-level edges (import-based + augmented with call counts)
    let file_edges = build_file_edges(&modules, &nodes, &edges);

    // 8. Layout
    compute_layout(&mut nodes, &edges);

    // 9. Build module list
    let module_list = build_module_list(&modules);

    // 10. Repo stats (git info is injected by frontend)
    let total_fns: i32 = modules.iter().map(|m| m.functions.len() as i32).sum();
    let total_classes: i32 = modules.iter().map(|m| m.classes.len() as i32).sum();
    let total_vulns: i32 = nodes
        .iter()
        .filter(|n| n.vulnerability.is_some())
        .count() as i32;

    let stats = RepoStats {
        name: String::new(),
        branch: String::new(),
        commit: String::new(),
        functions: total_fns,
        classes: total_classes,
        modules: modules.len() as i32,
        vulns: total_vulns,
    };

    AnalysisResult {
        nodes,
        edges,
        file_edges,
        modules: module_list,
        callers: callers_map,
        stats,
    }
}

fn build_file_edges(
    modules: &[ModuleInfo],
    nodes: &[crate::models::GraphNode],
    edges: &[crate::models::GraphEdge],
) -> Vec<FileEdge> {
    let module_to_file: HashMap<&str, &str> = modules
        .iter()
        .map(|m| (m.name.as_str(), m.path.as_str()))
        .collect();

    let mut file_edge_map: HashMap<(String, String), i32> = HashMap::new();

    // Import-based edges first
    for module in modules {
        for imported_module in &module.imports {
            if let Some(&target_file) = module_to_file.get(imported_module.as_str()) {
                if target_file != module.path {
                    let key = (module.path.clone(), target_file.to_string());
                    file_edge_map.entry(key).or_insert(0);
                }
            }
        }
    }

    // Augment with call counts from function-level edges
    let node_map: HashMap<&str, &crate::models::GraphNode> =
        nodes.iter().map(|n| (n.id.as_str(), n)).collect();

    for edge in edges {
        let src_file = node_map
            .get(edge.source.as_str())
            .and_then(|n| n.file.as_deref());
        let tgt_file = node_map
            .get(edge.target.as_str())
            .and_then(|n| n.file.as_deref());

        if let (Some(sf), Some(tf)) = (src_file, tgt_file) {
            if sf != tf {
                let key = (sf.to_string(), tf.to_string());
                *file_edge_map.entry(key).or_insert(0) += 1;
            }
        }
    }

    file_edge_map
        .into_iter()
        .map(|((s, t), c)| FileEdge {
            source: s,
            target: t,
            call_count: c,
        })
        .collect()
}

fn build_module_list(modules: &[ModuleInfo]) -> Vec<Module> {
    let mut mod_counts: HashMap<String, i32> = HashMap::new();

    for module in modules {
        let path = Path::new(&module.path);
        let parts: Vec<&str> = path
            .parent()
            .map(|p| p.to_str().unwrap_or(""))
            .unwrap_or("")
            .split('/')
            .filter(|s| !s.is_empty())
            .collect();

        let mod_name = if parts.is_empty() {
            "./".to_string()
        } else {
            format!("{}/", parts.join("/"))
        };

        *mod_counts.entry(mod_name).or_insert(0) +=
            (module.functions.len() + module.classes.len()) as i32;
    }

    let mut list: Vec<Module> = mod_counts
        .into_iter()
        .map(|(name, count)| Module { name, count })
        .collect();
    list.sort_by(|a, b| a.name.cmp(&b.name));
    list
}
