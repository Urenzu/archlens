export interface FileColor {
  border: string;
  text: string;
  selected: string;
}

/**
 * Generate a muted but distinct color for a given index using the golden angle.
 * Works for any number of files — no palette size limit.
 */
export function fileColor(index: number): FileColor {
  const hue = (index * 137.508) % 360; // golden angle
  return {
    border:   `hsl(${hue}, 40%, 42%)`,
    text:     `hsl(${hue}, 40%, 55%)`,
    selected: `hsl(${hue}, 60%, 72%)`,
  };
}

/** Assign a stable color index to each file path (sorted alphabetically). */
export function assignFileColors(filePaths: string[]): Map<string, number> {
  const unique = [...new Set(filePaths)].sort();
  const map = new Map<string, number>();
  unique.forEach((f, i) => map.set(f, i));
  return map;
}
