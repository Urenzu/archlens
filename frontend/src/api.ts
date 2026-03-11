import type { AnalysisResult } from "./types/graph";

export async function analyzeRepo(path: string): Promise<AnalysisResult> {
  const res = await fetch(
    `/api/analyze?path=${encodeURIComponent(path)}`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Analysis failed");
  }
  return res.json();
}
