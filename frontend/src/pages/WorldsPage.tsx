import { useWorldsLive } from "../api/queries";
import { ErrorBox } from "../components/ErrorBox";
import { Skeleton } from "../components/Skeleton";
import { LiveGame } from "./worlds/LiveGame";
import { PastGames } from "./worlds/PastGames";
import styles from "./worlds/worlds.module.css";

export function WorldsPage() {
  const live = useWorldsLive();

  let body;
  if (live.isError) {
    body = <ErrorBox error={live.error} onRetry={() => void live.refetch()} />;
  } else if (live.isPending) {
    body = <Skeleton height={420} />;
  } else if (live.data.games.length === 0) {
    body = <p className={styles.empty}>No Worlds game is being played right now.</p>;
  } else {
    body = live.data.games.map((g) => <LiveGame key={g.id} game={g} />);
  }

  return (
    <div>
      <div className={styles.intro}>
        <h1 className={styles.heading}>World Stats</h1>
        <p className={styles.lede}>
          Worlds games as they are played, about a minute behind the broadcast. The win chance is
          estimated from the gold lead alone.
        </p>
      </div>
      {body}
      <PastGames />
    </div>
  );
}
