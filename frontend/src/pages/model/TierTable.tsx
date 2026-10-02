import { Panel } from "../../components/Panel";
import { pct1, tierName, type TierRow } from "./metrics";
import styles from "./model.module.css";

/** Test results per tier; the player's tier is marked. */
export function TierTable({ rows, yourTier }: { rows: TierRow[]; yourTier: string }) {
  return (
    <Panel title="By tier">
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.left}>Tier</th>
            <th>Test games</th>
            <th>Accuracy</th>
            <th>Log loss</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const mine = r.tier.toUpperCase() === yourTier.toUpperCase();
            return (
              <tr key={r.tier} className={mine ? styles.mine : undefined}>
                <td className={styles.left} aria-current={mine ? "true" : undefined}>
                  {tierName(r.tier)}
                  {mine && <span className={styles.youTag}>your tier</span>}
                </td>
                <td className="num">{r.games.toLocaleString("en-US")}</td>
                <td className="num">{pct1(r.accuracy)}</td>
                <td className="num">{r.logLoss.toFixed(3)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
