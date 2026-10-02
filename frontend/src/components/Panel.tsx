import type { ReactNode } from "react";
import styles from "./Panel.module.css";

type Props = {
  title?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children?: ReactNode;
};

/** The one panel style. Only for lists and tables. */
export function Panel({ title, actions, className, children }: Props) {
  return (
    <section className={[styles.panel, className ?? ""].filter(Boolean).join(" ")}>
      {(title || actions) && (
        <header className={styles.header}>
          {title && <h2 className={styles.title}>{title}</h2>}
          {actions && <div className={styles.actions}>{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
