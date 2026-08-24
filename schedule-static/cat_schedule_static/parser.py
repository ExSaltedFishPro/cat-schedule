from __future__ import annotations

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

from cat_schedule_static.models import (
    CourseDetailRow,
    CourseTimeSegment,
    ScheduleOccurrence,
    ScheduleParseError,
    ScheduleParseResult,
)


WEEKDAY_MAP = {
    "一": (1, "星期一"),
    "二": (2, "星期二"),
    "三": (3, "星期三"),
    "四": (4, "星期四"),
    "五": (5, "星期五"),
    "六": (6, "星期六"),
    "日": (7, "星期日"),
    "天": (7, "星期日"),
}


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def parse_week_numbers(week_text: str) -> list[int]:
    body = normalize_text(week_text)
    if not body:
        return []

    body = body.replace("（", "(").replace("）", ")")
    body = body.replace("－", "-").replace("—", "-").replace("～", "-").replace("~", "-")
    body = re.sub(r"第|周次[:：]?|周", "", body)
    weeks: set[int] = set()

    for token in re.split(r"[，,、；;\s]+", body):
        token = token.strip("()[]{}")
        if not token:
            continue
        odd_only = "单" in token
        even_only = "双" in token
        token = re.sub(r"[单双]", "", token).strip("()[]{}")
        range_match = re.search(r"(\d+)\s*(?:-|至)\s*(\d+)", token)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if end < start:
                start, end = end, start
            for value in range(start, end + 1):
                if odd_only and value % 2 == 0:
                    continue
                if even_only and value % 2 == 1:
                    continue
                weeks.add(value)
            continue

        for number in re.findall(r"\d+", token):
            value = int(number)
            if odd_only and value % 2 == 0:
                continue
            if even_only and value % 2 == 1:
                continue
            weeks.add(value)

    return sorted(weeks)


def parse_time_segment_text(time_text: str, location: str | None) -> CourseTimeSegment | None:
    value = normalize_text(time_text)
    match = re.search(
        r"星期\s*([一二三四五六日天])\s*[（(]\s*(\d{1,2})\s*[-－—~～]\s*(\d{1,2})\s*小节\s*[）)]",
        value,
    )
    if not match:
        return None
    weekday, weekday_label = WEEKDAY_MAP[match.group(1)]
    return CourseTimeSegment(
        weekday=weekday,
        weekday_label=weekday_label,
        start_section=int(match.group(2)),
        end_section=int(match.group(3)),
        time_text=value,
        location=normalize_text(location) or None,
    )


def _looks_like_mhtml(content: bytes) -> bool:
    prefix = content[:8192].decode("latin-1", errors="ignore").lower()
    return "content-type: multipart/related" in prefix or (
        "mime-version:" in prefix and "content-location:" in prefix and "boundary=" in prefix
    )


def _looks_like_login_page(soup: BeautifulSoup) -> bool:
    password = soup.find("input", attrs={"type": re.compile(r"^password$", re.I)})
    if not password:
        return False
    username = soup.find(
        "input",
        attrs={"name": re.compile(r"user|account|login|name|xh|zjh|number", re.I)},
    )
    return username is not None


def _extract_term(soup: BeautifulSoup) -> tuple[str | None, list[str], list[str]]:
    warnings: list[str] = []
    select = soup.find("select", id=re.compile(r"^xnxq01id$", re.I))
    if not isinstance(select, Tag):
        return None, [], ["没有找到学期选择框 #xnxq01id，请通过 --term 指定学期。"]

    options = [item for item in select.find_all("option") if isinstance(item, Tag)]
    available_terms = []
    for option in options:
        text = normalize_text(option.get_text(" ", strip=True))
        if text and text not in available_terms:
            available_terms.append(text)

    selected = next((item for item in options if item.has_attr("selected")), None)
    if selected is None and select.get("value"):
        selected = next((item for item in options if item.get("value") == select.get("value")), None)
    if selected is None and len(options) == 1:
        selected = options[0]
    if selected is None:
        warnings.append("保存的 HTML 没有记录当前选中学期，请通过 --term 指定。")
        return None, available_terms, warnings

    return normalize_text(selected.get_text(" ", strip=True)) or None, available_terms, warnings


def _header_index(headers: list[str], aliases: Iterable[str]) -> int | None:
    for index, header in enumerate(headers):
        compact = re.sub(r"\s+", "", header)
        if any(alias in compact for alias in aliases):
            return index
    return None


