import type { Moment, ObjectiveWindow } from "../../api/models";
import { Delta } from "../../components/Delta";
import { formatDelta, formatTime } from "../../lib/format";
import { capitalize } from "./curve";
import styles from "./MomentDetail.module.css";

/** How long after a window closes a moment still counts as "what happened instead". */
const AFTER_WINDOW_S = 10;

export function WindowDetail({
  window: w,
  moments,
}: {
  window: ObjectiveWindow;
  moments: Moment[];
}) {
  const taken = [...new Set(w.taken)];
  const instead = moments.filter(
    (m) => m.t_end >= w.t_start && m.t_end <= w.t_end + AFTER_WINDOW_S,
  );
  return (
    <div className={styles.detail} data-testid={`detail-${w.id}`}>
      <div className={styles.head}>
        <span className={`${styles.time} num`}>
          {formatTime(w.t_start)}–{formatTime(w.t_end)}
        </span>
        <span className={`${styles.worth} num`}>worth ~{formatDelta(w.value)}</span>
      </div>
      <h3 className={styles.title}>{w.title}</h3>
      <p className={styles.note}>{w.reason}</p>
      <div className={styles.block}>
        <h4 className={styles.heading}>Available</h4>
        <ul className={styles.events}>
          {w.options.map((o) => (
            <li key={o.what} className={styles.event}>
              <span>{capitalize(o.what)}</span>
              <span className="num">{formatDelta(o.value)}</span>
            </li>
          ))}
        </ul>
      </div>
      {w.used ? (
        <p className={styles.note}>Your team took: {taken.join(", ")}</p>
      ) : (
        <div className={styles.block}>
          <h4 className={styles.heading}>What happened instead</h4>
          {instead.length > 0 ? (
            <ul className={styles.events}>
              {instead.map((m) => (
                <li key={m.id} className={styles.event}>
                  <span className="num">{formatTime(m.t_end)}</span>
                  <span>{m.title}</span>
                  <Delta value={m.delta} />
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.note}>Your team didn't take an objective or tower in time.</p>
          )}
        </div>
      )}
    </div>
  );
}
