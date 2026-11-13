"""解析结果的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field as _field
from typing import Any


@dataclass
class Field:
    """单条记录中的一个字段。"""

    name: str
    type: str = "str"
    raw: str = ""              # 解码后的原始串（未 trim）
    value: str = ""            # 展示值（类型格式化后）
    error: str | None = None   # 非致命解析错误说明
    offset: int | None = None  # 定长模式：起始字节偏移
    length: int | None = None  # 定长模式：字节长度
    scale: int | None = None   # dec：隐含小数位数


@dataclass
class Record:
    index: int = 0                # 1-based 记录序号
    line_no: int | None = None    # 原始文件行号
    fields: list[Field] = _field(default_factory=list)
    warning: str | None = None    # 行级警告（字段数不符等）


@dataclass
class ParseResult:
    fmt: str = "delimited"        # fixed / delimited / json / generic
    encoding: str = "utf-8"
    spec_name: str | None = None
    delimiter: str | None = None
    records: list[Record] = _field(default_factory=list)
    warnings: list[str] = _field(default_factory=list)
    notes: list[str] = _field(default_factory=list)
    # JSON 专用载荷：{"mode": table/kv/pretty/embedded, ...}
    payload: dict[str, Any] | None = None
