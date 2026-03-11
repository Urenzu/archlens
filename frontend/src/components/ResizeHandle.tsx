import type { RefObject } from "react";
import styles from "./ResizeHandle.module.css";

interface Props {
  side: "left" | "right";
  panelRef: RefObject<HTMLElement | null>;
  min?: number;
  max?: number;
}

export default function ResizeHandle({ side, panelRef, min = 120, max = 600 }: Props) {
  function onMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    const panel = panelRef.current;
    if (!panel) return;

    const startX = e.clientX;
    const startW = panel.offsetWidth;
    const el = panel;

    function onMove(ev: MouseEvent) {
      const delta = ev.clientX - startX;
      const newW = Math.min(max, Math.max(min, startW + (side === "left" ? delta : -delta)));
      el.style.width = `${newW}px`;
    }

    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  return <div className={styles.handle} onMouseDown={onMouseDown} />;
}
