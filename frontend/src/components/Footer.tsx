import { useHealth } from "../api/queries";
import { formatMonthDay } from "../lib/format";
import styles from "./Footer.module.css";

function modelLine(model: { kind: string; trained_at?: string | null; patches?: string[] | null }) {
  if (model.kind !== "trained") return "Placeholder model";
  const parts = ["Model trained"];
  if (model.trained_at) parts.push(formatMonthDay(model.trained_at));
  const patches = model.patches;
  if (patches && patches.length > 0) {
    const first = patches[0];
    const last = patches[patches.length - 1];
    parts.push(
      `on patch${first === last ? "" : "es"} ${first === last ? first : `${first}–${last}`}`,
    );
  }
  return parts.join(" ");
}

export function Footer() {
  const { data } = useHealth();
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <p className={styles.legal}>
          LeagueVODreview isn't endorsed by Riot Games and doesn't reflect the views or opinions of
          Riot Games or anyone officially involved in producing or managing Riot Games properties.
          Riot Games, and all associated properties are trademarks or registered trademarks of Riot
          Games, Inc.
        </p>
        {data && <p className={styles.model}>{modelLine(data.model)}</p>}
      </div>
    </footer>
  );
}
