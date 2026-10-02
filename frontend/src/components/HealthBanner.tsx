import { useHealth } from "../api/queries";
import styles from "./HealthBanner.module.css";

const MESSAGES = {
  expired:
    "Riot API key expired. Paste a new one after RIOT_API_KEY= in .env; it's picked up within a minute.",
  missing:
    "Riot API key missing. Paste one after RIOT_API_KEY= in .env; it's picked up within a minute.",
} as const;

export function HealthBanner() {
  const { data } = useHealth();
  if (!data || data.riot_key === "ok") return null;
  return (
    <div role="alert" className={styles.banner}>
      <p className={styles.inner}>{MESSAGES[data.riot_key]}</p>
    </div>
  );
}
