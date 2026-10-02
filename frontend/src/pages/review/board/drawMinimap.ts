import { initials } from "../../../lib/ddragon";
import {
  BUILDING_SIZE,
  ICON_SIZE,
  LANE_LINES,
  RING,
  debugGrid,
  type BuildingMark,
  type ChampionMark,
  type KillMark,
} from "./minimapModel";

export type MinimapColors = {
  bg: string;
  surface2: string;
  border: string;
  text: string;
  text3: string;
  ally: string;
  enemy: string;
  you: string;
};

export type DrawArgs = {
  size: number;
  dpr: number;
  colors: MinimapColors;
  map: HTMLImageElement | null;
  icons: Map<string, HTMLImageElement | null>;
  buildings: BuildingMark[];
  kills: KillMark[];
  champions: ChampionMark[];
  debug: boolean;
};

/** Canvas cannot read CSS variables, so the colors are looked up once per draw. */
export function readColors(el: Element): MinimapColors {
  const css = getComputedStyle(el);
  const get = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    bg: get("--bg", "#0e1217"),
    surface2: get("--surface-2", "#1a1f27"),
    border: get("--border", "#2a313b"),
    text: get("--text", "#e8e6e1"),
    text3: get("--text-3", "#858a92"),
    ally: get("--ally", "#3987e5"),
    enemy: get("--enemy", "#e66767"),
    you: get("--you", "#d4b26a"),
  };
}

const grayCache = new WeakMap<HTMLImageElement, HTMLCanvasElement | null>();

/** A grayscale copy of an icon, made once. Null if the pixels cannot be read. */
function grayscale(img: HTMLImageElement): HTMLCanvasElement | null {
  if (grayCache.has(img)) return grayCache.get(img) ?? null;
  let out: HTMLCanvasElement | null = null;
  try {
    const c = document.createElement("canvas");
    c.width = img.naturalWidth || ICON_SIZE;
    c.height = img.naturalHeight || ICON_SIZE;
    const g = c.getContext("2d");
    if (g) {
      g.drawImage(img, 0, 0, c.width, c.height);
      const data = g.getImageData(0, 0, c.width, c.height);
      const px = data.data;
      for (let i = 0; i < px.length; i += 4) {
        const y = 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2];
        px[i] = px[i + 1] = px[i + 2] = y;
      }
      g.putImageData(data, 0, 0);
      out = c;
    }
  } catch {
    out = null;
  }
  grayCache.set(img, out);
  return out;
}

function drawBackground(ctx: CanvasRenderingContext2D, a: DrawArgs) {
  const { size, colors } = a;
  ctx.fillStyle = colors.bg;
  ctx.fillRect(0, 0, size, size);
  if (a.map) {
    ctx.drawImage(a.map, 0, 0, size, size);
    ctx.fillStyle = "rgba(0, 0, 0, 0.2)"; // 80% brightness
    ctx.fillRect(0, 0, size, size);
    return;
  }
  ctx.strokeStyle = colors.border;
  ctx.lineWidth = 6;
  ctx.lineJoin = "round";
  for (const line of LANE_LINES) {
    ctx.beginPath();
    line.forEach(([fx, fy], i) =>
      i === 0 ? ctx.moveTo(fx * size, fy * size) : ctx.lineTo(fx * size, fy * size),
    );
    ctx.stroke();
  }
}

function drawBuildings(ctx: CanvasRenderingContext2D, a: DrawArgs) {
  const h = BUILDING_SIZE / 2;
  for (const b of a.buildings) {
    if (b.down) {
      ctx.strokeStyle = a.colors.border;
      ctx.lineWidth = 1;
      ctx.strokeRect(b.cx - h + 0.5, b.cy - h + 0.5, BUILDING_SIZE - 1, BUILDING_SIZE - 1);
    } else {
      ctx.fillStyle = a.colors[b.team];
      ctx.fillRect(b.cx - h, b.cy - h, BUILDING_SIZE, BUILDING_SIZE);
    }
  }
}

function drawKills(ctx: CanvasRenderingContext2D, a: DrawArgs) {
  const r = 5;
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  for (const k of a.kills) {
    ctx.strokeStyle = a.colors[k.team];
    ctx.beginPath();
    ctx.moveTo(k.cx - r, k.cy - r);
    ctx.lineTo(k.cx + r, k.cy + r);
    ctx.moveTo(k.cx + r, k.cy - r);
    ctx.lineTo(k.cx - r, k.cy + r);
    ctx.stroke();
  }
}

function drawChampion(ctx: CanvasRenderingContext2D, a: DrawArgs, m: ChampionMark) {
  const { cx, cy } = m;
  const r = ICON_SIZE / 2;
  const img = a.icons.get(m.player.champion) ?? null;
  ctx.save();
  ctx.globalAlpha = m.opacity;

  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, r, 0, Math.PI * 2);
  ctx.clip();
  ctx.fillStyle = a.colors.surface2;
  ctx.fillRect(cx - r, cy - r, ICON_SIZE, ICON_SIZE);
  if (img) {
    const src = m.dead ? (grayscale(img) ?? img) : img;
    ctx.drawImage(src, cx - r, cy - r, ICON_SIZE, ICON_SIZE);
  } else {
    ctx.fillStyle = a.colors.text3;
    ctx.font = "600 11px 'Barlow Semi Condensed', system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(initials(m.player.champion_name), cx, cy + 0.5);
  }
  ctx.restore();

  ctx.strokeStyle = a.colors[m.team];
  ctx.lineWidth = RING;
  ctx.beginPath();
  ctx.arc(cx, cy, r + RING / 2, 0, Math.PI * 2);
  ctx.stroke();
  if (m.isYou) {
    ctx.strokeStyle = a.colors.you;
    ctx.beginPath();
    ctx.arc(cx, cy, r + RING + RING / 2, 0, Math.PI * 2);
    ctx.stroke();
  }
  ctx.restore();

  if (m.dead) {
    ctx.fillStyle = a.colors.text;
    ctx.font = "500 11px 'Barlow Semi Condensed', system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText(`${m.respawn}`, cx, cy + r + RING * 2 + 2);
  }
}

function drawDebug(ctx: CanvasRenderingContext2D, a: DrawArgs) {
  ctx.save();
  ctx.strokeStyle = a.colors.text3;
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1;
  for (const l of debugGrid(a.size)) {
    ctx.beginPath();
    ctx.moveTo(l.x1, l.y1);
    ctx.lineTo(l.x2, l.y2);
    ctx.stroke();
  }
  ctx.restore();
}

/** Draws the whole minimap in UI.md's order: buildings, kill marks, enemies, allies, you. */
export function drawMinimap(ctx: CanvasRenderingContext2D, a: DrawArgs) {
  ctx.setTransform(a.dpr, 0, 0, a.dpr, 0, 0);
  ctx.clearRect(0, 0, a.size, a.size);
  drawBackground(ctx, a);
  drawBuildings(ctx, a);
  drawKills(ctx, a);
  for (const m of a.champions) drawChampion(ctx, a, m);
  if (a.debug) drawDebug(ctx, a);
}
