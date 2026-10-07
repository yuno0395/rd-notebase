#!/usr/bin/env python3
"""kv: Obsidian基幹システム 試作ツール（プラグイン＋サーバの処理を再現）
  new    : ノート作成（ID採番・テンプレート）
  attach : 添付の自動処理（命名・付属ノート・タグコピー・重複防止）
  push   : 検査 → コミット → サーバへ反映 → 索引更新
  refs   : 購読：見てよい他人のノートのスタブを _refs/ に作る
  copy   : 他人のノートを図・貼った画像ごと自分の vault にコピー（コピー元と版をプロパティと履歴に残す）
  build  : Web閲覧（上司用）生成
  pdf    : PDF出力
"""
import sys, os, re, json, hashlib, secrets, subprocess, unicodedata, datetime, sqlite3, shutil, yaml, html, base64, glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRV = os.environ.get('RDNB_SERVER') or os.path.join(ROOT, 'server')        # 利用者のPCで自分の vault を見る時は client/run.py が手元の置き場を指す
REG = os.environ.get('RDNB_REGISTRY') or os.path.join(SRV, 'registry.yml')   # 利用者のPCでは client/run.py が config/registry.yml を指す
OUT = os.environ.get('RDNB_OUT') or ROOT                                    # site/（Web閲覧）と out/（PDF）の置き場
SELF = os.environ.get('RDNB_SELF')                                          # 自分の vault だけを見る時の本人（全部見てよい）
IDS = os.path.join(SRV, 'allocated_ids.txt')
DB = os.path.join(SRV, 'index.db')
ALPH = 'abcdefghijkmnpqrstuvwxyz23456789'  # 0 o 1 l 除外 = 32種
ID_RE = re.compile(r'^\d{6}-[' + ALPH + r']{5}$')
FN_RE = re.compile(r'^(\d{6})_(.+)_([' + ALPH + r']{5})\.(md|excalidraw\.md)$')
REL = ['derived_from', 'based_on', 'verifies', 'affects', 'supersedes', 'promoted_to', 'copied_from']
TITLE_MAX = 40

def reg(): return yaml.safe_load(open(REG, encoding='utf-8'))
def bare_of(vault):
    """vault の Git（サーバでは server/<vault>.git。自分の vault を見る時は台帳の repos で vault の .git を指す）"""
    return (reg().get('repos') or {}).get(vault) or os.path.join(SRV, vault + '.git')
def nfc(s): return unicodedata.normalize('NFC', s)
def today(): return datetime.date.today()
def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if r.returncode: raise SystemExit(f'ERR {cmd}\n{r.stderr}')
    return r.stdout.strip()

# ---------- frontmatter ----------
def split_fm(text):
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', text, re.S)
    if not m: return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)

def join_fm(fm, body):
    return '---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip() + '\n---\n' + body

def read_note(p):
    return split_fm(open(p, encoding='utf-8').read())

# ---------- ID採番（サーバ） ----------
def alloc_id(d=None):
    d = d or today().strftime('%y%m%d')
    used = set(open(IDS).read().split()) if os.path.exists(IDS) else set()
    while True:
        i = f"{d}-{''.join(secrets.choice(ALPH) for _ in range(5))}"
        if i not in used:
            open(IDS, 'a').write(i + '\n'); return i

def safe_title(t):
    t = nfc(t)
    t = re.sub(r'[\\/:*?"<>|#^\[\]]', '_', t)
    return t[:TITLE_MAX]

def fname(nid, title, ext='md'):
    d, h = nid.split('-')
    return f"{d}_{safe_title(title)}_{h}.{ext}"

TEMPL = {
 'daily': "## 今日やること\n\n## メモ\n",
 'meeting': "## 参加者\n\n## 決定事項\n\n## 宿題\n",
 'req': "## 要求\n\n## 出所\n\n## 合否判定基準\n",
 'study': "## 目的\n\n## 検討\n\n## 結論\n\n## 却下した案と理由\n",
 'calc': "## 目的\n\n## 条件\n\n## 結果\n",
 'report': "## 要旨\n\n## 内容\n",
}
FOLDER = {'grant': '10_notes', 'daily': '01_daily', 'calc': '30_calc', 'attachment': '40_attachments'}

