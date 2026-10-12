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

/** Good plays ("!" or "!!") I was part of, most positive first. */
function bestOf(moments: Moment[]): Moment[] {
  return moments
    .filter((m) => m.involves_me && (m.grade === "!" || m.grade === "!!"))
    .sort((a, b) => b.delta - a.delta)
    .slice(0, MAX);
}

type Props = {
  review: Review;
  participantId: number;
  /** Jumps to a moment, like the "Biggest swing" link. */
  onJump: (m: Moment) => void;
};

function MomentLinks({
  heading,
  empty,
  moments,
  review,
  participantId,
  onJump,
}: Props & { heading: string; empty: string; moments: Moment[] }) {
  const { match } = review;
  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>{heading}</h2>
      {moments.length === 0 ? (
        <p className={styles.empty}>{empty}</p>
      ) : (
        <ul className={styles.list}>
          {moments.map((m) => (
            <li key={m.id} className={styles.item}>
              <a
                className={styles.link}
                href={`/review/${encodeURIComponent(match.match_id)}?p=${participantId}&t=${momentEnd(m, match.duration_s)}`}
                onClick={(e) => {
                  e.preventDefault();
                  onJump(m);
                }}
              >
                <span className="num">{formatTime(m.t_end)}</span>
                <span className={styles.title} title={m.title}>
                  {m.title}
                </span>
                <Delta value={m.delta} />
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function TopMistakes(props: Props) {
  return (
    <MomentLinks
      {...props}
      heading="Your biggest mistakes"
      empty="No mistakes graded against you in this game."
      moments={mistakesOf(props.review.moments)}
    />
  );
}

export function BestPlays(props: Props) {
  return (
    <MomentLinks
      {...props}
      heading="Your best plays"
      empty="No good plays graded for you in this game."
      moments={bestOf(props.review.moments)}
    />
  );
}
