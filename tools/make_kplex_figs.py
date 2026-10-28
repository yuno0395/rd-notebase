"""K-Plex の使い方マニュアル(docs/マニュアル/07_K-Plexの使い方.md)の絵を作る。

    python tools/make_kplex_figs.py

docs/マニュアル/img/kplex/*.svg を書き直す。絵は K-Plex 0.3.0 の画面を
単純にした「イメージ図」。仕組み(属性名や向き)を変えたら、ここを直して作り直す。
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent.parent / "docs" / "マニュアル" / "img" / "kplex"

FONT = "'Yu Gothic UI','Meiryo','Hiragino Sans','Noto Sans JP',sans-serif"
INK = "#1d2430"
SUB = "#5b6472"
LINE = "#b8bec8"
PRIO = {1: ("#e5484d", "#ffffff"), 2: ("#f08c00", "#ffffff"), 3: ("#f8e46e", "#1d2430"), 4: ("#c9cbd3", "#1d2430")}
ZONE = {
    "up": ("#eef3fb", "上 = 親"),
    "down": ("#eef7f1", "下 = 子"),
    "left": ("#f1f7ec", "左 = 目論見・味方"),
    "right": ("#fdf0ee", "右 = 不安材料・反対"),
}


def tw(s: str, fs: float) -> float:
    """文字列のおおよその幅(全角 1、半角 0.55)。"""
    return sum(fs if ord(c) > 0x2E7F else fs * 0.55 for c in s)


class Svg:
    def __init__(self, w: int, h: int, bg: str = "#ffffff"):
        self.w, self.h = w, h
        self.parts: list[str] = [
            f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" rx="14" fill="{bg}" stroke="#d6dae1"/>'
        ]

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, fs=15, color=INK, anchor="middle", weight="normal") -> None:
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-size="{fs}" fill="{color}" text-anchor="{anchor}" '
            f'font-weight="{weight}" dominant-baseline="middle">{escape(s)}</text>'
        )

    def rect(self, x, y, w, h, fill="#fff", stroke=LINE, rx=10, dash=False, sw=1.2) -> None:
        d = ' stroke-dasharray="6 4"' if dash else ""
        self.add(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{sw}"{d}/>'
        )

    def line(self, x1, y1, x2, y2, color=LINE, w=1.4, dash=False, arrow=False) -> None:
        d = ' stroke-dasharray="5 4"' if dash else ""
        a = ' marker-end="url(#arrow)"' if arrow else ""
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{w}"{d}{a}/>')

    def badge(self, x, y, n) -> None:
        """番号の丸(説明文の番号と対応)。"""
        self.add(f'<circle cx="{x}" cy="{y}" r="12" fill="#2f6fde"/>')
        self.text(x, y + 0.5, str(n), 13, "#fff", weight="bold")

    def key(self, x, y, s, fs=15) -> float:
        """キーの絵。幅を返す。"""
        w = tw(s, fs) + 20
        self.rect(x, y - 15, w, 30, "#f4f5f7", "#9aa1ad", rx=6)
        self.add(f'<rect x="{x:.1f}" y="{y + 12:.1f}" width="{w:.1f}" height="3" rx="1.5" fill="#9aa1ad"/>')
        self.text(x + w / 2, y, s, fs, INK, weight="bold")
        return w

    def save(self, name: str, title: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        body = "\n".join(self.parts)
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" font-family="{FONT}" role="img" aria-label="{escape(title)}">\n'
            f"<title>{escape(title)}</title>\n"
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#2f6fde"/></marker></defs>\n'
            f"{body}\n</svg>\n"
        )
        (OUT / name).write_text(svg, encoding="utf-8")


# ---- カード -------------------------------------------------------------

def card_w(label, center=False, small=False):
    fs = 22 if center else (12 if small else 15)
    return max(tw(label, fs) + (40 if center else 24), 56 if small else 70)


def card(s: Svg, cx, cy, label, kind="", prio=None, done=False, center=False, small=False):
    """K-Plex のカード。kind は小さく上に出す種類の名前。返り値は (x, y, w, h)。"""
    fs = 22 if center else (12 if small else 15)
    w = card_w(label, center, small)
    h = 58 if center else (30 if small else 40)
    x, y = cx - w / 2, cy - h / 2
    if center:
        fill, color, stroke = "#1f3a5f", "#ffffff", "#1f3a5f"
    elif done:
        fill, color, stroke = "#f3f3f5", "#9a9a9a", "#b0b0b0"
    elif prio:
        fill, color = PRIO[prio]
        stroke = fill
    else:
        fill, color, stroke = "#ffffff", INK, "#8f97a3"
    s.rect(x, y, w, h, fill, stroke, rx=8 if small else 10, dash=done, sw=2 if center else 1.3)
    s.text(cx, cy + 1, label, fs, color, weight="bold" if center else "normal")
    if kind:
        s.text(cx, y - 9, kind, 11, SUB)
    return x, y, w, h


def compass(
    s: Svg,
    center,
    up=(),
    down=(),
    left=(),
    right=(),
    siblings=(),
    box=None,
    zones=True,
    grand=None,
):
    """Compass 表示を描く。各要素は (名前, 種類, priority, 終わったか)。

    box = (x, y, w, h) の範囲に描く。grand は {下のカードの番号: [(名前,...)]}(拡張表示)。
    """
    bx, by, bw, bh = box or (0, 0, s.w, s.h)
    cx, cy = bx + bw / 2, by + bh / 2
    pad = 14
    if zones:
        zw = bw * 0.27
        zh = bh * 0.27
        s.rect(bx + zw, by + pad, bw - 2 * zw, zh - pad, ZONE["up"][0], "none", rx=10)
        s.rect(bx + zw, by + bh - zh, bw - 2 * zw, zh - pad, ZONE["down"][0], "none", rx=10)
        s.rect(bx + pad, by + zh * 0.55, zw - 2 * pad, bh - zh * 1.1, ZONE["left"][0], "none", rx=10)
        s.rect(bx + bw - zw + pad, by + zh * 0.55, zw - 2 * pad, bh - zh * 1.1, ZONE["right"][0], "none", rx=10)
        s.text(bx + zw + 10, by + pad + 13, ZONE["up"][1], 12, SUB, anchor="start")
        s.text(bx + bw - zw - 10, by + bh - pad - 13, ZONE["down"][1], 12, SUB, anchor="end")
        s.text(bx + zw / 2, by + zh * 0.55 + 16, ZONE["left"][1], 12, SUB)
        s.text(bx + bw - zw / 2, by + zh * 0.55 + 16, ZONE["right"][1], 12, SUB)

    def spread(n, a, b):
        if n == 1:
            return [(a + b) / 2]
        step = (b - a) / (n - 1)
        return [a + i * step for i in range(n)]

    targets = []
    zw = bw * 0.27
    zh = bh * 0.27
    for x, item in zip(spread(len(up), cx - bw * 0.2, cx + bw * 0.2), up):
        targets.append((x, by + zh * 0.62, item, "up"))
    dy = by + bh - zh * (0.80 if grand else 0.6)
    for x, item in zip(spread(len(down), cx - bw * 0.22, cx + bw * 0.22), down):
        targets.append((x, dy, item, "down"))
    cw = card_w(center[0], center=True)
    for y, item in zip(spread(len(left), cy - bh * 0.17, cy + bh * 0.2), left):
        w = card_w(item[0])
        targets.append((min(bx + zw / 2, cx - cw / 2 - 28 - w / 2), y, item, "left"))
    for y, item in zip(spread(len(right), cy - bh * 0.17, cy + bh * 0.2), right):
        w = card_w(item[0])
        targets.append((max(bx + bw - zw / 2, cx + cw / 2 + 28 + w / 2), y, item, "right"))
    for x, y, item, side in targets:
        if side == "up":
            s.line(cx, cy - 29, x, y + 20)
        elif side == "down":
            s.line(cx, cy + 29, x, y - 20)
        elif side == "left":
            s.line(cx - cw / 2, cy, x + card_w(item[0]) / 2, y)
        else:
            s.line(cx + cw / 2, cy, x - card_w(item[0]) / 2, y)
    downs = [t for t in targets if t[3] == "down"]
    if grand:
        for i, kids in grand.items():
            x, y = downs[i][0], downs[i][1]
            for gx, kid in zip(spread(len(kids), x - 46 * (len(kids) - 1), x + 46 * (len(kids) - 1)), kids):
                s.line(x, y + 20, gx, y + 50, dash=False)
                card(s, gx, y + 64, kid[0], "", *kid[2:], small=True)
    for x, y, item, side in targets:
        name, kind, *rest = item
        card(s, x, y, name, kind, *rest)
    if siblings:
        x = bx + bw - 16
        for item in reversed(siblings):
            w = tw(item[0], 12) + 16
            x -= w
            s.rect(x, by + 14, w, 22, "#ffffff", "#c3c8d0", rx=6)
            s.text(x + w / 2, by + 25, item[0], 12, SUB)
            x -= 6
        s.text(x - 4, by + 25, "兄弟(同じ親の下):", 11, SUB, anchor="end")
    card(s, cx, cy, center[0], center[1] if len(center) > 1 else "", center=True)


# ---- 1枚ずつ -------------------------------------------------------------

def fig_screen():
    s = Svg(960, 600, "#ffffff")
    # 上のツールバー
    s.rect(14, 14, 932, 50, "#f4f5f7", "#d6dae1", rx=10)
    s.rect(30, 24, 240, 30, "#ffffff", "#c3c8d0", rx=6)
    s.text(44, 39, "🔍 Search (F4)", 13, SUB, anchor="start")
    s.text(300, 39, "◀  ▶", 16, INK)
    s.rect(338, 24, 34, 30, "#ffffff", "#c3c8d0", rx=6)
    s.text(355, 39, "⇕", 16, INK)
    s.rect(382, 24, 34, 30, "#ffffff", "#c3c8d0", rx=6)
    s.text(399, 39, "⧩", 15, INK)
    s.text(805, 39, "👣", 15, INK)
    s.text(845, 39, "🔎", 14, INK)
    s.text(885, 39, "⛶", 16, INK)
    s.badge(150, 76, 1)
    s.badge(300, 76, 2)
    s.badge(355, 76, 3)
    s.badge(399, 76, 4)
    s.badge(805, 76, 5)
    s.badge(885, 76, 6)
    compass(
        s,
        ("A案 クランプ式", "設計案"),
        up=[("樹脂カバーを量産する", "目的")],
        down=[("電池ユニット", "設計案"), ("マグネット取付", "設計案")],
        left=[("電池が3年もつ", "価値の仮説"), ("10分で後付けできる", "価値の仮説")],
        right=[("ヒケで外観不良", "イシュー", 1), ("磁力が足りない", "イシュー", 3)],
        siblings=[("B案 ねじ止め式",)],
        box=(14, 92, 932, 494),
    )
    s.save("01_画面の全体.svg", "K-Plex の画面の全体(イメージ)")


def fig_compass():
    s = Svg(900, 520, "#ffffff")
    cx, cy = 450, 260
    card(s, cx, cy, "見ているノート", center=True)
    items = [
        (cx, 70, "上 = 親", "parent(目的・上の案・上の仮説)"),
        (cx, 450, "下 = 子", "parent でこのノートを指すもの・parts"),
        (150, cy, "左 = 目論見・味方", "価値仮説 / friend / previous"),
        (750, cy, "右 = 不安材料・反対", "脅かす / challenger / 次に生まれたもの"),
    ]
    for x, y, head, sub in items:
        w = max(tw(sub, 13), tw(head, 18)) + 40
        fill = {"上": "#eef3fb", "下": "#eef7f1", "左": "#f1f7ec", "右": "#fdf0ee"}[head[0]]
        s.rect(x - w / 2, y - 38, w, 76, fill, "#c9ced6", rx=12)
        s.text(x, y - 12, head, 18, INK, weight="bold")
        s.text(x, y + 16, sub, 13, SUB)
    s.line(cx, cy - 30, cx, 110, "#2f6fde", 2, arrow=True)
    s.line(cx, cy + 30, cx, 410, "#2f6fde", 2, arrow=True)
    s.line(cx - 95, cy, 300, cy, "#2f6fde", 2, arrow=True)
    s.line(cx + 95, cy, 600, cy, "#2f6fde", 2, arrow=True)
    s.save("02_上下左右の意味.svg", "上下左右の意味")


def fig_open():
    s = Svg(1160, 340, "#ffffff")
    # 1. ノート
    s.badge(30, 30, 1)
    s.text(50, 30, "ノートを開いて Ctrl+G", 15, INK, anchor="start", weight="bold")
    s.rect(24, 54, 270, 250, "#ffffff", "#c3c8d0", rx=10)
    s.text(40, 80, "A案 クランプ式", 17, INK, anchor="start", weight="bold")
    for i, t in enumerate(["## この案の中身", "クランプで挟んで固定する", "## 価値の仮説を実現できるか", "[[電池が3年もつ]]"]):
        s.text(40, 112 + i * 26, t, 13, "#7a3fbf" if "[[" in t else SUB, anchor="start")
    x = 70
    x += s.key(x, 260, "Ctrl") + 6
    s.text(x + 4, 260, "+", 15, INK)
    s.key(x + 16, 260, "G")
    s.line(300, 180, 345, 180, "#2f6fde", 2.5, arrow=True)
    # 2. K-Plex
    s.badge(380, 30, 2)
    s.text(400, 30, "そのノートが真ん中に出る", 15, INK, anchor="start", weight="bold")
    compass(
        s,
        ("A案 クランプ式",),
        up=[("目的", "")],
        down=[("電池", ""), ("取付", "")],
        left=[("仮説", "")],
        right=[("イシュー", "", 1)],
        box=(360, 50, 440, 270),
        zones=False,
    )
    s.line(800, 180, 845, 180, "#2f6fde", 2.5, arrow=True)
    # 3. クリック
    s.badge(870, 30, 3)
    s.text(890, 30, "赤いカードを1回クリック", 15, INK, anchor="start", weight="bold")
    s.text(890, 56, "→ そのカードが真ん中に移る", 13, SUB, anchor="start")
    compass(
        s,
        ("イシュー",),
        down=[("タスク", "")],
        right=[("A案", "")],
        box=(860, 70, 260, 250),
        zones=False,
    )
    s.save("03_開く.svg", "開いて中心を移す")


def fig_colors():
    s = Svg(900, 250, "#ffffff")
    s.text(30, 30, "イシューの色 = priority(同期プログラムが書く)", 15, INK, anchor="start", weight="bold")
    for i, (p, t) in enumerate([(1, "1 最優先"), (2, "2 次に"), (3, "3 手が空いたら"), (4, "4 保留")]):
        x = 110 + i * 170
        card(s, x, 90, "ヒケで外観不良", "", p)
        s.text(x, 128, t, 13, SUB)
    s.text(30, 175, "終わったもの(解消・中止・不採用・外れた)は灰色の点線", 15, INK, anchor="start", weight="bold")
    card(s, 110, 215, "ヒケで外観不良", "", None, True)
    card(s, 280, 215, "B案 ねじ止め式", "", None, True)
    s.text(380, 215, "← 消えずに薄く残る。経緯をたどれる", 13, SUB, anchor="start")
    s.save("04_色と点線.svg", "カードの色と点線")


def fig_link():
    s = Svg(1080, 400, "#ffffff")
    s.badge(30, 30, 1)
    s.text(50, 30, "本文の [[ ]] の上で右クリック", 15, INK, anchor="start", weight="bold")
    s.rect(24, 54, 300, 200, "#ffffff", "#c3c8d0", rx=10)
    s.text(40, 80, "A案 クランプ式", 17, INK, anchor="start", weight="bold")
    s.text(40, 112, "## 価値の仮説を実現できるか", 13, SUB, anchor="start")
    s.rect(38, 128, 150, 26, "#efe6fb", "none", rx=4)
    s.text(46, 141, "[[電池が3年もつ]]", 13, "#7a3fbf", anchor="start")
    # メニュー
    s.rect(150, 150, 190, 92, "#ffffff", "#8f97a3", rx=8)
    s.rect(156, 158, 178, 26, "#e7efff", "none", rx=5)
    s.text(166, 171, "関係としてつなぐ", 14, INK, anchor="start", weight="bold")
    s.text(166, 199, "反論としてつなぐ", 14, INK, anchor="start")
    s.text(166, 225, "ノードにする …", 13, SUB, anchor="start")
    s.line(345, 170, 390, 170, "#2f6fde", 2.5, arrow=True)
    # 属性欄
    s.badge(410, 30, 2)
    s.text(430, 30, "属性欄に入る(本文のリンクは残る)", 15, INK, anchor="start", weight="bold")
    s.rect(400, 54, 250, 150, "#fbfbfc", "#c3c8d0", rx=10)
    rows = [("type", "設計案"), ("parent", "樹脂カバーを量産する"), ("価値仮説", "電池が3年もつ")]
    for i, (k, v) in enumerate(rows):
        y = 84 + i * 36
        if k == "価値仮説":
            s.rect(408, y - 15, 234, 30, "#e7efff", "none", rx=5)
        s.text(416, y, k, 13, SUB, anchor="start")
        s.text(500, y, v, 13, INK, anchor="start")
    s.line(655, 130, 700, 130, "#2f6fde", 2.5, arrow=True)
    # K-Plex
    s.badge(745, 30, 3)
    s.text(765, 30, "K-Plex の左に出る", 15, INK, anchor="start", weight="bold")
    compass(s, ("A案",), left=[("電池が3年もつ", "")], box=(730, 50, 330, 170), zones=False)
    # 下の表
    s.rect(24, 280, 1032, 104, "#f7f8fa", "#e1e4ea", rx=10)
    s.text(44, 300, "どの欄に入るか(右クリックで自動で決まる)", 14, INK, anchor="start", weight="bold")
    tbl = [
        ("関係としてつなぐ", "設計案 → 価値の仮説", "価値仮説", "左"),
        ("関係としてつなぐ", "それ以外(ノード同士など)", "friend", "左"),
        ("反論としてつなぐ", "覆す事実・反例", "challenger", "右"),
    ]
    for i, (a, b, c, d) in enumerate(tbl):
        y = 326 + i * 22
        s.text(44, y, a, 13, INK, anchor="start")
        s.text(210, y, b, 13, SUB, anchor="start")
        s.text(470, y, "→ 属性 " + c, 13, INK, anchor="start")
        s.text(680, y, "→ K-Plex の" + d, 13, INK, anchor="start", weight="bold")
    s.save("05_つなぐ.svg", "右クリックでつなぐ")


def fig_auto():
    s = Svg(960, 300, "#ffffff")
    s.text(30, 30, "キーで作ると、つながりは自動で入る(右クリック不要)", 15, INK, anchor="start", weight="bold")
    rows = [
        ("Ctrl+I", "設計案の中で行をイシューに", "イシューの 脅かす = その設計案", "設計案の右に出る"),
        ("Ctrl+U", "仮説の中で行を設計案に", "設計案の 価値仮説 = その仮説", "設計案の左に出る"),
        ("Ctrl+T", "イシューの中で行をタスクに", "タスクの parent = そのイシュー", "イシューの下に出る"),
        ("Ctrl+I", "タスクの「リスクはどう変わったか」で", "新イシューの previous = そのタスク", "新イシューの左に出る"),
        ("Ctrl+H", "仮説の中で行を仮説に", "下の仮説の parent = その仮説", "仮説の下に出る"),
    ]
    for i, (k, a, b, c) in enumerate(rows):
        y = 70 + i * 46
        s.rect(24, y - 19, 912, 38, "#f7f8fa" if i % 2 == 0 else "#ffffff", "none", rx=6)
        s.key(36, y, k, 13)
        s.text(130, y, a, 13, INK, anchor="start")
        s.text(420, y, b, 13, SUB, anchor="start")
        s.text(720, y, c, 13, INK, anchor="start", weight="bold")
    s.save("06_キーで作るとつながる.svg", "キーで作ったときのつながり")


def fig_view_purpose():
    s = Svg(900, 460)
    compass(
        s,
        ("樹脂カバーを量産する", "目的"),
        down=[
            ("電池が3年もつ", "価値の仮説"),
            ("10分で後付け", "価値の仮説"),
            ("A案 クランプ式", "設計案"),
            ("B案 ねじ止め式", "設計案"),
        ],
    )
    s.save("10_目的を中心に.svg", "目的を中心にした見え方")


def fig_view_design():
    s = Svg(900, 500)
    compass(
        s,
        ("A案 クランプ式", "成果物候補"),
        up=[("樹脂カバーを量産する", "目的")],
        down=[("電池ユニット", "部分の案"), ("マグネット取付", "部分の案")],
        left=[("電池が3年もつ", "価値の仮説"), ("10分で後付け", "価値の仮説")],
        right=[("ヒケで外観不良", "イシュー", 1), ("爪が割れる", "イシュー", 2), ("色むら", "イシュー", None, True)],
        siblings=[("B案 ねじ止め式",), ("C案 接着",)],
    )
    s.save("11_設計案を中心に.svg", "設計案を中心にした見え方")


def fig_view_hyp():
    s = Svg(900, 470)
    compass(
        s,
        ("電池が3年もつ", "価値の仮説"),
        up=[("樹脂カバーを量産する", "目的")],
        down=[("待機電流 10µA 以下", "価値の仮説"), ("送信は1日4回で足りる", "価値の仮説")],
        left=[("電池ユニット", "設計案")],
        right=[("寒冷地で容量が半分", "反論"), ("電池の調達が不安定", "イシュー", 2)],
    )
    s.save("12_仮説を中心に.svg", "仮説を中心にした見え方")


def fig_view_issue():
    s = Svg(900, 470)
    compass(
        s,
        ("ヒケで外観不良", "イシュー"),
        down=[("保圧を変えて試作", "タスク"), ("肉厚を均す設計", "タスク")],
        left=[("ゲート位置を変える", "タスク(生んだもと)")],
        right=[("A案 クランプ式", "脅かす相手(設計案)")],
    )
    s.save("13_イシューを中心に.svg", "イシューを中心にした見え方")


def fig_view_node():
    s = Svg(900, 440)
    compass(
        s,
        ("電池ユニット", "ノード"),
        up=[("センサー端末", "ノード")],
        down=[("電池セル", "ノード"), ("ホルダー", "ノード"), ("端子", "ノード")],
        left=[("待機電流", "ノード(関係)")],
    )
    s.save("14_ノードを中心に.svg", "ノードを中心にした見え方")


def fig_expanded():
    s = Svg(960, 590)
    s.rect(14, 14, 932, 44, "#f4f5f7", "#d6dae1", rx=10)
    s.text(34, 36, "ツールバー", 12, SUB, anchor="start")
    s.rect(300, 21, 40, 30, "#e7efff", "#2f6fde", rx=6, sw=2)
    s.text(320, 36, "⇕", 16, "#2f6fde", weight="bold")
    s.text(352, 36, "← Expanded view(押すたびに 1段 ⇄ 2段)", 13, INK, anchor="start", weight="bold")
    compass(
        s,
        ("A案 クランプ式", "成果物候補"),
        up=[("樹脂カバーを量産する", "目的")],
        down=[("電池ユニット", "部分の案"), ("マグネット取付", "部分の案")],
        left=[("電池が3年もつ", "")],
        right=[("ヒケで外観不良", "", 1)],
        box=(14, 64, 932, 490),
        grand={0: [("セル選定", ""), ("ホルダー", "")], 1: [("磁石の種類", ""), ("位置決め", "")]},
    )
    s.text(480, 570, "小さいカード = 子の子(孫)。1段だけ増える", 13, "#2f6fde", weight="bold")
    s.save("20_拡張表示.svg", "Compass の拡張表示")


def fig_mindmap():
    s = Svg(960, 470)
    s.text(30, 30, "Mind Map: 子の木を、右へ何段でも開く", 15, INK, anchor="start", weight="bold")

    def node(x, y, label, kind="", fold=None, root=False):
        w = tw(label, 14) + 24
        if root:
            s.rect(x, y - 22, w + 10, 44, "#1f3a5f", "#1f3a5f", rx=10)
            s.text(x + (w + 10) / 2, y, label, 15, "#fff", weight="bold")
            w += 10
        else:
            s.rect(x, y - 17, w, 34, "#ffffff", "#8f97a3", rx=8)
            s.text(x + w / 2, y, label, 14)
        if kind:
            s.text(x + w / 2, y - 26 if not root else y - 32, kind, 11, SUB)
        if fold:
            s.add(f'<circle cx="{x + w + 12}" cy="{y}" r="9" fill="#ffffff" stroke="#2f6fde" stroke-width="1.6"/>')
            s.text(x + w + 12, y + 0.5, fold, 14, "#2f6fde", weight="bold")
        return x + w

    def link(x1, y1, x2, y2):
        mx = (x1 + x2) / 2
        s.add(f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" fill="none" stroke="{LINE}" stroke-width="1.5"/>')

    r = node(30, 240, "樹脂カバーを量産する", "目的(根)", root=True)
    lv1 = [(110, "電池が3年もつ", "−"), (240, "A案 クランプ式", "−"), (380, "B案 ねじ止め式", "+")]
    ends = []
    for y, t, f in lv1:
        link(r, 240, 270, y)
        ends.append(node(270, y, t, "", f))
    lv2 = [
        (0, 70, "待機電流 10µA 以下", None),
        (0, 150, "送信は1日4回", None),
        (1, 210, "電池ユニット", "−"),
        (1, 290, "マグネット取付", "+"),
    ]
    l2ends = {}
    for i, y, t, f in lv2:
        link(ends[i] + 22, lv1[i][0], 500, y)
        l2ends[t] = (node(500, y, t, "", f), y)
    for y, t in [(185, "セル選定"), (235, "ホルダー")]:
        e, yy = l2ends["電池ユニット"]
        link(e + 22, yy, 720, y)
        node(720, y, t)
    s.text(300, 440, "＋ = まだ閉じている(押すと1段開く)   − = 開いている(押すと閉じる)", 13, "#2f6fde", weight="bold")
    s.save("21_マインドマップ.svg", "Mind Map で多段に開く")


def fig_switch_view():
    s = Svg(960, 300)
    s.badge(30, 30, 1)
    s.text(50, 30, "ツールバーの漏斗(Views and lenses)を押す", 15, INK, anchor="start", weight="bold")
    s.rect(30, 56, 300, 44, "#f4f5f7", "#d6dae1", rx=10)
    s.rect(200, 63, 34, 30, "#e7efff", "#2f6fde", rx=6, sw=2)
    s.text(217, 78, "⧩", 15, "#2f6fde", weight="bold")
    s.rect(160, 110, 230, 150, "#ffffff", "#8f97a3", rx=8)
    s.text(176, 132, "Views", 13, SUB, anchor="start")
    s.text(176, 162, "● Compass(ふだん)", 14, INK, anchor="start")
    s.rect(168, 178, 214, 30, "#e7efff", "none", rx=5)
    s.text(176, 193, "○ Mind Map(多段)", 14, INK, anchor="start", weight="bold")
    s.text(176, 224, "○ Facets(使わない)", 14, SUB, anchor="start")
    s.line(400, 190, 450, 190, "#2f6fde", 2.5, arrow=True)
    s.badge(480, 30, 2)
    s.text(500, 30, "開きたいカードの ＋ を押す / 右クリック", 15, INK, anchor="start", weight="bold")
    s.rect(470, 56, 470, 210, "#fbfbfc", "#d6dae1", rx=10)
    items = [
        ("＋ / −(カードの右の丸)", "その枝を1段開く・閉じる"),
        ("右クリック → Expand branch", "同じ(Alt+Enter でも)"),
        ("Alt+. → Expand one generation", "見えている枝をまとめて1段開く"),
        ("右クリック → Use as map root", "そのカードを根にして描き直す"),
        ("Alt+. → Collapse one generation", "いちばん深い段を閉じる"),
    ]
    for i, (a, b) in enumerate(items):
        y = 84 + i * 38
        s.text(486, y, a, 13, INK, anchor="start", weight="bold")
        s.text(486, y + 17, b, 12, SUB, anchor="start")
    s.save("22_表示の切り替え.svg", "Compass と Mind Map の切り替え")


def fig_back():
    s = Svg(960, 300)
    s.text(30, 30, "たどった道を戻る", 15, INK, anchor="start", weight="bold")
    path = ["目的", "A案", "電池ユニット", "電池切れ"]
    x = 40
    pos = []
    for i, t in enumerate(path):
        _, _, w, _ = card(s, x + (tw(t, 15) + 24) / 2, 90, t, "", 1 if t == "電池切れ" else None)
        pos.append(x)
        x += w + 60
        if i < len(path) - 1:
            s.line(x - 56, 90, x - 6, 90, "#2f6fde", 2, arrow=True)
            s.text(x - 31, 70, "クリック", 11, SUB)
    s.rect(30, 140, 430, 140, "#f7f8fa", "#e1e4ea", rx=10)
    s.text(46, 162, "キー(K-Plex の画面を押してから)", 13, INK, anchor="start", weight="bold")
    xx = 46
    xx += s.key(xx, 196, "Backspace", 13)
    s.text(xx + 10, 196, "1つ前の中心へ戻る", 13, INK, anchor="start")
    xx = 46
    xx += s.key(xx, 236, "Shift", 13) + 4
    s.text(xx + 6, 236, "+", 13)
    xx += s.key(xx + 16, 236, "Backspace", 13) + 16
    s.text(xx + 10, 236, "進む", 13, INK, anchor="start")
    s.rect(490, 140, 440, 140, "#f7f8fa", "#e1e4ea", rx=10)
    s.text(506, 162, "足あと(右上の 👣 Footprints)", 13, INK, anchor="start", weight="bold")
    for i, t in enumerate(["電池切れ", "電池ユニット", "A案", "目的"]):
        s.text(520, 192 + i * 22, f"{i + 1}. {t}", 13, INK if i else "#2f6fde", anchor="start")
    s.text(700, 214, "← 押すとそこへ飛ぶ", 13, SUB, anchor="start")
    s.text(700, 236, "Alt+H でも一覧が出る", 13, SUB, anchor="start")
    s.save("23_戻る.svg", "たどった道を戻る")


def fig_make():
    s = Svg(1180, 340)
    s.badge(30, 30, 1)
    s.text(50, 30, "K-Plex で中心を決めて Ctrl+Shift+N", 15, INK, anchor="start", weight="bold")
    compass(s, ("ヒケで外観不良",), right=[("A案", "")], box=(20, 50, 330, 220), zones=False)
    x = 60
    for i, k in enumerate(["Ctrl", "Shift", "N"]):
        x += s.key(x, 300, k, 13) + 4
        if i < 2:
            s.text(x + 4, 300, "+", 13)
            x += 14
    s.line(390, 160, 430, 160, "#2f6fde", 2.5, arrow=True)
    s.badge(460, 30, 2)
    s.text(480, 30, "種類を選んで、名前を打つ", 15, INK, anchor="start", weight="bold")
    s.rect(450, 56, 250, 170, "#ffffff", "#8f97a3", rx=8)
    for i, t in enumerate(["タスク(リスクを下げる仕事)", "イシュー(心配なこと)", "設計案", "仮説"]):
        y = 82 + i * 36
        if i == 0:
            s.rect(456, y - 15, 238, 30, "#e7efff", "none", rx=5)
        s.text(466, y, t, 13, INK, anchor="start", weight="bold" if i == 0 else "normal")
    s.text(575, 250, "中心に合うものが上に出る", 12, SUB)
    s.line(710, 160, 750, 160, "#2f6fde", 2.5, arrow=True)
    s.badge(780, 30, 3)
    s.text(800, 30, "できたノートが K-Plex に出る", 15, INK, anchor="start", weight="bold")
    compass(
        s, ("ヒケで外観不良",), down=[("保圧を変えて試作", "")], right=[("A案", "")], box=(760, 50, 400, 260), zones=False
    )
    s.save("30_見ながら作る.svg", "K-Plex を見ながら作る")


def main():
    for f in [
        fig_screen,
        fig_compass,
        fig_open,
        fig_colors,
        fig_link,
        fig_auto,
        fig_view_purpose,
        fig_view_design,
        fig_view_hyp,
        fig_view_issue,
        fig_view_node,
        fig_expanded,
        fig_mindmap,
        fig_switch_view,
        fig_back,
        fig_make,
    ]:
        f()
    print(f"{OUT} に書きました")


if __name__ == "__main__":
    main()