def cmd_new(vault, typ, title, project=None, extra=None, drawing=False, **kw):
    extra = {**(extra or {}), **kw}
    r = reg(); vp = os.path.join(ROOT, vault); owner = r['vaults'][vault]
    nid = alloc_id()
    fm = {'id': nid, 'type': typ, 'title': nfc(title), 'owner': owner,
          'project': project or '', 'status': 'draft', 'access': [],
          'created': str(today()), 'updated': str(today()), 'summary': ''}
    if project and typ not in ('daily', 'memo'):
        fm['access'] = list(r['projects'][project]['default_tags'])   # 案件の既定タグ自動付与
    if typ in ('study', 'report'): fm.update({'progress': '検討中', 'next': ''})
    if extra: fm.update(extra)
    drawing = drawing or typ == 'drawing'
    ext = 'excalidraw.md' if drawing else 'md'
    folder = FOLDER.get(typ, '10_notes')
    os.makedirs(os.path.join(vp, folder), exist_ok=True)
    p = os.path.join(vp, folder, fname(nid, title, ext))
    body = TEMPL.get(typ, '')
    if drawing:   # 図付きMarkdown：前半が文章、%% の後が図のデータ（Excalidrawプラグインの形式）
        fm['excalidraw-plugin'] = 'parsed'
        body = (TEMPL.get(typ, '') + "\n%%\n# Excalidraw Data\n" if typ != 'drawing' else '') + "\n## Embedded Files\n\n## Drawing\n```json\n" + json.dumps({'type': 'excalidraw', 'elements': [], 'files': {}}) + "\n```\n"
        if typ != 'drawing': body += '%%\n'
    open(p, 'w', encoding='utf-8').write(join_fm(fm, body))
    print(f"作成: {os.path.relpath(p, vp)}  id={nid}  access={fm['access']}")
    return p

# ---------- 添付の自動処理 ----------
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def cmd_attach(vault, src, target, origin=''):
    vp = os.path.join(ROOT, vault); r = reg()
    size = os.path.getsize(src)
    if size > r['limits']['attach_max_bytes']:
        print(f"警告: {size/1e6:.0f}MB > 上限。データ保管庫へ送る（試作では未実装）"); return None
    h = sha(src); ad = os.path.join(vp, '40_attachments'); os.makedirs(ad, exist_ok=True)
    tfm, tbody = read_note(target)
    # 重複防止
    for side in glob.glob(os.path.join(ad, '*.md')):
        sfm, _ = read_note(side)
        if sfm.get('sha256') == h:
            print(f"重複: 既存添付を再利用 {sfm['file']}")
            fn = sfm['file']; break
    else:
        nid = alloc_id(); stem, ext = os.path.splitext(os.path.basename(src))
        stem = re.sub(r'^\d{6}_(.+)_[' + ALPH + r']{5}$', r'\1', stem)   # 既に命名済みのファイルは元の名前に戻す
        fn = fname(nid, stem, ext.lstrip('.').lower())
        shutil.copy(src, os.path.join(ad, fn))
        sfm = {'id': nid, 'type': 'attachment', 'title': nfc(stem), 'file': fn, 'sha256': h,
               'owner': tfm.get('owner'), 'project': tfm.get('project', ''),
               'access': list(tfm.get('access') or []), 'source': origin,
               'created': str(today()), 'updated': str(today()), 'summary': ''}
        open(os.path.join(ad, fname(nid, stem)), 'w', encoding='utf-8').write(join_fm(sfm, ''))
        print(f"添付: {fn}  タグ{sfm['access']}で保存しました［変更］")
    if target.endswith('.excalidraw.md'):
        return fn  # 図への埋め込みは呼び出し側
    tbody = tbody.rstrip() + f"\n\n![[{fn}]]\n"
    open(target, 'w', encoding='utf-8').write(join_fm(tfm, tbody))
    return fn

# ---------- 解析 ----------
LINK_RE = re.compile(r'(!?)\[\[([^\]|#@]+)(#F\d+|#\^frame=[^\]|@]+)?(@[0-9a-f]{7,})?(\|[^\]]*)?\]\]')   # フレームは #F02 か Excalidraw の #^frame=

def hash_of(target):
    m = re.search(r'_([' + ALPH + r']{5})(\.[a-z.]+)?$', target.strip())
    return m.group(1) if m else None

def has_drawing(n):
    """図を持つノートか（図付きMarkdown＝.excalidraw.md）。種類（type）とは独立"""
    return str(n.get('path', '')).endswith('.excalidraw.md')

