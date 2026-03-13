pub mod go;
pub mod python;
pub mod typescript;

use crate::models::Layer;

/// Information about a parsed function.
#[derive(Debug, Clone)]
pub struct FunctionInfo {
    pub name: String,
    pub qualified_name: String,
    pub module: String,
    pub class_name: Option<String>,
    pub lineno: i32,
    pub end_lineno: i32,
    pub loc: i32,
    pub calls: Vec<String>,
    pub complexity: i32,
    pub params: i32,
    pub max_nesting: i32,
    pub vulnerabilities: Vec<String>,
}

/// Information about a parsed class.
#[derive(Debug, Clone)]
pub struct ClassInfo {
    pub name: String,
    pub qualified_name: String,
    pub module: String,
    pub lineno: i32,
    pub end_lineno: i32,
    pub methods: Vec<String>,
}

/// Information about a parsed module (file).
#[derive(Debug, Clone)]
pub struct ModuleInfo {
    pub path: String,
    pub name: String,
    pub functions: Vec<FunctionInfo>,
    pub classes: Vec<ClassInfo>,
    pub imports: Vec<String>,
    pub layer: Layer,
}
