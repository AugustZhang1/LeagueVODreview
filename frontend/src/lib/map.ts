/** Game coordinates run from MAP_MIN to MAP_MAX on both axes. */
export const MAP_MIN = -120;
export const MAP_MAX = 14870;

/** Game (x, y) to canvas pixels. Game y points up; canvas y points down. */
export function toCanvas(x: number, y: number, size: number): { cx: number; cy: number } {
  const span = MAP_MAX - MAP_MIN;
  return {
    cx: ((x - MAP_MIN) / span) * size,
    cy: (1 - (y - MAP_MIN) / span) * size,
  };
}
