import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import type { Moment, Review } from "../../api/models";
import { useReplaySeek, useReplayStatus, useReview } from "../../api/queries";
import { ErrorBox } from "../../components/ErrorBox";
import { Panel } from "../../components/Panel";
import { Skeleton } from "../../components/Skeleton";
import { GameNotes } from "./GameNotes";
import { ImpactChart } from "./ImpactChart";
import { LaneChart } from "./LaneChart";
import { GRAPH_HEIGHT } from "./layout";
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

const leadIn = (m: Moment) => Math.max(0, m.t_start - REPLAY_LEAD_S);

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
  // mutate is stable, so this callback only changes when replayReady does
  const seekTo = useReplaySeek(matchId).mutate;
  const replayReady = status.data?.available === true;
  const onSelectMoment = useCallback(
    (m: Moment) => {
      if (replayReady) seekTo(leadIn(m));
    },
    [replayReady, seekTo],
  );
  const time = useReviewTime(review, initialT, onSelectMoment);
  const replay: ReplayControl = {
    available: replayReady,
    reason: status.data?.reason ?? "Open this game's replay in the League client",
    onOpen: () => seekTo(time.selected ? leadIn(time.selected) : time.t),
  };
  useShortcuts(time, () => replayReady && replay.onOpen());
  const { t, snapshot, selected, selectedWindow, moments, windows } = time;
  const { seek, selectMoment, selectWindow, setHoveredId, setFilter } = time;

  return (
    <div className={styles.page} data-wide>
      <div className={styles.head}>
        <ReviewHeader review={review} />
      </div>
      <div className={styles.chart}>
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
      <div className={styles.panels}>
        <div className={styles.minimap}>
          <Minimap review={review} snapshot={snapshot} t={t} />
        </div>
        <div className={styles.scoreboard}>
          <Scoreboard review={review} snapshot={snapshot} t={t} />
        </div>
      </div>
      <div className={styles.extras}>
        <LaneChart review={review} />
        <ImpactChart review={review} />
        <GameNotes matchId={matchId} participantId={participantId} t={t} />
      </div>
    </div>
  );
}

function ReviewSkeleton({ building }: { building: boolean }) {
  return (
    <div className={styles.page} aria-busy="true" data-wide>
      <div className={styles.head}>
        <div className={styles.skelHeader}>
          <Skeleton width={42} height={42} round />
          <div className={styles.skelHeaderText}>
            <div className={styles.skelTitleRow}>
              <Skeleton width={260} height={28} />
              <div className={styles.skelSummary}>
                <Skeleton width={44} height={32} />
                <Skeleton width={260} height={20} />
              </div>
            </div>
            <Skeleton width={480} height={18} />
          </div>
        </div>
      </div>
      <div className={styles.chart}>
        <div className={styles.skelReading}>
          <Skeleton width={180} height={16} />
          <Skeleton width={120} height={34} />
        </div>
        <div className={styles.skelGraph}>
          <Skeleton height={GRAPH_HEIGHT} />
          {building && <p className={styles.building}>Building review…</p>}
        </div>
        <Skeleton height={32} />
      </div>
      <div className={styles.moments}>
        <Panel title="Moments" className={styles.skelMoments}>
          <Skeleton height={346} />
        </Panel>
      </div>
      <div className={styles.panels}>
        <div className={`${styles.minimap} ${styles.skelMinimap}`}>
          <Skeleton height="100%" />
        </div>
        <div className={styles.scoreboard}>
          <Panel title="Scoreboard">
            <Skeleton height={344} />
          </Panel>
        </div>
      </div>
      <div className={styles.extras}>
        <Panel title={<Skeleton width={160} height={16} />}>
          <Skeleton height={200} />
          <div className={styles.skelChecks}>
            <Skeleton height={20} />
            <Skeleton height={20} />
          </div>
        </Panel>
        <Panel title={<Skeleton width={160} height={16} />}>
          <Skeleton height={200} />
          <div className={styles.skelChecks}>
            <Skeleton height={17} />
          </div>
        </Panel>
        <Panel title="Notes">
          <Skeleton height={160} />
        </Panel>
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
      <div className={styles.page} data-wide>
        <ErrorBox error={query.error} onRetry={() => void query.refetch()} />
      </div>
    );
  }
  if (!query.data) return <ReviewSkeleton building />;
  return (
    <ReviewView key={`${matchId}:${p}`} review={query.data} participantId={p} initialT={initialT} />
  );
}
