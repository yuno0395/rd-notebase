"""案件ごとのアーカイブ（利用者の PC で動く。client/run.py の「archive」から呼ぶ）

  notebase.cmd archive P00001            案件 P00001 の依存のマップをブラウザで開き、ノート・添付ごとに
                                         「移す／写す／残す」を選んでからアーカイブする
  notebase.cmd archive <まとめノート>     起点のまとめノート（id か名前）を直接指定
  notebase.cmd archive 日誌 2             2年より前のデイリー・週ノートと、どこにも属さない古いメモ
  notebase.cmd archive P00001 --yes      マップを開かず、初期値のままアーカイブ（確認済みの時）
  notebase.cmd archive --undo <記録名>    取り消し（移したノートを vault に戻す）
  notebase.cmd archive --list            これまでのアーカイブ

起点（案件のまとめ＝type: project のノート、と project がその案件のノート）からリンクを全部たどる（他の案件のまとめも止めずに）。
初期値：
  移す  この案件だけのもの（vault から消し、アーカイブの置き場へ）
  写す  他の続いている案件のもの、残るノートから参照されているもの（vault に残し、案件完了時点の写しを置き場へ）
  残す  デイリー・週ノート（年ごとのルール「日誌」で扱う）
アーカイブの置き場：.rdnb/config.yml の archive_dir（無ければデータの置き場の アーカイブ/）の <人>/<案件>_<日付>/。
中は vault と同じ並びなので、そのフォルダを Obsidian で開けば読める。記録（記録.md・manifest.json）に元の場所・版・sha256 を残す。
vault には記録の写し（.rdnb/archives/）を残し、移したノートには _refs/アーカイブ/ にスタブを置く（残るノートのリンクが切れない）。
サーバの索引は、記録の版から移したノートを読み出して、検索・Web 閲覧・PDF に残す。
"""
import os, re, json, glob, shutil, hashlib, datetime, subprocess, threading, webbrowser, html
import kv

KEEP_TYPES = ('daily', 'weeknote')
ACT_JA = {'move': '移す', 'copy': '写す', 'keep': '残す'}
SKIP = ('_', '.', '90_templates/', '20_工程/')

def nfc(s): return kv.nfc(s)

def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

# ---------- vault を読む ----------
def load(vp):
    """vault のノート（id のあるもの）→ {id: {rel, fm, body, links:set(id), bin:rel|None}}"""
    notes, names = {}, {}
    for p in glob.glob(os.path.join(vp, '**', '*.md'), recursive=True):
        rel = os.path.relpath(p, vp).replace(os.sep, '/')
        if rel.startswith(SKIP): continue
        fm, body = kv.read_note(p)
        if not fm.get('id') or kv.is_pm(fm): continue
        i = str(fm['id']); b = None
        if fm.get('type') == 'attachment' and fm.get('store') != 'data' and kv.file_of(fm):
            bp = os.path.join(os.path.dirname(p), kv.file_of(fm))
            if os.path.exists(bp): b = os.path.relpath(bp, vp).replace(os.sep, '/')
        notes[i] = {'id': i, 'rel': rel, 'fm': fm, 'body': body, 'bin': b, 'links': set()}
        keys = [kv.link_key(rel), i] + [kv.link_key(a) for a in (fm.get('aliases') or []) if isinstance(a, str)]
        if fm.get('type') == 'attachment' and kv.file_of(fm): keys.append(kv.link_key(kv.file_of(fm)))
        for k in keys:
            if k: names.setdefault(nfc(k), i)
    for n in notes.values():
        tg = [m[1] for m in kv.LINK_RE.findall(n['body'])]
        for k in kv.REL:
            v = n['fm'].get(k) or []
            tg += [v] if isinstance(v, str) else [str(x) for x in v]
        for t in tg:
            d = names.get(nfc(kv.link_key(t) or ''))
            if d and d != n['id']: n['links'].add(d)
    return notes

