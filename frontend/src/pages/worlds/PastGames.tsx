import { useState } from "react";
import { useWorldsMatch, useWorldsMatches } from "../../api/queries";
import { ErrorBox } from "../../components/ErrorBox";
import { Panel } from "../../components/Panel";
import { Segmented } from "../../components/Segmented";
import { Skeleton } from "../../components/Skeleton";
import { LiveGame } from "./LiveGame";
import styles from "./worlds.module.css";

const SHOWN = 30;

const day = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

function Match({ matchId }: { matchId: string }) {
  const match = useWorldsMatch(matchId);
  const [number, setNumber] = useState("1");

  if (match.isError) return <ErrorBox error={match.error} onRetry={() => void match.refetch()} />;
  if (match.isPending) return <Skeleton height={420} />;
  const games = match.data.games;
  if (games.length === 0) return <p className={styles.empty}>No finished games in this match.</p>;
  const game = games[Number(number) - 1] ?? games[0];
  return (
    <>
      {games.length > 1 && (
        <Segmented
          label="Game"
          value={String(games.indexOf(game) + 1)}
          onChange={setNumber}
          options={games.map((_, i) => ({ value: String(i + 1), label: `Game ${i + 1}` }))}
        />
      )}
      <LiveGame key={game.id} game={game} />
    </>
  );
}

export function PastGames() {
  const matches = useWorldsMatches();
  const [picked, setPicked] = useState<string | null>(null);

  if (matches.isError) {
    return <ErrorBox error={matches.error} onRetry={() => void matches.refetch()} />;
  }
  if (matches.isPending) return <Skeleton height={200} />;
  return (
    <section>
      <h2 className={styles.subheading}>Past games</h2>
      <Panel>
        <ul className={styles.matches}>
          {matches.data.matches.slice(0, SHOWN).map((m) => (
            <li key={m.id}>
              <button
                type="button"
                aria-pressed={m.id === picked}
                className={m.id === picked ? `${styles.match} ${styles.picked}` : styles.match}
                onClick={() => setPicked(m.id)}
              >
                <span className={styles.when}>{day(m.start)}</span>
                <span>{m.stage}</span>
                <span className="num">
                  {m.teams[0].code} {m.teams[0].wins} – {m.teams[1].wins} {m.teams[1].code}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Panel>
      {picked && <Match key={picked} matchId={picked} />}
    </section>
  );
}
