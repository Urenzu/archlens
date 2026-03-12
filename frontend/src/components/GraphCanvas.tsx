import { useRef, useState, useCallback, useEffect, useMemo } from "react";
import type { GraphNode, GraphEdge, FileGraphEdge } from "../types/graph";
import { fileColor, assignFileColors } from "../lib/fileColors";
import { drawFrame, hitTestEdge, type VisibleEdge } from "../lib/canvasRenderer";
import NodeOverlay from "./NodeOverlay";
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
const FILE_H_GAP = 220;
const FILE_V_GAP = 170;
const NO_FILE_COLOR = { border: "#444444", text: "#686868", selected: "#909090" } as const;
const EDGE_HIT_THRESHOLD = 12; // CSS pixels — zoom-independent

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
  const fileMap = new Map<string, GraphNode[]>();
  for (const n of nodes) {
    if (!n.file) continue;
    const arr = fileMap.get(n.file) ?? [];
    arr.push(n);
    fileMap.set(n.file, arr);
  }
  if (fileMap.size === 0) return { fileNodes: [], fileEdges: [] };

  const fileIds = [...fileMap.keys()].sort();

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

  const inAdj = new Map<string, string[]>(fileIds.map((id) => [id, []]));
  for (const e of fileEdges) {
    inAdj.get(e.target)?.push(e.source);
  }

  const layerMap = new Map<string, number>();
  const visiting = new Set<string>();

  function dfsLayer(id: string): number {
    if (layerMap.has(id)) return layerMap.get(id)!;
    if (visiting.has(id)) return 0;
    visiting.add(id);
    const preds = inAdj.get(id) ?? [];
    const l = preds.length === 0 ? 0 : Math.max(...preds.map(dfsLayer)) + 1;
    layerMap.set(id, l);
    visiting.delete(id);
    return l;
  }
  for (const id of fileIds) dfsLayer(id);

  const byLayer = new Map<number, string[]>();
  for (const [id, l] of layerMap.entries()) {
    const arr = byLayer.get(l) ?? [];
    arr.push(id);
    byLayer.set(l, arr);
  }
  for (const arr of byLayer.values()) arr.sort();

  const posMap = new Map<string, { x: number; y: number }>();
  for (const [l, ids] of byLayer.entries()) {
    const totalW = (ids.length - 1) * FILE_H_GAP;
    const startX = -totalW / 2 - FILE_NODE_W / 2;
    ids.forEach((id, i) => {
      posMap.set(id, { x: startX + i * FILE_H_GAP, y: l * FILE_V_GAP });
    });
  }

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
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeNodesRef = useRef<(GraphNode | FileNode)[]>([]);
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
  const frameRef = useRef<number>(0);

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const fileColorMap = useMemo(
    () => assignFileColors(nodes.map((n) => n.file ?? "").filter(Boolean)),
    [nodes],
  );

  const colorCache = useMemo(() => {
    const cache = new Map<string, ReturnType<typeof fileColor>>();
    for (const [file, idx] of fileColorMap.entries()) cache.set(file, fileColor(idx));
    return cache;
  }, [fileColorMap]);

  function colorFor(file: string | undefined) {
    if (!file) return NO_FILE_COLOR;
    return colorCache.get(file) ?? NO_FILE_COLOR;
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

  const hoveredEdge = useMemo(() => {
    if (!hoveredEdgeId) return null;
    const e = activeEdges.find((e) => e.id === hoveredEdgeId);
    if (!e) return null;
    if (viewMode === "functions" && selectedFileId !== null) {
      const src = nodeMap.get(e.source);
      const tgt = nodeMap.get(e.target);
      if (!(src?.file === selectedFileId && tgt?.file === selectedFileId)) return null;
    }
    return e;
  }, [hoveredEdgeId, activeEdges, viewMode, selectedFileId, nodeMap]);

  const effectiveHoveredEdgeId = hoveredEdge ? hoveredEdgeId : null;
  const connectedIds = useMemo(
    () => hoveredEdge ? new Set([hoveredEdge.source, hoveredEdge.target]) : null,
    [hoveredEdge],
  );

  const scale = transform.scale;
  const showLabels = scale >= LOD_HIDE_LABELS;
  const fnEdgeOpacity = scale < LOD_THIN_EDGES ? 0.25 : 0.5;

  // ── Build visible edges for the canvas renderer ────────────────────────────
  const visibleEdges: VisibleEdge[] = useMemo(() => {
    if (viewMode === "functions") {
      const result: VisibleEdge[] = [];
      for (const edge of edges) {
        const src = nodeMap.get(edge.source);
        const tgt = nodeMap.get(edge.target);
        if (!src || !tgt) continue;
        const hiddenByFile = selectedFileId !== null
          && !(src.file === selectedFileId && tgt.file === selectedFileId);
        if (hiddenByFile) continue;
        const isHovered = edge.id === effectiveHoveredEdgeId;
        const isCrossFile = src.file && tgt.file && src.file !== tgt.file;
        const stroke = colorFor(src.file).border;
        const baseOp = isCrossFile ? fnEdgeOpacity + 0.3 : fnEdgeOpacity;
        const b = nodeBottom(src);
        const t = nodeTop(tgt);
        result.push({
          id: edge.id,
          sx: b.x, sy: b.y,
          tx: t.x, ty: t.y,
          color: stroke,
          width: (isCrossFile ? 1.8 : 1.2) * (isHovered ? 2.2 : 1),
          opacity: isHovered ? 1 : effectiveHoveredEdgeId ? baseOp * 0.4 : baseOp,
          isHovered,
        });
      }
      return result;
    } else {
      const result: VisibleEdge[] = [];
      for (const edge of fileEdges) {
        const src = fileNodeMap.get(edge.source);
        const tgt = fileNodeMap.get(edge.target);
        if (!src || !tgt) continue;
        const isHovered = edge.id === effectiveHoveredEdgeId;
        const stroke = colorFor(src.id).border;
        const w = Math.min(1.5 + edge.callCount * 0.5, 6);
        const b = nodeBottom(src);
        const t = nodeTop(tgt);
        result.push({
          id: edge.id,
          sx: b.x, sy: b.y,
          tx: t.x, ty: t.y,
          color: stroke,
          width: w * (isHovered ? 1.8 : 1),
          opacity: isHovered ? 1 : effectiveHoveredEdgeId ? 0.15 : 0.7,
          isHovered,
        });
      }
      return result;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edges, fileEdges, nodeMap, fileNodeMap, viewMode, selectedFileId, effectiveHoveredEdgeId, fnEdgeOpacity]);

  // ── Canvas draw loop (also handles buffer sizing) ──────────────────────────
  useEffect(() => {
    cancelAnimationFrame(frameRef.current);
    frameRef.current = requestAnimationFrame(() => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;

      // Lazy-size the buffer to match the CSS display size every frame.
      // This self-corrects any sizing issues regardless of mount timing.
      const rect = canvas.getBoundingClientRect();
      const bufW = Math.round(rect.width * dpr);
      const bufH = Math.round(rect.height * dpr);
      if (bufW === 0 || bufH === 0) return; // container not laid out yet
      if (canvas.width !== bufW || canvas.height !== bufH) {
        canvas.width = bufW;
        canvas.height = bufH;
      }

      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      drawFrame({
        ctx,
        width: canvas.width,
        height: canvas.height,
        dpr,
        tx: transform.x,
        ty: transform.y,
        scale: transform.scale,
        edges: visibleEdges,
      });
    });
  }, [transform, visibleEdges]);

  // ── Fit view ───────────────────────────────────────────────────────────────
  const fitView = useCallback((ns: (GraphNode | FileNode)[]) => {
    if (!ns.length || !containerRef.current) return;
    const { width, height } = containerRef.current.getBoundingClientRect();
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
    const s = Math.min(width / graphW, height / graphH, 1);
    setTransform({
      x: (width  - graphW * s) / 2 - minX * s + PAD * s,
      y: (height - graphH * s) / 2 - minY * s + PAD * s,
      scale: s,
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

  // Re-fit when the container is resized (sidebar toggle / drag)
  useEffect(() => {
    const el = containerRef.current;
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

  // ── Wheel zoom ─────────────────────────────────────────────────────────────
  const onWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    if (inertiaFrame.current !== null) {
      cancelAnimationFrame(inertiaFrame.current);
      inertiaFrame.current = null;
    }
    setHoveredEdgeId(null);
    setTooltip(null);
    const rect = containerRef.current!.getBoundingClientRect();
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
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [onWheel, nodes]);

  // ── Pan / drag ─────────────────────────────────────────────────────────────
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
  }, []);

  // ── Edge hit testing on mouse move ─────────────────────────────────────────
  const onCanvasMouseMove = useCallback((e: React.MouseEvent) => {
    if (drag.current?.moved) return;
    const rect = containerRef.current!.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const worldX = (mx - transformRef.current.x) / transformRef.current.scale;
    const worldY = (my - transformRef.current.y) / transformRef.current.scale;

    const hitId = hitTestEdge(visibleEdges, worldX, worldY, EDGE_HIT_THRESHOLD, transformRef.current.scale);

    if (hitId) {
      setHoveredEdgeId(hitId);
      const edge = visibleEdges.find((e) => e.id === hitId);
      if (edge) {
        if (viewMode === "functions") {
          const src = nodes.find((n) => {
            const b = nodeBottom(n);
            return Math.abs(b.x - edge.sx) < 1 && Math.abs(b.y - edge.sy) < 1;
          });
          const tgt = nodes.find((n) => {
            const t = nodeTop(n);
            return Math.abs(t.x - edge.tx) < 1 && Math.abs(t.y - edge.ty) < 1;
          });
          if (src && tgt) {
            setTooltip({
              x: mx, y: my,
              label: `${src.label} → ${tgt.label}`,
              sub: [src.file?.split("/").pop(), tgt.file?.split("/").pop()]
                .filter(Boolean).join(" → "),
            });
          }
        } else {
          const srcFile = fileNodes.find((n) => {
            const b = nodeBottom(n);
            return Math.abs(b.x - edge.sx) < 1 && Math.abs(b.y - edge.sy) < 1;
          });
          const tgtFile = fileNodes.find((n) => {
            const t = nodeTop(n);
            return Math.abs(t.x - edge.tx) < 1 && Math.abs(t.y - edge.ty) < 1;
          });
          const fileEdge = fileEdges.find((e) => e.id === hitId);
          if (srcFile && tgtFile) {
            setTooltip({
              x: mx, y: my,
              label: `${srcFile.label} → ${tgtFile.label}`,
              sub: fileEdge ? `${fileEdge.callCount} call${fileEdge.callCount !== 1 ? "s" : ""}` : "",
            });
          }
        }
      }
    } else {
      if (hoveredEdgeId) {
        setHoveredEdgeId(null);
        setTooltip(null);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visibleEdges, viewMode, fileNodes, fileEdges, nodes, hoveredEdgeId]);

  const handleMouseLeave = useCallback(() => {
    setHoveredEdgeId(null);
    setTooltip(null);
  }, []);

  const isEmpty = !nodes.length;

  return (
    <div
      ref={containerRef}
      className={styles.canvas}
      onMouseDown={isEmpty ? undefined : onMouseDown}
      onMouseMove={isEmpty ? undefined : onCanvasMouseMove}
      onMouseLeave={isEmpty ? undefined : handleMouseLeave}
    >
      {/* Canvas layer — always mounted so refs are stable */}
      <canvas ref={canvasRef} className={styles.canvasLayer} />

      {isEmpty ? (
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
      ) : (
        <>
          <NodeOverlay
            viewMode={viewMode}
            nodes={nodes}
            fileNodes={fileNodes}
            selectedNodeId={selectedNodeId}
            selectedFileId={selectedFileId}
            hoveredNodeId={hoveredNodeId}
            effectiveHoveredEdgeId={effectiveHoveredEdgeId}
            connectedIds={connectedIds}
            colorFor={colorFor}
            showLabels={showLabels}
            onSelectNode={onSelectNode}
            onSelectFile={onSelectFile}
            onHoverNode={setHoveredNodeId}
            isDragging={!!drag.current?.moved}
            tx={transform.x}
            ty={transform.y}
            scale={transform.scale}
          />

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
        </>
      )}
    </div>
  );
}
