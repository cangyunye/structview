from structview.decoders.delimited import parse
from structview.spec import FieldDef, Spec


def make_spec(delim="|", quote='"') -> Spec:
    return Spec(name="T1", fmt="delimited", encoding="utf-8",
                delimiter=delim, quote=quote, fields=[
                    FieldDef(name="商户号"),
                    FieldDef(name="金额", type="dec", scale=2),
                    FieldDef(name="备注"),
                ])


def test_basic_types():
    res = parse("M001|10050|正常\n".encode(), make_spec(), "utf-8")
    r = res.records[0]
    assert r.fields[1].value == "100.50"
    assert r.fields[2].value == "正常"
    assert not res.warnings


def test_short_row_warns():
    res = parse("M001|500\n".encode(), make_spec(), "utf-8")
    assert any("2 < 3" in w for w in res.warnings)
    assert res.records[0].fields[2].value == ""
    assert res.records[0].warning


def test_extra_row_warns():
    res = parse("M001|1|ok|surplus\n".encode(), make_spec(), "utf-8")
    assert any("4 > 3" in w for w in res.warnings)


def test_quoted_delimiter():
    res = parse('M001|100|"含|竖线"\n'.encode(), make_spec(), "utf-8")
    assert res.records[0].fields[2].value == "含|竖线"


def test_quoted_newline_not_supported_but_quotechars_ok():
    # 引号内含分隔符与转义双引号
    res = parse('M001|1|"a""b"\n'.encode(), make_spec(), "utf-8")
    assert res.records[0].fields[2].value == 'a"b'


def test_multichar_delimiter_plain_split():
    res = parse("a||b||c\n".encode(), make_spec(delim="||", quote=None), "utf-8")
    assert [f.value for f in res.records[0].fields] == ["a", "b", "c"]


def test_generic_mode_without_spec():
    res = parse("a;b;c\n1;2;3\n".encode(), None, "utf-8")
    assert res.fmt == "generic"
    assert [f.name for f in res.records[0].fields] == ["col1", "col2", "col3"]
    assert res.records[1].fields[0].value == "1"


def test_generic_scans_delimiter_when_missing():
    res = parse("a|b|c\n".encode(), None, "utf-8")
    assert res.delimiter == "|"
    assert any("启发式" in w for w in res.warnings)


def test_empty_lines_skipped():
    res = parse("\nM001|1|x\n\n".encode(), make_spec(), "utf-8")
    assert len(res.records) == 1
    assert res.records[0].line_no == 2


def make_section_spec() -> Spec:
    s = make_spec()
    s.header_fields = [FieldDef(name="文件标识"), FieldDef(name="总笔数", type="int")]
    s.header_name = "清算头"
    s.tail_fields = [FieldDef(name="记录类型"), FieldDef(name="校验码")]
    s.tail_name = "清算尾"
    return s


def test_sections_delimited():
    data = "H|4\nM001|10050|正常\nM002|200|ok\nT|XYZ\n".encode()
    res = parse(data, make_section_spec(), "utf-8")
    assert res.header is not None and res.header.title == "文件头 · 清算头"
    assert [f.value for f in res.header.fields] == ["H", "4"]
    assert res.header.fields[1].type == "int"
    assert len(res.records) == 2
    assert (res.records[0].line_no, res.records[1].line_no) == (2, 3)  # 文件行号
    assert res.trailer is not None and res.trailer.title == "文件尾 · 清算尾"
    assert [f.value for f in res.trailer.fields] == ["T", "XYZ"]
    assert not res.warnings


def test_section_field_count_mismatch_warns():
    data = "H|4|extra\nM001|10050|正常\nT\n".encode()
    res = parse(data, make_section_spec(), "utf-8")
    assert any("文件头" in w and "字段数" in w for w in res.warnings)
    assert any("文件尾" in w and "字段数" in w for w in res.warnings)


def test_missing_tail_warns():
    res = parse("H|4\n".encode(), make_section_spec(), "utf-8")
    assert res.header is not None and res.trailer is None
    assert any("缺少尾记录" in w for w in res.warnings)
    assert res.records == []
