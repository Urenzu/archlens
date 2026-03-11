import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import type { GraphNode, GraphEdge, FileGraphEdge } from "../types/graph";
import { fileColor, assignFileColors } from "../lib/fileColors";
import styles from "./GraphCanvas.module.css";

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  fileEdges?: FileGraphEdge[];
  selectedNodeId: string | null;
  selectedFileId: string | null;
  onSelectNode: (id: string) => void;
  onSelectFile: (file: string) => void;
  viewMode: "functions" | "files";
  loading?: boolean;
  hasSelection?: boolean;
  onClearSelection?: () => void;
}

interface Transform { x: number; y: number; scale: number; }

interface Tooltip {
  x: number;
  y: number;
  label: string;
  sub: string;
}

interface FileNode {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fnCount: number;
  hasVuln: boolean;
  hasHot: boolean;
}

interface FileEdge {
  id: string;
  source: string;
  target: string;
  callCount: number;
}

const MIN_SCALE = 0.04;
const MAX_SCALE = 4;
const DRAG_THRESHOLD = 4;
const PAD = 60;
const LOD_HIDE_LABELS = 0.35;
const LOD_THIN_EDGES  = 0.20;
const FILE_NODE_W = 160;
const FILE_NODE_H = 58;
const FILE_H_GAP = 220;  // horizontal center-to-center
const FILE_V_GAP = 170;  // vertical layer-to-layer

function bezier(sx: number, sy: number, tx: number, ty: number): string {
  const midY = (sy + ty) / 2;
  return `M${sx},${sy} C${sx},${midY} ${tx},${midY} ${tx},${ty}`;
}

function nodeBottom(n: { x: number; y: number; width: number; height: number }) {
  return { x: n.x + n.width / 2, y: n.y + n.height };
}
function nodeTop(n: { x: number; y: number; width: number }) {
  return { x: n.x + n.width / 2, y: n.y };
}

/** Proper hierarchical layout for file-level graph */
function buildFileGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  apiFileEdges?: FileGraphEdge[],
): { fileNodes: FileNode[]; fileEdges: FileEdge[] } {
  // 1. Group function nodes by file
  const fileMap = new Map<string, GraphNode[]>();
  for (const n of nodes) {
    if (!n.file) continue;
    const arr = fileMap.get(n.file) ?? [];
    arr.push(n);
    fileMap.set(n.file, arr);
  }
  if (fileMap.size === 0) return { fileNodes: [], fileEdges: [] };

  const fileIds = [...fileMap.keys()].sort();

  // 2. Aggregate cross-file edges
  // Prefer import-based edges from the API (captures dynamic dispatch, indirect calls);
  // fall back to deriving edges from detected function calls only.
  let fileEdges: FileEdge[];
  if (apiFileEdges && apiFileEdges.length > 0) {
    fileEdges = apiFileEdges.map((e) => ({
      id: `${e.source}\x00${e.target}`,
      source: e.source,
      target: e.target,
      callCount: e.callCount,
    }));
  } else {
    const nodeFile = new Map<string, string>();
    for (const n of nodes) if (n.file) nodeFile.set(n.id, n.file);
    const edgeCountMap = new Map<string, number>();
    for (const e of edges) {
      const sf = nodeFile.get(e.source);
      const tf = nodeFile.get(e.target);
      if (!sf || !tf || sf === tf) continue;
      const key = `${sf}\x00${tf}`;
      edgeCountMap.set(key, (edgeCountMap.get(key) ?? 0) + 1);
    }
    fileEdges = [];
    for (const [key, count] of edgeCountMap.entries()) {
      const sep = key.indexOf("\x00");
      fileEdges.push({ id: key, source: key.slice(0, sep), target: key.slice(sep + 1), callCount: count });
    }
  }

  // 3. Assign layers via DFS longest-path from roots
  const inAdj = new Map<string, string[]>(fileIds.map((id) => [id, []]));
  for (const e of fileEdges) {
    inAdj.get(e.target)?.push(e.source);
  }

  const layerMap = new Map<string, number>();
  const visiting = new Set<string>();

  function dfsLayer(id: string): number {
    if (layerMap.has(id)) return layerMap.get(id)!;
    if (visiting.has(id)) return 0; // break cycle
    visiting.add(id);
    const preds = inAdj.get(id) ?? [];
    const l = preds.length === 0 ? 0 : Math.max(...preds.map(dfsLayer)) + 1;
    layerMap.set(id, l);
    visiting.delete(id);
    return l;
  }
  for (const id of fileIds) dfsLayer(id);

  // 4. Group by layer, sort alphabetically within layer
  const byLayer = new Map<number, string[]>();
  for (const [id, l] of layerMap.entries()) {
    const arr = byLayer.get(l) ?? [];
    arr.push(id);
    byLayer.set(l, arr);
  }
  for (const arr of byLayer.values()) arr.sort();

  // 5. Position: center each layer horizontally
  const posMap = new Map<string, { x: number; y: number }>();
  for (const [l, ids] of byLayer.entries()) {
    const totalW = (ids.length - 1) * FILE_H_GAP;
    const startX = -totalW / 2 - FILE_NODE_W / 2;
    ids.forEach((id, i) => {
      posMap.set(id, { x: startX + i * FILE_H_GAP, y: l * FILE_V_GAP });
    });
  }

  // 6. Build FileNode objects
  const fileNodes: FileNode[] = fileIds.map((file) => {
    const fns = fileMap.get(file)!;
    const pos = posMap.get(file) ?? { x: 0, y: 0 };
    return {
      id: file,
      label: file.split("/").pop() ?? file,
      x: pos.x,
      y: pos.y,
      width: FILE_NODE_W,
      height: FILE_NODE_H,
      fnCount: fns.length,
      hasVuln: fns.some((n) => !!n.vulnerability),
      hasHot: fns.some((n) => !!n.isHot),
    };
  });

  return { fileNodes, fileEdges };
}

