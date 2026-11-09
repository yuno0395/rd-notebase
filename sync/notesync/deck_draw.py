"""F-59b: 説明資料を Excalidraw の図にする(仕様書「資料の図の形」「資料のひな形」)。

1ページ = 16:9 のフレーム1つ。フレームは上から順に縦に並べ、名前は `01 表紙`・`02 <見出し>`(PDF の順)。
資料と一緒に「共通の図」(<資料>_共通.excalidraw.md)を作る。中にフレーム「表紙」「ページ」があり、
ひな形(共有 vault の _仕組み/説明資料のひな形/)の線・ロゴ・ヘッダー・フッターを写す。
資料の各ページのいちばん下に、共通のフレームを絵として貼って固定する。共通を1か所直せば全ページが変わる。
ページの番号・章・引用はページごとに違うので、共通には入れず各ページに文字として置く。

Excalidraw の書き出した SVG は使わない(枠の外も入るため)。図は圧縮しない JSON で書く。
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import shutil
import string
from dataclasses import dataclass, field
from pathlib import Path

from . import frontmatter

W, H, GAP = 1600, 900, 200
FONT = 2                        # Excalidraw の Normal(手書き風でない字体)
MAIN, ACCENT = "#1f3a5f", "#e8833a"   # 紺と橙(ひな形に色の四角がないとき)
INK, MUTED, LINE, HEAD_BG = "#1e1e1e", "#59636e", "#c9d1d9", "#f6f8fa"
LH = 1.25                       # 行の高さ(文字の大きさの何倍か)
PAGE_KEYS = ("{ページ}", "{全ページ}", "{章}", "{引用}")
COVER_ID, PAGE_ID = "deck_cover", "deck_page"
TEMPLATE_DIR = Path("_仕組み") / "説明資料のひな形"
BODY_WORD, LOGO_WORD = "本文", "ロゴを貼る"
COLOR_WORDS = {"メイン色": "main", "アクセント色": "accent"}
DRAWN = {"rectangle", "ellipse", "diamond", "line", "arrow", "freedraw", "text", "image"}
CUT_MARK = "…(続きはノートに)"
REF_MAX = 90                    # 引用の文字はこの長さまで。超えたら「ほか N 件」

HEADER = ("==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== "
          "You can decompress Drawing data with the command palette: 'Decompress current Excalidraw file'. "
          "For more info check in plugin settings under 'Saving'")


class TemplateError(Exception):
    """ひな形を読めない(壊れている・圧縮されている)。"""


# ---------- 文字の大きさ ----------

def char_w(c: str, size: float) -> float:
    return size * (1.0 if ord(c) > 0x2E7F else 0.56)


def line_w(s: str, size: float) -> float:
    return sum(char_w(c, size) for c in s)


def wrap(text: str, size: float, width: float) -> list[str]:
    out = []
    for para in text.split("\n"):
        cur, w = "", 0.0
        for c in para:
            cw = char_w(c, size)
            if cur and w + cw > width:
                out.append(cur)
                cur, w = "", 0.0
            cur += c
            w += cw
        out.append(cur)
    return out


def new_id(n: int = 8) -> str:
    return "".join(random.choice(string.ascii_letters + string.digits) for _ in range(n))


def file_id(link: str) -> str:
    return hashlib.sha1(link.encode("utf-8")).hexdigest()[:40]


# ---------- 図(Excalidraw の JSON)を組み立てる ----------

class Scene:
    def __init__(self):
        self.els: list[dict] = []
        self.files: dict[str, str] = {}   # fileId → [[リンク]] の中身

    def base(self, typ: str, x: float, y: float, w: float, h: float, frame: str | None = None, **kw) -> dict:
        e = {"id": new_id(), "type": typ, "x": round(x, 2), "y": round(y, 2), "width": round(w, 2),
             "height": round(h, 2), "angle": 0, "strokeColor": INK, "backgroundColor": "transparent",
             "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0, "opacity": 100,
             "groupIds": [], "frameId": frame, "roundness": None, "seed": random.randint(1, 2**31 - 1),
             "version": 1, "versionNonce": random.randint(1, 2**31 - 1), "isDeleted": False,
             "boundElements": [], "updated": 1, "link": None, "locked": False}
        e.update(kw)
        self.els.append(e)
        return e

    def frame(self, x, y, name, fid=None, custom=None) -> dict:
        e = self.base("frame", x, y, W, H, None, name=name)
        if fid:
            e["id"] = fid
        if custom:
            e["customData"] = custom
        return e

    def rect(self, x, y, w, h, frame, stroke="transparent", bg="transparent", **kw) -> dict:
        return self.base("rectangle", x, y, w, h, frame, strokeColor=stroke, backgroundColor=bg, **kw)

    def line(self, x, y, w, frame, color=LINE, width=1) -> dict:
        return self.base("line", x, y, w, 0, frame, strokeColor=color, strokeWidth=width,
                         points=[[0, 0], [round(w, 2), 0]], lastCommittedPoint=None,
                         startBinding=None, endBinding=None, startArrowhead=None, endArrowhead=None)

    def text(self, x, y, text, size, color, frame, width=None, align="left", custom=None,
             container=None, height=None, valign="top") -> dict:
        lines = wrap(text, size, width) if width else text.split("\n")
        w = width if width else max([line_w(s, size) for s in lines] + [1])
        h = max(len(lines), 1) * size * LH
        if align == "right" and not width and not container:
            x = x - w
        elif align == "center" and not width and not container:
            x = x - w / 2
        e = self.base("text", x, y, w, height if container and height else h, frame, strokeColor=color,
                      text="\n".join(lines), rawText=text, originalText=text, fontSize=size, fontFamily=FONT,
                      textAlign=align, verticalAlign=valign, containerId=container, autoResize=not width,
                      lineHeight=LH, baseline=round(size * 0.9, 2))
        if custom:
            e["customData"] = custom
        return e

    def box(self, x, y, w, h, text, size, color, frame, stroke="transparent", bg="transparent",
            align="left", valign="top", custom=None, min_size=None) -> tuple[dict, dict]:
        """四角に結んだ文字(四角の大きさを変えると折り返す)。入りきらなければ小さくし、それでもなら切る。"""
        pad = 6
        size, text = fit(text, size, w - 2 * pad, h - 2 * pad, min_size or size)
        r = self.rect(x, y, w, h, frame, stroke=stroke, bg=bg)
        lines = wrap(text, size, w - 2 * pad)
        th = len(lines) * size * LH
        ty = y + pad if valign == "top" else y + (h - th) / 2 if valign == "middle" else y + h - pad - th
        t = self.text(x + pad, ty, text, size, color, frame, width=w - 2 * pad, align=align, custom=custom,
                      container=r["id"], valign=valign)
        r["boundElements"] = [{"type": "text", "id": t["id"]}]
        return r, t

    def image(self, x, y, w, h, link, frame, locked=False, custom=None) -> dict:
        fid = file_id(link)
        self.files[fid] = link
        e = self.base("image", x, y, w, h, frame, fileId=fid, status="saved", scale=[1, 1], crop=None,
                      locked=locked)
        if custom:
            e["customData"] = custom
        return e


def fit(text: str, size: float, w: float, h: float, min_size: float) -> tuple[float, str]:
    s = size
    while s > min_size and len(wrap(text, s, w)) * s * LH > h:
        s -= 1
    lines = wrap(text, s, w)
    most = max(int(h // (s * LH)), 1)
    if len(lines) > most:
        keep = lines[:most]
        keep[-1] = keep[-1][: max(len(keep[-1]) - len(CUT_MARK), 0)] + CUT_MARK
        return s, "\n".join(keep)
    return s, text


def dump(scene_els: list[dict], files: dict[str, str], fm: dict | None = None) -> str:
    """Excalidraw の .excalidraw.md(圧縮しない)。"""
    head = ["---", "excalidraw-plugin: parsed", "tags: [excalidraw]"]
    for k, v in (fm or {}).items():
        head.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    head.append("---")
    texts = [f"{e['originalText']} ^{e['id']}\n" for e in scene_els
             if e["type"] == "text" and not e.get("isDeleted")]
    data = {"type": "excalidraw", "version": 2, "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin",
            "elements": scene_els, "appState": {"gridSize": 20, "viewBackgroundColor": "#ffffff"}, "files": {}}
    body = ["\n".join(head), HEADER, "", "# Excalidraw Data", "", "## Text Elements", *texts]
    if files:
        body += ["## Embedded Files", *[f"{k}: [[{v}]]" for k, v in files.items()], ""]
    body += ["%%", "## Drawing", "```json", json.dumps(data, ensure_ascii=False, indent=1), "```", "%%", ""]
    return "\n".join(body)


EMBED = re.compile(r"^([0-9A-Za-z]+): \[\[(.+?)\]\]\s*$", re.M)


def load(path: Path) -> tuple[dict, list[dict], dict[str, str]]:
    """(属性欄, 要素, fileId → リンク)。圧縮されていたら TemplateError。"""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise TemplateError(str(e)) from e
    return load_text(text)


def load_text(text: str) -> tuple[dict, list[dict], dict[str, str]]:
    m = re.search(r"```json\n(.*?)\n```", text, re.S)
    if not m:
        raise TemplateError("図の中身(JSON)がありません。圧縮しない設定で保存してください")
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise TemplateError(f"図の中身を読めません: {e}") from e
    els = [e for e in data.get("elements", []) if not e.get("isDeleted")]
    files = {}
    sec = re.search(r"## Embedded Files\n(.*?)(?:\n%%|\n## |\Z)", text, re.S)
    if sec:
        files = {a: b for a, b in EMBED.findall(sec.group(1))}
    return frontmatter.load(text), els, files


# ---------- ひな形 ----------

@dataclass
class Template:
    els: list[dict]                       # フレームの左上を原点にし、W×H に合わせたもの
    files: dict[str, Path | None]         # fileId → 画像のファイル(読めなければ None)
    body: tuple[float, float, float, float]
    colors: dict[str, str] = field(default_factory=dict)

    def has(self, key: str) -> bool:
        return any(key in (e.get("originalText") or e.get("text") or "") for e in self.els if e["type"] == "text")


def inside(e: dict, f: dict) -> bool:
    cx, cy = e["x"] + e.get("width", 0) / 2, e["y"] + e.get("height", 0) / 2
    return f["x"] <= cx <= f["x"] + f["width"] and f["y"] <= cy <= f["y"] + f["height"]


def text_of(e: dict) -> str:
    return str(e.get("originalText") or e.get("text") or "").strip()


def holder(els: list[dict], t: dict) -> dict | None:
    """文字の入っている四角(結んだ四角か、文字を囲む四角)。"""
    by_id = {e["id"]: e for e in els}
    if t.get("containerId") in by_id:
        return by_id[t["containerId"]]
    rs = [e for e in els if e["type"] == "rectangle" and inside(t, e)]
    return min(rs, key=lambda r: r["width"] * r["height"]) if rs else None


def read_template(path: Path, root: Path | None) -> Template:
    _, els, links = load(path)
    frames = [e for e in els if e["type"] == "frame"]
    if not frames:
        raise TemplateError("16:9 の枠(フレーム)がありません")
    f = frames[0]
    kx, ky = W / max(f["width"], 1), H / max(f["height"], 1)
    k = min(kx, ky)
    colors, skip = {}, set()
    body = None
    for t in els:
        if t["type"] != "text":
            continue
        word = text_of(t)
        box_ = holder(els, t)
        if word in COLOR_WORDS and box_ and not inside(box_, f):
            colors[COLOR_WORDS[word]] = box_.get("backgroundColor") or ""
            skip |= {t["id"], box_["id"]}
        elif word == BODY_WORD and box_ and inside(box_, f):
            body = ((box_["x"] - f["x"]) * kx, (box_["y"] - f["y"]) * ky, box_["width"] * kx, box_["height"] * ky)
            skip |= {t["id"], box_["id"]}
        elif word == LOGO_WORD and inside(t, f):
            skip.add(t["id"])
            if box_ and box_.get("strokeStyle") == "dashed":
                skip.add(box_["id"])
    out = []
    for e in els:
        if e["id"] in skip or e["type"] not in DRAWN:
            continue
        if not (e.get("frameId") == f["id"] or (not e.get("frameId") and inside(e, f))):
            continue
        c = copy.deepcopy(e)
        c["x"], c["y"] = (e["x"] - f["x"]) * kx, (e["y"] - f["y"]) * ky
        c["width"], c["height"] = e.get("width", 0) * kx, e.get("height", 0) * ky
        if "points" in c:
            c["points"] = [[p[0] * kx, p[1] * ky] for p in c["points"]]
        if c["type"] == "text":
            c["fontSize"] = round(c.get("fontSize", 20) * k, 1)
            c["fontFamily"] = c.get("fontFamily") or FONT
        if c.get("containerId") in skip:
            c["containerId"] = None
        c["boundElements"] = [b for b in (c.get("boundElements") or []) if b.get("id") not in skip]
        out.append(c)
    files: dict[str, Path | None] = {}
    for e in out:
        if e["type"] == "image":
            files[e["fileId"]] = find_file(links.get(e["fileId"], ""), path.parent, root)
    body = body or (W * 0.04, H * 0.12, W * 0.92, H * 0.76)
    return Template(out, files, body, {k2: v for k2, v in colors.items() if v and v != "transparent"})


def find_file(link: str, here: Path, root: Path | None) -> Path | None:
    name = link.split("|", 1)[0].split("#", 1)[0].strip()
    if not name:
        return None
    for base in [here] + ([root] if root else []):
        p = base / name
        if p.is_file():
            return p
    if root:
        hit = next((p for p in root.rglob(Path(name).name) if p.is_file()), None)
        return hit
    return None


def default_template(kind: str) -> Template:
    """ひな形がないときの形(配るひな形と同じ。上下に帯)。"""
    sc = Scene()
    default_elements(kind, sc)
    els = [e for e in sc.els if e.get("frameId") == "f"]
    for e in els:
        e["frameId"] = None
    body = (W * 0.04, H * 0.12, W * 0.92, H * 0.76)
    drop = set()
    for t in els:
        if t["type"] == "text" and text_of(t) in (BODY_WORD, LOGO_WORD):
            drop |= {t["id"], t.get("containerId")}
            if text_of(t) == BODY_WORD:
                b = next(e for e in els if e["id"] == t["containerId"])
                body = (b["x"], b["y"], b["width"], b["height"])
    for e in els:
        e["boundElements"] = [b for b in e.get("boundElements") or [] if b["id"] not in drop]
    return Template([e for e in els if e["id"] not in drop], {}, body, {"main": MAIN, "accent": ACCENT})


def default_elements(kind: str, sc: Scene) -> list[dict]:
    """配るひな形の中身(ページ / 表紙)。フレームの id は "f"。"""
    f = "f"
    if kind == "ページ":
        sc.rect(0, 0, W, 64, f, bg=MAIN)
        sc.text(40, 16, "{章}", 24, "#ffffff", f)
        sc.text(W - 40, 18, "{機密区分}", 22, "#ffffff", f, align="right")
        sc.line(40, H - 54, W - 80, f, color=MAIN, width=2)
        sc.text(40, H - 40, "{資料名}　文書番号: {文書番号}", 16, MUTED, f)
        sc.text(W / 2, H - 38, "{引用}", 13, MUTED, f, align="center")
        sc.text(W - 40, H - 40, "{ページ} / {全ページ}", 16, MUTED, f, align="right")
        sc.box(40, 84, W - 80, H - 84 - 64, BODY_WORD, 20, MUTED, f, stroke=LINE)
    else:
        r, _ = sc.box(60, 50, 240, 100, LOGO_WORD, 20, MUTED, f, stroke=MUTED, align="center", valign="middle")
        r["strokeStyle"] = "dashed"
        sc.text(W - 60, 56, "{機密区分}", 26, MAIN, f, align="right")
        sc.text(W - 60, 96, "文書番号: {文書番号}", 18, MUTED, f, align="right")
        sc.text(120, 300, "{資料名}", 60, MAIN, f, width=W - 240)
        sc.line(120, 470, W - 240, f, color=ACCENT, width=4)
        sc.text(120, 500, "{筋書き}", 28, MUTED, f)
        sc.text(120, 550, "{プロジェクト}", 28, INK, f)
        sc.text(120, 600, "{日付}　{所属} {作った人}", 24, INK, f)
        sc.rect(0, H - 60, W, 60, f, bg=MAIN)
        sc.text(40, H - 44, "{会社名}", 22, "#ffffff", f)
    sc.box(W + 100, 0, 220, 80, "メイン色", 20, "#ffffff", None, bg=MAIN, align="center", valign="middle")
    sc.box(W + 100, 120, 220, 80, "アクセント色", 20, "#ffffff", None, bg=ACCENT, align="center", valign="middle")
    return sc.els


def template_file(kind: str) -> str:
    """配るひな形のファイル(_仕組み/説明資料のひな形/<kind>.excalidraw.md)の中身。"""
    random.seed(kind)
    sc = Scene()
    sc.frame(0, 0, kind, fid="frame1")
    default_elements(kind, sc)
    for e in sc.els:
        if e.get("frameId") == "f":
            e["frameId"] = "frame1"
    random.seed()
    # フレームは中身の後ろに置く
    els = [e for e in sc.els if e["type"] != "frame"] + [e for e in sc.els if e["type"] == "frame"]
    return dump(els, {})


def templates(shared: Path | None, story: str) -> tuple[Template, Template, list[str]]:
    """(表紙, ページ, 知らせ)。<筋書き>_表紙 → 表紙 の順に探す。読めなければ配る形で作り、知らせを返す。"""
    notes = []
    out = []
    for kind in ("表紙", "ページ"):
        tpl = None
        if shared:
            for name in (f"{story}_{kind}", kind):
                p = shared / TEMPLATE_DIR / f"{name}.excalidraw.md"
                if p.is_file():
                    try:
                        tpl = read_template(p, shared)
                    except TemplateError:
                        notes.append("ひな形を読めませんでした")
                    break
        out.append(tpl or default_template(kind))
    return out[0], out[1], sorted(set(notes))


# ---------- 置き換え ----------

KEY = re.compile(r"\{[^{}\s]+\}")


def fill(text: str, values: dict[str, str]) -> str:
    return KEY.sub(lambda m: values.get(m.group(0), m.group(0)), text)


def is_page_text(e: dict) -> bool:
    return e["type"] == "text" and any(k in (e.get("originalText") or e.get("text") or "") for k in PAGE_KEYS)


def place(tpl_els: list[dict], scene: Scene, frame: str, ox: float, oy: float, values: dict[str, str],
          which: str, custom_key: str = "deck_tpl") -> list[dict]:
    """ひな形の要素を写す(id は新しくし、文字の言葉を置き換える)。which: common / page。"""
    pick = [e for e in tpl_els if (which == "page") == is_page_text(e)]
    ids = {e["id"]: new_id() for e in pick}
    out = []
    for e in pick:
        c = copy.deepcopy(e)
        c["id"] = ids[e["id"]]
        c["x"], c["y"] = c["x"] + ox, c["y"] + oy
        c["frameId"] = frame
        c["groupIds"] = [f"{g}_{frame}" for g in c.get("groupIds") or []]
        c["containerId"] = ids.get(c.get("containerId")) if c.get("containerId") else None
        c["boundElements"] = [dict(b, id=ids[b["id"]]) for b in (c.get("boundElements") or []) if b.get("id") in ids]
        c["seed"] = random.randint(1, 2**31 - 1)
        c["locked"] = False
        if c["type"] == "text":
            raw = c.get("originalText") or c.get("text") or ""
            if KEY.search(raw):
                c.setdefault("customData", {})[custom_key] = raw
            set_text(c, fill(raw, values))
        scene.els.append(c)
        out.append(c)
    return out


def set_text(e: dict, text: str) -> None:
    """文字を入れ替え、大きさを合わせる(右寄せ・真ん中寄せは端と真ん中を動かさない)。"""
    size = e.get("fontSize", 20)
    if e.get("containerId") or e.get("autoResize") is False:
        lines = wrap(text, size, max(e.get("width", 10), 10))
        e.update(text="\n".join(lines), rawText=text, originalText=text)
        if not e.get("containerId"):
            e["height"] = round(max(len(lines), 1) * size * LH, 2)
        return
    lines = text.split("\n")
    w = max([line_w(s, size) for s in lines] + [1])
    if e.get("textAlign") == "right":
        e["x"] = round(e["x"] + e.get("width", 0) - w, 2)
    elif e.get("textAlign") == "center":
        e["x"] = round(e["x"] + e.get("width", 0) / 2 - w / 2, 2)
    e.update(text=text, rawText=text, originalText=text, width=round(w, 2),
             height=round(max(len(lines), 1) * size * LH, 2))


# ---------- 中身 ----------

def plain_md(text: str) -> str:
    """欄の Markdown を図の文字に(箇条書きは「・」、表は「｜」で区切る)。"""
    out = []
    for line in text.splitlines():
        t = line.strip()
        if t.startswith("|"):
            cells = [c.strip() for c in t.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            out.append(" ｜ ".join(cells))
            continue
        m = re.match(r"^(?:[-*+]|\d+\.)\s+(?:\[[ xX]\]\s+)?(.*)$", t)
        out.append(f"・{m.group(1)}" if m else t)
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def sections_text(sections: list[tuple[str, str]]) -> str:
    parts = []
    for h, v in sections:
        body = plain_md(v) if v.strip() else "(まだ書いていません)"
        parts.append(f"■ {h}\n{body}" if h else body)
    return "\n\n".join(parts)


def refs_text(refs: list[tuple[str, str]], hide_ids: bool) -> str:
    if not refs:
        return ""
    items = [name if hide_ids else f"{fid} {name}" for fid, name in refs]
    out = "引用: " + items[0]
    used = 1
    for it in items[1:]:
        if len(out) + len(it) + 1 > REF_MAX:
            break
        out += "、" + it
        used += 1
    if used < len(items):
        out += f" ほか {len(items) - used} 件"
    return out


def svg_size(svg: str) -> tuple[float, float]:
    m = re.search(r'viewBox="\s*[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)[ ,]+([\d.]+)', svg)
    if m:
        return float(m.group(1)) or 4, float(m.group(2)) or 3
    w = re.search(r'\bwidth="([\d.]+)', svg)
    h = re.search(r'\bheight="([\d.]+)', svg)
    if w and h:
        return float(w.group(1)) or 4, float(h.group(1)) or 3
    return 4, 3


def styled_svg(svg: str) -> str:
    """K-Plex の形・工程表の SVG に色の決まりを入れる(週報の CSS の明るい方だけ)。"""
    from .weekly_html import CSS
    lines = CSS.strip().splitlines()
    light = "\n".join(lines[:2])
    figs = "\n".join(x for x in lines if ".kp" in x or ".gt" in x)
    style = f"<style>{light}\n{figs}</style>"
    svg = re.sub(r"<svg\b([^>]*)>", lambda m: f"<svg{m.group(1)}>{style}", svg, count=1)
    if "xmlns=" not in svg[:200]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def fit_box(aw: float, ah: float, bw: float, bh: float) -> tuple[float, float]:
    k = min(bw / aw, bh / ah)
    return aw * k, ah * k


# ---------- 表 ----------

TABLE_SIZE, ROW_PAD, MAX_LINES = 16, 8, 3


def cell_lines(text: str, w: float) -> list[str]:
    lines = wrap(text, TABLE_SIZE, w - 12)
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        lines[-1] = lines[-1][:-1] + "…"
    return lines


def row_h(cells: list[str], widths: list[float]) -> float:
    return max([len(cell_lines(str(c), w)) for c, w in zip(cells, widths)] + [1]) * TABLE_SIZE * LH + ROW_PAD * 2


def col_widths(n: int, total: float, first: float | None = None) -> list[float]:
    if n <= 0:
        return []
    if first and n > 1:
        return [total * first] + [total * (1 - first) / (n - 1)] * (n - 1)
    return [total / n] * n


def split_rows(headers: list[str], rows: list[list[str]], width: float, height: float, first=None) -> list[list[list[str]]]:
    """ページに入る分ずつに分ける。"""
    n = len(headers) or max((len(r) for r in rows), default=1)
    widths = col_widths(n, width, first)
    head = row_h(headers, widths) if headers else 0
    pages, cur, used = [], [], head
    for r in rows:
        h = row_h(r, widths)
        if cur and used + h > height:
            pages.append(cur)
            cur, used = [], head
        cur.append(r)
        used += h
    pages.append(cur)
    return pages


def draw_table(sc: Scene, x, y, width, headers, rows, frame, main, accent, first=None, key_col=False) -> None:
    n = len(headers) or max((len(r) for r in rows), default=1)
    widths = col_widths(n, width, first)
    cy = y
    if headers:
        h = row_h(headers, widths)
        cx = x
        for c, w in zip(headers, widths):
            sc.box(cx, cy, w, h, "\n".join(cell_lines(c, w)), TABLE_SIZE, "#ffffff", frame, stroke=main, bg=main,
                   valign="middle")
            cx += w
        cy += h
    for r in rows:
        h = row_h(r, widths)
        cx = x
        for i, (c, w) in enumerate(zip(list(r) + [""] * (n - len(r)), widths)):
            color = accent if key_col and i == 0 else INK
            sc.box(cx, cy, w, h, "\n".join(cell_lines(str(c), w)), TABLE_SIZE, color, frame, stroke=LINE,
                   valign="middle")
            cx += w
        cy += h


# ---------- 資料全体 ----------

@dataclass
class Page:
    kind: str
    title: str
    chapter: str
    slide: object = None
    rows: list[list[str]] | None = None   # 表を分けたときのこのページの分
    refs: list[tuple[str, str]] = field(default_factory=list)


def paginate(deck, body) -> list[Page]:
    """表の長いものを何枚かに分ける。"""
    bx, by, bw, bh = body
    out = []
    for s in deck.slides:
        if s.kind in ("table", "gaps") and s.rows:
            parts = split_rows(s.headers, s.rows, bw, bh - 72)
            for k, part in enumerate(parts):
                t = s.title if k == 0 else f"{s.title}(続き)"
                out.append(Page(s.kind, t, s.chapter, s, part, s.refs))
        elif s.kind == "summary" and s.sections:
            rows = [[k, v] for k, v in s.sections]
            parts = split_rows([], rows, bw, bh - 72, first=0.26)
            for k, part in enumerate(parts):
                out.append(Page(s.kind, s.title if k == 0 else f"{s.title}(続き)", s.chapter, s, part))
        else:
            out.append(Page(s.kind, s.title, s.chapter, s, None, list(getattr(s, "refs", []) or [])))
    return out


def link_for(path: Path, roots: list[Path], assets: Path, personal: Path) -> str:
    """vault の中のリンク。個人 vault に同じファイルがあればそれ(元の図を直すと変わる)、なければ写しを置く。"""
    for root in roots:
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if (personal / rel).is_file():
            return rel.as_posix()
    assets.mkdir(parents=True, exist_ok=True)
    dest = assets / path.name
    if not dest.exists() or dest.stat().st_mtime < path.stat().st_mtime:
        shutil.copy2(path, dest)
    return dest.relative_to(personal).as_posix()


def write_deck(deck, folder: Path, name: str, shared: Path | None, personal: Path) -> Path:
    """資料の図と共通の図を書く。戻り値は資料の図。"""
    cover, page, notes = templates(shared, deck.story)
    for n in notes:
        deck.gaps.append(["(ひな形)", n])
        if deck.slides and deck.slides[-1].kind == "gaps":
            deck.slides[-1].rows = deck.gaps
    main = page.colors.get("main") or cover.colors.get("main") or MAIN
    accent = page.colors.get("accent") or cover.colors.get("accent") or ACCENT
    folder.mkdir(parents=True, exist_ok=True)
    assets = folder / name
    common_rel = (folder / f"{name}_共通.excalidraw").relative_to(personal).as_posix()
    values = {"{機密区分}": deck.label, "{資料名}": deck.title, "{筋書き}": deck.story,
              "{プロジェクト}": deck.project if deck.story != "社外へ仕様を伝える" else "",
              "{日付}": deck.made_on.isoformat(), "{作った人}": deck.maker, "{所属}": deck.affiliation,
              "{会社名}": deck.company, "{文書番号}": ""}

    # 共通の図
    com = Scene()
    files: dict[str, str] = {}
    for tpl, fid, fname, oy in ((cover, COVER_ID, "表紙", 0), (page, PAGE_ID, "ページ", H + GAP)):
        place(tpl.els, com, fid, 0, oy, values, "common")
        for e in com.els:
            if e["type"] == "image" and e.get("frameId") == fid and e["fileId"] in tpl.files:
                src = tpl.files.get(e["fileId"])
                if src:
                    com.files[e["fileId"]] = link_for(src, [shared] if shared else [], assets, personal)
        if fid == COVER_ID and not tpl.has("{機密区分}"):
            com.text(40, oy + H - 30, "機密区分: " + deck.label, 14, MUTED, fid,
                     custom={"deck_tpl": "機密区分: {機密区分}"})
        com.frame(0, oy, fname, fid=fid)
    common_path = folder / f"{name}_共通.excalidraw.md"
    common_path.write_text(dump(com.els, com.files, {"deck_common": True}), encoding="utf-8")

    # 資料の図
    sc = Scene()
    pages = paginate(deck, page.body)
    total = len(pages)
    for i, pg in enumerate(pages, 1):
        oy = (i - 1) * (H + GAP)
        fid = f"deck_p{i:02d}"
        is_cover = pg.kind == "cover"
        tpl = cover if is_cover else page
        sc.image(0, oy, W, H, f"{common_rel}#^clippedframe={COVER_ID if is_cover else PAGE_ID}", fid, locked=True,
                 custom={"deck_common": "表紙" if is_cover else "ページ"})
        pv = {"{ページ}": str(i), "{全ページ}": str(total), "{章}": "" if pg.chapter == pg.title else pg.chapter,
              "{引用}": refs_text(pg.refs, deck.hide_ids)}
        place(tpl.els, sc, fid, 0, oy, pv, "page")
        if not is_cover and not tpl.has("{引用}"):
            sc.text(12, oy + H - 22, pv["{引用}"], 12, MUTED, fid, custom={"deck_tpl": "{引用}"})
        before = len(sc.els)
        if not is_cover:
            content(sc, pg, fid, page.body, oy, main, accent, assets, personal, shared, deck)
        if getattr(pg.slide, "faded", False):
            for e in sc.els[before:]:
                e["opacity"] = 50
        custom = {"deck_kind": pg.kind, "deck_title": pg.title, "deck_chapter": pv["{章}"],
                  "deck_refs": [list(r) for r in pg.refs]}
        if pg.kind == "gaps":
            custom["deck_gaps"] = deck.gaps
        sc.frame(0, oy, f"{i:02d} {pg.title}", fid=fid, custom=custom)
    fm = {"deck_source": [deck.source], "deck_story": [deck.story], "deck_title": deck.title,
          "deck_label": deck.label, "deck_outside": deck.hide_ids, "deck_pages": total,
          "deck_project": deck.project or "共通", "deck_pip": deck.pip,
          "deck_report": "" if (deck.pip or deck.hide_ids) else (deck.project or "共通"),
          "deck_common": common_path.name}
    path = folder / f"{name}.excalidraw.md"
    path.write_text(dump(sc.els, sc.files, fm), encoding="utf-8")
    return path


def content(sc: Scene, pg: Page, fid: str, body, oy: float, main: str, accent: str, assets: Path,
            personal: Path, shared: Path | None, deck) -> None:
    bx, by, bw, bh = body
    by += oy
    s = pg.slide
    sc.box(bx, by, bw, 56, pg.title, 32, main, fid, min_size=20)
    cy, ch = by + 66, bh - 66
    if pg.kind == "note":
        txt_x, txt_w = bx, bw
        if s.image_path:
            roots = [r for r in (shared, personal) if r]
            link = link_for(s.image_path, roots, assets, personal)
            aw, ah = svg_size(s.image or "")
            w, h = fit_box(aw, ah, bw * 0.46, ch - 30)
            sc.image(bx, cy, w, h, link, fid)
            txt_x, txt_w = bx + bw * 0.49, bw * 0.51
        sc.box(txt_x, cy, txt_w, ch - 30, sections_text(s.sections), 20, INK, fid, min_size=13)
        if s.foot:
            sc.text(bx, by + bh - 22, s.foot, 13, MUTED, fid, width=bw)
    elif pg.kind in ("table", "gaps"):
        if pg.rows:
            draw_table(sc, bx, cy, bw, s.headers, pg.rows, fid, main, accent)
        else:
            sc.text(bx, cy, "なし", 20, MUTED, fid)
    elif pg.kind == "summary":
        if pg.rows:
            draw_table(sc, bx, cy, bw, [], pg.rows, fid, main, accent, first=0.26, key_col=True)
    elif pg.kind == "figure":
        if s.svg:
            assets.mkdir(parents=True, exist_ok=True)
            from .deck import SAFE
            p = assets / SAFE.sub("_", f"{pg.title}.svg")
            p.write_text(styled_svg(s.svg), encoding="utf-8")
            aw, ah = svg_size(s.svg)
            w, h = fit_box(aw, ah, bw, ch)
            sc.image(bx + (bw - w) / 2, cy, w, h, p.relative_to(personal).as_posix(), fid)
    else:   # text
        y = cy
        if s.big:
            r, _ = sc.box(bx, y, bw, ch * 0.5, s.big, 44, main, fid, align="center", valign="middle", min_size=24)
            y += ch * 0.5 + 10
        rest = sections_text([("", v) for _, v in s.sections if v.strip()])
        if rest:
            sc.box(bx, y, bw, by + bh - y, rest, 20, INK, fid, min_size=13)
        elif not s.big:
            sc.text(bx, y, "(まだ書いていません)", 20, MUTED, fid)


# ---------- つなぐ(右クリック「説明資料をつなぐ」) ----------

def frames_of(els: list[dict]) -> list[dict]:
    return sorted([e for e in els if e["type"] == "frame"], key=lambda f: (f["y"], f["x"]))


def page_text(tpl: str, page: int, total: int, chapter: str, refs: list, hide_ids: bool) -> str:
    return fill(tpl, {"{ページ}": str(page), "{全ページ}": str(total), "{章}": chapter,
                      "{引用}": refs_text([tuple(r) for r in refs], hide_ids)})


def join_decks(paths: list[Path], personal: Path, label: str, inside_: bool, today) -> Path:
    """選んだ順に資料の図をつなぎ、新しい資料の図を作る(もとは変えない)。
    表紙は1つ目だけ、2つ目からは資料名だけの区切りのページ。共通の図は1つ目のものを写す。"""
    from .deck import SAFE, free_name
    decks = []
    for p in paths:
        fm, els, files = load(p)
        if not fm.get("deck_common"):
            raise TemplateError(f"説明資料の図ではありません: {p.name}")
        decks.append((p, fm, els, files))
    first_p, first_fm, _, _ = decks[0]
    folder = first_p.parent
    name = free_name(folder, SAFE.sub("_", f"つないだ資料_{first_fm.get('deck_title') or first_p.stem}_{today.isoformat()}"))
    hide = not inside_

    # 共通の図: 1つ目を写し、機密区分を選んだものにする
    cfm, cels, cfiles = load(folder / str(first_fm["deck_common"]))
    for e in cels:
        tpl = (e.get("customData") or {}).get("deck_tpl", "")
        if e["type"] == "text" and "{機密区分}" in tpl:
            cur = e.get("originalText") or e.get("text") or ""
            set_text(e, cur.replace(str(first_fm.get("deck_label") or ""), label) if first_fm.get("deck_label") else fill(tpl, {"{機密区分}": label}))
    common_path = folder / f"{name}_共通.excalidraw.md"
    common_path.write_text(dump(cels, cfiles, {"deck_common": True}), encoding="utf-8")
    common_rel = common_path.relative_to(personal).as_posix()[: -len(".md")]

    # ページの番号・章・引用の文字の見本(1つ目の資料の、表紙でない最初のページから)
    proto: list[dict] = []
    _, _, els0, _ = decks[0]
    for f in frames_of(els0):
        if (f.get("customData") or {}).get("deck_kind") != "cover":
            proto = [e for e in els0 if e.get("frameId") == f["id"] and "deck_tpl" in (e.get("customData") or {})]
            proto = [dict(e, _dy=e["y"] - f["y"], _dx=e["x"] - f["x"]) for e in proto]
            break

    out = Scene()
    pages: list[tuple[str, dict, list[dict]]] = []   # (種類, フレームの customData, 要素)
    gaps: list[list[str]] = []
    files: dict[str, str] = {}
    for k, (p, fm, els, fl) in enumerate(decks):
        for f in frames_of(els):
            cd = dict(f.get("customData") or {})
            kind = cd.get("deck_kind", "")
            if kind == "gaps":
                gaps += cd.get("deck_gaps") or []
                continue
            if kind == "cover" and k > 0:
                pages.append(("divider", {"deck_kind": "divider", "deck_title": str(fm.get("deck_title") or p.stem),
                                          "deck_chapter": "", "deck_refs": []}, []))
                continue
            kids = [e for e in els if e.get("frameId") == f["id"]]
            for e in kids:
                if e["type"] == "image" and not (e.get("customData") or {}).get("deck_common") and e["fileId"] in fl:
                    files[e["fileId"]] = fl[e["fileId"]]
            pages.append((kind, cd | {"_y": f["y"]}, kids))
    if gaps:
        pages.append(("gaps", {"deck_kind": "gaps", "deck_title": "足りないところ", "deck_chapter": "",
                               "deck_refs": [], "deck_gaps": gaps}, []))
    total = len(pages)
    for i, (kind, cd, kids) in enumerate(pages, 1):
        oy = (i - 1) * (H + GAP)
        fid = f"deck_p{i:02d}"
        refs = cd.get("deck_refs") or []
        if kids:
            ids = {e["id"]: new_id() for e in kids}
            dy = oy - cd["_y"]
            for e in kids:
                c = copy.deepcopy(e)
                c["id"] = ids[e["id"]]
                c["y"] = c["y"] + dy
                c["frameId"] = fid
                c["groupIds"] = [f"{g}_{fid}" for g in c.get("groupIds") or []]
                c["containerId"] = ids.get(c.get("containerId")) if c.get("containerId") else None
                c["boundElements"] = [dict(b, id=ids[b["id"]]) for b in c.get("boundElements") or [] if b.get("id") in ids]
                ccd = c.get("customData") or {}
                if ccd.get("deck_common"):
                    link = f"{common_rel}#^clippedframe={COVER_ID if ccd['deck_common'] == '表紙' else PAGE_ID}"
                    c["fileId"] = file_id(link)
                    files[c["fileId"]] = link
                if c["type"] == "text" and ccd.get("deck_tpl") and any(x in ccd["deck_tpl"] for x in PAGE_KEYS):
                    set_text(c, page_text(ccd["deck_tpl"], i, total, cd.get("deck_chapter", ""), refs, hide))
                out.els.append(c)
        else:
            link = f"{common_rel}#^clippedframe={PAGE_ID}"
            out.image(0, oy, W, H, link, fid, locked=True, custom={"deck_common": "ページ"})
            for e in proto:
                c = copy.deepcopy({x: v for x, v in e.items() if not x.startswith("_")})
                c["id"] = new_id()
                c["x"], c["y"] = e["_dx"], oy + e["_dy"]
                c["frameId"] = fid
                set_text(c, page_text(c["customData"]["deck_tpl"], i, total, "", [], hide))
                out.els.append(c)
            if kind == "divider":
                out.box(W * 0.08, oy + H * 0.35, W * 0.84, H * 0.3, cd["deck_title"], 48, MAIN, fid,
                        align="center", valign="middle", min_size=24)
            else:
                out.box(W * 0.04, oy + H * 0.12, W * 0.92, 56, "足りないところ", 32, MAIN, fid)
                rows_ = gaps
                draw_table(out, W * 0.04, oy + H * 0.12 + 66, W * 0.92, ["ノート", "足りないもの"],
                           rows_[:14], fid, MAIN, ACCENT)
        cd2 = {x: v for x, v in cd.items() if not x.startswith("_")}
        out.frame(0, oy, f"{i:02d} {cd2.get('deck_title', '')}", fid=fid, custom=cd2)
    srcs, stories = [], []
    for _, fm, _, _ in decks:
        srcs += [x for x in fm.get("deck_source") or [] if x not in srcs]
        stories += [x for x in fm.get("deck_story") or [] if x not in stories]
    report = ""
    if inside_ and not any(fm.get("deck_pip") for _, fm, _, _ in decks):
        report = str(first_fm.get("deck_project") or "共通")
    fm = {"deck_source": srcs, "deck_story": stories, "deck_title": f"つないだ資料_{first_fm.get('deck_title', '')}",
          "deck_label": label, "deck_outside": hide, "deck_pages": total,
          "deck_project": first_fm.get("deck_project") or "共通",
          "deck_pip": any(bool(fm.get("deck_pip")) for _, fm, _, _ in decks), "deck_report": report,
          "deck_common": common_path.name}
    path = folder / f"{name}.excalidraw.md"
    path.write_text(dump(out.els, files, fm), encoding="utf-8")
    return path
