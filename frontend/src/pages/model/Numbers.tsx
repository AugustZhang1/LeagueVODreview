import type { ReactNode } from "react";
import styles from "./model.module.css";

type Props = { head: string[]; rows: ReactNode[][] };

/** The same data as the chart above it, as a plain table. */
export function Numbers({ head, rows }: Props) {
  return (
    <details className={styles.numbers}>
      <summary>Numbers</summary>
      <table className={styles.table}>
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={h} className={i === 0 ? styles.left : undefined}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, r) => (
            <tr key={r}>
              {cells.map((c, i) => (
                <td key={i} className={i === 0 ? styles.left : "num"}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
