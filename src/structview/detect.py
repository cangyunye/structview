"""协议识别链与内容启发式。

识别优先级（CLI 层面）：CLI 显式参数 > 项目配置 overrides > spec 自带 match >
内容启发式（本模块）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as _field

CANDIDATE_DELIMS = ("|", "\t", ";", ",", "^", "~")


@dataclass
class Detection:
    encoding: str = "utf-8"
    encoding_notes: list[str] = _field(default_factory=list)
    fmt: str = "generic"          # fixed / delimited / json / generic
    delimiter: str | None = None
    line_count: int = 0
    line_lens: list[int] = _field(default_factory=list)
    notes: list[str] = _field(default_factory=list)


def split_lines(data: bytes) -> list[bytes]:
    """按 \\n 切行，去掉行尾 \\r 与结尾空行。"""
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return [ln[:-1] if ln.endswith(b"\r") else ln for ln in lines]


def scan_delimiter(lines: list[str]) -> tuple[str | None, str | None]:
    """启发式分隔符：要求每个非空行出现次数一致且 ≥1。"""
    nonempty = [ln for ln in lines if ln.strip()]
    if not nonempty:
        return None, None
    for d in CANDIDATE_DELIMS:
        counts = [ln.count(d) for ln in nonempty]
        if counts[0] >= 1 and min(counts) == max(counts):
            return d, f"每个非空行固定出现 {counts[0]} 次"
    return None, None


def detect(data: bytes) -> Detection:
    from .enc import detect_encoding, decode_text

    det = Detection()
    det.encoding, det.encoding_notes = detect_encoding(data)
    raw_lines = split_lines(data)
    det.line_lens = [len(ln) for ln in raw_lines]
    det.line_count = sum(1 for ln in raw_lines if ln.strip())
    text, _ = decode_text(data, det.encoding)
    lines = text.splitlines()

    # 1) JSON 特征
    stripped = text.lstrip()
    if stripped[:1] in ("{", "["):
        try:
            json.loads(stripped, parse_float=str)
            det.fmt = "json"
            det.notes.append("整体可作为 JSON 解析")
            return det
        except json.JSONDecodeError:
            jsonl = [ln for ln in lines if ln.strip()]
            if jsonl and all(ln.lstrip()[:1] in ("{", "[") for ln in jsonl):
                det.fmt = "json"
                det.notes.append("每行均为独立 JSON（JSON Lines）")
                return det
            det.notes.append("含 JSON 特征但整体/逐行均解析失败，回退行扫描")

    # 2) 定长特征：非空行字节长度全部一致
    lens = [x for x in det.line_lens if x > 0]
    if len(lens) >= 2 and min(lens) == max(lens):
        det.fmt = "fixed"
        det.notes.append(f"非空行字节长度一致（{lens[0]}B × {len(lens)} 行）")
        return det

    # 3) 分隔符特征
    d, why = scan_delimiter(lines)
    if d:
        det.fmt = "delimited"
        det.delimiter = d
        det.notes.append(f"分隔符 {d!r}：{why}")
        return det

    # 4) 内嵌 JSON 块（如 HTTP 日志正文）
    from .decoders.jsondec import _extract_blocks
    blocks = [b for b in _extract_blocks(text) if b["obj"] is not None]
    if blocks:
        det.fmt = "json"
        det.notes.append(f"检测到 {len(blocks)} 个内嵌 JSON 块")
        return det

    det.fmt = "generic"
    det.notes.append("未识别出明确特征，按兜底表格展示")
    return det


def guess_field_type(values: list[str]) -> tuple[str, dict, str | None]:
    """根据一列取值猜测字段类型，返回 (type, 额外键, 猜测说明)。供 spec infer 使用。"""
    vals = [v.strip() for v in values if v.strip()]
    if not vals:
        return "str", {}, None
    uniq = set(vals)
    if 1 < len(uniq) <= 8 and len(uniq) < len(vals) and max(map(len, vals)) <= 6:
        return "enum", {}, f"疑似枚举，取值: {' / '.join(sorted(uniq))}"
    if all(re.fullmatch(r"[12]\d{7}", v) for v in vals):
        return "date", {"fmt": "%Y%m%d"}, "疑似 yyyyMMdd 日期"
    if all(re.fullmatch(r"[12]\d{13}", v) for v in vals):
        return "date", {"fmt": "%Y%m%d%H%M%S"}, "疑似 yyyyMMddHHmmss"
    if all(re.fullmatch(r"-?\d+", v) for v in vals):
        return "int", {}, None
    if all(re.fullmatch(r"-?\d+\.\d+", v) for v in vals):
        scale = min(len(v.split(".")[1]) for v in vals)
        return "dec", {"scale": scale}, None
    return "str", {}, None
