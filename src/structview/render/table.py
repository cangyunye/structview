"""表格视图：每行一条记录，字段为列。

字段数超过 per_line 时按字段分段打印：每段独立成表（列名正确、列宽不被挤压），
续段标题注明字段范围，# 记录序号在各段重复，表明各段属于同一文件行的同一记录。
"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table as RichTable
from rich.text import Text

from .. import models
from . import type_style

_RIGHT_TYPES = {"int", "dec"}


def show_table(console: Console, res: models.ParseResult, raw_mode: bool = False,
               per_line: int = 10) -> None:
    if not res.records:
        console.print(Text("（无记录）", style="dim"))
        return
    first = res.records[0]
    n = len(first.fields)
    if not per_line or per_line <= 0 or n <= per_line:
        _show_block(console, res, raw_mode, first, 0, n)
        return
    for s in range(0, n, per_line):
        e = min(s + per_line, n)
        if s:
            console.print()
            console.print(Text(f"── 接上 · 字段 {s + 1}-{e}/{n}（# 同上，同一批记录）",
                               style="cyan"))
        _show_block(console, res, raw_mode, first, s, e)


def _show_block(console: Console, res: models.ParseResult, raw_mode: bool,
                first: models.Record, s: int, e: int) -> None:
    t = RichTable(box=box.MINIMAL_HEAVY_HEAD, header_style="bold cyan",
                  padding=(0, 1))
    t.add_column("#", justify="right", style="dim")
    for f in first.fields[s:e]:
        justify = "right" if (not raw_mode and f.type in _RIGHT_TYPES) else "left"
        t.add_column(f.name, justify=justify)
    for r in res.records:
        if s >= len(r.fields):
            continue
        row_style = "yellow" if r.warning else None
        cells: list = [str(r.index)]
        for f in r.fields[s:e]:
            value = f.raw.strip() if raw_mode else f.value
            cells.append(Text(value, style="red" if f.error else type_style(f.type)))
        t.add_row(*cells, style=row_style)
    console.print(t)
