"""定长协议解码器：字段按字节偏移切分，len 一律按字节。"""

from __future__ import annotations

from .. import models
from ..detect import split_lines
from ..enc import strip_bom
from ..fields import format_value, visible
from ..spec import Spec
from . import register


def _decode_chunk(chunk: bytes, encoding: str) -> str:
    try:
        return chunk.decode(encoding, errors="replace")
    except LookupError:
        return chunk.decode("utf-8", errors="replace")


def parse_line(raw_line: bytes, spec: Spec, encoding: str, line_no: int,
               warnings: list[str]) -> list[models.Field]:
    out: list[models.Field] = []
    pos = 0
    for fd in spec.fields:
        chunk = raw_line[pos: pos + fd.length]
        if len(chunk) < fd.length:
            warnings.append(f"行{line_no}: 字段 {fd.name} 不足 {fd.length} 字节（仅 {len(chunk)}B）")
        text = _decode_chunk(chunk, fd.encoding or encoding)
        value, err = format_value(fd, text)
        out.append(models.Field(name=fd.name, type=fd.type, raw=text, value=value,
                                error=err, offset=pos, length=fd.length))
        pos += fd.length
    if pos < len(raw_line):
        rest = raw_line[pos:]
        warnings.append(f"行{line_no}: 按字段合计 {pos}B，行内多出 {len(rest)}B 尾料")
        text = _decode_chunk(rest, encoding)
        out.append(models.Field(name="…尾料", raw=text, value=visible(text)))
    return out


@register("fixed")
def parse(data: bytes, spec: Spec | None, encoding: str, *, delimiter=None, raw_mode=False) -> models.ParseResult:
    if spec is None:
        raise ValueError("定长解析需要 spec：用 -p 指定，或将 spec 放入 specs/ 目录按文件名匹配")
    warnings: list[str] = []
    data = strip_bom(data)
    lines = split_lines(data)
    for i, ln in enumerate(lines, 1):
        if spec.record_len and len(ln) != spec.record_len:
            warnings.append(f"行{i}: 行长 {len(ln)}B ≠ record_len {spec.record_len}B")
    records = [
        models.Record(index=i, line_no=i,
                      fields=parse_line(ln, spec, encoding, i, warnings))
        for i, ln in enumerate(lines, 1)
    ]
    return models.ParseResult(fmt="fixed", encoding=encoding, spec_name=spec.name,
                              records=records, warnings=warnings)