DRAW_START = re.compile(r'\n?(%%\n)?#+ (Excalidraw Data|Text Elements|Embedded Files|Drawing)\b')
def text_part(body):
    """図付きノートの文章部分（図のデータより前）"""
    m = DRAW_START.search(body or ''); return (body[:m.start()] if m else body or '').strip()

def parse_drawing(body):
    m = re.search(r'## Drawing\n```json\n(.*?)\n```', body, re.S)
    return json.loads(m.group(1)) if m else {'elements': []}

def embedded_files(body):
    return dict(re.findall(r'^([0-9a-f]{8,}): \[\[([^\]]+)\]\]', body, re.M))

def is_pm(fm):
    """dotpm（工程管理プラグイン）のプロジェクト・タスク。id などの名前を dotpm の意味で使うので、ノートとしては扱わない"""
    return fm.get('pm-project') is True or fm.get('pm-task') is True

def scan_vault(vp):
    notes = {}
    for p in glob.glob(os.path.join(vp, '**', '*.md'), recursive=True):
        rel = p.replace(vp, '').replace(os.sep, '/')
        if '/_' in rel or rel.lstrip('/').startswith('20_工程/'): continue   # 20_工程＝取りまとめ役の手元にある案件リポジトリ（別の正本）
        fm, body = read_note(p)
        if not fm.get('id') or is_pm(fm): continue
        notes[fm['id']] = {'path': p, 'fm': fm, 'body': body}
    return notes

# ---------- 検査（プッシュ時、サーバ側） ----------
# プロパティの予約名（vault設計 5.4 レベル0）。システムが作るノート（開示・コメント・工程など）の項目も含む
RESERVED = set('''id type title aliases owner project status access created updated summary tags progress next parts
tool env inputs result_hash promoted_to excalidraw-plugin note
targets audience purpose requested_by approvers decision reason approved_targets approved_version approved_at report revoked
about about_label assignee due state file sha256 source checks approved_by
copied_version tasks baselines roadmap items week schedule changes ops lines code needs_approval why remap decided_by decided_at comment gantt'''.split()) | set(REL)
DATE_KEYS = ('created', 'updated', 'due')

def check_props(fn, fm, r, warns, errs):
    """プロパティの検査：台帳にない名前（my_ 以外）、型・書き方、顧客名"""
    reg_props = r.get('properties') or {}
    for k, v in fm.items():
        if k.startswith('my_'): continue
        if k not in RESERVED and k not in reg_props:
            warns.append(f"{fn}: 台帳にないプロパティ「{k}」（自分用なら my_{k} に。皆で使うなら台帳に登録）")
        spec = reg_props.get(k)
        if spec and spec.get('values') and v not in (None, '') and v not in spec['values']:
            warns.append(f"{fn}: 「{k}」の値「{v}」は台帳の候補 {spec['values']} にない")
        if spec and spec.get('scope') not in (None, '全社') and fm.get('project') != spec['scope']:
            warns.append(f"{fn}: 「{k}」は {spec['scope']} の中だけで使うプロパティ")
    for k in DATE_KEYS:
        if fm.get(k) not in (None, '') and not re.match(r'^\d{4}-\d{2}-\d{2}$', str(fm[k])):
            errs.append(f"{fn}: 「{k}」の日付は YYYY-MM-DD で書く（{fm[k]}）")
    words = r.get('customer_words') or []
    for k, v in fm.items():
        if k in ('title', 'aliases', 'about_label', 'file', 'access') or k in REL: continue   # タイトル・ファイル名は鍵の「タイトル非公開」、鍵の名前は台帳で守る
        if any(w in str(v) for w in words):
            warns.append(f"{fn}: プロパティ「{k}」に顧客名が入っています。他人に配るスタブに載るので、本文に書いてください")

def source_of(link):
    """コピー元（[[ファイル名]]）を索引から探す。索引に届かない時は None"""
    h = hash_of(str(link).strip('[]'))
    try:
        r = sqlite3.connect(DB).execute("select id, access from notes where id like ?", (f'%-{h}',)).fetchone()
    except sqlite3.Error: return None
    return {'id': r[0], 'access': json.loads(r[1])} if r else None

