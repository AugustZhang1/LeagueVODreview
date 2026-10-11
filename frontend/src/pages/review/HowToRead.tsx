import { GradeBadge } from "../../components/GradeBadge";
import { GRADES, gradeName, type Grade } from "../../lib/grades";
import styles from "./HowToRead.module.css";

const RANGES: Record<Grade, string> = {
  "!!": "+10% or more",
  "!": "+5%",
  "?": "−5%",
  "??": "−10% or worse",
};

/** What the header's numbers mean, collapsed until asked for. */
export function HowToRead() {
  return (
    <details className={styles.guide}>
      <summary>How to read this</summary>
      <ul className={styles.list}>
        <li>
          Win chance is the model's estimate of your team's chance to win at that moment, from games
          at your rank. It's not a prediction of this game.
        </li>
        <li>
          Grades compare the win chance from just before a moment to just after it:
          <ul className={styles.grades}>
            {GRADES.map((g) => (
              <li key={g} className={styles.grade}>
                <GradeBadge grade={g} />
                {gradeName(g)} ({RANGES[g]})
              </li>
            ))}
          </ul>
        </li>
        <li>
          "Miss" rows are a stretch when the enemy was weak (their jungler or 2+ players dead) and
          an objective or tower was up. "worth ~+7%" is how much your team's win chance would have
          gone up by taking the best option. "Used" rows are the same, when your team took something
          in time.
        </li>
        <li>The model is least sure in the first 5 minutes.</li>
      </ul>
    </details>
  );
}
