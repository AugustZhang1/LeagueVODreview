import { Fragment, type ReactNode } from "react";
import type { GameEvent, Moment, Player, Review } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { Delta } from "../../components/Delta";
import { formatWinChance } from "../../lib/format";
import { capitalize } from "./curve";
import styles from "./MomentDetail.module.css";

function objective(ev: GameEvent): string {
  const d = ev.detail ? `${ev.detail} ` : "";
  switch (ev.kind) {
    case "dragon":
      return `${d}Dragon`;
    case "elder":
      return "Elder Dragon";
    case "baron":
      return "Baron";
    case "herald":
      return "Rift Herald";
    case "grubs":
      return "Void Grubs";
    case "atakhan":
      return "Atakhan";
    case "tower":
      return `${d}tower`;
    case "inhibitor":
      return `${d}inhibitor`;
    case "plate":
      return `${d}plate`;
    default:
      return ev.kind;
  }
}

function eventText(ev: GameEvent): string {
  const what = objective(ev);
  const mine = ev.team === "ally";
  if (ev.kind === "tower" || ev.kind === "inhibitor") {
    return mine ? `Destroyed ${what}` : `Lost ${what}`;
  }
  return mine ? `Took ${what}` : `Enemy took ${what}`;
}

export function MomentDetail({ moment, review }: { moment: Moment; review: Review }) {
  const byId = new Map<number, Player>(review.players.map((p) => [p.participant_id, p]));
  const version = review.match.ddragon_version;

  const champ = (id: number | undefined | null): ReactNode => {
    const p = id == null ? undefined : byId.get(id);
    if (!p) return null;
    return (
      <span className={styles.champ}>
        <ChampIcon version={version} champion={p.champion} name={p.champion_name} size={16} />
        {p.champion_name}
      </span>
    );
  };

  const damage = moment.damage ?? [];
  const goldSwing = moment.kill_gold ?? 0;
  const maxDealt = Math.max(1, ...damage.map((d) => d.dealt));
  const teamDealt = (side: Player["team"]) =>
    damage.reduce((sum, d) => (byId.get(d.participant_id)?.team === side ? sum + d.dealt : sum), 0);

  return (
    <div className={styles.detail} data-testid={`detail-${moment.id}`}>
      <p className={styles.change}>
        <span className="num">
          {formatWinChance(moment.p_before)} to {formatWinChance(moment.p_after)}
        </span>
        <Delta value={moment.delta} />
      </p>
      <p className={styles.where}>{capitalize(moment.zone)}</p>
      <ul className={styles.events}>
        {moment.events.map((ev, i) => (
          <li key={i} className={styles.event}>
            {ev.kind === "kill" ? (
              <>
                {[ev.killer, ...(ev.assists ?? [])].map((id, j) => (
                  <Fragment key={j}>
                    {j > 0 && <span className={styles.plus}>+</span>}
                    {champ(id)}
                  </Fragment>
                ))}
                <span>killed</span>
                {champ(ev.victim)}
              </>
            ) : (
              <span>{eventText(ev)}</span>
            )}
          </li>
        ))}
      </ul>
      {damage.length > 0 && (
        <div className={styles.damage}>
          <h4 className={styles.heading}>Damage</h4>
          <div className={styles.rows}>
            {damage.map((d) => {
              const p = byId.get(d.participant_id);
              if (!p) return null;
              return (
                <div
                  key={d.participant_id}
                  className={`${styles.row} ${p.is_me ? styles.me : ""}`}
                  data-testid="damage-row"
                >
                  {champ(d.participant_id)}
                  <span className={styles.track}>
                    <span
                      className={`${styles.bar} ${p.team === "ally" ? styles.ally : styles.enemy}`}
                      style={{ width: `${(d.dealt / maxDealt) * 100}%` }}
                    />
                  </span>
                  <span className={`${styles.dealt} num`}>{d.dealt.toLocaleString("en-US")}</span>
                </div>
              );
            })}
          </div>
          <p className={styles.totals}>
            Your team <span className="num">{teamDealt("ally").toLocaleString("en-US")}</span>
            {" vs "}
            enemy <span className="num">{teamDealt("enemy").toLocaleString("en-US")}</span>
          </p>
        </div>
      )}
      {goldSwing !== 0 && (
        <p className={styles.gold}>
          Kill gold:{" "}
          <span className="num">
            {goldSwing > 0 ? "+" : "−"}
            {Math.abs(goldSwing)}
          </span>
        </p>
      )}
    </div>
  );
}
