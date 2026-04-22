import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type { AnalysisResult, Layer, RepoStats } from "./types/graph";
import { analyzeRepo } from "./api";
import Topbar from "./components/Topbar";
import SidebarLeft from "./components/SidebarLeft";
import SidebarRight from "./components/SidebarRight";
import GraphCanvas from "./components/GraphCanvas";
import ResizeHandle from "./components/ResizeHandle";
import styles from "./App.module.css";

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
  const [focusedLayer, setFocusedLayer] = useState<Layer | null>(null);

  const leftRef  = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  const nodes     = data?.nodes ?? [];
  const edges     = data?.edges ?? [];
  const fileEdges = data?.fileEdges;
  const callers   = data?.callers ?? {};
  const stats     = data?.stats ?? EMPTY_STATS;

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );
  const selectedCallers = useMemo(
    () => selectedNodeId ? (callers[selectedNodeId] ?? []) : [],
    [callers, selectedNodeId],
  );

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
      setFocusedLayer(null);
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
    <div className={styles.shell}>
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
      <div className={styles.workspace}>
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
          focusedLayer={focusedLayer}
        />
        <div ref={leftRef} className={styles.panelLeft}>
          <SidebarLeft
            nodes={nodes}
            selectedNode={selectedNode}
            selectedFileId={selectedFileId}
            onSelectNode={handleSelectNode}
            onSelectFile={handleSelectFile}
            focusedLayer={focusedLayer}
            onFocusLayer={setFocusedLayer}
          />
          <ResizeHandle side="left" panelRef={leftRef} />
        </div>
        <div ref={rightRef} className={styles.panelRight}>
          <ResizeHandle side="right" panelRef={rightRef} />
          <SidebarRight
            node={selectedNode}
            callers={selectedCallers}
            selectedFileId={selectedFileId}
            allNodes={nodes}
            fileEdges={fileEdges}
          />
        </div>
      </div>
    </div>
  );
}