def title(n): return kv.title_of(n['rel'], n['fm'])

def projects(reg):
    return reg.get('projects') or {}

def active(reg, pid):
    """続いている案件か（台帳にない案件は、念のため続いている扱い）"""
    p = projects(reg).get(pid)
    return not p or str(p.get('status', '')) not in ('完了', '中止', 'closed', 'done')

def find_root(notes, key, reg):
    """案件ID → その案件のまとめ（type: project）。id・名前 → そのノート。返り値 (起点の id か None, 案件ID)"""
    if key in projects(reg) or re.match(r'^P\d{5}$', key):
        roots = [n for n in notes.values() if n['fm'].get('type') == 'project' and n['fm'].get('project') == key]
        if len(roots) > 1: raise SystemExit(f'案件 {key} のまとめ（type: project）が {len(roots)} 件あります。まとめノートの id で指定してください：' + '、'.join(f"{title(n)}（{n['id']}）" for n in roots))
        return (roots[0]['id'] if roots else None), key
    hit = notes.get(key) or next((n for n in notes.values() if kv.link_key(n['rel']) == key or title(n) == key), None)
    if not hit:
        hits = [n for n in notes.values() if key in title(n)]
        if len(hits) != 1: raise SystemExit(f'「{key}」に合うノートが' + ('見つかりません' if not hits else f' {len(hits)} 件あります'))
        hit = hits[0]
    return hit['id'], hit['fm'].get('project') or ''

# ---------- 依存をたどって、初期値を決める ----------
def plan(vp, key, reg, today=None, years=None):
    notes = load(vp); today = today or datetime.date.today()
    inbound = {}
    for n in notes.values():
        for d in n['links']: inbound.setdefault(d, set()).add(n['id'])
    if years is not None:   # 日誌：古いデイリー・週ノートと、どこにも属さない古いメモ
        cut = today.replace(year=today.year - int(years))
        def old(n): return str(n['fm'].get('created') or n['fm'].get('updated') or '9999') < str(cut)
        seeds = [i for i, n in notes.items() if old(n) and (n['fm'].get('type') in KEEP_TYPES or
                 (not n['fm'].get('project') and n['fm'].get('type') not in ('attachment', 'project', 'grant') and not inbound.get(i)))]
        root, pid, follow = None, '', False
        name = f'日誌_{cut:%Y%m%d}より前'
    else:
        root, pid = find_root(notes, key, reg)
        seeds = ([root] if root else []) + sorted(i for i, n in notes.items() if pid and n['fm'].get('project') == pid and n['fm'].get('type') != 'project')
        if root is None and not seeds: raise SystemExit(f'案件 {key} のまとめノート（type: project）も、project が {key} のノートも見つかりません')
        follow = True; name = pid or kv.link_key(notes[root]['rel'])
    depth = {}; via = {}
    def walk(starts, d0):
        todo = [(s, d0) for s in starts]
        while todo:   # リンクを全部たどる（他の案件のまとめも止めずに）
            i, d = todo.pop(0)
            if i in depth and depth[i] <= d: continue
            depth[i] = d
            for j in sorted(notes[i]['links']):
                if follow or notes[j]['fm'].get('type') == 'attachment': todo.append((j, d + 1))
    if root: walk([root], 0)
    rest = [s for s in seeds if s not in depth]   # まとめからリンクされていないが、project がこの案件のもの
    for s in rest: via[s] = True
    walk(rest, 1 if root else 0)
    act, why = {}, {}
    for i in depth:
        fm = notes[i]['fm']; p = fm.get('project') or ''
        if i == root: act[i], why[i] = 'move', '起点のまとめ'
        elif years is not None: act[i], why[i] = 'move', '古い日誌・メモ' if fm.get('type') != 'attachment' else '貼られている'
        elif fm.get('type') in KEEP_TYPES: act[i], why[i] = 'keep', 'デイリー・週ノート（日誌のルールで扱う）'
        elif fm.get('type') == 'project': act[i], why[i] = 'copy', f'他の案件 {p} のまとめ'
        elif p and p != pid and active(reg, p): act[i], why[i] = 'copy', f'続いている案件 {p} のもの'
        else: act[i], why[i] = 'move', ('この案件だけ（まとめからリンクなし・project が同じ）' if via.get(i) else 'この案件だけ') if p == pid else 'たどった先（案件なし）'
    changed = True
    while changed:   # 残るノートから参照されているものは「写す」（移すとリンクが切れる）。デイリー・週ノートからの参照は数えない
        changed = False
        for i in list(act):
            if act[i] != 'move' or i == root: continue
            refs = [r for r in inbound.get(i, ()) if (r not in act or act[r] != 'move') and notes[r]['fm'].get('type') not in KEEP_TYPES]
            if refs:
                act[i] = 'copy'; why[i] = f'残るノート「{title(notes[refs[0]])}」から参照' + (f' ほか{len(refs) - 1}件' if len(refs) > 1 else ''); changed = True
    nodes = []
    for i, d in sorted(depth.items(), key=lambda x: (x[1], title(notes[x[0]]))):
        n = notes[i]; fm = n['fm']
        size = sum(os.path.getsize(os.path.join(vp, r)) for r in (n['rel'], n['bin']) if r and os.path.exists(os.path.join(vp, r)))
        nodes.append({'id': i, 'title': title(n), 'type': fm.get('type') or '', 'project': fm.get('project') or '', 'depth': d,
                      'act': act[i], 'why': why[i], 'rel': n['rel'], 'bin': n['bin'], 'size': size,
                      'links': sorted(j for j in n['links'] if j in depth), 'store': fm.get('store') or ''})
    return {'name': name, 'project': pid, 'root': root, 'nodes': nodes, 'date': str(today)}

