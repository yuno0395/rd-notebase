"""環境の準備と版の更新を1回で行う(仕様書「bat 1つで準備と更新」)。bat から呼ぶ。

    python setup.py 管理者 [試し]     正本(rd-notebase)の tools/ から。版を出して配る・共有 vault を用意する
    python setup.py PL [試し]         共有 vault の _仕組み/tools/準備/ の bat から。自分の環境＋プロジェクトの準備
    python setup.py メンバー [試し]   同じ。自分の環境だけ

どの役も、状態を見て「いま足りないこと」だけをする。何度押してもよい。
1. 前回までの控えを残すか捨てるかを聞く(Yu 2026-10-27)
2. 最初に聞くことをまとめて聞く(2回目からは覚えた答えを使う)
3. 「これからすること」を出し、Enter で進める(試し なら出すだけで何も変えない)
4. 書き換える前のファイルを控えの zip に入れてから、順にする
5. 最後に、手でやることだけを出す

ノート(01〜05、90_共有、日誌)は読まないし書かない。書くのは manifest.toml の仕組みのファイル・
最初だけのファイル、各自の設定フォルダ、PL が作る台帳と機密の窓口だけ。

Python 3.11 以上。yaml を読む部品(pyyaml)がなければ入れる。
"""

from __future__ import annotations

import csv
import fnmatch
import functools
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
# 正本の中(<正本>/tools/setup.py)か、配布物の中(<版>/準備/setup.py)か
if (HERE.parent / "manifest.toml").is_file() and (HERE.parent / "sync" / "notesync").is_dir():
    REPO: Path | None = HERE.parent
    DIST: Path | None = None
    SYNC_SRC = HERE.parent / "sync"
else:
    REPO = None
    DIST = HERE.parent
    SYNC_SRC = HERE.parent / "同期プログラム"

JST = timezone(timedelta(hours=9))
DEFAULT_REPO_DIR = Path(r"C:\dev\rd-notebase")
REPO_URL = "https://github.com/yuno0395/rd-notebase.git"
SYSTEM = "_仕組み"
VERSION_FILE = Path(SYSTEM) / "記録" / "版.txt"
MEMBER_CSV = Path(SYSTEM) / "tools" / "同期プログラム" / "メンバー.csv"
SECRET_CSV = Path(SYSTEM) / "tools" / "メンバー.csv"
SETTINGS = Path(SYSTEM) / "設定" / ".obsidian"
MY_SETTINGS = Path(SYSTEM) / "個人設定.md"
DIST_DIR = Path(SYSTEM) / "tools" / "配布"
PREP_DIR = Path(SYSTEM) / "tools" / "準備"
LATEST = "最新の版.txt"
CHANGES = "この版で変わること.md"
WINDOW_DIR = Path("共通") / "機密の窓口"
SEEN_VERSION = "知見同期の版.txt"  # 各自の設定フォルダに置く(管理者が誰が古いままかを見るため)
WINGET = {"Python": "Python.Python.3.12", "Git": "Git.Git", "Obsidian": "Obsidian.Obsidian"}


# ---------- 周りの決まり(テストで差し替える) ----------

@dataclass
class Env:
    app: Path          # %APPDATA%\知見同期(config.yaml・控え・記録)
    local: Path        # %LOCALAPPDATA%\知見同期(同期プログラムの本体)
    obsidian_conf: Path  # %APPDATA%\obsidian\obsidian.json
    home: Path
    windows: bool
    pc_name: str

    @classmethod
    def from_os(cls) -> "Env":
        appdata = Path(os.environ.get("APPDATA") or Path.home() / ".config")
        localapp = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
        return cls(app=appdata / "知見同期", local=localapp / "知見同期",
                   obsidian_conf=appdata / "obsidian" / "obsidian.json", home=Path.home(),
                   windows=os.name == "nt", pc_name=os.environ.get("COMPUTERNAME") or os.uname().nodename)

    @property
    def config(self) -> Path:
        return self.app / "config.yaml"

    @property
    def memo(self) -> Path:
        return self.app / "準備.json"   # この PC で覚えておくこと(PC の記号など)。Box には置かない

    @property
    def log(self) -> Path:
        return self.app / "準備の記録.txt"

    @property
    def program(self) -> Path:
        return self.local / "プログラム"


class Ext:
    """外のプログラムを動かすところ。テストでは何もしないものに差し替える。"""

    def __init__(self, env: Env):
        self.env = env

    def run(self, args: list[str], cwd: Path | None = None, env: dict | None = None) -> tuple[int, str]:
        # 子の Python の出力を UTF-8 にする(Windows のパイプは cp1252 などになり、日本語で落ちる)
        env = dict(env if env is not None else os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
        try:
            p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except OSError as e:
            return 127, str(e)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def has(self, cmd: str) -> bool:
        return shutil.which(cmd) is not None

    def winget(self, what: str) -> bool:
        if not self.has("winget"):
            return False
        code, _ = self.run(["winget", "install", "--id", WINGET[what], "-e", "--scope", "user",
                            "--accept-package-agreements", "--accept-source-agreements"])
        return code == 0

    def obsidian_exe(self) -> Path | None:
        for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("ProgramFiles")):
            if base:
                for p in (Path(base) / "Programs" / "Obsidian" / "Obsidian.exe", Path(base) / "Obsidian" / "Obsidian.exe"):
                    if p.is_file():
                        return p
        return None

    def obsidian_running(self) -> bool:
        if not self.env.windows:
            return False
        code, out = self.run(["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"])
        return code == 0 and "obsidian.exe" in out.lower()

    def open_url(self, url: str) -> None:
        if self.env.windows:
            try:
                os.startfile(url)  # type: ignore[attr-defined]
            except OSError:
                pass

    def clip(self, text: str) -> None:
        if self.env.windows:
            try:
                subprocess.run(["clip"], input=text.encode("utf-16le"), check=False)
            except OSError:
                pass

    def shortcut(self, name: str, target: Path) -> bool:
        if not self.env.windows:
            return False
        ps = ("$d=[Environment]::GetFolderPath('Desktop');"
              f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '{name}.lnk'));"
              f"$s.TargetPath='{target}';$s.WorkingDirectory='{target.parent}';$s.Save()")
        code, _ = self.run(["powershell", "-NoProfile", "-Command", ps])
        return code == 0


# ---------- 画面とのやりとり ----------

