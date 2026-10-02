import { memo, useEffect, useRef } from "react";
import type { Moment, Review } from "../../api/models";
import { Delta } from "../../components/Delta";
import { GradeBadge } from "../../components/GradeBadge";
import { Panel } from "../../components/Panel";
import { Segmented } from "../../components/Segmented";
import { formatTime } from "../../lib/format";
import { MomentDetail } from "./MomentDetail";
import styles from "./MomentList.module.css";
import type { MomentFilter } from "./useReviewTime";

const OPTIONS: { value: MomentFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "graded", label: "Graded" },
  { value: "mine", label: "Mine" },
];

export function filterMoments(moments: Moment[], filter: MomentFilter): Moment[] {
  if (filter === "graded") return moments.filter((m) => m.grade !== null);
  if (filter === "mine") return moments.filter((m) => m.involves_me);
  return moments;
}

type Props = {
  review: Review;
  moments: Moment[];
  filter: MomentFilter;
  selectedId: string | null;
  onFilter: (f: MomentFilter) => void;
  onSelect: (m: Moment) => void;
  onHover: (id: string | null) => void;
};

export const MomentList = memo(function MomentList({
  review,
  moments,
  filter,
  selectedId,
  onFilter,
  onSelect,
  onHover,
}: Props) {
  const visible = filterMoments(moments, filter);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    const list = listRef.current;
    const row = selectedId
      ? list?.querySelector<HTMLElement>(`[data-moment="${selectedId}"]`)
      : null;
    if (!list || !row) return;
    if (row.offsetTop < list.scrollTop) list.scrollTop = row.offsetTop;
    else if (row.offsetTop + row.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = row.offsetTop + row.offsetHeight - list.clientHeight;
    }
  }, [selectedId, filter]);

  return (
    <Panel
      title="Moments"
      className={styles.panel}
      actions={
        <Segmented label="Show moments" options={OPTIONS} value={filter} onChange={onFilter} />
      }
    >
      {visible.length === 0 ? (
        <p className={styles.empty}>No moments here.</p>
      ) : (
        <ul className={styles.list} ref={listRef} onMouseLeave={() => onHover(null)}>
          {visible.map((m) => {
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
                  <span className={styles.badge}>{m.grade && <GradeBadge grade={m.grade} />}</span>
                  <span className={`${styles.time} num`}>{formatTime(m.t_end)}</span>
                  <span className={styles.title} title={m.title}>
                    {m.title}
                  </span>
                  {m.involves_me && (
                    <span role="img" aria-label="You were in this" className={styles.you} />
                  )}
                  <Delta value={m.delta} muted={m.grade === null} />
                </button>
                {selected && <MomentDetail moment={m} review={review} />}
              </li>
            );
          })}
        </ul>
      )}
    </Panel>
  );
});
