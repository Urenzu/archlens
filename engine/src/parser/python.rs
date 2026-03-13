use std::collections::VecDeque;
use tree_sitter::{Node, Parser};

use super::{ClassInfo, FunctionInfo, ModuleInfo};
use crate::metrics::{compute_complexity, compute_max_nesting};
use crate::vulnerability::detect_vulnerabilities;

/// Parse a Python source file and extract functions, classes, and calls.
pub fn parse_file(source: &str, relative_path: &str) -> Option<ModuleInfo> {
    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_python::language())
        .expect("failed to load Python grammar");

    let tree = parser.parse(source, None)?;
    let root = tree.root_node();
    let source_bytes = source.as_bytes();

    // Module name: strip .py suffix, replace path separators with dots
    let module_name = relative_path
        .strip_suffix(".py")
        .unwrap_or(relative_path)
        .replace('/', ".")
        .replace('\\', ".");

    let mut module = ModuleInfo {
        path: relative_path.to_string(),
        name: module_name.clone(),
        functions: Vec::new(),
        classes: Vec::new(),
        imports: Vec::new(),
    };

    // Iterate top-level children only (like Python's ast.iter_child_nodes(tree))
    let mut cursor = root.walk();
    for child in root.named_children(&mut cursor) {
        match child.kind() {
            "import_statement" => {
                extract_import(&child, source_bytes, &mut module.imports);
            }
            "import_from_statement" => {
                extract_import_from(&child, source_bytes, &mut module.imports);
            }
            "function_definition" => {
                let fi = make_function_info(child, &module_name, None, source_bytes);
                module.functions.push(fi);
            }
            "class_definition" => {
                let class_name = child
                    .child_by_field_name("name")
                    .and_then(|n| n.utf8_text(source_bytes).ok())
                    .unwrap_or("")
                    .to_string();

                let qname = format!("{}.{}", module_name, class_name);
                let lineno = child.start_position().row as i32 + 1;
                let end_lineno = child.end_position().row as i32 + 1;

                let mut ci = ClassInfo {
                    name: class_name.clone(),
                    qualified_name: qname,
                    module: module_name.clone(),
                    lineno,
                    end_lineno,
                    methods: Vec::new(),
                };

                // Extract methods from class body
                if let Some(body) = child.child_by_field_name("body") {
                    let mut body_cursor = body.walk();
                    for item in body.named_children(&mut body_cursor) {
                        if item.kind() == "function_definition" {
                            let fi = make_function_info(
                                item,
                                &module_name,
                                Some(&class_name),
                                source_bytes,
                            );
                            ci.methods.push(fi.qualified_name.clone());
                            module.functions.push(fi);
                        }
                    }
                }

                module.classes.push(ci);
            }
            _ => {}
        }
    }

    Some(module)
}

fn extract_import(node: &Node, source: &[u8], imports: &mut Vec<String>) {
    // import os  →  dotted_name "os"
    // import os.path  →  dotted_name "os.path"
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        if child.kind() == "dotted_name" {
            if let Ok(name) = child.utf8_text(source) {
                imports.push(name.to_string());
            }
        }
    }
}

fn extract_import_from(node: &Node, source: &[u8], imports: &mut Vec<String>) {
    // from auth import authenticate  →  module_name: dotted_name "auth"
    if let Some(module_name) = node.child_by_field_name("module_name") {
        if let Ok(name) = module_name.utf8_text(source) {
            imports.push(name.to_string());
        }
    }
}

fn make_function_info(
    node: Node,
    module_name: &str,
    class_name: Option<&str>,
    source: &[u8],
) -> FunctionInfo {
    let name = node
        .child_by_field_name("name")
        .and_then(|n| n.utf8_text(source).ok())
        .unwrap_or("")
        .to_string();

    let prefix = match class_name {
        Some(cls) => format!("{}.{}", module_name, cls),
        None => module_name.to_string(),
    };
    let qname = format!("{}.{}", prefix, name);

    let lineno = node.start_position().row as i32 + 1;
    let end_lineno = node.end_position().row as i32 + 1;
    let loc = end_lineno - lineno + 1;

    // Count parameters
    let param_count = count_params(&node, source, class_name.is_some());

    // Extract calls (BFS to match Python's ast.walk order)
    let calls = extract_calls(node, source);

    // Compute complexity and nesting
    let complexity = compute_complexity(node);
    let max_nesting = compute_max_nesting(node);

    // Detect vulnerabilities
    let vulnerabilities = detect_vulnerabilities(node, source);

    FunctionInfo {
        name,
        qualified_name: qname,
        module: module_name.to_string(),
        class_name: class_name.map(|s| s.to_string()),
        lineno,
        end_lineno,
        loc,
        calls,
        complexity,
        params: param_count,
        max_nesting,
        vulnerabilities,
    }
}

fn count_params(node: &Node, source: &[u8], is_method: bool) -> i32 {
    let params_node = match node.child_by_field_name("parameters") {
        Some(p) => p,
        None => return 0,
    };

    let mut count = 0;
    let mut cursor = params_node.walk();
    for child in params_node.named_children(&mut cursor) {
        match child.kind() {
            "identifier" | "default_parameter" | "typed_parameter"
            | "typed_default_parameter" => {
                count += 1;
            }
            // Stop counting after *args (keyword-only params follow)
            "list_splat_pattern" => break,
            "dictionary_splat_pattern" => {
                // **kwargs — don't count, and it's always last
            }
            _ => {}
        }
    }

    // Subtract 1 for self/cls in methods
    if is_method && count > 0 {
        // Verify first param is self/cls
        if let Some(first) = params_node.named_child(0) {
            if first.kind() == "identifier" {
                if let Ok(name) = first.utf8_text(source) {
                    if name == "self" || name == "cls" {
                        count -= 1;
                    }
                }
            }
        }
    }

    count
}

/// Extract names of functions called within a node, using BFS
/// to match Python's ast.walk order.
///
/// Tree-sitter CST has extra wrapper nodes (`block`, `expression_statement`)
/// that Python's AST doesn't have. We "flatten" these by inlining their children
/// at the same BFS level, producing the same traversal order as ast.walk.
fn extract_calls(node: Node, source: &[u8]) -> Vec<String> {
    let mut calls = Vec::new();
    let mut queue = VecDeque::new();
    queue.push_back(node);

    while let Some(current) = queue.pop_front() {
        if current.kind() == "call" {
            if let Some(func) = current.child_by_field_name("function") {
                match func.kind() {
                    "identifier" => {
                        if let Ok(name) = func.utf8_text(source) {
                            calls.push(name.to_string());
                        }
                    }
                    "attribute" => {
                        if let Some(attr) = func.child_by_field_name("attribute") {
                            if let Ok(name) = attr.utf8_text(source) {
                                calls.push(name.to_string());
                            }
                        }
                    }
                    _ => {}
                }
            }
        }

        // Add named children to queue, flattening wrapper nodes
        // to match Python AST's BFS depth structure
        let mut cursor = current.walk();
        for child in current.named_children(&mut cursor) {
            enqueue_flattened(child, &mut queue);
        }
    }

    calls
}

/// Enqueue a node, but if it's a structural wrapper that Python's AST doesn't
/// have (block, expression_statement), inline its children at the same level.
fn enqueue_flattened<'a>(node: Node<'a>, queue: &mut VecDeque<Node<'a>>) {
    match node.kind() {
        "block" | "expression_statement" => {
            let mut cursor = node.walk();
            for child in node.named_children(&mut cursor) {
                enqueue_flattened(child, queue);
            }
        }
        _ => {
            queue.push_back(node);
        }
    }
}
