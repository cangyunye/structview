"""渲染入口：头部信息、table/detail/hex 视图与警告汇总。"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from .. import models

FMT_DESC = {
    "fixed": "定长",
    "delimited": "变长分隔符",
    "json": "JSON",
    "generic": "兜底解析",
}


def make_console(no_color: bool = False, stderr: bool = False) -> Console:
    return Console(highlight=False, no_color=no_color, stderr=stderr)


def print_header(console: Console, filename: str, res: models.ParseResult) -> None:
    t = Text()
    t.append(filename, style="bold")
    if res.spec_name:
        t.append(f" · {res.spec_name}")
    desc = FMT_DESC.get(res.fmt, res.fmt)
    if res.delimiter:
        desc += f" {res.delimiter!r}"
    t.append(f" · {desc}")
    t.append(f" · {res.encoding}")
    n = len(res.records)
    if res.fmt == "json" and res.payload:
        n = res.payload.get("count", n)
    t.append(f" · {n} 条记录")
    console.print(t)


def print_notes(console: Console, lines: list[str]) -> None:
    for ln in lines:
        console.print(Text(ln, style="dim"))


def print_warnings(console: Console, warnings: list[str]) -> None:
    if not warnings:
        return
    cap = 30
    for w in warnings[:cap]:
        console.print(Text(f"⚠ {w}", style="yellow"))
    if len(warnings) > cap:
        console.print(Text(f"⚠ …共 {len(warnings)} 条警告", style="yellow"))


def show(res: models.ParseResult, filename: str, view: str = "table",
         data: bytes | None = None, extra_lines: list[str] | None = None,
         no_color: bool = False, raw_mode: bool = False) -> None:
    console = make_console(no_color)
    print_header(console, filename, res)
    print_notes(console, extra_lines or [])

    if res.fmt == "json" and res.payload and res.payload.get("mode") in ("kv", "pretty", "embedded"):
        from .jsonview import show_json
        show_json(console, res)
    elif view == "hex" and data is not None:
        from .hexdump import show_hexdump
        show_hexdump(console, data)
    elif view == "detail":
        from .detail import show_detail
        show_detail(console, res, raw_mode)
    else:
        from .table import show_table
        show_table(console, res, raw_mode)

    print_warnings(console, res.warnings)
