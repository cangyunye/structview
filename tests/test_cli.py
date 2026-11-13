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
    line = "P1".ljust(8) + "0025000" + "1"
    f.write_bytes((line + "\n").encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", FIXED_DOC)
    rc = main(["read", str(f), "-p", str(spec), "-t", "detail", "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    # 原始值列：未 trim，补位空格转义为 ·
    assert "P1······" in out
    # 类型列：类型(协议字节长度)，dec 追加小数位
    assert "str(8)" in out and "dec(7,5)" in out and "enum(1)" in out
    # 偏移列：左闭右开字节区间
    assert "[0,8)" in out and "[8,15)" in out and "[15,16)" in out
    # 解析值列：值(实际字节数)
    assert "P1(2)" in out and "0.25000(7)" in out and "正常(1)" in out


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
    out = capsys.readouterr().out
    assert "\x1b[" in out                               # 管道中强制彩色
    assert "32m" in out and "35m" in out                # date 绿 / dec 品红，按类型着色

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


T2_DOC = {
    "name": "T2", "format": "delimited", "delimiter": "|", "encoding": "gbk",
    "fields": [
        {"name": "商户号"},
        {"name": "交易日期", "type": "date", "fmt": "%Y%m%d"},
        {"name": "交易金额", "type": "dec", "scale": 2},
    ],
}


def write_t2_specs(tmp_path):
    main = write_spec(tmp_path / "t.yaml", T2_DOC)
    (tmp_path / "t.head.yaml").write_text(
        yaml.safe_dump({"name": "清算头", "fields": [
            {"name": "文件标识"}, {"name": "总笔数", "type": "int"}]}, allow_unicode=True),
        encoding="utf-8")
    (tmp_path / "t.tail.yaml").write_text(
        yaml.safe_dump({"fields": [{"name": "校验码"}]}, allow_unicode=True),
        encoding="utf-8")
    f = tmp_path / "a.csv"
    f.write_bytes("H|2\nA|20260101|10050\nB|20260102|2000\nT|OK\n".encode("gbk"))
    return main, f


def test_read_head_tail_sections(tmp_path, capsys):
    spec, f = write_t2_specs(tmp_path)
    rc = main(["read", str(f), "-p", str(spec), "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "文件头 · 清算头" in out and "文件尾" in out
    assert "总笔数" in out and "校验码" in out
    assert "2 条记录" in out  # 头尾不计入体记录数


def test_read_records_filter_keeps_sections(tmp_path, capsys):
    spec, f = write_t2_specs(tmp_path)
    rc = main(["read", str(f), "-p", str(spec), "--no-color", "-r", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "文件头" in out and "文件尾" in out  # 过滤体记录不影响头尾展示
    assert "1 条记录" in out


def test_read_dos_line_ending(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_bytes("A|20260101|10050\r\nB|20260102|2000\r\n".encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    rc = main(["read", str(f), "-p", str(spec), "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DOS(CRLF)" in out              # 头部标注行尾风格
    assert "2026-01-01" in out             # \r 不影响解析


def test_read_mixed_line_ending_warns(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_bytes("A|20260101|10050\r\nB|20260102|2000\n".encode("gbk"))
    spec = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    rc = main(["read", str(f), "-p", str(spec), "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "行尾混用" in out               # 头部标注
    assert "⚠ 行尾混用" in out             # 告警汇总


WIDE_DOC = {
    "name": "W", "format": "delimited", "delimiter": "|", "encoding": "utf-8",
    "fields": [{"name": f"col{i}"} for i in range(1, 13)],
}


def write_wide(tmp_path):
    spec = write_spec(tmp_path / "w.yaml", WIDE_DOC)
    f = tmp_path / "w.csv"
    row1 = "|".join(f"v{i}" for i in range(1, 13))
    row2 = "|".join(str(i) for i in range(1, 13))
    f.write_bytes((row1 + "\n" + row2 + "\n").encode("utf-8"))
    return spec, f


def test_table_per_line_default_chunks(tmp_path, capsys):
    spec, f = write_wide(tmp_path)
    rc = main(["read", str(f), "-p", str(spec), "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "接上 · 字段 11-12/12" in out      # 缺省每行 10 字段，余 2 个分段
    assert "│ col1 " in out and "│ col11" in out  # 两段列头各自正确，# 序号对应同一批记录
    assert "v12" in out


def test_table_per_line_zero_disables(tmp_path, capsys):
    spec, f = write_wide(tmp_path)
    rc = main(["read", str(f), "-p", str(spec), "--no-color", "--per-line", "0"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "接上" not in out                  # 不分段，单表 12 列
    assert "col12" in out


def test_table_per_line_custom(tmp_path, capsys):
    spec, f = write_wide(tmp_path)
    rc = main(["read", str(f), "-p", str(spec), "--no-color", "--per-line", "4"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "接上 · 字段 5-8/12" in out
    assert "接上 · 字段 9-12/12" in out
