from structview.fields import format_value, normalize_type, visible
from structview.spec import FieldDef


def fd(**kw) -> FieldDef:
    return FieldDef(name="x", **kw)


def test_dec_implied_scale():
    v, e = format_value(fd(type="dec", scale=2), "10050")
    assert v == "100.50" and e is None


def test_dec_with_dot():
    v, e = format_value(fd(type="dec", scale=2), "100.5")
    assert v == "100.50" and e is None


def test_dec_zero_scale():
    v, e = format_value(fd(type="dec", scale=0), "10050")
    assert v == "10050" and e is None


def test_dec_negative():
    v, e = format_value(fd(type="dec", scale=2), "-10050")
    assert v == "-100.50" and e is None


def test_int_leading_zeros():
    assert format_value(fd(type="int"), "00042") == ("42", None)


def test_date_default_fmt():
    v, e = format_value(fd(type="date"), "20260101")
    assert v == "2026-01-01" and e is None


def test_date_custom_fmt():
    v, e = format_value(fd(type="date", fmt="%Y-%m-%d"), "2026-01-01")
    assert v == "2026-01-01" and e is None


def test_time():
    v, e = format_value(fd(type="time"), "093000")
    assert v == "09:30:00" and e is None


def test_hex_grouping():
    v, e = format_value(fd(type="hex"), "414243")
    assert v == "41 42 43" and e is None


def test_enum_mapped_and_unknown():
    f = fd(type="enum", map={"00": "成功", "01": "待清算"})
    assert format_value(f, "00") == ("成功", None)
    assert format_value(f, "09") == ("09", None)  # 未知枚举原样显示


def test_unknown_type_falls_back_to_str():
    v, e = format_value(fd(type="money2"), "123")
    assert v == "123" and e is None
    assert normalize_type("money2") == "str"


def test_bad_int():
    v, e = format_value(fd(type="int"), "12x3")
    assert v == "12x3" and e


def test_bad_date():
    v, e = format_value(fd(type="date", fmt="%Y%m%d"), "20261399")
    assert v == "20261399" and e


def test_empty_is_empty():
    v, e = format_value(fd(type="int"), "   ")
    assert v == "" and e is None


def test_visible_padding():
    assert visible("ab  ") == "ab··"
