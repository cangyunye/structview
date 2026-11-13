"""sv 命令行入口。

子命令：read / detect / gen / spec(check|infer)。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from rich import box
from rich.table import Table as RichTable
from rich.text import Text

from . import __version__
from .decoders import get_decoder
from .detect import detect as detect_content, guess_field_type
from .enc import decode_text, resolve_encoding
from .gen import generate, resolve_gen_encoding
from .render import make_console, show
from .spec import (
    SpecError,
    find_spec,
    load_config,
    load_spec,
    match_config_overrides,
    spec_search_dirs,
)

_FMT_DESC = {"fixed": "定长", "delimited": "变长分隔符", "json": "JSON", "generic": "未识别（将走兜底表格）"}


def _read_input(path: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在: {path}")
    return p.read_bytes()


def _resolve_spec(args) -> tuple[object | None, str | None]:
    """spec 决策：CLI --proto > 项目配置 overrides > spec 自带 match。"""
    if getattr(args, "proto", None):
        spec = load_spec(args.proto)
        return spec, f"CLI --proto {args.proto}"
    cfg = load_config()
    spec, src = match_config_overrides(cfg, args.file)
    if spec:
        return spec, src
    spec, _notes = find_spec(args.file, spec_search_dirs(cfg))
    if spec:
        return spec, f"spec match: {spec.path}"
    return None, None


def cmd_read(args) -> int:
    data = _read_input(args.file)
    spec, spec_src = _resolve_spec(args)
    enc, enc_notes = resolve_encoding(spec.encoding if spec else None, args.encoding, data)

    fmt = args.format
    det = None
    if fmt == "auto":
        fmt = spec.fmt if spec else None
    if fmt is None:
        det = detect_content(data)
        fmt = det.fmt
        if fmt == "generic":
            fmt = "delimited"
    generic = spec is None and fmt == "delimited"
    if fmt == "fixed" and spec is None:
        print("✗ 定长解析需要 spec：用 -p 指定，或将 spec 放入 specs/ 目录按文件名匹配", file=sys.stderr)
        return 1

    delimiter = args.delimiter or (spec.delimiter if spec else None)
    if delimiter is None and fmt == "delimited" and det is not None:
        delimiter = det.delimiter

    decoder = get_decoder(fmt)
    res = decoder(data, spec, enc, delimiter=delimiter, raw_mode=args.raw)
    if generic:
        res.fmt = "generic"

    extra = []
    if spec_src:
        extra.append(f"spec 来源: {spec_src}")
    extra.extend(enc_notes)
    if generic:
        extra.append("未匹配到 spec，使用兜底解析；可先运行 sv detect 查看识别详情")

    if args.records:
        res.records = [r for r in res.records if r.index in args.records]

    show(res, "stdin" if args.file == "-" else Path(args.file).name,
         view=args.view, data=data, extra_lines=extra,
         no_color=args.no_color, raw_mode=args.raw)
    return 0


def cmd_detect(args) -> int:
    data = _read_input(args.file)
    det = detect_content(data)
    cfg = load_config()
    spec, src = match_config_overrides(cfg, args.file)
    if not spec:
        spec, _notes = find_spec(args.file, spec_search_dirs(cfg))
        if spec:
            src = f"spec match: {spec.path}"
    c = make_console(args.no_color)
    name = "stdin" if args.file == "-" else Path(args.file).name
    t = Text(name, style="bold")
    t.append(f"  （{len(data)} 字节）", style="dim")
    c.print(t)

    def line(label: str, value: str, dim: bool = False):
        tt = Text(f"  {label:<6}", style="bold")
        tt.append(value, style="dim" if dim else "")
        c.print(tt)

    enc_desc = det.encoding + ("；" + "；".join(det.encoding_notes) if det.encoding_notes else "")
    line("编码", enc_desc)
    lens = [x for x in det.line_lens if x > 0]
    if lens:
        ld = f"{len(lens)} 个非空行，行长 {min(lens)}–{max(lens)} 字节"
        if min(lens) == max(lens):
            ld += "（完全一致 → 定长特征）"
        line("行长", ld)
    else:
        line("行长", "无内容")
    line("分隔符", repr(det.delimiter) if det.delimiter else "未检出")
    fmt_desc = _FMT_DESC[det.fmt] + ("；" + "；".join(det.notes) if det.notes else "")
    line("格式", fmt_desc)
    if spec:
        line("spec", f"{spec.name} ← {src}")
    else:
        line("spec", "未命中（可编写 spec 用 match 匹配，或用 --proto 强制）", dim=True)

    fname = args.file
    if spec:
        cmd = f"sv read {fname}"
    elif det.fmt == "delimited":
        cmd = f"sv read {fname} -f delimited -d {det.delimiter}"
    elif det.fmt == "fixed":
        cmd = f"sv spec infer {fname}   # 先推断草稿 spec，补齐字段后用 sv read -p 使用"
    else:
        cmd = f"sv read {fname}   # 兜底表格；或用 -f/-d/-e 强制解析"
    c.print(Text(f"  建议: {cmd}", style="green"))
    return 0


def cmd_gen(args) -> int:
    spec = load_spec(args.spec)
    enc = resolve_gen_encoding(spec, args.encoding)
    out, res = generate(spec, enc, count=args.count, seed=args.seed)
    if args.out:
        Path(args.out).write_bytes(out)
        target = args.out
    else:
        sys.stdout.buffer.write(out)
        sys.stdout.buffer.flush()
        target = "stdout"
    c = make_console(args.no_color, stderr=True)
    c.print(f"✓ 已生成 {args.count} 条记录 → {target}（编码 {enc}，{len(out)} 字节）", style="green")
    if res is not None:
        errs = [(r.index, f.name) for r in res.records for f in r.fields if f.error]
        if errs:
            c.print(f"⚠ 回读校验: {len(res.records)} 条记录，{len(errs)} 个字段解析异常"
                    f"（如 行{errs[0][0]} {errs[0][1]}）", style="yellow")
        else:
            c.print(f"✓ 回读校验: {len(res.records)} 条记录，字段解析全部正常", style="green")
        for w in res.warnings[:5]:
            c.print(Text(f"⚠ {w}", style="yellow"))
    return 0


def cmd_spec_check(args) -> int:
    spec = load_spec(args.spec)
    c = make_console(args.no_color)
    c.print(f"✓ spec 合法：{spec.name}", style="green")
    info = f"  format={spec.fmt}  encoding={spec.encoding}  match={spec.match or '—'}"
    if spec.delimiter:
        info += f"  delimiter={spec.delimiter!r}"
    if spec.record_len:
        info += f"  record_len={spec.record_len}B"
    c.print(info)
    t = RichTable(box=box.SIMPLE, show_edge=False, padding=(0, 1))
    t.add_column("#", justify="right", style="dim")
    t.add_column("name", style="bold")
    t.add_column("type")
    t.add_column("len", justify="right")
    t.add_column("fmt")
    t.add_column("scale", justify="right")
    t.add_column("map")
    t.add_column("sample")
    for i, fd in enumerate(spec.fields, 1):
        t.add_row(
            str(i), fd.name, fd.type,
            str(fd.length) if fd.length is not None else "—",
            fd.fmt or "—",
            str(fd.scale) if fd.scale is not None else "—",
            ", ".join(f"{k}→{v}" for k, v in (fd.map or {}).items()) or "—",
            ", ".join(map(str, fd.sample)) if fd.sample else "—",
        )
    c.print(t)
    for w in spec.warnings:
        c.print(Text(f"⚠ {w}", style="yellow"))
    return 0


def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _draft_yaml(filename: str, fmt: str, enc: str, det, text: str, lines: list[str]) -> str:
    out: list[str] = []
    base = Path(filename).name
    glob = re.sub(r"\d+", "*", base)
    out.append("# 由 sv spec infer 自动生成的草稿，请核对字段名/类型/长度后再使用")
    out.append(f"name: 待命名协议")
    out.append(f"match: [{_yaml_str(glob)}]")
    out.append(f"encoding: {enc}")
    out.append(f"format: {fmt}")
    if fmt == "delimited":
        d = det.delimiter or "|"
        out.append(f"delimiter: {_yaml_str(d)}")
        rows = [ln.split(d) for ln in lines]
        ncols = max(map(len, rows))
        out.append("fields:")
        for j in range(ncols):
            vals = [r[j] for r in rows if j < len(r)]
            typ, extra, note = guess_field_type(vals)
            kv = f'{{name: "col{j + 1}", type: "{typ}"'
            if "fmt" in extra:
                kv += f', fmt: "{extra["fmt"]}"'
            if "scale" in extra:
                kv += f", scale: {extra['scale']}"
            kv += "}"
            out.append(f"  - {kv}  # {note}" if note else f"  - {kv}")
    elif fmt == "fixed":
        lens = [len(ln.encode(enc, errors="replace")) for ln in lines]
        total = lens[0] if lens else 0
        out.append(f"record_len: {total}")
        out.append("fields:")
        out.append(f'  - {{name: "整行", type: "str", len: {total}}}')
        out.append("  # 定长字段边界无法从数据推断，请按协议文档补齐各字段 len（按字节）")
    elif fmt == "json":
        out.append("# JSON 无需 fields；sv read 会自动美化")
    else:
        out.append("# 未识别格式，请手动指定 format/delimiter 或编写 spec")
    return "\n".join(out) + "\n"


def cmd_spec_infer(args) -> int:
    data = _read_input(args.file)
    det = detect_content(data)
    enc = args.encoding or det.encoding
    fmt = args.format if args.format != "auto" else det.fmt
    text, _ = decode_text(data, enc)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    draft = _draft_yaml(args.file, fmt, enc, det, text, lines)
    if args.out:
        Path(args.out).write_text(draft, encoding="utf-8")
        print(f"✓ 草稿已写入 {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(draft)
    return 0


def _parse_range(s: str) -> set[int]:
    out: set[int] = set()
    try:
        for part in s.split(","):
            part = part.strip()
            if "-" in part:
                a, b = part.split("-", 1)
                out |= set(range(int(a), int(b) + 1))
            else:
                out.add(int(part))
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"无效的记录范围: {s!r}") from e
    if not out:
        raise argparse.ArgumentTypeError(f"无效的记录范围: {s!r}")
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sv",
        description="终端协议文件美化打印工具（定长 / 变长分隔符 / JSON）",
    )
    p.add_argument("-V", "--version", action="version", version=f"sv {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    rd = sub.add_parser("read", help="解析并美化打印协议文件")
    rd.add_argument("file", help="文件路径，或 - 读 stdin")
    rd.add_argument("-p", "--proto", help="强制指定协议 spec YAML")
    rd.add_argument("-f", "--format", choices=["auto", "fixed", "delimited", "json"],
                    default="auto", help="强制解析器（缺省自动识别）")
    rd.add_argument("-d", "--delimiter", help="强制分隔符（配合 delimited）")
    rd.add_argument("-e", "--encoding", help="强制编码，覆盖 spec 声明（如 gbk/utf-8/auto）")
    rd.add_argument("-t", "--view", choices=["table", "detail", "hex"], default="table",
                    help="输出形态（缺省 table）")
    rd.add_argument("--raw", action="store_true", help="显示原始值，不做类型格式化")
    rd.add_argument("-r", "--records", type=_parse_range, metavar="1-5",
                    help="只看指定记录")
    rd.add_argument("--no-color", action="store_true")
    rd.set_defaults(func=cmd_read)

    dt = sub.add_parser("detect", help="识别文件的协议/编码/分隔符")
    dt.add_argument("file", help="文件路径，或 - 读 stdin")
    dt.add_argument("--no-color", action="store_true")
    dt.set_defaults(func=cmd_detect)

    gn = sub.add_parser("gen", help="按协议 spec 反向生成数据文件")
    gn.add_argument("--spec", required=True, help="协议 spec YAML")
    gn.add_argument("--count", type=int, default=5, help="生成记录数（缺省 5）")
    gn.add_argument("--out", help="输出文件（缺省写到 stdout）")
    gn.add_argument("--seed", type=int, default=None, help="随机种子（可复现）")
    gn.add_argument("-e", "--encoding", help="生成编码（缺省取 spec 声明）")
    gn.add_argument("--no-color", action="store_true")
    gn.set_defaults(func=cmd_gen)

    sp = sub.add_parser("spec", help="spec 工具")
    spsub = sp.add_subparsers(dest="spec_cmd", required=True)
    ck = spsub.add_parser("check", help="校验 spec")
    ck.add_argument("spec")
    ck.add_argument("--no-color", action="store_true")
    ck.set_defaults(func=cmd_spec_check)
    inf = spsub.add_parser("infer", help="从数据文件反推草稿 spec")
    inf.add_argument("file")
    inf.add_argument("-f", "--format", choices=["auto", "fixed", "delimited", "json"],
                     default="auto")
    inf.add_argument("-e", "--encoding")
    inf.add_argument("--out", help="输出文件（缺省写到 stdout）")
    inf.set_defaults(func=cmd_spec_infer)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SpecError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
