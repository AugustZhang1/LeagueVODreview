import { useState } from "react";
import { initials } from "../lib/ddragon";
import styles from "./GameImage.module.css";

type Props = {
  src: string | null;
  label: string;
  size: number;
  round?: boolean;
  ring?: "ally" | "enemy" | "you";
  fallbackText?: string;
};

/** Fixed-size Data Dragon image; falls back to a `--surface-2` square with two letters. */
export function GameImage({ src, label, size, round = false, ring, fallbackText }: Props) {
  const [failed, setFailed] = useState<string | null>(null);
  const style = { width: size, height: size, fontSize: Math.max(10, Math.round(size * 0.4)) };
  const cls = [styles.frame, round ? styles.round : "", ring ? styles[ring] : ""]
    .filter(Boolean)
    .join(" ");
  if (!src || failed === src) {
    return (
      <span className={`${cls} ${styles.fallback}`} style={style} role="img" aria-label={label}>
        {src ? (fallbackText ?? initials(label)) : null}
      </span>
    );
  }
  return (
    <img
      className={cls}
      style={style}
      src={src}
      alt={label}
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(src)}
    />
  );
}
