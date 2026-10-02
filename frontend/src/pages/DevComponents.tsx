import { useState, type ReactNode } from "react";
import { ApiError } from "../api/client";
import { Button } from "../components/Button";
import { ChampIcon } from "../components/ChampIcon";
import { Delta } from "../components/Delta";
import { ErrorBox } from "../components/ErrorBox";
import { GradeBadge } from "../components/GradeBadge";
import { ItemIcon } from "../components/ItemIcon";
import { Panel } from "../components/Panel";
import { Segmented } from "../components/Segmented";
import { Skeleton } from "../components/Skeleton";
import { Tooltip } from "../components/Tooltip";
import {
  formatDelta,
  formatGold,
  formatGoldDelta,
  formatTime,
  formatWinChance,
} from "../lib/format";
import { GRADES } from "../lib/grades";
import styles from "./DevComponents.module.css";

const V = "26.19.1";

const TOKENS = [
  ["--bg", "page"],
  ["--surface", "panels, top bar"],
  ["--surface-2", "hover, selected"],
  ["--border", "dividers"],
  ["--text", "main text"],
  ["--text-2", "secondary"],
  ["--text-3", "muted"],
  ["--ally", "your team"],
  ["--enemy", "enemy"],
  ["--you", "you"],
  ["--ally-tint", "good fill"],
  ["--enemy-tint", "bad fill"],
] as const;

const ERRORS: [string, ApiError][] = [
  ["riot_id_not_found", new ApiError("riot_id_not_found", "", 404)],
  ["key_expired", new ApiError("key_expired", "", 401)],
  ["rate_limited", new ApiError("rate_limited", "", 429, 8)],
  ["riot_unavailable", new ApiError("riot_unavailable", "", 502)],
  ["match_not_found", new ApiError("match_not_found", "", 404)],
  ["unsupported_queue", new ApiError("unsupported_queue", "", 400)],
  ["anything else", new ApiError("boom", "", 500)],
];

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className={styles.row}>
      <h3 className={styles.label}>{label}</h3>
      <div className={styles.samples}>{children}</div>
    </div>
  );
}

