import json

from structview.decoders.jsondec import parse


def test_whole_flat_array_becomes_table():
    data = b'[{"a": "1", "amount": 123456789012345.67}, {"a": "2", "amount": 9.9}]'
    res = parse(data, None, "utf-8")
    assert res.payload["mode"] == "table"
    assert len(res.records) == 2
    # parse_float=str 保精度
    assert res.records[0].fields[1].value == "123456789012345.67"
    assert res.records[1].fields[1].value == "9.9"


def test_whole_nested_is_pretty():
    data = b'{"a": {"b": 1}}'
    res = parse(data, None, "utf-8")
    assert res.payload["mode"] == "pretty"


def test_whole_flat_dict_is_kv():
    res = parse(b'{"name": "x", "n": 5, "ok": true, "none": null}', None, "utf-8")
    assert res.payload["mode"] == "kv"
    vals = {f.name: f.value for f in res.records[0].fields} if res.records else {}
    assert vals == {}  # kv 模式不走 records
    obj = res.payload["obj"]
    assert obj["n"] == 5 and obj["ok"] is True and obj["none"] is None


def test_jsonl_flat():
    data = b'{"a": 1}\n{"a": 2}\n'
    res = parse(data, None, "utf-8")
    assert res.payload["mode"] == "table"
    assert res.records[1].fields[0].value == "2"


def test_jsonl_nested_is_pretty():
    data = b'{"a": {"b": 1}}\n{"a": {"b": 2}}\n'
    res = parse(data, None, "utf-8")
    assert res.payload["mode"] == "pretty"
    assert res.payload["count"] == 2


def test_embedded_json_in_log():
    text = ("2026-01-01 INFO  POST /api HTTP/1.1\n"
            "Content-Type: application/json\n"
            '{"order": "O1", "amount": 10.5}\n'
            "2026-01-01 done")
    res = parse(text.encode(), None, "utf-8")
    assert res.payload["mode"] == "embedded"
    blk = res.payload["blocks"][0]
    assert blk["obj"] == {"order": "O1", "amount": "10.5"}
    assert any("Content-Type" in ln for ln in blk["context"])


def test_embedded_json_with_escapes_and_nesting():
    text = 'log {"a": {"b": "x{y}"}, "c": [1, 2]} tail'
    res = parse(text.encode(), None, "utf-8")
    blk = res.payload["blocks"][0]
    assert blk["obj"] == {"a": {"b": "x{y}"}, "c": [1, 2]}


def test_no_json_at_all():
    res = parse(b"plain text only\n", None, "utf-8")
    assert res.payload["mode"] == "pretty"
    assert res.payload["count"] == 0
    assert any("未找到" in w for w in res.warnings)


def test_cell_semantics():
    from structview.decoders.jsondec import _cell
    assert _cell(None) == ""
    assert _cell(True) == "true"
    assert _cell(False) == "false"
    assert _cell({"k": 1}) == json.dumps({"k": 1}, ensure_ascii=False)
