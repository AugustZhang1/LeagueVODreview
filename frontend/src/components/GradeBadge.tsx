import { gradeName, type Grade } from "../lib/grades";
import styles from "./GradeBadge.module.css";

type Props = { grade: Grade; count?: number };

const TONES: Record<Grade, string> = {
  "!!": styles.great,
  "!": styles.good,
  "?": styles.mistake,
  "??": styles.blunder,
};

/** Glyph badge. Screen readers hear the grade's name instead of the glyph. */
export function GradeBadge({ grade, count }: Props) {
  const name = gradeName(grade);
  const cls = `${styles.badge} ${TONES[grade]}`;
  const label = count === undefined ? name : `${name}, ${count}`;
  return (
    <span role="img" aria-label={label} className={cls}>
      <span aria-hidden="true">{grade}</span>
      {count !== undefined && (
        <span aria-hidden="true" className={styles.count}>
          {count}
        </span>
      )}
    </span>
  );
}
