import { useMemo } from "react";
import type { GraphNode, Caller, FileGraphEdge } from "../types/graph";
import { fileColor, assignFileColors } from "../lib/fileColors";
import styles from "./SidebarRight.module.css";

interface Props {
  node: GraphNode | null;
  callers: Caller[];
  selectedFileId: string | null;
  allNodes: GraphNode[];
  fileEdges?: FileGraphEdge[];
}

export default function SidebarRight(
  { node, callers, selectedFileId, allNodes, fileEdges }: Props
) {
  // File-level analytics
  const fileStats = useMemo(() => {
    if (!selectedFileId || node) return null;
    const fns = allNodes.filter((n) => n.file === selectedFileId && n.kind === "function");
    const classes = allNodes.filter((n) => n.file === selectedFileId && n.kind === "class");
    const allInFile = allNodes.filter((n) => n.file === selectedFileId);
    const totalLoc = allInFile.reduce((s, n) => s + (n.metrics?.loc ?? 0), 0);
    const complexities = fns.map((n) => n.metrics?.cyclomatic ?? 1);
    const avgComplexity = complexities.length
      ? complexities.reduce((a, b) => a + b, 0) / complexities.length
      : 0;
    const peakFn = fns.reduce<GraphNode | null>(
      (best, n) => !best || (n.metrics?.cyclomatic ?? 0) > (best.metrics?.cyclomatic ?? 0) ? n : best,
      null,
    );
    const vulnNodes = allInFile.filter((n) => !!n.vulnerability);
    const hotNodes = allInFile.filter((n) => !!n.isHot);
    const complexNodes = allInFile.filter((n) => !!n.isComplex);
    const outgoing = fileEdges?.filter((e) => e.source === selectedFileId) ?? [];
    const incoming = fileEdges?.filter((e) => e.target === selectedFileId) ?? [];
    return { fns, classes, totalLoc, avgComplexity, peakFn, vulnNodes, hotNodes, complexNodes, outgoing, incoming };
  }, [selectedFileId, node, allNodes, fileEdges]);

  const fileColorMap = useMemo(
    () => assignFileColors(allNodes.map((n) => n.file ?? "").filter(Boolean)),
    [allNodes],
  );

  function colorForFile(file: string) {
    return fileColor(fileColorMap.get(file) ?? 0);
  }

  // ── Empty state ──
  if (!node && !selectedFileId) {
    return (
      <div className={styles.sidebar}>
        <div className={styles.empty}>Select a node to inspect</div>
      </div>
    );
  }

  // ── File analytics ──
  if (fileStats) {
    const { fns, classes, totalLoc, avgComplexity, peakFn, vulnNodes, hotNodes, complexNodes, outgoing, incoming } = fileStats;
    const color = colorForFile(selectedFileId!);
    const basename = selectedFileId!.split("/").pop() ?? selectedFileId!;
    const avgPct = Math.min((avgComplexity / 15) * 100, 100);
    const avgClass = avgComplexity <= 3 ? styles.low : avgComplexity <= 6 ? styles.med : avgComplexity <= 10 ? styles.high : styles.crit;

    return (
      <div className={styles.sidebar}>
        <div className={styles.header}>
          <span className={styles.fileAccent} style={{ background: color.border }} />
          <div>
            <div className={styles.title}>{basename}</div>
            <div className={styles.kind}>file</div>
          </div>
        </div>

        {/* Size */}
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Size</div>
          <MetaRow label="functions" value={String(fns.length)} />
          <MetaRow label="classes" value={String(classes.length)} />
          <MetaRow label="loc" value={String(totalLoc)} />
          <MetaRow label="hot functions" value={String(hotNodes.length)}
            valueStyle={hotNodes.length > 0 ? { color: "#c07840" } : undefined} />
          <MetaRow label="complex functions" value={String(complexNodes.length)}
            valueStyle={complexNodes.length > 0 ? { color: "#9a9daa" } : undefined} />
        </div>

        {/* Complexity */}
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Complexity</div>
          <MetaRow label="avg cyclomatic" value={avgComplexity.toFixed(1)} />
          <div className={styles.complexityBar}>
            <div className={`${styles.complexityFill} ${avgClass}`} style={{ width: `${avgPct}%` }} />
          </div>
          {peakFn && (
            <div className={styles.peakRow}>
              <span className={styles.peakLabel}>peak</span>
              <span className={styles.peakName}>{peakFn.label}</span>
              <span className={styles.peakVal}>{peakFn.metrics?.cyclomatic}</span>
            </div>
          )}
        </div>

        {/* Vulnerabilities */}
        {vulnNodes.length > 0 && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>
              Vulnerabilities
              <span className={styles.vulnCount}>{vulnNodes.length}</span>
            </div>
            {vulnNodes.map((n) => (
              <div key={n.id} className={styles.vulnItem}>
                <div className={styles.vulnFn}>{n.label}</div>
                <div className={styles.vulnTitle}>{n.vulnerability}</div>
              </div>
            ))}
          </div>
        )}

        {/* Coupling */}
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Coupling</div>
          <MetaRow label="imports from" value={String(outgoing.length)} />
          {outgoing.length > 0 && (
            <div className={styles.depList}>
              {outgoing.map((e) => {
                const c = colorForFile(e.target);
                const name = e.target.split("/").pop() ?? e.target;
                return (
                  <div key={e.target} className={styles.depRow}>
                    <span className={styles.depDot} style={{ background: c.border }} />
                    <span className={styles.depName}>{name}</span>
                    {e.callCount > 0 && <span className={styles.depCount}>{e.callCount}</span>}
                  </div>
                );
              })}
            </div>
          )}
          <div className={styles.metaRowSpaced}>
            <MetaRow label="imported by" value={String(incoming.length)} />
          </div>
          {incoming.length > 0 && (
            <div className={styles.depList}>
              {incoming.map((e) => {
                const c = colorForFile(e.source);
                const name = e.source.split("/").pop() ?? e.source;
                return (
                  <div key={e.source} className={styles.depRow}>
                    <span className={styles.depDot} style={{ background: c.border }} />
                    <span className={styles.depName}>{name}</span>
                    {e.callCount > 0 && <span className={styles.depCount}>{e.callCount}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Node inspection ──
  const m = node!.metrics;

  // Complexity
  const cycloPct   = Math.min((m.cyclomatic / 20) * 100, 100);
  const cycloClass = m.cyclomatic <= 5 ? styles.low : m.cyclomatic <= 10 ? styles.med : m.cyclomatic <= 15 ? styles.high : styles.crit;

  // Instability: callees / (callers + callees), 0 = stable, 1 = unstable
  const total = m.callers + m.callees;
  const instability = total > 0 ? m.callees / total : null;
  const instPct = instability !== null ? instability * 100 : 0;
  const instLabel = instability === null ? "—"
    : instability < 0.3 ? "stable"
    : instability < 0.7 ? "mixed"
    : "unstable";
  const instClass = instability === null ? styles.low
    : instability < 0.3 ? styles.low
    : instability < 0.7 ? styles.med
    : styles.high;

  return (
    <div className={styles.sidebar}>
      <div className={styles.header}>
        <div className={styles.title}>{node!.label}</div>
        <div className={styles.kind}>{node!.kind}</div>
      </div>

      {/* Complexity */}
      <div className={styles.section}>
        <div className={styles.sectionTitle}>Complexity &amp; Size</div>
        <MetaRow
          label="branch paths"
          value={String(m.cyclomatic)}
          valueStyle={m.cyclomatic > 10 ? { color: m.cyclomatic > 15 ? "var(--danger)" : "#b0b2bc" } : undefined}
          hint={
            m.cyclomatic <= 5 ? "simple — easy to read and test" :
            m.cyclomatic <= 10 ? "moderate — worth reviewing" :
            m.cyclomatic <= 15 ? "complex — consider splitting" :
            "very complex — high bug risk, hard to test"
          }
        />
        <div className={styles.complexityBar}>
          <div className={`${styles.complexityFill} ${cycloClass}`} style={{ width: `${cycloPct}%` }} />
        </div>
        <MetaRow label="lines of code" value={String(m.loc)} />
        <MetaRow
          label="parameters"
          value={String(m.params)}
          valueStyle={m.params > 5 ? { color: "#b0b2bc" } : undefined}
          hint={m.params > 5 ? "too many params — consider a config object" : undefined}
        />
        <MetaRow
          label="max nesting"
          value={String(m.maxNesting)}
          valueStyle={m.maxNesting > 3 ? { color: m.maxNesting > 5 ? "var(--danger)" : "#b0b2bc" } : undefined}
          hint={m.maxNesting > 3 ? "deeply nested — harder to follow logic" : undefined}
        />
      </div>

      {/* Coupling */}
      <div className={styles.section}>
        <div className={styles.sectionTitle}>Coupling</div>
        <MetaRow
          label="called by"
          value={m.callers === 0 ? "nothing" : `${m.callers} fn${m.callers !== 1 ? "s" : ""}`}
          hint="how many functions depend on this"
        />
        <MetaRow
          label="calls out to"
          value={m.callees === 0 ? "nothing" : `${m.callees} fn${m.callees !== 1 ? "s" : ""}`}
          hint="how many functions this depends on"
        />
        {instability !== null && (
          <>
            <div className={styles.instabilityRow}>
              <span className={styles.metaKey}>change risk</span>
              <span className={styles.instLabel}>{instLabel}</span>
            </div>
            <div className={styles.complexityBar}>
              <div className={`${styles.complexityFill} ${instClass}`} style={{ width: `${instPct}%` }} />
            </div>
            <div className={styles.instHint}>
              {instability < 0.3
                ? "many things depend on it — changes here have wide blast radius"
                : instability < 0.7
                ? "balanced — both a dependency and a dependent"
                : "depends on many things — fragile, hard to test in isolation"}
            </div>
          </>
        )}
      </div>

      {/* Vulnerability */}
      {node!.vulnerability && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>Vulnerabilities</div>
          <div className={styles.vulnItem}>
            <div className={styles.vulnTitle}>{node!.vulnerability}</div>
          </div>
        </div>
      )}

      {/* Callers */}
      <div className={styles.section}>
        <div className={styles.sectionTitle}>Called by</div>
        {callers.length === 0 && <div className={styles.empty}>No callers</div>}
        {callers.map((c) => (
          <div key={c.name} className={styles.callerItem}>
            <div className={styles.dot} />
            <div className={styles.callerName}>{c.name}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MetaRow({ label, value, valueStyle, hint }: {
  label: string; value: string; valueStyle?: React.CSSProperties; hint?: string;
}) {
  return (
    <div className={styles.metaRowBlock}>
      <div className={styles.metaRow}>
        <div className={styles.metaKey}>{label}</div>
        <div className={styles.metaVal} style={valueStyle}>{value}</div>
      </div>
      {hint && <div className={styles.metaHint}>{hint}</div>}
    </div>
  );
}
