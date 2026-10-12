import { useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useId, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiGet } from "../api/client";
import type { PlayerGames } from "../api/models";
import { useHealth, useModel } from "../api/queries";
import { Button } from "../components/Button";
import { GradeBadge } from "../components/GradeBadge";
import { describeError } from "../lib/errors";
import { GRADES, gradeName, type Grade } from "../lib/grades";
import { readMetrics } from "./model/metrics";
import { PLATFORMS, platformLabel } from "./search/platforms";
import { SampleGraph } from "./search/SampleGraph";
import { addRecent, parseRiotId, readPlatform, readRecent, savePlatform } from "./search/storage";
import styles from "./SearchPage.module.css";

const REPO_URL = "https://github.com/AugustZhang1/LeagueVODreview";

const GRADE_MEANING: Record<Grade, string> = {
  "!!": "Raised your team's win chance by 10% or more.",
  "!": "Raised it by 5% to 10%.",
  "?": "Cost 5% to 10%.",
  "??": "Cost 10% or more.",
};

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
  const sample = useHealth().data?.demo_player;
  const model = useModel();
  const view = model.data ? readMetrics(model.data) : null;

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
        <div className={styles.intro}>
          <h1 className={styles.headline}>Find the fights that decided your game.</h1>
          <p className={styles.tagline}>
            Every fight, objective and tower in your ranked games, graded by how much it moved your
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

          <div className={styles.after}>
            {sample && (
              <Link
                className={styles.sample}
                to={gamesPath(sample.platform, sampleName, sampleTag)}
              >
                Try a sample player <span className={styles.sampleId}>{sample.riot_id}</span>
              </Link>
            )}
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
        </div>

        <SampleGraph />
      </section>

      <section className={styles.grades} aria-labelledby="grades-title">
        <h2 id="grades-title" className={styles.sectionTitle}>
          Four grades, one question: did it help you win?
        </h2>
        <dl className={styles.gradeList}>
          {GRADES.map((g) => (
            <div key={g} className={styles.grade}>
              <dt>
                <GradeBadge grade={g} />
                <span className={styles.gradeName}>{gradeName(g)}</span>
              </dt>
              <dd>{GRADE_MEANING[g]}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className={styles.how} aria-labelledby="how-title">
        <div className={styles.howText}>
          <h2 id="how-title" className={styles.sectionTitle}>
            How the grades are made
          </h2>
          <p>
            A LightGBM model reads the game every 15 seconds: gold, kills, towers, dragons, who is
            dead and for how long, and where players stand. It predicts each team's chance to win,
            and a moment's grade is how far that chance moved across it.
          </p>
          <p>
            Reviews come from Riot's match timeline, so no replay file is needed. A Python (FastAPI)
            backend builds each review; this site is React and TypeScript.
          </p>
          <p className={styles.links}>
            <Link to="/model">Model accuracy</Link>
            <a href={REPO_URL} target="_blank" rel="noreferrer">
              Source on GitHub
            </a>
          </p>
        </div>
        {view && view.games !== null && (
          <dl className={styles.stats}>
            <div>
              <dt>Ranked games trained on</dt>
              <dd className="num">{view.games.toLocaleString("en-US")}</dd>
            </div>
            {view.accuracyAt10 !== null && (
              <div>
                <dt>Winner called right at 10 to 15 minutes</dt>
                <dd className="num">{(view.accuracyAt10 * 100).toFixed(1)}%</dd>
              </div>
            )}
            {view.patches.length > 0 && (
              <div>
                <dt>Patches</dt>
                <dd className="num">
                  {view.patches[0]} to {view.patches[view.patches.length - 1]}
                </dd>
              </div>
            )}
          </dl>
        )}
      </section>
    </div>
  );
}
