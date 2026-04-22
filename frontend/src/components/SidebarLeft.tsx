import { useState, useMemo } from "react";
import type { GraphNode, Layer } from "../types/graph";
import { fileColor, assignFileColors } from "../lib/fileColors";
import styles from "./SidebarLeft.module.css";

const LAYER_ORDER: Layer[] = ["frontend", "backend", "shared", "unknown"];

const LAYER_LABEL: Record<Layer, string> = {
  frontend: "Frontend",
  backend:  "Backend",
  shared:   "Shared",
  config:   "Config",
  unknown:  "Other",
};

interface Props {
  nodes: GraphNode[];
  selectedNode: GraphNode | null;
  selectedFileId: string | null;
  onSelectNode: (id: string) => void;
  onSelectFile: (file: string) => void;
  focusedLayer: Layer | null;
  onFocusLayer: (layer: Layer | null) => void;
}

export default function SidebarLeft({
  nodes, selectedNode, selectedFileId,
  onSelectNode, onSelectFile,
  focusedLayer, onFocusLayer,
}: Props) {
  const [collapsedFiles, setCollapsedFiles] = useState<Set<string>>(new Set());
  const [collapsedLayers, setCollapsedLayers] = useState<Set<Layer>>(new Set());

  const fileColorMap = useMemo(
    () => assignFileColors(nodes.map((n) => n.file ?? "").filter(Boolean)),
    [nodes],
  );

  // Group files by layer, then files within each layer
  const layerGroups = useMemo(() => {
    const map = new Map<Layer, Map<string, GraphNode[]>>();
    for (const n of nodes) {
      if (!n.file) continue;
      const layer: Layer = n.layer ?? "unknown";
      if (!map.has(layer)) map.set(layer, new Map());
      const fileMap = map.get(layer)!;
      const arr = fileMap.get(n.file) ?? [];
      arr.push(n);
      fileMap.set(n.file, arr);
    }
    // Sort files within each layer
    for (const fileMap of map.values()) {
      const sorted = new Map([...fileMap.entries()].sort(([a], [b]) => a.localeCompare(b)));
      for (const [k] of fileMap) fileMap.delete(k);
      for (const [k, v] of sorted) fileMap.set(k, v);
    }
    return map;
  }, [nodes]);

  function toggleFile(file: string) {
    setCollapsedFiles((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });
  }

  function toggleLayer(layer: Layer) {
    setCollapsedLayers((prev) => {
      const next = new Set(prev);
      next.has(layer) ? next.delete(layer) : next.add(layer);
      return next;
    });
  }

  function handleFileClick(file: string) {
    onSelectFile(file);
    setCollapsedFiles((prev) => {
      const next = new Set(prev);
      next.delete(file);
      return next;
    });
  }

  function handleLayerClick(layer: Layer) {
    // Toggle focus: clicking the active layer clears it
    onFocusLayer(focusedLayer === layer ? null : layer);
  }

  const presentLayers = LAYER_ORDER.filter((l) => layerGroups.has(l));

  return (
    <div className={styles.sidebar}>
      <div className={styles.section}>
        {presentLayers.map((layer) => {
          const fileMap = layerGroups.get(layer)!;
          const isLayerCollapsed = collapsedLayers.has(layer);
          const isLayerFocused = focusedLayer === layer;
          const isDimmed = focusedLayer !== null && !isLayerFocused;
          const totalNodes = [...fileMap.values()].reduce((s, arr) => s + arr.length, 0);

          return (
            <div
              key={layer}
              className={`${styles.layerGroup} ${isDimmed ? styles.layerDimmed : ""}`}
            >
              {/* Layer header */}
              <div
                className={`${styles.layerRow} ${isLayerFocused ? styles.layerActive : ""}`}
                onClick={() => handleLayerClick(layer)}
              >
                <span
                  className={styles.layerChevron}
                  onClick={(e) => { e.stopPropagation(); toggleLayer(layer); }}
                >
                  {isLayerCollapsed ? "▸" : "▾"}
                </span>
                <span className={styles.layerLabel}>{LAYER_LABEL[layer]}</span>
                <span className={styles.layerCount}>{fileMap.size} files · {totalNodes} fn</span>
                {isLayerFocused && <span className={styles.focusBadge}>focused</span>}
              </div>

              {/* Files within this layer */}
              {!isLayerCollapsed && [...fileMap.entries()].map(([file, fileNodes]) => {
                const colorIdx = fileColorMap.get(file) ?? 0;
                const palette = fileColor(colorIdx);
                const isOpen = !collapsedFiles.has(file);
                const isActive = file === selectedFileId;
                const basename = file.split("/").pop() ?? file;
                const dirname = file.includes("/")
                  ? file.slice(0, file.lastIndexOf("/"))
                  : null;

                return (
                  <div key={file}>
                    <div
                      className={`${styles.fileRow} ${isActive ? styles.fileActive : ""}`}
                      style={{ borderLeftColor: isActive ? palette.border : "transparent" }}
                      onClick={() => handleFileClick(file)}
                    >
                      <span
                        className={styles.chevron}
                        onClick={(e) => { e.stopPropagation(); toggleFile(file); }}
                      >
                        {isOpen ? "▾" : "▸"}
                      </span>
                      <span className={styles.fileIcon} style={{ color: palette.border }}>▪</span>
                      <span className={styles.fileName}>{basename}</span>
                      {dirname && <span className={styles.fileDir}>{dirname}/</span>}
                      <span className={styles.count}>{fileNodes.length}</span>
                    </div>

                    {isOpen && fileNodes.map((n) => {
                      const isNodeActive = n.id === selectedNode?.id;
                      return (
                        <div
                          key={n.id}
                          className={`${styles.fnRow} ${isNodeActive ? styles.fnActive : ""}`}
                          onClick={(e) => { e.stopPropagation(); onSelectNode(n.id); }}
                        >
                          <span className={styles.fnDot} style={{ background: palette.border }} />
                          <span className={styles.fnName}>{n.label}</span>
                          {n.isHot && n.isComplex
                            ? <span className={styles.tagHotCx}>hot·cx</span>
                            : n.isHot
                            ? <span className={styles.tagHot}>hot</span>
                            : n.isComplex
                            ? <span className={styles.tagCx}>cx</span>
                            : null}
                          {n.vulnerability && <span className={styles.tagVuln}>vuln</span>}
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
