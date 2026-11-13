"""YAML 协议描述（spec）的加载、校验与按文件名匹配。

spec 顶层键：
  name / match / encoding / format / delimiter / quote / escape /
  record_len / fields / key_field + layouts（预留）
字段键：name / type / len / fmt / scale / map / encoding（预留） / sample
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field as _field
from pathlib import Path

import yaml

from .fields import KNOWN_TYPES, normalize_type

VALID_FORMATS = ("fixed", "delimited", "json")


class SpecError(Exception):
    """spec 或项目配置非法。"""


@dataclass
class FieldDef:
    name: str
    type: str = "str"
    length: int | None = None
    fmt: str | None = None
    scale: int | None = None
    map: dict | None = None
    encoding: str | None = None
    sample: list | None = None


@dataclass
class Spec:
    path: Path | None = None
    name: str = ""
    fmt: str = "delimited"
    encoding: str = "auto"
    delimiter: str | None = None
    quote: str | None = '"'
    escape: str | None = None
    record_len: int | None = None
    match: list[str] = _field(default_factory=list)
    fields: list[FieldDef] = _field(default_factory=list)
    key_field: str | None = None
    layouts: dict | None = None
    header_fields: list[FieldDef] | None = None   # 头记录字段（同名 .head sidecar spec）
    tail_fields: list[FieldDef] | None = None     # 尾记录字段（同名 .tail sidecar spec）
    header_name: str | None = None                # sidecar 的 name，展示在段标题
    tail_name: str | None = None
    warnings: list[str] = _field(default_factory=list)

    @property
    def total_len(self) -> int:
        return self.record_len or sum(f.length or 0 for f in self.fields)


def _parse_field_list(raw_fields, fmt: str, p: Path, warnings: list[str],
                      what: str = "fields") -> list[FieldDef]:
    """解析一段字段定义列表（体 fields / 头尾 sidecar 共用）。"""
    if not isinstance(raw_fields, list):
        raise SpecError(f"{p}: {what} 必须是列表")
    fields: list[FieldDef] = []
    for i, f in enumerate(raw_fields, 1):
        if not isinstance(f, dict) or not f.get("name"):
            raise SpecError(f"{p}: {what} 第 {i} 项缺少 name")
        name = str(f["name"])
        t_raw = f.get("type")
        t = normalize_type(t_raw)
        if t_raw is not None and str(t_raw).strip().lower() not in KNOWN_TYPES:
            warnings.append(f"字段 {name}: 未知类型 {t_raw!r}，按 str 兜底")

        length = None
        if fmt == "fixed":
            length = f.get("len", f.get("length"))
            if not isinstance(length, int) or length <= 0:
                raise SpecError(f"{p}: 定长字段 {name} 缺少正整数 len（按字节）")

        scale = None
        if f.get("scale") is not None:
            try:
                scale = int(f["scale"])
            except (TypeError, ValueError) as e:
                raise SpecError(f"{p}: 字段 {name} 的 scale 必须是整数") from e

        enum_map = None
        if t == "enum" and f.get("map"):
            if not isinstance(f["map"], dict):
                raise SpecError(f"{p}: 字段 {name} 的 map 必须是键值映射")
            enum_map = {str(k): v for k, v in f["map"].items()}

        sample = f.get("sample")
        if sample is not None and not isinstance(sample, list):
            raise SpecError(f"{p}: 字段 {name} 的 sample 必须是列表")

        fields.append(FieldDef(
            name=name, type=t, length=length,
            fmt=str(f["fmt"]) if f.get("fmt") else None,
            scale=scale, map=enum_map,
            encoding=f.get("encoding"), sample=sample,
        ))
    return fields


def _load_sidecar(p: Path, kind: str, fmt: str, warnings: list[str]):
    """探测同名 .head/.tail sidecar spec，返回 (fields, name) 或 (None, None)。

    sidecar 只声明字段（结构/编码/分隔符继承主 spec），解析失败仅告警不阻塞。
    """
    sp = p.with_suffix(f".{kind}{p.suffix}")
    if not sp.is_file():
        return None, None
    try:
        doc = yaml.safe_load(sp.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        warnings.append(f"{sp.name}: YAML 解析失败，忽略该段: {e}")
        return None, None
    if isinstance(doc, list):
        raw_fields, name = doc, None
    elif isinstance(doc, dict):
        raw_fields, name = doc.get("fields"), doc.get("name")
    else:
        warnings.append(f"{sp.name}: 内容需为字段列表或 fields 键值映射，忽略该段")
        return None, None
    try:
        fields = _parse_field_list(raw_fields or [], fmt, sp, warnings, f"{kind} fields")
    except SpecError as e:
        warnings.append(f"{e}（忽略该段）")
        return None, None
    if not fields:
        warnings.append(f"{sp.name}: 未声明字段，忽略该段")
        return None, None
    return fields, (str(name) if name else None)


def load_spec(path) -> Spec:
    p = Path(path)
    if not p.is_file():
        raise SpecError(f"spec 文件不存在: {p}")
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise SpecError(f"{p}: YAML 解析失败: {e}") from e
    if not isinstance(doc, dict):
        raise SpecError(f"{p}: 顶层必须是键值映射")

    spec = Spec(path=p)
    spec.name = str(doc.get("name") or p.stem)

    fmt = doc.get("format")
    if fmt not in VALID_FORMATS:
        raise SpecError(f"{p}: format 必须是 {'/'.join(VALID_FORMATS)} 之一，当前为 {fmt!r}")
    spec.fmt = fmt

    spec.encoding = str(doc.get("encoding") or "auto")

    match = doc.get("match") or []
    if isinstance(match, str):
        match = [match]
    spec.match = [str(m) for m in match]

    spec.record_len = doc.get("record_len")
    if spec.record_len is not None and (not isinstance(spec.record_len, int) or spec.record_len <= 0):
        raise SpecError(f"{p}: record_len 必须是正整数（字节）")

    if doc.get("delimiter") is not None:
        spec.delimiter = str(doc["delimiter"])

    if "quote" in doc:
        q = doc["quote"]
        spec.quote = None if q in (None, "", False) else str(q)
    if "escape" in doc:
        e = doc["escape"]
        spec.escape = None if e in (None, "", False) else str(e)

    raw_fields = doc.get("fields") or []
    if fmt != "json" and not raw_fields:
        raise SpecError(f"{p}: fields 不能为空")
    spec.fields = _parse_field_list(raw_fields, fmt, p, spec.warnings) if raw_fields else []

    # 同名 .head/.tail sidecar spec：存在才加载（头/体/尾结构）
    spec.header_fields, spec.header_name = _load_sidecar(p, "head", fmt, spec.warnings)
    spec.tail_fields, spec.tail_name = _load_sidecar(p, "tail", fmt, spec.warnings)

    if fmt == "delimited" and not spec.delimiter:
        raise SpecError(f"{p}: delimited 格式必须声明 delimiter")
    if fmt == "delimited" and spec.delimiter and spec.quote and len(spec.delimiter) != 1:
        spec.warnings.append(f"多字符分隔符 {spec.delimiter!r} 不走引号规则，将按普通 split 处理")
    if fmt == "fixed":
        total = sum(f.length or 0 for f in spec.fields)
        if spec.record_len and spec.record_len != total:
            spec.warnings.append(f"record_len({spec.record_len}) ≠ 字段 len 合计({total})，解析以字段切分为准")

    if doc.get("key_field") or doc.get("layouts"):
        spec.key_field = doc.get("key_field")
        spec.layouts = doc.get("layouts")
        spec.warnings.append("key_field/layouts（多记录类型分叉）为预留功能，本期按主布局解析")
    return spec


def load_config(base: Path | None = None) -> dict:
    """读取项目配置 .structview/config.yaml（可选）。"""
    p = (base or Path.cwd()) / ".structview/config.yaml"
    if not p.is_file():
        return {}
    try:
        doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise SpecError(f"{p}: 项目配置解析失败: {e}") from e
    return doc if isinstance(doc, dict) else {}


def spec_search_dirs(cfg: dict, base: Path | None = None) -> list[Path]:
    raw = cfg.get("specs_dir") or ["specs", ".structview/specs"]
    if isinstance(raw, str):
        raw = [raw]
    b = base or Path.cwd()
    return [b / x for x in raw]


def match_config_overrides(cfg: dict, filename: str, base: Path | None = None):
    """项目配置 overrides：glob → spec。这是显式的人工决定，优先于 spec 自带 match。"""
    name = Path(filename).name
    b = base or Path.cwd()
    for ov in cfg.get("overrides") or []:
        if not isinstance(ov, dict):
            continue
        glob, spec_path = ov.get("glob"), ov.get("spec")
        if glob and spec_path and fnmatch.fnmatch(name, str(glob)):
            return load_spec(b / str(spec_path)), f"项目配置 overrides[{glob!r}] → {spec_path}"
    return None, None


def find_spec(filename: str, search_dirs) -> tuple[Spec | None, list[str]]:
    """扫描 spec 目录，按各 spec 的 match 模式匹配文件名。"""
    notes: list[str] = []
    name = Path(filename).name
    for d in search_dirs:
        if not d.is_dir():
            continue
        files = sorted(list(d.glob("*.yaml")) + list(d.glob("*.yml")))
        for sp in files:
            if sp.stem.endswith((".head", ".tail")):
                continue  # 头/尾 sidecar spec 随主 spec 加载，不参与独立匹配
            try:
                spec = load_spec(sp)
            except SpecError as e:
                notes.append(str(e))
                continue
            for pat in spec.match:
                if fnmatch.fnmatch(name, pat):
                    notes.append(f"文件名命中 {sp} 的 match 模式 {pat!r}")
                    return spec, notes
    return None, notes
