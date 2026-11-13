from structview.gen import generate, gen_value, resolve_gen_encoding
from structview.spec import FieldDef, Spec, load_spec

import yaml

FIXED_YAML = """
name: 产品表
format: fixed
encoding: gbk
record_len: 44
fields:
  - {name: PROD_CD, len: 8, type: str}
  - {name: PROD_NM, len: 20, type: str}
  - {name: RATE, len: 7, type: dec, scale: 5}
  - {name: EFF_DT, len: 8, type: date, fmt: "%Y%m%d"}
  - {name: ST, len: 1, type: enum, map: {"1": 正常, "0": 停售}}
"""

DELIM_YAML = """
name: T1
format: delimited
encoding: gbk
delimiter: "|"
fields:
  - {name: 商户号, type: str}
  - {name: 金额, type: dec, scale: 2}
  - {name: 日期, type: date}
  - {name: 币种, type: enum, map: {CNY: 人民币, USD: 美元}}
"""


def test_gen_fixed_roundtrip(tmp_path):
    p = tmp_path / "prod.yaml"
    p.write_text(FIXED_YAML, encoding="utf-8")
    spec = load_spec(p)
    out, res = generate(spec, "gbk", count=10, seed=42)
    assert res is not None
    assert len(res.records) == 10
    assert not [x for r in res.records for x in r.fields if x.error]
    assert not res.warnings
    # 每行恰 44 字节
    for ln in out.rstrip(b"\n").split(b"\n"):
        assert len(ln) == 44


def test_gen_delimited_roundtrip(tmp_path):
    p = tmp_path / "t1.yaml"
    p.write_text(DELIM_YAML, encoding="utf-8")
    spec = load_spec(p)
    out, res = generate(spec, "gbk", count=8, seed=7)
    assert len(res.records) == 8
    assert not [x for r in res.records for x in r.fields if x.error]
    # 分隔符每行固定 3 个
    for ln in out.rstrip(b"\n").split(b"\n"):
        assert ln.count(b"|") == 3


def test_gen_seed_reproducible(tmp_path):
    p = tmp_path / "t1.yaml"
    p.write_text(DELIM_YAML, encoding="utf-8")
    spec = load_spec(p)
    a, _ = generate(spec, "gbk", count=3, seed=99)
    b, _ = generate(spec, "gbk", count=3, seed=99)
    assert a == b


def test_gen_respects_sample_pool():
    fd = FieldDef(name="状态", type="enum", map={"1": "正常"}, sample=["KEEP"])
    import random
    vals = {gen_value(fd, random.Random(1)) for _ in range(20)}
    assert vals == {"KEEP"}


def test_fit_bytes_truncates_multibyte_safely():
    from structview.gen import _fit_bytes
    fd = FieldDef(name="名称", type="str", length=6)
    raw = _fit_bytes("货币基金", fd, "gbk")  # 8 字节 > 6，逐字收缩到 6 字节
    assert len(raw) == 6
    assert raw.decode("gbk") == "货币基"  # 不会截半个字符


def test_resolve_gen_encoding():
    spec = Spec(name="x", encoding="auto")
    assert resolve_gen_encoding(spec, None) == "utf-8"
    spec.encoding = "gbk"
    assert resolve_gen_encoding(spec, None) == "gbk"
    assert resolve_gen_encoding(spec, "utf-8") == "utf-8"
