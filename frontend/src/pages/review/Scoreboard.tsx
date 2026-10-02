import { Panel } from "../../components/Panel";
import { formatTime } from "../../lib/format";
import type { Review, Snapshot } from "../../api/models";
import styles from "./Placeholder.module.css";

/** Placeholder; the real scoreboard replaces this file. */
export function Scoreboard({ snapshot }: { review: Review; snapshot: Snapshot }) {
  return (
    <Panel title={`Scoreboard at ${formatTime(snapshot.t)}`}>
      <div className={styles.tall} />
    </Panel>
  );
}
