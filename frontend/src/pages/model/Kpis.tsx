import { pct, type ModelView } from "./metrics";
import styles from "./model.module.css";

const MISSING = "–";

function Kpi({ value, label }: { value: string; label: string }) {
  return (
    <div className={styles.kpi}>
      <div className={styles.kpiValue}>{value}</div>
      <div className={styles.kpiLabel}>{label}</div>
    </div>
  );
}

/** The four headline numbers from the metrics. A number that is missing shows a dash. */
export function Kpis({ view }: { view: ModelView }) {
  const { games, patches, accuracyAt10, nearest70, logLoss, baselineLogLoss } = view;
  const patchRange =
    patches.length > 1 ? `${patches[0]} to ${patches[patches.length - 1]}` : patches[0];
  return (
    <div className={styles.kpis}>
      <Kpi
        value={games === null ? MISSING : games.toLocaleString("en-US")}
        label={patchRange ? `games trained on, patches ${patchRange}` : "games trained on"}
      />
      <Kpi
        value={accuracyAt10 === null ? MISSING : pct(accuracyAt10)}
        label="picks the winner at 10:00"
      />
      <Kpi
        value={nearest70 ? `${pct(nearest70.predicted)} → ${pct(nearest70.actual)}` : MISSING}
        label={
          nearest70
            ? `says ${pct(nearest70.predicted)}, teams won ${pct(nearest70.actual)}`
            : "calibration near 70%"
        }
      />
      <Kpi
        value={logLoss === null ? MISSING : logLoss.toFixed(3)}
        label={
          baselineLogLoss === null
            ? "log loss"
            : `log loss (baseline ${baselineLogLoss.toFixed(3)})`
        }
      />
    </div>
  );
}
