import type { ObjectiveWindow } from "../../api/models";
import { formatDelta } from "../../lib/format";
import { capitalize } from "./curve";
import styles from "./MomentDetail.module.css";

export function WindowDetail({ window: w }: { window: ObjectiveWindow }) {
  return (
    <div className={styles.detail} data-testid={`detail-${w.id}`}>
      <p className={styles.change}>{w.reason}</p>
      <h4 className={styles.heading}>Available</h4>
      <ul className={styles.events}>
        {w.options.map((o) => (
          <li key={o.what} className={styles.event}>
            <span>{capitalize(o.what)}</span>
            <span className="num">{formatDelta(o.value)}</span>
          </li>
        ))}
      </ul>
      <p className={styles.where}>Your team didn't take an objective or tower in time.</p>
    </div>
  );
}
