import { memo, useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Review } from "../../api/models";
import { Panel } from "../../components/Panel";
import { formatTime } from "../../lib/format";
import { formatImpactPoints, impactCurve, type ImpactPoint } from "./impactCurve";
import styles from "./ImpactChart.module.css";

const TICK = { fill: "var(--text-3)", fontSize: 12, fontFamily: "var(--font-num)" };

const formatYTick = (v: number) => {
  const rounded = Math.round(v);
  if (rounded === 0) return "0%";
  return `${rounded > 0 ? "+" : "−"}${Math.abs(rounded)}%`;
};

function ImpactTooltip({
  active,
  payload,
  opponentName,
}: {
  active?: boolean;
  payload?: readonly { payload: ImpactPoint }[];
  opponentName?: string | null;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  const timeStr = formatTime(point.t);
  const teamStr = `team ${Math.round(point.teamP * 100)}%`;
  const youStr = `you ${formatImpactPoints(point.me)}`;
  const parts = [timeStr, teamStr, youStr];
  if (opponentName && point.opponent != null) {
    parts.push(`${opponentName} ${formatImpactPoints(point.opponent)}`);
  }
  return <div className={styles.tooltip}>{parts.join(" · ")}</div>;
}

export type ImpactChartProps = {
  review: Review;
};

/** Doesn't follow the scrubber, so it never re-renders while the game time moves. */
export const ImpactChart = memo(function ImpactChart({ review }: ImpactChartProps) {
  const curve = useMemo(() => impactCurve(review), [review]);
  if (!curve) return null;

  const { me, opponent, points } = curve;
  const duration = review.match.duration_s;

  let max = 10;
  for (const pt of points) {
    if (Number.isFinite(pt.team)) max = Math.max(max, Math.abs(pt.team));
    if (Number.isFinite(pt.me)) max = Math.max(max, Math.abs(pt.me));
    if (pt.opponent != null && Number.isFinite(pt.opponent)) {
      max = Math.max(max, Math.abs(pt.opponent));
    }
  }
  const maxVal = Math.ceil(max / 5) * 5;

  const laneLabel = me.lane == null ? null : `Lane ${formatImpactPoints(me.lane * 100)}`;

  const renderMeDot = (dotProps: {
    cx?: number;
    cy?: number;
    index?: number;
    payload?: ImpactPoint;
  }) => {
    const { cx, cy, index, payload } = dotProps;
    if (cx == null || cy == null || !payload || !payload.hasMyDot) return null;
    const isPos = (payload.myShare ?? 0) >= 0;
    const color = isPos ? "var(--ally)" : "var(--enemy)";
    return (
      <circle
        key={`dot-${index ?? payload.t}`}
        cx={cx}
        cy={cy}
        r={4}
        fill={color}
        stroke="var(--surface)"
        strokeWidth={1.5}
      />
    );
  };

  return (
    <Panel title="Impact">
      <div className={styles.chart}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
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
              domain={[-maxVal, maxVal]}
              tickFormatter={formatYTick}
              tick={TICK}
              tickLine={false}
              axisLine={false}
              width={48}
            />
            <ReferenceLine y={0} stroke="var(--text-3)" />
            {duration >= 840 && (
              <ReferenceLine
                x={840}
                stroke="var(--border)"
                strokeDasharray="3 3"
                label={
                  laneLabel
                    ? {
                        value: laneLabel,
                        position: "insideTopLeft",
                        fill: "var(--text-3)",
                        fontSize: 12,
                        fontFamily: "var(--font-num)",
                      }
                    : undefined
                }
              />
            )}
            <Tooltip
              content={(props) => (
                <ImpactTooltip
                  active={props.active}
                  payload={props.payload as readonly { payload: ImpactPoint }[] | undefined}
                  opponentName={opponent?.champion_name}
                />
              )}
              cursor={{ stroke: "var(--border)", strokeDasharray: "2 2" }}
              isAnimationActive={false}
            />
            <Area
              dataKey="team"
              type="linear"
              baseValue={0}
              stroke="var(--ally)"
              strokeWidth={1}
              strokeOpacity={0.4}
              fill="var(--ally-tint)"
              dot={false}
              activeDot={false}
              isAnimationActive={false}
            />
            {opponent && (
              <Line
                dataKey="opponent"
                type="stepAfter"
                stroke="var(--enemy)"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
                activeDot={false}
                isAnimationActive={false}
              />
            )}
            <Line
              dataKey="me"
              type="stepAfter"
              stroke="var(--you)"
              strokeWidth={2}
              dot={renderMeDot}
              activeDot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className={styles.footer}>
        <p>Fights and objectives only; farming between fights is the team&apos;s.</p>
      </div>
    </Panel>
  );
});
