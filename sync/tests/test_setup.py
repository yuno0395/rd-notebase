"""tools/setup.py: bat 1つで準備と更新(管理者・PL・メンバー)。"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("setup_tool", ROOT / "tools" / "setup.py")
st = importlib.util.module_from_spec(SPEC)
sys.modules["setup_tool"] = st
SPEC.loader.exec_module(st)

TODAY = datetime(2026, 10, 27, 10, 0, tzinfo=st.JST)


class FakeExt(st.Ext):
    """git・winget・pytest は動かしたことにする。組み立て(build.py)と試し運転(notesync)は本当に動かす。"""

    def __init__(self, env):
        super().__init__(env)
        self.calls = []

    def run(self, args, cwd=None, env=None):
        self.calls.append(args)
        if args[:3] == [sys.executable, "-m", "notesync"] or (len(args) > 1 and args[1].endswith("build.py")):
            return super().run(args, cwd=cwd, env=env)
        if args[:2] == ["git", "status"] or args[:2] == ["git", "tag"] and len(args) > 2 and args[2] == "--list":
            return 0, ""
        return 0, "1 passed\n"

    def has(self, cmd):
        return cmd == "git"

    def obsidian_exe(self):
        return Path("Obsidian.exe")

    def obsidian_running(self):
        return False

    def shortcut(self, name, target):
        return True


def env_of(tmp: Path, pc: str) -> st.Env:
    return st.Env(app=tmp / pc / "AppData" / "知見同期", local=tmp / pc / "Local" / "知見同期",
                  obsidian_conf=tmp / pc / "AppData" / "obsidian" / "obsidian.json", home=tmp / pc / "home",
                  windows=False, pc_name=pc.upper())


def run(role, env, answers, dry=False, dist=None, hint=None):
    ui = st.UI(list(answers))
    s = st.Setup(role, dry, ui=ui, env=env, ext=FakeExt(env), shared_hint=hint, today=TODAY)
    if dist:
        s.dist = dist
    code = s.main()
    return code, s, ui


@pytest.fixture
def team(tmp_path):
    """管理者が最初の版 9.9.20 を出してチームの土台を作ったところ。"""
    box = tmp_path / "Box"
    box.mkdir()
    env = env_of(tmp_path, "admin")
    answers = [
        str(box),       # Box のフォルダ
        "",             # 共有 vault の場所(Box/チーム/開発ノート_共有)
        "", "",         # 開発データ・報告
        "9.9.20",       # 出す版
        "1",            # 自分は Yu(001)
        "adm",          # PC の記号
        "",             # 個人 vault の場所
        "",             # Enter で進む
        "n",            # タグは打たない
    ]
    code, s, ui = run("管理者", env, answers)
    assert code == 0, "\n".join(ui.out)
    yield {"box": box, "shared": box / "チーム" / "開発ノート_共有", "admin_env": env, "tmp": tmp_path, "ui": ui}
    shutil.rmtree(ROOT / "dist" / "9.9.20", ignore_errors=True)
    shutil.rmtree(ROOT / "dist" / "9.9.21", ignore_errors=True)


def test_version_helpers():
    assert st.bump("0.3.0") == "0.3.1"
    assert st.vkey("v0.10.0") > st.vkey("0.9.9")
    assert st.is_version("1.2.3") and not st.is_version("1.2")


def test_admin_first_time(team):
    shared = team["shared"]
    assert st.read_version(shared) == "9.9.20"
    assert (shared / st.PREP_DIR / st.LATEST).read_text(encoding="utf-8").strip() == "9.9.20"
    assert (shared / st.PREP_DIR / "プロジェクトリーダー.bat").is_file()
    assert (shared / st.DIST_DIR / "9.9.20" / "準備" / "setup.py").is_file()
    assert (shared / st.DIST_DIR / "9.9.20" / "同期プログラム" / "notesync" / "run.py").is_file()
    assert (shared / st.DIST_DIR / "9.9.20" / st.CHANGES).is_file()
    assert (team["box"] / "チーム" / "開発データ").is_dir()
    personal = team["box"] / "個人" / "開発ノート_Yu"
    assert st.my_settings(personal) == ("Yu", "")   # 3文字の古い記号は個人設定.md に書かない(メンバー.csv で読む)
    assert (shared / ".obsidian-001_adm" / "hotkeys.json").is_file()
    # 手で入れていた設定も bat で入る(貼ったファイルの置き場所・図・コアプラグイン)
    for d in (shared / ".obsidian-001_adm", personal / ".obsidian"):
        cal = json.loads((d / "plugins/obsidian-custom-attachment-location/data.json").read_text(encoding="utf-8"))
        assert cal["attachmentFolderPath"] == "_仕組み/attachments/{{attachDir}}"
        assert cal["shouldFollowObsidianAttachmentLocation"] is False and "attachDir" in cal["customTokensStr"]
        exc = json.loads((d / "plugins/obsidian-excalidraw-plugin/data.json").read_text(encoding="utf-8"))
        assert exc["compress"] is False and exc["onceOffCompressFlagReset"] is True and exc["autoexportSVG"] is True
        core = json.loads((d / "core-plugins.json").read_text(encoding="utf-8"))
        assert core["daily-notes"] is False and core["templates"] is False and core["canvas"] is False
        assert core["bases"] is True
    conf = st.read_config(team["admin_env"].config)
    assert conf["member"] == "Yu" and conf["dry_run"] is True and Path(conf["shared"]) == shared
    assert (team["admin_env"].program / "notesync" / "run.py").is_file()
    out = "\n".join(team["ui"].out)
    assert "Box の画面で、共有 vault" in out and "設定フォルダを上書き" in out


def test_pl_first_time_with_project_and_secret(team):
    shared, box = team["shared"], team["box"]
    # 管理者が佐藤を足す
    aenv = team["admin_env"]
    code, s, ui = run("管理者", aenv, ["2", "佐藤", "123456", ""])  # メンバーを足す(1回目は上書きがなく控えはない)
    assert code == 0, "\n".join(ui.out)
    assert ("佐藤", "123456") in st.read_members(shared)

    env = env_of(team["tmp"], "pl")
    dist = shared / st.DIST_DIR / "9.9.20"
    answers = [
        "2",             # 佐藤(123456)
        "pc1",           # PC の記号
        str(box),        # Box のフォルダ
        "",              # 個人 vault の場所
        "",              # 開発データ
        "", "",          # 週報を作る・報告フォルダ
        "y", "樹脂カバー量産", "1",  # プロジェクト(メンバーに Yu も)
        "y", str(box / "機密" / "顧客A"), "案件A",  # 機密フォルダ
        "",              # Enter で進む
    ]
    code, s, ui = run("PL", env, answers, dist=dist, hint=shared)
    out = "\n".join(ui.out)
    assert code == 0, out
    personal = box / "個人" / "開発ノート_佐藤"
    assert st.my_settings(personal) == ("佐藤", "123456")
    assert st.read_version(personal) == "9.9.20"
    assert (shared / ".obsidian-123456_pc1" / "app.json").is_file()
    # 台帳
    ledgers = list((shared / "樹脂カバー量産").glob("*_樹脂カバー量産.md"))
    assert len(ledgers) == 1
    text = ledgers[0].read_text(encoding="utf-8")
    code36 = st.notesync().ids.code_of("123456")
    assert ledgers[0].name[6:10] == code36
    assert "members: [佐藤, Yu]" in text and "<%" not in text and 'aliases: ["樹脂カバー量産"]' in text
    assert "| DR1 | 2026-12-08 | 2026-12-08 |" in text
    assert (shared / "樹脂カバー量産" / "03_イシュー").is_dir()
    # 機密フォルダと窓口
    secret = box / "機密" / "顧客A"
    assert (secret / "06_事実").is_dir() and st.read_version(secret) == "9.9.20"
    assert "「案件A」" in (secret / "00_README.md").read_text(encoding="utf-8")
    assert ("佐藤", "123456") in st.read_members_csv(secret / st.SECRET_CSV)
    assert (secret / ".obsidian-123456_pc1").is_dir()
    windows = list((shared / st.WINDOW_DIR).glob("*_案件A.md"))
    assert len(windows) == 1
    w = windows[0].read_text(encoding="utf-8")
    assert "readers: [佐藤]" in w and "顧客A" not in w
    conf = st.read_config(env.config)
    assert [Path(p) for p in conf["secret"]] == [secret]
    # 機密フォルダの名前は、共有 vault にも準備の記録にも書かない
    assert "顧客A" not in env.log.read_text(encoding="utf-8")
    # Obsidian の一覧
    vaults = json.loads(env.obsidian_conf.read_text(encoding="utf-8"))["vaults"]
    assert {Path(v["path"]) for v in vaults.values()} == {personal, shared, secret}
    # 試し運転が通った
    assert "試し運転しました" in out
    # 2回目は何もしない
    code, s, ui = run("PL", env, ["", "n", "n"], dist=dist, hint=shared)
    out = "\n".join(ui.out)
    assert code == 0 and "(なし。いまの版になっています)" in out, out


def test_new_version_and_backups(team, monkeypatch):
    shared, box = team["shared"], team["box"]
    aenv = team["admin_env"]
    personal = box / "個人" / "開発ノート_Yu"
    readme = personal / "00_README.md"
    readme.write_text("自分で書き換えた README\n", encoding="utf-8", newline="\n")  # 仕組みのファイルは版で上書きされる
    hk = personal / ".obsidian" / "hotkeys.json"
    keys = json.loads(hk.read_text(encoding="utf-8"))
    keys["mine:x"] = [{"modifiers": ["Alt"], "key": "X"}]                     # 自分で足したキー
    keys["mine:y"] = [{"modifiers": ["Mod"], "key": "N"}]                     # 配る Ctrl+N とぶつかる
    hk.write_text(json.dumps(keys), encoding="utf-8")
    note = personal / "02_ノード" / "0RDGPG001_水.md"
    note.write_text("---\nid: 0RDGPG001\n---\n", encoding="utf-8")
    code, s, ui = run("管理者", aenv, ["1", "9.9.21", "", "n"])  # 新しい版(1回目は上書きがなく控えはない)
    out = "\n".join(ui.out)
    assert code == 0, out
    assert st.read_version(shared) == "9.9.21" and st.read_version(personal) == "9.9.21"
    assert readme.read_text(encoding="utf-8") != "自分で書き換えた README\n"
    assert note.read_text(encoding="utf-8") == "---\nid: 0RDGPG001\n---\n"
    keys = json.loads(hk.read_text(encoding="utf-8"))
    assert keys["mine:x"] == [{"modifiers": ["Alt"], "key": "X"}] and keys["mine:y"] == []  # 版を当てても残る。ぶつかる分は外れる
    assert "キーがぶつかりました: Ctrl+N" in out                                          # 画面と「手でやること」で知らせる   # ノートは触らない
    backs = s.backups.previous()
    assert len(backs) == 1
    with zipfile.ZipFile(backs[-1] / "個人vault.zip") as z:
        assert z.read("00_README.md").decode("utf-8") == "自分で書き換えた README\n"
    assert (backs[-1] / "状態.txt").read_text(encoding="utf-8").strip() == "終わった"
    # 次に押したとき、残すを選べば残り、捨てるを選べば消える
    code, s, ui = run("管理者", aenv, ["1", "3", ""])
    assert code == 0 and len(s.backups.previous()) == 1
    code, s, ui = run("管理者", aenv, ["", "3", ""])   # 前回は最後まで終わったので Enter は「捨てる」
    assert code == 0 and s.backups.previous() == []


def test_backups_default(tmp_path):
    b = st.Backups(tmp_path / "控え", dry=False)
    b.start()
    ui = st.UI([""])
    b.review(ui)   # 途中で止まった控えは、Enter で残す
    assert len(b.previous()) == 1
    b.finish()
    b2 = st.Backups(tmp_path / "控え", dry=False)
    b2.review(st.UI([""]))  # 終わった控えは、Enter で捨てる
    assert b2.previous() == []


def test_rename_vault_then_press_again(team):
    box, shared = team["box"], team["shared"]
    aenv = team["admin_env"]
    personal = box / "個人" / "開発ノート_Yu"
    renamed = box / "個人" / "Yu のノート"
    personal.rename(renamed)
    code, s, ui = run("管理者", aenv, ["3", ""])  # 自分の環境だけ
    out = "\n".join(ui.out)
    assert code == 0, out
    assert Path(st.read_config(aenv.config)["personal"]) == renamed
    vaults = json.loads(aenv.obsidian_conf.read_text(encoding="utf-8"))["vaults"]
    assert renamed in {Path(v["path"]) for v in vaults.values()}
    assert personal not in {Path(v["path"]) for v in vaults.values()}


def test_dry_run_changes_nothing(team):
    shared, box = team["shared"], team["box"]
    env = env_of(team["tmp"], "member")
    dist = shared / st.DIST_DIR / "9.9.20"
    code, s, ui = run("メンバー", env, ["1", "m1", str(box), str(box / "個人" / "試し"), "", "n"], dry=True, dist=dist, hint=shared)
    out = "\n".join(ui.out)
    assert code == 0 and "試しなので、ここでやめます" in out, out
    assert not (box / "個人" / "試し").exists()
    assert not env.config.exists() and not env.app.exists()
    assert not (shared / ".obsidian-001_m1").exists()


def test_member_not_in_csv_stops(team):
    shared = team["shared"]
    env = env_of(team["tmp"], "x")
    (shared / st.MEMBER_CSV).write_text("名前,番号,使い始めた日\n", encoding="utf-8")
    code, s, ui = run("メンバー", env, [], dist=shared / st.DIST_DIR / "9.9.20", hint=shared)
    assert code == 1 and "管理者に登録を頼んで" in "\n".join(ui.out)


def test_config_line_edits(tmp_path):
    p = tmp_path / "config.yaml"
    st.write_new_config(p, {"member": "Yu", "personal": "C:/a"}, [])
    assert st.add_secret(p, Path("C:/s1"))
    assert st.add_secret(p, Path("C:/s2"))
    assert not st.add_secret(p, Path("C:/s1"))
    assert st.set_key(p, "report", "C:/r")
    import yaml
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert [Path(x) for x in data["secret"]] == [Path("C:/s1"), Path("C:/s2")]
    assert data["report"] == "C:/r" and data["dry_run"] is True


def test_check_new_member():
    m = [("Yu", "229999")]
    assert st.check_new_member(m, "佐藤", "12345") != ""
    assert "Yu" in st.check_new_member(m, "鈴木", "229999")
    assert st.check_new_member(m, "佐藤", "123456") == ""


def test_write_changes(tmp_path):
    spec = ("# 仕様書 v0.53\n\n## 変更履歴\n\n- 2026-10-27 v0.53: 新しいこと\n- 2026-10-26 v0.52: 前のこと\n"
            "- 2026-10-25 v0.51: もっと前\n")
    prev = tmp_path / "prev.md"
    prev.write_text("# この版で変わること(仕様書 v0.52 まで)\n", encoding="utf-8")
    t = st.write_changes(tmp_path / "out", spec, prev).read_text(encoding="utf-8")
    assert "新しいこと" in t and "前のこと" not in t and "v0.53 まで" in t


def test_sync_report_tells_new_version(tmp_path):
    from notesync.report import Report
    from notesync.run import notice_new_version
    personal, shared = tmp_path / "個人", tmp_path / "共有"
    (personal / "_仕組み/記録").mkdir(parents=True)
    (personal / "_仕組み/記録/版.txt").write_text("0.3.0\n", encoding="utf-8")
    (shared / st.PREP_DIR).mkdir(parents=True)
    (shared / st.PREP_DIR / st.LATEST).write_text("0.3.1\n", encoding="utf-8")
    r = Report()
    notice_new_version(personal, shared, r)
    assert r.todos and "0.3.1" in r.todos[0]
    (personal / "_仕組み/記録/版.txt").write_text("0.3.1\n", encoding="utf-8")
    r = Report()
    notice_new_version(personal, shared, r)
    assert not r.todos


def test_input_ended_stops(monkeypatch):
    """答えが流れてこない(EOF)ときは、既定値で同じ質問を繰り返さずに止める。"""
    def eof(_prompt=""):
        raise EOFError
    monkeypatch.setattr("builtins.input", eof)
    ui = st.UI()
    with pytest.raises(st.Stop):
        ui.ask("Box Drive のフォルダ", "C:/nowhere")


def test_migrations_for_old_vaults(tmp_path):
    """版.txt のない vault(bat より前に作ったもの)にも移し替えを当てる。もう当てた版の vault には当てない。"""
    dist = tmp_path / "0.2.0"
    (dist / "個人" / "_仕組み" / "記録").mkdir(parents=True)
    (dist / "個人" / "_仕組み" / "記録" / "版.txt").write_text("0.2.0\n", encoding="utf-8")
    shutil.copy2(ROOT / "manifest.toml", dist / "manifest.toml")
    names = [Path(m["script"]).name for m in st.load_manifest(dist)["migrate"]]
    assert names == ["migrate_v054.py", "migrate_v055.py"]
    old = tmp_path / "古い個人"
    (old / "_仕組み").mkdir(parents=True)
    assert [p.name for _, p in st.plan_vault(dist, "個人", old).migrations] == names
    (old / "_仕組み" / "記録").mkdir()
    (old / "_仕組み" / "記録" / "版.txt").write_text("0.2.0\n", encoding="utf-8")
    assert st.plan_vault(dist, "個人", old).migrations == []
    assert st.plan_vault(dist, "個人", tmp_path / "新しい個人").migrations == []   # これから作る vault
