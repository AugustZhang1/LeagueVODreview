import {
  CartesianGrid,
  Cell,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "../../components/Panel";
import { Numbers } from "./Numbers";
import { pct, pct1, type CalibrationRow } from "./metrics";
import styles from "./model.module.css";

const TICK = { fill: "var(--text-3)", fontSize: 12, fontFamily: "var(--font-num)" };

type TipProps = { active?: boolean; payload?: { payload: CalibrationRow }[] };

function Tip({ active, payload }: TipProps) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className={styles.tip}>
      <p>
        Predicted <span className="num">{pct1(row.predicted)}</span>
      </p>
      <p>
        Won <span className="num">{pct1(row.actual)}</span>
      </p>
    </div>
  );
}

export function CalibrationChart({
  rows,
  nearest70,
}: {
  rows: CalibrationRow[];
  nearest70: CalibrationRow | null;
}) {
  return (
    <Panel
      title="Calibration"
      actions={<span className={styles.legend}>on the line = honest</span>}
    >
      <div className={styles.chart}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--border)" />
            <XAxis
              type="number"
              dataKey="predicted"
              domain={[0, 1]}
              ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
              tickFormatter={pct}
              tick={TICK}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              height={48}
              label={{
                value: "Predicted win chance",
                position: "insideBottom",
                offset: 4,
                fill: "var(--text-3)",
                fontSize: 12,
              }}
            />
            <YAxis
              type="number"
              dataKey="actual"
              domain={[0, 1]}
              ticks={[0, 0.2, 0.4, 0.6, 0.8, 1]}
              tickFormatter={pct}
              tick={TICK}
              tickLine={false}
              axisLine={false}
              width={40}
            />
            <ReferenceLine
              segment={[
                { x: 0, y: 0 },
                { x: 1, y: 1 },
              ]}
              stroke="var(--text-3)"
              strokeDasharray="5 4"
              ifOverflow="visible"
            />
            <Tooltip content={<Tip />} cursor={false} isAnimationActive={false} />
            <Scatter data={rows} fill="var(--text)" isAnimationActive={false}>
              {rows.map((r) => (
                <Cell key={r.predicted} fill={r === nearest70 ? "var(--you)" : "var(--text)"} />
              ))}
            </Scatter>
            {nearest70 && (
              <ReferenceDot
                x={nearest70.predicted}
                y={nearest70.actual}
                r={8}
                fill="none"
                stroke="var(--you)"
                strokeWidth={2}
                label={{
                  value: `says ${pct(nearest70.predicted)}, won ${pct(nearest70.actual)}`,
                  position: "right",
                  fill: "var(--text-2)",
                  fontSize: 12,
                }}
              />
            )}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <Numbers
        head={["Predicted", "Won", "Games"]}
        rows={rows.map((r) => [pct1(r.predicted), pct1(r.actual), r.count.toLocaleString("en-US")])}
      />
    </Panel>
  );
}
