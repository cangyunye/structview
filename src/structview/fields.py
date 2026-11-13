"""字段类型格式化与兜底。

内置类型：str / int / dec（隐含小数位） / date / time / hex / enum。
spec 未写 type 或写了未知类型时，一律按 str 兜底：trim 后原样显示。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

KNOWN_TYPES = ("str", "int", "dec", "date", "time", "hex", "enum")


def normalize_type(t) -> str:
    t = str(t or "str").strip().lower()
    return t if t in KNOWN_TYPES else "str"


def format_value(fdef, raw: str) -> tuple[str, str | None]:
    """按字段定义格式化原始串，返回 (展示值, 错误说明)。错误不影响其它字段。"""
    t = normalize_type(getattr(fdef, "type", None))
    s = raw.strip()
    if t == "str" or s == "":
        return s, None
    try:
        if t == "int":
            return str(int(s)), None
        if t == "dec":
            scale = int(getattr(fdef, "scale", None) or 0)
            d = Decimal(s) if "." in s else Decimal(s).scaleb(-scale)
            if scale:
                d = d.quantize(Decimal(1).scaleb(-scale))
            return format(d, "f"), None
        if t == "date":
            fmt = getattr(fdef, "fmt", None) or "%Y%m%d"
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d"), None
        if t == "time":
            fmt = getattr(fdef, "fmt", None) or "%H%M%S"
            return datetime.strptime(s, fmt).strftime("%H:%M:%S"), None
        if t == "hex":
            h = s.replace(" ", "")
            if h and all(c in "0123456789abcdefABCDEF" for c in h):
                h = h.upper()
                return " ".join(h[i: i + 2] for i in range(0, len(h), 2)), None
            return s, "内容不是十六进制"
        if t == "enum":
            m = getattr(fdef, "map", None) or {}
            if s in m:
                return str(m[s]), None
            return s, None  # 未知枚举值：原样显示
    except (ValueError, InvalidOperation):
        pass
    # 解析失败兜底：原样显示 + 错误标注
    if t == "int":
        return s, "无法解析为整数"
    if t == "dec":
        return s, "无法解析为数值"
    if t == "date":
        return s, f"日期不符合 {getattr(fdef, 'fmt', None) or '%Y%m%d'}"
    if t == "time":
        return s, f"时间不符合 {getattr(fdef, 'fmt', None) or '%H%M%S'}"
    return s, None


def visible(raw: str) -> str:
    """原始值可视化：空格/制表符转可见符号，便于核对定长填充。"""
    return raw.replace(" ", "·").replace("\t", "→")
