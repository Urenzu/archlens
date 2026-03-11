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
}

export default function Topbar({
  stats, repoPath, onRepoPathChange, onAnalyze,
  loading, error, leftCollapsed, rightCollapsed, onToggleLeft, onToggleRight,
  viewMode, onViewModeChange,
}: Props) {
  const s = stats;
  const hasData = s.functions > 0 || s.modules > 0;
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
          placeholder="enter repo path…"
          spellCheck={false}
        />
        <button
          className={styles.analyzeBtn}
          type="submit"
          disabled={loading || !repoPath.trim()}
        >
          {loading ? <span className={styles.analyzingDot} /> : "analyze"}
        </button>
      </form>

      {/* View mode toggle — full words so intent is obvious */}
      <div className={styles.viewToggle}>
        <button
          className={`${styles.viewBtn} ${viewMode === "functions" ? styles.viewBtnActive : ""}`}
          onClick={() => onViewModeChange("functions")}
          title="Show individual functions"
        >
          functions
        </button>
        <button
          className={`${styles.viewBtn} ${viewMode === "files" ? styles.viewBtnActive : ""}`}
          onClick={() => onViewModeChange("files")}
          title="Show file-level dependencies"
        >
          files
        </button>
      </div>

      {/* Stats — only shown after a repo is loaded */}
      {hasData && (
        <div className={styles.stats}>
          {error && <span className={styles.statError}>{error}</span>}
          <span className={styles.statItem}>
            <span className={styles.statVal}>{s.functions.toLocaleString()}</span>
            <span className={styles.statLabel}>functions</span>
          </span>
          <span className={styles.statDivider} />
          <span className={styles.statItem}>
            <span className={styles.statVal}>{s.classes}</span>
            <span className={styles.statLabel}>classes</span>
          </span>
          <span className={styles.statDivider} />
          <span className={styles.statItem}>
            <span className={styles.statVal}>{s.modules}</span>
            <span className={styles.statLabel}>modules</span>
          </span>
          {s.vulns > 0 && (
            <>
              <span className={styles.statDivider} />
              <span className={`${styles.statItem} ${styles.statItemDanger}`}>
                <span className={styles.statVal}>{s.vulns}</span>
                <span className={styles.statLabel}>vulns</span>
              </span>
            </>
          )}
        </div>
      )}

      <button
        className={`${styles.panelBtn} ${rightCollapsed ? styles.panelBtnDim : ""}`}
        onClick={onToggleRight}
        title="Toggle inspector panel"
      >
        <PanelRightIcon />
      </button>

      {loading && <div className={styles.loadingBar} />}
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
