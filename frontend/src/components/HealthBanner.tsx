import { useHealth } from "../api/queries";
import styles from "./HealthBanner.module.css";

// The expired message keeps the "Paste..." sentence right after its lead, so the
// text reads the same as the games page's error box.
const MESSAGES = {
  expired: {
    lead: "Riot API key expired.",
    text: "Paste a new one after RIOT_API_KEY= in .env; it's picked up within a minute. New searches and reviews are paused. Reviewed games still open.",
  },
  missing: {
    lead: "Riot API key missing.",
    text: "Paste one after RIOT_API_KEY= in .env; it's picked up within a minute.",
  },
} as const;

export function HealthBanner() {
  const { data } = useHealth();
  if (!data || data.riot_key === "ok") return null;
  const message = MESSAGES[data.riot_key];
  return (
    <div role="alert" className={styles.banner}>
      <p className={styles.inner}>
        <strong className={styles.lead}>{message.lead}</strong> {message.text}
      </p>
    </div>
  );
}
