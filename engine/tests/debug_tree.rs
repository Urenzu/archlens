use tree_sitter::Parser;

fn print_tree(node: tree_sitter::Node, source: &[u8], indent: usize) {
    let kind = node.kind();
    let text_preview = node
        .utf8_text(source)
        .unwrap_or("")
        .lines()
        .next()
        .unwrap_or("")
        .chars()
        .take(60)
        .collect::<String>();

    let field_name = node
        .parent()
        .and_then(|p| {
            for i in 0..p.child_count() {
                if let Some(c) = p.child(i) {
                    if c.id() == node.id() {
                        return p.field_name_for_child(i as u32);
                    }
                }
            }
            None
        })
        .unwrap_or("");

    let prefix = if !field_name.is_empty() {
        format!("{}: ", field_name)
    } else {
        String::new()
    };

    println!(
        "{:indent$}{}{} [{}-{}] {:?}",
        "",
        prefix,
        kind,
        node.start_position().row,
        node.end_position().row,
        text_preview,
        indent = indent
    );

    let mut cursor = node.walk();
    for child in node.named_children(&mut cursor) {
        print_tree(child, source, indent + 2);
    }
}

#[test]
fn debug_handle_admin_request() {
    let source = r#"def handle_admin_request(request):
    if not authorize(request, role="admin"):
        return format_response(403, "Forbidden")
    action = request.get("params", {}).get("action")
    if action == "list_users":
        return list_all_users(request)
    elif action == "run_query":
        return run_custom_query(request)
    elif action == "render":
        return render_template(request)
    else:
        return format_response(400, "Unknown action")
"#;

    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_python::language())
        .unwrap();
    let tree = parser.parse(source, None).unwrap();
    println!("\n=== handle_admin_request tree ===");
    print_tree(tree.root_node(), source.as_bytes(), 0);
}

#[test]
fn debug_validate_token() {
    let source = r#"def validate_token(token):
    if not token or len(token) < 10:
        return False
    parts = token.split(".")
    if len(parts) != 3:
        return False
    try:
        payload = decode_payload(parts[1])
        signature = parts[2]
        return verify_signature(parts[0] + "." + parts[1], signature)
    except Exception:
        return False
"#;

    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_python::language())
        .unwrap();
    let tree = parser.parse(source, None).unwrap();
    println!("\n=== validate_token tree ===");
    print_tree(tree.root_node(), source.as_bytes(), 0);
}

#[test]
fn debug_build_template() {
    let source = r#"def build_template(name, data):
    template = load_template(name)
    rendered = eval(f'f"""{template}"""', {"data": data})
    return format_response(200, rendered)
"#;

    let mut parser = Parser::new();
    parser
        .set_language(&tree_sitter_python::language())
        .unwrap();
    let tree = parser.parse(source, None).unwrap();
    println!("\n=== build_template tree ===");
    print_tree(tree.root_node(), source.as_bytes(), 0);
}
