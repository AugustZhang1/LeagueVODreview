import { memo, useEffect, useRef } from "react";
import type { Moment, ObjectiveWindow, Review } from "../../api/models";
import { Delta } from "../../components/Delta";
import { GradeBadge } from "../../components/GradeBadge";
import { Segmented } from "../../components/Segmented";
import { formatDelta, formatTime } from "../../lib/format";
import { MomentDetail } from "./MomentDetail";
import { WindowDetail } from "./WindowDetail";
import styles from "./MomentList.module.css";
import type { MomentFilter } from "./useReviewTime";

const OPTIONS: { value: MomentFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "yours", label: "Your mistakes" },
  { value: "team", label: "Team mistakes" },
  { value: "great", label: "Great" },
  { value: "missed", label: "Missed" },
  { value: "mine", label: "Mine" },
];

const isMistake = (m: Moment) => m.grade === "?" || m.grade === "??";

export function filterMoments(moments: Moment[], filter: MomentFilter): Moment[] {
  if (filter === "missed") return [];
  if (filter === "yours") return moments.filter((m) => isMistake(m) && m.involves_me);
  if (filter === "team") return moments.filter((m) => isMistake(m) && !m.involves_me);
  if (filter === "great") return moments.filter((m) => m.grade === "!!" || m.grade === "!");
  if (filter === "mine") return moments.filter((m) => m.involves_me);
  return moments;
}

type Row =
  { kind: "moment"; at: number; m: Moment } | { kind: "window"; at: number; w: ObjectiveWindow };

/** Moments and missed windows in one list, in time order. */
function buildRows(moments: Moment[], windows: ObjectiveWindow[], filter: MomentFilter): Row[] {
  const rows: Row[] = filterMoments(moments, filter).map((m) => ({
    kind: "moment",
    at: m.t_end,
    m,
  }));
  if (filter === "all" || filter === "missed") {
    for (const w of windows) {
      if (filter === "all" || !w.used) rows.push({ kind: "window", at: w.t_start, w });
    }
  }
  return rows.sort((a, b) => a.at - b.at);
}

type Props = {
  review: Review;
  moments: Moment[];
  windows: ObjectiveWindow[];
  filter: MomentFilter;
  selectedId: string | null;
  selectedWindowId: string | null;
  onFilter: (f: MomentFilter) => void;
  onSelect: (m: Moment) => void;
  onSelectWindow: (w: ObjectiveWindow) => void;
  onHover: (id: string | null) => void;
};

/** The rail: the selected item's detail on top, every visible moment and window below it. */
export const MomentList = memo(function MomentList({
  review,
  moments,
  windows,
  filter,
  selectedId,
  selectedWindowId,
  onFilter,
  onSelect,
  onSelectWindow,
  onHover,
}: Props) {
  const visible = buildRows(moments, windows, filter);
  const open = visible.find((r) =>
    r.kind === "moment" ? r.m.id === selectedId : r.w.id === selectedWindowId,
  );
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const list = listRef.current;
    const key = selectedId ?? selectedWindowId;
    const row = key ? list?.querySelector<HTMLElement>(`[data-moment="${key}"]`) : null;
    if (!list || !row) return;
    if (row.offsetTop < list.scrollTop) list.scrollTop = row.offsetTop;
    else if (row.offsetTop + row.offsetHeight > list.scrollTop + list.clientHeight)
      list.scrollTop = row.offsetTop + row.offsetHeight - list.clientHeight;
  }, [selectedId, selectedWindowId, filter]);

  return (
    <section className={styles.rail}>
      <header className={styles.head}>
        <h2 className={styles.heading}>Moments</h2>
        <Segmented label="Show moments" options={OPTIONS} value={filter} onChange={onFilter} />
      </header>
      {open?.kind === "moment" && <MomentDetail moment={open.m} review={review} />}
      {open?.kind === "window" && <WindowDetail window={open.w} moments={moments} />}
      {visible.length === 0 ? (
        <p className={styles.empty}>No moments here.</p>
      ) : (
        <ul className={styles.list} ref={listRef} onMouseLeave={() => onHover(null)}>
          {visible.map((r) => {
            if (r.kind === "window") {
              const w = r.w;
              const selected = w.id === selectedWindowId;
              return (
                <li key={w.id} data-moment={w.id} className={styles.item}>
                  <button
                    type="button"
                    className={selected ? `${styles.row} ${styles.selected}` : styles.row}
                    aria-current={selected || undefined}
                    onClick={() => onSelectWindow(w)}
                  >
                    <span className={`${styles.time} num`}>{formatTime(w.t_start)}</span>
                    <span className={styles.badge}>
                      {w.used ? (
                        <span role="img" aria-label="Used window" className={styles.used}>
                          <span aria-hidden="true">Used</span>
                        </span>
                      ) : (
                        <span role="img" aria-label="Missed window" className={styles.miss}>
                          <span aria-hidden="true">Miss</span>
                        </span>
                      )}
                    </span>
                    <span className={styles.title} title={w.title}>
                      {w.title}
                    </span>
                    <span className={`${styles.value} num`}>~{formatDelta(w.value)}</span>
                  </button>
                </li>
              );
            }
            const m = r.m;
            const selected = m.id === selectedId;
            return (
              <li key={m.id} data-moment={m.id} className={styles.item}>
                <button
                  type="button"
                  className={selected ? `${styles.row} ${styles.selected}` : styles.row}
                  aria-current={selected || undefined}
                  onClick={() => onSelect(m)}
                  onMouseEnter={() => onHover(m.id)}
                  onFocus={() => onHover(m.id)}
                  onBlur={() => onHover(null)}
                >
                  <span className={`${styles.time} num`}>{formatTime(m.t_end)}</span>
                  <span className={styles.badge}>{m.grade && <GradeBadge grade={m.grade} />}</span>
                  <span className={styles.title} title={m.title}>
                    {m.involves_me && (
                      <span role="img" aria-label="You were in this" className={styles.you} />
                    )}
                    {m.title}
                  </span>
                  <Delta value={m.delta} muted={m.grade === null} />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
});
