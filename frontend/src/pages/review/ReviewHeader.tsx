import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";
import type { GradeCounts, Moment, Review } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { Delta } from "../../components/Delta";
import { GradeBadge } from "../../components/GradeBadge";
import { formatFullDate, formatRelative, formatTime, formatWinChance } from "../../lib/format";
import { GRADES } from "../../lib/grades";
import { momentEnd } from "./curve";
import { HowToRead } from "./HowToRead";
import { TopMistakes } from "./TopMistakes";
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

function Grades({ label, counts }: { label: string; counts: GradeCounts }) {
  return (
    <span className={styles.group}>
      <span className={styles.factLabel}>{label}</span>
      {GRADES.map((g) => (
        <GradeBadge key={g} grade={g} count={counts[g]} />
      ))}
    </span>
  );
}

type Props = {
  review: Review;
  participantId: number;
  /** Jumps to a moment (the biggest swing). */
  onJump: (m: Moment) => void;
};

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

export function ReviewHeader({ review, participantId, onJump }: Props) {
  const { match, summary } = review;
  const me = review.players.find((p) => p.is_me) ?? review.players[0];
  const win = match.result === "win";
  const biggest = review.moments.find((m) => m.id === summary.biggest_id);
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
      <ChampIcon
        version={match.ddragon_version}
        champion={me.champion}
        name={me.champion_name}
        size={48}
      />
      <div className={styles.body}>
        <div className={styles.titleRow}>
          <h1 className={styles.title}>
            <span className={win ? styles.win : styles.loss}>{win ? "Victory" : "Defeat"}</span> as{" "}
            {me.champion_name}
            {surrender}
          </h1>
          {notes.map((n) => (
            <p key={n} className={styles.note}>
              {n}
            </p>
          ))}
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
          <Grades label="You" counts={summary.me} />
          <Grades label="Team" counts={summary.team} />
          {biggest && (
            <span className={styles.fact}>
              <span className={styles.factLabel}>Biggest swing</span>
              <a
                className={styles.link}
                href={`/review/${encodeURIComponent(match.match_id)}?p=${participantId}&t=${momentEnd(biggest, match.duration_s)}`}
                onClick={(e) => {
                  e.preventDefault();
                  onJump(biggest);
                }}
              >
                <span className="num">{formatTime(biggest.t_end)}</span>
                <Delta value={biggest.delta} />
              </a>
            </span>
          )}
          {comeback && (
            <Facts
              label={comeback.kind === "comeback" ? "Comeback" : "Thrown lead"}
              value={`from ${formatWinChance(comeback.p)} at ${formatTime(comeback.t)}`}
            />
          )}
        </div>
        <TopMistakes review={review} participantId={participantId} onJump={onJump} />
        <HowToRead />
      </div>
      <Link to={gamesHref} className={styles.back}>
        <ChevronLeft size={16} aria-hidden="true" />
        Games
      </Link>
    </header>
  );
}
