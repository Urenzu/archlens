use std::collections::VecDeque;
use tree_sitter::{Node, Parser};

use super::{ClassInfo, FunctionInfo, ModuleInfo};

pub fn parse_file(source: &str, relative_path: &str) -> Option<ModuleInfo> {
    let mut parser = Parser::new();
    let language = if relative_path.ends_with(".tsx") || relative_path.ends_with(".jsx") {
        tree_sitter_typescript::language_tsx()
    } else {
        tree_sitter_typescript::language_typescript()
    };
    parser.set_language(&language).expect("failed to load TypeScript grammar");

    let tree = parser.parse(source, None)?;
    let root = tree.root_node();
    let source_bytes = source.as_bytes();

    let module_name = strip_ts_ext(relative_path)
        .replace('/', ".")
        .replace('\\', ".");

    let mut module = ModuleInfo {
        path: relative_path.to_string(),
        name: module_name.clone(),
        functions: Vec::new(),
        classes: Vec::new(),
        imports: Vec::new(),
        layer: crate::models::Layer::Unknown,
    };

    let mut cursor = root.walk();
    for child in root.named_children(&mut cursor) {
        visit_top_level(&child, source_bytes, &module_name, relative_path, &mut module);
    }

    Some(module)
}

fn strip_ts_ext(path: &str) -> &str {
    for ext in &[".tsx", ".ts", ".jsx", ".js"] {
        if let Some(s) = path.strip_suffix(ext) {
            return s;
        }
    }
    path
}

fn visit_top_level(
    node: &Node,
    src: &[u8],
    module_name: &str,
    file_path: &str,
    module: &mut ModuleInfo,
) {
    match node.kind() {
        "import_statement" => {
            extract_import(node, src, file_path, &mut module.imports);
        }
        "function_declaration" | "generator_function_declaration" => {
            if let Some(f) = make_fn(node, src, module_name, None) {
                module.functions.push(f);
            }
        }
        "lexical_declaration" | "variable_declaration" => {
            extract_var_fns(node, src, module_name, &mut module.functions);
        }
        "class_declaration" => {
            extract_class(node, src, module_name, module);
        }
        "export_statement" => {
            // Unwrap: export function/class/const/let/var/default
            if let Some(decl) = node.child_by_field_name("declaration") {
                visit_top_level(&decl, src, module_name, file_path, module);
            } else {
                // export default expr
                let mut c = node.walk();
                for child in node.named_children(&mut c) {
                    if matches!(child.kind(), "function_declaration" | "class_declaration" | "generator_function_declaration") {
                        visit_top_level(&child, src, module_name, file_path, module);
                    }
                }
            }
        }
        _ => {}
    }
}

// ── Import extraction ────────────────────────────────────────────────────────

fn extract_import(node: &Node, src: &[u8], file_path: &str, imports: &mut Vec<String>) {
    // import_statement has a `source` field: the string literal
    let source_str = node
        .child_by_field_name("source")
        .and_then(|n| n.utf8_text(src).ok())
        .unwrap_or("")
        .trim_matches(|c| c == '\'' || c == '"')
        .to_string();

    if source_str.is_empty() {
        return;
    }

    if source_str.starts_with('.') {
        // Relative import — resolve to dotted module name for edge building
        if let Some(resolved) = resolve_relative(&source_str, file_path) {
            imports.push(resolved);
        }
    } else {
        // Package import — store the bare package name for classifier
        let pkg = source_str.split('/').next().unwrap_or(&source_str);
        // Strip @scope prefix for matching (e.g. "@nestjs/common" → "@nestjs/common" kept whole)
        imports.push(source_str.clone());
        if pkg != source_str {
            imports.push(pkg.to_string());
        }
    }
}

/// Resolve a relative import path to the dotted module name used in our graph.
/// e.g. from "frontend/src/components/Dashboard.tsx", "../hooks/useAuth"
///      → "frontend.src.hooks.useAuth"
fn resolve_relative(import_path: &str, from_file: &str) -> Option<String> {
    // Get directory of current file
    let dir = from_file.rsplit_once('/').map(|(d, _)| d).unwrap_or("");
    let mut parts: Vec<&str> = dir.split('/').filter(|s| !s.is_empty()).collect();

    for seg in import_path.split('/') {
        match seg {
            "." => {}
            ".." => { parts.pop(); }
            s => parts.push(s),
        }
    }

    let joined = parts.join(".");
    // Strip any remaining extension
    let stripped = if let Some(p) = joined.strip_suffix(".tsx")
        .or_else(|| joined.strip_suffix(".ts"))
        .or_else(|| joined.strip_suffix(".jsx"))
        .or_else(|| joined.strip_suffix(".js")) {
        p.to_string()
    } else {
        joined
    };

    if stripped.is_empty() { None } else { Some(stripped) }
}

