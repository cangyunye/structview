"""表格视图：每行一条记录，字段为列。"""

from __future__ import annotations

from rich import box
from rich.table import Table as RichTable
from rich.text import Text

from .. import models

_RIGHT_TYPES = {"int", "dec"}


def show_table(console: Console, res: models.ParseResult, raw_mode: bool = False) -> None:
    if not res.records:
        console.print(Text("（无记录）", style="dim"))
        return
    first = res.records[0]
    t = RichTable(box=box.MINIMAL_HEAVY_HEAD, header_style="bold cyan",
                  padding=(0, 1))
    t.add_column("#", justify="right", style="dim")
    for f in first.fields:
        justify = "right" if (not raw_mode and f.type in _RIGHT_TYPES) else "left"
        t.add_column(f.name, justify=justify)
    for r in res.records:
        row_style = "yellow" if r.warning else None
        cells: list = [str(r.index)]
        for f in r.fields:
            value = f.raw.strip() if raw_mode else f.value
            cells.append(Text(value, style="red" if f.error else None))
        t.add_row(*cells, style=row_style)
    console.print(t)
