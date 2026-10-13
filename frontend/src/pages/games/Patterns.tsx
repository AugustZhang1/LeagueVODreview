import type { GameSummary, PatternRow } from "../../api/models";
import { usePatterns } from "../../api/queries";
import { formatDelta, formatGoldDelta } from "../../lib/format";
import styles from "./Patterns.module.css";

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** "Mid game (14-25 min)" becomes "Mid game". */
const shortPhase = (label: string) => capitalise(label.replace(/ \(.*\)$/, ""));

/** A count difference with a sign: "+6", "−2", "0". */
function signed(n: number): string {
  if (n === 0) return "0";
  return n > 0 ? `+${n}` : `−${-n}`;
}

/** One breakdown: a red bar per row, sized against the biggest loss in the block. */
function Breakdown({
  heading,
  rows,
  format = (label: string) => label,
}: {
  heading: string;
  rows: PatternRow[];
  format?: (label: string) => string;
}) {
  if (!rows.some((r) => r.mistakes > 0)) return null;
  const biggest = Math.max(...rows.map((r) => Math.abs(r.lost)));
  return (
    <section className={styles.block}>
      <h3 className={styles.heading}>{heading}</h3>
      {rows.map((r) => (
        <div key={r.label} className={styles.row}>
          <span className={styles.rowLabel}>{format(r.label)}</span>
          <span
            className={styles.bar}
            style={{ width: `${biggest > 0 ? (Math.abs(r.lost) / biggest) * 100 : 0}%` }}
          />
          <span className={`${styles.rowValue} num`}>{formatDelta(r.lost)}</span>
        </div>
      ))}
    </section>
  );
}

function Tile({ value, label }: { value: string | number; label: string }) {
  return (
    <div className={styles.tile}>
      <div className={`${styles.value} num`}>{value}</div>
      <div className={styles.tileLabel}>{label}</div>
    </div>
  );
}

type Props = { games: GameSummary[] };

/** Where and why I lose win chance across the games I've already reviewed. */
export function Patterns({ games }: Props) {
  const data = usePatterns(games.filter((g) => g.reviewed)).data;
  if (!data || data.games < 2) return null;

  const mistakes = data.grades["?"] + data.grades["??"];
  const gold = data.lane_gold_10;
  const cs = data.lane_cs_10;

  return (
    <section className={styles.card}>
      <header className={styles.header}>
        <h2 className={styles.title}>Your patterns</h2>
        <span className={styles.from}>from {data.games} reviewed games</span>
      </header>
      <div className={styles.tiles}>
        <Tile value={(mistakes / data.games).toFixed(1)} label="mistakes a game" />
        <Tile
          value={`${Math.round(data.missed_value * 100)}%`}
          label="win chance left in missed windows"
        />
        <Tile value={data.comebacks} label={data.comebacks === 1 ? "comeback" : "comebacks"} />
        <Tile value={data.thrown} label={data.thrown === 1 ? "thrown lead" : "thrown leads"} />
      </div>
      <Breakdown heading="When you lose win chance" rows={data.by_phase} format={shortPhase} />
      <Breakdown heading="Where" rows={data.by_zone} format={capitalise} />
      <Breakdown heading="Why" rows={data.by_driver} />
      {gold !== null && cs !== null && (
        <section className={styles.block}>
          <h3 className={styles.heading}>Lane at 10:00 vs your opponent</h3>
          <div className={styles.lane}>
            <span>
              <span className={`${styles.big} num`}>{formatGoldDelta(gold)}</span>{" "}
              <span className={styles.unit}>gold</span>
            </span>
            <span>
              <span className={`${styles.big} num`}>{signed(cs)}</span>{" "}
              <span className={styles.unit}>CS</span>
            </span>
          </div>
          <p className={styles.note}>Average over your reviewed games.</p>
        </section>
      )}
    </section>
  );
}
