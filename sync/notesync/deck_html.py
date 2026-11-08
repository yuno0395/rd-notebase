"""F-59: 説明資料の HTML。ブラウザで開く1ファイル(週報と同じく外のファイル・ネットを読まない)。

16:9 の1枚ずつ。矢印キー・スペースでめくり、「一覧」で全部を縮めて並べる。印刷すると1枚1ページ。
図の SVG は <img> の data: で中に入れる(図の中のスクリプトや色の決まりが資料に混ざらないように)。
"""

from __future__ import annotations

import base64
import os
import re
from html import escape
from pathlib import Path

from .weekly_html import CSS as WEEKLY_CSS

# 週報の図(K-Plex の形・工程表)の色と線の決まりを使う
FIG_CSS = "\n".join(line for line in WEEKLY_CSS.splitlines()
                    if line.startswith((":root", "--", "@media (prefers-color-scheme")) or ".kp" in line)

CSS = """
*{box-sizing:border-box}
html,body{margin:0;background:#3d444d;color:var(--fg);font:16px/1.6 "Yu Gothic UI","Meiryo",system-ui,sans-serif}
.bar{position:fixed;top:0;left:0;right:0;display:flex;gap:8px;align-items:center;padding:6px 12px;
background:var(--head);border-bottom:1px solid var(--line);z-index:2;font-size:13px}
.bar button{font:inherit;padding:2px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);cursor:pointer}
.bar .pos{margin-left:auto;color:var(--muted)}
.deck{padding:48px 16px 16px}
.slide{width:min(100%,calc((100vh - 72px) * 16 / 9));aspect-ratio:16/9;margin:0 auto 16px;background:var(--bg);
border-radius:6px;padding:3.2% 4%;display:none;flex-direction:column;overflow:hidden;position:relative}
.slide.on{display:flex}
.grid .slide{display:flex;width:calc(33% - 12px);display:inline-flex;margin:6px;font-size:6px;cursor:pointer;vertical-align:top}
.chap{color:var(--muted);font-size:.8em;margin:0}
h1{font-size:2.6em;margin:auto 0 .3em;line-height:1.3}
h2{font-size:1.7em;margin:0 0 .4em;line-height:1.3}
.cover dl{display:grid;grid-template-columns:auto 1fr;gap:.2em 1em;margin:0 0 auto;font-size:1.1em}
.cover dt{color:var(--muted)}
.made{position:absolute;bottom:3%;left:4%;right:4%;color:var(--muted);font-size:.75em}
.body{display:flex;gap:3%;flex:1;min-height:0}
.pic{flex:0 0 46%;display:flex;align-items:center;justify-content:center;min-height:0}
.pic img{max-width:100%;max-height:100%;object-fit:contain;background:#fff;border-radius:4px}
.txt{flex:1;overflow:hidden;font-size:1.05em}
.txt h3{font-size:.85em;color:var(--muted);margin:.6em 0 .1em}
.txt h3:first-child{margin-top:0}
.txt p,.txt ul{margin:.1em 0}
.txt ul{padding-left:1.2em}
.empty{color:var(--muted)}
.foot{color:var(--muted);font-size:.72em;border-top:1px solid var(--line);padding-top:.4em;margin-top:.6em}
.faded{opacity:.55}
table{border-collapse:collapse;width:100%;font-size:.85em}
th,td{border:1px solid var(--line);padding:.25em .5em;text-align:left;vertical-align:top}
th{background:var(--head)}
.big{font-size:2.2em;font-weight:700;margin:auto 0;line-height:1.4}
.sum{display:grid;grid-template-columns:auto 1fr;gap:.5em 1.2em;font-size:1.25em;margin:auto 0}
.sum dt{color:var(--muted)}
.svg{flex:1;min-height:0;display:flex;align-items:center;justify-content:center}
.svg svg{max-width:100%;max-height:100%}
@media print{
 @page{size:A4 landscape;margin:0}
 html,body{background:#fff}
 .bar{display:none}.deck{padding:0}
 .slide{display:flex!important;width:100%;height:100vh;aspect-ratio:auto;margin:0;border-radius:0;break-after:page}
}
"""

JS = """
(function(){
var s=[].slice.call(document.querySelectorAll('.slide')),i=0,deck=document.querySelector('.deck'),pos=document.querySelector('.pos');
function show(k){i=Math.max(0,Math.min(s.length-1,k));s.forEach(function(x,j){x.classList.toggle('on',j===i)});
 pos.textContent=(i+1)+' / '+s.length;}
function grid(on){deck.classList.toggle('grid',on);document.getElementById('g').textContent=on?'1枚ずつ':'一覧';}
document.addEventListener('keydown',function(e){
 if(deck.classList.contains('grid')){if(e.key==='Escape')grid(false);return;}
 if(['ArrowRight','ArrowDown','PageDown',' ','Enter'].indexOf(e.key)>=0){show(i+1);e.preventDefault();}
 if(['ArrowLeft','ArrowUp','PageUp','Backspace'].indexOf(e.key)>=0){show(i-1);e.preventDefault();}
 if(e.key==='Home')show(0);if(e.key==='End')show(s.length-1);});
s.forEach(function(x,j){x.addEventListener('click',function(){if(deck.classList.contains('grid')){grid(false);show(j);}});});
document.getElementById('g').onclick=function(){grid(!deck.classList.contains('grid'));};
document.getElementById('p').onclick=function(){show(i-1)};document.getElementById('n').onclick=function(){show(i+1)};
show(0);
})();
"""


