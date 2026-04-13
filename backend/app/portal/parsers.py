from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag


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


@dataclass
class LoginFormMeta:
    action: str
    method: str
    username_field: str
    password_field: str
    captcha_field: str
    hidden_fields: dict[str, str]
    captcha_image_url: str | None


@dataclass
class CourseTimeSegment:
    weekday: int
    weekday_label: str
    start_section: int | None
    end_section: int | None
    time_text: str
    location: str | None = None


@dataclass
class CourseDetailRow:
    course_code: str | None
    class_no: str | None
    course_name: str
    teacher: str | None
    segments: list[CourseTimeSegment]
    credit: str | None
    course_attribute: str | None
    selection_stage: str | None


@dataclass
class ScheduleOccurrence:
    course_code: str | None
    class_no: str | None
    course_name: str
    teacher: str | None
    weekday: int
    weekday_label: str
    block_start: int
    block_end: int
    block_label_start: str
    block_label_end: str
    time_text: str
    week_text: str
    week_numbers: list[int]
    location: str | None
    credit: str | None
    course_attribute: str | None
    selection_stage: str | None
    raw_payload: dict


@dataclass
class LessonsParseResult:
    term: str | None
    available_terms: list[str]
    entries: list[ScheduleOccurrence]
    raw_summary: dict


@dataclass
class GradeItemParsed:
    record_key: str
    term: str
    course_code: str | None
    course_name: str
    score: str | None
    score_numeric: float | None
    score_flag: str | None
    grade_point_text: str | None
    credit: str | None
    total_hours: str | None
    assessment_method: str | None
    course_attribute: str | None
    course_nature: str | None
    raw_payload: dict


@dataclass
class GradesParseResult:
    items: list[GradeItemParsed]
    raw_summary: dict


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _input_key(input_tag: Tag) -> str:
    return (input_tag.get("name") or input_tag.get("id") or "").strip()


def _matches_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def parse_login_form(html: str) -> LoginFormMeta:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if not form:
        raise ValueError("Portal login form not found")

    hidden_fields: dict[str, str] = {}
    visible_inputs: list[Tag] = []

    for input_tag in form.find_all("input"):
        input_name = _input_key(input_tag)
        if not input_name:
            continue
        input_type = (input_tag.get("type") or "text").lower()
        if input_type == "hidden":
            hidden_fields[input_name] = input_tag.get("value", "")
            continue
        if input_type in {"submit", "button", "reset", "image", "checkbox", "radio"}:
            continue
        visible_inputs.append(input_tag)

    password_input = next((item for item in visible_inputs if (item.get("type") or "text").lower() == "password"), None)
    captcha_input = next(
        (
            item
            for item in visible_inputs
            if _matches_any(_input_key(item), ["captcha", "randomcode", "verify", "safecode", "checkcode", "rand"])
        ),
        None,
    )
    if not captcha_input:
        captcha_input = next(
            (
                item
                for item in visible_inputs
                if item is not password_input and item.find_parent("td") and item.find_parent("td").find("img")
            ),
            None,
        )

    username_input = next(
        (
            item
            for item in visible_inputs
            if item is not password_input and item is not captcha_input
            and _matches_any(_input_key(item), ["user", "account", "login", "name", "xh", "zjh", "number"])
        ),
        None,
    )
    if not username_input:
        username_input = next(
            (item for item in visible_inputs if item is not password_input and item is not captcha_input),
            None,
        )

    captcha_img = (
        form.find("img", id=re.compile("safecode", re.I))
        or form.find("img", src=re.compile("verify|captcha|safecode|randomcode", re.I))
        or soup.find("img", id=re.compile("safecode", re.I))
        or soup.find("img", src=re.compile("verify|captcha|safecode|randomcode", re.I))
    )

    return LoginFormMeta(
        action=form.get("action") or "/",
        method=(form.get("method") or "post").upper(),
        username_field=_input_key(username_input) or "USERNAME",
        password_field=_input_key(password_input) or "PASSWORD",
        captcha_field=_input_key(captcha_input) or "RANDOMCODE",
        hidden_fields=hidden_fields,
        captcha_image_url=captcha_img.get("src") if captcha_img else None,
    )


