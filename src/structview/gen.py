"""按协议 spec 反向生成数据文件（sv gen），并回读校验。"""

from __future__ import annotations

import random
import string
from datetime import datetime, timedelta

from .decoders import get_decoder
from .enc import normalize_encoding
from .fields import normalize_type
from .spec import Spec

_ALNUM = string.ascii_uppercase + string.digits


def gen_value(fd, rng: random.Random) -> str:
    """按字段类型生成一个合法值。字段写了 sample 时从取值池随机。"""
    if fd.sample:
        return str(rng.choice(fd.sample))
    t = normalize_type(fd.type)
    if t == "enum" and fd.map:
        return str(rng.choice(list(fd.map.keys())))
    if t == "int":
        digits = max(fd.length or 4, 1)
        return str(rng.randrange(10 ** min(digits, 9)))
    if t == "dec":
        scale = fd.scale if fd.scale is not None else 2
        digits = max(fd.length or (scale + 4), scale + 1)
        return str(rng.randrange(10 ** min(digits, 12)))
    if t == "date":
        fmt = fd.fmt or "%Y%m%d"
        day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) \
            - timedelta(days=rng.randrange(365))
        return day.strftime(fmt)
    if t == "time":
        fmt = fd.fmt or "%H%M%S"
        return (datetime(2000, 1, 1) + timedelta(seconds=rng.randrange(86400))).strftime(fmt)
    if t == "hex":
        n = fd.length or 8
        return "".join(rng.choice("0123456789abcdef") for _ in range(n))
    # str 及未知类型兜底：大写字母+数字
    n = fd.length or rng.randrange(4, 11)
    return "".join(rng.choice(_ALNUM) for _ in range(n))


def _fit_bytes(value: str, fd, enc: str) -> bytes:
    """定长字段：编码后按字节截断/填充。文本左对齐补空格，数值右对齐补 0。"""
    t = normalize_type(fd.type)
    target = fd.length
    raw = value.encode(enc, errors="replace")
    if target:
        while len(raw) > target and value:
            value = value[:-1]
            raw = value.encode(enc, errors="replace")
    if target is None:
        return raw
    if t in ("int", "dec"):
        return raw.rjust(target, b"0")
    return raw.ljust(target, b" ")


def resolve_gen_encoding(spec: Spec, cli_enc: str | None) -> str:
    if cli_enc:
        return normalize_encoding(cli_enc)
    enc = normalize_encoding(spec.encoding or "auto")
    return "utf-8" if enc == "auto" else enc


def generate(spec: Spec, encoding: str, count: int, seed: int | None):
    """生成数据并回读校验，返回 (文件字节, 回读 ParseResult 或 None)。"""
    rng = random.Random(seed)
    lines: list[bytes] = []
    for _ in range(max(count, 0)):
        vals = [gen_value(fd, rng) for fd in spec.fields]
        if spec.fmt == "fixed":
            line = b"".join(_fit_bytes(v, fd, encoding) for fd, v in zip(spec.fields, vals))
        else:
            line = (spec.delimiter or "|").join(vals).encode(encoding, errors="replace")
        lines.append(line)
    out = b"\n".join(lines) + (b"\n" if lines else b"")

    res = None
    if lines:
        decoder = get_decoder(spec.fmt)
        res = decoder(out, spec, encoding, raw_mode=False)
    return out, res
