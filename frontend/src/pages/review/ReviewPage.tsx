import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import type { Review } from "../../api/models";
import { useReview } from "../../api/queries";
import { ErrorBox } from "../../components/ErrorBox";
import { Panel } from "../../components/Panel";
import { Skeleton } from "../../components/Skeleton";
import { Minimap } from "./Minimap";
import { MomentList } from "./MomentList";
import { ReviewHeader } from "./ReviewHeader";
import { Scoreboard } from "./Scoreboard";
import { Scrubber } from "./Scrubber";
import { WinGraph } from "./WinGraph";
import { useReviewTime, type ReviewTime } from "./useReviewTime";
import styles from "./ReviewPage.module.css";

const TYPING = "input:not([type=range]), textarea, select, [contenteditable]";

/** Page-level shortcuts. Ignored while typing, and where a focused control owns the key. */
function useShortcuts(time: ReviewTime) {
  const latest = useRef(time);
  useEffect(() => {
    latest.current = time;
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
      const target = e.target instanceof Element ? e.target : null;
      if (target?.closest(TYPING)) return;
      const k = latest.current;
      let handled = true;
      switch (e.key) {
        case "ArrowLeft":
          if (e.shiftKey) k.seek(k.t - 15, null);
          else k.stepMoment(-1);
          break;
        case "ArrowRight":
          if (e.shiftKey) k.seek(k.t + 15, null);
          else k.stepMoment(1);
          break;
        case "Home":
          k.seek(0, null);
          break;
        case "End":
          k.seek(k.duration, null);
          break;
        case " ":
          // a focused button turns Space into its own click
          if (target?.closest("button, a")) return;
          k.togglePlay();
          break;
        default:
          handled = false;
      }
      if (handled) e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}

function ReviewView({
  review,
  participantId,
  initialT,
}: {
  review: Review;
  participantId: number;
  initialT: number | null;
}) {
  const time = useReviewTime(review, initialT);
  useShortcuts(time);
  const { t, snapshot, selected, moments } = time;
  const { seek, selectMoment, setHoveredId, setFilter } = time;

  return (
    <div className={styles.page}>
      <ReviewHeader review={review} participantId={participantId} onJump={selectMoment} />
      <WinGraph
        review={review}
        t={t}
        selected={selected}
        hoveredId={time.hoveredId}
        onSeek={seek}
      />
      <Scrubber
        t={t}
        duration={time.duration}
        curve={review.curve}
        playing={time.playing}
        onSeek={seek}
        onStep={time.stepMoment}
        onTogglePlay={time.togglePlay}
      />
      <div className={styles.panels}>
        <div className={styles.minimap}>
          <Minimap review={review} snapshot={snapshot} t={t} />
        </div>
        <div className={styles.scoreboard}>
          <Scoreboard review={review} snapshot={snapshot} />
        </div>
        <div className={styles.moments}>
          <MomentList
            review={review}
            moments={moments}
            filter={time.filter}
            selectedId={selected?.id ?? null}
            onFilter={setFilter}
            onSelect={selectMoment}
            onHover={setHoveredId}
          />
        </div>
      </div>
    </div>
  );
}

function ReviewSkeleton({ building }: { building: boolean }) {
  return (
    <div className={styles.page} aria-busy="true">
      <div className={styles.skelHeader}>
        <Skeleton width={48} height={48} round />
        <div className={styles.skelHeaderText}>
          <Skeleton width={220} height={28} />
          <Skeleton width={360} height={24} />
          <Skeleton width={520} height={24} />
        </div>
      </div>
      <div className={styles.skelGraph}>
        <Skeleton height={268} />
        {building && <p className={styles.building}>Building review…</p>}
      </div>
      <Skeleton height={36} />
      <div className={styles.panels}>
        <div className={styles.minimap}>
          <Panel title="Minimap">
            <Skeleton height={328} />
          </Panel>
        </div>
        <div className={styles.scoreboard}>
          <Panel title="Scoreboard">
            <Skeleton height={328} />
          </Panel>
        </div>
        <div className={styles.moments}>
          <Panel title="Moments" className={styles.skelMoments}>
            <Skeleton height={328} />
          </Panel>
        </div>
      </div>
    </div>
  );
}

export function ReviewPage() {
  const { matchId = "" } = useParams();
  const [params] = useSearchParams();
  const p = Number(params.get("p") ?? 0);
  const tParam = params.get("t");
  const [initialT] = useState(() =>
    tParam !== null && Number.isFinite(Number(tParam)) ? Number(tParam) : null,
  );
  const query = useReview(matchId, p);

  if (query.isError) {
    return (
      <div className={styles.page}>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  }
  if (!query.data) return <ReviewSkeleton building />;
  return (
    <ReviewView key={`${matchId}:${p}`} review={query.data} participantId={p} initialT={initialT} />
  );
}
