export type NodeKind = "function" | "class" | "module";
export type Layer = "frontend" | "backend" | "shared" | "config" | "unknown";

export interface GraphNode {
  id: string;
  label: string;
  kind: NodeKind;
  x: number;
  y: number;
  width: number;
  height: number;
  metrics: NodeMetrics;
  isHot?: boolean;
  isComplex?: boolean;
  vulnerability?: string;
  file?: string;
  layer?: Layer;
}

export interface NodeMetrics {
  cyclomatic: number;
  loc: number;
  params: number;
  maxNesting: number;
  callers: number;
  callees: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: "normal" | "critical";
}

export interface Module {
  name: string;
  count: number;
}

export interface Caller {
  name: string;
  kind: "function" | "class";
}

export interface RepoStats {
  name: string;
  branch: string;
  commit: string;
  functions: number;
  classes: number;
  modules: number;
  vulns: number;
}

export interface FileGraphEdge {
  source: string;   // relative file path
  target: string;   // relative file path
  callCount: number;
}

export interface AnalysisResult {
  nodes: GraphNode[];
  edges: GraphEdge[];
  fileEdges?: FileGraphEdge[];
  modules: Module[];
  callers: Record<string, Caller[]>;
  stats: RepoStats;
}
