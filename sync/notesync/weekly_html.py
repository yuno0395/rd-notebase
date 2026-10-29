"""週報の HTML(F-29)。管理者がブラウザで開いて読む1ファイル。

Markdown と Excel に分けていたものを1つにまとめた(Yu 2026-10-25)。外のファイルやネットを読まない
(CSS と並べ替えの小さなスクリプトは中に入れる)。表は見出しを押すと並べ替え、行が多い表は絞り込める。
報告フォルダの直下には、全プロジェクトの週報への目次「週報の一覧.html」を置く。
"""

from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

INDEX_NAME = "週報の一覧.html"
WEEK_FILE = re.compile(r"^(\d{4})-W(\d{2})\.html$")
FILTER_ROWS = 6  # これ以上の行がある表に絞り込み欄をつける

CSS = """
:root{--bg:#fff;--fg:#1f2328;--muted:#59636e;--line:#d1d9e0;--head:#f6f8fa;--card:#fff;
--good:#1a7f37;--warn:#9a6700;--bad:#cf222e;--accent:#0969da;--warnbg:#fff8c5}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--line:#3d444d;
--head:#151b23;--card:#0d1117;--good:#3fb950;--warn:#d29922;--bad:#f85149;--accent:#4493f8;--warnbg:#2e2a1a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 "Yu Gothic UI","Meiryo",system-ui,sans-serif}
main{max-width:1040px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px}
h2{font-size:17px;margin:36px 0 4px;padding-top:8px;border-top:1px solid var(--line)}
.sub,.lead{color:var(--muted);font-size:13px;margin:0 0 12px}
.cards{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}
.card{flex:1 1 200px;border:1px solid var(--line);border-radius:8px;padding:12px 14px;background:var(--card)}
.card .k{color:var(--muted);font-size:12px}
.card .v{font-size:15px;margin-top:2px;word-break:break-word}
.card .big{font-size:34px;font-weight:700;line-height:1.2}
.good{color:var(--good)}.warn{color:var(--warn)}.bad{color:var(--bad)}
.note{padding:8px 12px;border-radius:6px;background:var(--head);margin:8px 0}
.note.warn{background:var(--warnbg);color:var(--fg);border-left:4px solid var(--warn)}
nav{border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:16px 0}
nav ol{margin:0;padding-left:20px;columns:2;column-gap:24px}
nav li{break-inside:avoid}
nav a{color:var(--accent);text-decoration:none}
.count{display:inline-block;min-width:22px;padding:0 6px;margin-left:6px;border-radius:10px;
font-size:12px;text-align:center;background:var(--head);color:var(--muted)}
.count.on{background:var(--warn);color:#fff}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:var(--head);cursor:pointer;user-select:none;white-space:nowrap}
th::after{content:" ↕";color:var(--muted);font-size:11px}
th.asc::after{content:" ▲"}th.desc::after{content:" ▼"}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.empty{color:var(--muted)}
input.filter{width:100%;max-width:320px;padding:6px 8px;margin:4px 0 8px;border:1px solid var(--line);
border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}
ul.weeks{padding-left:20px}
footer{margin-top:48px;color:var(--muted);font-size:12px}
.figs{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,480px),1fr));gap:12px;margin:12px 0}
.fig{border:1px solid var(--line);border-radius:8px;padding:8px;background:var(--card)}
.fig svg{width:100%;height:auto;display:block}
.kp text{font:12px "Yu Gothic UI","Meiryo",system-ui,sans-serif;fill:var(--fg)}
.kp .zone{font-size:11px;fill:var(--muted)}
.kp .ln{stroke:var(--line);stroke-width:1.2;fill:none}
.kp .c{fill:var(--card);stroke:var(--line)}
.kp .goal{fill:var(--head);stroke:var(--line)}
.kp .me{fill:var(--card);stroke:var(--accent);stroke-width:2.5}
.kp .hyp{fill:var(--card);stroke:var(--good);stroke-width:1.5}
.kp .off{opacity:.45;stroke-dasharray:4 3}
.kp text.dark{fill:#1f2328}.kp text.light{fill:#fff}
@media (max-width:640px){nav ol{columns:1}}
@media print{nav,input.filter{display:none}th::after{content:""}h2{break-after:avoid}}
"""

