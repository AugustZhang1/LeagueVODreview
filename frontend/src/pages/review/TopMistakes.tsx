import type { Moment, Review } from "../../api/models";
import { Delta } from "../../components/Delta";
import { formatTime } from "../../lib/format";
import { momentEnd } from "./curve";
import styles from "./TopMistakes.module.css";

const MAX = 3;

/** Mistakes ("?" or "??") graded against me, most negative first. */
function mistakesOf(moments: Moment[]): Moment[] {
  return moments
    .filter((m) => m.involves_me && (m.grade === "?" || m.grade === "??"))
    .sort((a, b) => a.delta - b.delta)
    .slice(0, MAX);
}

type Props = {
  review: Review;
  participantId: number;
  /** Jumps to a moment, like the "Biggest swing" link. */
  onJump: (m: Moment) => void;
};

export function TopMistakes({ review, participantId, onJump }: Props) {
  const { match } = review;
  const worst = mistakesOf(review.moments);

  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>Your biggest mistakes</h2>
      {worst.length === 0 ? (
        <p className={styles.empty}>No mistakes graded against you in this game.</p>
      ) : (
        <ul className={styles.list}>
          {worst.map((m) => (
            <li key={m.id}>
              <a
                className={styles.link}
                href={`/review/${encodeURIComponent(match.match_id)}?p=${participantId}&t=${momentEnd(m, match.duration_s)}`}
                onClick={(e) => {
                  e.preventDefault();
                  onJump(m);
                }}
              >
                <span className="num">{formatTime(m.t_end)}</span>
                <span>{m.title}</span>
                <Delta value={m.delta} />
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
