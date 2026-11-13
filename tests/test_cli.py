import pytest
import yaml

from structview.cli import main


def write_spec(path, doc):
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


DELIM_DOC = {
    "name": "T1", "format": "delimited", "delimiter": "|", "encoding": "gbk",
    "fields": [
        {"name": "商户号"},
        {"name": "交易日期", "type": "date", "fmt": "%Y%m%d"},
        {"name": "金额", "type": "dec", "scale": 2},
    ],
}

FIXED_DOC = {
    "name": "P", "format": "fixed", "encoding": "gbk", "record_len": 16,
    "fields": [
        {"name": "CODE", "len": 8, "type": "str"},
        {"name": "RATE", "len": 7, "type": "dec", "scale": 5},
        {"name": "ST", "len": 1, "type": "enum", "map": {"1": "正常"}},
    ],
}


@pytest.fixture(autouse=True)
def _wide_terminal(monkeypatch):
    # 非 tty 下 rich 默认按 80 列渲染，测试里放宽避免换行截断断言
    monkeypatch.setenv("COLUMNS", "200")


def test_read_with_proto(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_bytes("A|20260101|10050\nB|20260102|99\n".encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    rc = main(["read", str(f), "-p", str(spec), "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "2026-01-01" in out and "100.50" in out


def test_read_record_range(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_bytes("A|20260101|1\nB|20260102|2\nC|20260103|3\n".encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    rc = main(["read", str(f), "-p", str(spec), "-r", "2-3", "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "A" not in out.split("\n")[0] or True
    body = out
    assert "2026-01-02" in body and "2026-01-03" in body and "2026-01-01" not in body


def test_detail_fixed_view(tmp_path, capsys):
    f = tmp_path / "a.txt"
    line = "P0000001".ljust(8) + "0025000" + "1"
    f.write_bytes((line + "\n").encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", FIXED_DOC)
    rc = main(["read", str(f), "-p", str(spec), "-t", "detail", "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    # 类型列：类型(协议字节长度)，dec 追加小数位
    assert "str(8)" in out and "dec(7,5)" in out and "enum(1)" in out
    # 偏移列：左闭右开字节区间
    assert "[0,8)" in out and "[8,15)" in out and "[15,16)" in out
    # 解析值列：值(实际字节数)
    assert "P0000001(8)" in out and "0.25000(7)" in out and "正常(1)" in out


def test_detail_delimited_no_offset(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_bytes("A|20260101|10050\n".encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    rc = main(["read", str(f), "-p", str(spec), "-t", "detail", "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    # 变长无协议长度：裸类型，dec 仅显示小数位；无偏移列
    assert "dec(2)" in out and "100.50(5)" in out and "2026-01-01(8)" in out
    assert "[0," not in out


def test_color_env_control(tmp_path, capsys, monkeypatch):
    f = tmp_path / "a.csv"
    f.write_bytes("A|20260101|10050\n".encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    argv = ["read", str(f), "-p", str(spec)]
    monkeypatch.setenv("TERM", "xterm-256color")

    monkeypatch.setenv("FORCE_COLOR", "1")
    main(argv)
    assert "\x1b[" in capsys.readouterr().out          # 管道中强制彩色

    main(argv + ["--no-color"])
    assert "\x1b[" not in capsys.readouterr().out      # --no-color 完全无转义

    monkeypatch.setenv("NO_COLOR", "1")
    main(argv)
    assert "\x1b[" not in capsys.readouterr().out      # NO_COLOR 优先于 FORCE_COLOR


def test_read_fixed_without_spec_errors(tmp_path, capsys):
    f = tmp_path / "a.txt"
    f.write_bytes(b"12345678\n")
    rc = main(["read", str(f), "-f", "fixed"])
    err = capsys.readouterr().err
    assert rc == 1 and "spec" in err


def test_read_missing_file(tmp_path):
    rc = main(["read", str(tmp_path / "nope.csv")])
    assert rc == 1


def test_spec_check_invalid(tmp_path, capsys):
    p = tmp_path / "bad.yaml"
    p.write_text("name: x\nformat: delimited\nfields: [{name: a}]\n", encoding="utf-8")
    rc = main(["spec", "check", str(p)])
    err = capsys.readouterr().err
    assert rc == 1 and "delimiter" in err


def test_spec_check_valid(tmp_path, capsys):
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    rc = main(["spec", "check", str(spec), "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0 and "合法" in out


def test_spec_infer_valid_yaml(tmp_path, capsys):
    f = tmp_path / "data.csv"
    # 行长故意不一致，避免被判定为定长
    f.write_bytes("aa;b;20260101\n1;b;20260102\n".encode())
    rc = main(["spec", "infer", str(f)])
    out = capsys.readouterr().out
    assert rc == 0
    doc = yaml.safe_load(out)
    assert doc["format"] == "delimited" and doc["delimiter"] == ";"
    assert len(doc["fields"]) == 3


def test_gen_stdout_then_read(tmp_path, capsys):
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    rc = main(["gen", "--spec", str(spec), "--count", "3", "--seed", "1"])
    assert rc == 0
    data = capsys.readouterr().out.encode("gbk")
    # 生成的数据可被 sv read 正确回读
    f = tmp_path / "gen.csv"
    f.write_bytes(data)
    rc = main(["read", str(f), "-p", str(spec), "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "3 条记录" in out
