import styles from "./ScoreBadge.module.css";

type Props = {
  score: number | null | undefined;
  badge?: "mvp" | "ace" | null;
  rank?: number | null;
  size?: "md" | "sm";
  label?: string;
};

/** Ranks run 1 to 10, so only the first three need their own suffix. */
const SUFFIX: Record<number, string> = { 1: "st", 2: "nd", 3: "rd" };
const ordinal = (n: number) => `${n}${SUFFIX[n] ?? "th"}`;

function band(score: number): string {
  if (score >= 8) return styles.great;
  if (score >= 6) return styles.good;
  if (score >= 4) return styles.neutral;
  return styles.blunder;
}

/**
 * A score out of 10 in a tinted box, with an optional MVP or ACE tag and, on md,
 * the rank in the game ("Score, 1st of 10").
 */
export function ScoreBadge({ score, badge, rank, size = "md", label }: Props) {
  // Round first, so the colour always matches the number shown (7.96 shows as 8.0, so it's great).
  const value = score == null ? null : Math.round(score * 10) / 10;
  const text = value === null ? "–" : value.toFixed(1);
  const tone = value === null ? styles.none : band(value);
  const cls = [styles.box, size === "sm" ? styles.sm : styles.md, tone].join(" ");
  const line =
    size === "md" && rank != null ? `${label ? `${label}, ` : ""}${ordinal(rank)} of 10` : null;
  return (
    <span className={`${styles.wrap} ${size === "sm" ? styles.wrapSm : ""}`}>
      <span
        role="img"
        aria-label={value === null ? "No score" : `Score ${text} out of 10`}
        className={cls}
      >
        <span aria-hidden="true">{text}</span>
      </span>
      {(badge || line) && (
        <span className={styles.side}>
          {badge && <span className={styles.tag}>{badge.toUpperCase()}</span>}
          {line && <small className={styles.line}>{line}</small>}
        </span>
      )}
    </span>
  );
}
