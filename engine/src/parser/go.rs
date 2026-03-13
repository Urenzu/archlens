use std::collections::VecDeque;
use tree_sitter::{Node, Parser};

use super::{ClassInfo, FunctionInfo, ModuleInfo};

pub fn parse_file(source: &str, relative_path: &str) -> Option<ModuleInfo> {
    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_go::language())
        .expect("failed to load Go grammar");

    let tree = parser.parse(source, None)?;
    let root = tree.root_node();
    let source_bytes = source.as_bytes();

    // Module name: strip .go suffix, replace path separators with dots
    let module_name = relative_path
        .strip_suffix(".go")
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

    let mut cursor = root.walk();
    for child in root.named_children(&mut cursor) {
        match child.kind() {
            "import_declaration" => {
                extract_imports(&child, source_bytes, &mut module.imports, &relative_path);
            }
            "function_declaration" => {
                if let Some(f) = make_function_info(&child, source_bytes, &module_name, None) {
                    module.functions.push(f);
                }
            }
            "method_declaration" => {
                // Get the receiver type name to group methods under a "class"
                let receiver_type = extract_receiver_type(&child, source_bytes);
                if let Some(f) =
                    make_function_info(&child, source_bytes, &module_name, receiver_type.as_deref())
                {
                    // Add a synthetic ClassInfo entry if first method of this type
                    let class_qname = receiver_type
                        .as_deref()
                        .map(|t| format!("{}.{}", module_name, t))
                        .unwrap_or_else(|| module_name.clone());

                    if !module.classes.iter().any(|c| c.qualified_name == class_qname) {
                        module.classes.push(ClassInfo {
                            name: receiver_type.clone().unwrap_or_default(),
                            qualified_name: class_qname.clone(),
                            module: module_name.clone(),
                            lineno: child.start_position().row as i32 + 1,
                            end_lineno: child.end_position().row as i32 + 1,
                            methods: Vec::new(),
                        });
                    }

                    // Track method name on the class
                    if let Some(class) = module
                        .classes
                        .iter_mut()
                        .find(|c| c.qualified_name == class_qname)
                    {
                        class.methods.push(f.name.clone());
                    }

                    module.functions.push(f);
                }
            }
            _ => {}
        }
    }

    Some(module)
}

fn extract_receiver_type(node: &Node, source_bytes: &[u8]) -> Option<String> {
    // method_declaration → parameter_list (receiver) → parameter_declaration → type_identifier or pointer_type
    let params = node.child_by_field_name("receiver")?;
    let param = params.named_child(0)?;
    let type_node = param.child_by_field_name("type")?;
    let name = match type_node.kind() {
        "pointer_type" => {
            // *TypeName
            type_node
                .named_child(0)
                .map(|n| n.utf8_text(source_bytes).unwrap_or("").to_string())
        }
        _ => Some(type_node.utf8_text(source_bytes).unwrap_or("").to_string()),
    };
    name.filter(|s| !s.is_empty())
}

fn make_function_info(
    node: &Node,
    source_bytes: &[u8],
    module_name: &str,
    class_name: Option<&str>,
) -> Option<FunctionInfo> {
    let name_node = node.child_by_field_name("name")?;
    let name = name_node.utf8_text(source_bytes).ok()?.to_string();

    let qualified_name = match class_name {
        Some(cls) => format!("{}.{}.{}", module_name, cls, name),
        None => format!("{}.{}", module_name, name),
    };

    let lineno = node.start_position().row as i32 + 1;
    let end_lineno = node.end_position().row as i32 + 1;
    let loc = end_lineno - lineno + 1;

    let params = count_params(node);

    let body = node.child_by_field_name("body");
    let (calls, complexity, max_nesting) = if let Some(body) = body {
        (
            extract_calls(&body, source_bytes),
            compute_complexity(&body),
            compute_max_nesting(&body, 0),
        )
    } else {
        (Vec::new(), 1, 0)
    };

    Some(FunctionInfo {
        name,
        qualified_name,
        module: module_name.to_string(),
        class_name: class_name.map(|s| s.to_string()),
        lineno,
        end_lineno,
        loc,
        calls,
        complexity,
        params,
        max_nesting,
        vulnerabilities: Vec::new(),
    })
}

