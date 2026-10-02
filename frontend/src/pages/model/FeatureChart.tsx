import { Bar, BarChart, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { Panel } from "../../components/Panel";
import { Numbers } from "./Numbers";
import { featureName, pct1, type FeatureRow } from "./metrics";
import styles from "./model.module.css";

const ROW_H = 24;

export function FeatureChart({ rows }: { rows: FeatureRow[] }) {
  const data = rows.map((r) => ({ ...r, name: featureName(r.feature) }));
  return (
    <Panel title="Top features">
      <p className={styles.caption}>Share of the model's total gain.</p>
      <div className={styles.chart} style={{ height: Math.max(data.length, 1) * ROW_H + 8 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 48, bottom: 0, left: 0 }}
            barCategoryGap={4}
          >
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis
              type="category"
              dataKey="name"
              width={140}
              tickLine={false}
              axisLine={false}
              interval={0}
              tick={{ fill: "var(--text-2)", fontSize: 12 }}
            />
            <Bar dataKey="gain" fill="var(--text-3)" isAnimationActive={false} radius={2}>
              <LabelList
                dataKey="share"
                position="right"
                formatter={(v: unknown) => (typeof v === "number" ? pct1(v) : "")}
                fill="var(--text)"
                fontSize={12}
                fontFamily="var(--font-num)"
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <Numbers
        head={["Feature", "Gain", "Share"]}
        rows={data.map((r) => [r.name, r.gain.toLocaleString("en-US"), pct1(r.share)])}
      />
    </Panel>
  );
}