def md(text: str) -> str:
    """欄の文(Markdown のごく一部: 箇条書き・表・段落)を HTML に。"""
    out, table, items = [], [], []

    def flush():
        if items:
            out.append("<ul>" + "".join(f"<li>{escape(x)}</li>" for x in items) + "</ul>")
            items.clear()
        if table:
            rows = [r for r in table if not set("".join(r)) <= set("-: ")]
            if rows:
                head, body = rows[0], rows[1:]
                out.append("<table><tr>" + "".join(f"<th>{escape(c)}</th>" for c in head) + "</tr>" +
                           "".join("<tr>" + "".join(f"<td>{escape(c)}</td>" for c in r) + "</tr>" for r in body) +
                           "</table>")
            table.clear()

    for line in text.splitlines():
        t = line.strip()
        if t.startswith("|"):
            if items:
                flush()
            table.append([c.strip() for c in t.strip("|").split("|")])
            continue
        if table:
            flush()
        m = re.match(r"^(?:[-*+]|\d+\.)\s+(?:\[[ xX]\]\s+)?(.*)$", t)
        if m:
            items.append(m.group(1))
            continue
        flush()
        if t:
            out.append(f"<p>{escape(t)}</p>")
    flush()
    return "".join(out)


def image(svg: str) -> str:
    if not svg.strip():
        return ""
    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<div class="pic"><img alt="図" src="data:image/svg+xml;base64,{data}"></div>'


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return '<p class="empty">なし</p>'
    return ("<table><tr>" + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr>" +
            "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows) + "</table>")


def slide_html(s) -> str:
    cls = "slide" + (" faded" if s.faded else "") + (" cover" if s.kind == "cover" else "")
    chap = f'<p class="chap">{escape(s.chapter)}</p>' if s.chapter and s.chapter != s.title else ""
    if s.kind == "cover":
        dl = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in s.sections)
        return (f'<section class="{cls}"><h1>{escape(s.title)}</h1><dl>{dl}</dl>'
                '<p class="made">ノートから自動で作った資料です。直すときはノートを直して作り直します</p></section>')
    if s.kind == "summary":
        dl = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in s.sections)
        return f'<section class="{cls}"><h2>{escape(s.title)}</h2><dl class="sum">{dl}</dl></section>'
    if s.kind == "note":
        txt = "".join(f"<h3>{escape(h)}</h3>" + (md(v) if v.strip() else '<p class="empty">(まだ書いていません)</p>')
                      for h, v in s.sections)
        foot = f'<div class="foot">{escape(s.foot)}</div>' if s.foot else ""
        return (f'<section class="{cls}">{chap}<h2>{escape(s.title)}</h2>'
                f'<div class="body">{image(s.image)}<div class="txt">{txt}</div></div>{foot}</section>')
    if s.kind in ("table", "gaps"):
        return f'<section class="{cls}">{chap}<h2>{escape(s.title)}</h2><div class="txt">{table(s.headers, s.rows)}</div></section>'
    if s.kind == "figure":
        return f'<section class="{cls}">{chap}<h2>{escape(s.title)}</h2><div class="svg">{s.svg}</div></section>'
    # text
    body = f'<div class="big">{escape(s.big)}</div>' if s.big else ""
    for _, v in s.sections:
        body += f'<div class="txt">{md(v)}</div>'
    if not body:
        body = '<p class="empty">(まだ書いていません)</p>'
    return f'<section class="{cls}">{chap}<h2>{escape(s.title)}</h2>{body}</section>'


def render(deck) -> str:
    slides = "\n".join(slide_html(s) for s in deck.slides)
    return ("<!doctype html>\n<html lang=\"ja\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{escape(deck.title)}({escape(deck.story)})</title><style>{FIG_CSS}{CSS}</style></head><body>"
            '<div class="bar"><button id="p">◀</button><button id="n">▶</button><button id="g">一覧</button>'
            f'<span>{escape(deck.story)}: {escape(deck.title)}</span><span class="pos"></span></div>'
            f'<div class="deck">{slides}</div><script>{JS}</script></body></html>\n')


def write(path: Path, deck) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(render(deck), encoding="utf-8")
    os.replace(tmp, path)
