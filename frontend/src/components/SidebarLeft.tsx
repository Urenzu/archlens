import { useState, useMemo, forwardRef } from "react";
import type { GraphNode } from "../types/graph";
import { fileColor, assignFileColors } from "../lib/fileColors";
import styles from "./SidebarLeft.module.css";

interface Props {
  nodes: GraphNode[];
  selectedNode: GraphNode | null;
  selectedFileId: string | null;
  onSelectNode: (id: string) => void;
  onSelectFile: (file: string) => void;
}

const SidebarLeft = forwardRef<HTMLDivElement, Props>(function SidebarLeft(
  { nodes, selectedNode, selectedFileId, onSelectNode, onSelectFile }, ref
) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const fileColorMap = useMemo(
    () => assignFileColors(nodes.map((n) => n.file ?? "").filter(Boolean)),
    [nodes],
  );

  const fileTree = useMemo(() => {
    const map = new Map<string, GraphNode[]>();
    for (const n of nodes) {
      if (!n.file) continue;
      const arr = map.get(n.file) ?? [];
      arr.push(n);
      map.set(n.file, arr);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [nodes]);

  function toggleCollapse(file: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });
  }

  function handleFileClick(file: string) {
    onSelectFile(file);
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.delete(file);
      return next;
    });
  }

  return (
    <div ref={ref} className={styles.sidebar} style={{ width: 220 }}>
      <div className={styles.section}>
        <div className={styles.label}>Files</div>
        {fileTree.map(([file, fileNodes]) => {
          const colorIdx = fileColorMap.get(file) ?? 0;
          const palette = fileColor(colorIdx);
          const isOpen = !collapsed.has(file);
          const isActive = file === selectedFileId;
          const basename = file.split("/").pop() ?? file;
          const dirname = file.includes("/")
            ? file.slice(0, file.lastIndexOf("/"))
            : null;

          return (
            <div key={file}>
              <div
                className={`${styles.fileRow} ${isActive ? styles.fileActive : ""}`}
                style={{ borderLeftColor: isActive ? palette.border : "transparent"  }}
                onClick={() => handleFileClick(file)}
              >
                <span
                  className={styles.chevron}
                  onClick={(e) => { e.stopPropagation(); toggleCollapse(file); }}
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
                    <span
                      className={styles.fnDot}
                      style={{ background: palette.border }}
                    />
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
    </div>
  );
});

export default SidebarLeft;
