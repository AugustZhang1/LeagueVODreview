import { useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet } from "../api/client";
import type { PlayerGames } from "../api/models";
import { Button } from "../components/Button";
import { describeError } from "../lib/errors";
import { PLATFORMS, platformLabel } from "./search/platforms";
import { addRecent, parseRiotId, readPlatform, readRecent, savePlatform } from "./search/storage";
import styles from "./SearchPage.module.css";

const gamesPath = (platform: string, name: string, tag: string) =>
  `/p/${platform}/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`;

export function SearchPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const errorId = useId();
  const [riotId, setRiotId] = useState("");
  const [platform, setPlatform] = useState(readPlatform);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [recent] = useState(readRecent);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    const parsed = parseRiotId(riotId);
    if ("error" in parsed) {
      setError(parsed.error);
      return;
    }
    const { name, tag } = parsed;
    setError(null);
    setBusy(true);
    try {
      const first = await apiGet<PlayerGames>(
        `/api/player/${platform}/${encodeURIComponent(name)}/${encodeURIComponent(tag)}?start=0&count=10`,
      );
      queryClient.setQueryData(["player", platform, name, tag], {
        pages: [first],
        pageParams: [0],
      });
      addRecent({ platform, name, tag });
      navigate(gamesPath(platform, name, tag));
    } catch (err) {
      setError(describeError(err, { name, tag, platform: platformLabel(platform) }).message);
      setBusy(false);
    }
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.wordmark}>LeagueVODreview</h1>
      <p className={styles.tagline}>
        Grades every moment of your ranked games by how much it moved your team's chance to win.
      </p>

      <form className={styles.form} onSubmit={submit} noValidate>
        <div className={styles.group}>
          <input
            className={styles.input}
            type="text"
            value={riotId}
            onChange={(e) => setRiotId(e.target.value)}
            placeholder="Name#TAG"
            aria-label="Riot ID"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? errorId : undefined}
            autoFocus
            autoComplete="off"
            spellCheck={false}
          />
          <select
            className={styles.select}
            value={platform}
            aria-label="Server"
            onChange={(e) => {
              setPlatform(e.target.value);
              savePlatform(e.target.value);
            }}
          >
            {PLATFORMS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
          <Button type="submit" variant="primary" className={styles.submit} disabled={busy}>
            <Search size={16} aria-hidden="true" />
            {busy ? "Finding games…" : "Find games"}
          </Button>
        </div>
        <p id={errorId} className={styles.error} role={error ? "alert" : undefined}>
          {error}
        </p>
      </form>

      {recent.length > 0 && (
        <nav className={styles.recent} aria-label="Recent searches">
          <span className={styles.recentLabel}>Recent</span>
          {recent.map((r) => (
            <Link
              key={`${r.platform}/${r.name}/${r.tag}`}
              to={gamesPath(r.platform, r.name, r.tag)}
            >
              {r.name}#{r.tag}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
