import { RefreshCw } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { usePlayerGames } from "../api/queries";
import type { GameSummary, Rank } from "../api/models";
import { Button } from "../components/Button";
import { ErrorBox } from "../components/ErrorBox";
import { Segmented } from "../components/Segmented";
import { Skeleton } from "../components/Skeleton";
import { GameRow, GameRowSkeleton } from "./games/GameRow";
import { Patterns } from "./games/Patterns";
import { platformLabel } from "./search/platforms";
import styles from "./GamesPage.module.css";

const SKELETON_ROWS = 10;

type Filter = "all" | "reviewed" | "todo";

const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "reviewed", label: "Reviewed" },
  { value: "todo", label: "Not yet" },
];

/** Remakes can't be reviewed, so they never count as "Not yet". */
const FILTER_MATCH: Record<Filter, (g: GameSummary) => boolean> = {
  all: () => true,
  reviewed: (g) => g.reviewed,
  todo: (g) => !g.reviewed && g.result !== "remake",
};

const titleCase = (s: string) => s.charAt(0) + s.slice(1).toLowerCase();

/** "Gold III" (the LP is shown beside it). */
const rankName = (rank: Rank) =>
  rank.division ? `${titleCase(rank.tier)} ${rank.division}` : titleCase(rank.tier);

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statKey}>{label}</span>
      <span className={styles.statValue}>{children}</span>
    </div>
  );
}

export function GamesPage() {
  const { platform = "na1", name = "", tag = "" } = useParams();
  const query = usePlayerGames(platform, name, tag);
  const [filter, setFilter] = useState<Filter>("all");
  const label = platformLabel(platform);
  const context = { name, tag, platform: label };

  const first = query.data?.pages[0];
  const games = query.data?.pages.flatMap((p) => p.games) ?? [];
  const loading = query.isPending && !query.isError;
  // A rate limit retries by itself, so show it while the query is still waiting.
  const waitingError = query.isPending ? query.failureReason : null;
  const failed = query.isError && !query.data;
  const refreshing = query.isRefetching && !query.isFetchingNextPage;

  const [riotName = "", riotTag = ""] = (first?.riot_id ?? `${name}#${tag}`).split("#");
  const played = games.filter((g) => g.result !== "remake");
  const wins = played.filter((g) => g.result === "win").length;
  const reviewed = games.filter((g) => g.reviewed).length;
  const scores = games.flatMap((g) => (g.score == null ? [] : [g.score]));
  const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;
  const shown = games.filter(FILTER_MATCH[filter]);

  return (
    <>
      <header className={styles.header}>
        <div className={styles.avatar} aria-hidden="true">
          {riotName.charAt(0).toUpperCase()}
        </div>
        <div className={styles.who}>
          <h1 className={styles.title}>
            {riotName}
            {riotTag && <span className={styles.handle}>#{riotTag}</span>}
          </h1>
          <p className={styles.meta}>
            {loading ? (
              <Skeleton width={150} height={16} />
            ) : (
              first &&
              (first.rank ? (
                <span>
                  <span className={styles.tier}>{rankName(first.rank)}</span> {first.rank.lp} LP
                </span>
              ) : (
                <span>Unranked</span>
              ))
            )}
            <span>{label}</span>
          </p>
        </div>
        <div className={styles.stats}>
          {loading ? (
            <Skeleton width={240} height={40} />
          ) : (
            played.length > 0 && (
              <>
                <Stat label={`Last ${played.length} games`}>
                  {wins}W <span className={styles.muted}>{played.length - wins}L</span>
                </Stat>
                {average !== null && (
                  <Stat label="Avg score">
                    {average.toFixed(1)} <span className={styles.unit}>/ 10</span>
                  </Stat>
                )}
                <Stat label="Reviewed">{reviewed}</Stat>
              </>
            )
          )}
          <Button onClick={() => void query.refetch()} disabled={query.isFetching}>
            <RefreshCw size={16} aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </header>

      <div className={`${styles.layout} ${reviewed >= 2 ? styles.split : ""}`}>
        <section className={styles.card}>
          <header className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>Ranked games</h2>
            {games.length > 0 && (
              <Segmented options={FILTERS} value={filter} onChange={setFilter} label="Show games" />
            )}
          </header>
          <div aria-busy={loading || refreshing}>
            {failed ? (
              <div className={styles.message}>
                <ErrorBox
                  error={query.error}
                  context={context}
                  onRetry={() => void query.refetch()}
                />
              </div>
            ) : waitingError ? (
              <div className={styles.message}>
                <ErrorBox error={waitingError} context={context} />
              </div>
            ) : loading ? (
              <ul className={styles.list} aria-label="Loading games">
                {Array.from({ length: SKELETON_ROWS }, (_, i) => (
                  <GameRowSkeleton key={i} />
                ))}
              </ul>
            ) : games.length === 0 ? (
              <p className={styles.empty}>No ranked solo games found.</p>
            ) : shown.length === 0 ? (
              <p className={styles.empty}>No games match this filter.</p>
            ) : (
              <ul className={styles.list}>
                {shown.map((g) => (
                  <GameRow key={g.match_id} game={g} />
                ))}
                {query.isFetchingNextPage &&
                  Array.from({ length: 3 }, (_, i) => <GameRowSkeleton key={`s${i}`} />)}
              </ul>
            )}

            {query.isFetchNextPageError && (
              <div className={styles.message}>
                <ErrorBox
                  error={query.error}
                  context={context}
                  onRetry={() => void query.fetchNextPage()}
                />
              </div>
            )}

            {query.hasNextPage && !query.isFetchNextPageError && (
              <div className={styles.more}>
                <Button
                  onClick={() => void query.fetchNextPage()}
                  disabled={query.isFetchingNextPage}
                >
                  {query.isFetchingNextPage ? "Loading…" : "Load 10 more"}
                </Button>
              </div>
            )}
          </div>
        </section>

        {reviewed >= 2 && <Patterns games={games} />}
      </div>
    </>
  );
}
