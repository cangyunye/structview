"""渲染入口：头部信息、头/尾段、table/detail/hex 视图与警告汇总。"""

from __future__ import annotations

import os

from rich import box
from rich.console import Console
from rich.table import Table as RichTable
from rich.text import Text

from .. import models

FMT_DESC = {
    "fixed": "定长",
    "delimited": "变长分隔符",
    "json": "JSON",
    "generic": "兜底解析",
}

# 数据类型 → 色彩：table 的值与 detail 的值/类型标签按类型着色，便于扫读。
# str 与未知类型不着色（协议文件里占大头，整屏着色反而看不清），错误红永远优先。
TYPE_STYLES = {
    "int": "blue",
    "dec": "magenta",
    "date": "green",
    "time": "green",
    "hex": "cyan",
    "enum": "yellow",
}


def type_style(t: str | None) -> str | None:
    return TYPE_STYLES.get(t or "str")


LINE_ENDING_LABELS = {"dos": "DOS(CRLF)", "unix": "Unix(LF)", "mac": "Mac(CR)", "mixed": "行尾混用"}


def make_console(no_color: bool | None = None, stderr: bool = False) -> Console:
    # 色彩开关优先级：--no-color 参数 > NO_COLOR 环境变量 > rich 自动检测
    # （非 tty 自动无色，FORCE_COLOR=1 可在管道中强制彩色）。
    # 关闭时显式 color_system=None：连粗体/暗淡这类属性也不输出任何 ANSI 转义，
    # 兼容无法渲染转义序列的终端。
    if no_color or os.environ.get("NO_COLOR"):
        return Console(highlight=False, stderr=stderr, color_system=None)
    return Console(highlight=False, stderr=stderr)


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
    le = LINE_ENDING_LABELS.get(res.line_ending or "")
    if le:
        t.append(f" · {le}", style="dim")
    n = len(res.records)
    if res.fmt == "json" and res.payload:
        n = res.payload.get("count", n)
    t.append(f" · {n} 条记录")
    console.print(t)


def print_notes(console: Console, lines: list[str]) -> None:
    for ln in lines:
        console.print(Text(ln, style="dim"))


def print_section(console: Console, sec: models.Section) -> None:
    """头/尾段：两列 kv 小表，值按数据类型着色，解析错误标红。"""
    console.print(Text(f"── {sec.title}", style="bold cyan"))
    kv = RichTable(box=box.SIMPLE, show_edge=False, padding=(0, 1))
    kv.add_column("字段", style="bold")
    kv.add_column("值")
    for f in sec.fields:
        val = Text(f.value, style="red" if f.error else type_style(f.type))
        if f.error:
            val.append(f"  ⚠ {f.error}", style="dim red")
        kv.add_row(f.name, val)
    console.print(kv)


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
         no_color: bool = False, raw_mode: bool = False, per_line: int = 10) -> None:
    console = make_console(no_color)
    print_header(console, filename, res)
    print_notes(console, extra_lines or [])
    if res.header:
        print_section(console, res.header)

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
        show_table(console, res, raw_mode, per_line)

    if res.trailer:
        print_section(console, res.trailer)
    print_warnings(console, res.warnings)
