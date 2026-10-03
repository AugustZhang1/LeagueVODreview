import { useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import type { Moment, Review } from "../../api/models";
import { useReplaySeek, useReplayStatus, useReview } from "../../api/queries";
import { ErrorBox } from "../../components/ErrorBox";
import { Panel } from "../../components/Panel";
import { Skeleton } from "../../components/Skeleton";
import { Minimap } from "./Minimap";
import { MomentList } from "./MomentList";
import { ReviewHeader } from "./ReviewHeader";
import { Scoreboard } from "./Scoreboard";
import { Scrubber, type ReplayControl } from "./Scrubber";
import { WinGraph } from "./WinGraph";
import { useReviewTime, type ReviewTime } from "./useReviewTime";
import styles from "./ReviewPage.module.css";

/** How far before a moment starts the League replay is sent, in seconds. */
const REPLAY_LEAD_S = 15;

const TYPING = "input:not([type=range]), textarea, select, [contenteditable]";

/** Page-level shortcuts. Ignored while typing, and where a focused control owns the key. */
function useShortcuts(time: ReviewTime, openReplay: () => void) {
  const latest = useRef({ time, openReplay });
  useEffect(() => {
    latest.current = { time, openReplay };
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented) return;
      const target = e.target instanceof Element ? e.target : null;
      if (target?.closest(TYPING)) return;
      const { time: k, openReplay: open } = latest.current;
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
        case "o":
        case "O":
          open();
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
  const matchId = review.match.match_id;
  const status = useReplayStatus(matchId);
  const seekReplay = useReplaySeek(matchId);
  const replayReady = status.data?.available === true;
  const leadIn = (m: Moment) => Math.max(0, m.t_start - REPLAY_LEAD_S);
  const time = useReviewTime(review, initialT, (m) => {
    if (replayReady) seekReplay.mutate(leadIn(m));
  });
  const replay: ReplayControl = {
    available: replayReady,
    reason: status.data?.reason ?? "Open this game's replay in the League client",
    onOpen: () => seekReplay.mutate(time.selected ? leadIn(time.selected) : time.t),
  };
  useShortcuts(time, () => replayReady && replay.onOpen());
  const { t, snapshot, selected, selectedWindow, moments, windows } = time;
  const { seek, selectMoment, selectWindow, setHoveredId, setFilter } = time;

  return (
    <div className={styles.page}>
      <ReviewHeader review={review} participantId={participantId} onJump={selectMoment} />
      <WinGraph
        review={review}
        t={t}
        selected={selected}
        selectedWindow={selectedWindow}
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
        replay={replay}
      />
      <div className={styles.panels}>
        <div className={styles.minimap}>
          <Minimap review={review} snapshot={snapshot} t={t} />
        </div>
        <div className={styles.scoreboard}>
          <Scoreboard review={review} snapshot={snapshot} t={t} />
        </div>
        <div className={styles.moments}>
          <MomentList
            review={review}
            moments={moments}
            windows={windows}
            filter={time.filter}
            selectedId={selected?.id ?? null}
            onFilter={setFilter}
            selectedWindowId={selectedWindow?.id ?? null}
            onSelect={selectMoment}
            onSelectWindow={selectWindow}
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
          <Skeleton width={220} height={24} />
          <Skeleton width={560} height={20} />
        </div>
      </div>
      <div className={styles.skelGraph}>
        <Skeleton height={216} />
        {building && <p className={styles.building}>Building review…</p>}
      </div>
      <Skeleton height={32} />
      <div className={styles.panels}>
        <div className={styles.minimap}>
          <Skeleton height={360} />
        </div>
        <div className={styles.scoreboard}>
          <Panel title="Scoreboard">
            <Skeleton height={346} />
          </Panel>
        </div>
        <div className={styles.moments}>
          <Panel title="Moments" className={styles.skelMoments}>
            <Skeleton height={346} />
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
