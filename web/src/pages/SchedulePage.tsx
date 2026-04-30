import { CSSProperties, useEffect, useMemo, useState } from "react";
import { ApiError, api, ScheduleEntry, SchedulePayload } from "../lib/api";
import { readCache, removeCache, writeCache } from "../lib/localCache";
import { formatWeekLabel, getCurrentWeekNumber, getTermStartDate, getWeekDateRange } from "../lib/termDates";

type WeekData = SchedulePayload["weeks"][number];
type DayData = WeekData["days"][number];
type MobileViewMode = "week" | "day";
type ExamScheduleItem = {
  id: string;
  term?: string | null;
  course_code?: string | null;
  course_name: string;
  exam_session?: string | null;
  exam_time_text?: string | null;
  exam_start_at?: string | null;
  exam_end_at?: string | null;
  location?: string | null;
  seat_no?: string | null;
};
type PositionedItem = {
  item: ScheduleEntry;
  laneIndex: number;
  laneCount: number;
  overlay: boolean;
  zOrder: number;
};

type TimetableBoardProps = {
  days: DayData[];
  positionedDays: PositionedItem[][];
  totalBlocks: number;
  blockNumbers: number[];
  onSelect: (item: ScheduleEntry) => void;
  singleDay?: boolean;
  compact?: boolean;
};

const WEEKDAYS = [
  { weekday: 1, label: "周一" },
  { weekday: 2, label: "周二" },
  { weekday: 3, label: "周三" },
  { weekday: 4, label: "周四" },
  { weekday: 5, label: "周五" },
  { weekday: 6, label: "周六" },
  { weekday: 7, label: "周日" }
] as const;

const BOARD_BLOCK_HEIGHT = 62;
const COMPACT_BLOCK_HEIGHT = 48;
const DAY_COLUMN_WIDTH = 112;
const DAY_COLUMN_GAP = 10;
const TIME_COLUMN_WIDTH = 46;
const MIN_BLOCKS = 14;
const SCHEDULE_CACHE_TTL_MS = 15 * 60 * 1000;
const SCHEDULE_CACHE_LAST_KEY = "cat-schedule:schedule:last";
const DAY_MS = 24 * 60 * 60 * 1000;

const COURSE_COLORS = [
  { background: "#f08a8c", border: "#dd6d72", text: "#ffffff" },
  { background: "#8ebcf0", border: "#74a6e1", text: "#ffffff" },
  { background: "#a99bef", border: "#8b7edf", text: "#ffffff" },
  { background: "#9ad8b0", border: "#7bc296", text: "#1f4732" },
  { background: "#f5c27b", border: "#e0a85d", text: "#643d12" }
];

function getScheduleCacheKey(term?: string) {
  return `cat-schedule:schedule:${term || "default"}`;
}

function getVisualSectionRange(item: ScheduleEntry) {
  const matched = item.time_text.match(/\((\d{2})-(\d{2})小节\)/);
  if (matched) {
    return { start: Number(matched[1]), end: Number(matched[2]) };
  }
  return { start: item.block_start, end: item.block_end };
}

function getPayloadExams(payload: SchedulePayload | null): ExamScheduleItem[] {
  return ((payload as (SchedulePayload & { exams?: ExamScheduleItem[] }) | null)?.exams ?? []).filter(
    (item) => item.exam_start_at
  );
}

