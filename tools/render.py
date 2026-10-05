"""描画：図（SVG）、本文、版、鍵、見せる相手の表示"""
import sys, os, re, json, sqlite3, html, base64, datetime, subprocess, hashlib, functools, yaml, markdown
sys.path.insert(0, os.path.dirname(__file__))
from kv import ROOT, SRV, DB, reg, parse_drawing, embedded_files, LINK_RE, hash_of, can_see, read_note, split_fm
from core import *
from access import *

# ---- 共通の図・画像は1回だけページに入れ、各ページからは参照する（軽量化） ----
ASSETS = {}
def asset(html_):
    k = hashlib.sha1(html_.encode()).hexdigest()[:10]; ASSETS[k] = html_
    return f'<x-a k="{k}"></x-a>'


def scope_html(notes, n, frame=None, viewer='staff'):
    """資料の公開範囲：鍵＋開示先、一般社員（社内）から見えるか"""
    tags = json.loads(n['access']); tgt = n['id'] + (frame or '')
    aud = sorted({a for g in approved_grants(notes) for a in g.get('audience', [])
                  if tgt in (g.get('approved_targets') or []) or n['id'] in (g.get('approved_targets') or [])})
    seen = can_see(viewer, tags) or bool(granted(viewer, notes, tgt))
    cur = ' / '.join(tags) + (f' ＋公開 {" / ".join(aud)}' if aud else '')
    label = n['title'] + (f' {frame}' if frame else '')
    r_ = reg()
    if seen: lv, cls = '社内公開', 's-open'
    elif any(r_['tags'][t].get('hide_title') for t in tags): lv, cls = 'NDA', 's-nda'
    else: lv, cls = 'チーム限定', 's-shut'
    return (f'<button type="button" class="scope {cls}" data-st="{esc(tgt)}" data-sl="{esc(label)}" data-sb="{esc(cur)}" data-sg="{1 if aud else 0}" '
            f'data-base="{esc(json.dumps(tags, ensure_ascii=False))}" data-aud="{esc(json.dumps(aud, ensure_ascii=False))}" '
            f'aria-label="見せる相手：{esc(cur)}。押すと変更" title="見せる相手：{esc(cur)}（押すと変更）">{lv}</button>')

def lock_html(access, label='アクセス権なし', title=None, tid=''):
    """タイトル（フレームは名称）と鍵マークを表示。押すと必要な鍵と相談先を出す"""
    r = reg(); a = json.loads(access) if isinstance(access, str) else access
    if any(r['tags'][t].get('hide') for t in a): return ''
    if title is not None and any(r['tags'][t].get('hide_title') for t in a): title = '（タイトル非公開）'
    tl = f'<span class="lkt">{esc(title)}</span>' if title else ''
    who = []
    for t in a:
        tg = r['tags'][t]; w = f"{r['users'].get(tg['owner'])}" + (f"（代理 {r['users'].get(tg.get('deputy'))}）" if tg.get('deputy') else '')
        if w not in who: who.append(w)
    return (f'<button type="button" class="lockbtn" data-lk-id="{esc(tid)}" data-lk-label="{esc(label)}" data-lk-tags="{esc(" / ".join(a))}" data-lk-who="{esc("、".join(who))}" '
            f'aria-label="{esc(label)}。押すと開示の相談先を表示">🔒</button>{tl}')

_AT = {}
def at_version(n, ver):
    key = (n['id'], ver)
    if key not in _AT: _AT[key] = _at_version(n, ver)
    return _AT[key]

def _at_version(n, ver):
    """版を固定した引用：指定コミット時点のノート本文を返す"""
    if not ver or ver == n['commit_']: return n
    bare = os.path.join(SRV, n['vault'] + '.git')
    r = subprocess.run(['git', f'--git-dir={bare}', 'show', f'{ver}:{n["path"]}'], capture_output=True, text=True)
    if r.returncode: return n
    from kv import split_fm
    m = dict(n); m['body'] = split_fm(r.stdout)[1]; return m

def frames_of(n):
    d = parse_drawing(n['body'])
    els = [e for e in d['elements'] if not e.get('isDeleted')]
    fr = [e for e in els if e['type'] == 'frame']
    fr.sort(key=lambda e: (e.get('customData') or {}).get('kvFrame', ''))
    return fr, els

