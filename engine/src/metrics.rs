use std::collections::VecDeque;
use tree_sitter::Node;

/// Compute cyclomatic complexity of a tree-sitter node (function body).
/// Mirrors Python's _compute_complexity using ast.walk (BFS).
pub fn compute_complexity(node: Node) -> i32 {
    let mut complexity = 1;
    let mut queue = VecDeque::new();
    queue.push_back(node);

    while let Some(current) = queue.pop_front() {
        match current.kind() {
            "if_statement" | "elif_clause" | "conditional_expression" => complexity += 1,
            "for_statement" | "while_statement" => complexity += 1,
            "except_clause" => complexity += 1,
            "with_statement" => complexity += 1,
            "assert_statement" => complexity += 1,
            "boolean_operator" => complexity += 1,
            _ => {}
        }

        // Add all named children to queue
        for i in 0..current.named_child_count() {
            if let Some(child) = current.named_child(i) {
                queue.push_back(child);
            }
        }
    }

    complexity
}

/// Compute maximum block nesting depth within a function body.
/// Mirrors Python's _compute_max_nesting using recursive DFS.
///
/// In Python AST, elif chains create nested If nodes (depth increments for each).
/// In tree-sitter, elif_clause nodes are flat siblings of if_statement.
/// We handle this by incrementing depth for each successive elif_clause sibling.
pub fn compute_max_nesting(node: Node) -> i32 {
    fn depth(n: Node, current: i32) -> i32 {
        let mut max_d = current;
        let mut elif_offset = 0;

        for i in 0..n.named_child_count() {
            if let Some(child) = n.named_child(i) {
                match child.kind() {
                    "if_statement" | "for_statement" | "while_statement"
                    | "with_statement" | "try_statement" => {
                        elif_offset = 0;
                        max_d = max_d.max(depth(child, current + 1));
                    }
                    "elif_clause" => {
                        // Each successive elif adds depth (matching Python's nested If)
                        elif_offset += 1;
                        max_d = max_d.max(depth(child, current + elif_offset));
                    }
                    _ => {
                        max_d = max_d.max(depth(child, current));
                    }
                }
            }
        }

        max_d
    }

    depth(node, 0)
}