// ── Function extraction ──────────────────────────────────────────────────────

fn make_fn(node: &Node, src: &[u8], module_name: &str, class_name: Option<&str>) -> Option<FunctionInfo> {
    let name = node
        .child_by_field_name("name")
        .and_then(|n| n.utf8_text(src).ok())
        .unwrap_or("")
        .to_string();

    if name.is_empty() {
        return None;
    }

    let qname = match class_name {
        Some(cls) => format!("{}.{}.{}", module_name, cls, name),
        None => format!("{}.{}", module_name, name),
    };

    let lineno = node.start_position().row as i32 + 1;
    let end_lineno = node.end_position().row as i32 + 1;

    let body = node.child_by_field_name("body");
    let calls = body.map(|b| extract_calls(&b, src)).unwrap_or_default();
    let complexity = body.map(|b| compute_complexity(&b)).unwrap_or(1);
    let max_nesting = body.map(|b| compute_max_nesting(&b, 0)).unwrap_or(0);
    let params = count_params(node, src);

    Some(FunctionInfo {
        name,
        qualified_name: qname,
        module: module_name.to_string(),
        class_name: class_name.map(|s| s.to_string()),
        lineno,
        end_lineno,
        loc: end_lineno - lineno + 1,
        calls,
        complexity,
        params,
        max_nesting,
        vulnerabilities: Vec::new(),
    })
}

/// Extract arrow functions and function expressions from const/let/var declarations.
/// e.g. `const foo = () => { ... }` or `const foo = function() { ... }`
fn extract_var_fns(node: &Node, src: &[u8], module_name: &str, fns: &mut Vec<FunctionInfo>) {
    let mut cursor = node.walk();
    for decl in node.named_children(&mut cursor) {
        if decl.kind() != "variable_declarator" {
            continue;
        }
        let name_node = match decl.child_by_field_name("name") {
            Some(n) => n,
            None => continue,
        };
        // Only handle simple identifier names (not destructuring)
        if name_node.kind() != "identifier" {
            continue;
        }
        let name = match name_node.utf8_text(src) {
            Ok(n) => n.to_string(),
            Err(_) => continue,
        };

        let value = match decl.child_by_field_name("value") {
            Some(v) => v,
            None => continue,
        };

        let body_node = match value.kind() {
            "arrow_function" | "function_expression" | "generator_function" => {
                value.child_by_field_name("body")
            }
            _ => continue,
        };

        let lineno = decl.start_position().row as i32 + 1;
        let end_lineno = decl.end_position().row as i32 + 1;
        let calls = body_node.map(|b| extract_calls(&b, src)).unwrap_or_default();
        let complexity = body_node.map(|b| compute_complexity(&b)).unwrap_or(1);
        let max_nesting = body_node.map(|b| compute_max_nesting(&b, 0)).unwrap_or(0);
        let params = count_params(&value, src);

        fns.push(FunctionInfo {
            name: name.clone(),
            qualified_name: format!("{}.{}", module_name, name),
            module: module_name.to_string(),
            class_name: None,
            lineno,
            end_lineno,
            loc: end_lineno - lineno + 1,
            calls,
            complexity,
            params,
            max_nesting,
            vulnerabilities: Vec::new(),
        });
    }
}

// ── Class extraction ─────────────────────────────────────────────────────────