JS = """
document.querySelectorAll('table.sortable').forEach(function(t){
  t.querySelectorAll('th').forEach(function(th,i){
    th.addEventListener('click',function(){
      var asc=!th.classList.contains('asc');
      t.querySelectorAll('th').forEach(function(x){x.classList.remove('asc','desc')});
      th.classList.add(asc?'asc':'desc');
      var b=t.tBodies[0],rows=Array.prototype.slice.call(b.rows);
      function key(r){var s=r.cells[i].textContent.trim(),n=parseFloat(s.replace(/[^0-9.+-]/g,''));
        return /^[+-]?[0-9.]+/.test(s)&&!isNaN(n)?n:s}
      rows.sort(function(a,c){var x=key(a),y=key(c);
        var d=(typeof x==='number'&&typeof y==='number')?x-y:String(x).localeCompare(String(y),'ja');
        return asc?d:-d});
      rows.forEach(function(r){b.appendChild(r)});
    });
  });
});
document.querySelectorAll('input.filter').forEach(function(inp){
  var t=document.getElementById(inp.dataset.for);
  inp.addEventListener('input',function(){
    var q=inp.value.trim().toLowerCase();
    Array.prototype.forEach.call(t.tBodies[0].rows,function(r){
      r.style.display=!q||r.textContent.toLowerCase().indexOf(q)>=0?'':'none'});
  });
});
"""

NUM = re.compile(r"^[+-]?\d+(\.\d+)?(%.*| 日)?$")


# K-Plex のカードの色(priority。仕様書「全体像の把握(K-Plex)」と同じ)
PRIO_FILL = {1: ("#e5484d", "light"), 2: ("#f08c00", "light"), 3: ("#f8e46e", "dark"), 4: ("#c9cbd3", "dark")}
FIG_MAX = 6      # 1列に出すカードの数。多ければ「ほか n 件」


