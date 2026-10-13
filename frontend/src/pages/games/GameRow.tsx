import { Link } from "react-router-dom";
import type { GameSummary, Role } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { GradeBadge } from "../../components/GradeBadge";
import { ScoreBadge } from "../../components/ScoreBadge";
import { Skeleton } from "../../components/Skeleton";
import { formatFullDate, formatKda, formatRelative, formatTime } from "../../lib/format";
import type { Grade } from "../../lib/grades";
import styles from "./GameRow.module.css";

const ROLE_LABEL: Record<Role, string> = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MIDDLE: "Mid",
  BOTTOM: "Bottom",
  UTILITY: "Support",
};

const RESULT_LABEL = { win: "Victory", loss: "Defeat", remake: "Remake" } as const;

/** The grade counts shown on a row. "!" (good) is left off to keep the row short. */
const SHOWN_GRADES: Grade[] = ["!!", "?", "??"];

/** Games cached before the field existed only have the patch. */
const ddragonVersion = (game: GameSummary) => game.ddragon_version || `${game.patch}.1`;

/** (Kills + assists) / deaths, with no deaths counted as one. */
const kdaRatio = (game: GameSummary) => ((game.k + game.a) / Math.max(game.d, 1)).toFixed(1);

/** Win chance over the game from the player's side: blue when they won, red when they lost. */
function Spark({ values, win }: { values: number[]; win: boolean }) {
  const w = 100;
  const h = 28;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - (v / 100) * h}`)
    .join(" ");
  return (
    <svg
      className={styles.sparkSvg}
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Win chance over the game"
    >
      <line
        className={styles.midline}
        x1={0}
        x2={w}
        y1={h / 2}
        y2={h / 2}
        vectorEffect="non-scaling-stroke"
      />
      <polyline
        className={win ? styles.lineWin : styles.lineLoss}
        points={points}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function GameRow({ game }: { game: GameSummary }) {
  const remake = game.result === "remake";
  const grades = game.grades;
  const tone =
    game.result === "win" ? styles.win : game.result === "loss" ? styles.loss : styles.muted;
  const cls = `${styles.row} ${tone}`;
  const content = (
    <>
      <ChampIcon version={ddragonVersion(game)} champion={game.champion} size={32} />
      <span className={styles.result}>
        {RESULT_LABEL[game.result]}
        <span className={styles.role}>{remake || !game.role ? "" : ROLE_LABEL[game.role]}</span>
      </span>
      <ScoreBadge score={game.score} badge={game.badge} rank={game.score_rank} />
      <span className={styles.chart}>
        {game.spark ? (
          <Spark values={game.spark} win={game.result === "win"} />
        ) : (
          !remake && <span className={styles.none}>Not reviewed</span>
        )}
      </span>
      <span className={styles.kda}>
        <span className={styles.kdaLine}>{formatKda(game.k, game.d, game.a)}</span>
        {!remake && <span className={styles.ratio}>{kdaRatio(game)} KDA</span>}
      </span>
      <span className={styles.cs}>{game.cs} CS</span>
      <span className={styles.time}>
        <span>{formatTime(game.duration_s)}</span>
        <span className={styles.date} title={formatFullDate(game.started_at)}>
          {formatRelative(game.started_at)}
        </span>
      </span>
      <span className={styles.grades}>
        {grades &&
          SHOWN_GRADES.map(
            (g) => grades[g] > 0 && <GradeBadge key={g} grade={g} count={grades[g]} />,
          )}
      </span>
      <span className={styles.tagCell}>
        {!remake &&
          (game.reviewed ? (
            <span className={`${styles.tag} ${styles.done}`}>Reviewed</span>
          ) : (
            <span className={`${styles.tag} ${styles.todo}`}>Review</span>
          ))}
      </span>
    </>
  );
  if (remake) {
    return <li className={cls}>{content}</li>;
  }
  return (
    <li>
      <Link
        className={`${cls} ${styles.link}`}
        to={`/review/${encodeURIComponent(game.match_id)}?p=${game.participant_id}`}
      >
        {content}
      </Link>
    </li>
  );
}

/** Same cells as GameRow, so the skeleton hides and shows the same columns. */
export function GameRowSkeleton() {
  return (
    <li className={styles.row} aria-hidden="true">
      <Skeleton width={32} height={32} round />
      <Skeleton width={56} height={14} />
      <Skeleton width={108} height={32} />
      <span className={styles.chart}>
        <Skeleton height={14} />
      </span>
      <Skeleton width={72} height={14} />
      <span className={styles.cs}>
        <Skeleton width={44} height={14} />
      </span>
      <span className={styles.time}>
        <Skeleton width={40} height={14} />
      </span>
      <span className={styles.grades}>
        <Skeleton width={72} height={20} />
      </span>
      <span className={styles.tagCell}>
        <Skeleton width={76} height={22} />
      </span>
    </li>
  );
}
