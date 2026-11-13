"""hexdump 视图：原始字节对照（前 4KB）。"""

from __future__ import annotations

from rich.text import Text


def hexdump_lines(data: bytes, width: int = 16, max_bytes: int = 4096) -> list[str]:
    out: list[str] = []
    view = data[:max_bytes]
    for off in range(0, len(view), width):
        chunk = view[off: off + width]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        pad = "   " * (width - len(chunk))
        asc = "".join(chr(b) if 32 <= b < 127 else "·" for b in chunk)
        out.append(f"{off:08x}  {hexs}{pad}  |{asc}|")
    return out


def show_hexdump(console, data: bytes) -> None:
    view_len = min(len(data), 4096)
    console.print(Text(f"hexdump（前 {view_len} 字节 / 共 {len(data)} 字节）", style="dim"))
    for ln in hexdump_lines(data):
        console.print(Text(ln))
