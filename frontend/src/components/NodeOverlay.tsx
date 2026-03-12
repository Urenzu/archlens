import type { GraphNode } from "../types/graph";
import type { FileColor } from "../lib/fileColors";
import styles from "./NodeOverlay.module.css";

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

interface Props {
  viewMode: "functions" | "files";
  // function view
  nodes: GraphNode[];
  selectedNodeId: string | null;
  selectedFileId: string | null;
  hoveredNodeId: string | null;
  effectiveHoveredEdgeId: string | null;
  connectedIds: Set<string> | null;
  colorFor: (file: string | undefined) => FileColor;
  showLabels: boolean;
  onSelectNode: (id: string) => void;
  onSelectFile: (file: string) => void;
  onHoverNode: (id: string | null) => void;
  isDragging: boolean;
  // file view
  fileNodes: FileNode[];
  // shared transform
  tx: number;
  ty: number;
  scale: number;
}

export default function NodeOverlay({
  viewMode, nodes, selectedNodeId, selectedFileId,
  hoveredNodeId, effectiveHoveredEdgeId, connectedIds, colorFor,
  showLabels, onSelectNode, onSelectFile, onHoverNode, isDragging,
  fileNodes, tx, ty, scale,
}: Props) {
  return (
    <div
      className={styles.nodeLayer}
      style={{ pointerEvents: isDragging ? "none" : undefined }}
    >
      <div
        className={styles.worldContainer}
        style={{ transform: `translate(${tx}px,${ty}px) scale(${scale})` }}
      >
        {viewMode === "functions" && nodes.map((node) => {
          const isSelected = node.id === selectedNodeId;
          const isVuln = !!node.vulnerability;
          const isHot = !!node.isHot;
          const isComplex = !!node.isComplex;
          const isConnected = connectedIds?.has(node.id) ?? false;
          const isDimmedByFile = selectedFileId !== null && node.file !== selectedFileId;
          const isDimmedByEdge = effectiveHoveredEdgeId !== null && !isConnected;
          const isNodeHovered = node.id === hoveredNodeId && !isDragging;
          const color = colorFor(node.file);
          const borderColor = isSelected ? color.selected
            : isNodeHovered ? color.text
            : isConnected ? color.text
            : color.border;

          return (
            <div
              key={node.id}
              className={styles.node}
              style={{
                left: node.x,
                top: node.y,
                width: node.width,
                height: node.height,
                "--node-border": borderColor,
              } as React.CSSProperties}
              data-selected={isSelected || undefined}
              data-hovered={isNodeHovered || undefined}
              data-connected={isConnected || undefined}
              data-hot={isHot || undefined}
              data-complex={isComplex || undefined}
              data-dimmed={isDimmedByFile || isDimmedByEdge || undefined}
              onMouseEnter={() => onHoverNode(node.id)}
              onMouseLeave={() => onHoverNode(null)}
              onClick={(e) => { e.stopPropagation(); onSelectNode(node.id); }}
            >
              {isVuln && <div className={styles.vulnRing} />}
              <div className={styles.highlight} />
              {showLabels && (
                <>
                  <span className={styles.label}>{node.label}</span>
                  {node.kind && <span className={styles.kind}>{node.kind}</span>}
                </>
              )}
            </div>
          );
        })}

        {viewMode === "files" && fileNodes.map((node) => {
          const color = colorFor(node.id);
          const isConnected = connectedIds?.has(node.id) ?? false;
          const isActive = node.id === selectedFileId;
          const dimmed = effectiveHoveredEdgeId !== null && !isConnected;
          const borderColor = node.hasVuln ? "#e03535"
            : isActive ? color.selected
            : isConnected ? color.text
            : color.border;
          const labelColor = isActive ? color.selected : color.text;
          const tags = [
            node.fnCount + " fn",
            node.hasHot ? "hot" : null,
            node.hasVuln ? "vuln" : null,
          ].filter(Boolean).join("  \u00b7  ");

          return (
            <div
              key={node.id}
              className={styles.fileNode}
              style={{
                left: node.x,
                top: node.y,
                width: node.width,
                height: node.height,
                "--node-border": borderColor,
              } as React.CSSProperties}
              data-active={isActive || undefined}
              data-connected={isConnected || undefined}
              data-dimmed={dimmed || undefined}
              onClick={() => onSelectFile(node.id)}
            >
              <div className={styles.highlight} />
              <div className={styles.accentBar} style={{ background: color.border }} />
              {showLabels && (
                <>
                  <span className={styles.fileLabel} style={{ color: labelColor }}>
                    {node.label}
                  </span>
                  <span className={styles.fileMeta} style={{ color: color.border }}>
                    {tags}
                  </span>
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
