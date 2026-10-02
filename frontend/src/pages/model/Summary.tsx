import { formatMonthDay } from "../../lib/format";
import { pct, type ModelView } from "./metrics";
import styles from "./model.module.css";

function joinPatches(patches: string[]): string {
  if (patches.length === 1) return `patch ${patches[0]}`;
  const head = patches.slice(0, -1).join(", ");
  return `patches ${head} and ${patches[patches.length - 1]}`;
}

const N = ({ children }: { children: string }) => <span className={styles.strong}>{children}</span>;

/** The model's numbers in words; each sentence is left out when its data is missing. */
export function Summary({ view }: { view: ModelView }) {
  const { trainedAt, games, patches, accuracyAt10, nearest70, logLoss, baselineLogLoss } = view;
  return (
    <p className={styles.summary}>
      {trainedAt && (
        <>
          Trained <N>{formatMonthDay(trainedAt)}</N>
          {games !== null && (
            <>
              {" "}
              on <N>{games.toLocaleString("en-US")}</N> games
            </>
          )}
          {patches.length > 0 && <> from {joinPatches(patches)}</>}.{" "}
        </>
      )}
      {accuracyAt10 !== null && (
        <>
          At 10 minutes it picks the winner <N>{pct(accuracyAt10)}</N> of the time.{" "}
        </>
      )}
      {nearest70 && (
        <>
          When it says <N>{pct(nearest70.predicted)}</N>, teams won <N>{pct(nearest70.actual)}</N>{" "}
          of the time.{" "}
        </>
      )}
      {logLoss !== null && baselineLogLoss !== null && (
        <>
          Log loss <N>{logLoss.toFixed(3)}</N> (baseline {baselineLogLoss.toFixed(3)}).
        </>
      )}
    </p>
  );
}