def _detail_column_map(header_cells: list[Tag], width: int) -> dict[str, int | None]:
    headers = [normalize_text(cell.get_text(" ", strip=True)) for cell in header_cells]
    mapped = {
        "course_code": _header_index(headers, ["课程编号", "课程代码", "课程号"]),
        "class_no": _header_index(headers, ["课序号", "教学班号", "班号"]),
        "course_name": _header_index(headers, ["课程名称", "课程名"]),
        "teacher": _header_index(headers, ["授课教师", "任课教师", "教师"]),
        "time": _header_index(headers, ["上课时间", "时间"]),
        "credit": _header_index(headers, ["学分"]),
        "location": _header_index(headers, ["上课地点", "教室", "地点"]),
        "course_attribute": _header_index(headers, ["课程属性"]),
        "selection_stage": _header_index(headers, ["选课阶段", "选课状态"]),
    }
    if mapped["course_name"] is not None and mapped["time"] is not None:
        return mapped
    if width >= 10:
        return {
            "course_code": 1,
            "class_no": 2,
            "course_name": 3,
            "teacher": 4,
            "time": 5,
            "credit": 6,
            "location": 7,
            "course_attribute": 8,
            "selection_stage": 9,
        }
    return mapped


def _cell_text(cells: list[Tag], index: int | None) -> str:
    if index is None or index < 0 or index >= len(cells):
        return ""
    return normalize_text(cells[index].get_text(" ", strip=True))


def _cell_lines(cells: list[Tag], index: int | None) -> list[str]:
    if index is None or index < 0 or index >= len(cells):
        return []
    return [
        normalize_text(line)
        for line in cells[index].get_text("\n", strip=True).splitlines()
        if normalize_text(line)
    ]


def _parse_schedule_details(soup: BeautifulSoup) -> tuple[dict[str, list[CourseDetailRow]], bool]:
    detail_table = soup.find(id=re.compile(r"^dataList$", re.I))
    if not isinstance(detail_table, Tag):
        return {}, False
    rows = detail_table.find_all("tr")
    if not rows:
        return {}, True

    header_cells = rows[0].find_all(["th", "td"])
    first_data_cells = rows[1].find_all("td") if len(rows) > 1 else []
    column_map = _detail_column_map(header_cells, len(first_data_cells))
    result: dict[str, list[CourseDetailRow]] = {}

    for row in rows[1:]:
        cells = [cell for cell in row.find_all("td", recursive=False) if isinstance(cell, Tag)]
        if not cells:
            cells = [cell for cell in row.find_all("td") if isinstance(cell, Tag)]
        course_name = _cell_text(cells, column_map["course_name"])
        if not course_name:
            continue

        time_lines = _cell_lines(cells, column_map["time"])
        location_text = _cell_text(cells, column_map["location"])
        locations = [normalize_text(item) for item in re.split(r"[,，;；\n]+", location_text) if normalize_text(item)]
        segments: list[CourseTimeSegment] = []
        for index, time_line in enumerate(time_lines):
            location = locations[index] if index < len(locations) else (locations[0] if len(locations) == 1 else None)
            segment = parse_time_segment_text(time_line, location)
            if segment:
                segments.append(segment)

        detail = CourseDetailRow(
            course_code=_cell_text(cells, column_map["course_code"]) or None,
            class_no=_cell_text(cells, column_map["class_no"]) or None,
            course_name=course_name,
            teacher=_cell_text(cells, column_map["teacher"]) or None,
            segments=segments,
            credit=_cell_text(cells, column_map["credit"]) or None,
            course_attribute=_cell_text(cells, column_map["course_attribute"]) or None,
            selection_stage=_cell_text(cells, column_map["selection_stage"]) or None,
        )
        result.setdefault(course_name, []).append(detail)
    return result, True


def _prefixed_value(lines: list[str], labels: Iterable[str]) -> str | None:
    for line in lines:
        for label in labels:
            match = re.match(rf"^{re.escape(label)}\s*[:：]\s*(.+)$", line)
            if match:
                return normalize_text(match.group(1)) or None
    return None


