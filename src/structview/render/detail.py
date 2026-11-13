"""详情视图：每条记录一个字段块，展示原始值与解析值对照。"""

from __future__ import annotations

from rich import box
from rich.table import Table as RichTable
from rich.text import Text

from .. import models
from ..fields import visible


def show_detail(console: Console, res: models.ParseResult, raw_mode: bool = False) -> None:
    if not res.records:
        console.print(Text("（无记录）", style="dim"))
        return
    total = len(res.records)
    fixed = res.records[0].fields[0].offset is not None
    for r in res.records:
        head = Text(f"记录 {r.index}/{total}", style="bold")
        if r.line_no is not None:
            head.append(f"  (行 {r.line_no})", style="dim")
        console.print(head)
        if r.warning:
            console.print(Text(f"⚠ {r.warning}", style="yellow"))
        t = RichTable(box=box.SIMPLE, show_edge=False, padding=(0, 1))
        t.add_column("#", justify="right", style="dim")
        t.add_column("字段", style="bold")
        if fixed:
            t.add_column("字节", justify="right", style="dim")
        t.add_column("原始值", style="dim")
        t.add_column("解析值")
        for j, f in enumerate(r.fields, 1):
            raw_txt = Text(visible(f.raw) if f.raw else "")
            style = "red" if f.error else None
            if raw_mode:
                val = Text(f.raw.strip(), style=style)
            else:
                val = Text(f.value, style=style)
                if f.error:
                    val.append(f"  ⚠ {f.error}", style="dim red")
            cells: list = [str(j), Text(f.name)]
            if fixed:
                cells.append(f"{f.offset}-{f.offset + (f.length or 1) - 1}")
            cells += [raw_txt, val]
            t.add_row(*cells)
        console.print(t)
