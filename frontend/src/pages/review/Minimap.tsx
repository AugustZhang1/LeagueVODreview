import { Panel } from "../../components/Panel";
import type { Review, Snapshot } from "../../api/models";
import styles from "./Placeholder.module.css";

/** Placeholder; the real minimap replaces this file. */
export function Minimap({ t }: { review: Review; snapshot: Snapshot; t: number }) {
  return (
    <Panel title="Minimap">
      <div className={styles.square} data-t={t} />
    </Panel>
  );
}
