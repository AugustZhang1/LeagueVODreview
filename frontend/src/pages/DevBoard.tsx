import { useMemo, useState } from "react";
import { makeReview } from "../mocks/makeReview";
import { formatTime } from "../lib/format";
import { Minimap } from "./review/Minimap";
import { Scoreboard } from "./review/Scoreboard";
import styles from "./DevBoard.module.css";

/** Minimap and scoreboard on the mock review, with a slider for the selected time. */
export default function DevBoard() {
  const review = useMemo(() => makeReview(), []);
  const [t, setT] = useState(1330);
  const last = review.snapshots.length - 1;
  const snapshot = review.snapshots[Math.min(last, Math.floor(t / 15))];
  return (
    <div className={styles.page}>
      <label className={styles.slider}>
        Time <span className="num">{formatTime(t)}</span>
        <input
          type="range"
          min={0}
          max={review.match.duration_s}
          step={1}
          value={t}
          onChange={(e) => setT(Number(e.target.value))}
        />
      </label>
      <div className={styles.boards}>
        <div>
          <Minimap review={review} snapshot={snapshot} t={t} />
        </div>
        <Scoreboard review={review} snapshot={snapshot} t={t} />
      </div>
    </div>
  );
}