export default function GraphCanvas({
  nodes, edges, fileEdges: apiFileEdges, selectedNodeId, selectedFileId,
  onSelectNode, onSelectFile, viewMode, loading, hasSelection, onClearSelection,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const activeNodesRef = useRef<typeof activeNodes>([]);
  const [transform, setTransform] = useState<Transform>({ x: 0, y: 0, scale: 1 });
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);
  const drag = useRef<{
    active: boolean; startX: number; startY: number;
    startTx: number; startTy: number; moved: boolean;
  } | null>(null);
  const velocity = useRef({ vx: 0, vy: 0 });
  const lastPos = useRef({ x: 0, y: 0, t: 0 });
  const inertiaFrame = useRef<number | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const fileColorMap = useMemo(
    () => assignFileColors(nodes.map((n) => n.file ?? "").filter(Boolean)),
    [nodes],
  );

  function colorFor(file: string | undefined) {
    if (!file) return { border: "#444444", text: "#686868", selected: "#909090" };
    return fileColor(fileColorMap.get(file) ?? 0);
  }

  const { fileNodes, fileEdges } = useMemo(
    () => buildFileGraph(nodes, edges, apiFileEdges),
    [nodes, edges, apiFileEdges],
  );

  const fileNodeMap = useMemo(
    () => new Map(fileNodes.map((n) => [n.id, n])),
    [fileNodes],
  );

  const activeNodes = viewMode === "files" ? fileNodes : nodes;
  const activeEdges = viewMode === "files" ? fileEdges : edges;
  activeNodesRef.current = activeNodes;

  // Validate hoveredEdgeId against the *actually rendered* edge set.
  // activeEdges contains ALL edges, but in functions view some are hidden by
  // the file filter (return null, no hit area in DOM). Checking only activeEdges
  // would still treat those hidden edges as valid, keeping the dim locked.
  // So we also apply the same hiddenByFile logic used in the render.
  const hoveredEdge = (() => {
    if (!hoveredEdgeId) return null;
    const e = activeEdges.find((e) => e.id === hoveredEdgeId);
    if (!e) return null;
    if (viewMode === "functions" && selectedFileId !== null) {
      const src = nodeMap.get(e.source);
      const tgt = nodeMap.get(e.target);
      if (!(src?.file === selectedFileId && tgt?.file === selectedFileId)) return null;
    }
    return e;
  })();
  const effectiveHoveredEdgeId = hoveredEdge ? hoveredEdgeId : null;
  const connectedIds = hoveredEdge
    ? new Set([hoveredEdge.source, hoveredEdge.target])
    : null;

  // Extract fit logic so it can be triggered from multiple sources
  const fitView = useCallback((ns: typeof activeNodes) => {
    if (!ns.length || !svgRef.current) return;
    const el = svgRef.current.parentElement;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    if (!width || !height) return;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const n of ns) {
      minX = Math.min(minX, n.x);
      minY = Math.min(minY, n.y);
      maxX = Math.max(maxX, n.x + n.width);
      maxY = Math.max(maxY, n.y + n.height);
    }
    const graphW = maxX - minX + PAD * 2;
    const graphH = maxY - minY + PAD * 2;
    const scale = Math.min(width / graphW, height / graphH, 1);
    setTransform({
      x: (width  - graphW * scale) / 2 - minX * scale + PAD * scale,
      y: (height - graphH * scale) / 2 - minY * scale + PAD * scale,
      scale,
    });
  }, []);

  // Re-fit when nodes or viewMode change
  useEffect(() => {
    fitView(activeNodes);
    setHoveredEdgeId(null);
    setTooltip(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, nodes]);

  // Cancel inertia on unmount
  useEffect(() => () => {
    if (inertiaFrame.current !== null) cancelAnimationFrame(inertiaFrame.current);
  }, []);

  // Re-fit when the canvas container is resized (either sidebar toggled or dragged)
  useEffect(() => {
    const el = svgRef.current?.parentElement;
    if (!el) return;
    let lastW = 0, lastH = 0;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (Math.abs(width - lastW) > 1 || Math.abs(height - lastH) > 1) {
        lastW = width; lastH = height;
        fitView(activeNodesRef.current);
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fitView]);

  const onWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    if (inertiaFrame.current !== null) {
      cancelAnimationFrame(inertiaFrame.current);
      inertiaFrame.current = null;
    }
    setHoveredEdgeId(null);
    setTooltip(null);
    const rect = svgRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    setTransform((prev) => {
      const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev.scale * factor));
      return {
        x: mx - ((mx - prev.x) / prev.scale) * s,
        y: my - ((my - prev.y) / prev.scale) * s,
        scale: s,
      };
    });
  }, []);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [onWheel, nodes]); // re-run when nodes load so the SVG ref is populated

  // Store transform in a ref so drag closures always see the latest value
  // without needing transform in the useCallback deps (which caused re-creation
  // every frame during drag, leading to stale closures and the "black screen").
  const transformRef = useRef(transform);
  transformRef.current = transform;

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    if (inertiaFrame.current !== null) {
      cancelAnimationFrame(inertiaFrame.current);
      inertiaFrame.current = null;
    }
    velocity.current = { vx: 0, vy: 0 };
    lastPos.current = { x: e.clientX, y: e.clientY, t: performance.now() };
    const startX = e.clientX;
    const startY = e.clientY;
    const startTx = transformRef.current.x;
    const startTy = transformRef.current.y;
    drag.current = { active: true, startX, startY, startTx, startTy, moved: false };

    function onMove(ev: MouseEvent) {
      if (!drag.current?.active) return;
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;
      if (!drag.current.moved && Math.hypot(dx, dy) > DRAG_THRESHOLD)
        drag.current.moved = true;
      if (drag.current.moved) {
        setHoveredEdgeId(null);
        setTooltip(null);
        const now = performance.now();
        const dt = now - lastPos.current.t;
        if (dt > 0 && dt < 80) {
          velocity.current = {
            vx: (ev.clientX - lastPos.current.x) / dt * 16,
            vy: (ev.clientY - lastPos.current.y) / dt * 16,
          };
        }
        lastPos.current = { x: ev.clientX, y: ev.clientY, t: now };
        setTransform((prev) => ({ ...prev, x: startTx + dx, y: startTy + dy }));
      }
    }

    function onUp() {
      drag.current = null;
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      const FRICTION = 0.88;
      const MIN_VEL = 0.3;
      function animate() {
        velocity.current.vx *= FRICTION;
        velocity.current.vy *= FRICTION;
        if (Math.abs(velocity.current.vx) < MIN_VEL && Math.abs(velocity.current.vy) < MIN_VEL) {
          inertiaFrame.current = null;
          return;
        }
        const { vx, vy } = velocity.current;
        setTransform((prev) => ({ ...prev, x: prev.x + vx, y: prev.y + vy }));
        inertiaFrame.current = requestAnimationFrame(animate);
      }
      if (Math.hypot(velocity.current.vx, velocity.current.vy) > MIN_VEL) {
        inertiaFrame.current = requestAnimationFrame(animate);
      }
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []); // stable — no deps needed, reads transform from ref


  const scale = transform.scale;
  const showLabels = scale >= LOD_HIDE_LABELS;
  const fnEdgeOpacity = scale < LOD_THIN_EDGES ? 0.25 : 0.5;

  if (!nodes.length) {
    return (
      <div className={styles.canvas}>
        <div className={styles.empty}>
          {loading ? (
            <>
              <div className={styles.loadingSpinner} />
              <div className={styles.emptyTitle}>analyzing…</div>
            </>
          ) : (
            <>
              <div className={styles.emptyTitle}>no repo loaded</div>
              <div className={styles.emptyHint}>enter a path above and click analyze</div>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={styles.canvas}>
      <svg
        ref={svgRef}
        className={styles.graph}
        xmlns="http://www.w3.org/2000/svg"
        onMouseDown={onMouseDown}
        onMouseLeave={() => { setHoveredEdgeId(null); setTooltip(null); }}
      >
        <defs>
          <pattern id="dot-grid"
            x={transform.x % 28} y={transform.y % 28}
            width="28" height="28" patternUnits="userSpaceOnUse">
            <circle cx="0" cy="0" r="0.65" fill="#1a1a1a" />
          </pattern>
          <marker id="arrow-fn" markerWidth="7" markerHeight="7" refX="6" refY="3.5"
            orient="auto" markerUnits="strokeWidth">
            <path d="M0,0.5 L0,6.5 L6,3.5 z" fill="context-stroke" />
          </marker>
          <marker id="arrow-file" markerWidth="8" markerHeight="8" refX="7" refY="4"
            orient="auto" markerUnits="strokeWidth">
            <path d="M0,0.5 L0,7.5 L7,4 z" fill="context-stroke" />
          </marker>
        </defs>
        <rect width="100%" height="100%" fill="url(#dot-grid)" />

        <g transform={`translate(${transform.x},${transform.y}) scale(${scale})`}>

          {/* ════ FUNCTIONS VIEW ════ */}
          {viewMode === "functions" && (
            <>
              {edges.map((edge) => {
                const src = nodeMap.get(edge.source);
                const tgt = nodeMap.get(edge.target);
                if (!src || !tgt) return null;
                // Hide unless both endpoints belong to the selected file
                const hiddenByFile = selectedFileId !== null
                  && !(src.file === selectedFileId && tgt.file === selectedFileId);
                if (hiddenByFile) return null;
                const isHovered = edge.id === effectiveHoveredEdgeId;
                const isCrossFile = src.file && tgt.file && src.file !== tgt.file;
                const stroke = colorFor(src.file).border;
                const baseOp = isCrossFile ? fnEdgeOpacity + 0.3 : fnEdgeOpacity;
                const b = nodeBottom(src);
                const t = nodeTop(tgt);
                return (
                  <path key={edge.id}
                    d={bezier(b.x, b.y, t.x, t.y)}
                    stroke={stroke}
                    strokeWidth={(isCrossFile ? 1.8 : 1.2) * (isHovered ? 2.2 : 1)}
                    fill="none"
                    opacity={isHovered ? 1 : effectiveHoveredEdgeId ? baseOp * 0.4 : baseOp}
                    markerEnd="url(#arrow-fn)"
                    style={{ transition: "opacity 0.1s, stroke-width 0.1s" }}
                  />
                );
              })}

              {edges.map((edge) => {
                const src = nodeMap.get(edge.source);
                const tgt = nodeMap.get(edge.target);
                if (!src || !tgt) return null;
                // Don't register hit areas for edges hidden by file selection
                const hiddenByFile = selectedFileId !== null
                  && !(src.file === selectedFileId && tgt.file === selectedFileId);
                if (hiddenByFile) return null;
                const b = nodeBottom(src);
                const t = nodeTop(tgt);
                return (
                  <path key={`hit-${edge.id}`}
                    d={bezier(b.x, b.y, t.x, t.y)}
                    stroke="transparent" strokeWidth={12} fill="none"
                    style={{ cursor: "crosshair" }}
                    onMouseEnter={(e) => {
                      if (drag.current?.moved) return;
                      setHoveredEdgeId(edge.id);
                      const rect = svgRef.current!.getBoundingClientRect();
                      setTooltip({
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top,
                        label: `${src.label} → ${tgt.label}`,
                        sub: [src.file?.split("/").pop(), tgt.file?.split("/").pop()]
                          .filter(Boolean).join(" → "),
                      });
                    }}
                    onMouseMove={(e) => {
                      const rect = svgRef.current!.getBoundingClientRect();
                      setTooltip((p) => p ? { ...p, x: e.clientX - rect.left, y: e.clientY - rect.top } : null);
                    }}
                    onMouseLeave={() => { setHoveredEdgeId(null); setTooltip(null); }}
                  />
                );
              })}

              {nodes.map((node) => {
                const isSelected = node.id === selectedNodeId;
                const isVuln = !!node.vulnerability;
                const isHot = !!node.isHot;
                const isComplex = !!node.isComplex;
                const color = colorFor(node.file);
                const isConnected = connectedIds?.has(node.id) ?? false;
                const isDimmedByFile = selectedFileId !== null && node.file !== selectedFileId;
                const isDimmedByEdge = effectiveHoveredEdgeId !== null && !isConnected;
                const isNodeHovered = node.id === hoveredNodeId && !drag.current?.moved;
                const fill = isSelected ? "#202020"
                  : isNodeHovered ? "#1c1c1c"
                  : isConnected ? "#1a1a1a"
                  : (isHot || isComplex) ? "#161616"
                  : "#111111";
                const stroke = isSelected ? color.selected
                  : isNodeHovered ? color.text
                  : isConnected ? color.text
                  : color.border;
                const labelColor = "#888888";
                const cx = node.x + node.width / 2;
                const cy = node.y + node.height / 2;
                return (
                  <g key={node.id} className={styles.nodeGroup}
                    opacity={isDimmedByFile ? 0.28 : isDimmedByEdge ? 0.28 : 1}
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                    onClick={(e) => { if (drag.current?.moved) return; e.stopPropagation(); onSelectNode(node.id); }}>
                    {isVuln && (
                      <rect x={node.x - 2} y={node.y - 2}
                        width={node.width + 4} height={node.height + 4}
                        rx={3} fill="none" stroke="#e03535" strokeWidth={1.5}
                        className={styles.vulnRing} />
                    )}
                    <rect x={node.x} y={node.y} width={node.width} height={node.height}
                      rx={2} fill={fill} stroke={stroke}
                      strokeWidth={isSelected ? 1.5 : isNodeHovered ? 1.5 : isConnected ? 1.5 : 1} />
                    {showLabels && (
                      <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle"
                        fill={labelColor} fontFamily="'IBM Plex Mono', monospace"
                        fontSize={11} fontWeight={isSelected || isConnected || isHot ? 500 : 400}>
                        {node.label}
                      </text>
                    )}
                  </g>
                );
              })}
            </>
          )}

          {/* ════ FILES VIEW ════ */}
          {viewMode === "files" && (
            <>
              {/* Edges (visible) */}
              {fileEdges.map((edge) => {
                const src = fileNodeMap.get(edge.source);
                const tgt = fileNodeMap.get(edge.target);
                if (!src || !tgt) return null;
                const isHovered = edge.id === effectiveHoveredEdgeId;
                const stroke = colorFor(src.id).border;
                const w = Math.min(1.5 + edge.callCount * 0.5, 6);
                const b = nodeBottom(src);
                const t = nodeTop(tgt);
                return (
                  <path key={edge.id}
                    d={bezier(b.x, b.y, t.x, t.y)}
                    stroke={stroke}
                    strokeWidth={w * (isHovered ? 1.8 : 1)}
                    fill="none"
                    opacity={isHovered ? 1 : effectiveHoveredEdgeId ? 0.15 : 0.7}
                    markerEnd="url(#arrow-file)"
                    style={{ transition: "opacity 0.12s, stroke-width 0.1s" }}
                  />
                );
              })}

              {/* Edge hit areas */}
              {fileEdges.map((edge) => {
                const src = fileNodeMap.get(edge.source);
                const tgt = fileNodeMap.get(edge.target);
                if (!src || !tgt) return null;
                const b = nodeBottom(src);
                const t = nodeTop(tgt);
                return (
                  <path key={`hit-${edge.id}`}
                    d={bezier(b.x, b.y, t.x, t.y)}
                    stroke="transparent" strokeWidth={18} fill="none"
                    style={{ cursor: "crosshair" }}
                    onMouseEnter={(e) => {
                      if (drag.current?.moved) return;
                      setHoveredEdgeId(edge.id);
                      const rect = svgRef.current!.getBoundingClientRect();
                      setTooltip({
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top,
                        label: `${src.label} → ${tgt.label}`,
                        sub: `${edge.callCount} call${edge.callCount !== 1 ? "s" : ""}`,
                      });
                    }}
                    onMouseMove={(e) => {
                      const rect = svgRef.current!.getBoundingClientRect();
                      setTooltip((p) => p ? { ...p, x: e.clientX - rect.left, y: e.clientY - rect.top } : null);
                    }}
                    onMouseLeave={() => { setHoveredEdgeId(null); setTooltip(null); }}
                  />
                );
              })}

              {/* File nodes */}
              {fileNodes.map((node) => {
                const color = colorFor(node.id);
                const isConnected = connectedIds?.has(node.id) ?? false;
                const isActive = node.id === selectedFileId;
                const dimmed = effectiveHoveredEdgeId !== null && !isConnected;
                const stroke = node.hasVuln ? "#e03535"
                  : isActive ? color.selected
                  : isConnected ? color.text
                  : color.border;
                const fill = isActive || isConnected ? "#1c1c1c" : "#111111";
                const cx = node.x + node.width / 2;
                const nameY = node.y + node.height / 2 - 9;
                const metaY = node.y + node.height / 2 + 10;
                const tags = [
                  node.fnCount + " fn",
                  node.hasHot ? "hot" : null,
                  node.hasVuln ? "vuln" : null,
                ].filter(Boolean).join("  ·  ");

                return (
                  <g key={node.id} className={styles.fileNodeGroup}
                    opacity={dimmed ? 0.28 : 1}
                    style={{ transition: "opacity 0.12s" }}
                    onClick={() => { if (!drag.current?.moved) onSelectFile(node.id); }}>
                    {/* Subtle colored left accent bar */}
                    <rect x={node.x} y={node.y}
                      width={3} height={node.height} rx={1}
                      fill={color.border} opacity={0.9} />
                    {/* Main box */}
                    <rect x={node.x} y={node.y}
                      width={node.width} height={node.height}
                      rx={3} fill={fill} stroke={stroke}
                      strokeWidth={isActive ? 1.5 : isConnected ? 1.5 : 1} />
                    {showLabels && (
                      <>
                        <text x={cx} y={nameY}
                          textAnchor="middle" dominantBaseline="middle"
                          fill={isActive ? color.selected : color.text}
                          fontFamily="'IBM Plex Mono', monospace"
                          fontSize={12} fontWeight={600}>
                          {node.label}
                        </text>
                        <text x={cx} y={metaY}
                          textAnchor="middle" dominantBaseline="middle"
                          fill={color.border}
                          fontFamily="'IBM Plex Mono', monospace"
                          fontSize={9}>
                          {tags}
                        </text>
                      </>
                    )}
                  </g>
                );
              })}
            </>
          )}

        </g>
      </svg>

      {tooltip && (
        <div className={styles.tooltip}
          style={{ left: tooltip.x + 14, top: tooltip.y - 14 }}>
          <div className={styles.tooltipLabel}>{tooltip.label}</div>
          {tooltip.sub && <div className={styles.tooltipSub}>{tooltip.sub}</div>}
        </div>
      )}

      {hasSelection && onClearSelection && (
        <button className={styles.showAllBtn} onClick={onClearSelection}>
          esc · show all
        </button>
      )}
    </div>
  );
}
