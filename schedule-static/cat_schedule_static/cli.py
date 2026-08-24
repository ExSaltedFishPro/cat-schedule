from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from cat_schedule_static import __version__
from cat_schedule_static.models import ScheduleBuildError, ScheduleParseError, ScheduleParseResult
from cat_schedule_static.parser import parse_schedule_html
from cat_schedule_static.payload import build_schedule_document
from cat_schedule_static.renderer import render_schedule_html


def _read_and_parse(path: Path, encoding: str | None) -> tuple[bytes, ScheduleParseResult]:
    if not path.is_file():
        raise ScheduleParseError(f"输入文件不存在或不是普通文件: {path}")
    content = path.read_bytes()
    return content, parse_schedule_html(content, encoding=encoding)


def _validate_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ScheduleBuildError("--term-start 必须是 YYYY-MM-DD，例如 2026-09-07。") from exc
    if parsed.weekday() != 0:
        raise ScheduleBuildError("--term-start 必须是第一周的周一。")
    return parsed.isoformat()


def _ensure_output_available(path: Path, *, force: bool) -> None:
    if path.exists() and not force:
        raise ScheduleBuildError(f"输出文件已存在: {path}；如需覆盖请添加 --force。")


def _atomic_write(path: Path, content: str, *, force: bool) -> None:
    _ensure_output_available(path, force=force)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(content)
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _summary(parsed: ScheduleParseResult) -> dict:
    weeks = sorted({week for entry in parsed.entries for week in entry.week_numbers})
    return {
        "term": parsed.term,
        "available_terms": parsed.available_terms,
        "source_encoding": parsed.source_encoding,
        "entry_count": len(parsed.entries),
        "week_numbers": weeks,
        "incomplete_entry_count": sum(not entry.week_numbers for entry in parsed.entries),
        "warnings": parsed.warnings,
    }


def inspect_command(args: argparse.Namespace) -> int:
    _, parsed = _read_and_parse(args.input, args.encoding)
    summary = _summary(parsed)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"输入文件: {args.input}")
    print(f"字符编码: {summary['source_encoding'] or '未知'}")
    print(f"当前学期: {summary['term'] or '未识别'}")
    print(f"课程记录: {summary['entry_count']}")
    print(f"已识别周次: {', '.join(map(str, summary['week_numbers'])) or '无'}")
    if summary["warnings"]:
        print("警告:")
        for warning in summary["warnings"]:
            print(f"  - {warning}")
    return 0


def build_command(args: argparse.Namespace) -> int:
    content, parsed = _read_and_parse(args.input, args.encoding)
    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        raise ScheduleBuildError("输出文件不能覆盖输入课表 HTML。")

    json_path = args.data_output.resolve() if args.data_output else None
    if json_path and json_path in {input_path, output_path}:
        raise ScheduleBuildError("--data-output 必须与输入文件和 HTML 输出文件不同。")
    _ensure_output_available(args.output, force=args.force)
    if args.data_output:
        _ensure_output_available(args.data_output, force=args.force)

    document = build_schedule_document(
        parsed,
        source_sha256=hashlib.sha256(content).hexdigest(),
        term=args.term,
        term_start_date=_validate_date(args.term_start),
        title=args.title,
        allow_empty=args.allow_empty,
        allow_incomplete=args.allow_incomplete,
    )
    rendered = render_schedule_html(document)
    _atomic_write(args.output, rendered, force=args.force)
    if args.data_output:
        _atomic_write(
            args.data_output,
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            force=args.force,
        )

    print(f"已生成单文件课表: {args.output}")
    if args.data_output:
        print(f"已生成结构化数据: {args.data_output}")
    print(f"学期: {document['schedule']['term']}，课程记录: {document['schedule']['total_entries']}")
    for warning in document["warnings"]:
        print(f"警告: {warning}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cat-schedule-static",
        description="把手动保存的教务处课表 HTML 转换成可由 Nginx 托管的单文件课表。",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="检查 HTML 是否可解析，不生成文件")
    inspect_parser.add_argument("input", type=Path, help="浏览器保存的课表 HTML")
    inspect_parser.add_argument("--encoding", help="强制指定输入字符编码，例如 gb18030")
    inspect_parser.add_argument("--json", action="store_true", help="以 JSON 输出检查结果")
    inspect_parser.set_defaults(handler=inspect_command)

    build_parser = subparsers.add_parser("build", help="生成单文件静态课表")
    build_parser.add_argument("input", type=Path, help="浏览器保存的课表 HTML")
    build_parser.add_argument("-o", "--output", type=Path, default=Path("index.html"), help="HTML 输出路径")
    build_parser.add_argument("--data-output", type=Path, help="可选：同时输出结构化 JSON")
    build_parser.add_argument("--term", help="覆盖或补充学期名称，例如 2026-2027-1")
    build_parser.add_argument("--term-start", help="第一周周一，格式 YYYY-MM-DD")
    build_parser.add_argument("--title", default="C.A.T. Schedule", help="页面标题")
    build_parser.add_argument("--encoding", help="强制指定输入字符编码，例如 gb18030")
    build_parser.add_argument("--allow-empty", action="store_true", help="允许生成没有课程的空课表")
    build_parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="允许未识别周次的课程，并放入“周次未识别”视图",
    )
    build_parser.add_argument("--force", action="store_true", help="覆盖已有输出文件")
    build_parser.set_defaults(handler=build_command)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        exit_code = args.handler(args)
    except (ScheduleParseError, ScheduleBuildError, OSError) as exc:
        parser.exit(2, f"错误: {exc}\n")
    raise SystemExit(exit_code)
