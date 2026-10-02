import { memo } from "react";
import type { Review, Snapshot } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { ItemIcon } from "../../components/ItemIcon";
import { Panel } from "../../components/Panel";
import { Tooltip } from "../../components/Tooltip";
import { formatTime } from "../../lib/format";
import { respawnAt } from "./board/minimapModel";
import { buildScoreboard, type Row, type TeamHeader } from "./board/boardModel";
import styles from "./Scoreboard.module.css";

type Props = { review: Review; snapshot: Snapshot; t: number };

function Pair({ label, value }: { label: string; value: string | number }) {
  return (
    <span className={styles.pair}>
      <span className={styles.pairLabel}>{label}</span> <span className="num">{value}</span>
    </span>
  );
}

function Header({ h }: { h: TeamHeader }) {
  const dragons = <Pair label="Dragons" value={h.dragonCount} />;
  return (
    <div className={styles.header}>
      <span className={styles.teamName}>
        <span className={`${styles.mark} ${styles[h.team]}`} aria-hidden="true" />
        {h.label}
      </span>
      <Pair label="Kills" value={h.kills} />
      <Pair label="Gold" value={h.gold} />
      <Pair label="Towers" value={h.towers} />
      {h.dragonTypes.length > 0 ? (
        <Tooltip content={h.dragonTypes.join(", ")}>
          <span tabIndex={0}>{dragons}</span>
        </Tooltip>
      ) : (
        dragons
      )}
      {h.soul && <span className={styles.pairLabel}>{h.soul}</span>}
      {h.buff && <Pair label={h.buff.label} value={h.buff.time} />}
      {h.lead && <span className={`${styles.lead} num`}>{h.lead}</span>}
    </div>
  );
}

function PlayerRow({ row, version }: { row: Row; version: string }) {
  const { player, state } = row;
  return (
    <tr className={`${styles.row} ${row.dead ? styles.dead : ""} ${player.is_me ? styles.me : ""}`}>
      <td className={styles.champ}>
        <ChampIcon
          version={version}
          champion={player.champion}
          name={player.champion_name}
          size={24}
        />
      </td>
      <td className={styles.name} title={player.riot_id}>
        {player.riot_id.split("#")[0]}
      </td>
      <td className={`${styles.num} ${row.dead ? styles.deadText : ""} num`}>
        {row.deadText ?? state.level}
      </td>
      <td className={`${styles.num} ${styles.kda} num`}>
        {state.k} / {state.d} / {state.a}
      </td>
      <td className={`${styles.num} num`}>{state.cs}</td>
      <td className={`${styles.num} ${styles.gold} num`}>{row.gold}</td>
      <td className={styles.items}>
        {row.slots.map((id, i) => (
          <ItemIcon key={i} version={version} itemId={id} size={20} />
        ))}
      </td>
    </tr>
  );
}

function ScoreboardView({ review, snapshot, t }: Props) {
  const blocks = buildScoreboard(review, snapshot, t);
  const version = review.match.ddragon_version;
  return (
    <Panel title={`Scoreboard at ${formatTime(snapshot.t)}`} className={styles.panel}>
      {blocks.map((b) => (
        <section key={b.header.team} className={styles.team}>
          <Header h={b.header} />
          <table className={styles.table}>
            <tbody>
              {b.rows.map((r) => (
                <PlayerRow key={r.player.participant_id} row={r} version={version} />
              ))}
            </tbody>
          </table>
        </section>
      ))}
    </Panel>
  );
}

/** Whole seconds still on each death timer; the only thing besides the snapshot that changes the table. */
const timers = ({ snapshot, t }: Props) =>
  snapshot.players.map((p) => Math.ceil(respawnAt(p, t, snapshot))).join(",");

/**
 * Re-renders when the review or snapshot changes, or a death timer ticks over; not on every
 * scrubber tick.
 */
export const Scoreboard = memo(
  ScoreboardView,
  (a, b) => a.review === b.review && a.snapshot === b.snapshot && timers(a) === timers(b),
);