# ---------- マップ（ブラウザで選ぶ） ----------
def map_html(pl):
    cols = {}
    for n in pl['nodes']: cols.setdefault(n['depth'], []).append(n)
    W, H, GX, GY = 230, 40, 90, 14; pos = {}
    for d, ns in cols.items():
        ns.sort(key=lambda n: ({'move': 0, 'copy': 1, 'keep': 2}[n['act']], n['type'] == 'attachment', n['title']))
        for k, n in enumerate(ns): pos[n['id']] = (20 + d * (W + GX), 50 + k * (H + GY))
    width = 40 + (max(cols) + 1) * (W + GX) if cols else 400
    height = 80 + max(len(v) for v in cols.values()) * (H + GY) if cols else 200
    pcol = {}
    pal = ['#1f6f8b', '#8b5a1f', '#5a1f8b', '#1f8b4c', '#8b1f3a', '#4c4c4c']
    for n in pl['nodes']:
        if n['project'] and n['project'] not in pcol: pcol[n['project']] = pal[len(pcol) % len(pal)]
    edges = []
    for n in pl['nodes']:
        x1, y1 = pos[n['id']]
        for j in n['links']:
            x2, y2 = pos[j]
            edges.append(f'<path d="M{x1 + W},{y1 + H / 2} C{x1 + W + 40},{y1 + H / 2} {x2 - 40},{y2 + H / 2} {x2},{y2 + H / 2}" class="e" data-s="{n["id"]}" data-d="{j}"/>')
    boxes = []
    for n in pl['nodes']:
        x, y = pos[n['id']]; pc = pcol.get(n['project'], '#9aa3ad')
        label = ('📎 ' if n['type'] == 'attachment' else '◆ ' if n['type'] == 'project' else '') + n['title']
        boxes.append(f'<g class="n" data-id="{n["id"]}" transform="translate({x},{y})"><title>{html.escape(n["title"])}\n{html.escape(n["why"])}</title>'
                     f'<rect width="{W}" height="{H}" rx="6" class="b"/><rect width="6" height="{H}" rx="2" fill="{pc}"/>'
                     f'<text x="14" y="17" class="t">{html.escape(label[:16] + ("…" if len(label) > 16 else ""))}</text>'
                     f'<text x="14" y="32" class="s">{html.escape((n["project"] or "案件なし") + " ・ " + (n["type"] or "未分類"))}</text>'
                     f'<text x="{W - 8}" y="32" text-anchor="end" class="a"></text></g>')
    legend = ''.join(f'<span class="pj"><i style="background:{c}"></i>{html.escape(p)}</span>' for p, c in pcol.items())
    data = json.dumps({n['id']: {'act': n['act'], 'title': n['title'], 'why': n['why'], 'size': n['size'], 'type': n['type']} for n in pl['nodes']}, ensure_ascii=False)
    head = f"アーカイブ：{html.escape(pl['name'])}" + (f"（起点 {html.escape(next(n['title'] for n in pl['nodes'] if n['id'] == pl['root']))}）" if pl['root'] else '')
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>アーカイブの選択</title>
<style>
:root{{--bg:#f6f7f9;--fg:#1d232a;--mut:#56606b;--line:#c5ccd4;--card:#fff;--mv:#c0392b;--cp:#b7791f;--kp:#7a8591}}
body{{margin:0;font:14px/1.5 system-ui,-apple-system,"Segoe UI","Hiragino Sans","Yu Gothic UI",sans-serif;background:var(--bg);color:var(--fg)}}
header{{padding:12px 16px;background:var(--card);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:10px;align-items:center}}
h1{{font-size:16px;margin:0 12px 0 0}} .sum b{{font-variant-numeric:tabular-nums}} .pj{{margin-right:10px;color:var(--mut)}} .pj i{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px}}
.key span{{display:inline-block;padding:1px 8px;border-radius:10px;color:#fff;margin-right:4px;font-size:12px}}
main{{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:0;height:calc(100vh - 62px)}}
#map{{overflow:auto;background:var(--bg)}} aside{{overflow:auto;background:var(--card);border-left:1px solid var(--line);padding:10px 12px}}
.e{{fill:none;stroke:#aab3bd;stroke-width:1.2}} .e.hot{{stroke:#1d232a;stroke-width:2}}
.n{{cursor:pointer}} .b{{fill:var(--card);stroke:var(--line);stroke-width:1.5}} .t{{font-size:12.5px;fill:var(--fg)}} .s{{font-size:11px;fill:var(--mut)}} .a{{font-size:11.5px;font-weight:700}}
.n.move .b{{stroke:var(--mv);stroke-width:2.2}} .n.copy .b{{stroke:var(--cp);stroke-width:2.2;stroke-dasharray:5 3}} .n.keep .b{{stroke:var(--kp)}} .n.keep{{opacity:.6}}
.n.move .a{{fill:var(--mv)}} .n.copy .a{{fill:var(--cp)}} .n.keep .a{{fill:var(--kp)}} .n.sel .b{{fill:#eef4fb}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}} td{{border-bottom:1px solid #eceff3;padding:4px 2px;vertical-align:top}} td.w{{color:var(--mut);font-size:11.5px}}
select{{font:inherit;font-size:12px}} button{{font:inherit;padding:6px 14px;border-radius:6px;border:1px solid #1d232a;background:#1d232a;color:#fff;cursor:pointer}}
button.sub{{background:#fff;color:#1d232a}} #msg{{white-space:pre-wrap;color:var(--mut)}}
@media (max-width:800px){{main{{grid-template-columns:1fr;height:auto}} #map{{height:60vh}}}}
</style></head><body>
<header><h1>{head}</h1><span class="sum">移す <b id="c-move">0</b>・写す <b id="c-copy">0</b>・残す <b id="c-keep">0</b>（移す {''}<b id="c-size">0</b> MB）</span>
<span class="key"><span style="background:var(--mv)">移す</span><span style="background:var(--cp)">写す</span><span style="background:var(--kp)">残す</span></span>{legend}
<span style="flex:1"></span><button class="sub" id="reset">初期値に戻す</button><button id="go">この内容でアーカイブ</button></header>
<main><div id="map"><svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">{''.join(edges)}{''.join(boxes)}</svg></div>
<aside><p style="margin:0 0 6px;color:var(--mut)">箱を押すと 移す→写す→残す と切り替わります。線は「左のノートが右をリンク・貼り付け」。左の色の帯は案件。</p>
<p id="msg"></p><table id="list"></table></aside></main>
<script>
const D = {data}, INIT = JSON.parse(JSON.stringify(D)), ORDER = ['move', 'copy', 'keep'], JA = {json.dumps(ACT_JA, ensure_ascii=False)};
function draw() {{
  const c = {{move: 0, copy: 0, keep: 0}}; let sz = 0;
  document.querySelectorAll('.n').forEach(g => {{ const d = D[g.dataset.id]; g.classList.remove('move', 'copy', 'keep'); g.classList.add(d.act); g.querySelector('.a').textContent = JA[d.act]; c[d.act]++; if (d.act === 'move') sz += d.size; }});
  for (const k in c) document.getElementById('c-' + k).textContent = c[k];
  document.getElementById('c-size').textContent = (sz / 1e6).toFixed(1);
  document.getElementById('list').innerHTML = Object.entries(D).map(([i, d]) => `<tr data-id="${{i}}"><td><select data-id="${{i}}">${{ORDER.map(a => `<option value="${{a}}" ${{a === d.act ? 'selected' : ''}}>${{JA[a]}}</option>`).join('')}}</select></td><td>${{d.type === 'attachment' ? '📎 ' : ''}}${{d.title.replace(/</g, '&lt;')}}<div class="w">${{d.why.replace(/</g, '&lt;')}}</div></td></tr>`).join('');
  document.querySelectorAll('#list select').forEach(s => s.onchange = () => {{ D[s.dataset.id].act = s.value; D[s.dataset.id].why = '手で選択'; draw(); }});
}}
document.querySelectorAll('.n').forEach(g => {{
  g.onclick = () => {{ const d = D[g.dataset.id]; d.act = ORDER[(ORDER.indexOf(d.act) + 1) % 3]; d.why = '手で選択'; draw(); }};
  g.onmouseenter = () => document.querySelectorAll(`.e[data-s="${{g.dataset.id}}"],.e[data-d="${{g.dataset.id}}"]`).forEach(e => e.classList.add('hot'));
  g.onmouseleave = () => document.querySelectorAll('.e.hot').forEach(e => e.classList.remove('hot'));
}});
document.getElementById('reset').onclick = () => {{ for (const i in D) Object.assign(D[i], INIT[i]); draw(); }};
document.getElementById('go').onclick = async () => {{
  const acts = Object.fromEntries(Object.entries(D).map(([i, d]) => [i, d.act]));
  const m = document.getElementById('msg'); m.textContent = 'アーカイブしています…';
  try {{ const r = await fetch('run', {{method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(acts)}}); m.textContent = await r.text(); document.getElementById('go').disabled = true; }}
  catch (e) {{ m.textContent = 'notebase に届きませんでした（コマンドの画面を閉じていませんか）：' + e; }}
}};
draw();
</script></body></html>"""

def choose(pl, out_html, open_it=True, timeout=1800):
    """マップをブラウザで開き、選んだ結果を受け取る（この PC の中だけの一時的な受け口 127.0.0.1）。
    返り値：({id: 扱い}, 結果をブラウザに返す関数)。時間切れは (None, None)"""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    page = map_html(pl).encode('utf-8')
    with open(out_html, 'wb') as f: f.write(page)
    box = {'acts': None, 'text': ''}; got, answered = threading.Event(), threading.Event()
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.end_headers(); self.wfile.write(page)
        def do_POST(self):
            n = int(self.headers.get('Content-Length') or 0)
            if got.is_set(): text = 'もう受け付けました'
            else:
                box['acts'] = json.loads(self.rfile.read(n) or b'{}'); got.set(); answered.wait(900); text = box['text']
            self.send_response(200); self.send_header('Content-Type', 'text/plain; charset=utf-8'); self.end_headers()
            self.wfile.write(text.encode('utf-8'))
    srv = ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('RDNB_ARCHIVE_PORT', '0'))), H)
    url = f'http://127.0.0.1:{srv.server_address[1]}/'
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f'マップを開きます：{url}（開かない時はこのアドレスをブラウザに貼る。選び終えたら「この内容でアーカイブ」）', flush=True)
    if open_it: webbrowser.open(url)
    if not got.wait(timeout): srv.shutdown(); return None, None
    def reply(text):
        box['text'] = text; answered.set(); threading.Timer(1.5, srv.shutdown).start()
    return box['acts'], reply

# ---------- 実行・取り消し ----------
def archive_dir(c, data_dir):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(c.get('archive_dir') or os.path.join(data_dir, 'アーカイブ'))))

def apply(vp, c, pl, acts, base_dir, git, today=None):
    """選んだ内容でアーカイブする → (記録名, 文)"""
    today = today or datetime.date.today(); user = c.get('user', '')
    nodes = {n['id']: n for n in pl['nodes']}
    for i, a in acts.items():
        if i in nodes and a in ACT_JA: nodes[i]['act'] = a
    sel = [n for n in nodes.values() if n['act'] in ('move', 'copy')]
    if not any(n['act'] == 'move' for n in sel) and not sel: return None, '移す・写すものがないので、何もしませんでした'
    name = f"{pl['name']}_{today:%Y%m%d}"; dest = os.path.join(base_dir, user, name); k = 1
    while os.path.exists(dest): k += 1; dest = os.path.join(base_dir, user, f'{name}_{k}')
    name = os.path.basename(dest)
    commit = git('rev-parse', 'HEAD')
    entries = []
    for n in sel:
        files = []
        for rel in (n['rel'], n['bin']):
            if not rel: continue
            src = os.path.join(vp, rel); dst = os.path.join(dest, 'vault', rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst)
            files.append({'path': rel, 'sha256': sha_file(src), 'size': os.path.getsize(src)})
        e = {'id': n['id'], 'act': n['act'], 'title': n['title'], 'type': n['type'], 'project': n['project'], 'why': n['why'], 'files': files}
        if n.get('store') == 'data':
            fm = kv.read_note(os.path.join(vp, n['rel']))[0]; e['data'] = {'path': fm.get('path'), 'sha256': fm.get('sha256')}
        entries.append(e)
    man = {'name': name, 'project': pl['project'], 'root': pl['root'], 'user': user, 'date': str(today), 'commit': commit,
           'place': dest, 'entries': entries, 'kept': [n['id'] for n in nodes.values() if n['act'] == 'keep']}
    os.makedirs(dest, exist_ok=True)
    json.dump(man, open(os.path.join(dest, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    open(os.path.join(dest, '記録.md'), 'w', encoding='utf-8').write(record_md(man))
    for e in entries:   # 移す：vault から消す
        if e['act'] != 'move': continue
        for f in e['files']:
            p = os.path.join(vp, f['path'])
            if os.path.exists(p): os.remove(p)
    write_stubs(vp, man)
    mp = os.path.join(vp, '.rdnb', 'archives', name + '.json'); os.makedirs(os.path.dirname(mp), exist_ok=True)
    json.dump(man, open(mp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    mv = sum(e['act'] == 'move' for e in entries); cp = sum(e['act'] == 'copy' for e in entries)
    git('add', '-A'); git('commit', '-q', '-m', f'アーカイブ: {name}（移す {mv}・写す {cp}）')
    return name, f'アーカイブしました：{name}（移す {mv} 件・写す {cp} 件）\n置き場：{dest}\nvault から消したノートは _refs/アーカイブ/ にスタブを置きました。取り消すには notebase.cmd archive --undo {name}'

def record_md(man):
    rows = ''.join(f"| {ACT_JA[e['act']]} | {e['title']} | `{e['id']}` | {e['type'] or '未分類'} | {e['project'] or '—'} | "
                   + '<br>'.join(f"`{f['path']}` `{f['sha256'][:16]}…`" for f in e['files'])
                   + (f"<br>データの置き場 `{e['data']['path']}`" if e.get('data') else '') + f" | {e['why']} |\n" for e in man['entries'])
    return (f"# アーカイブの記録：{man['name']}\n\n- 案件：{man['project'] or '—'}\n- 作った人：{man['user']}\n- 日付：{man['date']}\n"
            f"- 元の vault の版：`{man['commit']}`（この版に、移す前のノートがすべて残っている）\n"
            f"- 移す＝vault から消してここに置いた。写す＝vault に残したまま、この時点の写しをここに置いた\n"
            f"- sha256 は置いた時点の中身。差し替わっていないかは notebase.cmd archive --verify {man['name']} で照合できる\n\n"
            "| 扱い | 題名 | id | 種類 | 案件 | ファイル（sha256） | 理由 |\n|---|---|---|---|---|---|---|\n" + rows)

STUBS = os.path.join('_refs', 'アーカイブ')
def write_stubs(vp, man):
    """移したノートの名前でスタブを置く（残るノートの [[名前]] がそのまま開ける）"""
    d = os.path.join(vp, STUBS); os.makedirs(d, exist_ok=True); n = 0
    for e in man['entries']:
        if e['act'] != 'move' or e['type'] == 'attachment': continue
        rel = e['files'][0]['path']; p = os.path.join(d, os.path.basename(rel))
        place = os.path.join(man['place'], 'vault', rel)
        body = (f"> [!info] アーカイブ済み（{man['name']}・{man['date']}）\n> このノートは vault から移しました。本文はアーカイブの置き場か Web 閲覧で見られます。\n\n"
                f"- 置き場：[{os.path.basename(rel)}](<file:///{place.replace(os.sep, '/').lstrip('/')}>)\n- 元の版：`{man['commit'][:10]}`\n- 戻す：`notebase.cmd archive --undo {man['name']}`\n")
        kv.write_note(p, {'archived': man['name'], 'ref_id': e['id'], 'project': e['project']}, body); n += 1
    return n

def stubs_all(vp):
    """記録（.rdnb/archives/）からスタブを置き直す（別の PC・_refs を消した時）"""
    n = 0
    for mp in glob.glob(os.path.join(vp, '.rdnb', 'archives', '*.json')):
        man = json.load(open(mp, encoding='utf-8'))
        if not man.get('undone'): n += write_stubs(vp, man)
    return n

def undo(vp, name, git):
    mp = os.path.join(vp, '.rdnb', 'archives', name + '.json')
    if not os.path.exists(mp): raise SystemExit(f'アーカイブの記録 {name} が見つかりません（notebase.cmd archive --list で確認）')
    man = json.load(open(mp, encoding='utf-8'))
    paths = [f['path'] for e in man['entries'] if e['act'] == 'move' for f in e['files']]
    back = [p for p in paths if not os.path.exists(os.path.join(vp, p))]
    if back: git('checkout', man['commit'], '--', *back)
    for e in man['entries']:
        if e['act'] == 'move' and e['type'] != 'attachment':
            s = os.path.join(vp, STUBS, os.path.basename(e['files'][0]['path']))
            if os.path.exists(s): os.remove(s)
    os.remove(mp)
    rec = os.path.join(man['place'], '記録.md')
    if os.path.exists(rec):
        with open(rec, 'a', encoding='utf-8') as f: f.write(f"\n\n**{datetime.date.today()} に取り消しました**（ノートは vault に戻しました。このフォルダは消してかまいません）\n")
    git('add', '-A'); git('commit', '-q', '-m', f'アーカイブの取り消し: {name}（{len(back)} ファイルを戻す）')
    return f'取り消しました：{name}（{len(back)} ファイルを vault に戻しました）'

def listing(vp):
    out = []
    for mp in sorted(glob.glob(os.path.join(vp, '.rdnb', 'archives', '*.json'))):
        m = json.load(open(mp, encoding='utf-8'))
        out.append(f"{m['name']}  {m['date']}  移す {sum(e['act'] == 'move' for e in m['entries'])}・写す {sum(e['act'] == 'copy' for e in m['entries'])}  {m['place']}")
    return out or ['（アーカイブはまだありません）']

def verify(vp, name):
    m = json.load(open(os.path.join(vp, '.rdnb', 'archives', name + '.json'), encoding='utf-8')); bad = []; n = 0
    for e in m['entries']:
        for f in e['files']:
            p = os.path.join(m['place'], 'vault', f['path']); n += 1
            if not os.path.exists(p): bad.append(f"{f['path']}: 置き場にありません")
            elif sha_file(p) != f['sha256']: bad.append(f"{f['path']}: 中身が記録（sha256）と違います")
    return n, bad

def done_projects(vp, reg):
    """完了した案件で、まだアーカイブしていないもの（自分の vault にその案件のノートがある）"""
    have = set()
    for mp in glob.glob(os.path.join(vp, '.rdnb', 'archives', '*.json')):
        have.add(json.load(open(mp, encoding='utf-8')).get('project'))
    mine = {kv.read_note(p)[0].get('project') for p in glob.glob(os.path.join(vp, '10_notes', '**', '*.md'), recursive=True)}
    return [pid for pid, p in projects(reg).items() if str(p.get('status', '')) == '完了' and pid in mine and pid not in have]

# ---------- 入口（client/run.py から） ----------
def run(vp, c, args, say, git, ws, data_dir):
    reg = kv.reg()
    if not args or args[0] == '--list':
        for l in listing(vp): say(l)
        if not args: say('使い方：notebase.cmd archive <案件ID か まとめノート>（--yes で確認なし） / archive 日誌 <年> / archive --undo <記録名> / archive --list')
        return
    if args[0] == '--undo':
        if len(args) < 2: raise SystemExit('使い方：notebase.cmd archive --undo <記録名>（archive --list で確認）')
        return say(undo(vp, args[1], git))
    if args[0] == '--verify':
        n, bad = verify(vp, args[1])
        for b in bad: say('問題:', b)
        return say(f'照合：{n} ファイル' + ('、問題なし' if not bad else f'、問題 {len(bad)} 件'))
    yes = '--yes' in args; args = [a for a in args if a != '--yes']
    pl = plan(vp, args[1] if args[0] == '日誌' and len(args) > 1 else args[0], reg, years=(args[1] if len(args) > 1 else 2) if args[0] == '日誌' else None)
    say(f"アーカイブ候補：{pl['name']}　" + '・'.join(f"{ACT_JA[a]} {sum(n['act'] == a for n in pl['nodes'])}" for a in ACT_JA))
    base = archive_dir(c, data_dir)
    if yes:
        name, msg = apply(vp, c, pl, {}, base, git); return say(msg)
    html_path = os.path.join(ws, f"アーカイブ_{pl['name']}.html")
    acts, reply = choose(pl, html_path, open_it=os.environ.get('RDNB_NO_BROWSER') != '1')
    if acts is None: return say('マップで選ばれなかったので、アーカイブしていません')
    try:
        name, msg = apply(vp, c, pl, acts, base, git)
    except Exception as e:
        reply(f'アーカイブできませんでした：{e}'); raise
    reply(msg); say(msg)
    try: os.remove(html_path)
    except OSError: pass
