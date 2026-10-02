import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "../../components/Panel";
import { Numbers } from "./Numbers";
import { pct, pct1, type MinuteRow } from "./metrics";
import styles from "./model.module.css";

const TICK = { fill: "var(--text-3)", fontSize: 12, fontFamily: "var(--font-num)" };

type EndLabelProps = { x?: number | string; y?: number | string; index?: number };

/** Names a line at its right end: the label is drawn only for the last point. */
const endLabel = (name: string, last: number) =>
  function EndLabel({ x, y, index }: EndLabelProps) {
    if (index !== last || typeof x !== "number" || typeof y !== "number") return null;
    return (
      <text x={x + 8} y={y} dy={4} fill="var(--text-2)" fontSize={12}>
        {name}
      </text>
    );
  };

type TipProps = { active?: boolean; label?: string | number; payload?: { payload: MinuteRow }[] };

function Tip({ active, label, payload }: TipProps) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className={styles.tip}>
      <p className={styles.tipTitle}>{label} min</p>
      <p>
        LightGBM <span className="num">{pct1(row.lightgbm)}</span>
      </p>
      <p>
        Baseline <span className="num">{pct1(row.baseline)}</span>
      </p>
    </div>
  );
}

export function AccuracyChart({ rows }: { rows: MinuteRow[] }) {
  const values = rows.flatMap((r) => [r.lightgbm, r.baseline]);
  const lo = Math.floor(Math.min(...values) * 20) / 20;
  const hi = Math.ceil(Math.max(...values) * 20) / 20;
  const last = rows.length - 1;
  const ticks = Array.from({ length: Math.round((hi - lo) / 0.05) + 1 }, (_, i) => lo + i * 0.05);
  return (
    <Panel title="Accuracy by minute">
      <div className={styles.chart}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 84, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={TICK}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              label={{
                value: "Minute of the game",
                position: "insideBottom",
                offset: 4,
                fill: "var(--text-3)",
                fontSize: 12,
              }}
              height={48}
            />
            <YAxis
              domain={[lo, hi]}
              ticks={ticks}
              tickFormatter={pct}
              tick={TICK}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <Tooltip
              content={<Tip />}
              cursor={{ stroke: "var(--text-3)", strokeWidth: 1 }}
              isAnimationActive={false}
            />
            <Line
              dataKey="lightgbm"
              stroke="var(--text)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              label={endLabel("LightGBM", last)}
              activeDot={{ r: 4, fill: "var(--text)", stroke: "var(--surface)" }}
            />
            <Line
              dataKey="baseline"
              stroke="var(--text-3)"
              strokeWidth={2}
              strokeDasharray="5 4"
              dot={false}
              isAnimationActive={false}
              label={endLabel("Baseline", last)}
              activeDot={{ r: 4, fill: "var(--text-3)", stroke: "var(--surface)" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Numbers
        head={["Minute", "LightGBM", "Baseline"]}
        rows={rows.map((r) => [r.label, pct1(r.lightgbm), pct1(r.baseline)])}
      />
    </Panel>
  );
}
