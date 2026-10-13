import { memo, useMemo, useState, type CSSProperties, type MouseEvent } from "react";
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { Moment, ObjectiveWindow, Review } from "../../api/models";
import { Delta } from "../../components/Delta";
import { GradeBadge } from "../../components/GradeBadge";
import { formatTime } from "../../lib/format";
import { GRADES, gradeColor, gradeName } from "../../lib/grades";
import { winAtClock, winLabel, winWord } from "./curve";
import { HowToRead } from "./HowToRead";
import { GRAPH_HEIGHT, PLOT_LEFT, PLOT_RIGHT } from "./layout";
import styles from "./WinGraph.module.css";

const HEIGHT = GRAPH_HEIGHT;
/** Room above the plot for the grade tags. */
const PLOT_TOP = 24;
const MARGIN = { top: PLOT_TOP, right: PLOT_RIGHT, bottom: 0, left: 0 };
const Y_AXIS_WIDTH = PLOT_LEFT;
const X_AXIS_HEIGHT = 24;
const PLOT_BOTTOM = HEIGHT - X_AXIS_HEIGHT;
const GRADIENT_ID = "win-fill";
const Y_TICKS = [0, 50, 100];

const plotInset = {
  left: Y_AXIS_WIDTH,
  right: MARGIN.right,
  top: PLOT_TOP,
  bottom: X_AXIS_HEIGHT,
};

const axisText = {
  fill: "var(--text-3)",
  fontSize: 12,
  fontFamily: "var(--font-num)",
};

type Row = { t: number; main: number | null; tail: number | null };