def check(vp):
    r = reg(); errs, warns = [], []
    notes = scan_vault(vp); byhash = {i.split('-')[1]: n for i, n in notes.items()}
    tags = set(r['tags'])
    ok = {t for n in notes.values() if n['fm'].get('type') == 'grant' and n['fm'].get('decision') == 'approved' for t in n['fm'].get('approved_targets') or []}
    # IDのないノート（テンプレートを使わずに作った）を見つける。テンプレート置き場と隠しフォルダは除く
    for p in glob.glob(os.path.join(vp, '**', '*.md'), recursive=True):
        rel = os.path.relpath(p, vp)
        if rel.startswith(('90_templates', '20_工程', '_', '.')) or '/.' in rel: continue
        fm0 = read_note(p)[0]
        if is_pm(fm0): continue
        if not fm0.get('id'): errs.append(f"{rel}: id がありません（テンプレートから作り直すか、プラグインで付与）")
    # 全社で重複するID（他のvaultの索引と比べる）
    try:
        con = sqlite3.connect(DB); vname = os.path.basename(vp)
        for (i,) in con.execute('select id from notes where vault != ?', (vname,)):
            if i in notes: errs.append(f"{os.path.basename(notes[i]['path'])}: id {i} が他のvaultと重複（振り直す）")
    except sqlite3.Error: pass
    for nid, n in notes.items():
        fn = os.path.basename(n['path']); fm = n['fm']
        check_props(fn, fm, r, warns, errs)
        if fn != nfc(fn): errs.append(f"{fn}: NFCでない")
        if not ID_RE.match(nid): errs.append(f"{fn}: id形式不正 {nid}")
        m = FN_RE.match(fn)
        daily_ok = (fm.get('type') == 'daily' and re.match(r'^\d{4}-\d{2}-\d{2}\.md$', fn)) or \
                   (fm.get('type') == 'weeknote' and re.match(r'^\d{4}-W\d{2}\.md$', fn))   # デイリー・週ノートは日付・週の名前でよい（Periodic Notes）
        if not daily_ok and (not m or f"{m.group(1)}-{m.group(3)}" != nid): errs.append(f"{fn}: ファイル名とidが不一致")
        for t in fm.get('access') or []:
            if t not in tags: errs.append(f"{fn}: 未登録タグ {t}")
        if fm.get('copied_from'):   # コピーはコピー元より広く見せられない（コピー元の鍵を全部持つこと）
            src = source_of(fm['copied_from'])
            mine = fm.get('access') or []   # 鍵なし＝本人だけ（いちばん狭い）。鍵を付けるならコピー元の鍵を全部含める
            lack = [t for t in (src or {}).get('access', []) if mine and t not in mine]
            if lack: errs.append(f"{fn}: コピー元の鍵 {lack} が外れています（コピー元より広く見せることになる）")
        for p in fm.get('parts') or []:
            if not re.match(r['part_regex'], str(p)): warns.append(f"{fn}: 品番形式外 {p}")
        for k in fm:
            if k.endswith('_from') or k in ('based_on', 'verifies'):
                if k not in REL: warns.append(f"{fn}: 未登録の関係 {k}")
        # 埋め込みのタグ継承（同じ元はまとめる）
        mine = set(fm.get('access') or []); lack = {}
        for bang, tgt, fr, ver, _ in LINK_RE.findall(n['body']):
            if not bang: continue
            src = byhash.get(hash_of(tgt))
            if src and not set(src['fm'].get('access') or []) <= mine and f"{src['fm']['id']}{fr}" not in ok and src['fm']['id'] not in ok:
                lack.setdefault(src['fm']['title'], set()).add(fr.lstrip('#') or '全体')
        if lack:
            items = '、'.join(f"{t}（{'/'.join(sorted(f))}）" for t, f in lack.items())
            warns.append(f"{fn}: 公開範囲 {sorted(mine)} より狭い資料を埋め込んでいます：{items}\n"
                         "    → 選択肢 1) 引用元の公開範囲を広げる  2) 開示を申請する（kv.py request）  3) この報告の公開範囲を戻す")
    return errs, warns

def cmd_push(vault, msg='auto'):
    vp = os.path.join(ROOT, vault)
    errs, warns = check(vp)
    for w in warns: print('警告:', w)
    if errs:
        for e in errs: print('拒否:', e)
        raise SystemExit('プッシュ拒否')
    sh('git add -A', vp)
    if sh('git status --porcelain', vp):
        sh(f'git commit -qm "{msg}"', vp)
    sh('git push -q origin main', vp)
    cmd_index()
    print('反映OK', sh('git rev-parse --short HEAD', vp))

