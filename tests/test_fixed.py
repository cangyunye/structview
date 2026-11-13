from structview.decoders.fixed import parse
from structview.spec import FieldDef, Spec


def make_spec() -> Spec:
    return Spec(name="产品表", fmt="fixed", encoding="gbk", record_len=44, fields=[
        FieldDef(name="PROD_CD", length=8),
        FieldDef(name="PROD_NM", length=20),
        FieldDef(name="RATE", type="dec", scale=5, length=7),
        FieldDef(name="EFF_DT", type="date", fmt="%Y%m%d", length=8),
        FieldDef(name="ST", type="enum", map={"1": "正常", "0": "停售"}, length=1),
    ])


def make_line() -> bytes:
    # GBK 下“货币基金”占 8 字节，字段总长 8+20+7+8+1 = 44
    line = (b"P0000001"
            + "货币基金".encode("gbk").ljust(20)
            + b"0025000" + b"20260101" + b"1")
    assert len(line) == 44
    return line


def test_fixed_byte_slicing_and_types():
    res = parse(make_line() + b"\n", make_spec(), "gbk")
    assert not res.warnings
    r = res.records[0]
    assert r.fields[1].value == "货币基金"
    assert r.fields[2].value == "0.25000"
    assert r.fields[3].value == "2026-01-01"
    assert r.fields[4].value == "正常"
    # 字节偏移
    assert (r.fields[0].offset, r.fields[0].length) == (0, 8)
    assert (r.fields[1].offset, r.fields[1].length) == (8, 20)
    assert (r.fields[2].offset, r.fields[2].length) == (28, 7)


def test_fixed_multiline():
    data = make_line() + b"\n" + make_line() + b"\n"
    res = parse(data, make_spec(), "gbk")
    assert len(res.records) == 2
    assert res.records[1].index == 2


def test_fixed_short_line_warns():
    res = parse(make_line()[:-1] + b"\n", make_spec(), "gbk")
    assert any("43B" in w for w in res.warnings)
    assert res.records[0].fields[4].value == ""


def test_fixed_trailing_bytes():
    res = parse(make_line() + b"XY" + b"\n", make_spec(), "gbk")
    assert any("尾料" in w for w in res.warnings)
    assert res.records[0].fields[-1].name == "…尾料"


def test_fixed_requires_spec():
    try:
        parse(make_line() + b"\n", None, "gbk")
        assert False, "应当抛出 ValueError"
    except ValueError as e:
        assert "spec" in str(e)


def test_fixed_field_level_encoding_override():
    spec = make_spec()
    spec.fields[1].encoding = "utf-8"
    # PROD_NM 位置放 utf-8 中文（6 字节）+ 14 空格 = 20 字节
    line = (b"P0000001"
            + "货币基金".encode("utf-8").ljust(20)
            + b"0025000" + b"20260101" + b"1")
    res = parse(line + b"\n", spec, "gbk")
    assert res.records[0].fields[1].value == "货币基金"
