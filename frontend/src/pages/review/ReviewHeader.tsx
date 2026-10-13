import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";
import type { Player, Review } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { GradeBadge } from "../../components/GradeBadge";
import { ScoreBadge } from "../../components/ScoreBadge";
import { formatFullDate, formatRelative, formatTime, formatWinChance } from "../../lib/format";
import { GRADES } from "../../lib/grades";
import styles from "./ReviewHeader.module.css";

const ROLE_NAMES = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MIDDLE: "Mid",
  BOTTOM: "Bottom",
  UTILITY: "Support",
} as const;

function Facts({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <span className={styles.fact} title={title}>
      <span className={styles.factLabel}>{label}</span>
      <span className="num">{value}</span>
    </span>
  );
}

export function notesFor(review: Review): string[] {
  const { match } = review;
  const notes: string[] = [];
  if (match.model.kind === "stub") notes.push("Placeholder model");
  if (!match.patch_in_training) {
    notes.push(`Patch ${match.patch} is outside the patches the model was trained on`);
  }
  if (match.tier_note) notes.push(match.tier_note);
  return notes;
}

export type Comeback = { kind: "comeback" | "thrown"; p: number; t: number };

/**
 * A win that dipped below 20% or a loss that rose above 80%, with the point where it happened.
 * The last curve point is the result, so it's left out.
 */
export function comebackOf(review: Review): Comeback | null {
  const points = review.curve.slice(0, -1);
  if (points.length === 0) return null;
  const { result } = review.match;
  if (result === "win") {
    const low = points.reduce((a, b) => (b.p < a.p ? b : a));
    if (low.p < 0.2) return { kind: "comeback", p: low.p, t: low.t };
  } else if (result === "loss") {
    const high = points.reduce((a, b) => (b.p > a.p ? b : a));
    if (high.p > 0.8) return { kind: "thrown", p: high.p, t: high.t };
  }
  return null;
}

/**
 * My place among the players by score (1 is best). Ties go to the lower participant id,
 * and a player with no score ranks below everyone who has one. Null when I have no score.
 */
export function scoreRank(players: Player[], me: Player): number | null {
  const mine = me.score;
  if (mine == null) return null;
  const ahead = players.filter((p) => {
    const s = p.score ?? -1;
    return s > mine || (s === mine && p.participant_id < me.participant_id);
  });
  return ahead.length + 1;
}

export function ReviewHeader({ review }: { review: Review }) {
  const { match, summary } = review;
  const me = review.players.find((p) => p.is_me) ?? review.players[0];
  const win = match.result === "win";
  const [name, tag] = me.riot_id.split("#");
  const gamesHref = `/p/${encodeURIComponent(match.platform.toLowerCase())}/${encodeURIComponent(name)}/${encodeURIComponent(tag ?? "")}`;
  const surrender = match.surrender
    ? win
      ? ", enemy surrendered"
      : ", your team surrendered"
    : "";
  const notes = notesFor(review);
  const comeback = comebackOf(review);

  return (
    <header className={styles.header}>
      <Link to={gamesHref} className={styles.back}>
        <ChevronLeft size={16} aria-hidden="true" />
        Games
      </Link>
      <ChampIcon
        version={match.ddragon_version}
        champion={me.champion}
        name={me.champion_name}
        size={42}
      />
      <div className={styles.body}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>
            <span className={win ? styles.win : styles.loss}>{win ? "Victory" : "Defeat"}</span> as{" "}
            {me.champion_name}
            {surrender}
          </h1>
          <div className={styles.summary}>
            <ScoreBadge
              score={me.score}
              badge={me.badge}
              rank={scoreRank(review.players, me)}
              label="Score"
              size="md"
            />
            <span className={styles.grades}>
              <span className={styles.label}>Your grades</span>
              {GRADES.map((g) => (
                <GradeBadge key={g} grade={g} count={summary.me[g]} />
              ))}
            </span>
          </div>
        </div>
        <div className={styles.facts}>
          <Facts label="Role" value={ROLE_NAMES[me.role]} />
          <Facts label="Length" value={formatTime(match.duration_s)} />
          <Facts label="Patch" value={match.patch} />
          <Facts
            label="Played"
            value={formatRelative(match.started_at)}
            title={formatFullDate(match.started_at)}
          />
          {comeback && (
            <Facts
              label={comeback.kind === "comeback" ? "Comeback" : "Thrown lead"}
              value={`from ${formatWinChance(comeback.p)} at ${formatTime(comeback.t)}`}
            />
          )}
        </div>
        {notes.map((n) => (
          <p key={n} className={styles.note}>
            {n}
          </p>
        ))}
      </div>
    </header>
  );
}
