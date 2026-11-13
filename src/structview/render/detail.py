"""详情视图：每条记录一个字段块，展示解析值（含实际字节数）与类型/偏移等协议元信息。"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table as RichTable
from rich.text import Text

from .. import models
from . import type_style


def _type_desc(f: models.Field) -> str:
    """类型列：定长带协议字节长度 str(8)，dec 追加小数位 dec(7,5)；变长仅 dec 显示 scale dec(2)。"""
    t = f.type or "str"
    if f.name == "…尾料":
        return t  # 尾料是行溢出内容，length 只是实测大小，不是协议长度
    if f.length:
        if t == "dec" and f.scale:
            return f"{t}({f.length},{f.scale})"
        return f"{t}({f.length})"
    if t == "dec" and f.scale:
        return f"{t}({f.scale})"
    return t


def _value_cell(f: models.Field, encoding: str, raw_mode: bool) -> Text:
    """解析值列：值(实际字节数)，按数据类型着色；解析错误标红，--raw 时回退原始串。"""
    shown = f.raw.strip() if raw_mode else f.value
    err_style = "red" if f.error else type_style(f.type)
    val = Text(shown, style=err_style)
    try:
        n = len(f.raw.strip().encode(encoding or "utf-8", errors="replace"))
    except LookupError:
        n = len(f.raw.strip())
    val.append(f"({n})", style="dim red" if f.error else "dim")
    if f.error and not raw_mode:
        val.append(f"  ⚠ {f.error}", style="dim red")
    return val


def show_detail(console: Console, res: models.ParseResult, raw_mode: bool = False) -> None:
    if not res.records:
        console.print(Text("（无记录）", style="dim"))
        return
    total = len(res.records)
    fixed = any(f.offset is not None for f in res.records[0].fields)
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
        t.add_column("解析值")
        t.add_column("类型")
        if fixed:
            t.add_column("偏移", style="dim")
        for j, f in enumerate(r.fields, 1):
            cells: list = [str(j), Text(f.name),
                           _value_cell(f, res.encoding, raw_mode),
                           Text(_type_desc(f), style=type_style(f.type))]
            if fixed:
                rng = (f"[{f.offset},{f.offset + (f.length or 0)})"
                       if f.offset is not None else "")
                cells.append(Text(rng))
            t.add_row(*cells)
        console.print(t)
