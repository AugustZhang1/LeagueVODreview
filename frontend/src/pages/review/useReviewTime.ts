import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Moment, ObjectiveWindow, Review, Snapshot } from "../../api/models";
import { momentEnd } from "./curve";

export type MomentFilter = "all" | "graded" | "missed" | "mine";

const URL_WRITE_MS = 200;
const PLAY_RATE = 60;

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
  );
}

function writeUrlT(t: number) {
  const url = new URL(window.location.href);
  if (url.searchParams.get("t") === String(t)) return;
  url.searchParams.set("t", String(t));
  window.history.replaceState(window.history.state, "", url);
}

/** The selected time and everything that follows from it. `initialT` is the URL's `t`. */
export function useReviewTime(
  review: Review,
  initialT: number | null,
  onSelectMoment?: (m: Moment) => void,
) {
  const duration = Math.floor(review.match.duration_s);
  const moments = useMemo(
    () => [...review.moments].sort((a, b) => a.t_end - b.t_end),
    [review.moments],
  );

  const windows = useMemo(
    () => [...(review.windows ?? [])].sort((a, b) => a.t_start - b.t_start),
    [review.windows],
  );

  const [t, setT] = useState(() => clamp(Math.floor(initialT ?? 0), 0, duration));
  const [selectedId, setSelectedId] = useState<string | null>(
    () =>
      moments.find((m) => momentEnd(m, duration) === clamp(Math.floor(initialT ?? -1), 0, duration))
        ?.id ?? null,
  );
  const [selectedWindowId, setSelectedWindowId] = useState<string | null>(null);
  const [filter, setFilter] = useState<MomentFilter>("all");
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const tRef = useRef(t);

  const seek = useCallback(
    (next: number, momentId?: string | null) => {
      const value = clamp(Math.round(next), 0, duration);
      tRef.current = value;
      setT(value);
      setSelectedWindowId(null);
      setSelectedId(
        momentId !== undefined
          ? momentId
          : (moments.find((m) => momentEnd(m, duration) === value)?.id ?? null),
      );
    },
    [duration, moments],
  );

  const selectMoment = useCallback(
    (m: Moment) => {
      seek(momentEnd(m, duration), m.id);
      onSelectMoment?.(m);
    },
    [seek, duration, onSelectMoment],
  );

  const selectWindow = useCallback(
    (w: ObjectiveWindow) => {
      seek(w.t_start, null);
      setSelectedWindowId(w.id);
    },
    [seek],
  );

  const selectedIndex = moments.findIndex((m) => m.id === selectedId);

  const stepMoment = useCallback(
    (dir: 1 | -1) => {
      let target: Moment | undefined;
      if (selectedIndex >= 0) {
        target = moments[selectedIndex + dir];
      } else if (dir === 1) {
        target = moments.find((m) => momentEnd(m, duration) > tRef.current);
      } else {
        target = [...moments].reverse().find((m) => momentEnd(m, duration) < tRef.current);
      }
      if (target) selectMoment(target);
      else if (dir === -1) seek(0, null);
    },
    [moments, selectedIndex, selectMoment, seek, duration],
  );

  const togglePlay = useCallback(() => {
    if (!playing && tRef.current >= duration) seek(0, null);
    setPlaying(!playing);
  }, [playing, duration, seek]);

  useEffect(() => {
    if (!playing) return;
    const advance = (to: number) => {
      seek(to);
      if (to >= duration) setPlaying(false);
    };
    if (prefersReducedMotion()) {
      const id = setInterval(() => advance(tRef.current + PLAY_RATE), 1000);
      return () => clearInterval(id);
    }
    let raf = 0;
    let last = performance.now();
    let exact = tRef.current;
    const tick = (now: number) => {
      // a seek while playing (arrow keys, scrubbing) moves the clock; follow it
      if (Math.abs(exact - tRef.current) > 1) exact = tRef.current;
      exact = Math.min(duration, exact + ((now - last) / 1000) * PLAY_RATE);
      last = now;
      if (Math.floor(exact) !== tRef.current) advance(Math.floor(exact));
      if (exact < duration) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, duration, seek]);

  // keep the URL's `t` current, writing at most every 200 ms
  const lastWrite = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    const wait = lastWrite.current + URL_WRITE_MS - Date.now();
    if (wait <= 0) {
      lastWrite.current = Date.now();
      writeUrlT(t);
    } else if (timer.current === null) {
      timer.current = setTimeout(() => {
        timer.current = null;
        lastWrite.current = Date.now();
        writeUrlT(tRef.current);
      }, wait);
    }
  }, [t]);
  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );

  const snapshot: Snapshot =
    review.snapshots[clamp(Math.floor(t / 15), 0, review.snapshots.length - 1)];
  const selected = selectedIndex >= 0 ? moments[selectedIndex] : null;

  const selectedWindow = windows.find((w) => w.id === selectedWindowId) ?? null;

  return {
    t,
    duration,
    snapshot,
    moments,
    windows,
    selected,
    selectedWindow,
    filter,
    setFilter,
    hoveredId,
    setHoveredId,
    playing,
    togglePlay,
    seek,
    selectMoment,
    selectWindow,
    stepMoment,
  };
}

export type ReviewTime = ReturnType<typeof useReviewTime>;
