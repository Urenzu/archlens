import type { GraphNode, GraphEdge, Module } from "../types/graph";

export const mockNodes: GraphNode[] = [
  {
    id: "handleRequest",
    label: "handleRequest",
    kind: "function",
    x: 385, y: 60, width: 130, height: 34,
    file: "api/handlers.py",
    metrics: { cyclomatic: 14, loc: 187, params: 2, maxNesting: 3, callers: 2, callees: 4 },
    isHot: true, isComplex: true,
  },
  {
    id: "validateToken",
    label: "validateToken",
    kind: "function",
    x: 60, y: 180, width: 110, height: 34,
    file: "middleware/auth.py",
    metrics: { cyclomatic: 5, loc: 52, params: 1, maxNesting: 2, callers: 1, callees: 1 },
  },
  {
    id: "parseBody",
    label: "parseBody",
    kind: "function",
    x: 250, y: 180, width: 110, height: 34,
    file: "api/handlers.py",
    metrics: { cyclomatic: 4, loc: 38, params: 1, maxNesting: 2, callers: 1, callees: 0 },
  },
  {
    id: "buildResponse",
    label: "buildResponse",
    kind: "function",
    x: 530, y: 180, width: 110, height: 34,
    file: "api/handlers.py",
    metrics: { cyclomatic: 3, loc: 28, params: 1, maxNesting: 2, callers: 1, callees: 1 },
  },
  {
    id: "logRequest",
    label: "logRequest",
    kind: "function",
    x: 720, y: 180, width: 110, height: 34,
    file: "utils/logging.py",
    metrics: { cyclomatic: 2, loc: 18, params: 1, maxNesting: 2, callers: 1, callees: 1 },
  },
  {
    id: "fetchUser",
    label: "fetchUser",
    kind: "function",
    x: 60, y: 300, width: 110, height: 34,
    file: "db/queries.py",
    metrics: { cyclomatic: 4, loc: 42, params: 1, maxNesting: 1, callers: 1, callees: 0 },
    vulnerability: "SQL injection — unsanitized query param passed to rawSQL()",
  },
  {
    id: "sendJSON",
    label: "sendJSON",
    kind: "function",
    x: 530, y: 300, width: 110, height: 34,
    file: "api/handlers.py",
    metrics: { cyclomatic: 1, loc: 12, params: 1, maxNesting: 1, callers: 1, callees: 0 },
  },
  {
    id: "writeLog",
    label: "writeLog",
    kind: "function",
    x: 720, y: 300, width: 110, height: 34,
    file: "utils/logging.py",
    metrics: { cyclomatic: 1, loc: 8, params: 1, maxNesting: 1, callers: 1, callees: 0 },
  },
];

export const mockEdges: GraphEdge[] = [
  { id: "e1", source: "handleRequest", target: "validateToken", kind: "normal" },
  { id: "e2", source: "handleRequest", target: "parseBody",     kind: "normal" },
  { id: "e3", source: "handleRequest", target: "buildResponse", kind: "normal" },
  { id: "e4", source: "handleRequest", target: "logRequest",    kind: "normal" },
  { id: "e5", source: "validateToken", target: "fetchUser",     kind: "critical" },
  { id: "e6", source: "buildResponse", target: "sendJSON",      kind: "normal" },
  { id: "e7", source: "logRequest",    target: "writeLog",      kind: "normal" },
];

export const mockModules: Module[] = [
  { name: "api/", count: 48 },
  { name: "middleware/", count: 9 },
  { name: "db/", count: 22 },
  { name: "utils/", count: 17 },
];

export const mockCallers = [
  { name: "Router.dispatch", kind: "class" as const, depth: 1 },
  { name: "server.listen.cb", kind: "function" as const, depth: 1 },
  { name: "testHarness.inject", kind: "function" as const, depth: 1 },
];

export const mockRepoStats = {
  name: "github/myorg/platform-api",
  branch: "main",
  commit: "a3f9c2b",
  functions: 2847,
  classes: 184,
  modules: 62,
  vulns: 7,
};
