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
OK_SECTIONS = {"出荷準備度(目的ごと)", "開発の目処(成果物候補ごと)", "残っている候補の数", "マイルストーン", "担当者ごとのタスク"}


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
