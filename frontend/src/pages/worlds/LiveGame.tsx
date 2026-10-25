import { useMemo, useState } from "react";
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { WorldsGame, WorldsPoint, WorldsTeam } from "../../api/models";
import { ChampIcon } from "../../components/ChampIcon";
import { Panel } from "../../components/Panel";
import { formatGold, formatGoldDelta, formatTime } from "../../lib/format";
import { ddragonVersion, winFromLead } from "../../lib/worlds";
import styles from "./worlds.module.css";

const axisText = { fill: "var(--text-3)", fontSize: 12, fontFamily: "var(--font-num)" };

const leadOf = (p: WorldsPoint) => p.blue.gold - p.red.gold;

function WinChart({ game, at }: { game: WorldsGame; at: number }) {
  const data = useMemo(
    () => game.points.map((p) => ({ t: p.t, p: winFromLead(leadOf(p)) * 100 })),
    [game.points],
  );
  const ticks = useMemo(() => {
    const out: number[] = [];
    for (let s = 0; s <= game.elapsed_s; s += 300) out.push(s);
    return out;
  }, [game.elapsed_s]);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <defs>
          {/* blue above the 50% line, red below it */}
          <linearGradient id="worlds-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" style={{ stopColor: "var(--ally-tint)" }} />
            <stop offset="0.5" style={{ stopColor: "var(--ally-tint)" }} />
            <stop offset="0.5" style={{ stopColor: "var(--enemy-tint)" }} />
            <stop offset="1" style={{ stopColor: "var(--enemy-tint)" }} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="t"
          type="number"
          domain={[0, game.elapsed_s]}
          ticks={ticks}
          tickFormatter={(s: number) => formatTime(s)}
          tick={axisText}
          tickMargin={6}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="number"
          domain={[0, 100]}
          ticks={[0, 50, 100]}
          width={40}
          tickFormatter={(v: number) => `${v}%`}
          tick={axisText}
          axisLine={false}
          tickLine={false}
        />
        <ReferenceLine y={50} stroke="var(--border)" strokeDasharray="4 4" />
        <ReferenceLine x={at} stroke="var(--text-2)" />
        <Area
          dataKey="p"
          baseValue={50}
          type="linear"
          stroke="var(--text)"
          strokeWidth={2}
          fill="url(#worlds-fill)"
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function TeamTable({ team, version }: { team: WorldsTeam; version: string }) {
  return (
    <Panel
      title={
        <span className={team.side === "blue" ? styles.blue : styles.red}>
          {team.name} · <span className="num">{team.kills}</span> kills ·{" "}
          <span className="num">{formatGold(team.gold)}</span> gold
        </span>
      }
    >
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Player</th>
            <th scope="col">Lv</th>
            <th scope="col">KDA</th>
            <th scope="col">CS</th>
            <th scope="col">Gold</th>
          </tr>
        </thead>
        <tbody>
          {team.players.map((p) => (
            <tr key={p.name}>
              <th scope="row">
                <span className={styles.player}>
                  <ChampIcon version={version} champion={p.champion} size={28} />
                  {p.name}
                </span>
              </th>
              <td className="num">{p.level}</td>
              <td className="num">
                {p.k}/{p.d}/{p.a}
              </td>
              <td className="num">{p.cs}</td>
              <td className="num">{formatGold(p.gold)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

export function LiveGame({ game }: { game: WorldsGame }) {
  // null follows the live edge; dragging the slider pins a minute
  const [pinned, setPinned] = useState<number | null>(null);
  const last = game.points.length - 1;
  const index = Math.min(pinned ?? last, last);
  const point = game.points[index];
  const { blue, red } = point;
  const lead = leadOf(point);
  const bluePct = Math.round(winFromLead(lead) * 100);
  const version = ddragonVersion(game.patch);
  return (
    <section className={styles.game}>
      <header className={styles.head}>
        <p className={styles.kicker}>
          {game.stage} � best of {game.best_of} � <span className="num">{formatTime(point.t)}</span>
          {game.live && index === last ? " (live)" : ""}
        </p>
        <div className={styles.score}>
          <span className={styles.blue}>{blue.code}</span>
          <span className={`${styles.pct} num`}>
            {bluePct}% � {100 - bluePct}%
          </span>
          <span className={styles.red}>{red.code}</span>
        </div>
        <p className={styles.kicker}>
          Gold lead:{" "}
          <span className="num">
            {formatGoldDelta(Math.abs(lead))} {lead >= 0 ? blue.code : red.code}
          </span>
        </p>
      </header>
      <WinChart game={game} at={point.t} />
      <div className={styles.slider}>
        <input
          type="range"
          min={0}
          max={last}
          value={index}
          onChange={(e) => setPinned(Number(e.target.value))}
          aria-label="Game time"
        />
        {game.live && (
          <button type="button" className={styles.liveBtn} onClick={() => setPinned(null)}>
            Live
          </button>
        )}
      </div>
      <dl className={styles.objectives}>
        {[blue, red].map((t) => (
          <div key={t.side}>
            <dt className={t.side === "blue" ? styles.blue : styles.red}>{t.code}</dt>
            <dd className="num">
              {t.towers} towers � {t.dragons} dragons � {t.barons} barons
            </dd>
          </div>
        ))}
      </dl>
      <div className={styles.teams}>
        <TeamTable team={blue} version={version} />
        <TeamTable team={red} version={version} />
      </div>
    </section>
  );
}
