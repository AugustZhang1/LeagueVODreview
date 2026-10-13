import { memo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Review } from "../../api/models";
import { Panel } from "../../components/Panel";
import { formatGoldDelta, formatTime } from "../../lib/format";
import { formatImpactPoints } from "./impactCurve";
import { diffAt, laneDiff } from "./laneDiff";
import styles from "./LaneChart.module.css";

const TICK = { fill: "var(--text-3)", fontSize: 12, fontFamily: "var(--font-num)" };

/** The lead is noted at these times, when the game lasted that long. */
const CHECKPOINTS = [600, 900];

/** "+8", "−3", "0". */
const signed = (n: number) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n)}`;

/** Doesn't follow the scrubber, so it never re-renders while the game time moves. */
export const LaneChart = memo(function LaneChart({ review }: { review: Review }) {
  const lane = laneDiff(review);
  if (!lane) return null;
  const { opponent } = lane;
  const duration = review.match.duration_s;
  // the last snapshot can be a few seconds past the end of the game
  const points = lane.points.filter((p) => p.t <= duration);
  const me = review.players.find((p) => p.is_me);
  const laneValue = me?.lane != null ? ` · ${formatImpactPoints(me.lane * 100)} at 14:00` : "";
  return (
    <Panel title={`Lane vs ${opponent.champion_name}${laneValue}`}>
      <div className={styles.chart}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              domain={[0, duration]}
              tickFormatter={(s: number) => formatTime(s)}
              tick={TICK}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              height={24}
            />
            <YAxis
              tickFormatter={(v: number) => formatGoldDelta(v)}
              tick={TICK}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <ReferenceLine y={0} stroke="var(--text-3)" />
            <Tooltip
              labelFormatter={(v) => formatTime(Number(v))}
              formatter={(v) => formatGoldDelta(Number(v))}
              cursor={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="gold"
              stroke="var(--you)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className={styles.checks}>
        {CHECKPOINTS.filter((s) => s <= duration).map((s) => {
          const point = diffAt(points, s);
          if (!point) return null;
          return (
            <p key={s}>
              At {formatTime(s)}: {formatGoldDelta(point.gold)} gold, {signed(point.cs)} CS
            </p>
          );
        })}
      </div>
    </Panel>
  );
});
