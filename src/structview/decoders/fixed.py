"""定长协议解码器：字段按字节偏移切分，len 一律按字节。

头/体/尾：spec 加载了同名 .head/.tail sidecar 时，首行按头字段解析、末行按尾字段
解析、中间行为体记录；record_len 行长检查只针对体行。
"""

from __future__ import annotations

from .. import models
from ..detect import split_lines
from ..enc import strip_bom
from ..fields import format_value, visible
from ..spec import FieldDef, Spec
from . import register


def _decode_chunk(chunk: bytes, encoding: str) -> str:
    try:
        return chunk.decode(encoding, errors="replace")
    except LookupError:
        return chunk.decode("utf-8", errors="replace")


def parse_line(raw_line: bytes, field_defs: list[FieldDef], encoding: str,
               line_no: int, warnings: list[str]) -> list[models.Field]:
    out: list[models.Field] = []
    pos = 0
    for fd in field_defs:
        chunk = raw_line[pos: pos + fd.length]
        if len(chunk) < fd.length:
            warnings.append(f"行{line_no}: 字段 {fd.name} 不足 {fd.length} 字节（仅 {len(chunk)}B）")
        text = _decode_chunk(chunk, fd.encoding or encoding)
        value, err = format_value(fd, text)
        out.append(models.Field(name=fd.name, type=fd.type, raw=text, value=value,
                                error=err, offset=pos, length=fd.length, scale=fd.scale))
        pos += fd.length
    if pos < len(raw_line):
        rest = raw_line[pos:]
        warnings.append(f"行{line_no}: 按字段合计 {pos}B，行内多出 {len(rest)}B 尾料")
        text = _decode_chunk(rest, encoding)
        out.append(models.Field(name="…尾料", raw=text, value=visible(text),
                                offset=pos, length=len(rest)))
    return out


def _parse_section(raw_line: bytes, field_defs: list[FieldDef], encoding: str,
                   line_no: int, warnings: list[str], title: str) -> models.Section:
    return models.Section(title=title,
                          fields=parse_line(raw_line, field_defs, encoding, line_no, warnings))


@register("fixed")
def parse(data: bytes, spec: Spec | None, encoding: str, *, delimiter=None, raw_mode=False) -> models.ParseResult:
    if spec is None:
        raise ValueError("定长解析需要 spec：用 -p 指定，或将 spec 放入 specs/ 目录按文件名匹配")
    warnings: list[str] = []
    data = strip_bom(data)
    lines = split_lines(data)
    n = len(lines)

    head_title = "文件头" + (f" · {spec.header_name}" if spec.header_name else "")
    tail_title = "文件尾" + (f" · {spec.tail_name}" if spec.tail_name else "")
    header = trailer = None
    lo, hi = 0, n
    if spec.header_fields:
        if n == 0:
            warnings.append("文件为空，缺少头记录")
        else:
            header = _parse_section(lines[0], spec.header_fields, encoding, 1, warnings, head_title)
            lo = 1
    if spec.tail_fields:
        if n <= lo:
            warnings.append("文件行数不足，缺少尾记录")
        else:
            trailer = _parse_section(lines[-1], spec.tail_fields, encoding, n, warnings, tail_title)
            hi = n - 1

    body = lines[lo:hi]
    for k, ln in enumerate(body):
        i = lo + k + 1  # 文件行号
        if spec.record_len and len(ln) != spec.record_len:
            warnings.append(f"行{i}: 行长 {len(ln)}B ≠ record_len {spec.record_len}B")
    records = [
        models.Record(index=j, line_no=lo + j,
                      fields=parse_line(ln, spec.fields, encoding, lo + j, warnings))
        for j, ln in enumerate(body, 1)
    ]
    return models.ParseResult(fmt="fixed", encoding=encoding, spec_name=spec.name,
                              records=records, header=header, trailer=trailer,
                              warnings=warnings)