export default function DevComponents() {
  const [filter, setFilter] = useState<"all" | "graded" | "mine">("all");
  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Components</h1>

      <Row label="Tokens">
        <div className={styles.swatches}>
          {TOKENS.map(([name, use]) => (
            <div key={name} className={styles.swatch}>
              <span className={styles.chip} style={{ background: `var(${name})` }} />
              <span className="num">{name}</span>
              <span className={styles.muted}>{use}</span>
            </div>
          ))}
        </div>
      </Row>

      <Row label="Type">
        <div className={styles.type}>
          <span className="num" style={{ fontSize: 36, fontWeight: 600 }}>
            LeagueVODreview
          </span>
          <span style={{ fontSize: 20, fontWeight: 600 }}>Victory as Ahri</span>
          <span style={{ fontSize: 16, fontWeight: 600 }}>Panel title</span>
          <span>Body text, 14 px: the quick brown fox 0123456789</span>
          <span className="num">Numbers, Semi Condensed: 31:42 9.1k 212 8 / 2 / 11</span>
          <span style={{ fontSize: 12, color: "var(--text-3)" }}>
            Axis labels and footnotes, 12 px
          </span>
        </div>
      </Row>

      <Row label="Buttons">
        <Button variant="primary">Find games</Button>
        <Button variant="primary" disabled>
          Finding games…
        </Button>
        <Button>Refresh</Button>
        <Button disabled>Load 10 more</Button>
      </Row>

      <Row label="GradeBadge">
        {GRADES.map((g) => (
          <GradeBadge key={g} grade={g} />
        ))}
        <span className={styles.gap} />
        {GRADES.map((g, i) => (
          <GradeBadge key={g} grade={g} count={i + 1} />
        ))}
      </Row>

      <Row label="Delta">
        <Delta value={0.18} />
        <Delta value={-0.11} />
        <Delta value={0.004} />
        <Delta value={0.03} muted />
        <Delta value={-0.03} muted />
      </Row>

      <Row label="ChampIcon">
        {[16, 24, 32, 48].map((s) => (
          <ChampIcon key={s} version={V} champion="Ahri" size={s} />
        ))}
        <span className={styles.gap} />
        <ChampIcon version={V} champion="Zed" size={32} ring="enemy" />
        <ChampIcon version={V} champion="Vi" size={32} ring="ally" />
        <ChampIcon version={V} champion="Ahri" size={32} ring="you" />
        <span className={styles.gap} />
        <ChampIcon version={V} champion="NoSuchChampion" name="Missing" size={32} />
        <ChampIcon version={V} champion="MonkeyKing" name="Wukong" size={32} />
      </Row>

      <Row label="ItemIcon">
        <ItemIcon version={V} itemId={3089} />
        <ItemIcon version={V} itemId={6655} />
        <ItemIcon version={V} itemId={null} />
        <ItemIcon version={V} itemId={null} />
        <ItemIcon version={V} itemId={999999} />
        <ItemIcon version={V} itemId={3340} size={32} />
      </Row>

      <Row label="Segmented">
        <Segmented
          label="Moments filter"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "All" },
            { value: "graded", label: "Graded" },
            { value: "mine", label: "Mine" },
          ]}
        />
      </Row>

      <Row label="Tooltip">
        <Tooltip content="Ocean Dragon, taken at 05:04">
          <Button>Hover or focus me</Button>
        </Tooltip>
      </Row>

      <Row label="Skeleton">
        <div className={styles.skeletons}>
          <Skeleton height={56} />
          <Skeleton height={56} />
          <div className={styles.inline}>
            <Skeleton width={32} height={32} round />
            <Skeleton width={160} height={14} />
          </div>
        </div>
      </Row>

      <Row label="ErrorBox">
        <div className={styles.errors}>
          {ERRORS.map(([code, err]) => (
            <div key={code} className={styles.errorItem}>
              <span className={styles.muted}>{code}</span>
              <ErrorBox
                error={err}
                onRetry={() => {}}
                context={{ name: "Name", tag: "TAG", platform: "na" }}
              />
            </div>
          ))}
        </div>
      </Row>

      <Row label="Panel">
        <Panel
          title="Moments"
          actions={
            <Segmented
              label="Filter"
              value="all"
              onChange={() => {}}
              options={[
                { value: "all", label: "All" },
                { value: "graded", label: "Graded" },
              ]}
            />
          }
        >
          <ul className={styles.list}>
            {[
              ["!!", "22:10", "Won fight 4 for 1", 0.18],
              ["?", "14:32", "Lost top outer tower", -0.07],
              [null, "05:04", "Took Ocean Dragon", 0.02],
            ].map(([g, t, title, d]) => (
              <li key={String(t)} className={styles.listRow}>
                <span className={styles.slot}>{g && <GradeBadge grade={g as "!!" | "?"} />}</span>
                <span className="num">{t as string}</span>
                <span className={styles.truncate}>{title as string}</span>
                <Delta value={d as number} muted={!g} />
              </li>
            ))}
          </ul>
        </Panel>
      </Row>

      <Row label="Format">
        <table className={`${styles.table} num`}>
          <tbody>
            <tr>
              <td>formatTime(1902)</td>
              <td>{formatTime(1902)}</td>
            </tr>
            <tr>
              <td>formatTime(3725)</td>
              <td>{formatTime(3725)}</td>
            </tr>
            <tr>
              <td>formatWinChance(0.004)</td>
              <td>{formatWinChance(0.004)}</td>
            </tr>
            <tr>
              <td>formatWinChance(1, true)</td>
              <td>{formatWinChance(1, true)}</td>
            </tr>
            <tr>
              <td>formatDelta(-0.11)</td>
              <td>{formatDelta(-0.11)}</td>
            </tr>
            <tr>
              <td>formatGold(9120)</td>
              <td>{formatGold(9120)}</td>
            </tr>
            <tr>
              <td>formatGoldDelta(-800)</td>
              <td>{formatGoldDelta(-800)}</td>
            </tr>
          </tbody>
        </table>
      </Row>
    </div>
  );
}
