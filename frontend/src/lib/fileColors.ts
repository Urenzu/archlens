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
  // Warm, desaturated palette — industrial / forge feel.
  // Low saturation keeps things from feeling rainbow; warm bias fits the theme.
  const hue = (index * 137.508) % 360;
  return {
    border:   `hsl(${hue}, 52%, 38%)`,
    text:     `hsl(${hue}, 52%, 58%)`,
    selected: `hsl(${hue}, 62%, 74%)`,
  };
}

/** Assign a stable color index to each file path (sorted alphabetically). */
export function assignFileColors(filePaths: string[]): Map<string, number> {
  const unique = [...new Set(filePaths)].sort();
  const map = new Map<string, number>();
  unique.forEach((f, i) => map.set(f, i));
  return map;
}
