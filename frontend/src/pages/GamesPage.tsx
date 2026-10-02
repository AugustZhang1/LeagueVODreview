import { RefreshCw } from "lucide-react";
import { useParams } from "react-router-dom";
import { usePlayerGames } from "../api/queries";
import type { Rank } from "../api/models";
import { Button } from "../components/Button";
import { ErrorBox } from "../components/ErrorBox";
import { Panel } from "../components/Panel";
import { GameRow, GameRowSkeleton } from "./games/GameRow";
import { platformLabel } from "./search/platforms";
import styles from "./GamesPage.module.css";

const SKELETON_ROWS = 10;

const titleCase = (s: string) => s.charAt(0) + s.slice(1).toLowerCase();

function rankLine(rank: Rank | null): string {
  if (!rank) return "Unranked";
  const tier = titleCase(rank.tier);
  return `${rank.division ? `${tier} ${rank.division}` : tier}, ${rank.lp} LP`;
}

export function GamesPage() {
  const { platform = "na1", name = "", tag = "" } = useParams();
  const query = usePlayerGames(platform, name, tag);
  const label = platformLabel(platform);
  const context = { name, tag, platform: label };

  const first = query.data?.pages[0];
  const games = query.data?.pages.flatMap((p) => p.games) ?? [];
  const loading = query.isPending && !query.isError;
  // A rate limit retries by itself, so show it while the query is still waiting.
  const waitingError = query.isPending ? query.failureReason : null;
  const failed = query.isError && !query.data;
  const refreshing = query.isRefetching && !query.isFetchingNextPage;

  return (
    <Panel className={styles.panel}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.title}>{first?.riot_id ?? `${name}#${tag}`}</h1>
          <p className={styles.sub}>
            {first && <span>{rankLine(first.rank)}</span>}
            <span className={styles.platform}>{label}</span>
          </p>
        </div>
        <Button onClick={() => void query.refetch()} disabled={query.isFetching}>
          <RefreshCw size={16} aria-hidden="true" />
          Refresh
        </Button>
      </header>

      <div className={styles.body} aria-busy={loading || refreshing}>
        {failed ? (
          <div className={styles.message}>
            <ErrorBox error={query.error} context={context} onRetry={() => void query.refetch()} />
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
        ) : (
          <ul className={styles.list}>
            {games.map((g) => (
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
            <Button onClick={() => void query.fetchNextPage()} disabled={query.isFetchingNextPage}>
              {query.isFetchingNextPage ? "Loading…" : "Load 10 more"}
            </Button>
          </div>
        )}
      </div>
    </Panel>
  );
}
