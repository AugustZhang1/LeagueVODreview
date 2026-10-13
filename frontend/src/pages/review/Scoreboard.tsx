import { memo } from "react";
import type { Player, Review, Snapshot } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { ItemIcon } from "../../components/ItemIcon";
import { Panel } from "../../components/Panel";
import { ScoreBadge } from "../../components/ScoreBadge";
import { Tooltip } from "../../components/Tooltip";
import { formatTime } from "../../lib/format";
import { respawnAt } from "./board/minimapModel";
import {
  buildObjectives,
  buildScoreboard,
  formatScoreParts,
  type Row,
  type TeamHeader,
} from "./board/boardModel";
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
      <span className={`${styles.teamName} ${styles[h.team]}`}>{h.label}</span>
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
      {h.grubs > 0 && <Pair label="Grubs" value={h.grubs} />}
      {h.heralds > 0 && <Pair label="Herald" value={h.heralds} />}
      {h.barons > 0 && <Pair label="Baron" value={h.barons} />}
      {h.soul && <span className={styles.pairLabel}>{h.soul}</span>}
      {h.buff && <Pair label={h.buff.label} value={h.buff.time} />}
      {h.lead && (
        <span className={styles.lead}>
          <Pair label="Gold lead" value={h.lead} />
        </span>
      )}
    </div>
  );
}

/** The score for the whole game, with the parts it came from on hover. */
function ScoreCell({ player }: { player: Player }) {
  const badge = <ScoreBadge score={player.score} badge={player.badge} size="sm" />;
  if (player.score == null) return badge;
  const parts = formatScoreParts(player.score_parts);
  return (
    <Tooltip
      content={
        <>
          Score for the whole game, 0-10
          {parts && (
            <>
              <br />
              {parts}
            </>
          )}
        </>
      }
    >
      <span tabIndex={0}>{badge}</span>
    </Tooltip>
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
        <div className={styles.nameInner}>
          <span className={styles.nameText}>{player.riot_id.split("#")[0]}</span>
          {player.is_me && <span className={styles.you}>you</span>}
        </div>
      </td>
      <td className={styles.score}>
        <ScoreCell player={player} />
      </td>
      <td className={`${styles.level} ${row.dead ? styles.deadText : ""} num`}>
        {row.deadText ?? state.level}
      </td>
      <td className={`${styles.num} ${styles.kda} num`}>
        {state.k} / {state.d} / {state.a}
      </td>
      <td className={`${styles.num} ${styles.cs} num`}>{state.cs}</td>
      <td className={`${styles.num} ${styles.gold} num`}>{row.gold}</td>
      <td className={styles.items}>
        {row.slots.map((id, i) => (
          <ItemIcon key={i} version={version} itemId={id} size={18} />
        ))}
      </td>
    </tr>
  );
}

function TeamsView({ review, snapshot, t }: Props) {
  const blocks = buildScoreboard(review, snapshot, t);
  const version = review.match.ddragon_version;
  return blocks.map((b) => (
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
  ));
}

/** Whole seconds still on each death timer; the only thing besides the snapshot that changes the table. */
const timers = ({ snapshot, t }: Props) =>
  snapshot.players.map((p) => Math.ceil(respawnAt(p, t, snapshot))).join(",");

/**
 * Re-renders when the review or snapshot changes, or a death timer ticks over; not on every
 * scrubber tick.
 */
const Teams = memo(
  TeamsView,
  (a, b) => a.review === b.review && a.snapshot === b.snapshot && timers(a) === timers(b),
);

/** The objective timers tick every second, so they sit outside the memoized table. */
export function Scoreboard({ review, snapshot, t }: Props) {
  const objectives = buildObjectives(snapshot, t);
  return (
    <Panel
      title={`Scoreboard at ${formatTime(snapshot.t)}`}
      actions={
        objectives && (
          <div className={styles.objectives}>
            <Pair label={objectives.dragon.label} value={objectives.dragon.time} />
            <Pair label={objectives.pit.label} value={objectives.pit.time} />
          </div>
        )
      }
      className={styles.panel}
    >
      <Teams review={review} snapshot={snapshot} t={t} />
    </Panel>
  );
}
