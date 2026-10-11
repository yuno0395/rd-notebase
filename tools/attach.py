"""添付の手入れ（利用者の PC で push の前に動く。client/run.py から呼ぶ）

  40_attachments/   ノートや図に貼る画像など（Git＋LFS）。1件ごとに説明の .md（type: attachment）を付ける
  50_data/          実験データなど重いもの。vault には説明の .md だけを置き、本体は「データの置き場」（vault の外。
                    .rdnb/config.yml の data_dir。クラウドの同期フォルダを指定する）に移す。Git には入れない

push のたびに次をする（何度実行しても同じ結果）：
  1. 説明の .md の file をリンク（file: "[[名前.png]]"）にそろえる → Obsidian で改名すると一緒に直る
  2. 50_data に置かれた本体と、40_attachments に置かれた大きすぎるファイル（台帳の limits.attach_max_bytes 超）を
     データの置き場へ移し、50_data に説明の .md を作る（貼ってあったリンクは説明の .md へのリンクに直す）
  3. 説明の .md が指す本体が見つからない時は、同じ中身（sha256）のファイルを探して付け直す（Obsidian の外で改名した時）
  4. 説明の .md のない本体：既にある添付と中身が同じなら、リンクをそちらに直して重複を消す。
     新しいものには説明の .md を作る（id・sha256・大きさ。持ち主・案件・鍵は貼ったノートから引き継ぐ）
  5. 新しく来た大きい画像（長辺が image_max_px 超）は、原寸をデータの置き場（原寸/）に残して、vault には縮小版を置く
"""
import os, re, glob, json, shutil, hashlib, secrets, datetime, unicodedata
import kv

ATT, DATA = '40_attachments', '50_data'
IMG = ('.png', '.jpg', '.jpeg', '.webp')
ALPH = kv.ALPH

def nfc(s): return unicodedata.normalize('NFC', s)

def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

class ShaCache:
    """sha256 の控え（大きさと更新時刻が同じなら計算し直さない）。.rdnb/cache/sha.json（Git に入れない）"""
    def __init__(self, path):
        self.path = path
        try: self.d = json.load(open(path, encoding='utf-8'))
        except (OSError, ValueError): self.d = {}
        self.dirty = False
    def __call__(self, p):
        st = os.stat(p); k = os.path.abspath(p); v = self.d.get(k)
        if v and v[0] == st.st_size and v[1] == int(st.st_mtime): return v[2]
        h = sha_file(p); self.d[k] = [st.st_size, int(st.st_mtime), h]; self.dirty = True
        return h
    def save(self):
        if self.dirty:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            json.dump(self.d, open(self.path, 'w', encoding='utf-8'))

def link(name): return f'[[{name}]]'

def free_name(folder, name):
    """folder に同じ名前があれば「名前 2.拡張子」…"""
    stem, ext = os.path.splitext(name); n = 1; out = name
    while os.path.exists(os.path.join(folder, out)):
        n += 1; out = f'{stem} {n}{ext}'
    return out

def sidecars(vp):
    """説明の .md（type: attachment）→ [{path, fm, body}]"""
    out = []
    for folder in (ATT, DATA):
        for p in glob.glob(os.path.join(vp, folder, '**', '*.md'), recursive=True):
            fm, body = kv.read_note(p)
            if fm.get('type') == 'attachment': out.append({'path': p, 'fm': fm, 'body': body})
    return out

def binaries(vp, folder):
    out = []
    for p in glob.glob(os.path.join(vp, folder, '**', '*'), recursive=True):
        b = os.path.basename(p)
        if os.path.isfile(p) and not b.endswith('.md') and b != '.gitkeep' and not b.startswith('.'): out.append(p)
    return sorted(out)

def used_ids(vp):
    return {kv.read_note(p)[0].get('id') for p in glob.glob(os.path.join(vp, '**', '*.md'), recursive=True)} - {None}

def new_id(day, used):
    while True:
        i = f"{day}-{''.join(secrets.choice(ALPH) for _ in range(5))}"
        if i not in used: used.add(i); return i

def notes_using(vp):
    """添付の名前 → それを貼っている（リンクしている）ノートの frontmatter の一覧（最初に見つけたもの順）"""
    out = {}
    for p in glob.glob(os.path.join(vp, '**', '*.md'), recursive=True):
        rel = os.path.relpath(p, vp).replace(os.sep, '/')
        if rel.startswith(('_', '.', '90_templates/', '20_工程/', ATT + '/', DATA + '/')): continue
        fm, body = kv.read_note(p)
        if not fm.get('id'): continue
        for name in re.findall(r'\[\[([^\]|#]+)', body):
            out.setdefault(nfc(os.path.basename(name.strip())), []).append(fm)
    return out