def short(s: str, n: int = 12) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def kplex_svg(f: dict) -> str:
    """成果物候補を中心にした K-Plex 風の図。上に目的、左に実現する仮説、右に脅かすイシュー、下に部分の案。

    イシューは priority で色をつけ、方針リスクは太字にする。解決したもの(低減済み・解消)と外れた仮説は薄く点線にする。"""
    W, CW, CH, GAP = 640, 176, 30, 8
    LX, MX, RX = 8, (W - CW) // 2, W - CW - 8

    def col(items):
        extra = max(0, len(items) - FIG_MAX)
        return items[:FIG_MAX], extra

    hyps, hx = col(f["hyps"])
    issues, ix = col(f["issues"])
    parts, px = col(f["parts"])
    side = max(len(hyps) + (1 if hx else 0), len(issues) + (1 if ix else 0), 1)
    top = 28
    side_h = side * (CH + GAP)
    mid_y = top + max(52, (side_h - CH) // 2)   # 目的の下。左右が長ければその真ん中
    parts_y = mid_y + CH + 28
    H = max(top + side_h, parts_y + len(parts) * (CH + GAP) + (18 if px else 0)) + 12
    out = [f'<svg class="kp" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="{escape(f["name"])} の構造">',
           f'<title>{escape(f["name"])}</title>',
           f'<text class="zone" x="{LX}" y="16">左 = 実現する価値の仮説</text>',
           f'<text class="zone" x="{RX + CW}" y="16" text-anchor="end">右 = 脅かすイシュー</text>']
    cx, cy = MX + CW // 2, mid_y + CH // 2

    def card(x, y, label, cls="c", text_cls="", bold=False, tip=""):
        weight = ' font-weight="700"' if bold else ""
        return (f'<g><title>{escape(tip or label)}</title><rect class="{cls}" x="{x}" y="{y}" width="{CW}" height="{CH}" rx="6"/>'
                f'<text class="{text_cls}" x="{x + CW / 2}" y="{y + CH / 2 + 4}" text-anchor="middle"{weight}>'
                f'{escape(short(label))}</text></g>')

    # 上: 目的
    gy = top - 6
    out.append(f'<path class="ln" d="M{cx} {gy + CH} L{cx} {mid_y}"/>')
    out.append(card(MX, gy, f["goal"] or "目的", "goal", tip=f"目的: {f['goal']}"))
    # 左右
    def side_cards(items, x, kind):
        y0 = top + 12 if side_h > CH else top
        for k, it in enumerate(items):
            y = y0 + k * (CH + GAP)
            ex = x + CW if kind == "hyp" else x
            out.append(f'<path class="ln" d="M{ex} {y + CH / 2} C{(ex + (MX if kind == "hyp" else MX + CW)) / 2} {y + CH / 2},'
                       f'{(ex + (MX if kind == "hyp" else MX + CW)) / 2} {cy},{MX if kind == "hyp" else MX + CW} {cy}"/>')
            if kind == "hyp":
                name, gone = it
                out.append(card(x, y, name, "hyp off" if gone else "hyp", tip=name + ("(外れた)" if gone else "")))
            else:
                name, p, solved, policy = it
                fill, tc = PRIO_FILL.get(p, ("", ""))
                cls = "c off" if solved else "c"
                rect = card(x, y, name, cls, tc if fill and not solved else "", bold=policy,
                            tip=f"{name}(priority {p or '-'}{'、方針' if policy else ''}{'、解決' if solved else ''})")
                if fill and not solved:
                    rect = rect.replace(f'class="{cls}"', f'class="{cls}" style="fill:{fill};stroke:{fill}"', 1)
                out.append(rect)
        return y0 + len(items) * (CH + GAP)
    if not hyps:
        out.append(f'<text class="zone" x="{LX + 4}" y="{top + 28}">まだつながっていない</text>')
    if not issues:
        out.append(f'<text class="zone" x="{RX + CW - 4}" y="{top + 28}" text-anchor="end">なし</text>')
    ly = side_cards(hyps, LX, "hyp")
    if hx:
        out.append(f'<text class="zone" x="{LX + 4}" y="{ly + 12}">ほか {hx} 件</text>')
    ry = side_cards(issues, RX, "issue")
    if ix:
        out.append(f'<text class="zone" x="{RX + CW - 4}" y="{ry + 12}" text-anchor="end">ほか {ix} 件</text>')
    # 下: 部分の案
    for k, name in enumerate(parts):
        y = parts_y + k * (CH + GAP)
        out.append(f'<path class="ln" d="M{cx - CW / 2 + 12} {mid_y + CH} L{cx - CW / 2 + 12} {y + CH / 2} L{MX + 24} {y + CH / 2}"/>')
        out.append(card(MX + 24, y, name, tip=f"部分の案: {name}").replace(f'width="{CW}"', f'width="{CW - 24}"', 1)
                   .replace(f'x="{MX + 24 + CW / 2}"', f'x="{MX + 24 + (CW - 24) / 2}"', 1))
    if px:
        out.append(f'<text class="zone" x="{MX + 28}" y="{parts_y + len(parts) * (CH + GAP) + 10}">ほか {px} 件</text>')
    # 中心: 成果物候補
    out.append(card(MX, mid_y, f["name"], "me", bold=True, tip=f"{f['name']}({f['status']})"))
    out.append("</svg>")
    return "".join(out)


def gantt_svg(plan, today=None) -> str:
    """工程表(F-53)。左にタスクの名前、右に日付の軸。上に節目、下にイシューごとのタスクの棒。"""
    from datetime import date as _date, timedelta
    today = today or _date.today()
    days = [d for b in plan.bars for d in (b.start, b.end)] + [d for _, p, f in plan.stones for d in (p, f) if d] + [today]
    lo, hi = min(days), max(days)
    lo = lo - timedelta(days=lo.weekday())            # 月曜から
    hi = hi + timedelta(days=7 - hi.weekday())
    span = max((hi - lo).days, 7)
    LW, W, RH, TOP = 240, 1000, 22, 34
    PW = W - LW - 12

    def x(d):
        return LW + PW * (d - lo).days / span

    rows = []   # (kind, data)
    if plan.stones:
        rows.append(("head", "マイルストーン"))
        rows += [("stone", s) for s in plan.stones]
    group = None
    for b in plan.bars:
        if b.group != group:
            group = b.group
            rows.append(("head", group))
        rows.append(("bar", b))
    H = TOP + len(rows) * RH + 12
    out = [f'<svg class="kp gt" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="工程表 {escape(plan.project)}"><title>工程表 {escape(plan.project)}</title>']
    # 軸: 週の線と、月の初めの日付
    d = lo
    while d <= hi:
        gx = x(d)
        out.append(f'<path class="ln" d="M{gx:.1f} {TOP - 6} L{gx:.1f} {H - 8}" style="opacity:.5"/>')
        if span <= 140 or d.day <= 7 or d == lo:   # 20週までは毎週、それより長ければ月の初めだけ
            out.append(f'<text class="zone" x="{gx + 2:.1f}" y="{TOP - 12}">{d.month}/{d.day}</text>')
        d += timedelta(days=7)
    tx = x(today)
    out.append(f'<path d="M{tx:.1f} {TOP - 6} L{tx:.1f} {H - 8}" style="stroke:var(--accent);stroke-width:1.5;stroke-dasharray:4 3"/>'
               f'<text class="zone" x="{tx + 3:.1f}" y="{H - 2}">今日</text>')
    for k, (kind, data) in enumerate(rows):
        y = TOP + k * RH
        if kind == "head":
            out.append(f'<text x="4" y="{y + 15}" font-weight="700">{escape(short(data, 18))}</text>')
            continue
        if kind == "stone":
            name, p, f = data
            out.append(f'<text x="14" y="{y + 15}">{escape(short(name, 17))}</text>')
            late = bool(p and f and f > p)
            for day, filled in ((p, False), (f, True)):
                if not day or (filled and day == p):
                    continue
                cx, cy = x(day), y + RH / 2
                color = "var(--bad)" if filled and late else "var(--fg)"
                fill = color if filled else "var(--card)"
                out.append(f'<g><title>{escape(name)} {"見込み" if filled else "計画"} {day.isoformat()}</title>'
                           f'<path d="M{cx:.1f} {cy - 7} L{cx + 7:.1f} {cy} L{cx:.1f} {cy + 7} L{cx - 7:.1f} {cy} Z" '
                           f'style="fill:{fill};stroke:{color};stroke-width:1.5"/></g>')
            continue
        b = data
        out.append(f'<text x="14" y="{y + 15}">{escape(short(b.name, 17))}</text>')
        x0, x1 = x(b.start), x(b.end + timedelta(days=1))
        style = {"完了": "fill:var(--good);opacity:.75", "中止": "fill:var(--muted);opacity:.5",
                 }.get(b.state, "fill:var(--accent)")
        dash = ";stroke:var(--fg);stroke-dasharray:3 2" if b.guessed else ""
        tip = f"{b.name}: {b.start.isoformat()} 〜 {b.end.isoformat()}({b.state}{'、推定' if b.guessed else ''})"
        out.append(f'<g><title>{escape(tip)}</title><rect x="{x0:.1f}" y="{y + 5}" width="{max(x1 - x0, 3):.1f}" '
                   f'height="{RH - 10}" rx="3" style="{style}{dash}"/></g>')
        if b.due and lo <= b.due <= hi:
            dx = x(b.due + timedelta(days=1))
            out.append(f'<g><title>期日 {b.due.isoformat()}</title><path d="M{dx:.1f} {y + 3} L{dx:.1f} {y + RH - 3}" '
                       f'style="stroke:var(--warn);stroke-width:2"/></g>')
    out.append("</svg>")
    return "".join(out)


def page(title: str, body: str) -> str:
    return ("<!doctype html>\n<html lang=\"ja\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(title)}</title><style>{CSS}</style></head>"
            f"<body><main>{body}</main><script>{JS}</script></body></html>\n")


def row_html(cells: list[str]) -> str:
    """表の1行。テストでも同じ形を探すので、ここだけで組み立てる。"""
    return "<tr>" + "".join(
        f"<td class=\"num\">{escape(c)}</td>" if NUM.match(c) else f"<td>{escape(c)}</td>" for c in cells) + "</tr>"


def render(report) -> str:
    sections: list[tuple[str, str, list]] = []  # (見出し, 説明, 中の部品)
    for b in report.blocks:
        if b[0] == "h2":
            sections.append((b[1], b[2], []))
        elif sections:
            sections[-1][2].append(b)

    out = [f"<h1>{escape(report.title)}</h1>",
           "<p class=\"sub\">知見同期プログラムが共有 vault のノートから自動で作りました。"
           "表の見出しを押すと並べ替えられます。</p>"]

    # 管理者に判断してほしいこと(書いてあるときだけ、いちばん上に)
    if getattr(report, "request", ""):
        out.append("<div class=\"cards\"><div class=\"card\"><div class=\"k\">管理者に判断してほしいこと</div>"
                   f"<div class=\"v\">{escape(report.request)}</div></div></div>")

    # 目次(該当の件数つき)
    toc = []
    for i, (h, _, parts) in enumerate(sections):
        n = sum(len(b[3]) for b in parts if b[0] == "table")
        has_table = any(b[0] == "table" for b in parts)
        badge = f"<span class=\"count{' on' if n and h not in OK_SECTIONS else ''}\">{n}</span>" if has_table else ""
        toc.append(f"<li><a href=\"#s{i}\">{escape(h)}</a>{badge}</li>")
    out.append("<nav><ol>" + "".join(toc) + "</ol></nav>")

    for i, (h, lead, parts) in enumerate(sections):
        out.append(f"<h2 id=\"s{i}\">{escape(h)}</h2>")
        if lead:
            out.append(f"<p class=\"lead\">{escape(lead)}</p>")
        for b in parts:
            if b[0] == "note":
                out.append(f"<p class=\"note{' warn' if b[2] else ''}\">{escape(b[1])}</p>")
            elif b[0] == "items":
                out.append("<ul>" + "".join(f"<li>{escape(k)}: {escape(v)}</li>" for k, v, _ in b[1]) + "</ul>")
            elif b[0] == "gantt":
                out.append(f"<div class=\"fig gantt\">{gantt_svg(b[1], b[2])}</div>")
            elif b[0] == "figs":
                out.append("<div class=\"figs\">" + "".join(f"<div class=\"fig\">{kplex_svg(f)}</div>" for f in b[1])
                           + "</div>")
            elif b[0] == "table":
                _, name, header, body, empty = b
                if not body:
                    out.append(f"<p class=\"empty\">{escape(empty)}</p>")
                    continue
                tid = f"t{i}"
                if len(body) >= FILTER_ROWS:
                    out.append(f"<input class=\"filter\" data-for=\"{tid}\" placeholder=\"絞り込み(名前・担当など)\">")
                out.append(f"<div class=\"wrap\"><table class=\"sortable\" id=\"{tid}\"><thead><tr>"
                           + "".join(f"<th>{escape(c)}</th>" for c in header)
                           + "</tr></thead><tbody>" + "".join(row_html(r) for r in body) + "</tbody></table></div>")
    out.append("<footer>週報は毎週月曜の朝に作られます。中身は各ノートの属性から集めたもので、"
               "判断してほしいことだけをプロジェクトのまとめ役が書いています。</footer>")
    return page(report.title, "".join(out))


# 件数があっても注意ではない節(目次の件数を目立たせない)
OK_SECTIONS = {"今週のトピック", "出荷準備度(目的ごと)", "開発の目処(成果物候補ごと)", "残っている候補の数", "マイルストーン", "工程表",
               "担当者ごとのタスク"}


def write_report(path: Path, report) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(report), encoding="utf-8")


