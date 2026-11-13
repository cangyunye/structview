"""JSON 视图：kv / pretty / embedded 三种形态。

table 形态（扁平对象数组）已在解码层转为 records，复用通用表格视图。
"""

from __future__ import annotations

import json
import re

from rich import box
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table as RichTable
from rich.text import Text

_HEADER_RE = re.compile(r"^(?:HTTP/[\d.]+\b|[A-Za-z][A-Za-z0-9-]*:\s)")


def _dump(obj, indent: int = 2) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=indent, default=str)


def _cell_str(v) -> str:
    if v is None:
        return ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False)


def _syntax(text: str) -> Syntax:
    return Syntax(text, "json", theme="ansi_dark", word_wrap=True,
                  background_color="default")


def show_json(console, res) -> None:
    p = res.payload or {}
    mode = p.get("mode")
    if mode == "kv":
        t = RichTable(box=box.SIMPLE, show_edge=False, padding=(0, 1))
        t.add_column("键", style="bold")
        t.add_column("值")
        for k, v in (p.get("obj") or {}).items():
            t.add_row(Text(str(k)), Text(_cell_str(v)))
        console.print(t)
    elif mode == "pretty":
        for item in p.get("items") or []:
            console.print(_syntax(_dump(item)))
            console.print()
    elif mode == "embedded":
        for blk in p.get("blocks") or []:
            ctx = blk.get("context") or []
            if ctx:
                title = "HTTP 头部 / 上下文" if any(_HEADER_RE.match(ln) for ln in ctx) else "上下文"
                console.print(Panel(Text("\n".join(ctx), style="dim"),
                                    title=title, box=box.SIMPLE))
            obj = blk.get("obj")
            if obj is None:
                console.print(Text(blk.get("text", ""), style="red"))
            else:
                console.print(_syntax(_dump(obj)))
            console.print()
