import { formatDelta } from "../lib/format";
import styles from "./Delta.module.css";

type Props = { value: number; muted?: boolean };

/** Change in win chance (a fraction). Blue when positive, red when negative; the sign is always shown. */
export function Delta({ value, muted = false }: Props) {
  const whole = Math.round(value * 100);
  const tone = muted || whole === 0 ? styles.muted : whole > 0 ? styles.up : styles.down;
  return <span className={`${styles.delta} ${tone} num`}>{formatDelta(value)}</span>;
}
