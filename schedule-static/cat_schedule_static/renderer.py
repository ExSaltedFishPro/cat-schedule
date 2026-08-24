from __future__ import annotations

import html
import json
from importlib.resources import files


DATA_MARKER = "__CAT_SCHEDULE_DATA__"
TITLE_MARKER = "__CAT_SCHEDULE_TITLE__"


def _safe_embedded_json(payload: dict) -> str:
    value = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        value.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_schedule_html(document: dict) -> str:
    template = files("cat_schedule_static").joinpath("template.html").read_text(encoding="utf-8")
    if template.count(DATA_MARKER) != 1 or template.count(TITLE_MARKER) != 1:
        raise RuntimeError("内置页面模板占位符无效。")
    rendered = template.replace(DATA_MARKER, _safe_embedded_json(document), 1)
    rendered = rendered.replace(TITLE_MARKER, html.escape(str(document.get("page_title") or "C.A.T. Schedule")), 1)
    return rendered