function dateOnly(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

function isDateInRange(value: Date, range: [Date, Date]) {
  const day = dateOnly(value).getTime();
  return day >= dateOnly(range[0]).getTime() && day <= dateOnly(range[1]).getTime();
}

function timeToSection(value?: string | null) {
  if (!value) {
    return 1;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 1;
  }
  const minutes = date.getHours() * 60 + date.getMinutes();
  const starts = [8 * 60, 8 * 60 + 55, 10 * 60, 10 * 60 + 55, 13 * 60 + 30, 14 * 60 + 25, 15 * 60 + 30, 16 * 60 + 25, 18 * 60 + 30, 19 * 60 + 25, 20 * 60 + 20, 21 * 60 + 15];
  let section = 1;
  for (let index = 0; index < starts.length; index += 1) {
    if (minutes >= starts[index]) {
      section = index + 1;
    }
  }
  return section;
}

function examToScheduleEntry(exam: ExamScheduleItem): ScheduleEntry | null {
  if (!exam.exam_start_at) {
    return null;
  }
  const startAt = new Date(exam.exam_start_at);
  if (Number.isNaN(startAt.getTime())) {
    return null;
  }
  const weekday = startAt.getDay() === 0 ? 7 : startAt.getDay();
  const startSection = timeToSection(exam.exam_start_at);
  const endSection = Math.max(startSection, timeToSection(exam.exam_end_at));
  return {
    id: `exam-${exam.id}`,
    course_code: exam.course_code,
    class_no: exam.exam_session ?? null,
    course_name: `考试：${exam.course_name}`,
    teacher: exam.seat_no ? `座位 ${exam.seat_no}` : null,
    weekday,
    weekday_label: WEEKDAYS[weekday - 1]?.label ?? "",
    block_start: startSection,
    block_end: endSection,
    block_label_start: String(startSection),
    block_label_end: String(endSection),
    time_text: exam.exam_time_text || exam.exam_start_at,
    week_text: "考试安排",
    week_numbers: [],
    location: exam.location,
    credit: null,
    course_attribute: "考试",
    selection_stage: null
  };
}

function getExamWeekNumber(term: string | null | undefined, exam: ExamScheduleItem) {
  const startDate = getTermStartDate(term);
  if (!startDate || !exam.exam_start_at) {
    return null;
  }
  const examDate = new Date(exam.exam_start_at);
  if (Number.isNaN(examDate.getTime())) {
    return null;
  }
  const diffDays = Math.floor((dateOnly(examDate).getTime() - dateOnly(startDate).getTime()) / DAY_MS);
  const weekNumber = Math.floor(diffDays / 7) + 1;
  return weekNumber > 0 ? weekNumber : null;
}

function buildDisplayWeeks(payload: SchedulePayload | null, term: string | null | undefined): WeekData[] {
  if (!payload) {
    return [];
  }
  const byWeek = new Map<number, WeekData>();
  for (const weekItem of payload.weeks) {
    byWeek.set(weekItem.week_number, weekItem);
  }
  for (const exam of getPayloadExams(payload)) {
    const weekNumber = getExamWeekNumber(term ?? payload.term, exam);
    if (weekNumber && !byWeek.has(weekNumber)) {
      byWeek.set(weekNumber, { week_number: weekNumber, days: [] });
    }
  }
  return [...byWeek.values()].sort((left, right) => left.week_number - right.week_number);
}

function layoutDayItems(items: ScheduleEntry[]): PositionedItem[] {
  const sorted = [...items].sort((left, right) => {
    const leftRange = getVisualSectionRange(left);
    const rightRange = getVisualSectionRange(right);
    return (
      leftRange.start - rightRange.start ||
      rightRange.end - leftRange.end ||
      left.course_name.localeCompare(right.course_name, "zh-CN")
    );
  });

  const positioned: PositionedItem[] = [];
  let group: ScheduleEntry[] = [];
  let groupEnd = 0;

  const flushGroup = () => {
    if (!group.length) {
      return;
    }

    const ranges = group.map((item) => ({ item, range: getVisualSectionRange(item) }));
    const useOverlay = ranges.some((left, leftIndex) =>
      ranges.some((right, rightIndex) => {
        if (leftIndex === rightIndex) {
          return false;
        }
        return left.range.start <= right.range.start && left.range.end >= right.range.end;
      })
    );

    if (useOverlay) {
      const overlayItems = [...group].sort((left, right) => {
        const leftRange = getVisualSectionRange(left);
        const rightRange = getVisualSectionRange(right);
        const leftSpan = leftRange.end - leftRange.start;
        const rightSpan = rightRange.end - rightRange.start;
        return (
          rightSpan - leftSpan ||
          leftRange.start - rightRange.start ||
          left.course_name.localeCompare(right.course_name, "zh-CN")
        );
      });

      positioned.push(
        ...overlayItems.map((item, index) => ({
          item,
          laneIndex: 0,
          laneCount: 1,
          overlay: true,
          zOrder: index + 1
        }))
      );
      group = [];
      groupEnd = 0;
      return;
    }

    const laneEnds: number[] = [];
    const groupPlaced: Array<{ item: ScheduleEntry; laneIndex: number }> = [];

    for (const item of group) {
      const range = getVisualSectionRange(item);
      let laneIndex = laneEnds.findIndex((laneEnd) => laneEnd < range.start);
      if (laneIndex === -1) {
        laneIndex = laneEnds.length;
        laneEnds.push(range.end);
      } else {
        laneEnds[laneIndex] = range.end;
      }
      groupPlaced.push({ item, laneIndex });
    }

    const laneCount = Math.max(laneEnds.length, 1);
    positioned.push(
      ...groupPlaced.map((entry) => ({
        ...entry,
        laneCount,
        overlay: false,
        zOrder: laneCount - entry.laneIndex
      }))
    );
    group = [];
    groupEnd = 0;
  };

  for (const item of sorted) {
    const range = getVisualSectionRange(item);
    if (!group.length) {
      group = [item];
      groupEnd = range.end;
      continue;
    }

    if (range.start <= groupEnd) {
      group.push(item);
      groupEnd = Math.max(groupEnd, range.end);
      continue;
    }

    flushGroup();
    group = [item];
    groupEnd = range.end;
  }

  flushGroup();
  return positioned;
}

function formatSectionRange(item: ScheduleEntry): string {
  const range = getVisualSectionRange(item);
  if (range.start === range.end) {
    return `第 ${range.start} 节`;
  }
  return `第 ${range.start}-${range.end} 节`;
}

function buildCourseMeta(item: ScheduleEntry, expanded: boolean): string {
  if (expanded) {
    return [item.location, item.teacher].filter(Boolean).join(" · ");
  }
  return item.location || item.teacher || "";
}

function pickCourseColor(courseName: string) {
  const hash = Array.from(courseName).reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return COURSE_COLORS[hash % COURSE_COLORS.length];
}

function TimetableBoard({
  days,
  positionedDays,
  totalBlocks,
  blockNumbers,
  onSelect,
  singleDay = false,
  compact = false
}: TimetableBoardProps) {
  const blockHeight = compact ? COMPACT_BLOCK_HEIGHT : BOARD_BLOCK_HEIGHT;
  const boardHeight = totalBlocks * blockHeight;
  const frameWidth =
    TIME_COLUMN_WIDTH + DAY_COLUMN_GAP + days.length * DAY_COLUMN_WIDTH + (days.length - 1) * DAY_COLUMN_GAP;
  const columnsTemplate = singleDay
    ? "minmax(0, 1fr)"
    : compact
      ? `repeat(${days.length}, minmax(0, 1fr))`
      : `repeat(${days.length}, ${DAY_COLUMN_WIDTH}px)`;
  const frameStyle = singleDay || compact ? undefined : ({ width: `${frameWidth}px` } as CSSProperties);
  const boardClassName = ["timetable-board", compact ? "is-compact" : "", singleDay ? "is-single-day" : ""]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={boardClassName}>
      <div className="timetable-frame" style={frameStyle}>
        <div className="timetable-header-row">
          <div className="timetable-corner">节次</div>
          <div className="timetable-day-headers" style={{ gridTemplateColumns: columnsTemplate }}>
            {days.map((day) => (
              <div key={day.weekday} className="timetable-day-header">
                {day.weekday_label}
              </div>
            ))}
          </div>
        </div>

        <div className="timetable-body-row">
          <div className="timetable-time-column" style={{ gridTemplateRows: `repeat(${totalBlocks}, ${blockHeight}px)` }}>
            {blockNumbers.map((block) => (
              <div key={block} className="timetable-time-slot">
                <strong>{block}</strong>
              </div>
            ))}
          </div>

          <div className="timetable-grid-columns" style={{ gridTemplateColumns: columnsTemplate }}>
            {days.map((day, dayIndex) => (
              <div key={day.weekday} className="timetable-day-column" style={{ height: `${boardHeight}px` }}>
                <div className="timetable-column-grid" style={{ gridTemplateRows: `repeat(${totalBlocks}, ${blockHeight}px)` }}>
                  {blockNumbers.map((block) => (
                    <div key={`${day.weekday}-${block}`} className="timetable-grid-cell" />
                  ))}
                </div>

                {positionedDays[dayIndex].map((entry) => {
                  const color = pickCourseColor(entry.item.course_name);
                  const range = getVisualSectionRange(entry.item);
                  const span = range.end - range.start + 1;
                  const widthPercent = 100 / entry.laneCount;
                  const meta = buildCourseMeta(entry.item, singleDay);
                  const showSection = singleDay || (!compact && span >= 2) || (compact && span >= 3);
                  const showMeta = Boolean(meta) && (singleDay || (!compact && span >= 3 && entry.laneCount === 1));
                  const classNames = [
                    "timetable-course",
                    span <= 1 ? "is-short" : span <= 2 ? "is-medium" : "is-tall",
                    entry.laneCount > 1 ? "is-split" : "",
                    singleDay ? "is-expanded" : ""
                  ]
                    .filter(Boolean)
                    .join(" ");
                  const style: CSSProperties = {
                    top: `${(range.start - 1) * blockHeight + 3}px`,
                    height: `${span * blockHeight - 6}px`,
                    left: entry.overlay ? "1px" : `calc(${entry.laneIndex * widthPercent}% + 1px)`,
                    width: entry.overlay ? "calc(100% - 2px)" : `calc(${widthPercent}% - 2px)`,
                    background: color.background,
                    borderColor: color.border,
                    color: color.text,
                    zIndex: 100 + entry.zOrder
                  };

                  return (
                    <button
                      key={entry.item.id}
                      className={classNames}
                      style={style}
                      onClick={() => onSelect(entry.item)}
                      title={`${entry.item.course_name} ${formatSectionRange(entry.item)}`}
                    >
                      {showSection ? <span className="timetable-course-section">{formatSectionRange(entry.item)}</span> : null}
                      <strong>{entry.item.course_name}</strong>
                      {showMeta ? <span className="timetable-course-meta">{meta}</span> : null}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function getDefaultWeekNumber(payload: SchedulePayload, preferredTerm?: string, currentWeek?: number) {
  const availableWeeks = buildDisplayWeeks(payload, preferredTerm ?? payload.term).map((item) => item.week_number);
  const currentTermWeek = getCurrentWeekNumber(availableWeeks, payload.term ?? preferredTerm);
  if (currentTermWeek !== null) {
    return currentTermWeek;
  }
  if (currentWeek && availableWeeks.includes(currentWeek)) {
    return currentWeek;
  }
  return payload.weeks[0]?.week_number;
}

export function SchedulePage() {
  const [data, setData] = useState<SchedulePayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [term, setTerm] = useState<string | undefined>(undefined);
  const [week, setWeek] = useState<number | undefined>(undefined);
  const [mobileDay, setMobileDay] = useState<number | null>(null);
  const [mobileViewMode, setMobileViewMode] = useState<MobileViewMode>("week");
  const [selected, setSelected] = useState<ScheduleEntry | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function applyPayload(payload: SchedulePayload, preferredTerm?: string) {
    setData(payload);
    const resolvedTerm = payload.term ?? preferredTerm;
    setTerm(resolvedTerm);
    setWeek((currentWeek) => getDefaultWeekNumber(payload, resolvedTerm, currentWeek));
  }

  function persistPayload(payload: SchedulePayload, requestedTerm?: string) {
    const resolvedTerm = payload.term ?? requestedTerm;
    writeCache(SCHEDULE_CACHE_LAST_KEY, payload);
    if (resolvedTerm) {
      writeCache(getScheduleCacheKey(resolvedTerm), payload);
    }
  }

  async function load(nextTerm?: string) {
    setError("");
    setSelected(null);

    const cacheEntry =
      readCache<SchedulePayload>(getScheduleCacheKey(nextTerm), SCHEDULE_CACHE_TTL_MS) ||
      (!nextTerm ? readCache<SchedulePayload>(SCHEDULE_CACHE_LAST_KEY, SCHEDULE_CACHE_TTL_MS) : null);

    if (cacheEntry) {
      applyPayload(cacheEntry.data, nextTerm);
      setLoading(false);
      if (!cacheEntry.stale) {
        return;
      }
    } else {
      setLoading(true);
    }

    try {
      const result = await api.getSchedule(nextTerm);
      applyPayload(result, nextTerm);
      persistPayload(result, nextTerm);
    } catch (err) {
      if (!cacheEntry) {
        setError(err instanceof ApiError ? err.message : "课表加载失败");
      } else {
        setError(err instanceof ApiError ? `${err.message}，先展示本地缓存。` : "网络异常，先展示本地缓存。");
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const activeWeek = useMemo(
    () => buildDisplayWeeks(data, term).find((item) => item.week_number === week) ?? buildDisplayWeeks(data, term)[0],
    [data, term, week]
  );

  const displayWeeks = useMemo(() => buildDisplayWeeks(data, term), [data, term]);

  const activeWeekDateRange = useMemo(() => {
    if (!activeWeek) {
      return null;
    }
    return getWeekDateRange(term, activeWeek.week_number);
  }, [activeWeek, term]);

  const activeWeekExams = useMemo(() => {
    if (!data || !activeWeekDateRange) {
      return [];
    }
    return getPayloadExams(data)
      .filter((exam) => {
        const startAt = new Date(exam.exam_start_at || "");
        return !Number.isNaN(startAt.getTime()) && isDateInRange(startAt, activeWeekDateRange);
      })
      .map(examToScheduleEntry)
      .filter((item): item is ScheduleEntry => Boolean(item));
  }, [data, activeWeekDateRange]);

  const days = useMemo<DayData[]>(
    () =>
      WEEKDAYS.map(({ weekday, label }) => {
        const matched = activeWeek?.days.find((item) => item.weekday === weekday);
        const exams = activeWeekExams.filter((item) => item.weekday === weekday);
        return { weekday, weekday_label: label, items: [...(matched?.items ?? []), ...exams] };
      }),
    [activeWeek, activeWeekExams]
  );

  const positionedDays = useMemo(() => days.map((day) => layoutDayItems(day.items)), [days]);

  const totalBlocks = useMemo(() => {
    const maxBlock = days
      .flatMap((day) => day.items)
      .reduce((current, item) => Math.max(current, getVisualSectionRange(item).end), 0);
    return Math.max(MIN_BLOCKS, maxBlock);
  }, [days]);

  const blockNumbers = useMemo(() => Array.from({ length: totalBlocks }, (_, index) => index + 1), [totalBlocks]);

  useEffect(() => {
    if (mobileDay !== null && days.some((day) => day.weekday === mobileDay)) {
      return;
    }
    const defaultDay = days.find((day) => day.items.length > 0)?.weekday ?? days[0]?.weekday ?? 1;
    setMobileDay(defaultDay);
  }, [days, mobileDay]);

  const mobileDayData = useMemo(
    () => days.find((day) => day.weekday === mobileDay) ?? days[0],
    [days, mobileDay]
  );

  const mobilePositionedDays = useMemo(
    () => [layoutDayItems(mobileDayData?.items ?? [])],
    [mobileDayData]
  );

  const activeWeekRangeText = useMemo(() => {
    if (!activeWeekDateRange) {
      return "";
    }
    return `${activeWeekDateRange[0].getMonth() + 1}/${activeWeekDateRange[0].getDate()} - ${activeWeekDateRange[1].getMonth() + 1}/${activeWeekDateRange[1].getDate()}`;
  }, [activeWeekDateRange]);

  async function refresh() {
    setRefreshing(true);
    setMessage("");
    setError("");
    try {
      await api.refreshSchedule(term);
      removeCache(SCHEDULE_CACHE_LAST_KEY);
      if (term) {
        removeCache(getScheduleCacheKey(term));
      }
      setMessage("已提交刷新任务，稍后重新打开会自动读取新的缓存课表。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "提交刷新失败");
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <section className="page schedule-page">
      <div className="panel">
        <div className="panel-row schedule-toolbar-row">
          <div>
            <h2>课表</h2>
            <p className="schedule-updated">
              更新于 {data?.last_refreshed_at ? new Date(data.last_refreshed_at).toLocaleString() : "暂无"}
            </p>
          </div>
          <button className="button primary compact" onClick={refresh} disabled={refreshing}>
            {refreshing ? "提交中..." : "刷新课表"}
          </button>
        </div>

        <div className="schedule-filter-grid">
          {data?.available_terms?.length ? (
            <label className="field schedule-term-field">
              <span>学期</span>
              <select
                value={term ?? ""}
                onChange={(event) => {
                  const nextTerm = event.target.value;
                  setTerm(nextTerm);
                  void load(nextTerm);
                }}
              >
                {data.available_terms.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          {displayWeeks.length ? (
            <label className="field schedule-week-field">
              <span>周次</span>
              <select value={activeWeek?.week_number ?? ""} onChange={(event) => setWeek(Number(event.target.value))}>
                {displayWeeks.map((item) => (
                  <option key={item.week_number} value={item.week_number}>
                    {formatWeekLabel(term, item.week_number)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>

        {activeWeekRangeText ? <p className="schedule-week-caption">当前显示：{activeWeekRangeText}</p> : null}
        {message ? <div className="message success">{message}</div> : null}
        {error ? <div className="message error">{error}</div> : null}
      </div>

      <div className="panel timetable-panel">
        {loading ? (
          <p className="muted">正在加载课表...</p>
        ) : !displayWeeks.length ? (
          <div className="empty-state">当前还没有课表，先去绑定账号后刷新一次。</div>
        ) : (
          <>
            <div className="mobile-schedule-shell">
              <div className="schedule-view-switch">
                <button
                  className={mobileViewMode === "week" ? "view-pill active" : "view-pill"}
                  onClick={() => setMobileViewMode("week")}
                >
                  整周
                </button>
                <button
                  className={mobileViewMode === "day" ? "view-pill active" : "view-pill"}
                  onClick={() => setMobileViewMode("day")}
                >
                  单日
                </button>
              </div>

              {mobileViewMode === "week" ? (
                <TimetableBoard
                  days={days}
                  positionedDays={positionedDays}
                  totalBlocks={totalBlocks}
                  blockNumbers={blockNumbers}
                  onSelect={setSelected}
                  compact
                />
              ) : (
                <>
                  <div className="mobile-day-strip">
                    {days.map((day) => (
                      <button
                        key={day.weekday}
                        className={day.weekday === mobileDay ? "day-pill active" : "day-pill"}
                        onClick={() => setMobileDay(day.weekday)}
                      >
                        {day.weekday_label}
                      </button>
                    ))}
                  </div>

                  {mobileDayData ? (
                    <TimetableBoard
                      days={[mobileDayData]}
                      positionedDays={mobilePositionedDays}
                      totalBlocks={totalBlocks}
                      blockNumbers={blockNumbers}
                      onSelect={setSelected}
                      singleDay
                    />
                  ) : null}
                </>
              )}
            </div>

            <div className="desktop-timetable">
              <TimetableBoard
                days={days}
                positionedDays={positionedDays}
                totalBlocks={totalBlocks}
                blockNumbers={blockNumbers}
                onSelect={setSelected}
              />
            </div>
          </>
        )}
      </div>

      {selected ? (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <div className="modal-sheet" onClick={(event) => event.stopPropagation()}>
            <h3>{selected.course_name}</h3>
            <div className="detail-list">
              <div>
                <span>教师</span>
                <strong>{selected.teacher || "未填写"}</strong>
              </div>
              <div>
                <span>地点</span>
                <strong>{selected.location || "未填写"}</strong>
              </div>
              <div>
                <span>节次</span>
                <strong>{formatSectionRange(selected)}</strong>
              </div>
              <div>
                <span>时间</span>
                <strong>{selected.time_text}</strong>
              </div>
              <div>
                <span>周次</span>
                <strong>{selected.week_text}</strong>
              </div>
              <div>
                <span>学分</span>
                <strong>{selected.credit || "-"}</strong>
              </div>
              <div>
                <span>课程属性</span>
                <strong>{selected.course_attribute || "-"}</strong>
              </div>
            </div>
            <button className="button ghost" onClick={() => setSelected(null)}>
              关闭
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
