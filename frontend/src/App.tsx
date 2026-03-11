import { useState, useCallback, useEffect, useRef } from "react";
import type { AnalysisResult, RepoStats } from "./types/graph";
import { analyzeRepo } from "./api";
import Topbar from "./components/Topbar";
import SidebarLeft from "./components/SidebarLeft";
import SidebarRight from "./components/SidebarRight";
import GraphCanvas from "./components/GraphCanvas";
import ResizeHandle from "./components/ResizeHandle";

const DEFAULT_REPO_PATH = import.meta.env.VITE_REPO_PATH || "";

const EMPTY_STATS: RepoStats = {
  name: "archlens",
  branch: "",
  commit: "",
  functions: 0,
  classes: 0,
  modules: 0,
  vulns: 0,
};

export default function App() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [repoPath, setRepoPath] = useState(DEFAULT_REPO_PATH);
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [viewMode, setViewMode] = useState<"functions" | "files">("functions");

  const leftRef  = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  const nodes     = data?.nodes ?? [];
  const edges     = data?.edges ?? [];
  const fileEdges = data?.fileEdges;
  const callers   = data?.callers ?? {};
  const stats     = data?.stats ?? EMPTY_STATS;

  const selectedNode    = nodes.find((n) => n.id === selectedNodeId) ?? null;
  const selectedCallers = selectedNodeId ? (callers[selectedNodeId] ?? []) : [];

  const clearSelection = useCallback(() => {
    setSelectedNodeId(null);
    setSelectedFileId(null);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") clearSelection();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clearSelection]);

  const handleSelectNode = useCallback((id: string) => {
    setSelectedNodeId((prev) => (prev === id ? null : id));
  }, []);

  const handleSelectFile = useCallback((file: string) => {
    setSelectedFileId((prev) => (prev === file ? null : file));
    setSelectedNodeId(null);
  }, []);

  const handleAnalyze = useCallback(async (path: string) => {
    if (!path.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeRepo(path);
      setData(result);
      setSelectedNodeId(null);
      setSelectedFileId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (DEFAULT_REPO_PATH) handleAnalyze(DEFAULT_REPO_PATH);
  }, [handleAnalyze]);

  function toggleLeft() {
    const el = leftRef.current;
    if (!el) return;
    if (!leftCollapsed) {
      el.dataset.width = el.style.width || `${el.offsetWidth}px`;
      el.style.width = "0px";
    } else {
      el.style.width = el.dataset.width || "220px";
    }
    setLeftCollapsed((c) => !c);
  }

  function toggleRight() {
    const el = rightRef.current;
    if (!el) return;
    if (!rightCollapsed) {
      el.dataset.width = el.style.width || `${el.offsetWidth}px`;
      el.style.width = "0px";
    } else {
      el.style.width = el.dataset.width || "260px";
    }
    setRightCollapsed((c) => !c);
  }

  return (
    <div style={{ display: "grid", gridTemplateRows: "auto 1fr", height: "100vh", overflow: "hidden" }}>
      <Topbar
        stats={stats}
        repoPath={repoPath}
        onRepoPathChange={setRepoPath}
        onAnalyze={handleAnalyze}
        loading={loading}
        error={error}
        leftCollapsed={leftCollapsed}
        rightCollapsed={rightCollapsed}
        onToggleLeft={toggleLeft}
        onToggleRight={toggleRight}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
      />
      <div style={{ display: "flex", overflow: "hidden" }}>
        <SidebarLeft
          ref={leftRef}
          nodes={nodes}
          selectedNode={selectedNode}
          selectedFileId={selectedFileId}
          onSelectNode={handleSelectNode}
          onSelectFile={handleSelectFile}
        />
        <ResizeHandle side="left" panelRef={leftRef} />
        <GraphCanvas
          nodes={nodes}
          edges={edges}
          fileEdges={fileEdges}
          selectedNodeId={selectedNodeId}
          selectedFileId={selectedFileId}
          onSelectNode={handleSelectNode}
          onSelectFile={handleSelectFile}
          viewMode={viewMode}
          loading={loading}
          hasSelection={!!(selectedFileId || selectedNodeId)}
          onClearSelection={clearSelection}
        />
        <ResizeHandle side="right" panelRef={rightRef} />
        <SidebarRight
          ref={rightRef}
          node={selectedNode}
          callers={selectedCallers}
          selectedFileId={selectedFileId}
          allNodes={nodes}
          fileEdges={fileEdges}
        />
      </div>
    </div>
  );
}
