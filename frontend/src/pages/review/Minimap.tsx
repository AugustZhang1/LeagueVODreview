import { useEffect, useMemo, useRef, useState } from "react";
import { championIconUrl, mapUrl } from "../../lib/ddragon";
import { formatKda, formatTime } from "../../lib/format";
import type { Review, Snapshot } from "../../api/models";
import { drawMinimap, readColors } from "./board/drawMinimap";
import { loadImage } from "./board/loadImage";
import { hitTest, positionAge, reviewMarks, type ChampionMark } from "./board/minimapModel";
import styles from "./Minimap.module.css";

type Props = { review: Review; snapshot: Snapshot; t: number };
type Hover = { mark: ChampionMark; x: number; y: number };
type Assets = { map: HTMLImageElement | null; icons: Map<string, HTMLImageElement | null> };

/** The match's map and the ten champion icons; resolves once every one has loaded or failed. */
function useAssets(review: Review): Assets | null {
  const version = review.match.ddragon_version;
  const [loaded, setLoaded] = useState<{ key: string; assets: Assets } | null>(null);
  const champions = useMemo(
    () => [...new Set(review.players.map((p) => p.champion))],
    [review.players],
  );
  const key = `${version}|${champions.join(",")}`;
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      loadImage(mapUrl(version)),
      ...champions.map((c) => loadImage(championIconUrl(version, c))),
    ]).then(([map, ...imgs]) => {
      if (cancelled) return;
      setLoaded({ key, assets: { map, icons: new Map(champions.map((c, i) => [c, imgs[i]])) } });
    });
    return () => {
      cancelled = true;
    };
  }, [key, version, champions]);
  return loaded?.key === key ? loaded.assets : null;
}

function useWidth(ref: React.RefObject<HTMLElement | null>): number {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => setWidth(el.clientWidth);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return width;
}

export function Minimap({ review, snapshot, t }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const size = useWidth(wrap);
  const assets = useAssets(review);
  const [hover, setHover] = useState<Hover | null>(null);
  const debug = new URLSearchParams(window.location.search).get("debug") === "1";

  const marks = useMemo(() => reviewMarks(review, snapshot, t, size), [review, snapshot, t, size]);

  useEffect(() => {
    const el = canvas.current;
    if (!el || !assets || size === 0) return;
    const dpr = window.devicePixelRatio || 1;
    const frame = requestAnimationFrame(() => {
      const ctx = el.getContext("2d");
      if (!ctx) return;
      const px = Math.round(size * dpr);
      if (el.width !== px) {
        el.width = px;
        el.height = px;
      }
      drawMinimap(ctx, {
        size,
        dpr,
        colors: readColors(el),
        map: assets.map,
        icons: assets.icons,
        buildings: marks.buildings,
        kills: marks.kills,
        champions: marks.champions,
        debug,
      });
    });
    return () => cancelAnimationFrame(frame);
  }, [assets, size, marks, debug]);

  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - box.left;
    const y = e.clientY - box.top;
    const mark = hitTest(marks.champions, x, y);
    setHover(mark ? { mark, x, y } : null);
  };

  const tip = hover?.mark;
  return (
    <div ref={wrap} className={styles.wrap}>
      <canvas
        ref={canvas}
        className={styles.canvas}
        style={{ width: size, height: size }}
        role="img"
        aria-label="Minimap"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      />
      {hover && tip && (
        <div
          className={styles.tip}
          role="tooltip"
          style={{
            left: Math.min(hover.x + 14, Math.max(0, size - 180)),
            top: Math.min(hover.y + 14, Math.max(0, size - 84)),
          }}
        >
          <div className={styles.champ}>{tip.player.champion_name}</div>
          <div className={styles.riotId}>{tip.player.riot_id}</div>
          <div className={`${styles.line} num`}>
            Level {tip.state.level}
            {"  "}
            {formatKda(tip.state.k, tip.state.d, tip.state.a)}
          </div>
          <div className={`${styles.line} num`}>
            position {formatTime(positionAge(tip, t, snapshot))} old
          </div>
        </div>
      )}
    </div>
  );
}
