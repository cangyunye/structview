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


def make_section_spec() -> Spec:
    s = make_spec()
    s.header_fields = [FieldDef(name="文件标识", length=1), FieldDef(name="总笔数", type="int", length=2)]
    s.tail_fields = [FieldDef(name="校验码", length=4)]
    return s


def test_fixed_sections_and_record_len_skips_head_tail():
    data = b"H05\n" + make_line() + b"\n" + make_line() + b"\n" + b"MD5X\n"
    res = parse(data, make_section_spec(), "gbk")
    assert not res.warnings  # 头 3B / 尾 4B ≠ record_len 44 不误报
    assert res.header is not None
    assert [f.value for f in res.header.fields] == ["H", "5"]  # int 格式化去前导零
    assert (res.header.fields[0].offset, res.header.fields[0].length) == (0, 1)
    assert len(res.records) == 2
    assert (res.records[0].line_no, res.records[1].line_no) == (2, 3)
    assert res.trailer is not None and res.trailer.fields[0].value == "MD5X"


def test_fixed_header_only_file_warns_missing_tail():
    spec = make_section_spec()
    spec.tail_fields = None
    spec.header_fields = [FieldDef(name="文件标识", length=1)]
    spec.tail_fields = [FieldDef(name="校验码", length=4)]
    res = parse(b"H\n", spec, "gbk")
    assert res.header is not None and res.trailer is None
    assert any("缺少尾记录" in w for w in res.warnings)


def test_fixed_single_line_as_tail():
    spec = make_spec()
    spec.tail_fields = [FieldDef(name="校验码", length=4)]
    res = parse(b"MD5X\n", spec, "gbk")
    assert res.trailer is not None and res.trailer.fields[0].value == "MD5X"
    assert res.records == []