def _iter_cell_segments(div: Tag) -> list[dict[str, str | None]]:
    segments: list[dict[str, str | None]] = []
    chunks = [chunk.strip() for chunk in re.split(r"-{5,}", div.decode_contents()) if chunk.strip()]

    for chunk in chunks:
        fragment = BeautifulSoup(chunk, "html.parser")
        lines = [
            normalize_text(line)
            for line in fragment.get_text("\n", strip=True).splitlines()
            if normalize_text(line)
        ]
        if not lines:
            continue
        current: dict[str, str | None] = {
            "course_name": lines[0],
            "teacher": None,
            "week_text": None,
            "location": None,
            "group_name": None,
        }

        for child in fragment.find_all(["font", "span"]):
            label = normalize_text(child.get("title") or child.get("data-title"))
            value = normalize_text(child.get_text(" ", strip=True))
            if "老师" in label or "教师" in label:
                current["teacher"] = value
            elif "周次" in label:
                current["week_text"] = value
            elif "教室" in label or "地点" in label:
                current["location"] = value
            elif "分组" in label:
                current["group_name"] = value

        current["teacher"] = current["teacher"] or _prefixed_value(lines[1:], ["教师", "老师"])
        current["week_text"] = current["week_text"] or _prefixed_value(lines[1:], ["周次"])
        current["location"] = current["location"] or _prefixed_value(lines[1:], ["地点", "教室"])
        course_name = normalize_text(current["course_name"])
        if course_name:
            current["course_name"] = course_name
            segments.append(current)
    return segments


def _detail_match_score(item: dict, detail: CourseDetailRow, segment: CourseTimeSegment) -> int:
    score = 0
    teacher = item.get("teacher")
    location = item.get("location")
    if teacher and detail.teacher and teacher in detail.teacher:
        score += 4
    if location and segment.location and location == segment.location:
        score += 6
    elif location and segment.location and location in segment.location:
        score += 4
    return score


def _matching_order_key(item: dict) -> tuple:
    return (
        item["course_name"],
        item["weekday"],
        item["block_start"],
        item["block_end"],
        item["week_text"],
        item.get("teacher") or "",
        item.get("location") or "",
    )


def _assign_detail_segments(
    merged_entries: list[dict],
    detail_map: dict[str, list[CourseDetailRow]],
) -> list[tuple[dict, CourseDetailRow | None, CourseTimeSegment | None]]:
    assignments: list[tuple[dict, CourseDetailRow | None, CourseTimeSegment | None]] = []
    grouped_entries: dict[str, list[dict]] = {}
    for item in merged_entries:
        grouped_entries.setdefault(item["course_name"], []).append(item)

    for course_name, course_items in grouped_entries.items():
        candidates: list[tuple[CourseDetailRow, CourseTimeSegment]] = []
        for detail in detail_map.get(course_name, []):
            for segment in detail.segments:
                candidates.append((detail, segment))

        used_indices: set[int] = set()
        for item in sorted(course_items, key=_matching_order_key):
            same_weekday = [
                (index, detail, segment)
                for index, (detail, segment) in enumerate(candidates)
                if index not in used_indices and segment.weekday == item["weekday"]
            ]
            if same_weekday:
                chosen_index, detail, segment = max(
                    same_weekday,
                    key=lambda entry: (_detail_match_score(item, entry[1], entry[2]), -entry[0]),
                )
                used_indices.add(chosen_index)
                assignments.append((item, detail, segment))
                continue

            fallback = next(
                (
                    (detail, segment)
                    for detail, segment in candidates
                    if segment.weekday == item["weekday"]
                ),
                (None, None),
            )
            assignments.append((item, fallback[0], fallback[1]))

    return sorted(assignments, key=lambda entry: _matching_order_key(entry[0]))


def _occurrence_key(item: ScheduleOccurrence) -> tuple:
    return (
        item.course_code,
        item.class_no,
        item.course_name,
        item.teacher,
        item.weekday,
        item.block_start,
        item.block_end,
        tuple(item.week_numbers),
        item.location,
        item.time_text,
    )


