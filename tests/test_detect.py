from structview.detect import detect, detect_line_ending, guess_field_type, scan_delimiter


def test_fixed_uniform_line_lengths():
    data = b"A" * 10 + b"\n" + b"B" * 10 + b"\n"
    det = detect(data)
    assert det.fmt == "fixed"
    assert "一致" in det.notes[0]


def test_delimiter_prefers_pipe():
    d, why = scan_delimiter(["a|b|c", "1|2|3"])
    assert d == "|"
    assert why and "固定出现 2 次" in why


def test_delimiter_tab():
    d, _ = scan_delimiter(["a\tb", "c\td"])
    assert d == "\t"


def test_delimiter_inconsistent_returns_none():
    assert scan_delimiter(["a|b|c", "1|2"]) == (None, None)


def test_json_whole():
    assert detect(b'{"a": 1}').fmt == "json"


def test_jsonl():
    det = detect(b'{"a": 1}\n{"a": 2}\n')
    assert det.fmt == "json"
    assert any("JSON Lines" in n for n in det.notes)


def test_embedded_json_in_log():
    data = (b"log line\n"
            b'{"a": 1}\n'
            b"tail line\n"
            b'{"b": 2}\n')
    det = detect(data)
    assert det.fmt == "json"
    assert any("内嵌" in n for n in det.notes)


def test_delimited_fallback():
    # 行长故意不一致，避免被判定为定长
    det = detect("aa;b;c\n1;2;3\n".encode())
    assert det.fmt == "delimited"
    assert det.delimiter == ";"


def test_generic_fallback():
    det = detect("hello world\nanother line\n".encode())
    assert det.fmt == "generic"


def test_guess_date():
    t, extra, note = guess_field_type(["20260101", "20260102"])
    assert t == "date" and extra["fmt"] == "%Y%m%d" and note


def test_guess_datetime():
    t, extra, _ = guess_field_type(["20260101093000"])
    assert t == "date" and extra["fmt"] == "%Y%m%d%H%M%S"


def test_guess_int_and_dec():
    assert guess_field_type(["1", "22", "333"])[0] == "int"
    t, extra, _ = guess_field_type(["1.50", "2.25"])
    assert t == "dec" and extra["scale"] == 2


def test_guess_enum():
    t, _, note = guess_field_type(["PAID", "NEW", "PAID", "FAIL"])
    assert t == "enum" and "PAID" in note


def test_line_ending_styles():
    assert detect_line_ending(b"a\nb\n")[0] == "unix"
    assert detect_line_ending(b"a\r\nb\r\n")[0] == "dos"
    assert detect_line_ending(b"a\rb")[0] == "mac"  # 纯 Mac 行尾不含 \n
    assert detect_line_ending(b"abc")[0] == "none"
    code, desc = detect_line_ending(b"a\r\nb\nc\rd")
    assert code == "mixed"
    assert "CRLF" in desc and "LF" in desc and "CR" in desc


def test_detect_reports_line_ending():
    det = detect(b"A" * 10 + b"\r\n" + b"B" * 10 + b"\r\n")
    assert det.line_ending == "dos"
    assert "DOS" in det.line_ending_desc