/** Only redraws when the review itself changes, never for the selected time. */
export const GraphChart = memo(function GraphChart({ review }: { review: Review }) {
  const duration = review.match.duration_s;
  const data = useMemo<Row[]>(() => {
    const n = review.curve.length;
    return review.curve.map((pt, i) => ({
      t: pt.t,
      main: i < n - 1 ? pt.p * 100 : null,
      tail: i >= n - 2 ? pt.p * 100 : null,
    }));
  }, [review.curve]);
  const xTicks = useMemo(() => {
    const ticks: number[] = [];
    for (let s = 0; s <= duration; s += 300) ticks.push(s);
    return ticks;
  }, [duration]);

  return (
    <ResponsiveContainer width="100%" height={HEIGHT}>
      <AreaChart data={data} margin={MARGIN} accessibilityLayer={false}>
        <defs>
          {/* blue above the 50% line, red below it */}
          <linearGradient
            id={GRADIENT_ID}
            gradientUnits="userSpaceOnUse"
            x1="0"
            y1={PLOT_TOP}
            x2="0"
            y2={PLOT_BOTTOM}
          >
            <stop offset="0" style={{ stopColor: "var(--ally-tint)" }} />
            <stop offset="0.5" style={{ stopColor: "var(--ally-tint)" }} />
            <stop offset="0.5" style={{ stopColor: "var(--enemy-tint)" }} />
            <stop offset="1" style={{ stopColor: "var(--enemy-tint)" }} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="t"
          type="number"
          domain={[0, duration]}
          ticks={xTicks}
          tickFormatter={(s: number) => formatTime(s)}
          height={X_AXIS_HEIGHT}
          tick={axisText}
          tickMargin={6}
          axisLine={false}
          tickLine={false}
          allowDataOverflow
        />
        <YAxis
          type="number"
          domain={[0, 100]}
          ticks={Y_TICKS}
          width={Y_AXIS_WIDTH}
          tick={axisText}
          tickMargin={8}
          axisLine={false}
          tickLine={false}
        />
        <ReferenceLine y={50} stroke="var(--border)" strokeDasharray="4 4" />
        <Area
          dataKey="main"
          baseValue={50}
          type="linear"
          stroke="var(--text)"
          strokeWidth={2}
          fill={`url(#${GRADIENT_ID})`}
          dot={false}
          activeDot={false}
          isAnimationActive={false}
          connectNulls={false}
        />
        <Area
          dataKey="tail"
          baseValue={50}
          type="linear"
          stroke="var(--text)"
          strokeWidth={2}
          strokeDasharray="2 4"
          fill={`url(#${GRADIENT_ID})`}
          dot={false}
          activeDot={false}
          isAnimationActive={false}
          connectNulls={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
});

type Props = {
  review: Review;
  t: number;
  selected: Moment | null;
  selectedWindow: ObjectiveWindow | null;
  hoveredId: string | null;
  onSeek: (t: number) => void;
};

/** The moment a hovered time falls in, or the graded one nearest to it. */
function momentAt(moments: Moment[], at: number, duration: number): Moment | null {
  const inside = moments.find((m) => at >= m.t_start - 1 && at <= m.t_end + 1);
  if (inside) return inside;
  const reach = duration * 0.015;
  let best: Moment | null = null;
  let bestGap = reach;
  for (const m of moments) {
    if (!m.grade) continue;
    const gap = Math.abs(m.t_end - at);
    if (gap <= bestGap) {
      best = m;
      bestGap = gap;
    }
  }
  return best;
}

export function WinGraph({ review, t, selected, selectedWindow, hoveredId, onSeek }: Props) {
  const { duration_s: duration } = review.match;
  const curve = review.curve;
  const [hoverT, setHoverT] = useState<number | null>(null);

  const markers = useMemo(
    () =>
      review.moments
        .filter((m) => m.grade !== null)
        .map((m) => ({ m, x: m.t_end / duration, p: winAtClock(curve, m.t_end, duration) })),
    [review.moments, curve, duration],
  );

  const span = selected ?? selectedWindow;
  // the selected moment's band takes its grade's colour, faintly
  const spanFill = selected?.grade
    ? `color-mix(in srgb, ${gradeColor(selected.grade)} 14%, transparent)`
    : "var(--surface-2)";

  const pct = (frac: number) => `${(Math.min(1, Math.max(0, frac)) * 100).toFixed(3)}%`;
  const timeAt = (e: MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = rect.width > 0 ? (e.clientX - rect.left) / rect.width : 0;
    return Math.min(duration, Math.max(0, frac * duration));
  };

  const hoverMoment = hoverT === null ? null : momentAt(review.moments, hoverT, duration);
  const now = winAtClock(curve, t, duration);

  return (
    <section className={styles.graph} aria-label="Win chance">
      <div className={styles.head}>
        <div className={styles.current}>
          <p className={styles.kicker}>
            Win chance at <span className="num">{formatTime(t)}</span>
          </p>
          <div className={styles.reading}>
            <span className={`${styles.value} num`}>{winLabel(curve, t, duration)}</span>
            {selected && <Delta value={selected.delta} />}
            <span className={styles.word}>{winWord(now)}</span>
          </div>
        </div>
        <div className={styles.legend}>
          {GRADES.map((g) => (
            <span key={g} className={styles.legendItem}>
              <GradeBadge grade={g} />
              {gradeName(g).toLowerCase()}
            </span>
          ))}
        </div>
        <HowToRead />
      </div>
      <div className={styles.stage} style={{ height: HEIGHT }}>
        <div className={styles.layer} style={plotInset} aria-hidden="true">
          {(review.windows ?? []).map((w) => (
            <div
              key={w.id}
              data-testid={`band-${w.id}`}
              data-missed={!w.used || undefined}
              className={w.used ? styles.band : `${styles.band} ${styles.missed}`}
              style={{
                left: pct(w.t_start / duration),
                width: `max(2px, ${pct((w.t_end - w.t_start) / duration)})`,
              }}
            />
          ))}
          {span && (
            <div
              className={styles.span}
              style={{
                left: pct(span.t_start / duration),
                width: `max(2px, ${pct((span.t_end - span.t_start) / duration)})`,
                background: spanFill,
              }}
            />
          )}
        </div>
        <div className={styles.chart}>
          <GraphChart review={review} />
        </div>
        <div className={styles.layer} style={plotInset}>
          {markers.map(({ m, x, p }) => {
            const grade = m.grade!;
            const big = hoveredId === m.id || selected?.id === m.id;
            return (
              <span
                key={m.id}
                data-testid={`marker-${m.id}`}
                data-grown={big || undefined}
                className={big ? `${styles.marker} ${styles.grown}` : styles.marker}
                style={
                  {
                    left: pct(x),
                    top: pct(1 - p),
                    "--grade": gradeColor(grade),
                  } as CSSProperties
                }
              >
                <span className={styles.dot} />
                <span className={styles.tag} aria-hidden="true">
                  {grade}
                </span>
              </span>
            );
          })}
          <div className={styles.now} style={{ left: pct(t / duration) }} data-testid="now-line" />
          {hoverT !== null && (
            <>
              <div className={styles.cross} style={{ left: pct(hoverT / duration) }} />
              <div
                className={[styles.tip, hoverT / duration > 0.7 ? styles.tipLeft : ""].join(" ")}
                style={{ left: pct(hoverT / duration) }}
                role="status"
              >
                <div className={styles.tipHead}>
                  <span className="num">{formatTime(hoverT)}</span>
                  <span className="num">{winLabel(curve, hoverT, duration)}</span>
                </div>
                {hoverMoment && (
                  <div className={styles.tipMoment}>
                    {hoverMoment.grade && <GradeBadge grade={hoverMoment.grade} />}
                    <span>{hoverMoment.title}</span>
                  </div>
                )}
              </div>
            </>
          )}
          <div
            className={styles.hit}
            data-testid="graph-hit"
            onMouseMove={(e) => setHoverT(timeAt(e))}
            onMouseLeave={() => setHoverT(null)}
            onClick={(e) => onSeek(timeAt(e))}
          />
        </div>
      </div>
    </section>
  );
}
