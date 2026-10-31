"""F-50: vault の名前を変えても、同期が新しい場所を見つけて設定を直す。見つからなければ何も作らずに止まる。"""

import shutil
from pathlib import Path

from notesync.config import load
from notesync.relocate import VAULT_ID, record_path, rewrite_config
from notesync.run import run_once

from .conftest import SAMPLE


def setup(tmp_path: Path, dry: bool = False) -> tuple[Path, Path]:
    box = tmp_path / "Box"
    shutil.copytree(SAMPLE, box)
    (box / "共有/_仕組み/同期設定.yaml").write_text("{}\n", encoding="utf-8")
    appdata = tmp_path / "appdata"
    appdata.mkdir()
    conf = appdata / "config.yaml"
    conf.write_text(
        "member: Yu   # 名前\n"
        f"personal: {(box / '個人').as_posix()}\n"
        f"shared: \"{(box / '共有').as_posix()}\"   # 共有\n"
        "secret:\n"
        f"  - {(box / '機密').as_posix()}\n"
        f"dry_run: {'true' if dry else 'false'}\n"
        "idle_seconds: 0\n"
        f"backup_dir: {(tmp_path / 'backup').as_posix()}\n",
        encoding="utf-8")
    return box, conf


def test_ids_are_placed_and_remembered(tmp_path):
    box, conf = setup(tmp_path)
    load(conf)
    for name in ("個人", "共有", "機密"):
        assert (box / name / VAULT_ID).read_text(encoding="utf-8").strip()
    assert record_path(conf).exists()


def test_renamed_vaults_are_followed(tmp_path):
    box, conf = setup(tmp_path)
    load(conf)                                   # 名前を変える前に1回動いている
    (box / "個人").rename(box / "開発ノート_Yu")
    (box / "共有").rename(box / "開発ノート_共有")
    (box / "機密").rename(box / "顧客A")
    cfg = load(conf)
    assert cfg.personal == box / "開発ノート_Yu"
    assert cfg.shared == box / "開発ノート_共有"
    assert cfg.secret == [box / "顧客A"]
    text = conf.read_text(encoding="utf-8")
    assert "開発ノート_Yu" in text and "# 共有" in text and "# 名前" in text  # コメントは残す
    assert f"\"{(box / '開発ノート_共有').as_posix()}\"" in text               # 引用符もそのまま
    assert list(conf.parent.glob("config.yaml.*.bak"))                      # 直す前の控え
    report = run_once(cfg)
    assert not report.stopped
    assert any("設定を直した" in r for r in (box / "開発ノート_Yu/_仕組み/同期レポート.md").read_text(encoding="utf-8").splitlines())
    assert not (box / "個人").exists()                                      # 古い名前のフォルダは作らない


def test_renamed_while_watching(tmp_path):
    box, conf = setup(tmp_path)
    cfg = load(conf)
    (box / "個人").rename(box / "個人2")
    report = run_once(cfg)                        # watch 中に名前が変わった
    assert not report.stopped and cfg.personal == box / "個人2"
    assert not (box / "個人").exists()


def test_found_by_content_without_record(tmp_path):
    box, conf = setup(tmp_path)
    (box / "個人/_仕組み/個人設定.md").write_text('---\nname: Yu\n---\n', encoding="utf-8")
    (box / "共有").rename(box / "共有_新")       # この PC ではまだ1回も動いていない
    (box / "個人").rename(box / "個人_新")
    cfg = load(conf)
    assert cfg.shared == box / "共有_新"
    assert cfg.personal == box / "個人_新"


def test_parent_renamed_too(tmp_path):
    box, conf = setup(tmp_path)
    load(conf)
    (box / "顧客").mkdir()
    (box / "機密").rename(box / "顧客/顧客A")
    cfg = load(conf)
    assert cfg.secret == [box / "顧客/顧客A"]


def test_two_candidates_are_not_chosen(tmp_path):
    box, conf = setup(tmp_path)
    for d in ("個人_a", "個人_b"):
        (box / d / "_仕組み").mkdir(parents=True)
        (box / d / "_仕組み/個人設定.md").write_text("---\nname: Yu\n---\n", encoding="utf-8")
    shutil.rmtree(box / "個人")
    cfg = load(conf)
    assert cfg.personal == box / "個人"
    assert any("選べません" in w for w in cfg.move_warnings)
    report = run_once(cfg)
    assert report.stopped and "個人 vault が見つかりません" in report.stopped
    assert not (box / "個人").exists()


def test_missing_secret_stops_before_sharing(tmp_path):
    box, conf = setup(tmp_path)
    shutil.rmtree(box / "機密")                  # 権限が外れた・消えた
    cfg = load(conf)
    before = sorted(p.relative_to(box / "共有").as_posix() for p in (box / "共有").rglob("*"))
    report = run_once(cfg)
    assert "機密フォルダが見つかりません" in report.stopped
    after = sorted(p.relative_to(box / "共有").as_posix() for p in (box / "共有").rglob("*"))
    assert before == after                         # 共有へは何も送らない
    assert "機密フォルダが見つかりません" in (box / "個人/_仕組み/同期レポート.md").read_text(encoding="utf-8")


def test_dry_run_does_not_rewrite_config(tmp_path):
    box, conf = setup(tmp_path, dry=True)
    load(conf)
    before = conf.read_text(encoding="utf-8")
    (box / "個人").rename(box / "個人2")
    cfg = load(conf)
    assert cfg.personal == box / "個人2"
    assert conf.read_text(encoding="utf-8") == before
    report = run_once(cfg)
    assert any("設定を" in r and "直す" in r for r in report.records)


def test_rewrite_keeps_backslashes(tmp_path):
    conf = tmp_path / "config.yaml"
    conf.write_text("personal: C:\\Users\\a\\Box\\個人   # 個人\n", encoding="utf-8")
    old = Path(str(tmp_path / "x"))  # 形だけ確かめる(Windows の区切りは Linux では1つの名前になる)
    assert not rewrite_config(conf, old, tmp_path / "y")
    conf.write_text(f"personal: {old}   # 個人\n", encoding="utf-8")
    assert rewrite_config(conf, old, tmp_path / "y")
    assert conf.read_text(encoding="utf-8") == f"personal: {tmp_path / 'y'}   # 個人\n"


def test_moved_to_sibling_folder(tmp_path):
    box, conf = setup(tmp_path)
    (box / "個人_親").mkdir()
    (box / "個人").rename(box / "個人_親/開発ノート_Yu")
    conf.write_text(conf.read_text(encoding="utf-8").replace((box / "個人").as_posix(), (box / "個人_親/開発ノート_Yu").as_posix()), encoding="utf-8")
    load(conf)
    (box / "チーム").mkdir()
    (box / "個人_親/開発ノート_Yu").rename(box / "チーム/開発ノート_Yu")   # 親の隣のフォルダへ動かした
    cfg = load(conf)
    assert cfg.personal == box / "チーム/開発ノート_Yu"


def test_backup_copy_is_not_taken_for_the_real_vault(tmp_path):
    """元の場所が見えないとき、同じ印を持つ控え(丸ごとの写し)を本物として選ばない(F-55)。"""
    box, conf = setup(tmp_path)
    load(conf)
    shutil.copytree(box / "共有", box / "共有の控え")
    shutil.rmtree(box / "共有")
    cfg = load(conf)
    assert cfg.shared == box / "共有"                                       # 控えへは切り替えない
    assert "共有の控え" not in conf.read_text(encoding="utf-8")
