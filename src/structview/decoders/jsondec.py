"""JSON 解码器：整体 JSON / JSON Lines / 日志内嵌 JSON 提取。

浮点一律按字符串解析（parse_float=str），避免大数金额丢失精度；
展示时浮点会以字符串形式出现，属预期行为。
"""

from __future__ import annotations

import json

from .. import models
from ..enc import decode_text
from . import register

_MISS = object()


def _loads(s: str):
    return json.loads(s, parse_float=str)


def _scalar(v) -> bool:
    return v is None or isinstance(v, (str, int, bool, float))


def _flat(items) -> bool:
    return bool(items) and all(isinstance(x, dict) for x in items) and \
        all(_scalar(v) for row in items for v in row.values())


def _cell(v) -> str:
    if v is None:
        return ""
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False)


def _records_from(items: list[dict]) -> list[models.Record]:
    keys: list[str] = []
    for row in items:
        for k in row:
            if k not in keys:
                keys.append(k)
    records = []
    for idx, row in enumerate(items, 1):
        fields = []
        for k in keys:
            v = row.get(k)
            fields.append(models.Field(name=k, raw=json.dumps(v, ensure_ascii=False), value=_cell(v)))
        records.append(models.Record(index=idx, fields=fields))
    return records


def _find_block_end(text: str, start: int) -> int | None:
    """找与 text[start] 匹配的闭括号下标（字符串/转义感知）。找不到返回 None。"""
    opener = text[start]
    closer = {"{": "}", "[": "]"}[opener]
    in_str = esc = False
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
    return None


def _extract_blocks(text: str) -> list[dict]:
    """提取文本中所有顶层 JSON 块，附带上文（如 HTTP 头部）。"""
    blocks: list[dict] = []
    i = 0
    prev_end = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "{[":
            end = _find_block_end(text, i)
            seg_end = n if end is None else end + 1
            raw = text[i:seg_end].strip()
            ctx = [ln for ln in text[prev_end:i].splitlines() if ln.strip()][-12:]
            try:
                obj = _loads(raw)
            except json.JSONDecodeError:
                obj = None
            blocks.append({"context": ctx, "text": raw, "obj": obj,
                           "truncated": end is None})
            prev_end = seg_end
            i = seg_end
        else:
            i += 1
    return blocks


@register("json")
def parse(data: bytes, spec, encoding: str, *, delimiter=None, raw_mode=False) -> models.ParseResult:
    text, notes = decode_text(data, encoding)
    warnings = list(notes)
    res = models.ParseResult(fmt="json", encoding=encoding,
                             spec_name=spec.name if spec else None, warnings=warnings)

    stripped = text.lstrip()
    whole = _MISS
    if stripped[:1] in ("{", "["):
        try:
            whole = _loads(stripped)
        except json.JSONDecodeError:
            pass
    if whole is not _MISS:
        if isinstance(whole, list) and _flat(whole):
            res.records = _records_from(whole)
            res.payload = {"mode": "table", "count": len(whole)}
        elif isinstance(whole, dict) and all(_scalar(v) for v in whole.values()):
            res.payload = {"mode": "kv", "obj": whole, "count": 1}
        else:
            res.payload = {"mode": "pretty", "items": [whole], "count": 1}
        return res

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines and all(ln.lstrip()[:1] in ("{", "[") for ln in lines):
        try:
            items = [_loads(ln) for ln in lines]
        except json.JSONDecodeError:
            items = None
        if items is not None:
            if _flat(items):
                res.records = _records_from(items)
                res.payload = {"mode": "table", "count": len(items)}
            else:
                res.payload = {"mode": "pretty", "items": items, "count": len(items)}
            return res

    blocks = _extract_blocks(text)
    if not blocks:
        res.payload = {"mode": "pretty", "items": [], "count": 0}
        warnings.append("未找到任何 JSON 内容")
        return res
    bad = sum(1 for b in blocks if b["obj"] is None)
    if bad:
        warnings.append(f"{bad} 个 JSON 块解析失败，按原文显示")
    res.payload = {"mode": "embedded", "blocks": blocks, "count": len(blocks)}
    return res