# ---------- LFS（サーバ側で引換券を中身に戻す） ----------
def lfs_resolve(work, bare):
    n = 0
    for p in glob.glob(os.path.join(work, '40_attachments', '*')):
        head = open(p, 'rb').read(200)
        if not head.startswith(b'version https://git-lfs'): continue
        oid = re.search(rb'oid sha256:([0-9a-f]{64})', head).group(1).decode()
        obj = os.path.join(bare, 'lfs', 'objects', oid[:2], oid[2:4], oid)
        if os.path.exists(obj): shutil.copy(obj, p); n += 1
        else: print('警告: LFSの中身がサーバにない', os.path.basename(p))
    return n

# ---------- 索引DB ----------
def cmd_index():
    r = reg()
    if os.path.exists(DB): os.remove(DB)
    db = sqlite3.connect(DB)
    db.executescript("""create table notes(id primary key, vault, path, type, title, owner, project, status,
        access, progress, next, updated, summary, commit_, fm, body);
        create table links(src, dst, kind, frame, ver);
        create table ext(src, ref);
        create virtual table fts using fts5(id, title, body, tokenize='trigram');""")
    for vault in r['vaults']:
        bare = bare_of(vault); work = os.path.join(SRV, 'work', vault)
        if os.path.exists(work): shutil.rmtree(work)
        os.makedirs(work)
        # main の中身を書き出す。一時の index を使い、元のリポジトリの HEAD・index には触らない（LFS は下で中身に戻す）
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(SRV, 'work', '.index'), GIT_LFS_SKIP_SMUDGE='1')
        for args in (['read-tree', 'main'], ['checkout-index', '-a', '-f']):
            subprocess.run(['git', f'--git-dir={bare}', f'--work-tree={work}', *args], env=env, check=True, capture_output=True)
        lfs_resolve(work, bare)
        commit = sh(f'git --git-dir="{bare}" rev-parse --short main')
        for nid, n in scan_vault(work).items():
            fm = n['fm']; body = n['body']
            db.execute('insert into notes values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                nid, vault, os.path.relpath(n['path'], work), fm.get('type'), fm.get('title'), fm.get('owner'),
                fm.get('project'), fm.get('status'), json.dumps(fm.get('access') or [], ensure_ascii=False),
                fm.get('progress'), fm.get('next'), str(fm.get('updated')), fm.get('summary'), commit,
                json.dumps(fm, ensure_ascii=False, default=str), body))
            text = body
            if has_drawing(n):
                text = text_part(body) + ' ' + ' '.join(e.get('text', '') or e.get('name', '') or '' for e in parse_drawing(body)['elements'])
            db.execute('insert into fts values(?,?,?)', (nid, fm.get('title'), text))
            for bang, tgt, fr, ver, _ in LINK_RE.findall(body):
                if tgt.startswith(tuple(t + ':' for t in r['ref_types'])):
                    db.execute('insert into ext values(?,?)', (nid, tgt)); continue
                h = hash_of(tgt)
                if h: db.execute('insert into links values(?,?,?,?,?)', (nid, h, 'cites' if bang else 'link', fr, ver))
            for k in REL:
                vs = fm.get(k) or []
                for v in ([vs] if isinstance(vs, str) else vs):   # 1つだけの時は文字列でもよい（copied_from など）
                    h = hash_of(str(v).strip('[]'))
                    if h: db.execute('insert into links values(?,?,?,?,?)', (nid, h, k, '', ''))
            for p in fm.get('parts') or []:
                db.execute('insert into ext values(?,?)', (nid, f'part:{p}'))
            if fm.get('project'): db.execute('insert into ext values(?,?)', (nid, f"proj:{fm['project']}"))
    db.commit(); print('索引更新', db.execute('select count(*) from notes').fetchone()[0], '件')

def can_see(user, access):
    if SELF and user == SELF: return True   # 自分の vault だけを見る時は全部自分のノート
    r = reg(); a = json.loads(access) if isinstance(access, str) else access
    if not a: return False  # タグなし＝本人のみ
    return all(user in (r['tags'].get(t) or {}).get('members', []) for t in a)

