import { Check } from "lucide-react";
import { Link } from "react-router-dom";
import type { GameSummary, Role } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { Skeleton } from "../../components/Skeleton";
import { formatFullDate, formatKda, formatRelative, formatTime } from "../../lib/format";
import styles from "./GameRow.module.css";

const ROLE_LABEL: Record<Role, string> = {
  TOP: "Top",
  JUNGLE: "Jungle",
  MIDDLE: "Mid",
  BOTTOM: "Bottom",
  UTILITY: "Support",
};

const RESULT_LABEL = { win: "Victory", loss: "Defeat", remake: "Remake" } as const;

/** Games cached before the field existed only have the patch. */
const ddragonVersion = (game: GameSummary) => game.ddragon_version || `${game.patch}.1`;

export function GameRow({ game }: { game: GameSummary }) {
  const remake = game.result === "remake";
  const tone = game.result === "win" ? styles.win : game.result === "loss" ? styles.loss : "";
  const content = (
    <>
      <ChampIcon version={ddragonVersion(game)} champion={game.champion} size={32} />
      <span className={`${styles.result} ${tone}`}>{RESULT_LABEL[game.result]}</span>
      <span className={styles.role}>{remake || !game.role ? "" : ROLE_LABEL[game.role]}</span>
      <span className={`${styles.num} num`}>{formatKda(game.k, game.d, game.a)}</span>
      <span className={`${styles.num} num`}>{game.cs} CS</span>
      <span className={`${styles.num} num`}>{formatTime(game.duration_s)}</span>
      <span className={styles.date} title={formatFullDate(game.started_at)}>
        {formatRelative(game.started_at)}
      </span>
      <span className={styles.check}>
        {game.reviewed ? (
          <Check size={16} aria-label="Reviewed" role="img" />
        ) : (
          !remake && <span className={styles.open}>Review</span>
        )}
      </span>
    </>
  );
  if (remake) {
    return <li className={`${styles.row} ${styles.muted}`}>{content}</li>;
  }
  return (
    <li>
      <Link
        className={`${styles.row} ${styles.link}`}
        to={`/review/${encodeURIComponent(game.match_id)}?p=${game.participant_id}`}
      >
        {content}
      </Link>
    </li>
  );
}

export function GameRowSkeleton() {
  return (
    <li className={styles.row} aria-hidden="true">
      <Skeleton width={32} height={32} round />
      <Skeleton width={56} height={14} />
      <Skeleton width={48} height={14} />
      <Skeleton width={72} height={14} />
      <Skeleton width={48} height={14} />
      <Skeleton width={40} height={14} />
      <Skeleton width={80} height={14} />
      <span />
    </li>
  );
}
