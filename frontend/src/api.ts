import type { AnalysisResult } from "./types/graph";

export async function analyzeRepo(path: string): Promise<AnalysisResult> {
  const res = await fetch(`/api/analyze?path=${encodeURIComponent(path)}`);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || "Analysis failed");
  }
  return res.json();
}