# ---------- 購読（他人のノートのスタブ。vault設計 6.2・6.3 レベル2） ----------
STUB_KEYS = ['id', 'type', 'title', 'owner', 'project', 'status', 'access', 'created', 'updated', 'summary', 'progress', 'next', 'parts', 'copied_version'] + REL
REFS_BASE = '''# notebase が作る（手で直しても次の更新で戻る）。購読している他人のノートの一覧
filters:
  and:
    - file.ext == "md"
    - file.inFolder("_refs")
properties:
  note.title: {displayName: タイトル}
  note.owner: {displayName: 書いた人}
  note.type: {displayName: 種類}
  note.project: {displayName: 案件}
  note.updated: {displayName: 更新}
  note.summary: {displayName: 要約}
views:
  - type: table
    name: 参照
    groupBy: {property: note.owner, direction: ASC}
    order: [file.name, type, project, summary, updated]
    sort:
      - {property: updated, direction: DESC}
'''

FIG = '_図'
def write_if_changed(p, text):
    if os.path.exists(p) and open(p, encoding='utf-8').read() == text: return False
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w', encoding='utf-8').write(text); return True

def drawing_svgs(nid, viewer):
    """図付きノートのフレームごとの SVG（Web閲覧と同じ描画。貼った画像は viewer が見てよいものだけ）"""
    import render, core
    c = core.db(); notes = core.all_notes(c); n = notes[nid]
    frs, els = render.frames_of(n); out = []
    for f in frs:
        k = re.search(r'k="([^"]+)"', render.svg_frame(n, f, els, viewer, notes)).group(1)
        svg = render.ASSETS.pop(k).replace('<svg ', f'<svg width="{f["width"] + 20:.0f}" height="{f["height"] + 20:.0f}" ', 1)
        fid = (f.get('customData') or {}).get('kvFrame')
        out.append((fid, f"{fid} {f.get('name', '')}".strip() if fid else f.get('name', ''), svg))   # 見出しに # を付けるとタグになる
    return out

def cmd_refs(vp, viewer, sources):
    """購読した vault のノートのうち、viewer が見てよいものだけをスタブにして vp/_refs/<vault>/ に置く。
    スタブはプロパティ（予約名と台帳で stub: true のもの）・要約・見てよいリンク先だけ。本文・図・添付は持たない。
    見られなくなったノート（鍵の変更・削除）のスタブは消す。リンクが同じ名前で解決するよう、ファイル名は元と同じにする"""
    r = reg(); con = sqlite3.connect(DB); users = r.get('users') or {}
    keys = STUB_KEYS + [k for k, v in (r.get('properties') or {}).items() if v.get('stub')]
    rows = {i: (v, p, json.loads(fm), json.loads(a), c) for i, v, p, fm, a, c in
            con.execute('select id, vault, path, fm, access, commit_ from notes')}
    seen = lambda i: i in rows and (rows[i][2].get('owner') == viewer or can_see(viewer, rows[i][3]))
    byhash = {i.split('-')[1]: i for i in rows}
    made, removed = 0, 0
    for src in sources:
        out = os.path.join(vp, '_refs', src); os.makedirs(out, exist_ok=True); keep, keep_fig = {FIG}, set()
        for nid, (v, path, fm, acc, commit) in rows.items():
            if v != src or not seen(nid): continue
            name = os.path.basename(path); keep.add(name)
            sfm = {k: fm[k] for k in keys if k in fm}
            sfm['ref'] = f'{src}@{commit}'
            links = []
            for (dst,) in con.execute('select distinct dst from links where src = ?', (nid,)):
                d = byhash.get(dst)
                if d and seen(d): links.append(os.path.basename(rows[d][1])[:-3])
            who = users.get(fm.get('owner'), fm.get('owner'))
            body = (f"> [!quote] {who} のノート（参照用のスタブ）\n"
                    f"> 本文はサーバで見る（Web閲覧）。図はサーバが描いた控え。ここを書き換えても元のノートは変わらず、次の更新で戻る\n\n"
                    f"## 要約\n{fm.get('summary') or '（要約なし）'}\n")
            if links: body += '\n## リンク先\n' + ''.join(f'- [[{l}]]\n' for l in sorted(links))
            if name.endswith('.excalidraw.md'):   # 図はサーバで SVG にして置く（データそのものは配らない。貼った画像も見てよいものだけ）
                body += '\n## 図\n'
                for fid, label, svg in drawing_svgs(nid, viewer):
                    sp = f'{FIG}/{nid}_{fid or "全体"}.svg'; keep_fig.add(os.path.basename(sp))
                    write_if_changed(os.path.join(out, sp), svg)
                    body += f'\n### {label}\n![[_refs/{src}/{sp}]]\n'
            text = join_fm(sfm, body); p = os.path.join(out, name)
            if not os.path.exists(p) or open(p, encoding='utf-8').read() != text:
                open(p, 'w', encoding='utf-8').write(text); made += 1
        for f in os.listdir(out):
            if f not in keep: os.remove(os.path.join(out, f)); removed += 1
        fd = os.path.join(out, FIG)
        for f in os.listdir(fd) if os.path.isdir(fd) else []:
            if f not in keep_fig: os.remove(os.path.join(fd, f))
    base = os.path.join(vp, '_refs', '参照.base')
    if not os.path.exists(base) or open(base, encoding='utf-8').read() != REFS_BASE:
        open(base, 'w', encoding='utf-8').write(REFS_BASE)
    n = sum(f.endswith('.md') for _, _, fs in os.walk(os.path.join(vp, '_refs')) for f in fs)
    return f'参照：スタブ {n} 件（更新 {made}・削除 {removed}）'

