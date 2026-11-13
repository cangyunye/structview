"""分隔符变长协议解码器。

单字符分隔符走 CSV 引号规则（quote/escape 可配），多字符分隔符按普通 split。
无 spec 时进入 generic 兜底模式：列名 col1..colN，全部按 str 展示。

头/体/尾：spec 加载了同名 .head/.tail sidecar 时，首个非空行按头字段解析、
末个非空行按尾字段解析、中间行为体记录。
"""

from __future__ import annotations

import csv

from .. import models
from ..detect import scan_delimiter
from ..enc import decode_text
from ..fields import format_value
from ..spec import FieldDef, Spec
from . import register


def _split_line(line: str, delim: str, quote: str | None, escape: str | None) -> list[str]:
    if quote and len(delim) == 1:
        try:
            return next(csv.reader([line], delimiter=delim, quotechar=quote,
                                   escapechar=escape, doublequote=True))
        except (csv.Error, StopIteration):
            return line.split(delim)
    return line.split(delim)


@register("delimited")
def parse(data: bytes, spec: Spec | None, encoding: str, *, delimiter=None, raw_mode=False) -> models.ParseResult:
    text, notes = decode_text(data, encoding)
    warnings = list(notes)
    delim = delimiter or (spec.delimiter if spec else None)
    if not delim:
        d, why = scan_delimiter(text.splitlines())
        delim = d or "|"
        warnings.append(f"未显式指定分隔符，启发式选定 {delim!r}" + (f"（{why}）" if why else "（默认 |）"))
    quote = spec.quote if spec else '"'
    escape = spec.escape if spec else None

    entries = [(i, ln) for i, ln in enumerate(text.splitlines(), 1) if ln.strip()]

    def _section(line_no: int, line: str, defs: list[FieldDef], title: str) -> models.Section:
        cells = _split_line(line, delim, quote, escape)
        fields = []
        for j, fd in enumerate(defs):
            cell = cells[j] if j < len(cells) else ""
            value, err = format_value(fd, cell)
            fields.append(models.Field(name=fd.name, type=fd.type, raw=cell, value=value,
                                       error=err, scale=fd.scale))
        if len(cells) != len(defs):
            warnings.append(f"行{line_no}: {title}字段数 {len(cells)} ≠ 声明 {len(defs)}")
        return models.Section(title=title, fields=fields)

    header = trailer = None
    lo, hi = 0, len(entries)
    if spec and spec.header_fields:
        head_title = "文件头" + (f" · {spec.header_name}" if spec.header_name else "")
        if not entries:
            warnings.append("文件为空，缺少头记录")
        else:
            i, ln = entries[0]
            header = _section(i, ln, spec.header_fields, head_title)
            lo = 1
    if spec and spec.tail_fields:
        tail_title = "文件尾" + (f" · {spec.tail_name}" if spec.tail_name else "")
        if len(entries) <= lo:
            warnings.append("文件行数不足，缺少尾记录")
        else:
            i, ln = entries[-1]
            trailer = _section(i, ln, spec.tail_fields, tail_title)
            hi = len(entries) - 1

    names: list[str] | None = [f.name for f in spec.fields] if spec and spec.fields else None
    rows: list[tuple[int, list[str]]] = []
    max_cols = len(names) if names else 0
    for i, line in entries[lo:hi]:
        cells = _split_line(line, delim, quote, escape)
        rows.append((i, cells))
        max_cols = max(max_cols, len(cells))
    if names is None:
        names = [f"col{j}" for j in range(1, max_cols + 1)]

    records: list[models.Record] = []
    for i, cells in rows:
        warning = None
        if len(cells) < len(names):
            warning = f"行{i}: 字段数 {len(cells)} < {len(names)}，缺失字段留空"
        elif len(cells) > len(names):
            warning = f"行{i}: 字段数 {len(cells)} > {len(names)}，多余内容截断"
        if warning:
            warnings.append(warning)
        fields: list[models.Field] = []
        for j, name in enumerate(names):
            cell = cells[j] if j < len(cells) else ""
            if spec and j < len(spec.fields):
                fd = spec.fields[j]
                value, err = format_value(fd, cell)
                fields.append(models.Field(name=name, type=fd.type, raw=cell, value=value,
                                           error=err, scale=fd.scale))
            else:
                fields.append(models.Field(name=name, raw=cell, value=cell.strip()))
        records.append(models.Record(index=len(records) + 1, line_no=i, fields=fields, warning=warning))

    return models.ParseResult(
        fmt="delimited" if spec else "generic",
        encoding=encoding,
        spec_name=spec.name if spec else None,
        delimiter=delim, records=records, header=header, trailer=trailer,
        warnings=warnings,
    )