def shrink(p, maxpx):
    """画像の長辺が maxpx を超えていれば、同じ形式・同じ名前のまま縮める。縮めたら True"""
    if not maxpx or not p.lower().endswith(IMG): return False
    from PIL import Image, ImageOps
    with Image.open(p) as im:
        if max(im.size) <= maxpx: return False
        im = ImageOps.exif_transpose(im); im.thumbnail((maxpx, maxpx))
        fmt = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.webp': 'WEBP'}[os.path.splitext(p)[1].lower()]
        if fmt == 'JPEG' and im.mode not in ('RGB', 'L'): im = im.convert('RGB')
        tmp = p + '.tmp'
        im.save(tmp, fmt, **({'quality': 85} if fmt in ('JPEG', 'WEBP') else {'optimize': True}))
    os.replace(tmp, p); return True

def to_store(src, store, sub=''):
    """本体をデータの置き場に移す（同じ名前があれば番号を付ける）→ 置き場の中の相対パス"""
    d = os.path.join(store, sub); os.makedirs(d, exist_ok=True)
    name = free_name(d, os.path.basename(src)); shutil.move(src, os.path.join(d, name))
    return (os.path.join(sub, name) if sub else name).replace(os.sep, '/')

def file_url(p):
    return 'file:///' + os.path.abspath(p).replace(os.sep, '/').lstrip('/')

def data_body(fm, store):
    p = os.path.join(store, fm['path'])
    return (f"本体はデータの置き場（vault の外・Git に入らない）にあります：`{fm['path']}`\n\n"
            f"- [本体を開く](<{file_url(p)}>)\n- 大きさ {fm.get('size', 0) / 1e6:.1f} MB、sha256 `{fm['sha256'][:16]}…`（`notebase.cmd verify` で照合）\n")

def tend(vp, user, store, cache_path, max_bytes=20_000_000, maxpx=1920, today=None):
    """上の 1〜5 をする。返り値：画面とログに出す文の一覧"""
    today = today or datetime.date.today(); msgs = []
    sha = ShaCache(cache_path); used = None; using = None
    sides = sidecars(vp)

    # 1. file をリンクに（vault の中にある本体だけ。データの置き場のものは名前のまま）
    for s in sides:
        fm = s['fm']; f = kv.file_of(fm)
        if f and fm.get('store') != 'data' and fm.get('file') != link(f):
            fm['file'] = link(f); kv.write_note(s['path'], fm, s['body'])

    def make_side(folder, base, fm):
        nonlocal used
        d = os.path.join(vp, folder); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, free_name(d, os.path.splitext(base)[0] + '.md'))
        kv.write_note(p, fm, fm.pop('_body', '')); s = {'path': p, 'fm': fm, 'body': ''}; sides.append(s); return s

    def inherit(name):
        nonlocal using
        if using is None: using = notes_using(vp)
        src = (using.get(nfc(name)) or [{}])[0]
        return {'owner': src.get('owner') or user, 'project': src.get('project') or '', 'access': list(src.get('access') or [])}

    def ids():
        nonlocal used
        if used is None: used = used_ids(vp)
        return used

    moved_links = {}   # 貼ってあったリンクの付け替え {旧名: 新名}

    # 2. 50_data の本体・40_attachments の大きすぎるファイル → データの置き場
    big = [p for p in binaries(vp, ATT) if os.path.getsize(p) > max_bytes]
    for p in binaries(vp, DATA) + big:
        if not store:
            msgs.append(f'データの置き場（.rdnb/config.yml の data_dir）が未設定なので、{os.path.relpath(p, vp)} を移せません'); continue
        base = os.path.basename(p); h = sha(p); size = os.path.getsize(p)
        same = next((s for s in sides if s['fm'].get('store') == 'data' and s['fm'].get('sha256') == h), None)
        made = datetime.date.fromtimestamp(os.path.getmtime(p))
        if same:   # 同じ中身が置き場にある → 本体は捨てて、リンクだけ付け替える
            os.remove(p); moved_links[base] = os.path.basename(same['path'])[:-3]
            msgs.append(f'データ：{base} は既にある {os.path.basename(same["path"])[:-3]} と同じ中身なので、そちらを使います'); continue
        rel = to_store(p, store, user or '')
        fm = {'id': new_id(made.strftime('%y%m%d'), ids()), 'type': 'attachment', 'store': 'data', 'file': base,
              'path': rel, 'sha256': h, 'size': size, **inherit(base), 'status': 'draft',
              'created': str(made), 'updated': str(today), 'summary': ''}
        fm['_body'] = data_body(fm, store)
        s = make_side(DATA, base, fm); moved_links[base] = os.path.basename(s['path'])[:-3]
        msgs.append(f'データ：{base}（{size / 1e6:.1f} MB）を置き場に移し、説明 {os.path.relpath(s["path"], vp)} を作りました')

    # 3〜5. 40_attachments の本体
    files = binaries(vp, ATT)
    by_name = {nfc(os.path.basename(p)): p for p in files}
    claimed = set()
    for s in sides:
        f = kv.file_of(s['fm'])
        if s['fm'].get('store') != 'data' and f and nfc(f) in by_name: claimed.add(by_name[nfc(f)])
    orphans = [p for p in files if p not in claimed]
    osha = {p: sha(p) for p in orphans}

    for s in sides:   # 3. 指す先が無い説明の .md → 同じ中身の本体に付け直す
        fm = s['fm']; f = kv.file_of(fm)
        if fm.get('store') == 'data' or not f or nfc(f) in by_name: continue
        hit = next((p for p in orphans if osha[p] == fm.get('sha256')), None)
        if hit:
            fm['file'] = link(os.path.basename(hit)); fm['updated'] = str(today); kv.write_note(s['path'], fm, s['body'])
            orphans.remove(hit); claimed.add(hit); moved_links[f] = os.path.basename(hit)
            msgs.append(f'添付：{f} は {os.path.basename(hit)} に名前が変わっていたので、説明 {os.path.basename(s["path"])} を付け直しました')
        else:
            msgs.append(f'警告：説明 {os.path.relpath(s["path"], vp)} の本体 {f} が見つかりません（消した時は説明の .md も消してください）')

    for s in sides:   # 中身が変わった添付（同じ名前で差し替えた）→ 記録を今の中身に
        fm = s['fm']; f = kv.file_of(fm)
        if fm.get('store') == 'data' or not f or nfc(f) not in by_name or not fm.get('sha256'): continue
        h = sha(by_name[nfc(f)])
        if h != fm['sha256']:
            fm['sha256'] = h; fm['size'] = os.path.getsize(by_name[nfc(f)]); fm['updated'] = str(today); kv.write_note(s['path'], fm, s['body'])
            msgs.append(f'添付：{f} の中身が変わっていたので、記録（sha256）を今の中身にしました（前の中身は Git の履歴に残っています）')

    known = {}
    for s in sides:
        if s['fm'].get('store') != 'data' and s['fm'].get('sha256'): known.setdefault(s['fm']['sha256'], kv.file_of(s['fm']))
    for p in sorted(orphans, key=os.path.getmtime):   # 4. 説明の .md のない本体（古いものから）
        base = os.path.basename(p); h = osha[p]
        if h in known and known[h] != base and os.path.exists(os.path.join(vp, ATT, known[h])):
            os.remove(p); moved_links[base] = known[h]
            msgs.append(f'添付：{base} は既にある {known[h]} と同じ画像なので、リンクをそちらに直して重複を消しました'); continue
        fm = {'id': None, 'type': 'attachment', 'file': link(base), 'sha256': h, 'size': os.path.getsize(p),
              **inherit(base), 'status': 'draft', 'source': '', 'created': None, 'updated': str(today), 'summary': ''}
        made = datetime.date.fromtimestamp(os.path.getmtime(p))
        if store and shrink_needed(p, maxpx):   # 5. 大きい画像：原寸は置き場に残し、vault には縮小版
            orig = os.path.join(store, user or '', '原寸'); os.makedirs(orig, exist_ok=True)
            dst = free_name(orig, base); shutil.copy2(p, os.path.join(orig, dst))
            fm['original'] = f"{user + '/' if user else ''}原寸/{dst}"; fm['original_sha256'] = h
            shrink(p, maxpx); fm['sha256'] = sha_file(p); fm['size'] = os.path.getsize(p)
            msgs.append(f'添付：{base} を長辺 {maxpx}px に縮めました（原寸はデータの置き場の {fm["original"]}）')
        fm['id'] = new_id(made.strftime('%y%m%d'), ids()); fm['created'] = str(made)
        s = make_side(ATT, base, fm); known.setdefault(fm['sha256'], base)
        msgs.append(f'添付：{base} に説明 {os.path.basename(s["path"])} を作りました（鍵 {fm["access"] or "なし＝本人だけ"}）')

    if moved_links: kv.relink(vp, moved_links)
    sha.save()
    return msgs

