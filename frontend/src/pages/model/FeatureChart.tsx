import { Panel } from "../../components/Panel";
import { Numbers } from "./Numbers";
import { featureName, pct, pct1, type FeatureRow } from "./metrics";
import styles from "./model.module.css";

/** The features as bars with no track, largest first. The top one gets the takeaway line. */
export function FeatureChart({ rows }: { rows: FeatureRow[] }) {
  const data = rows.map((r) => ({ ...r, name: featureName(r.feature) }));
  const top = data[0];
  return (
    <Panel
      title="What it looks at"
      actions={<span className={styles.legend}>share of total gain</span>}
    >
      <ul className={styles.features}>
        {data.map((r) => (
          <li key={r.feature} className={styles.feature}>
            <span className={styles.featureName}>{r.name}</span>
            <span className={styles.featureBar} style={{ width: `${r.share * 100}%` }} />
            <span className={styles.featureValue}>{pct1(r.share)}</span>
          </li>
        ))}
      </ul>
      <p className={styles.takeaway}>
        {top.name} carries {pct(top.share)} of the model's total gain.
      </p>
      <Numbers
        head={["Feature", "Gain", "Share"]}
        rows={data.map((r) => [r.name, r.gain.toLocaleString("en-US"), pct1(r.share)])}
      />
    </Panel>
  );
}
