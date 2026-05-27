import type { NormalizedPoint } from "./types";

export function normalizedToCanvas(
  point: NormalizedPoint,
  canvasW: number,
  canvasH: number
): { x: number; y: number } {
  return { x: point.x * canvasW, y: point.y * canvasH };
}

export function canvasToNormalized(
  x: number,
  y: number,
  canvasW: number,
  canvasH: number
): NormalizedPoint {
  return {
    x: Math.max(0, Math.min(1, x / canvasW)),
    y: Math.max(0, Math.min(1, y / canvasH)),
  };
}

export function pointsToFlatArray(
  points: NormalizedPoint[],
  canvasW: number,
  canvasH: number
): number[] {
  return points.flatMap((p) => {
    const c = normalizedToCanvas(p, canvasW, canvasH);
    return [c.x, c.y];
  });
}

export function polygonCenter(
  points: NormalizedPoint[],
  canvasW: number,
  canvasH: number
): { x: number; y: number } {
  const canvas = points.map((p) => normalizedToCanvas(p, canvasW, canvasH));
  const x = canvas.reduce((s, p) => s + p.x, 0) / canvas.length;
  const y = canvas.reduce((s, p) => s + p.y, 0) / canvas.length;
  return { x, y };
}

export function getPlotColor(plot: {
  number_detected: boolean;
  confidence: number;
  plot_number: string | null;
  verified?: boolean;
}): { fill: string; stroke: string } {
  if (plot.verified) {
    return { fill: "rgba(34,197,94,0.3)", stroke: "#16a34a" };
  }
  if (plot.plot_number && plot.number_detected) {
    return { fill: "rgba(34,197,94,0.25)", stroke: "#22c55e" };
  }
  if (plot.confidence > 0.5) {
    return { fill: "rgba(234,179,8,0.3)", stroke: "#ca8a04" };
  }
  return { fill: "rgba(239,68,68,0.3)", stroke: "#ef4444" };
}