fn count_params(node: &Node) -> i32 {
    let params = match node.child_by_field_name("parameters") {
        Some(p) => p,
        None => return 0,
    };
    // parameter_declaration children — each may declare multiple names
    let mut count = 0;
    let mut cursor = params.walk();
    for child in params.named_children(&mut cursor) {
        if child.kind() == "parameter_declaration" || child.kind() == "variadic_parameter_declaration" {
            // Count name identifiers in this declaration
            let names = child.named_children(&mut child.walk())
                .filter(|n| n.kind() == "identifier")
                .count();
            count += names.max(1) as i32;
        }
    }
    count
}

fn extract_calls(body: &Node, source_bytes: &[u8]) -> Vec<String> {
    let mut calls = Vec::new();
    let mut seen = std::collections::HashSet::new();
    let mut queue: VecDeque<Node> = VecDeque::new();

    let mut c = body.walk();
    for child in body.named_children(&mut c) {
        queue.push_back(child);
    }

    while let Some(node) = queue.pop_front() {
        if node.kind() == "call_expression" {
            if let Some(func_node) = node.child_by_field_name("function") {
                let name = extract_call_name(&func_node, source_bytes);
                if !name.is_empty() && seen.insert(name.clone()) {
                    calls.push(name);
                }
            }
            if let Some(args) = node.child_by_field_name("arguments") {
                let mut c2 = args.walk();
                for child in args.named_children(&mut c2) {
                    queue.push_back(child);
                }
            }
        } else {
            let mut c2 = node.walk();
            for child in node.named_children(&mut c2) {
                queue.push_back(child);
            }
        }
    }

    calls
}

fn extract_call_name(node: &Node, source_bytes: &[u8]) -> String {
    match node.kind() {
        "identifier" => node.utf8_text(source_bytes).unwrap_or("").to_string(),
        "selector_expression" => {
            // pkg.Func or obj.Method — take the field (right side)
            node.child_by_field_name("field")
                .and_then(|n| n.utf8_text(source_bytes).ok())
                .unwrap_or("")
                .to_string()
        }
        _ => String::new(),
    }
}

fn extract_imports(node: &Node, source_bytes: &[u8], imports: &mut Vec<String>, relative_path: &str) {
    // import_declaration → import_spec_list → import_spec, or single import_spec
    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        match child.kind() {
            "import_spec_list" => {
                let mut c2 = child.walk();
                for spec in child.named_children(&mut c2) {
                    if spec.kind() == "import_spec" {
                        add_import(&spec, source_bytes, imports, relative_path);
                    }
                }
            }
            "import_spec" => {
                add_import(&child, source_bytes, imports, relative_path);
            }
            _ => {}
        }
    }
}

fn add_import(spec: &Node, source_bytes: &[u8], imports: &mut Vec<String>, relative_path: &str) {
    if let Some(path_node) = spec.child_by_field_name("path") {
        let raw = path_node.utf8_text(source_bytes).unwrap_or("");
        // Strip surrounding quotes
        let raw = raw.trim_matches('"');
        // Convert import path to module name format matching our naming convention
        // e.g. "github.com/sample/api/handlers" -> "handlers.handlers" if file is handlers/...
        // We keep just the last path component to match how we name modules
        let last = raw.split('/').last().unwrap_or(raw);
        // Check if this import matches a file in the same repo by comparing last component
        // to our module names (which are derived from file paths)
        let repo_base = relative_path.split('/').next().unwrap_or("");
        if raw.contains(repo_base) || !raw.contains('.') {
            imports.push(last.to_string());
        }
    }
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
            "if_statement"
            | "for_statement"
            | "range_clause"
            | "type_switch_statement"
            | "expression_switch_statement"
            | "select_statement"
            | "communication_case"
            | "expression_case" => {
                complexity += 1;
            }
            "binary_expression" => {
                if let Some(op) = n.child(1) {
                    if op.kind() == "&&" || op.kind() == "||" {
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
            "if_statement" | "for_statement" | "select_statement"
            | "expression_switch_statement" | "type_switch_statement" => depth + 1,
            _ => depth,
        };
        let child_max = compute_max_nesting(&child, new_depth);
        if child_max > max {
            max = child_max;
        }
    }
    max
}