# ---------- 他人のノートのコピー（図・貼った画像ごと） ----------
def cmd_copy(vp, viewer, key):
    """見てよい他人のノートを、新しい ID で自分の vault にコピーする。
    コピー元はプロパティ copied_from（リンク）と copied_version（その時の版）に残し、鍵（access）はコピー元のまま引き継ぐ。
    貼った画像も 40_attachments にコピーする。返り値：(作ったファイル, コミットの文言)"""
    import core, render
    c = core.db(); notes = core.all_notes(c); hmap = core.by_hash(notes)
    n = notes.get(key) or hmap.get(hash_of(key) or '')
    if not n:
        hits = [x for x in notes.values() if key in (x['title'] or '') and x['owner'] != viewer and x['type'] not in ('attachment', 'grant', 'comment')]
        if len(hits) != 1: raise SystemExit(f'「{key}」に合うノートが' + ('見つかりません' if not hits else f' {len(hits)} 件あります：' + '、'.join(f"{x['title']}（{x['id']}）" for x in hits[:5])))
        n = hits[0]
    fm = json.loads(n['fm'])
    if fm.get('owner') == viewer: raise SystemExit('自分のノートです（コピーは他人のノートに使います）')
    if not can_see(viewer, n['access']): raise SystemExit('このノートを見る権限がないので、コピーできません')
    body = n['body']; files = embedded_files(body); copies = []
    for fid, fn in files.items():   # 貼った画像：見てよいものだけ。1枚でも見られなければコピーしない
        p = render.image_file(n, fn, viewer, notes, hmap)
        if not p: raise SystemExit(f'図に貼った「{fn}」を見る権限がないので、コピーできません')
        dst = os.path.basename(p); copies.append((p, dst))
        body = body.replace(f'{fid}: [[{fn}]]', f'{fid}: [[{dst}]]')
    nid = alloc_id(); src = os.path.basename(n['path'])
    stem = src[:-3]
    new = {k: v for k, v in fm.items() if not k.startswith('my_')}
    new.update({'id': nid, 'owner': viewer, 'status': 'draft', 'created': str(today()), 'updated': str(today()),
                'copied_from': f'[[{stem}]]', 'copied_version': n['commit_']})
    ext = 'excalidraw.md' if src.endswith('.excalidraw.md') else 'md'
    out = os.path.join(vp, '10_notes', fname(nid, fm.get('title') or stem, ext)); os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8').write(join_fm(new, body))
    made = [out]
    for p, dst in copies:
        d = os.path.join(vp, '40_attachments', dst)
        if not os.path.exists(d): os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy(p, d); made.append(d)
    who = reg()['users'].get(fm.get('owner'), fm.get('owner'))
    msg = f"コピー: {fm.get('title')}（{who} の {n['id']}@{n['commit_']} から）"
    return made, msg