def is_login_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.find("input", attrs={"name": "USERNAME"})) and bool(
        soup.find("input", attrs={"name": "PASSWORD"})
    )


def extract_login_error(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    red_font = soup.find("font", attrs={"color": "red"})
    if red_font:
        value = normalize_text(red_font.get_text(" ", strip=True))
        if value:
            return value
    return None


def parse_week_numbers(week_text: str) -> list[int]:
    body = normalize_text(week_text).replace("(周)", "").replace("周", "")
    if not body:
        return []
    weeks: set[int] = set()
    for token in re.split(r"[，,]", body):
        token = token.strip()
        if not token:
            continue
        odd_only = "单" in token
        even_only = "双" in token
        token = token.replace("单", "").replace("双", "")
        range_match = re.match(r"(\d+)-(\d+)", token)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            for value in range(start, end + 1):
                if odd_only and value % 2 == 0:
                    continue
                if even_only and value % 2 == 1:
                    continue
                weeks.add(value)
            continue
        if token.isdigit():
            value = int(token)
            if odd_only and value % 2 == 0:
                continue
            if even_only and value % 2 == 1:
                continue
            weeks.add(value)
    return sorted(weeks)


def parse_time_segment_text(time_text: str, location: str | None) -> CourseTimeSegment | None:
    time_text = normalize_text(time_text)
    match = re.search(r"星期([一二三四五六日天])\((\d{2})-(\d{2})小节\)", time_text)
    if not match:
        return None
    weekday, weekday_label = WEEKDAY_MAP[match.group(1)]
    return CourseTimeSegment(
        weekday=weekday,
        weekday_label=weekday_label,
        start_section=int(match.group(2)),
        end_section=int(match.group(3)),
        time_text=time_text,
        location=normalize_text(location) or None,
    )


def _parse_schedule_details(soup: BeautifulSoup) -> dict[str, list[CourseDetailRow]]:
    rows = soup.select("#dataList tr")
    result: dict[str, list[CourseDetailRow]] = {}
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 10:
            continue
        course_name = normalize_text(cells[3].get_text(" ", strip=True))
        teacher = normalize_text(cells[4].get_text(" ", strip=True)) or None
        time_lines = [
            normalize_text(chunk)
            for chunk in cells[5].get_text("\n", strip=True).split("\n")
            if normalize_text(chunk)
        ]
        location_values = [normalize_text(item) for item in (cells[7].get_text(" ", strip=True) or "").split(",")]
        segments: list[CourseTimeSegment] = []
        for index, time_line in enumerate(time_lines):
            location = location_values[index] if index < len(location_values) else None
            parsed = parse_time_segment_text(time_line, location)
            if parsed:
                segments.append(parsed)
        detail = CourseDetailRow(
            course_code=normalize_text(cells[1].get_text(" ", strip=True)) or None,
            class_no=normalize_text(cells[2].get_text(" ", strip=True)) or None,
            course_name=course_name,
            teacher=teacher,
            segments=segments,
            credit=normalize_text(cells[6].get_text(" ", strip=True)) or None,
            course_attribute=normalize_text(cells[8].get_text(" ", strip=True)) or None,
            selection_stage=normalize_text(cells[9].get_text(" ", strip=True)) or None,
        )
        result.setdefault(course_name, []).append(detail)
    return result


def _finalize_segment(current: dict[str, str | None], target: list[dict[str, str | None]]) -> None:
    course_name = normalize_text(current.get("course_name"))
    if not course_name:
        return
    target.append(
        {
            "course_name": course_name,
            "teacher": normalize_text(current.get("teacher")) or None,
            "week_text": normalize_text(current.get("week_text")) or "",
            "location": normalize_text(current.get("location")) or None,
            "group_name": normalize_text(current.get("group_name")) or None,
        }
    )


def _iter_cell_segments(div: Tag) -> list[dict[str, str | None]]:
    segments: list[dict[str, str | None]] = []
    raw_html = div.decode_contents()
    chunks = [chunk.strip() for chunk in re.split(r"-{5,}", raw_html) if chunk.strip()]

    for chunk in chunks:
        fragment = BeautifulSoup(chunk, "html.parser")
        current: dict[str, str | None] = {}
        all_lines = [normalize_text(line) for line in fragment.get_text("\n", strip=True).split("\n") if normalize_text(line)]
        if all_lines:
            current["course_name"] = all_lines[0]

        for child in fragment.find_all("font"):
            label = normalize_text(child.get("title"))
            value = normalize_text(child.get_text(" ", strip=True))
            if "老师" in label:
                current["teacher"] = value
            elif "周次" in label:
                current["week_text"] = value
            elif "教室" in label:
                current["location"] = value
            elif "分组" in label:
                current["group_name"] = value

        _finalize_segment(current, segments)

    return segments


def _match_detail(
    course_name: str,
    teacher: str | None,
    location: str | None,
    weekday: int,
    detail_map: dict[str, list[CourseDetailRow]],
) -> tuple[CourseDetailRow | None, CourseTimeSegment | None]:
    best_detail: CourseDetailRow | None = None
    best_segment: CourseTimeSegment | None = None
    best_score = -1
    for detail in detail_map.get(course_name, []):
        for segment in detail.segments:
            if segment.weekday != weekday:
                continue
            score = 0
            if teacher and detail.teacher and teacher in detail.teacher:
                score += 2
            if location and segment.location and location == segment.location:
                score += 3
            elif location and segment.location and location in segment.location:
                score += 2
            if score > best_score:
                best_score = score
                best_detail = detail
                best_segment = segment
    return best_detail, best_segment


def _detail_match_score(
    item: dict,
    detail: CourseDetailRow,
    segment: CourseTimeSegment,
) -> int:
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
        item["teacher"] or "",
        item["location"] or "",
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
        candidates: list[tuple[int, CourseDetailRow, CourseTimeSegment]] = []
        for detail_index, detail in enumerate(detail_map.get(course_name, [])):
            for segment in detail.segments:
                candidates.append((detail_index, detail, segment))

        used_indices: set[int] = set()
        for item in sorted(course_items, key=_matching_order_key):
            same_weekday = [
                (index, detail, segment)
                for index, (detail_index, detail, segment) in enumerate(candidates)
                if index not in used_indices and segment.weekday == item["weekday"]
            ]
            if same_weekday:
                chosen_index, chosen_detail, chosen_segment = max(
                    same_weekday,
                    key=lambda entry: (
                        _detail_match_score(item, entry[1], entry[2]),
                        -entry[0],
                    ),
                )
                used_indices.add(chosen_index)
                assignments.append((item, chosen_detail, chosen_segment))
                continue

            detail, detail_segment = _match_detail(
                item["course_name"],
                item["teacher"],
                item["location"],
                item["weekday"],
                detail_map,
            )
            assignments.append((item, detail, detail_segment))

    assignments.sort(key=lambda entry: _matching_order_key(entry[0]))
    return assignments


def _section_label(value: int | None, fallback: str) -> str:
    return str(value) if value is not None else fallback


def _occurrence_dedupe_key(item: ScheduleOccurrence) -> tuple:
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


def parse_lessons_html(html: str) -> LessonsParseResult:
    soup = BeautifulSoup(html, "html.parser")
    selected_term_option = soup.select_one("#xnxq01id option[selected]")
    term = normalize_text(selected_term_option.get_text(strip=True)) if selected_term_option else None
    available_terms = [normalize_text(option.get_text(strip=True)) for option in soup.select("#xnxq01id option")]
    detail_map = _parse_schedule_details(soup)
    grid_rows = soup.select("#kbtable tr")[1:]

    raw_entries: list[dict] = []
    for row_index, row in enumerate(grid_rows, start=1):
        header = row.find("th")
        if not header:
            continue
        block_label = normalize_text(header.get_text(" ", strip=True))
        cells = row.find_all("td")
        for weekday_index, cell in enumerate(cells, start=1):
            detail_div = cell.find("div", class_="kbcontent")
            if not detail_div:
                continue
            for segment in _iter_cell_segments(detail_div):
                if not segment["course_name"]:
                    continue
                raw_entries.append(
                    {
                        "course_name": segment["course_name"],
                        "teacher": segment["teacher"],
                        "week_text": segment["week_text"],
                        "week_numbers": parse_week_numbers(segment["week_text"] or ""),
                        "location": segment["location"],
                        "weekday": weekday_index,
                        "weekday_label": f"星期{'一二三四五六日'[weekday_index - 1]}",
                        "block_index": row_index,
                        "block_label": block_label,
                    }
                )

    raw_entries.sort(
        key=lambda item: (
            item["course_name"],
            item["teacher"] or "",
            item["location"] or "",
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
        block_start = detail_segment.start_section if detail_segment and detail_segment.start_section is not None else item["block_start"]
        block_end = detail_segment.end_section if detail_segment and detail_segment.end_section is not None else item["block_end"]
        entries.append(
            ScheduleOccurrence(
                course_code=detail.course_code if detail else None,
                class_no=detail.class_no if detail else None,
                course_name=item["course_name"],
                teacher=item["teacher"],
                weekday=item["weekday"],
                weekday_label=item["weekday_label"],
                block_start=block_start,
                block_end=block_end,
                block_label_start=_section_label(
                    detail_segment.start_section if detail_segment else None,
                    item["block_label"],
                ),
                block_label_end=_section_label(
                    detail_segment.end_section if detail_segment else None,
                    item.get("block_label_end", item["block_label"]),
                ),
                time_text=detail_segment.time_text if detail_segment else f"{item['weekday_label']} {item['block_label']}",
                week_text=item["week_text"],
                week_numbers=item["week_numbers"],
                location=item["location"] or (detail_segment.location if detail_segment else None),
                credit=detail.credit if detail else None,
                course_attribute=detail.course_attribute if detail else None,
                selection_stage=detail.selection_stage if detail else None,
                raw_payload={
                    "matched_detail": detail.course_code if detail else None,
                    "detail_time_text": detail_segment.time_text if detail_segment else None,
                    "layout_source": "detail_segment" if detail_segment else "grid_row",
                },
            )
        )

    deduped_entries: list[ScheduleOccurrence] = []
    seen_keys: set[tuple] = set()
    for entry in entries:
        dedupe_key = _occurrence_dedupe_key(entry)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)
        deduped_entries.append(entry)

    return LessonsParseResult(
        term=term,
        available_terms=available_terms,
        entries=deduped_entries,
        raw_summary={
            "table_row_count": len(grid_rows),
            "detail_course_count": sum(len(values) for values in detail_map.values()),
            "entry_count": len(deduped_entries),
        },
    )


def parse_grades_html(html: str) -> GradesParseResult:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("#dataList tr")[1:]
    items: list[GradeItemParsed] = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 11:
            continue
        term = normalize_text(cells[1].get_text(" ", strip=True))
        course_code = normalize_text(cells[2].get_text(" ", strip=True)) or None
        course_name = normalize_text(cells[3].get_text(" ", strip=True))
        score = normalize_text(cells[4].get_text(" ", strip=True)) or None
        score_flag = normalize_text(cells[5].get_text(" ", strip=True)) or None
        credit = normalize_text(cells[6].get_text(" ", strip=True)) or None
        total_hours = normalize_text(cells[7].get_text(" ", strip=True)) or None
        assessment_method = normalize_text(cells[8].get_text(" ", strip=True)) or None
        course_attribute = normalize_text(cells[9].get_text(" ", strip=True)) or None
        course_nature = normalize_text(cells[10].get_text(" ", strip=True)) or None
        score_numeric: float | None = None
        if score:
            try:
                score_numeric = float(score)
            except ValueError:
                score_numeric = None
        record_source = "|".join(
            [term, course_code or "", course_name, assessment_method or "", course_attribute or "", course_nature or ""]
        )
        record_key = hashlib.sha256(record_source.encode("utf-8")).hexdigest()
        items.append(
            GradeItemParsed(
                record_key=record_key,
                term=term,
                course_code=course_code,
                course_name=course_name,
                score=score,
                score_numeric=score_numeric,
                score_flag=score_flag,
                grade_point_text=None,
                credit=credit,
                total_hours=total_hours,
                assessment_method=assessment_method,
                course_attribute=course_attribute,
                course_nature=course_nature,
                raw_payload={"raw_columns": [normalize_text(cell.get_text(" ", strip=True)) for cell in cells]},
            )
        )
    return GradesParseResult(items=items, raw_summary={"row_count": len(items)})
