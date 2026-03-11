import type { RepoStats } from "../types/graph";
import styles from "./Topbar.module.css";

interface Props {
  stats: RepoStats;
  repoPath: string;
  onRepoPathChange: (path: string) => void;
  onAnalyze: (path: string) => void;
  loading: boolean;
  error: string | null;
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  viewMode: "functions" | "files";
  onViewModeChange: (mode: "functions" | "files") => void;
  hasSelection: boolean;
  onClearSelection: () => void;
}

export default function Topbar({
  stats, repoPath, onRepoPathChange, onAnalyze,
  loading, error, leftCollapsed, rightCollapsed, onToggleLeft, onToggleRight,
  viewMode, onViewModeChange, hasSelection, onClearSelection,
}: Props) {
  const s = stats;
  return (
    <div className={styles.topbar}>

      <button
        className={`${styles.panelBtn} ${leftCollapsed ? styles.panelBtnDim : ""}`}
        onClick={onToggleLeft}
        title="Toggle file panel"
      >
        <PanelLeftIcon />
      </button>

      <form
        className={styles.analyzeForm}
        onSubmit={(e) => { e.preventDefault(); onAnalyze(repoPath); }}
      >
        <input
          className={styles.pathInput}
          type="text"
          value={repoPath}
          onChange={(e) => onRepoPathChange(e.target.value)}
          placeholder="repo path…"
          spellCheck={false}
        />
        <button
          className={styles.analyzeBtn}
          type="submit"
          disabled={loading || !repoPath.trim()}
        >
          {loading ? "…" : "analyze"}
        </button>
      </form>

      {hasSelection && (
        <button
          className={styles.showAllBtn}
          onClick={onClearSelection}
          title="Clear selection — show everything"
        >
          show all
        </button>
      )}

      <div className={styles.viewToggle}>
        <button
          className={`${styles.viewBtn} ${viewMode === "functions" ? styles.viewBtnActive : ""}`}
          onClick={() => onViewModeChange("functions")}
          title="Functions view"
        >
          fn
        </button>
        <button
          className={`${styles.viewBtn} ${viewMode === "files" ? styles.viewBtnActive : ""}`}
          onClick={() => onViewModeChange("files")}
          title="Files view"
        >
          files
        </button>
      </div>

      <div className={styles.stats}>
        {error && <span className={styles.statDanger}>{error}</span>}
        <span className={styles.stat}>{s.functions.toLocaleString()} fn</span>
        <span className={styles.stat}>{s.classes} class</span>
        <span className={styles.stat}>{s.modules} mod</span>
        <span className={`${styles.stat} ${styles.statDanger}`}>{s.vulns} vuln</span>
      </div>

      <button
        className={`${styles.panelBtn} ${rightCollapsed ? styles.panelBtnDim : ""}`}
        onClick={onToggleRight}
        title="Toggle inspector panel"
      >
        <PanelRightIcon />
      </button>

    </div>
  );
}

function PanelLeftIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <rect x="1" y="1" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
      <line x1="5" y1="1" x2="5" y2="13" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}

function PanelRightIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <rect x="1" y="1" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.2" />
      <line x1="9" y1="1" x2="9" y2="13" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  );
}