class UI:
    def __init__(self, answers: list[str] | None = None):
        self.answers = answers  # テストのときの答え(上から順に使う)
        self.out: list[str] = []

    def say(self, text: str = "") -> None:
        self.out.append(text)
        print(text, flush=True)

    def _input(self, prompt: str) -> str:
        if self.answers is not None:
            a = self.answers.pop(0) if self.answers else ""
            self.out.append(prompt + a)
            return a
        try:
            return input(prompt)
        except EOFError:
            # 答えが来ない(画面がない・流し込みが尽きた)まま既定値で進むと、同じ質問を繰り返し続けるので止める
            raise Stop("答えを読めませんでした(入力が終わっています)。bat をダブルクリックして画面で答えてください。")

    def ask(self, q: str, default: str = "") -> str:
        hint = f" [{default}]" if default else ""
        a = self._input(f"{q}{hint}: ").strip().strip('"')
        return a or default

    def yes(self, q: str, default: bool = True) -> bool:
        a = self._input(f"{q} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
        if not a:
            return default
        return a in ("y", "yes", "はい", "1")

    def choose(self, q: str, options: list[str], default: int = 0) -> int:
        self.say(q)
        for i, o in enumerate(options, 1):
            self.say(f"  {i}. {o}")
        while True:
            a = self._input(f"番号 [{default + 1}]: ").strip()
            if not a:
                return default
            if a.isdigit() and 1 <= int(a) <= len(options):
                return int(a) - 1
            self.say("番号で選んでください")
            if self.answers is not None and not self.answers:
                return default

    def pause(self, q: str = "Enter で進みます。やめるときはこの画面を閉じてください") -> None:
        self._input(q)


class Stop(Exception):
    """続けられないので止める(理由を画面に出す)。"""


# ---------- 版 ----------

def vkey(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except ValueError:
        return ()


def is_version(v: str) -> bool:
    return bool(re.fullmatch(r"\d+\.\d+\.\d+", v.strip().lstrip("v")))


def bump(v: str) -> str:
    k = list(vkey(v)) or [0, 1, 0]
    while len(k) < 3:
        k.append(0)
    k[2] += 1
    return ".".join(map(str, k[:3]))


def read_version(vault: Path) -> str:
    try:
        return (vault / VERSION_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def versions_in(dist_root: Path) -> list[str]:
    if not dist_root.is_dir():
        return []
    vs = [p.name for p in dist_root.iterdir() if p.is_dir() and is_version(p.name) and (p / "manifest.toml").is_file()]
    return sorted(vs, key=vkey)


# ---------- 控え(Yu 2026-10-27: 前回の控えを残すか捨てるか、押すたびに選ぶ) ----------

class Backups:
    STATUS = "状態.txt"

    def __init__(self, root: Path, dry: bool):
        self.root = root
        self.dry = dry
        self.dir: Path | None = None

    def previous(self) -> list[Path]:
        if not self.root.is_dir():
            return []
        return sorted((p for p in self.root.iterdir() if p.is_dir()), key=lambda p: p.name)

    @staticmethod
    def size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())

    def status_of(self, p: Path) -> str:
        try:
            return (p / self.STATUS).read_text(encoding="utf-8").strip()
        except OSError:
            return "途中"

    def review(self, ui: UI) -> None:
        old = self.previous()
        if not old:
            return
        total = sum(self.size(p) for p in old)
        newest = old[-1]
        st = self.status_of(newest)
        when = newest.name.replace("_", " ")
        ui.say(f"前回までの控えが {len(old)} 個あります(合計 {total / 1e6:.1f} MB)。いちばん新しいもの: {when}・{st}")
        keep_default = st != "終わった"
        i = ui.choose("控えをどうしますか。", ["残す", "捨てる"], 0 if keep_default else 1)
        if i == 1:
            if self.dry:
                ui.say("試し: 控えは捨てずに残します")
                return
            for p in old:
                shutil.rmtree(p, ignore_errors=True)
            ui.say("前回までの控えを捨てました")
        else:
            ui.say(f"控えを残します: {self.root}")

    def start(self) -> None:
        if self.dry:
            return
        stamp = datetime.now(JST).strftime("%Y-%m-%d_%H%M%S")
        self.dir = self.root / stamp
        n = 1
        while self.dir.exists():
            n += 1
            self.dir = self.root / f"{stamp}-{n}"
        self.dir.mkdir(parents=True)
        (self.dir / self.STATUS).write_text("途中\n", encoding="utf-8")

    def save(self, label: str, base: Path, rels: list[str]) -> None:
        """base の rels(あるものだけ)を <控え>/<label>.zip に足す。"""
        if self.dry or not self.dir:
            return
        files = [r for r in rels if (base / r).is_file()]
        if not files:
            return
        with zipfile.ZipFile(self.dir / f"{label}.zip", "a", zipfile.ZIP_DEFLATED) as z:
            have = set(z.namelist())
            for r in files:
                if r not in have:
                    z.write(base / r, r)

    def finish(self) -> None:
        if self.dir:
            (self.dir / self.STATUS).write_text("終わった\n", encoding="utf-8")
            if len([f for f in self.dir.iterdir() if f.name != self.STATUS]) == 0:
                shutil.rmtree(self.dir, ignore_errors=True)  # 何も上書きしなかった回の空の控えは残さない


# ---------- 配布物を vault に当てる(要件書 F-46) ----------

def load_manifest(dist: Path) -> dict:
    return tomllib.loads((dist / "manifest.toml").read_text(encoding="utf-8"))


def vault_rules(manifest: dict, kind: str) -> dict:
    for v in manifest.get("vault", []):
        if v["name"] == kind:
            return v
    raise Stop(f"manifest.toml に {kind} がありません")


def kind_of(rel: str, rules: dict) -> str | None:
    for k in ("system", "seed"):
        if any(fnmatch.fnmatchcase(rel, p) for p in rules.get(k, [])):
            return k
    return None


def same(a: Path, b: Path) -> bool:
    try:
        return a.stat().st_size == b.stat().st_size and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def read_list(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [x for x in data if isinstance(x, str)] if isinstance(data, list) else []


def merged(*lists: list[str]) -> list[str]:
    out: list[str] = []
    for lst in lists:
        for x in lst:
            if x not in out:
                out.append(x)
    return out


PLUGIN_LIST = ".obsidian/community-plugins.json"
CONFIG = ".obsidian"


def merge_names(dist: Path) -> tuple[str, ...]:
    return getattr(dist_plugins(dist), "MERGED", ())


@functools.lru_cache(maxsize=None)
def dist_plugins(dist: Path):
    """配布物の plugins.py(キーやコアプラグインの合わせ方)を読む。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dist_plugins", dist / "plugins.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@dataclass
class VaultPlan:
    kind: str
    target: Path
    src: Path
    version: str
    old_version: str
    put: list[str] = field(default_factory=list)       # 新しく置く
    replace: list[str] = field(default_factory=list)   # 上書きする
    plugin_list: list[str] | None = None               # 合わせた community-plugins.json
    merged: list[str] = field(default_factory=list)    # 各自の分と合わせる設定(キー・右クリックメニュー・QuickAdd)
    notes: list[str] = field(default_factory=list)     # 合わせるときに知らせること(キーがぶつかった など)
    migrations: list[tuple[str, Path]] = field(default_factory=list)

    @property
    def new(self) -> bool:
        return not (self.target / SYSTEM).is_dir()

    def summary(self) -> str:
        parts = []
        if self.migrations:
            parts.append(f"移し替え {len(self.migrations)} 本")
        if self.put:
            parts.append(f"置く {len(self.put)}")
        if self.replace:
            parts.append(f"上書き {len(self.replace)}")
        if self.plugin_list is not None:
            parts.append("プラグインの一覧を合わせる")
        if self.merged:
            parts.append("キーなどを自分の分と合わせる")
        head = "作る" if self.new else (f"{self.old_version or '版なし'} → {self.version}" if self.old_version != self.version else f"{self.version} のまま")
        return f"{head}({'、'.join(parts) or '変わるファイルなし'})"

    @property
    def changes(self) -> bool:
        return bool(self.put or self.replace or self.migrations or self.plugin_list is not None or bool(self.merged)
                    or self.old_version != self.version)


def plan_vault(dist: Path, kind: str, target: Path) -> VaultPlan:
    """dist(<版>/)の kind の配布物を target に当てると何が起きるかを数える。"""
    manifest = load_manifest(dist)
    rules = vault_rules(manifest, kind)
    src = dist / kind
    version = read_version(src)
    old = read_version(target)
    vp = VaultPlan(kind, target, src, version, old)
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src).as_posix()
        if rel == VERSION_FILE.as_posix():
            continue
        k = kind_of(rel, rules)
        dst = target / rel
        if kind == "個人" and rel == PLUGIN_LIST and dst.is_file():
            have = read_list(dst)
            want = merged(have, read_list(f))
            if want != have:
                vp.plugin_list = want
            continue
        if kind == "個人" and rel.startswith(CONFIG + "/") and rel[len(CONFIG) + 1:] in merge_names(dist) and dst.is_file():
            pl = dist_plugins(dist)
            sent = pl.read_json(target / CONFIG / pl.SENT)
            have = pl.read_json(dst)
            want, notes = pl.merge_one(rel[len(CONFIG) + 1:], have, pl.read_json(f), sent if isinstance(sent, dict) else {})
            if want != have:
                vp.merged.append(rel)
                vp.notes += notes
            continue
        if not dst.exists():
            vp.put.append(rel)
        elif k == "system" and not same(f, dst):
            vp.replace.append(rel)
    # 版.txt のない vault(bat より前に作ったもの)にも当てる。移し替えは何度走らせても同じ結果になるので害がない
    if not vp.new and (not old or vkey(old) < vkey(version)):
        for m in manifest.get("migrate", []):
            if kind in m.get("vaults", [kind]) and (not old or vkey(old) < vkey(m["version"])) \
                    and vkey(m["version"]) <= vkey(version):
                vp.migrations.append((m["version"], dist / "移し替え" / Path(m["script"]).name))
        vp.migrations.sort(key=lambda x: vkey(x[0]))
    return vp


def apply_vault(vp: VaultPlan, backups: Backups, label: str, ext: Ext | None = None) -> list[str]:
    done: list[str] = []
    for ver, script in vp.migrations:
        if not script.is_file():
            raise Stop(f"移し替え {script.name}(版 {ver})が配布物にありません")
        bdir = backups.dir or backups.root
        bdir.mkdir(parents=True, exist_ok=True)
        code, out = (ext or Ext(Env.from_os())).run([sys.executable, str(script), str(vp.target), "--run", "--backup", str(bdir)])
        if code != 0:
            raise Stop(f"版 {ver} の移し替えが失敗しました。版.txt は進めていません:\n{out[-800:]}")
        done.append(f"版 {ver} の移し替えを当てた")
    backups.save(label, vp.target, vp.replace + ([PLUGIN_LIST] if vp.plugin_list is not None else []) + vp.merged)
    for rel in vp.put + vp.replace:
        dst = vp.target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vp.src / rel, dst)
    # 空のフォルダ(01_目的 など)も作る
    for d in vp.src.rglob("*"):
        if d.is_dir():
            (vp.target / d.relative_to(vp.src)).mkdir(parents=True, exist_ok=True)
    if vp.plugin_list is not None:
        (vp.target / PLUGIN_LIST).write_text(json.dumps(vp.plugin_list, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if vp.kind == "個人" and (vp.src / CONFIG).is_dir() and (vp.src.parent / "plugins.py").is_file():
        # キー・右クリックメニュー・QuickAdd は、各自で足した分を残して合わせる(配ったものの覚えもここで書く)
        _, notes = dist_plugins(vp.src.parent).merge_settings(vp.src / CONFIG, vp.target / CONFIG)
        done += notes
    (vp.target / VERSION_FILE).parent.mkdir(parents=True, exist_ok=True)
    (vp.target / VERSION_FILE).write_text(vp.version + "\n", encoding="utf-8")
    if vp.put or vp.replace:
        done.append(f"置いた {len(vp.put)}・上書きした {len(vp.replace)}")
    return done


# ---------- メンバー.csv ----------

def read_members(shared: Path) -> list[tuple[str, str]]:
    return read_members_csv(shared / MEMBER_CSV)


def read_members_csv(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return [(r[0].strip(), r[1].strip()) for r in rows[1:] if len(r) >= 2 and r[0].strip() and r[1].strip()]


def check_new_member(members: list[tuple[str, str]], name: str, number: str) -> str:
    """足してよければ ""、だめなら理由。"""
    if not name or "," in name:
        return "名前を打ってください(カンマは使えません)"
    if not re.fullmatch(r"\d{6}", number):
        return "番号は6桁の数字にしてください(例 229999)"
    for n, num in members:
        if n == name:
            return f"{name} はもう登録されています"
        if num == number:
            return f"番号 {number} は {n} が使っています"
    return ""


def add_member_line(shared: Path, name: str, number: str, today: str) -> None:
    path = shared / MEMBER_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8-sig") if path.is_file() else "名前,番号,使い始めた日\n"
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + f"{name},{number},{today}\n", encoding="utf-8")


# ---------- config.yaml(行だけ書き換える。コメントは残す) ----------

def write_new_config(path: Path, values: dict, secrets: list[Path]) -> None:
    lines = ["# 知見同期の個人設定(準備の bat が作りました。直してもかまいません)"]
    for k in ("member", "personal", "shared", "shared_data", "report"):
        if values.get(k):
            lines.append(f"{k}: {values[k]}")
    lines.append("secret:" if secrets else "secret: []")
    lines += [f"  - {p}" for p in secrets]
    lines += ["dry_run: true                    # 最初は試し運転。確かめたら false にする", "idle_seconds: 10"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_key(path: Path, key: str, value: str) -> bool:
    """key: の行を value にする。なければ足す。変えたら True。"""
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    pat = re.compile(rf"^{re.escape(key)}:\s*(?P<val>[^#]*?)\s*(?P<tail>#.*)?$")
    for i, l in enumerate(lines):
        m = pat.match(l)
        if m:
            if m.group("val").strip().strip("'\"") == value:
                return False
            lines[i] = f"{key}: {value}" + (f"   {m.group('tail')}" if m.group("tail") else "")
            break
    else:
        lines.append(f"{key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def add_secret(path: Path, folder: Path) -> bool:
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if re.match(r"^secret:", l):
            has_items = i + 1 < len(lines) and re.match(r"^\s+-\s", lines[i + 1])
            if re.match(r"^secret:\s*(\[\s*\])?\s*(#.*)?$", l) and not has_items:
                lines[i] = "secret:"
                lines.insert(i + 1, f"  - {folder}")
            else:
                j = i + 1
                while j < len(lines) and re.match(r"^\s+-\s", lines[j]):
                    if os.path.normcase(lines[j].split("-", 1)[1].split("#")[0].strip().strip("'\"")) == os.path.normcase(str(folder)):
                        return False
                    j += 1
                lines.insert(j, f"  - {folder}")
            break
    else:
        lines += ["secret:", f"  - {folder}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def read_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    import yaml
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except yaml.YAMLError as e:
        raise Stop(f"設定ファイルが YAML として読めません: {path}: {e}")


# ---------- 個人設定.md ----------

def my_settings(personal: Path) -> tuple[str, str]:
    try:
        text = (personal / MY_SETTINGS).read_text(encoding="utf-8")
    except OSError:
        return "", ""
    def f(key):
        m = re.search(rf"^{key}:[ \t]*[\"']?([^\"'#\r\n]*?)[\"']?[ \t]*(?:#.*)?$", text, re.M)
        return m.group(1).strip() if m else ""
    return f("name"), f("number")


def write_my_settings(personal: Path, name: str, number: str) -> None:
    path = personal / MY_SETTINGS
    text = path.read_text(encoding="utf-8")
    text = re.sub(r'^name:[ \t]*""', f'name: "{name}"', text, count=1, flags=re.M)
    if number:
        text = re.sub(r'^number:[ \t]*""', f'number: "{number}"', text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


# ---------- id とテンプレート ----------

def notesync():
    """同期プログラムの部品(id の作り方・場所の探し方)を使う。"""
    if str(SYNC_SRC) not in sys.path:
        sys.path.insert(0, str(SYNC_SRC))
    import notesync.ids as ids  # noqa: F401
    import notesync.relocate as relocate  # noqa: F401
    import notesync
    return notesync


def used_ids(root: Path) -> set[str]:
    ids = notesync().ids
    out = set()
    for p in root.rglob("*.md"):
        i, _ = ids.split_filename(p.stem)
        if i:
            out.add(i)
    return out


def make_note_id(shared: Path, number: str, when: datetime | None = None) -> str:
    ids = notesync().ids
    return ids.make_id(when or datetime.now(JST), ids.code_of(number), used_ids(shared))


def yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def render(template: str, note_id: str, alias: str, today: datetime, lists: dict[str, list[str]]) -> str:
    """Templater のテンプレートを、Obsidian を通さずに埋める(台帳と機密の窓口だけ)。"""
    out = []
    for line in template.splitlines():
        if line.startswith("id: <%"):
            line = f"id: {note_id}"
        elif line.startswith("aliases: [<%"):
            line = f"aliases: [{json.dumps(alias, ensure_ascii=False)}]"
        else:
            for key, items in lists.items():
                m = re.match(rf"^{key}:\s*\[\]\s*(#.*)?$", line)
                if m:
                    line = f"{key}: {yaml_list(items)}" + (f"   {m.group(1)}" if m.group(1) else "")
        line = re.sub(r'<%\s*tp\.date\.now\("YYYY-MM-DD",\s*(-?\d+)\)\s*%>',
                      lambda m: (today + timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d"), line)
        out.append(line)
    text = "\n".join(out) + "\n"
    if "<%" in text:
        raise Stop("テンプレートに埋められない書き方があります。Obsidian の Ctrl+N で作ってください")
    return text


def find_alias(folder: Path, alias: str) -> Path | None:
    if not folder.is_dir():
        return None
    ids = notesync().ids
    for p in folder.rglob("*.md"):
        if ids.split_filename(p.stem)[1] == alias:
            return p
        try:
            head = p.read_text(encoding="utf-8")[:600]
        except OSError:
            continue
        if re.search(rf'^aliases:.*["\[,\s]{re.escape(alias)}["\],]', head, re.M):
            return p
    return None


# ---------- Obsidian の vault の一覧 ----------

def read_config_json(conf: Path) -> dict:
    try:
        data = json.loads(conf.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def register_vaults(conf: Path, paths: list[Path], moved: dict[str, Path] | None = None) -> list[str]:
    """%APPDATA%\\obsidian\\obsidian.json に vault を足す(Obsidian を閉じているときだけ)。"""
    data = read_config_json(conf)
    vaults = data.setdefault("vaults", {})
    key = lambda p: os.path.normcase(os.path.normpath(str(p)))
    done = []
    for old, new in (moved or {}).items():
        for v in vaults.values():
            if key(v.get("path", "")) == key(old):
                v["path"] = str(new)
                done.append("Obsidian の一覧の場所を1つ直した")
    have = {key(v.get("path", "")) for v in vaults.values()}
    for p in paths:
        if key(p) not in have:
            vaults[uuid.uuid4().hex[:16]] = {"path": str(p), "ts": int(time.time() * 1000)}
            have.add(key(p))
            done.append("Obsidian の一覧に vault を1つ足した")
    if done:
        conf.parent.mkdir(parents=True, exist_ok=True)
        conf.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return done


# ---------- 準備の流れ ----------

@dataclass
class Step:
    text: str
    fn: object = None   # 引数なしの関数。None なら表示だけ


class Setup:
    def __init__(self, role: str, dry: bool, ui: UI | None = None, env: Env | None = None, ext: Ext | None = None,
                 shared_hint: Path | None = None, today: datetime | None = None):
        self.role = role
        self.dry = dry
        self.ui = ui or UI()
        self.env = env or Env.from_os()
        self.ext = ext or Ext(self.env)
        self.shared_hint = shared_hint
        self.today = today or datetime.now(JST)
        self.steps: list[Step] = []
        self.hand: list[str] = []          # 最後に出す、手でやること
        self.backups = Backups(self.env.app / "準備の控え", dry)
        self.memo = self._load_memo()
        self.conf: dict = {}
        self.moved: dict[str, Path] = {}
        self.dist: Path | None = None      # 当てる版の配布物(<版>/)
        self.need_obsidian_closed = False
        self.personal: Path | None = None
        self.shared: Path | None = None
        self.secrets: list[Path] = []
        self.new_config_dirs: list[str] = []
        self.first_config = False
        self.clip_text = ""
        self.tag_pending = False

    # --- 覚えておくこと ---
    def _load_memo(self) -> dict:
        try:
            return json.loads(self.env.memo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_memo(self) -> None:
        self.env.memo.parent.mkdir(parents=True, exist_ok=True)
        self.env.memo.write_text(json.dumps(self.memo, ensure_ascii=False, indent=1), encoding="utf-8")

    def say_note(self, label: str, line: str) -> None:
        """したことを記録に書く。キーがぶつかったなど本人に知らせることは、画面にも出し、最後の「手でやること」にも入れる。"""
        self.log(f"{label}: {line}")
        if line.startswith("キー"):
            self.ui.say(f"    {line}")
            self.hand_once("key:" + line, f"{label}: {line}")

    def log(self, text: str) -> None:
        if self.dry:
            return
        self.env.log.parent.mkdir(parents=True, exist_ok=True)
        with self.env.log.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(JST):%Y-%m-%d %H:%M} [{self.role}] {text}\n")

    def add(self, text: str, fn=None) -> None:
        self.steps.append(Step(text, fn))

    # --- 入口 ---
    def main(self) -> int:
        title = {"管理者": "システム管理者", "PL": "プロジェクトリーダー", "メンバー": "チームメンバー"}[self.role]
        self.ui.say(f"開発ノートの準備({title}){' 試し: 何も変えません' if self.dry else ''}")
        self.ui.say("")
        try:
            self.backups.review(self.ui)
            self.ensure_yaml()
            self.follow_moves()
            if self.role == "管理者":
                self.ask_admin()
            else:
                self.ask_common()
                if self.role == "PL":
                    self.ask_pl()
            self.after_steps()
            return self.run_steps()
        except Stop as e:
            self.ui.say("")
            self.ui.say(f"止めました: {e}")
            self.log(f"止めた: {str(e).splitlines()[0]}")
            return 1

    def ensure_yaml(self) -> None:
        try:
            import yaml  # noqa: F401
            return
        except ImportError:
            pass
        self.ui.say("yaml を読む部品(pyyaml)を入れます。")
        code, out = self.ext.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "pyyaml"])
        if code != 0:
            raise Stop("pyyaml を入れられませんでした。ネットにつながっているか確かめてください:\n" + out[-400:])
        import importlib
        import site
        site.addsitedir(site.getusersitepackages())
        importlib.invalidate_caches()

    def follow_moves(self) -> None:
        """vault の名前や場所が変わっていたら、同期プログラムと同じ探し方(F-50)で見つけて config.yaml を直す。"""
        self.conf = read_config(self.env.config)
        if not self.conf.get("member") or not self.conf.get("personal"):
            return
        ns = notesync()
        from notesync.config import Config
        c = Config(member=str(self.conf["member"]), personal=Path(self.conf["personal"]),
                   shared=Path(self.conf["shared"]) if self.conf.get("shared") else None,
                   secret=[Path(p) for p in (self.conf.get("secret") or [])], config_path=self.env.config)
        before = {"個人": c.personal, "共有": c.shared, **{f"機密{i}": p for i, p in enumerate(c.secret)}}
        records, warnings = ns.relocate.follow(c, dry=self.dry)
        after = {"個人": c.personal, "共有": c.shared, **{f"機密{i}": p for i, p in enumerate(c.secret)}}
        for k, old in before.items():
            if old and after[k] and old != after[k]:
                self.moved[str(old)] = after[k]
        for r in records:
            self.ui.say(r if not r.startswith("機密") else "機密フォルダの場所が変わっていたので、設定を直しました")
        for w in warnings:
            self.ui.say("注意: " + w)
        if records and not self.dry:
            self.conf = read_config(self.env.config)
        elif records:
            self.conf.update({"personal": str(c.personal), "shared": str(c.shared) if c.shared else None,
                              "secret": [str(p) for p in c.secret]})

    # --- Box の場所 ---
    def box_root(self) -> Path:
        if self.memo.get("box") and Path(self.memo["box"]).is_dir():
            return Path(self.memo["box"])
        guess = self.env.home / "Box"
        if not guess.is_dir() and self.shared_hint:
            guess = self.shared_hint.parent
        while True:
            a = Path(self.ui.ask("Box Drive のフォルダ(エクスプローラーのアドレス欄から写せます)", str(guess)))
            if a.is_dir():
                self.memo["box"] = str(a)
                return a
            self.ui.say(f"フォルダが見つかりません: {a}")

    def pc_code(self) -> str:
        if self.memo.get("pc"):
            return self.memo["pc"]
        guess = re.sub(r"[^0-9a-z]", "", self.env.pc_name.lower()) or "pc"
        while True:
            a = self.ui.ask("この PC の記号(英小文字と数字。PC ごとに違うもの。Enter で PC の名前)", guess).lower()
            if re.fullmatch(r"[0-9a-z]+", a):
                self.memo["pc"] = a
                return a
            self.ui.say("英小文字と数字だけにしてください")

    # --- どの版を当てるか ---
    def pick_dist(self, shared: Path) -> Path:
        latest = ""
        try:
            latest = (shared / PREP_DIR / LATEST).read_text(encoding="utf-8").strip()
        except OSError:
            pass
        vs = versions_in(shared / DIST_DIR)
        if not latest and vs:
            latest = vs[-1]
        if not latest:
            raise Stop(f"共有 vault に配布物がありません({shared / DIST_DIR})。システム管理者に版を出してもらってください")
        d = shared / DIST_DIR / latest
        if not (d / "manifest.toml").is_file():
            raise Stop(f"配布物 {latest} が見つかりません: {d}")
        return d

    # --- 自分を選ぶ ---
    def choose_me(self, shared: Path, members: list[tuple[str, str]], can_add: bool) -> tuple[str, str]:
        known = str(self.conf.get("member") or "")
        for n, num in members:
            if n == known:
                return n, num
        options = [f"{n}({num})" for n, num in members]
        if can_add:
            options.append("自分を新しく登録する")
        if not options:
            raise Stop("メンバー.csv に誰もいません。システム管理者に登録を頼んでください")
        i = self.ui.choose("あなたはどれですか(メンバー.csv)。", options, 0)
        if i < len(members):
            return members[i]
        name, number = self.ask_new_member(members)
        self.add(f"メンバー.csv に {name}({number})を足す", lambda: add_member_line(shared, name, number, self.today.strftime("%Y-%m-%d")))
        return name, number

    def ask_new_member(self, members: list[tuple[str, str]]) -> tuple[str, str]:
        while True:
            name = self.ui.ask("名前(同期レポートや台帳に出る名前。例 佐藤)")
            number = self.ui.ask("6桁の番号(社員番号など。ほかの人と重ならないもの)")
            why = check_new_member(members, name, number)
            if not why:
                return name, number
            self.ui.say(why)

    # --- 自分の環境(管理者・PL・メンバー共通) ---
    def ask_common(self, shared: Path | None = None, can_add_me: bool = False) -> None:
        shared = shared or (Path(self.conf["shared"]) if self.conf.get("shared") else None) or self.shared_hint
        if not shared or (not (shared / SYSTEM).is_dir() and self.role != "管理者"):
            raise Stop("共有 vault が見つかりません。共有 vault の _仕組み/tools/準備/ の bat から押してください")
        if self.conf.get("shared") and self.shared_hint and os.path.normcase(str(self.shared_hint)) != os.path.normcase(str(shared)) \
                and (self.shared_hint / SYSTEM).is_dir():
            raise Stop(f"この PC の設定の共有 vault({shared})と、押した bat の共有 vault({self.shared_hint})が違います。"
                       f"設定ファイル {self.env.config} の shared を確かめてください")
        self.shared = shared
        if self.dist is None:
            self.dist = self.pick_dist(shared)
        # 共有 vault を作る前(管理者の初回)は、配布物の メンバー.csv を見る
        members = read_members(shared) if (shared / SYSTEM).is_dir() else read_members(self.dist / "共有")
        self.me, self.number = self.choose_me(shared, members, can_add_me)
        self.pc = self.pc_code()

        # 個人 vault
        if self.conf.get("personal"):
            personal = Path(self.conf["personal"])
        else:
            box = self.box_root()
            personal = Path(self.ui.ask("個人 vault の場所(なければ作ります)", str(box / "個人" / f"開発ノート_{self.me}")))
        self.personal = personal
        if personal.exists() and not (personal / SYSTEM).is_dir() and any(personal.iterdir()):
            raise Stop(f"{personal} は vault ではないファイルが入っています。空のフォルダか個人 vault を指してください")
        for other in [shared] + [Path(p) for p in (self.conf.get("secret") or [])]:
            if personal.resolve().is_relative_to(other.resolve()) or other.resolve().is_relative_to(personal.resolve()):
                raise Stop("個人 vault と共有・機密のフォルダは入れ子にしないでください")
        self.plan_apply("個人", personal, "個人 vault")
        name, number = my_settings(personal)
        legacy = not re.fullmatch(r"\d{6}", self.number)  # v0.38 までの3文字の記号(個人設定.md には書かない)
        if (name and name != self.me) or (number and number != self.number):
            raise Stop(f"個人 vault の個人設定.md が {name or '空'}・{number or '空'} です。メンバー.csv の {self.me}・{self.number} と"
                       f"そろえてください({personal / MY_SETTINGS})")
        if not name or (not number and not legacy):
            self.add(f"個人設定.md に name {self.me}" + ("" if legacy else f"・number {self.number}") + " を書く",
                     lambda: write_my_settings(personal, self.me, "" if legacy else self.number))

        # 週報(報告フォルダ)
        report = self.conf.get("report")
        data = self.conf.get("shared_data")
        if not self.conf.get("member"):
            box = self.box_root()
            if not data:
                d = Path(self.ui.ask("開発データ(重い添付)のフォルダ", str(shared.parent / "開発データ")))
                data = str(d)
            if not report and self.ui.yes("この PC で管理者向けの週報も作りますか(報告フォルダに書ける人)", self.role != "メンバー"):
                report = self.ui.ask("報告フォルダ", str(shared.parent / "開発ノート_報告"))
        self.data, self.report = data, report

        # 機密フォルダ(設定にあるもの)
        self.secrets = [Path(p) for p in (self.conf.get("secret") or []) if Path(p).is_dir()]
        for i, s in enumerate(self.secrets, 1):
            self.plan_apply("機密", s, f"機密フォルダ {i}")

        self.plan_config_dirs()
        self.plan_program()

    def plan_apply(self, kind: str, target: Path, label: str) -> VaultPlan:
        vp = plan_vault(self.dist, kind, target)
        if vp.changes:
            def go(vp=vp, label=label):
                for line in apply_vault(vp, self.backups, label.replace(" ", ""), self.ext):
                    self.say_note(label, line)
            where = "" if kind == "機密" else f"({target})"
            self.add(f"{label}{where} を作る" if vp.new else f"{label} を今の版に: {vp.summary()}", go)
        return vp

    def config_name(self) -> str:
        return f".obsidian-{self.number}_{self.pc}"

    def plan_config_dirs(self) -> None:
        """共有・機密は .obsidian-<番号>_<PC の記号>、個人は .obsidian に、配る設定とプラグインを入れる。"""
        name = self.config_name()
        targets = [("共有 vault", self.shared)] + [(f"機密フォルダ {i}", s) for i, s in enumerate(self.secrets, 1)]
        for label, v in targets:
            d = v / name
            if not d.is_dir():
                self.new_config_dirs.append(label)
            self.plan_plugins(label, v, name)
        self.plan_plugins("個人 vault", self.personal, ".obsidian")

    def plan_plugins(self, label: str, vault: Path, config: str) -> None:
        source = self.dist / "プラグイン"
        def go():
            d = vault / config
            if not d.is_dir():
                d.mkdir(parents=True)
                for old in self.legacy_dirs(vault):
                    shutil.copytree(old, d, dirs_exist_ok=True)  # 画面の配置などを引き継ぐ
                    self.log(f"{label}: {old.name} の中身を {config} に写した")
                    break
            settings = vault / SETTINGS
            if settings.is_dir() and settings.resolve() != d.resolve():
                rels = [f.relative_to(settings).as_posix() for f in settings.rglob("*") if f.is_file()]
                self.backups.save(label.replace(" ", "") + "_設定", d, rels)
            sys.path.insert(0, str(self.dist))
            import importlib
            plugins = importlib.import_module("plugins")
            if (source / "プラグインの出典.md").is_file():
                for line in plugins.install(vault, config, source):
                    self.say_note(label, line)
            elif settings.is_dir() and settings.resolve() != d.resolve():
                for f in settings.rglob("*"):
                    if f.is_file() and f.name != "community-plugins.json" and f.relative_to(settings).as_posix() not in plugins.MERGED:
                        (d / f.relative_to(settings)).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, d / f.relative_to(settings))
                for line in plugins.merge_settings(settings, d)[1]:  # キーなどは各自で足した分を残す
                    self.say_note(label, line)
                if not (d / "community-plugins.json").is_file() and (settings / "community-plugins.json").is_file():
                    shutil.copy2(settings / "community-plugins.json", d / "community-plugins.json")
            if plugins.set_core_plugins(d):  # 本体がない版でも、個人 vault でも合わせる
                self.log(f"{label}: コアプラグインを合わせた")
            (d / SEEN_VERSION).write_text(read_version(self.dist / "共有") + "\n", encoding="utf-8")
        if not self.config_needs_update(vault, config):
            return
        self.need_obsidian_closed = True
        kind = "設定とプラグインを入れる" if (source / "プラグインの出典.md").is_file() else "配る設定を入れる(この版にプラグインの本体はありません)"
        where = f"{config}" if label != "個人 vault" else ".obsidian"
        self.add(f"{label} の {where} に{kind}", go)

    def config_needs_update(self, vault: Path, config: str) -> bool:
        d = vault / config
        if not d.is_dir():
            return True
        try:
            seen = (d / SEEN_VERSION).read_text(encoding="utf-8").strip()
        except OSError:
            return True
        return seen != read_version(self.dist / "共有")

    def legacy_dirs(self, vault: Path) -> list[Path]:
        names = [f".obsidian-{self.number}", f".obsidian-{self.me}"]
        return [vault / n for n in names if (vault / n).is_dir()]

    def plan_program(self) -> None:
        dst = self.env.program
        have = ""
        try:
            have = (dst / "版.txt").read_text(encoding="utf-8").strip()
        except OSError:
            pass
        ver = read_version(self.dist / "共有")
        src = self.dist / "同期プログラム" if (self.dist / "同期プログラム").is_dir() else SYNC_SRC
        if have != ver or not (dst / "notesync").is_dir():
            def go():
                if dst.exists():
                    shutil.rmtree(dst / "notesync", ignore_errors=True)
                for part in ("notesync", "起動"):
                    if (src / part).is_dir():
                        shutil.copytree(src / part, dst / part, dirs_exist_ok=True,
                                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
                if (src / "config.example.yaml").is_file():
                    shutil.copy2(src / "config.example.yaml", dst / "config.example.yaml")
                (dst / "版.txt").write_text(ver + "\n", encoding="utf-8")
                if self.ext.shortcut("知見同期を続ける", dst / "起動" / "3_同期を続ける.bat"):
                    self.log("デスクトップに「知見同期を続ける」を置いた")
            self.add(f"同期プログラムを {have or 'なし'} → {ver} にする({dst})", go)
            if have:
                self.hand_once("watch_restart", "「知見同期を続ける」の画面が開いていたら、閉じてからデスクトップの「知見同期を続ける」で開き直す")

        conf = self.env.config
        values = {"member": self.me, "personal": str(self.personal), "shared": str(self.shared),
                  "shared_data": self.data, "report": self.report}
        if not conf.is_file():
            self.add("同期の設定 config.yaml を作る(試し運転のまま)",
                     lambda: write_new_config(conf, values, self.secrets))
            self.first_config = True
        else:
            self.first_config = False
            for k, v in values.items():
                if v and not self.conf.get(k):
                    self.add(f"config.yaml に {k} を足す", lambda k=k, v=v: set_key(conf, k, str(v)))
        self.wants_trial = True

    def trial(self) -> None:
        env = dict(os.environ, PYTHONPATH=str(self.env.program), PYTHONUTF8="1")
        code, out = self.ext.run([sys.executable, "-m", "notesync", "once", "--dry-run", "--config", str(self.env.config)],
                                 env=env)
        last = [l for l in out.strip().splitlines() if l.strip()][-1:] or ["(何も出ませんでした)"]
        self.ui.say("    " + last[0])
        if code != 0:
            self.hand.append("試し運転が止まりました。上の1行を見て直し、もう一度この bat を押す(直し方はマニュアル 05 の 7)")
        elif self.first_config:
            self.hand.append(f"同期レポート({self.personal / '_仕組み' / '同期レポート.md'})を見て、よければ config.yaml の dry_run を false にする")

    def hand_once(self, key: str, text: str) -> None:
        if text not in self.hand:
            self.hand.append(text)

    # --- PL ---
    def ask_pl(self) -> None:
        if self.ui.yes("新しいプロジェクトを作りますか", False):
            self.ask_project()
        if self.ui.yes("機密フォルダ(顧客の資料)を用意しますか", False):
            self.ask_secret()

    def ask_project(self) -> None:
        members = read_members(self.shared)
        while True:
            name = self.ui.ask("プロジェクトの名前(例 樹脂カバー量産)")
            if not name:
                return
            if re.search(r'[\\/:*?"<>|#^\[\]]', name):
                self.ui.say("名前に \\ / : * ? \" < > | # ^ [ ] は使えません")
                continue
            if name in ("共通", "00_inbox", "00_週報", "99_archive", SYSTEM) or (self.shared / name).exists():
                self.ui.say(f"共有 vault に {name} がもうあります。別の名前にしてください")
                continue
            break
        self.ui.say("メンバー(番号をカンマで。例 1,3。Enter で自分だけ):")
        for i, (n, num) in enumerate(members, 1):
            self.ui.say(f"  {i}. {n}")
        a = self.ui.ask("番号")
        chosen = [self.me]
        for x in re.split(r"[,、\s]+", a):
            if x.isdigit() and 1 <= int(x) <= len(members) and members[int(x) - 1][0] not in chosen:
                chosen.append(members[int(x) - 1][0])
        tmpl = self.shared / SYSTEM / "templates" / "プロジェクト.md"

        def go():
            root = self.shared / name
            for sub in ("01_目的", "01_設計案", "03_イシュー", "04_タスク", "05_ナレッジ"):
                (root / sub).mkdir(parents=True, exist_ok=True)
            nid = make_note_id(self.shared, self.number)
            text = render(tmpl.read_text(encoding="utf-8"), nid, name, self.today, {"members": chosen})
            (root / f"{nid}_{name}.md").write_text(text, encoding="utf-8")
            self.log(f"プロジェクト {name} を作った")
        self.add(f"共有 vault にプロジェクト「{name}」(メンバー {'、'.join(chosen)})のフォルダと台帳を作る", go)
        self.hand.append(f"共有 vault で「{name}」の台帳を開き、本文の節目の表を直して、目的から書き始める(マニュアル 03 の 2〜)")

    def ask_secret(self) -> None:
        while True:
            p = Path(self.ui.ask("機密フォルダの場所(Box に作ったフォルダ。なければ作ります)"))
            if not str(p) or str(p) == ".":
                return
            bad = [x for x in [self.shared, self.personal] if p.resolve().is_relative_to(x.resolve()) or x.resolve().is_relative_to(p.resolve())]
            if bad:
                self.ui.say("共有・個人の vault と入れ子にしないでください。別の場所にしてください")
                continue
            if p.is_dir() and any(p.iterdir()) and not (p / SYSTEM).is_dir():
                self.ui.say("そのフォルダにはもうファイルがあります。空のフォルダか、機密フォルダを指してください")
                continue
            break
        while True:
            alias = self.ui.ask("共有に出す呼び名(顧客名を使わない。例 案件A)")
            if not alias:
                return
            if find_alias(self.shared / WINDOW_DIR, alias):
                self.ui.say(f"窓口「{alias}」はもうあります。別の呼び名にしてください")
                continue
            break
        idx = len(self.secrets) + 1
        new = not (p / SYSTEM).is_dir()

        def make_folder():
            p.mkdir(parents=True, exist_ok=True)
        if new:
            self.add(f"機密フォルダ {idx} を作る", make_folder)
        self.secrets.append(p)
        vp_label = f"機密フォルダ {idx}"
        # 配布物を当てる(作るときは中身を全部置く)

        def apply_secret():
            vp = plan_vault(self.dist, "機密", p)
            for line in apply_vault(vp, self.backups, vp_label.replace(" ", ""), self.ext):
                self.log(f"{vp_label}: {line}")
            # メンバー.csv の写しは共有のいまのものに
            shutil.copy2(self.shared / MEMBER_CSV, p / SECRET_CSV)
            readme = p / "00_README.md"
            if readme.is_file():
                t = readme.read_text(encoding="utf-8")
                t = re.sub(r"^- 共有の窓口ノート:.*$", f"- 共有の窓口ノート: 共通/機密の窓口/ の「{alias}」", t, count=1, flags=re.M)
                readme.write_text(t, encoding="utf-8")
        self.add(f"{vp_label}に配布物を置き、README に窓口「{alias}」を書く", apply_secret)
        name = self.config_name()
        self.new_config_dirs.append(vp_label)
        self.plan_plugins(vp_label, p, name)
        tmpl = self.shared / SYSTEM / "templates" / "機密の窓口.md"

        def window():
            d = self.shared / WINDOW_DIR
            d.mkdir(parents=True, exist_ok=True)
            nid = make_note_id(self.shared, self.number)
            text = render(tmpl.read_text(encoding="utf-8"), nid, alias, self.today, {"readers": [self.me], "owner": [self.me]})
            (d / f"{nid}_{alias}.md").write_text(text, encoding="utf-8")
        self.add(f"共有 vault に機密の窓口「{alias}」(readers・owner は {self.me})を作る", window)
        conf = self.env.config
        self.add(f"config.yaml の secret に {vp_label}を足す",
                 lambda: add_secret(conf, p) if conf.is_file() else None)
        self.hand.append(f"Box の画面で{vp_label}の共同作業者を、案件の担当者だけにする(見てよい人を窓口「{alias}」の readers にも書く)")

    # --- 管理者 ---
    def ask_admin(self) -> None:
        if REPO is None:
            raise Stop("システム管理者の bat は、正本(rd-notebase)の tools\\ から押してください")
        self.ensure_git()
        code, _ = self.git("rev-parse", "--is-inside-work-tree")
        if code != 0:
            # GitHub から ZIP で持ってきたとき。Git で持ってきた正本に置きかえる
            if DEFAULT_REPO_DIR.exists():
                raise Stop(f"この正本は Git で持ってきたものではありません。{DEFAULT_REPO_DIR}\\tools\\システム管理者.bat を押してください")
            if self.dry:
                raise Stop(f"正本を Git で {DEFAULT_REPO_DIR} に持ってくる必要があります(試しなのでやめます)")
            self.ui.say(f"正本を Git で {DEFAULT_REPO_DIR} に持ってきます(Box の外)。")
            code, out = self.ext.run(["git", "clone", REPO_URL, str(DEFAULT_REPO_DIR)])
            if code != 0:
                raise Stop("正本を持ってこられませんでした:\n" + out[-600:])
            raise Stop(f"正本を {DEFAULT_REPO_DIR} に置きました。これからは {DEFAULT_REPO_DIR}\\tools\\システム管理者.bat を押してください")
        shared = Path(self.conf["shared"]) if self.conf.get("shared") else None
        first = not shared or not (shared / SYSTEM).is_dir()
        if first:
            self.ui.say("共有 vault がまだありません。チームの土台を作ります。")
            box = self.box_root()
            shared = Path(self.ui.ask("共有 vault の場所", str(box / "チーム" / "開発ノート_共有")))
            if (shared / SYSTEM).is_dir():
                first = False
            else:
                data = Path(self.ui.ask("開発データ(重い添付)のフォルダ", str(shared.parent / "開発データ")))
                report = Path(self.ui.ask("管理者向けの報告フォルダ", str(shared.parent / "開発ノート_報告")))
                self.conf.setdefault("shared_data", str(data))
                self.conf.setdefault("report", str(report))
                for d in (shared, data, report):
                    if not d.is_dir():
                        self.add(f"フォルダを作る: {d}", lambda d=d: d.mkdir(parents=True, exist_ok=True))
                self.hand += ["Box の画面で、共有 vault・開発データ・報告フォルダにメンバーを共同作業者(編集)として招待する",
                              "報告フォルダに、週報を読む上司を閲覧で招待する"]
        self.shared = shared
        if not first:
            self.show_status(shared)
            i = self.ui.choose("何をしますか。", ["新しい版を出して配る", "メンバーを足す", "自分の環境だけ整える"], 0)
            if i == 1:
                self.ask_add_member(shared)
                return
            if i == 2:
                self.ask_common(shared, can_add_me=True)
                return
        self.ask_release(shared, first)
        self.ask_common(shared, can_add_me=True)

    def ensure_git(self) -> None:
        if self.ext.has("git"):
            return
        self.ui.say("Git が見つからないので入れます(winget)。")
        if self.dry or not self.ext.winget("Git"):
            raise Stop("Git を入れられませんでした。https://git-scm.com/download/win から入れて、もう一度押してください")
        raise Stop("Git を入れました。いったんこの画面を閉じ、もう一度 bat を押してください(PATH を読み直すため)")

    def git(self, *args: str) -> tuple[int, str]:
        return self.ext.run(["git", *args], cwd=REPO)

    def show_status(self, shared: Path) -> None:
        self.ui.say(f"共有 vault: {shared}(版 {read_version(shared) or 'なし'})")
        code, out = self.git("log", "-1", "--format=%h %cd %s", "--date=short")
        if code == 0:
            self.ui.say(f"正本: {out.strip()}")
        members = read_members(shared)
        self.ui.say(f"メンバー: {len(members)} 人")
        seen = []
        for d in sorted(shared.glob(".obsidian-*")):
            try:
                seen.append(f"{d.name[len('.obsidian-'):]} は {(d / SEEN_VERSION).read_text(encoding='utf-8').strip()}")
            except OSError:
                pass
        if seen:
            self.ui.say("各 PC の版: " + "、".join(seen))
        self.ui.say("")

    def ask_add_member(self, shared: Path) -> None:
        members = read_members(shared)
        name, number = self.ask_new_member(members)
        today = self.today.strftime("%Y-%m-%d")

        def go():
            self.backups.save("共有vault", shared, [MEMBER_CSV.as_posix()])
            add_member_line(shared, name, number, today)
            for s in [Path(p) for p in (self.conf.get("secret") or [])]:
                if (s / SECRET_CSV).is_file():
                    self.backups.save("機密フォルダ", s, [SECRET_CSV.as_posix()])
                    shutil.copy2(shared / MEMBER_CSV, s / SECRET_CSV)
        self.add(f"メンバー.csv に {name}({number})を足す(権限のある機密フォルダの写しにも)", go)
        self.hand.append(f"Box の画面で {name} を共有 vault・開発データ・報告フォルダに招待し、共有 vault の "
                         f"{PREP_DIR.as_posix()}/チームメンバー.bat を押してもらう")

    def ask_release(self, shared: Path, first: bool) -> None:
        code, out = self.git("status", "--porcelain")
        dirty = code == 0 and bool(out.strip())
        if dirty:
            self.ui.say("正本に、まだ記録していない変更があります:")
            for l in out.strip().splitlines()[:10]:
                self.ui.say("  " + l)
            if not self.ui.yes("この変更も入れて版を出しますか", False):
                raise Stop("正本の変更を記録(コミット)するか戻してから、もう一度押してください")
        known = versions_in(shared / DIST_DIR) if not first else []
        code, tags = self.git("tag", "--list", "v*")
        tag_vs = [t.strip()[1:] for t in tags.splitlines() if is_version(t.strip())] if code == 0 else []
        prev = max(known + tag_vs + ([read_version(shared)] if read_version(shared) else []), key=vkey, default="")
        while True:
            ver = self.ui.ask("出す版の番号", bump(prev) if prev else "0.2.0")
            if not is_version(ver):
                self.ui.say("0.3.1 のような形にしてください")
                continue
            if prev and vkey(ver) <= vkey(prev):
                if not self.ui.yes(f"{ver} は今の {prev} より新しくありません。それでも出しますか", False):
                    continue
            break
        self.version = ver
        plugin_from = Path(self.conf["personal"]) / ".obsidian" if self.conf.get("personal") else None
        out_dir = REPO / "dist" / ver
        # 正本の中で組み立てる(Box はまだ変えない)。何を当てるかは、組み立てたものを見て決める
        self.ui.say("")
        self.ui.say(f"まず正本の中で版 {ver} を組み立てます。Box はまだ何も変えません。")
        if not dirty and not self.dry:
            self.ui.say("- 正本を GitHub の最新にする(git pull)")
            self.git_pull()
        self.ui.say("- 自動テスト(落ちたらここで止め、何も配らない)")
        self.run_tests()
        self.ui.say(f"- 組み立て(dist\\{ver})")
        self.build(ver)
        self.ui.say("- プラグインの本体をそろえる(ネットを使う)")
        self.pack(ver, plugin_from)
        prev_changes = shared / DIST_DIR / prev / CHANGES if prev else None
        write_changes(out_dir, (REPO / "docs" / "00_仕様書.md").read_text(encoding="utf-8"), prev_changes)
        self.dist = out_dir
        dst = shared / DIST_DIR / ver

        def place():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(out_dir, dst)
        self.add(f"共有 vault の {DIST_DIR.as_posix()}/{ver}/ に配布物を置く", place)
        vp = plan_vault(out_dir, "共有", shared)

        def apply_shared():
            for line in apply_vault(plan_vault(out_dir, "共有", shared), self.backups, "共有vault", self.ext):
                self.log(f"共有 vault: {line}")
            (shared / PREP_DIR).mkdir(parents=True, exist_ok=True)
            (shared / PREP_DIR / LATEST).write_text(ver + "\n", encoding="utf-8")
        self.add(f"共有 vault を{'作る' if vp.new else ' ' + vp.summary() + ' にする'}。準備の bat が {ver} を使うようにする", apply_shared)
        self.tag_pending = True

    def git_pull(self) -> None:
        code, out = self.git("pull", "--ff-only")
        if code != 0:
            raise Stop("正本を最新にできませんでした:\n" + out[-600:])

    def run_tests(self) -> None:
        code, _ = self.ext.run([sys.executable, "-c", "import pytest"])
        if code != 0:
            self.ext.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "pytest"])
        code, out = self.ext.run([sys.executable, "-m", "pytest", "-q", "sync/tests"], cwd=REPO)
        tail = [l for l in out.strip().splitlines() if l.strip()][-1:] or [""]
        self.ui.say("    " + tail[0])
        if code != 0:
            raise Stop("自動テストが落ちました。版は出していません:\n" + out[-1500:])

    def build(self, ver: str) -> None:
        code, out = self.ext.run([sys.executable, str(REPO / "tools" / "build.py"), ver], cwd=REPO)
        if code != 0:
            raise Stop("組み立てで止まりました:\n" + out[-1500:])

    def pack(self, ver: str, installed: Path | None) -> None:
        args = [sys.executable, str(REPO / "tools" / "plugins.py"), "pack", ver, "--download"]
        if installed and installed.is_dir():
            args += ["--from", str(installed)]
        code, out = self.ext.run(args, cwd=REPO)
        for l in out.strip().splitlines():
            if l.startswith("要対応"):
                self.ui.say("    " + l)
        if code != 0:
            self.hand.append(f"プラグインの「要対応」を片付ける(dist\\{ver}\\プラグイン\\。マニュアル 06 の 1)。直したら、もう一度この bat で同じ版を出し直す")

    def tag(self) -> None:
        if not self.ui.yes(f"GitHub にタグ v{self.version} を打ちますか(GitHub にサインインした PC だけ)", True):
            self.hand.append(f"あとで GitHub にタグ v{self.version} を打つ(git tag v{self.version} → git push origin v{self.version})")
            return
        code, out = self.git("tag", f"v{self.version}")
        if code == 0:
            code, out = self.git("push", "origin", f"v{self.version}")
        if code != 0:
            self.hand.append(f"タグ v{self.version} を GitHub に送れませんでした。サインインしてから git push origin v{self.version}")

    # --- 仕上げ ---
    def after_steps(self) -> None:
        self.after_env()
        if self.tag_pending:
            self.add(f"GitHub にタグ v{self.version} を打つ(打つ前に聞きます)", self.tag)

    def after_env(self) -> None:
        if self.personal is None:
            return  # メンバーを足すだけのとき
        if self.steps and getattr(self, "wants_trial", False):
            self.add("同期プログラムを試し運転する(ノートは変えない)", self.trial)
        targets = [p for p in [self.personal, self.shared] + self.secrets if p]
        have = read_config_json(self.env.obsidian_conf)
        known = {os.path.normcase(os.path.normpath(v.get("path", ""))) for v in have.get("vaults", {}).values()}
        if self.moved or any(os.path.normcase(os.path.normpath(str(p))) not in known for p in targets):
            self.need_obsidian_closed = True
            self.add("Obsidian の vault の一覧に足す(場所が変わったものは直す)",
                     lambda: [self.log(l) for l in register_vaults(self.env.obsidian_conf, targets, self.moved)])
        if self.ext.obsidian_exe() is None and self.env.windows:
            def inst():
                if not self.ext.winget("Obsidian"):
                    self.hand.append("Obsidian を https://obsidian.md/download から入れる")
            self.steps.insert(0, Step("Obsidian を入れる(winget)", inst))
        new_dirs = self.new_config_dirs
        if new_dirs:
            name = self.config_name()
            self.hand.append(f"Obsidian で {'・'.join(new_dirs)} を開き、設定 → ファイルとリンク →「設定フォルダを上書き」に "
                             f"{name} と打って Obsidian を開き直す(この名前はクリップボードに入れてあります)")
            self.clip_text = name
        if self.memo.get("first_done") is None:
            self.hand += ["Obsidian で vault を開いて「このフォルダの作者を信頼し、プラグインを有効にする」を押す(vault ごとに1回)",
                          "設定 → Templater →「Trigger Templater on new file creation」をオン(この PC で1回。設定ファイルでは配れない)"]

    def run_steps(self) -> int:
        ui = self.ui
        ui.say("")
        ui.say("これからすること:")
        if not self.steps:
            ui.say("  (なし。いまの版になっています)")
        for i, s in enumerate(self.steps, 1):
            ui.say(f"  {i}. {s.text}")
        ui.say("")
        if self.dry:
            ui.say("試しなので、ここでやめます。何も変えていません。")
            self._hand()
            return 0
        if not self.steps:
            self._hand()
            return 0
        ui.pause()
        if self.need_obsidian_closed:
            while self.ext.obsidian_running():
                ui.pause("Obsidian が開いています。閉じてから Enter を押してください")
        self.backups.start()
        self.log("始めた: " + " / ".join(s.text for s in self.steps))
        for i, s in enumerate(self.steps, 1):
            ui.say(f"[{i}/{len(self.steps)}] {s.text}")
            if s.fn:
                try:
                    s.fn()
                except Stop:
                    raise
                except Exception as e:  # 途中で止まっても、押し直せば続きから
                    raise Stop(f"「{s.text}」で止まりました({type(e).__name__}: {e})。直してからもう一度押してください。"
                               f"控え: {self.backups.dir}")
        self.backups.finish()
        self.memo["first_done"] = self.today.strftime("%Y-%m-%d")
        self._save_memo()
        self.log("終わった")
        if self.clip_text:
            self.ext.clip(self.clip_text)
        for p in [self.personal, self.shared]:
            if p and p.is_dir():
                self.ext.open_url("obsidian://open?path=" + quote(str(p)))
                break
        ui.say("")
        ui.say("終わりました。")
        self._hand()
        return 0

    def _hand(self) -> None:
        if not self.hand:
            return
        self.ui.say("")
        self.ui.say("手でやること:")
        for i, h in enumerate(self.hand, 1):
            self.ui.say(f"  {i}. {h}")


def write_changes(out_dir: Path, spec: str, prev_file: Path | None) -> Path:
    """仕様書の変更履歴から、前の版より新しいところを「この版で変わること.md」にする。"""
    m = re.search(r"^# .*? v(\d+\.\d+)", spec, re.M)
    spec_v = m.group(1) if m else ""
    since = ""
    if prev_file and prev_file.is_file():
        mm = re.search(r"仕様書 v(\d+\.\d+)", prev_file.read_text(encoding="utf-8"))
        since = mm.group(1) if mm else ""
    entries = re.findall(r"^- (\d{4}-\d{2}-\d{2}) v(\d+\.\d+): (.*)$", spec, re.M)
    pick = [e for e in entries if not since or vkey(e[1]) > vkey(since)]
    if not since:
        pick = pick[:5]
    lines = [f"# この版で変わること(仕様書 v{spec_v} まで)", ""]
    lines += [f"- v{v}({d}): {t}" for d, v, t in pick] or ["- 仕組みの中身の変更はありません"]
    path = out_dir / CHANGES
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    roles = {"管理者": "管理者", "admin": "管理者", "PL": "PL", "pl": "PL", "メンバー": "メンバー", "member": "メンバー"}
    if not argv or argv[0] not in roles:
        print(__doc__)
        return 2
    role = roles[argv[0]]
    dry = "試し" in argv[1:] or "--dry-run" in argv[1:]
    hint = None
    if "--here" in argv:
        i = argv.index("--here")
        if i + 1 < len(argv):
            here = Path(argv[i + 1])
            # <共有>/_仕組み/tools/準備/
            hint = here.resolve().parents[2] if len(here.resolve().parents) >= 3 else None
    if DIST is not None and hint is None:
        hint = DIST.parents[3] if len(DIST.parents) >= 4 else None  # <共有>/_仕組み/tools/配布/<版>/
    s = Setup(role, dry, shared_hint=hint)
    if DIST is not None and role != "管理者":
        s.dist = DIST if (DIST / "manifest.toml").is_file() else None
    return s.main()


if __name__ == "__main__":
    sys.exit(main())
