import { useRef, useState, type PointerEvent } from "react";
import { ChampIcon } from "../../components/ChampIcon";
import { Delta } from "../../components/Delta";
import { GradeBadge } from "../../components/GradeBadge";
import { splashUrl } from "../../lib/ddragon";
import { formatTime } from "../../lib/format";
import { isGoodGrade, isStrongGrade } from "../../lib/grades";
import { SAMPLE_CHAMPION, SAMPLE_CURVE, SAMPLE_DURATION_S, SAMPLE_MOMENTS } from "./sampleGame";
import styles from "./SampleGraph.module.css";

const W = 600;
const H = 160;
const x = (t: number) => (t / SAMPLE_DURATION_S) * W;
const y = (p: number) => H - (p / 100) * H;
const LINE = SAMPLE_CURVE.map(
  ([t, p], i) => `${i ? "L" : "M"}${x(t).toFixed(1)},${y(p).toFixed(1)}`,
).join("");
const AREA = `${LINE}L${W},${H / 2}L0,${H / 2}Z`;

/** Win chance in % at game time `t`, between the sampled points. */
function winAt(t: number): number {
  const i = SAMPLE_CURVE.findIndex(([ct]) => ct >= t);
  if (i <= 0) return SAMPLE_CURVE[Math.max(0, i)][1];
  const [t0, p0] = SAMPLE_CURVE[i - 1];
  const [t1, p1] = SAMPLE_CURVE[i];
  return p0 + ((p1 - p0) * (t - t0)) / Math.max(1, t1 - t0);
}

/** A real (made-up player's) review in miniature: the curve draws itself, the swings pop in. */
export function SampleGraph() {
  const [active, setActive] = useState<number | null>(null);
  const cursor = useRef<HTMLDivElement>(null);
  const readout = useRef<HTMLSpanElement>(null);

  // Pointer position drives the DOM directly; no re-render per mouse move.
  const onMove = (e: PointerEvent<HTMLDivElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (e.clientX - box.left) / box.width));
    const t = frac * SAMPLE_DURATION_S;
    if (cursor.current) {
      cursor.current.style.left = `${frac * 100}%`;
      cursor.current.hidden = false;
    }
    if (readout.current) {
      readout.current.textContent = `${formatTime(t)}  ${Math.round(winAt(t))}%`;
    }
  };
  const onLeave = () => {
    if (cursor.current) cursor.current.hidden = true;
    if (readout.current) readout.current.textContent = "";
  };

  return (
    <figure className={styles.card}>
      <div
        className={styles.splash}
        style={{ backgroundImage: `url(${splashUrl(SAMPLE_CHAMPION.id)})` }}
        aria-hidden="true"
      />
      <figcaption className={styles.head}>
        <ChampIcon version={SAMPLE_CHAMPION.ddragon} champion={SAMPLE_CHAMPION.id} size={40} />
        <div>
          <p className={styles.title}>
            <span className={styles.loss}>Defeat</span> as Fiddlesticks
          </p>
          <p className={styles.sub}>
            Sample review <span className="num">38:05</span>
          </p>
        </div>
        <span ref={readout} className={`${styles.readout} num`} aria-hidden="true" />
      </figcaption>

      <div
        className={styles.stage}
        onPointerMove={onMove}
        onPointerLeave={onLeave}
        role="img"
        aria-label="Win chance over the sample game: about even until 16:41, then three lost fights take it to zero."
      >
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={styles.svg}>
          <defs>
            <linearGradient
              id="sample-fill"
              gradientUnits="userSpaceOnUse"
              x1="0"
              y1="0"
              x2="0"
              y2={H}
            >
              <stop offset="0.5" style={{ stopColor: "var(--ally-fill)" }} />
              <stop offset="0.5" style={{ stopColor: "var(--enemy-fill)" }} />
            </linearGradient>
          </defs>
          <line x1="0" x2={W} y1={H / 2} y2={H / 2} className={styles.mid} />
          <path d={AREA} fill="url(#sample-fill)" className={styles.area} />
          <path d={LINE} pathLength={1} className={styles.line} />
        </svg>
        {SAMPLE_MOMENTS.map((m, i) => (
          <span
            key={m.t}
            className={[
              styles.marker,
              isGoodGrade(m.grade) ? styles.good : styles.bad,
              isStrongGrade(m.grade) ? styles.filled : "",
            ].join(" ")}
            data-active={active === i || undefined}
            style={{
              left: `${(m.t / SAMPLE_DURATION_S) * 100}%`,
              top: `${100 - winAt(m.t)}%`,
              animationDelay: `${0.9 + i * 0.18}s`,
            }}
            aria-hidden="true"
          />
        ))}
        <div ref={cursor} className={styles.cursor} hidden />
      </div>

      <ol className={styles.moments}>
        {SAMPLE_MOMENTS.map((m, i) => (
          <li
            key={m.t}
            className={styles.moment}
            data-active={active === i || undefined}
            onPointerEnter={() => setActive(i)}
            onPointerLeave={() => setActive(null)}
          >
            <span className="num">{formatTime(m.t)}</span>
            <GradeBadge grade={m.grade} />
            <span className={styles.momentTitle}>{m.title}</span>
            <Delta value={m.delta} />
          </li>
        ))}
      </ol>
    </figure>
  );
}
