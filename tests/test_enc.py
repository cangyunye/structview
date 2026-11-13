from structview.enc import decode_text, detect_encoding, resolve_encoding, strip_bom


def test_detect_utf8():
    enc, notes = detect_encoding("中文abc".encode("utf-8"))
    assert enc == "utf-8"


def test_detect_gbk_as_gb18030():
    enc, _ = detect_encoding("货币基金".encode("gbk"))
    assert enc == "gb18030"


def test_detect_bom():
    enc, notes = detect_encoding(b"\xef\xbb\xbfabc")
    assert enc == "utf-8-sig"
    assert any("BOM" in n for n in notes)


def test_detect_utf16_bom_before_utf32_prefix():
    # utf-32-le BOM 是 utf-16-le BOM 的超长前缀，必须先判 utf-32
    enc, _ = detect_encoding(b"\xff\xfe\x00\x00a\x00\x00\x00")
    assert enc == "utf-32-le"


def test_strip_bom():
    assert strip_bom(b"\xef\xbb\xbfabc") == b"abc"
    assert strip_bom(b"abc") == b"abc"


def test_cli_encoding_overrides_spec():
    data = "中文".encode("utf-8")
    enc, notes = resolve_encoding("gbk", "utf-8", data)
    assert enc == "utf-8"
    assert any("覆盖" in n for n in notes)


def test_spec_gbk_recovers_utf8_content():
    # GBK 严格解码 utf-8 中文会失败 → 自动降级探测并正确恢复为 utf-8
    data = "中文".encode("utf-8")
    enc, notes = resolve_encoding("gbk", None, data)
    assert enc == "utf-8"
    assert any("降级" in n for n in notes)


def test_spec_gbk_honored_when_content_is_gbk():
    data = "货币基金".encode("gbk")
    enc, notes = resolve_encoding("gbk", None, data)
    assert enc == "gbk"


def test_spec_gbk_fails_falls_back_to_auto():
    data = b"\x80abc"  # 0x80 不是合法 GBK 前导字节
    enc, notes = resolve_encoding("gbk", None, data)
    assert enc != "gbk"
    assert any("降级" in n for n in notes)


def test_decode_text_replacement_note():
    text, notes = decode_text(b"\x80abc", "utf-8")
    assert "\ufffd" in text
    assert notes


def test_decode_text_unknown_codec():
    text, notes = decode_text("abc".encode(), "not-a-codec")
    assert text == "abc"
    assert notes