def shrink_needed(p, maxpx):
    if not maxpx or not p.lower().endswith(IMG): return False
    try:
        from PIL import Image
        with Image.open(p) as im: return max(im.size) > maxpx
    except Exception: return False

def verify(vp, store):
    """データの置き場の本体を sha256 で照合する（差し替わり・欠けの確認）→ (照合した数, 問題の一覧)"""
    n, bad = 0, []
    for s in sidecars(vp):
        fm = s['fm']
        for key, hkey in (('path', 'sha256'), ('original', 'original_sha256')):
            if key == 'path' and fm.get('store') != 'data': continue
            if not fm.get(key): continue
            p = os.path.join(store or '', fm[key]); n += 1
            if not store or not os.path.exists(p): bad.append(f'{os.path.basename(s["path"])}: 本体 {fm[key]} がありません')
            elif sha_file(p) != fm.get(hkey): bad.append(f'{os.path.basename(s["path"])}: 本体 {fm[key]} の中身が記録（sha256）と違います')
    for s in sidecars(vp):   # vault の中の添付
        fm = s['fm']; f = kv.file_of(fm)
        if fm.get('store') == 'data' or not f: continue
        p = os.path.join(os.path.dirname(s['path']), f); n += 1
        if not os.path.exists(p): bad.append(f'{os.path.basename(s["path"])}: 本体 {f} がありません')
        elif fm.get('sha256') and sha_file(p) != fm['sha256']: bad.append(f'{os.path.basename(s["path"])}: 本体 {f} の中身が記録（sha256）と違います')
    return n, bad
