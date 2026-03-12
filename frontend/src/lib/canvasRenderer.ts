/** Canvas-based rendering for dot grid, edges, and arrowheads. */

export interface VisibleEdge {
  id: string;
  sx: number; sy: number; // source anchor (world coords)
  tx: number; ty: number; // target anchor (world coords)
  color: string;
  width: number;
  opacity: number;
  isHovered: boolean;
}

export interface DrawParams {
  ctx: CanvasRenderingContext2D;
  width: number;   // canvas.width (physical pixels)
  height: number;   // canvas.height (physical pixels)
  dpr: number;
  tx: number;       // transform x (CSS pixels)
  ty: number;       // transform y (CSS pixels)
  scale: number;    // zoom scale
  edges: VisibleEdge[];
}

const DOT_SPACING = 24;
const DOT_RADIUS = 0.7;
const DOT_COLOR = "#222222";
const ARROW_SIZE = 5;

export function drawFrame(p: DrawParams): void {
  const { ctx, width, height, dpr, tx, ty, scale, edges } = p;
  const cssW = width / dpr;
  const cssH = height / dpr;

  // Clear entire canvas (physical pixels)
  ctx.clearRect(0, 0, width, height);

  // All drawing from here uses CSS-pixel coordinates, scaled up by DPR once.
  ctx.save();
  ctx.scale(dpr, dpr);

  // ── Dot grid (screen space) ───────────────────────────
  ctx.fillStyle = DOT_COLOR;
  const offsetX = ((tx % DOT_SPACING) + DOT_SPACING) % DOT_SPACING;
  const offsetY = ((ty % DOT_SPACING) + DOT_SPACING) % DOT_SPACING;
  for (let x = offsetX; x < cssW; x += DOT_SPACING) {
    for (let y = offsetY; y < cssH; y += DOT_SPACING) {
      ctx.beginPath();
      ctx.arc(x, y, DOT_RADIUS, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // ── Apply world transform (on top of DPR) ─────────────
  ctx.translate(tx, ty);
  ctx.scale(scale, scale);

  // ── Draw edges (non-hovered first, then hovered on top) ─
  for (const e of edges) {
    if (e.isHovered) continue;
    drawEdge(ctx, e, scale);
  }
  for (const e of edges) {
    if (!e.isHovered) continue;
    drawEdge(ctx, e, scale);
  }

  ctx.restore();
}

function drawEdge(ctx: CanvasRenderingContext2D, e: VisibleEdge, worldScale: number): void {
  const { sx, sy, color, width, opacity } = e;
  // Rename to avoid shadowing — edge target coords
  const etx = e.tx;
  const ety = e.ty;
  const midY = (sy + ety) / 2;

  ctx.globalAlpha = opacity;
  ctx.strokeStyle = color;
  // Compensate line width for world scale so edges stay visible at low zoom
  ctx.lineWidth = width / worldScale;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  // Bezier curve
  ctx.beginPath();
  ctx.moveTo(sx, sy);
  ctx.bezierCurveTo(sx, midY, etx, midY, etx, ety);
  ctx.stroke();

  // Arrowhead at target end
  const dt = 0.02;
  const prevT = 1 - dt;
  const mt = 1 - prevT;
  const px = mt*mt*mt*sx + 3*mt*mt*prevT*sx + 3*mt*prevT*prevT*etx + prevT*prevT*prevT*etx;
  const py = mt*mt*mt*sy + 3*mt*mt*prevT*midY + 3*mt*prevT*prevT*midY + prevT*prevT*prevT*ety;
  const angle = Math.atan2(ety - py, etx - px);

  const arrowLen = ARROW_SIZE * Math.min(width, 2.5) / worldScale;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(etx, ety);
  ctx.lineTo(
    etx - arrowLen * Math.cos(angle - Math.PI / 7),
    ety - arrowLen * Math.sin(angle - Math.PI / 7),
  );
  ctx.lineTo(
    etx - arrowLen * Math.cos(angle + Math.PI / 7),
    ety - arrowLen * Math.sin(angle + Math.PI / 7),
  );
  ctx.closePath();
  ctx.fill();

  ctx.globalAlpha = 1;
}

/** Sample a cubic bezier at parameter t. */
function sampleBezier(
  sx: number, sy: number, etx: number, ety: number, t: number,
): { x: number; y: number } {
  const midY = (sy + ety) / 2;
  const mt = 1 - t;
  // P0=(sx,sy) P1=(sx,midY) P2=(etx,midY) P3=(etx,ety)
  const x = mt*mt*mt*sx + 3*mt*mt*t*sx + 3*mt*t*t*etx + t*t*t*etx;
  const y = mt*mt*mt*sy + 3*mt*mt*t*midY + 3*mt*t*t*midY + t*t*t*ety;
  return { x, y };
}

/**
 * Hit test edges by sampling bezier curves.
 * @param screenThreshold — hit distance in CSS pixels (zoom-independent)
 * @param worldScale — current zoom level, used to convert threshold to world coords
 */
export function hitTestEdge(
  edges: VisibleEdge[],
  worldX: number,
  worldY: number,
  screenThreshold: number,
  worldScale: number,
): string | null {
  // Convert screen-pixel threshold to world-coordinate distance
  const threshold = screenThreshold / worldScale;

  let bestId: string | null = null;
  let bestDist = threshold;

  for (const e of edges) {
    // Bounding box pre-filter — expand by threshold AND account for bezier bow-out.
    // The control points are at (sx, midY) and (tx, midY) where midY = (sy+ty)/2,
    // so the curve can extend sideways beyond the endpoints.
    const midY = (e.sy + e.ty) / 2;
    const minX = Math.min(e.sx, e.tx) - threshold;
    const maxX = Math.max(e.sx, e.tx) + threshold;
    const minY = Math.min(e.sy, e.ty, midY) - threshold;
    const maxY = Math.max(e.sy, e.ty, midY) + threshold;
    if (worldX < minX || worldX > maxX || worldY < minY || worldY > maxY) continue;

    // Adaptive sample count: longer edges get more samples so gaps stay < threshold
    const edgeLen = Math.hypot(e.tx - e.sx, e.ty - e.sy);
    const samples = Math.max(20, Math.ceil(edgeLen / (threshold * 0.8)));
    const step = 1 / samples;

    for (let t = 0; t <= 1; t += step) {
      const p = sampleBezier(e.sx, e.sy, e.tx, e.ty, t);
      const d = Math.hypot(p.x - worldX, p.y - worldY);
      if (d < bestDist) {
        bestDist = d;
        bestId = e.id;
      }
    }
  }
  return bestId;
}