def svg_frame(n, frame, els, user, notes, pad=10, mark=None):
    x0, y0, w, h = frame['x'], frame['y'], frame['width'], frame['height']
    files = embedded_files(n['body']); hmap = by_hash(notes)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0-pad} {y0-pad} {w+2*pad} {h+2*pad}" class="frame-svg">',
           f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="#fff" stroke="#9aa3ad" stroke-width="1"/>']
    for e in els:
        if e.get('frameId') != frame['id']: continue
        sc = e.get('strokeColor', '#1e1e1e'); bg = e.get('backgroundColor', 'transparent')
        bg = 'none' if bg == 'transparent' else bg; sw = e.get('strokeWidth', 1.5)
        X, Y, W, H = e['x'], e['y'], e.get('width', 0), e.get('height', 0)
        t = e['type']
        if e.get('opacity', 100) == 0: continue
        if e.get('strokeStyle') == 'dashed': sw = f'{sw}" stroke-dasharray="5 3'
        if t == 'rectangle':
            out.append(f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" rx="4" fill="{bg}" stroke="{sc}" stroke-width="{sw}"/>')
        elif t == 'diamond':
            out.append(f'<path d="M{X+W/2},{Y}L{X+W},{Y+H/2}L{X+W/2},{Y+H}L{X},{Y+H/2}Z" fill="{bg}" stroke="{sc}" stroke-width="{sw}"/>')
        elif t == 'ellipse':
            out.append(f'<ellipse cx="{X+W/2}" cy="{Y+H/2}" rx="{W/2}" ry="{H/2}" fill="{bg}" stroke="{sc}" stroke-width="{sw}"/>')
        elif t in ('line', 'arrow'):
            pts = ' '.join(f'{X+p[0]},{Y+p[1]}' for p in e['points'])
            mk = ' marker-end="url(#ah)"' if t == 'arrow' else ''
            out.append(f'<polyline points="{pts}" fill="none" stroke="{sc}" stroke-width="{sw}"{mk}/>')
        elif t == 'text':
            fs = e.get('fontSize', 20); al = e.get('textAlign', 'left')
            tx, ta = (X + W, 'end') if al == 'right' else (X + W / 2, 'middle') if al == 'center' else (X, 'start')
            for i, line in enumerate(str(e.get('text', '')).split('\n')):
                out.append(f'<text x="{tx}" y="{Y+fs*(i+1)}" text-anchor="{ta}" font-size="{fs}" fill="{sc}" font-family="BIZ UDPGothic, sans-serif">{esc(line)}</text>')
        elif t == 'image':
            fn = files.get(e.get('fileId'))
            side = hmap.get(hash_of(fn or ''))
            if side and (can_see(user, side['access']) or granted(user, notes, side['id'])):
                p = os.path.join(os.path.dirname(work_path(side)), json.loads(side['fm'])['file'])
                mime = 'image/png' if p.endswith('.png') else 'image/jpeg' if p.endswith(('.jpg', '.jpeg')) else 'image/svg+xml'
                b = base64.b64encode(open(p, 'rb').read()).decode()
                out.append(f'<image x="{X}" y="{Y}" width="{W}" height="{H}" href="data:{mime};base64,{b}"/>')
            else:
                out.append(f'<rect x="{X}" y="{Y}" width="{W}" height="{H}" fill="#eceff3" stroke="#9aa3ad"/>'
                           f'<text x="{X+W/2}" y="{Y+H/2}" text-anchor="middle" font-size="18" fill="#56606b">🔒 アクセス権なし</text>')
    out.insert(1, '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0L10,5L0,10z" fill="#1e1e1e"/></marker></defs>')
    if mark:
        out.append(f'<text x="{x0+w-12}" y="{y0+h-12}" text-anchor="end" font-size="16" fill="#1f6f8b" opacity=".55">{esc(mark)}</text>')
    out.append('</svg>')
    return asset(''.join(out))

# ---------- Markdown → HTML（リンク解決・権限） ----------
LOCKS = []
def thumb_html(n, notes):
    """コメントの画像：一覧は小さい画像。押すと大きい画像（ASSETSに1回だけ）を表示"""
    hm = by_hash(notes); out = []
    for tgt in re.findall(r'^!\[\[([^\]]+)\]\]$', n['body'], re.M):
        tn = hm.get(hash_of(tgt))
        if not tn or tn['type'] != 'attachment': continue
        fm = json.loads(tn['fm']); p = os.path.join(os.path.dirname(work_path(tn)), fm['file'])
        if not p.lower().endswith(('.png', '.jpg', '.jpeg')): continue
        tb, tm = web_image(p, 240, 0, 70)
        fb, fmime = web_image(p)
        full = asset(f'<img alt="{esc(fm["title"])}" src="data:{fmime};base64,{fb}">')   # 本文の表示と同じ画像（重複させない）
        k = re.search(r'k="([^"]+)"', full).group(1)
        out.append(f'<button type="button" class="thumb" data-full="{k}" aria-label="{esc(fm["title"])}を拡大">{asset(f'<img alt="" src="data:{tm};base64,{tb}">')}</button>')
    return ''.join(out)

def web_image(p, maxpx=1000, limit=300_000, q=70):
    """閲覧用の画像。大きい写真は縮小して載せる（原本はvaultに残る）"""
    raw = open(p, 'rb').read(); mime = 'image/png' if p.endswith('.png') else 'image/jpeg'
    if len(raw) > limit:
        from PIL import Image, ImageOps; import io
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB'); im.thumbnail((maxpx, maxpx))
        buf = io.BytesIO(); im.save(buf, 'JPEG', quality=q); raw, mime = buf.getvalue(), 'image/jpeg'
    return base64.b64encode(raw).decode(), mime
def render_body(n, user, notes):
    hmap = by_hash(notes)
    def rep(m):
        bang, tgt, fr, ver, alias = m.groups()
        if ':' in tgt:
            typ, val = tgt.split(':', 1)
            if typ == 'part': return f'<a class="chip" href="#part-{esc(val)}">品番 {esc(val)}</a>'
            return f'<span class="chip">{esc(tgt)}</span>'
        tn = hmap.get(hash_of(tgt))
        if not tn: return '<span class="lock">🔒 リンク先なし</span>'
        if not can_see(user, tn['access']) and granted(user, notes, tn['id']) and not bang:
            return f'<a href="#n-{tn["id"]}">{esc(alias.lstrip("|") if alias else tn["title"])}</a>'
        if not can_see(user, tn['access']):
            if bang and has_drawing(tn) and fr:
                gv = granted(user, notes, tn['id'] + fr)
                if gv:
                    tv = at_version(tn, gv); frs, els = frames_of(tv); r_ = reg()
                    f = next((f for f in frs if (f.get('customData') or {}).get('kvFrame') == fr.lstrip('#')), None)
                    if f: return (f'<figure class="cite granted">{svg_frame(tv, f, els, user, notes, mark="社内公開 " + r_["users"].get(user, user))}'
                                  f'<figcaption>{esc(tn["title"])} {fr} {esc(f.get("name",""))} {upd_html(tn, gv, fr.lstrip("#"))}</figcaption></figure>')
            LOCKS.append(tn['access'])
            ttl = tn['title']
            if bang and has_drawing(tn) and fr:
                frs_, _ = frames_of(tn); f_ = next((f for f in frs_ if (f.get('customData') or {}).get('kvFrame') == fr.lstrip('#')), None)
                ttl = (f_ or {}).get('name') or ttl
            return lock_html(tn['access'], 'アクセス権のない資料' if bang else 'アクセス権なし', ttl, tn['id'] + (fr if bang and fr else ''))
        if bang:
            if tn['type'] == 'attachment':
                fm = json.loads(tn['fm']); p = os.path.join(os.path.dirname(work_path(tn)), fm['file'])
                if p.endswith(('.png', '.jpg', '.jpeg')):
                    b, mime = web_image(p)
                    sb = f'<div class="scopebar">{scope_html(notes, tn)}</div>' if is_mgr(user) else ''
                    img = f'<img alt="{esc(fm["title"])}" src="data:{mime};base64,{b}">'
                    return f'<figure>{sb}{asset(img)}<figcaption>{esc(fm["title"])}</figcaption></figure>'
                return f'<span class="chip">添付 {esc(fm["file"])}</span>'
            if has_drawing(tn):
                tv = at_version(tn, ver.lstrip('@') if ver else None)
                frs, els = frames_of(tv)
                want = fr.lstrip('#') if fr else None
                pin = ''
                cur = ' ' + upd_html(tn, ver.lstrip('@') if ver else None, None)
                parts = []
                for f in frs:
                    fid = (f.get('customData') or {}).get('kvFrame')
                    if want and fid != want: continue
                    sb = f'<div class="scopebar">{scope_html(notes, tn, "#" + fid)}</div>' if is_mgr(user) else ''
                    cur = ' ' + upd_html(tn, ver.lstrip('@') if ver else None, fid)
                    parts.append(f'<figure class="cite">{sb}{svg_frame(tv, f, els, user, notes)}<figcaption>引用: <a href="#n-{tn["id"]}">{esc(tn["title"])}</a> #{fid} {esc(f.get("name",""))}{pin}{cur}</figcaption></figure>')
                return ''.join(parts)
        return f'<a href="#n-{tn["id"]}">{esc(alias.lstrip("|") if alias else tn["title"])}</a>'
    text = LINK_RE.sub(rep, n['body'])
    # やること（チェックボックス）を読める形に。task:: は工程タスクの札に
    text = re.sub(r'^(\s*)- \[[xX]\] ', r'\1- ☑ ', text, flags=re.M); text = re.sub(r'^(\s*)- \[ \] ', r'\1- ☐ ', text, flags=re.M)
    text = re.sub(r'^(\s*)- \[-\] (.*)$', r'\1- <s>\2</s>（中止）', text, flags=re.M)
    text = re.sub(r'\[task:: [0-9]{6}-[a-z0-9]{5}#([TM]\d+)\]', r'<span class="tg">工程 \1</span>', text)
    return markdown.markdown(text, extensions=['tables'])

def ver_info(n, upto=None):
    return _ver_info(n['vault'], n['path'], upto)

@functools.lru_cache(maxsize=None)
def _ver_info(vault, path, upto):
    n = {'vault': vault, 'path': path}
    bare = os.path.join(SRV, n['vault'] + '.git')
    r = subprocess.run(['git', f'--git-dir={bare}', 'log', '-1', '--date=format:%Y-%m-%d %H:%M', '--format=%h|%an|%ad', upto or 'main', '--', n['path']],
                       capture_output=True, text=True).stdout.strip()
    h, who, at = (r.split('|') + ['', '', ''])[:3]
    return {'hash': h, 'who': who, 'at': at}

def frame_sig(n, ver, fid):
    """フレームの中身（要素）だけを比較するための署名"""
    tv = at_version(n, ver); frs, els = frames_of(tv)
    f = next((f for f in frs if (f.get('customData') or {}).get('kvFrame') == fid), None)
    if not f: return None
    return json.dumps(sorted((json.dumps({k: v for k, v in e.items() if k not in ('id', 'frameId')}, sort_keys=True) for e in els if e.get('frameId') == f['id'])))

def upd_html(n, granted_ver=None, fid=None):
    shown = ver_info(n, granted_ver); latest = ver_info(n) if granted_ver else shown
    newer = latest['hash'] != shown['hash']
    if newer and fid:   # フレームは、そのフレームの中身が変わった時だけ＋
        newer = frame_sig(n, granted_ver, fid) != frame_sig(n, n['commit_'], fid)
    users = reg()['users']; nm = lambda u: users.get(u, u)
    return (f'<button type="button" class="upd" data-h="{esc(shown["hash"])}" data-w="{esc(nm(shown["who"]))}" data-a="{esc(shown["at"])}" '
            + (f'data-lh="{esc(latest["hash"])}" data-lw="{esc(nm(latest["who"]))}" data-la="{esc(latest["at"])}" ' if newer else '')
            + f'aria-label="更新 {esc(shown["at"])}{"。新しい版あり" if newer else ""}。押すと版の情報を表示">{esc(shown["at"])}{"<sup class=plus>＋</sup>" if newer else ""}</button>')

# ---------- 報告の親子関係 ----------
def children(c, notes, nid, depth=2):
    hm = by_hash(notes); out = []
    def walk(i, d):
        for row in c.execute('select dst,kind from links where src=?', (i,)):
            ch = hm.get(row['dst'])
            if not ch or ch['type'] == 'attachment' or ch['id'] == nid or ch['id'] in [x[0] for x in out]: continue
            out.append((ch['id'], row['kind'], d))
            if d < depth: walk(ch['id'], d + 1)
    walk(nid, 1); return out

def parents(c, notes, nid):
    return [n for n in notes.values() if n['type'] == 'report' and nid in [x[0] for x in children(c, notes, n['id'])]]

