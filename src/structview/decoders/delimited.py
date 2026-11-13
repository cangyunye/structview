"""分隔符变长协议解码器。

单字符分隔符走 CSV 引号规则（quote/escape 可配），多字符分隔符按普通 split。
无 spec 时进入 generic 兜底模式：列名 col1..colN，全部按 str 展示。
"""

from __future__ import annotations

import csv

from .. import models
from ..detect import scan_delimiter
from ..enc import decode_text
from ..fields import format_value
from ..spec import Spec
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

    names: list[str] | None = [f.name for f in spec.fields] if spec and spec.fields else None
    rows: list[tuple[int, list[str]]] = []
    max_cols = len(names) if names else 0
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
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
                fields.append(models.Field(name=name, type=fd.type, raw=cell, value=value, error=err))
            else:
                fields.append(models.Field(name=name, raw=cell, value=cell.strip()))
        records.append(models.Record(index=len(records) + 1, line_no=i, fields=fields, warning=warning))

    return models.ParseResult(
        fmt="delimited" if spec else "generic",
        encoding=encoding,
        spec_name=spec.name if spec else None,
        delimiter=delim, records=records, warnings=warnings,
    )