def write_index(out_dir: Path, today: date) -> Path:
    """報告フォルダの直下に、全プロジェクトの週報への目次を書く。新しい週が上。"""
    items = []
    for d in sorted(p for p in out_dir.iterdir() if p.is_dir()) if out_dir.exists() else []:
        weeks = sorted((p.name for p in d.iterdir() if WEEK_FILE.match(p.name)), reverse=True)
        if not weeks:
            continue
        latest = weeks[0]
        rest = "".join(f"<li><a href=\"{escape(d.name)}/{escape(w)}\">{escape(w[:-5])}</a></li>" for w in weeks[1:9])
        items.append(f"<h2>{escape(d.name)}</h2><p><a href=\"{escape(d.name)}/{escape(latest)}\">"
                     f"最新: {escape(latest[:-5])}</a></p>"
                     + (f"<details><summary>前の週</summary><ul class=\"weeks\">{rest}</ul></details>" if rest else ""))
    body = (f"<h1>週報の一覧</h1><p class=\"sub\">{today.isoformat()} 更新。プロジェクトごとの最新の週報を開いてください。</p>"
            + ("".join(items) or "<p class=\"empty\">まだ週報がありません</p>"))
    path = out_dir / INDEX_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page("週報の一覧", body), encoding="utf-8")
    return path
