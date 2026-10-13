import { useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet } from "../api/client";
import type { PlayerGames } from "../api/models";
import { useHealth } from "../api/queries";
import { Button } from "../components/Button";
import { describeError } from "../lib/errors";
import { PLATFORMS, platformLabel } from "./search/platforms";
import { SampleGraph } from "./search/SampleGraph";
import { addRecent, parseRiotId, readPlatform, readRecent, savePlatform } from "./search/storage";
import styles from "./SearchPage.module.css";

const HELPER = "Name and tag, as shown in the League client.";

const gamesPath = (platform: string, name: string, tag: string) =>
  `/p/${platform}/${encodeURIComponent(name)}/${encodeURIComponent(tag)}`;

export function SearchPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const messageId = useId();
  const [riotId, setRiotId] = useState("");
  const [platform, setPlatform] = useState(readPlatform);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [recent] = useState(readRecent);
  const sample = useHealth().data?.demo_player;

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

  const [sampleName, sampleTag] = sample?.riot_id.split("#") ?? ["", ""];

  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div>
          <h1 className={styles.headline}>Find the moments that decided your game.</h1>
          <p className={styles.lead}>
            Every fight, objective and death in your ranked games, graded by how much it moved your
            team's chance to win.
          </p>

          <form className={styles.form} onSubmit={submit} noValidate>
            <label className={styles.label} htmlFor="riot-id">
              Riot ID
            </label>
            <div className={styles.group}>
              <input
                id="riot-id"
                className={styles.input}
                type="text"
                value={riotId}
                onChange={(e) => setRiotId(e.target.value)}
                placeholder="Name#TAG"
                aria-invalid={error ? true : undefined}
                aria-describedby={messageId}
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
            {/* The helper line becomes the error while there is one, so the layout doesn't move. */}
            <p
              id={messageId}
              className={`${styles.message} ${error ? styles.error : styles.helper}`}
              role={error ? "alert" : undefined}
            >
              {error ?? HELPER}
            </p>
          </form>

          <div className={styles.recent}>
            {recent.length > 0 && (
              <nav className={styles.recentList} aria-label="Recent searches">
                <span className={styles.recentLabel}>Recent</span>
                {recent.map((r) => (
                  <Link
                    key={`${r.platform}/${r.name}/${r.tag}`}
                    className={styles.chip}
                    to={gamesPath(r.platform, r.name, r.tag)}
                  >
                    {r.name}#{r.tag}
                  </Link>
                ))}
              </nav>
            )}
            {sample && (
              <Link className={styles.chip} to={gamesPath(sample.platform, sampleName, sampleTag)}>
                Try a sample player <span className={styles.sampleId}>{sample.riot_id}</span>
              </Link>
            )}
          </div>
        </div>

        <SampleGraph />
      </section>

      <ol className={styles.steps} aria-label="How it works">
        <li>
          <h2 className={styles.stepTitle}>Search your Riot ID</h2>
          <p className={styles.stepText}>
            We pull your recent ranked games from Riot. Nothing to install.
          </p>
        </li>
        <li>
          <h2 className={styles.stepTitle}>Pick a game</h2>
          <p className={styles.stepText}>
            Reviewed games open instantly. New ones take about a minute.
          </p>
        </li>
        <li>
          <h2 className={styles.stepTitle}>Read the moments</h2>
          <p className={styles.stepText}>
            See what swung the game, why, and what the better play was.
          </p>
        </li>
      </ol>
    </div>
  );
}
