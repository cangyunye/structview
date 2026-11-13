from pathlib import Path

import pytest
import yaml

from structview.spec import (
    SpecError,
    find_spec,
    load_config,
    load_spec,
    match_config_overrides,
    spec_search_dirs,
)


def write_spec(path: Path, doc: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return path


DELIM_DOC = {
    "name": "T1", "format": "delimited", "delimiter": "|", "encoding": "gbk",
    "match": ["T1.111.*.csv"],
    "fields": [{"name": "a"}, {"name": "b"}],
}


def test_match_glob(tmp_path):
    d = tmp_path / "specs"
    write_spec(d / "t1.yaml", DELIM_DOC)
    spec, notes = find_spec("T1.111.2020.csv", [d])
    assert spec is not None and spec.name == "T1"
    assert any("match" in n for n in notes)
    assert find_spec("other.csv", [d])[0] is None


def test_find_spec_skips_invalid(tmp_path):
    d = tmp_path / "specs"
    d.mkdir()
    (d / "bad.yaml").write_text("format: nope\n", encoding="utf-8")
    write_spec(d / "ok.yaml", DELIM_DOC)
    spec, notes = find_spec("T1.111.2020.csv", [d])
    assert spec is not None
    assert any("bad.yaml" in n for n in notes)  # 无效 spec 被跳过并留痕


def test_delimited_requires_delimiter(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("name: x\nformat: delimited\nfields: [{name: a}]\n", encoding="utf-8")
    with pytest.raises(SpecError):
        load_spec(p)


def test_fixed_requires_len(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("name: x\nformat: fixed\nfields: [{name: a}]\n", encoding="utf-8")
    with pytest.raises(SpecError):
        load_spec(p)


def test_fixed_record_len_mismatch_warns(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(
        "name: x\nformat: fixed\nrecord_len: 100\n"
        "fields: [{name: a, len: 8}, {name: b, len: 4}]\n",
        encoding="utf-8",
    )
    spec = load_spec(p)
    assert any("≠" in w for w in spec.warnings)


def test_unknown_type_warns(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text(
        'name: x\nformat: delimited\ndelimiter: "|"\n'
        'fields: [{name: a, type: money2}]\n',
        encoding="utf-8",
    )
    spec = load_spec(p)
    assert spec.fields[0].type == "str"
    assert any("money2" in w for w in spec.warnings)


def test_enum_keys_normalized_to_str():
    doc = dict(DELIM_DOC)
    doc["fields"] = [{"name": "a", "type": "enum", "map": {1: "一", "2": "二"}}]
    p = write_spec(Path("/tmp") / "sv_test_enum.yaml", doc)
    spec = load_spec(p)
    assert spec.fields[0].map == {"1": "一", "2": "二"}


def test_layouts_reserved_warning(tmp_path):
    doc = dict(DELIM_DOC)
    doc["key_field"] = "a"
    doc["layouts"] = {"X": {"fields": [{"name": "a"}]}}
    p = write_spec(Path("/tmp") / "sv_test_layout.yaml", doc)
    spec = load_spec(p)
    assert any("预留" in w for w in spec.warnings)


def test_config_overrides(tmp_path):
    write_spec(tmp_path / "specs" / "x.yaml",
               {"name": "X", "format": "delimited", "delimiter": ";",
                "fields": [{"name": "c1"}]})
    cfg_path = tmp_path / ".structview"
    cfg_path.mkdir()
    (cfg_path / "config.yaml").write_text(yaml.safe_dump({
        "overrides": [{"glob": "a*.txt", "spec": "specs/x.yaml"}],
        "specs_dir": "specs",
    }, allow_unicode=True), encoding="utf-8")

    cfg = load_config(tmp_path)
    assert spec_search_dirs(cfg, tmp_path) == [tmp_path / "specs"]
    spec, src = match_config_overrides(cfg, "abc.txt", tmp_path)
    assert spec is not None and spec.name == "X"
    assert match_config_overrides(cfg, "other.txt", tmp_path)[0] is None


def test_sidecar_head_tail_loaded(tmp_path):
    p = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    (tmp_path / "s.head.yaml").write_text(
        yaml.safe_dump({"name": "清算头", "fields": [{"name": "总笔数", "type": "int"}]},
                       allow_unicode=True), encoding="utf-8")
    (tmp_path / "s.tail.yaml").write_text(
        yaml.safe_dump([{"name": "校验码"}], allow_unicode=True), encoding="utf-8")
    spec = load_spec(p)
    assert spec.header_fields is not None and spec.header_fields[0].name == "总笔数"
    assert spec.header_name == "清算头"
    assert spec.tail_fields is not None and spec.tail_fields[0].name == "校验码"


def test_sidecar_absent(tmp_path):
    spec = load_spec(write_spec(tmp_path / "s.yaml", DELIM_DOC))
    assert spec.header_fields is None and spec.tail_fields is None


def test_sidecar_malformed_warns_and_ignored(tmp_path):
    p = write_spec(tmp_path / "s.yaml", DELIM_DOC)
    (tmp_path / "s.head.yaml").write_text("fields: [{name: a}, 3]\n", encoding="utf-8")
    spec = load_spec(p)
    assert spec.header_fields is None
    assert any("s.head.yaml" in w for w in spec.warnings)


def test_find_spec_sidecars_not_standalone(tmp_path):
    d = tmp_path / "specs"
    write_spec(d / "t1.yaml", DELIM_DOC)
    (d / "t1.head.yaml").write_text("fields: [{name: a}]\n", encoding="utf-8")
    (d / "t1.tail.yaml").write_text("fields: [{name: a}]\n", encoding="utf-8")
    spec, notes = find_spec("T1.111.2020.csv", [d])
    assert spec is not None and spec.name == "T1"
    assert spec.header_fields is not None  # 命中主 spec 时顺便加载同名 sidecar
    d2 = tmp_path / "only"
    d2.mkdir()
    (d2 / "x.head.yaml").write_text("fields: [{name: a}]\n", encoding="utf-8")
    assert find_spec("T1.111.2020.csv", [d2])[0] is None  # sidecar 不作为独立协议
