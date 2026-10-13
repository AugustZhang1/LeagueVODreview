import { Fragment, type ReactNode } from "react";
import type { GameEvent, Moment, Player, Review } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { Delta } from "../../components/Delta";
import { GradeBadge } from "../../components/GradeBadge";
import { formatTime, formatWinChance } from "../../lib/format";
import { capitalize } from "./curve";
import styles from "./MomentDetail.module.css";

/** Under this share of my team's fight damage, I get a "Low damage" tag. */
const LOW_SHARE = 0.15;

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

  const drivers = moment.drivers ?? [];
  const maxChange = Math.max(1e-6, ...drivers.map((d) => Math.abs(d.change)));
  const damage = moment.damage ?? [];
  const goldSwing = moment.kill_gold ?? 0;
  const maxDealt = Math.max(1, ...damage.map((d) => d.dealt));
  const teamDealt = (side: Player["team"]) =>
    damage.reduce((sum, d) => (byId.get(d.participant_id)?.team === side ? sum + d.dealt : sum), 0);
  const allyDealt = damage.filter((d) => byId.get(d.participant_id)?.team === "ally");
  const mine = allyDealt.find((d) => byId.get(d.participant_id)?.is_me);
  const share = mine ? mine.dealt / Math.max(1, teamDealt("ally")) : 0;
  let partTag = "";
  if (mine && allyDealt.length > 1) {
    if (mine.dealt === Math.max(...allyDealt.map((d) => d.dealt)))
      partTag = "Top damage on your team";
    else if (share < LOW_SHARE) partTag = "Low damage";
  }

  const me = review.players.find((p) => p.is_me);
  const myCredit = me
    ? moment.credit?.find((c) => c.participant_id === me.participant_id)
    : undefined;
  const myShare = myCredit?.share;

  const whole = Math.round(moment.delta * 100);
  const tone = whole > 0 ? styles.up : whole < 0 ? styles.down : "";

  return (
    <div className={styles.detail} data-testid={`detail-${moment.id}`}>
      <div className={styles.head}>
        {moment.grade && <GradeBadge grade={moment.grade} />}
        <span className={`${styles.time} num`}>{formatTime(moment.t_end)}</span>
        {moment.zone && <span className={styles.where}>{capitalize(moment.zone)}</span>}
        <span className={styles.change}>
          <span className={`${styles.shift} ${tone} num`}>
            {formatWinChance(moment.p_before)} to {formatWinChance(moment.p_after)}
          </span>
          <Delta value={moment.delta} />
        </span>
      </div>
      <h3 className={styles.title}>{moment.title}</h3>
      {drivers.length > 0 && (
        <div className={styles.why}>
          <h4 className={styles.heading}>Why</h4>
          <div className={styles.rows}>
            {drivers.map((d) => (
              <div
                key={d.label}
                className={`${styles.row} ${styles.driver}`}
                data-testid="driver-row"
              >
                <span>{d.label}</span>
                <span className={styles.track}>
                  <span
                    className={`${styles.bar} ${d.change > 0 ? styles.ally : styles.enemy}`}
                    style={{ width: `${(Math.abs(d.change) / maxChange) * 100}%` }}
                  />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
      {moment.tip && (
        <p className={styles.tip} data-testid="tip">
          <span className={styles.tipLabel}>Better play:</span> {moment.tip}
        </p>
      )}
      {myShare != null && Math.round(myShare * 1000) !== 0 && (
        <p className={styles.share} data-testid="your-share">
          Your share:{" "}
          <span className={`${styles.shareDelta} ${myShare > 0 ? styles.up : styles.down} num`}>
            {myShare > 0 ? "+" : "−"}
            {Math.abs(myShare * 100).toFixed(1)}%
          </span>
        </p>
      )}
      {moment.t_end < 300 && (
        <p className={styles.early}>Early game: the model is least sure in the first 5 minutes.</p>
      )}
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
          {mine && (
            <p className={styles.totals} data-testid="your-part">
              You <span className="num">{mine.dealt.toLocaleString("en-US")}</span>,{" "}
              {Math.round(share * 100)}% of your team's
              {partTag && <span className={styles.partTag}> · {partTag}</span>}
            </p>
          )}
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
