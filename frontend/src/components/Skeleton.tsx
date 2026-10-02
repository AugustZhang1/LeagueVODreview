import type { CSSProperties } from "react";
import styles from "./Skeleton.module.css";

type Props = { width?: number | string; height?: number | string; round?: boolean };

/** A block at its final size, so nothing shifts when the data arrives. */
export function Skeleton({ width = "100%", height = 16, round = false }: Props) {
  const style: CSSProperties = { width, height };
  return (
    <span
      aria-hidden="true"
      className={round ? `${styles.skeleton} ${styles.round}` : styles.skeleton}
      style={style}
    />
  );
}
