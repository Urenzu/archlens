use serde::{Deserialize, Serialize, Serializer};
use std::collections::HashMap;

fn serialize_f64_as_int<S: Serializer>(val: &f64, s: S) -> Result<S::Ok, S::Error> {
    s.serialize_i64(*val as i64)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeMetrics {
    pub cyclomatic: i32,
    pub loc: i32,
    pub params: i32,
    #[serde(rename = "maxNesting")]
    pub max_nesting: i32,
    pub callers: i32,
    pub callees: i32,
}

impl Default for NodeMetrics {
    fn default() -> Self {
        Self {
            cyclomatic: 1,
            loc: 0,
            params: 0,
            max_nesting: 0,
            callers: 0,
            callees: 0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum NodeKind {
    Function,
    Class,
    Module,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "lowercase")]
pub enum Layer {
    Frontend,
    Backend,
    Shared,
    Config,
    #[default]
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphNode {
    pub id: String,
    pub label: String,
    pub kind: NodeKind,
    #[serde(serialize_with = "serialize_f64_as_int")]
    pub x: f64,
    #[serde(serialize_with = "serialize_f64_as_int")]
    pub y: f64,
    #[serde(serialize_with = "serialize_f64_as_int")]
    pub width: f64,
    #[serde(serialize_with = "serialize_f64_as_int")]
    pub height: f64,
    pub metrics: NodeMetrics,
    #[serde(rename = "isHot", skip_serializing_if = "Option::is_none")]
    pub is_hot: Option<bool>,
    #[serde(rename = "isComplex", skip_serializing_if = "Option::is_none")]
    pub is_complex: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vulnerability: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub layer: Option<Layer>,
}

impl GraphNode {
    pub fn new(id: String, label: String, kind: NodeKind) -> Self {
        Self {
            id,
            label,
            kind,
            x: 0.0,
            y: 0.0,
            width: 110.0,
            height: 34.0,
            metrics: NodeMetrics::default(),
            is_hot: None,
            is_complex: None,
            vulnerability: None,
            file: None,
            layer: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum EdgeKind {
    Normal,
    Critical,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEdge {
    pub id: String,
    pub source: String,
    pub target: String,
    pub kind: EdgeKind,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Module {
    pub name: String,
    pub count: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Caller {
    pub name: String,
    pub kind: String,
    pub depth: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepoStats {
    pub name: String,
    pub branch: String,
    pub commit: String,
    pub functions: i32,
    pub classes: i32,
    pub modules: i32,
    pub vulns: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileEdge {
    pub source: String,
    pub target: String,
    #[serde(rename = "callCount")]
    pub call_count: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnalysisResult {
    pub nodes: Vec<GraphNode>,
    pub edges: Vec<GraphEdge>,
    #[serde(rename = "fileEdges")]
    pub file_edges: Vec<FileEdge>,
    pub modules: Vec<Module>,
    pub callers: HashMap<String, Vec<Caller>>,
    pub stats: RepoStats,
}