fn extract_class(node: &Node, src: &[u8], module_name: &str, module: &mut ModuleInfo) {
    let name = node
        .child_by_field_name("name")
        .and_then(|n| n.utf8_text(src).ok())
        .unwrap_or("")
        .to_string();

    if name.is_empty() {
        return;
    }

    let qname = format!("{}.{}", module_name, name);
    let lineno = node.start_position().row as i32 + 1;
    let end_lineno = node.end_position().row as i32 + 1;

    let mut ci = ClassInfo {
        name: name.clone(),
        qualified_name: qname,
        module: module_name.to_string(),
        lineno,
        end_lineno,
        methods: Vec::new(),
    };

    if let Some(body) = node.child_by_field_name("body") {
        let mut c = body.walk();
        for item in body.named_children(&mut c) {
            match item.kind() {
                "method_definition" => {
                    if let Some(f) = make_fn(&item, src, module_name, Some(&name)) {
                        ci.methods.push(f.qualified_name.clone());
                        module.functions.push(f);
                    }
                }
                "public_field_definition" => {
                    // class field with arrow function: foo = () => {}
                    if let Some(val) = item.child_by_field_name("value") {
                        if matches!(val.kind(), "arrow_function" | "function_expression") {
                            let field_name = item
                                .child_by_field_name("name")
                                .and_then(|n| n.utf8_text(src).ok())
                                .unwrap_or("")
                                .to_string();
                            if !field_name.is_empty() {
                                let body_node = val.child_by_field_name("body");
                                let lineno = item.start_position().row as i32 + 1;
                                let end_lineno = item.end_position().row as i32 + 1;
                                let calls = body_node.map(|b| extract_calls(&b, src)).unwrap_or_default();
                                let qname = format!("{}.{}.{}", module_name, name, field_name);
                                ci.methods.push(qname.clone());
                                module.functions.push(FunctionInfo {
                                    name: field_name.clone(),
                                    qualified_name: qname,
                                    module: module_name.to_string(),
                                    class_name: Some(name.clone()),
                                    lineno,
                                    end_lineno,
                                    loc: end_lineno - lineno + 1,
                                    calls,
                                    complexity: 1,
                                    params: count_params(&val, src),
                                    max_nesting: 0,
                                    vulnerabilities: Vec::new(),
                                });
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    }

    module.classes.push(ci);
}

// ── Calls, complexity, nesting ───────────────────────────────────────────────

fn extract_calls(node: &Node, src: &[u8]) -> Vec<String> {
    let mut calls = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let mut queue: VecDeque<Node> = VecDeque::new();

    let mut c = node.walk();
    for child in node.named_children(&mut c) {
        queue.push_back(child);
    }

    while let Some(n) = queue.pop_front() {
        if n.kind() == "call_expression" {
            if let Some(func) = n.child_by_field_name("function") {
                let name = match func.kind() {
                    "identifier" => func.utf8_text(src).unwrap_or("").to_string(),
                    "member_expression" => func
                        .child_by_field_name("property")
                        .and_then(|p| p.utf8_text(src).ok())
                        .unwrap_or("")
                        .to_string(),
                    _ => String::new(),
                };
                if !name.is_empty() && seen.insert(name.clone()) {
                    calls.push(name);
                }
            }
            // Still descend into arguments
            if let Some(args) = n.child_by_field_name("arguments") {
                let mut c2 = args.walk();
                for child in args.named_children(&mut c2) {
                    queue.push_back(child);
                }
            }
        } else {
            let mut c2 = n.walk();
            for child in n.named_children(&mut c2) {
                queue.push_back(child);
            }
        }
    }

    calls
}

fn count_params(node: &Node, _src: &[u8]) -> i32 {
    let params = match node.child_by_field_name("parameters")
        .or_else(|| node.child_by_field_name("parameter")) {
        Some(p) => p,
        None => return 0,
    };
    params.named_children(&mut params.walk())
        .filter(|n| matches!(n.kind(),
            "identifier" | "required_parameter" | "optional_parameter" |
            "rest_parameter" | "assignment_pattern"
        ))
        .count() as i32
}

fn compute_complexity(node: &Node) -> i32 {
    let mut complexity = 1;
    let mut queue: VecDeque<Node> = VecDeque::new();
    let mut c = node.walk();
    for child in node.named_children(&mut c) {
        queue.push_back(child);
    }
    while let Some(n) = queue.pop_front() {
        match n.kind() {
            "if_statement" | "for_statement" | "for_in_statement" | "while_statement" |
            "do_statement" | "switch_case" | "catch_clause" |
            "ternary_expression" | "optional_chain" => {
                complexity += 1;
            }
            "binary_expression" => {
                if let Some(op) = n.child(1) {
                    if op.kind() == "&&" || op.kind() == "||" || op.kind() == "??" {
                        complexity += 1;
                    }
                }
            }
            _ => {}
        }
        let mut c2 = n.walk();
        for child in n.named_children(&mut c2) {
            queue.push_back(child);
        }
    }
    complexity
}

fn compute_max_nesting(node: &Node, depth: i32) -> i32 {
    let mut max = depth;
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        let new_depth = match child.kind() {
            "if_statement" | "for_statement" | "for_in_statement" |
            "while_statement" | "do_statement" | "switch_statement" => depth + 1,
            _ => depth,
        };
        let child_max = compute_max_nesting(&child, new_depth);
        if child_max > max {
            max = child_max;
        }
    }
    max
}
