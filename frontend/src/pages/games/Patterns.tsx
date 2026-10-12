import type { GameSummary, PatternRow } from "../../api/models";
import { usePatterns } from "../../api/queries";
import { Delta } from "../../components/Delta";
import { formatDelta, formatGoldDelta } from "../../lib/format";
import styles from "./Patterns.module.css";

/** "Mid game (14-25 min)" becomes "mid game". */
const shortPhase = (label: string) => label.replace(/ \(.*\)$/, "").toLowerCase();

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/** A count difference with a sign: "+6", "−2", "0". */
function signed(n: number): string {
  if (n === 0) return "0";
  return n > 0 ? `+${n}` : `−${-n}`;
}

/** The phase where the most win chance was lost, or null when none was. */
function worstPhase(rows: PatternRow[]): PatternRow | null {
  const worst = rows.reduce<PatternRow | null>(
    (a, r) => (a === null || r.lost < a.lost ? r : a),
    null,
  );
  return worst && worst.lost < 0 ? worst : null;
}

function PatternTable({
  heading,
  rows,
  format = (label: string) => label,
}: {
  heading: string;
  rows: PatternRow[];
  format?: (label: string) => string;
}) {
  if (!rows.some((r) => r.mistakes > 0)) return null;
  return (
    <section className={styles.table}>
      <h3 className={styles.heading}>{heading}</h3>
      <table>
        <thead>
          <tr>
            <th scope="col" />
            <th scope="col">Mistakes</th>
            <th scope="col">Games</th>
            <th scope="col">Lost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row">{format(r.label)}</th>
              <td className="num">{r.mistakes}</td>
              <td className="num">{r.games}</td>
              <td>
                <Delta value={r.lost} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

type Props = { games: GameSummary[] };

/** Where and why I lose win chance across the games I've already reviewed. */
export function Patterns({ games }: Props) {
  const data = usePatterns(games.filter((g) => g.reviewed)).data;
  if (!data || data.games < 2) return null;

  const mistakes = data.grades["?"] + data.grades["??"];
  const phase = worstPhase(data.by_phase);
  const summary =
    `Patterns in your ${data.games} reviewed games: ` +
    `${(mistakes / data.games).toFixed(1)} mistakes a game` +
    (phase ? `, most win chance lost in ${shortPhase(phase.label)}` : "");

  const facts = [
    `${count(data.wins, "win", "wins")}, ${count(data.games - data.wins, "loss", "losses")}`,
    data.comebacks > 0 && count(data.comebacks, "comeback", "comebacks"),
    data.thrown > 0 && count(data.thrown, "thrown lead", "thrown leads"),
    data.windows_missed + data.windows_used > 0 &&
      `Missed windows: ${data.windows_missed}` +
        (data.windows_missed > 0 ? ` (worth ~${formatDelta(data.missed_value)} in total)` : "") +
        `, used ${data.windows_used}`,
  ]
    .filter(Boolean)
    .join(" · ");

  const gold = data.lane_gold_10;
  const cs = data.lane_cs_10;

  return (
    <details className={styles.patterns}>
      <summary className={styles.summary}>{summary}</summary>
      <div className={styles.body}>
        <p>{facts}</p>
        {gold !== null && cs !== null && (
          <p>
            {`At 10:00 vs your lane opponent: ${formatGoldDelta(gold)} gold, ${signed(cs)} CS (average)`}
          </p>
        )}
        <div className={styles.tables}>
          <PatternTable heading="When" rows={data.by_phase} />
          <PatternTable heading="Where" rows={data.by_zone} format={capitalise} />
          <PatternTable heading="Why" rows={data.by_driver} />
        </div>
      </div>
    </details>
  );
}
