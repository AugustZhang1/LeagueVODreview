import { ChevronLeft, ChevronRight, MonitorPlay, Pause, Play } from "lucide-react";
import type { CSSProperties } from "react";
import type { CurvePoint } from "../../api/models";
import { Tooltip } from "../../components/Tooltip";
import { formatTime, formatWinChance } from "../../lib/format";
import { winAt } from "./curve";
import { PLOT_LEFT, PLOT_RIGHT } from "./layout";
import styles from "./Scrubber.module.css";

export type ReplayControl = { available: boolean; reason: string | null; onOpen: () => void };

type Props = {
  t: number;
  duration: number;
  curve: CurvePoint[];
  playing: boolean;
  onSeek: (t: number) => void;
  onStep: (dir: 1 | -1) => void;
  onTogglePlay: () => void;
  replay: ReplayControl;
};

export function Scrubber({
  t,
  duration,
  curve,
  playing,
  onSeek,
  onStep,
  onTogglePlay,
  replay,
}: Props) {
  const style = {
    "--played": `${duration > 0 ? t / duration : 0}`,
    gridTemplateColumns: `${PLOT_LEFT}px minmax(0, 1fr) ${PLOT_RIGHT}px`,
  } as CSSProperties;
  return (
    <div className={styles.scrubber} style={style}>
      <div className={styles.controls}>
        <button
          type="button"
          className={styles.button}
          aria-label="Previous moment"
          onClick={() => onStep(-1)}
        >
          <ChevronLeft size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className={styles.button}
          aria-label="Next moment"
          onClick={() => onStep(1)}
        >
          <ChevronRight size={16} aria-hidden="true" />
        </button>
        <button
          type="button"
          className={styles.button}
          aria-label={playing ? "Pause" : "Play"}
          onClick={onTogglePlay}
        >
          {playing ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
        </button>
      </div>
      <input
        type="range"
        className={styles.range}
        min={0}
        max={duration}
        step={1}
        value={t}
        aria-label="Game time"
        aria-valuetext={`${formatTime(t)}, win chance ${formatWinChance(winAt(curve, t), t >= duration)}`}
        onChange={(e) => onSeek(e.currentTarget.valueAsNumber)}
      />
      <div className={styles.end}>
        <span className={`${styles.time} num`}>{formatTime(t)}</span>
        <Tooltip content={replay.available ? "Open in replay (O)" : replay.reason}>
          <button
            type="button"
            className={styles.button}
            aria-label="Open in replay"
            aria-disabled={!replay.available}
            onClick={() => replay.available && replay.onOpen()}
          >
            <MonitorPlay size={16} aria-hidden="true" />
          </button>
        </Tooltip>
      </div>
    </div>
  );
}
