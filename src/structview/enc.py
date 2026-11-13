"""编码解析与自动探测。

约定：spec 与 CLI 中的一切字段长度一律按“字节”计算（GBK 一个汉字占 2 字节），
显示时才做解码。auto 探测链：BOM → utf-8 严格 → gb18030 → latin-1。
"""

from __future__ import annotations

import codecs

# 注意顺序：utf-32 的 BOM 前缀包含 utf-16 的 BOM，必须先判长 BOM
_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)

_ALIASES = {
    "utf8": "utf-8",
    "utf-8": "utf-8",
    "gb2312": "gb18030",
    "gbk": "gbk",
    "cp936": "gbk",
    "gb18030": "gb18030",
    "big5": "big5",
    "latin1": "latin-1",
    "latin-1": "latin-1",
}


def normalize_encoding(name: str) -> str:
    return _ALIASES.get(name.strip().lower(), name.strip())


def detect_encoding(data: bytes) -> tuple[str, list[str]]:
    """对原始字节做编码探测，返回 (编码, 说明列表)。"""
    notes: list[str] = []
    for bom, enc in _BOMS:
        if data.startswith(bom):
            notes.append(f"命中 {enc} BOM")
            return enc, notes
    try:
        data.decode("utf-8")
        notes.append("utf-8 严格解码通过")
        return "utf-8", notes
    except UnicodeDecodeError:
        pass
    try:
        data.decode("gb18030")  # GBK/GB2312 的超集，几乎必成功
        notes.append("utf-8 失败，gb18030（GBK 超集）解码通过")
        return "gb18030", notes
    except UnicodeDecodeError:
        notes.append("utf-8 / gb18030 均失败，按 latin-1 兜底")
        return "latin-1", notes


def strip_bom(data: bytes) -> bytes:
    for bom, _enc in _BOMS:
        if data.startswith(bom):
            return data[len(bom):]
    return data


def _valid_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def resolve_encoding(spec_enc: str | None, cli_enc: str | None, data: bytes) -> tuple[str, list[str]]:
    """编码决策：CLI 强制 > spec 声明（无法解码时降级探测）> auto 探测。"""
    notes: list[str] = []
    if cli_enc:
        enc = normalize_encoding(cli_enc)
        if spec_enc:
            notes.append(f"CLI 强制编码 {enc}（覆盖 spec 声明）")
        else:
            notes.append(f"CLI 指定编码 {enc}")
        if enc == "auto":
            e2, n2 = detect_encoding(data)
            return e2, notes + n2
        return enc, notes
    if spec_enc and normalize_encoding(spec_enc) != "auto":
        enc = normalize_encoding(spec_enc)
        try:
            data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            notes.append(f"spec 声明编码 {enc} 无法严格解码，降级 auto 探测")
            e2, n2 = detect_encoding(data)
            return e2, notes + n2
        if enc in ("gbk", "gb18030", "big5") and _valid_utf8(data):
            notes.append(
                f"注意：数据可按 utf-8 严格解码，但 spec 声明 {enc}；"
                f"如出现乱码可用 -e utf-8 覆盖"
            )
        notes.append(f"使用 spec 声明编码 {enc}")
        return enc, notes
    e2, n2 = detect_encoding(data)
    return e2, notes + n2


def decode_text(data: bytes, encoding: str) -> tuple[str, list[str]]:
    """解码整个文件；失败字符用替换符并给出警告。"""
    notes: list[str] = []
    try:
        return data.decode(encoding), notes
    except UnicodeDecodeError:
        text = data.decode(encoding, errors="replace")
        bad = text.count("\ufffd")
        notes.append(f"编码 {encoding} 存在 {bad} 个无法解码字符（以 � 显示），可用 -e 强制其它编码")
        return text, notes
    except LookupError:
        notes.append(f"未知编码 {encoding}，按 utf-8 替换解码")
        return data.decode("utf-8", errors="replace"), notes