def cmd_request(vault, report_path, targets, audience, purpose):
    """開示申請：見せてよい図のフレーム・添付を選んで申請（図に埋め込まれた画像も自動で対象に加える）"""
    vp = os.path.join(ROOT, vault); r = reg(); notes = scan_vault(vp); byhash = {i.split('-')[1]: n for i, n in notes.items()}
    full = []
    for t in targets:
        full.append(t); nid, _, fid = t.partition('#'); n = notes.get(nid)
        if n and has_drawing(n) and fid:
            d = parse_drawing(n['body']); files = embedded_files(n['body'])
            fr = next(e for e in d['elements'] if e['type'] == 'frame' and (e.get('customData') or {}).get('kvFrame') == fid)
            for e in d['elements']:
                if e.get('frameId') == fr['id'] and e['type'] == 'image':
                    side = byhash.get(hash_of(files.get(e['fileId'], '')))
                    if side and side['fm']['id'] not in full: full.append(side['fm']['id'])
    tags = set()
    for t in full: tags |= set((notes[t.split('#')[0]]['fm'].get('access')) or [])
    owners = sorted({r['tags'][t]['owner'] for t in tags})
    rfm, _ = read_note(report_path)
    p = cmd_new(vault, 'grant', f"{rfm['title']} 開示申請", project=rfm.get('project'),
                targets=full, audience=audience, purpose=purpose, requested_by=r['vaults'][vault],
                approvers=owners, decision='requested', reason='', approved_targets=[], approved_version='', report=rfm['id'])
    print(f"開示申請: {len(full)}件（画像を含む） 承認者 {owners}")
    return p

def cmd_comment(vault, target, text, images=(), assignee=None, due=None):
    """コメント：書いた人のvaultにコメントのノート（type: comment）を作る。担当・期限があれば「やること」（指摘）になる。
    鍵＝書いた人がその資料を見ている範囲（元の鍵で見ているなら元の鍵、公開で見ているなら公開先）"""
    r = reg(); user = r['vaults'][vault]
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    nid, _, fid = target.partition('#')
    t = c.execute('select * from notes where id=?', (nid,)).fetchone()
    if not t: raise SystemExit(f'対象なし {target}')
    tfm = json.loads(t['fm']); stem = os.path.basename(t['path']).rsplit('.md', 1)[0].replace('.excalidraw', '')
    if can_see(user, tfm.get('access') or []): acc = list(tfm.get('access') or [])
    else:
        acc = sorted({a for g in c.execute("select fm from notes where type='grant'") for gf in [json.loads(g['fm'])]
                      if gf.get('decision') == 'approved' and {target, nid} & set(gf.get('approved_targets') or [])
                      for a in gf.get('audience') or [] if user in r['tags'][a]['members']})
        if not acc: raise SystemExit('見られない資料にはコメントできません')
    label = tfm['title'] + (f' #{fid}' if fid else '')
    if fid and has_drawing(dict(t)):
        f = next((e for e in parse_drawing(t['body'])['elements'] if e['type'] == 'frame' and (e.get('customData') or {}).get('kvFrame') == fid), None)
        if f and f.get('name'): label += ' ' + f['name']
    extra = dict(about=target, about_label=label)
    if assignee: extra.update(assignee=assignee, due=due, state='open')
    p = cmd_new(vault, 'comment', f"コメント {tfm['title']}"[:TITLE_MAX], project=tfm.get('project') or None, **extra)
    fm, _ = read_note(p); fm['access'] = acc
    line = (f"- [ ] {text} 📅 {due} [assignee:: user:{assignee}] [about:: {target}]" if assignee else text)
    open(p, 'w', encoding='utf-8').write(join_fm(fm, f"## 対象\n[[{stem}{'#' + fid if fid else ''}|{label}]]\n\n## 内容\n{line}\n"))
    for im in images: cmd_attach(vault, im, p, origin='コメントの添付')
    return p

if __name__ == '__main__':
    c, *a = sys.argv[1:]
    if c == 'new':
        kw = {}
        for x in a[3:]:
            k, v = x.split('=', 1); kw[k] = v
        cmd_new(a[0], a[1], a[2], project=kw.pop('project', None), extra=kw or None)
    elif c == 'attach': cmd_attach(a[0], a[1], a[2], a[3] if len(a) > 3 else '')
    elif c == 'push': cmd_push(a[0], a[1] if len(a) > 1 else 'auto')
    elif c == 'index': cmd_index()
    elif c == 'copy':   # kv.py copy <自分のvault> <ノートのid・タイトルの一部>
        vp = os.path.join(ROOT, a[0]); made, msg = cmd_copy(vp, reg()['vaults'][a[0]], a[1])
        for m in made: print('作成:', os.path.relpath(m, vp))
        sh('git add -A', vp); sh(f'git commit -qm "{msg}"', vp); print(msg)
    elif c == 'refs': print(cmd_refs(os.path.join(ROOT, a[0]), reg()['vaults'][a[0]], a[1:]))   # kv.py refs <自分のvault> <購読するvault>...
    elif c == 'check': print(check(os.path.join(ROOT, a[0])))
    else: print(__doc__)