def parse_schedule_html(content: bytes, *, encoding: str | None = None) -> ScheduleParseResult:
    if not content.strip():
        raise ScheduleParseError("输入文件为空。")
    if _looks_like_mhtml(content):
        raise ScheduleParseError("暂不支持 MHTML，请在浏览器中选择“网页，仅 HTML”后重新保存。")

    try:
        soup = BeautifulSoup(content, "html.parser", from_encoding=encoding)
    except LookupError as exc:
        raise ScheduleParseError(f"未知字符编码: {encoding}") from exc

    schedule_table = soup.find(id=re.compile(r"^kbtable$", re.I))
    if not isinstance(schedule_table, Tag):
        if _looks_like_login_page(soup):
            raise ScheduleParseError("输入文件是登录页面，不是课表页面。请登录后打开课表并保存该页面。")
        raise ScheduleParseError("没有找到课表表格 #kbtable；页面格式可能不受支持。")

    term, available_terms, warnings = _extract_term(soup)
    detail_map, found_detail_table = _parse_schedule_details(soup)
    if not found_detail_table:
        warnings.append("没有找到课程明细表 #dataList，课程编号、学分或精确节次可能缺失。")
    elif not detail_map:
        warnings.append("课程明细表存在，但没有识别出有效课程行。")

    raw_entries: list[dict] = []
    block_index = 0
    for row in schedule_table.find_all("tr"):
        header = row.find("th")
        cells = [cell for cell in row.find_all("td", recursive=False) if isinstance(cell, Tag)]
        if not header or not cells:
            continue
        block_index += 1
        block_label = normalize_text(header.get_text(" ", strip=True)) or str(block_index)
        for weekday_index, cell in enumerate(cells[:7], start=1):
            detail_div = cell.select_one("div.kbcontent")
            if not isinstance(detail_div, Tag):
                continue
            for segment in _iter_cell_segments(detail_div):
                course_name = normalize_text(segment.get("course_name"))
                if not course_name:
                    continue
                week_text = normalize_text(segment.get("week_text"))
                raw_entries.append(
                    {
                        "course_name": course_name,
                        "teacher": normalize_text(segment.get("teacher")) or None,
                        "week_text": week_text,
                        "week_numbers": parse_week_numbers(week_text),
                        "location": normalize_text(segment.get("location")) or None,
                        "weekday": weekday_index,
                        "weekday_label": f"星期{'一二三四五六日'[weekday_index - 1]}",
                        "block_index": block_index,
                        "block_label": block_label,
                    }
                )

    raw_entries.sort(
        key=lambda item: (
            item["course_name"],
            item.get("teacher") or "",
            item.get("location") or "",
            item["weekday"],
            item["week_text"],
            item["block_index"],
        )
    )
    merged_entries: list[dict] = []
    for entry in raw_entries:
        if not merged_entries:
            merged_entries.append({**entry, "block_start": entry["block_index"], "block_end": entry["block_index"]})
            continue
        previous = merged_entries[-1]
        same_key = all(
            previous[key] == entry[key]
            for key in ["course_name", "teacher", "location", "weekday", "week_text", "weekday_label"]
        )
        if same_key and previous["block_end"] + 1 == entry["block_index"]:
            previous["block_end"] = entry["block_index"]
            previous["block_label_end"] = entry["block_label"]
        else:
            merged_entries.append({**entry, "block_start": entry["block_index"], "block_end": entry["block_index"]})

    entries: list[ScheduleOccurrence] = []
    for item, detail, detail_segment in _assign_detail_segments(merged_entries, detail_map):
        block_start = detail_segment.start_section if detail_segment and detail_segment.start_section else item["block_start"]
        block_end = detail_segment.end_section if detail_segment and detail_segment.end_section else item["block_end"]
        entries.append(
            ScheduleOccurrence(
                course_code=detail.course_code if detail else None,
                class_no=detail.class_no if detail else None,
                course_name=item["course_name"],
                teacher=item.get("teacher") or (detail.teacher if detail else None),
                weekday=item["weekday"],
                weekday_label=item["weekday_label"],
                block_start=block_start,
                block_end=block_end,
                block_label_start=str(detail_segment.start_section) if detail_segment else item["block_label"],
                block_label_end=(
                    str(detail_segment.end_section)
                    if detail_segment
                    else item.get("block_label_end", item["block_label"])
                ),
                time_text=(
                    detail_segment.time_text
                    if detail_segment
                    else f"{item['weekday_label']} {item['block_label']}"
                ),
                week_text=item["week_text"],
                week_numbers=item["week_numbers"],
                location=item.get("location") or (detail_segment.location if detail_segment else None),
                credit=detail.credit if detail else None,
                course_attribute=detail.course_attribute if detail else None,
                selection_stage=detail.selection_stage if detail else None,
            )
        )

    deduped: list[ScheduleOccurrence] = []
    seen: set[tuple] = set()
    for entry in entries:
        key = _occurrence_key(entry)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    missing_weeks = [entry.course_name for entry in deduped if not entry.week_numbers]
    if missing_weeks:
        preview = "、".join(dict.fromkeys(missing_weeks[:3]))
        warnings.append(f"有 {len(missing_weeks)} 条课程未识别出周次（例如：{preview}）。")
    if not deduped:
        warnings.append("课表结构已识别，但没有解析出课程。")

    return ScheduleParseResult(
        term=term,
        available_terms=available_terms,
        entries=deduped,
        source_encoding=soup.original_encoding,
        warnings=warnings,
    )
