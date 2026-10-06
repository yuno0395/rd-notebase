#!/usr/bin/env python3
"""notebase：利用者の PC で動く部分（workspace/notebase.cmd から呼ばれる）

  workspace/
  ├─ notebase.cmd   入口（ダブルクリック）
  ├─ vault/         個人の Obsidian vault（自分の正本リポジトリ）
  └─ .notebase/     rd-notebase（このリポジトリ）

  run.py            （引数なし）初回は初期設定。以降は 更新 → 検査 → push
  run.py push       検査 → push だけ（タスクスケジューラから定期実行）
  run.py update     vault の更新だけ
  run.py view       自分の vault を Obsidian なしで見る（workspace/閲覧.html を作って開く）
  run.py pdf <ID>   ノートを PDF に（A4。2つ目の引数で A3〜A0。workspace/pdf/ に出す）
  run.py copy <ID>  他人のノートを図・貼った画像ごと自分の vault にコピー（コピー元と版を残す）
  run.py status     状態の表示
"""
import os, sys, re, json, glob, shutil, hashlib, secrets, subprocess, datetime, time, unicodedata, urllib.request, tempfile, platform
import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))   # .notebase
WS = os.path.dirname(ROOT)                                              # workspace
VAULT = os.path.join(WS, 'vault')
TPL = os.path.join(ROOT, 'sample-vault')
CFG = os.path.join(VAULT, '.rdnb', 'config.yml')
STATE = os.path.join(VAULT, '.rdnb', 'managed.json')
LOCK = os.path.join(ROOT, '.state', 'lock')
LOG = os.path.join(ROOT, '.state', 'log.txt')
VIEW = os.path.join(ROOT, '.state', 'view')        # 自分の vault だけの索引（Web閲覧・PDF用）
NOTICE = os.path.join(VAULT, '_notebase のお知らせ.md')   # 保存（push）できない時に Obsidian で目に入るように置く
MAN = yaml.safe_load(open(os.path.join(ROOT, 'client', 'vault.yml'), encoding='utf-8'))
TASK = 'rd-notebase push'
PUSH_MINUTES = 30
ALPH = 'abcdefghijkmnpqrstuvwxyz23456789'

os.environ.setdefault('RDNB_REGISTRY', os.path.join(ROOT, 'config', 'registry.yml'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

# ---------- 共通 ----------
def say(*a):
    msg = ' '.join(str(x) for x in a)
    print(msg, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f: f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")

def git(*a, cwd=VAULT, check=True):
    r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode: raise RuntimeError(f"git {' '.join(a)}\n{r.stderr.strip()}")
    return r.stdout.strip()

def nfc(s): return unicodedata.normalize('NFC', s)
def read(p): return open(p, encoding='utf-8').read()
def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='\n') as f: f.write(s)
def cfg(): return yaml.safe_load(read(CFG)) if os.path.exists(CFG) else None

class Lock:
    """定期実行と手動実行が重ならないようにする（10分で期限切れ）"""
    def __enter__(self):
        os.makedirs(os.path.dirname(LOCK), exist_ok=True)
        if os.path.exists(LOCK) and time.time() - os.path.getmtime(LOCK) < 600:
            raise SystemExit('別の notebase が実行中です。少し待ってからもう一度実行してください')
        write(LOCK, str(os.getpid())); return self
    def __exit__(self, *a):
        if os.path.exists(LOCK): os.remove(LOCK)

# ---------- 初期設定 ----------
def ask(q, default=''):
    a = input(f"{q}{f' [{default}]' if default else ''}: ").strip()
    return a or default

def setup():
    say('== 初期設定 ==')
    user = ''
    while not re.match(r'^[a-z][a-z0-9_-]{1,31}$', user):
        user = ask('あなたのユーザーID（英小文字。例 yamada）')
    remote = ask('あなたの vault の正本リポジトリのURL（未定なら空のままEnter）')
    if remote and git('ls-remote', remote, cwd=WS, check=False):
        say('正本に既存の vault があるので取得します（2台目のPCなど）')
        git('clone', remote, VAULT, cwd=WS)
    else:
        os.makedirs(VAULT, exist_ok=True)
        git('init', '-q', '-b', 'main')
        if remote: git('remote', 'add', 'origin', remote)
    write(CFG, yaml.safe_dump({'user': user, 'remote': remote, 'branch': 'main'}, allow_unicode=True, sort_keys=False))
    if not git('config', 'user.email', check=False):
        git('config', 'user.name', user); git('config', 'user.email', f'{user}@rd-notebase.local')
    if subprocess.run(['git', 'lfs', 'version'], capture_output=True).returncode == 0:
        git('lfs', 'install', '--local', check=False)
    else:
        say('注意: Git LFS が見つかりません。添付（画像・PDF）を push する前に Git for Windows を入れ直してください')
    update_vault()
    register_schedule()
    push()
    say('初期設定が終わりました。Obsidian で「保管庫としてフォルダを開く」から次のフォルダを開いてください：', VAULT)
    say('開いたら一度だけ：設定 → コミュニティプラグイン →「制限モードを解除」')

def register_schedule():
    if platform.system() != 'Windows':
        say(f'（定期 push：Windows 以外では cron 等で「{sys.executable} {__file__} push」を {PUSH_MINUTES} 分ごとに実行してください）'); return
    vbs = os.path.join(ROOT, 'client', 'hidden.vbs')
    r = subprocess.run(['schtasks', '/Create', '/F', '/SC', 'MINUTE', '/MO', str(PUSH_MINUTES), '/TN', TASK,
                        '/TR', f'wscript.exe "{vbs}" push'], capture_output=True, text=True)
    say(f'定期 push（{PUSH_MINUTES}分ごと）を登録しました' if r.returncode == 0 else f'定期 push を登録できませんでした：{r.stderr.strip()}')

# ---------- vault の更新（システムが管理する部分だけ） ----------
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def deep_merge(dst, src):
    for k, v in src.items():
        dst[k] = deep_merge(dst.get(k, {}), v) if isinstance(v, dict) and isinstance(dst.get(k), dict) else v
    return dst

def copy_if_changed(src, dst, changed):
    if not os.path.exists(dst) or sha(src) != sha(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy2(src, dst); changed.append(os.path.relpath(dst, VAULT))

def install_plugins(changed):
    for pid, spec in MAN['plugins'].items():
        d = os.path.join(VAULT, '.obsidian', 'plugins', pid); mf = os.path.join(d, 'manifest.json')
        if os.path.exists(mf) and json.loads(read(mf)).get('version') == str(spec['version']) and \
           all(os.path.exists(os.path.join(d, f)) and sha(os.path.join(d, f)) == h for f, h in spec['files'].items()):
            continue
        say(f'プラグインを入れます：{pid} {spec["version"]}')
        with tempfile.TemporaryDirectory() as tmp:
            for f, h in spec['files'].items():
                p = os.path.join(tmp, f)
                urllib.request.urlretrieve(f"{spec['url']}/{f}", p)
                if sha(p) != h: raise SystemExit(f'{pid}/{f} の照合に失敗しました（ダウンロードが壊れたか、配布元が変わった）')
            os.makedirs(d, exist_ok=True)
            for f in spec['files']: shutil.copy2(os.path.join(tmp, f), os.path.join(d, f))
        changed.append(f'.obsidian/plugins/{pid}')

def update_vault():
    changed, removed = [], []
    state = json.loads(read(STATE)) if os.path.exists(STATE) else {'mirror': []}
    # フォルダ
    for f in MAN['folders']:
        d = os.path.join(VAULT, f); os.makedirs(d, exist_ok=True)
        if not os.listdir(d): write(os.path.join(d, '.gitkeep'), '')
    # 丸ごと同じにするフォルダ
    now = []
    for m in MAN['mirror']:
        for src in glob.glob(os.path.join(TPL, m, '**', '*'), recursive=True):
            if os.path.isfile(src):
                rel = nfc(os.path.relpath(src, TPL)).replace(os.sep, '/'); now.append(rel)
                copy_if_changed(src, os.path.join(VAULT, rel), changed)
    for rel in set(state.get('mirror', [])) - set(now) | set(MAN['retired']['files']):
        p = os.path.join(VAULT, rel)
        if os.path.exists(p): os.remove(p); removed.append(rel)
    # ファイル
    for f in MAN['files']:
        copy_if_changed(os.path.join(TPL, f), os.path.join(VAULT, f), changed)
    for f in MAN.get('initial', []):   # 無い時だけ置く（その後は利用者のもの）
        if not os.path.exists(os.path.join(VAULT, f)): copy_if_changed(os.path.join(TPL, f), os.path.join(VAULT, f), changed)
    for f in MAN['append_lines']:
        p = os.path.join(VAULT, f); have = read(p).splitlines() if os.path.exists(p) else []
        add = [l for l in read(os.path.join(TPL, f)).splitlines() if l.strip() and l not in have]
        if add: write(p, '\n'.join(have + add) + '\n'); changed.append(f)
    # 設定の JSON
    for f in MAN['json_overlay']:   # 「ファイル名」か「{file: ファイル名, keys: [上書きする項目]}」
        f, keys = (f['file'], f['keys']) if isinstance(f, dict) else (f, None)
        src, dst = os.path.join(TPL, f), os.path.join(VAULT, f)
        cur = json.loads(read(dst)) if os.path.exists(dst) else {}
        add = json.loads(read(src))
        if keys: add = {k: add[k] for k in keys}
        new = deep_merge(json.loads(json.dumps(cur)), add)
        if new != cur: write(dst, json.dumps(new, ensure_ascii=False, indent=2) + '\n'); changed.append(f)
    # 有効にするプラグインの一覧（雛形の分を足し、やめたものを外す。利用者が足した分は残す）
    p = os.path.join(VAULT, '.obsidian', 'community-plugins.json')
    cur = json.loads(read(p)) if os.path.exists(p) else []
    new = [x for x in cur if x not in MAN['retired']['plugins']]
    new += [x for x in json.loads(read(os.path.join(TPL, '.obsidian', 'community-plugins.json'))) if x not in new]
    if new != cur: write(p, json.dumps(new, indent=2) + '\n'); changed.append('.obsidian/community-plugins.json')
    for pid in MAN['retired']['plugins']:
        d = os.path.join(VAULT, '.obsidian', 'plugins', pid)
        if os.path.isdir(d): shutil.rmtree(d); removed.append(f'.obsidian/plugins/{pid}')
    install_plugins(changed)
    write(STATE, json.dumps({'mirror': sorted(now), 'notebase': git('rev-parse', '--short', 'HEAD', cwd=ROOT, check=False),
                             'updated': f'{datetime.datetime.now():%Y-%m-%d %H:%M}'}, ensure_ascii=False, indent=2) + '\n')
    if changed or removed:
        say(f'vault を更新しました：変更 {len(changed)} 件・削除 {len(removed)} 件')
        for x in changed + removed: say('  ', x)
    else:
        say('vault は最新です')

# ---------- ID の付与（テンプレートを使わずに作ったノート） ----------
def new_id(d, used):
    while True:
        i = f"{d}-{''.join(secrets.choice(ALPH) for _ in range(5))}"
        if i not in used: used.add(i); return i

def fix_ids():
    import kv
    user = (cfg() or {}).get('user', '')
    notes = glob.glob(os.path.join(VAULT, '**', '*.md'), recursive=True)
    used = {fm.get('id') for p in notes for fm in [kv.read_note(p)[0]] if fm.get('id')}
    renames = {}
    for p in notes:
        rel = os.path.relpath(p, VAULT).replace(os.sep, '/')
        if rel.startswith(('90_templates/', '_')): continue
        fm, body = kv.read_note(p)
        dirty = False
        if user and fm.get('id') and not fm.get('owner'): fm['owner'] = user; dirty = True
        if not fm.get('id'):
            base = os.path.basename(p); drawing = base.endswith('.excalidraw.md')
            stem = base[:-len('.excalidraw.md')] if drawing else base[:-3]
            made = datetime.date.fromtimestamp(os.path.getmtime(p))
            nid = new_id(made.strftime('%y%m%d'), used)
            typ = 'daily' if re.match(r'^\d{4}-\d{2}-\d{2}$', stem) else 'weeknote' if re.match(r'^\d{4}-W\d{2}$', stem) else ''
            fm = {'id': nid, 'type': typ, 'title': nfc(stem), 'owner': user, 'project': '', 'status': 'draft', 'access': [],
                  'created': str(made), 'updated': str(made), 'summary': '', **fm}
            if not typ:   # 日付・週のノート以外は「作成日_タイトル_hash」に名前を直す
                new = kv.fname(nid, stem, 'excalidraw.md' if drawing else 'md')
                renames[stem] = new[:-len('.excalidraw.md')] if drawing else new[:-3]
                os.remove(p); p = os.path.join(os.path.dirname(p), new)
            dirty = True
            say(f'id を付けました：{rel} → {os.path.relpath(p, VAULT)}')
        if dirty: write(p, kv.join_fm(fm, body))
    if renames:   # vault 内のリンクを新しい名前に直す
        for p in glob.glob(os.path.join(VAULT, '**', '*.md'), recursive=True):
            s = read(p); t = s
            for old, new in renames.items():
                t = re.sub(r'\[\[' + re.escape(old) + r'(?=[\]|#])', '[[' + new, t)
            if t != s: write(p, t)

# ---------- 検査 → push ----------
def push(quiet=False):
    c = cfg()
    if not c: raise SystemExit('まだ初期設定していません。notebase.cmd をダブルクリックしてください')
    import kv
    fix_ids()
    errs, warns = kv.check(VAULT)
    for w in warns: say('警告:', w)
    if errs:
        raise SystemExit('検査で止まりました。次の「拒否」を直してから、もう一度実行してください\n' + '\n'.join('拒否: ' + e for e in errs))
    git('add', '-A')
    n = len(git('status', '--porcelain').splitlines())
    if n:
        git('commit', '-q', '-m', f'保存 {datetime.datetime.now():%Y-%m-%d %H:%M}')
    head = git('rev-parse', '--short', 'HEAD')
    if not c.get('remote'):   # 定期実行でも毎回1行残す（動いたかどうかをログで分かるように）
        say(f"{'定期' if quiet else ''}保存：変更 {n} 件（{head}）" + ('' if quiet else '。正本が未設定なので push はしていません（.rdnb/config.yml の remote に書くと push します）'))
        return n
    r = subprocess.run(['git', 'push', '-q', '-u', 'origin', f"HEAD:{c.get('branch', 'main')}"], cwd=VAULT, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode: raise SystemExit(f'push できませんでした（ネットワーク・権限を確認）：\n{r.stderr.strip()}')
    say(f"{'定期' if quiet else ''}push しました：変更 {n} 件（{head}）")
    return n

def refs():
    """購読（.rdnb/config.yml の subscribe に vault 名を並べる）：見てよい他人のノートのスタブを _refs/ に作る"""
    c = cfg() or {}; subs = c.get('subscribe') or []
    if not subs: return
    import kv
    if not os.path.exists(kv.DB): say('参照：索引に届かないので、スタブは前のまま'); return
    say(kv.cmd_refs(VAULT, c['user'], subs))

# ---------- 自分の vault を見る（Web閲覧 段階1・PDF） ----------
def local_index():
    """自分の vault だけで索引を作る（サーバと同じ部品を、手元の置き場 .state/view で動かす）。作れない時は None"""
    c = cfg() or {}; user = c.get('user')
    if not user or not git('rev-parse', '--verify', '-q', 'main', check=False): return None
    import kv
    r = yaml.safe_load(read(kv.REG)); vname = f'vault-{user}'
    r['vaults'] = {vname: user}; r['repos'] = {vname: os.path.join(VAULT, '.git')}
    r.setdefault('users', {}).setdefault(user, user)
    write(os.path.join(VIEW, 'registry.yml'), yaml.safe_dump(r, allow_unicode=True, sort_keys=False))
    kv.SRV, kv.REG, kv.DB, kv.OUT, kv.SELF = VIEW, os.path.join(VIEW, 'registry.yml'), os.path.join(VIEW, 'index.db'), VIEW, user
    quietly(kv.cmd_index)
    return user

def quietly(f, *a):
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()): return f(*a)

def view(open_it=False):
    """Obsidian なしで読める控え：workspace/閲覧.html（1つのファイルに全部入り。ダブルクリックで開く）"""
    out = os.path.join(WS, '閲覧.html'); stamp = os.path.join(VIEW, 'built')
    head = git('rev-parse', '-q', '--verify', 'main', check=False)
    if not open_it and os.path.exists(out) and os.path.exists(stamp) and read(stamp) == head: return   # 前に作った時から変わっていない
    try:
        user = local_index()
        if not user: return
        import pages   # 索引の置き場を決めてから読み込む
        quietly(pages.build, user, 'index.html')
    except Exception as e:   # 控えが作れなくても保存（push）は止めない
        if open_it: raise
        say('閲覧.html を作れませんでした：', e); return
    shutil.copy(os.path.join(VIEW, 'site', 'index.html'), out); write(stamp, head)
    say('閲覧.html を作りました' + ('' if open_it else '（workspace の 閲覧.html をダブルクリックで開けます）'))
    if open_it: open_file(out)

def pdf(key, size='A4'):
    user = local_index()
    if not user: raise SystemExit('まだノートが保存されていません')
    import kv, sqlite3
    con = sqlite3.connect(kv.DB)
    rows = con.execute('select id, title from notes where id = ? or path like ? or title = ?', (key, f'%{key}%', key)).fetchall()
    if len(rows) != 1:
        raise SystemExit(f'「{key}」に合うノートが{"見つかりません" if not rows else " " + str(len(rows)) + " 件あります：" + "、".join(f"{t}（{i}）" for i, t in rows[:5])}。ノートの id で指定してください')
    import pdf_out
    quietly(pdf_out.pdf, rows[0][0], size.upper(), user)
    src = os.path.join(VIEW, 'out', f'{rows[0][0]}_{size.upper()}.pdf')
    dst = os.path.join(WS, 'pdf', f"{kv.safe_title(rows[0][1] or '')}_{rows[0][0]}_{size.upper()}.pdf")
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.move(src, dst)
    say('PDF を作りました：', os.path.relpath(dst, WS)); open_file(dst)

def open_file(p):
    if platform.system() == 'Windows': os.startfile(p)
    elif shutil.which('xdg-open'): subprocess.Popen(['xdg-open', p])

# ---------- 保存できない時のお知らせ ----------
def notice(msg=None):
    """push や検査が止まったら vault に「_notebase のお知らせ」を置く（Obsidian の一覧とデイリーの未分類に出る）。直ったら消す"""
    if not os.path.isdir(VAULT): return
    if msg is None:
        if os.path.exists(NOTICE): os.remove(NOTICE); say('お知らせを消しました（保存できるようになりました）')
        return
    write(NOTICE, f"""# 保存（push）ができていません

{datetime.datetime.now():%Y-%m-%d %H:%M} の notebase の実行で止まりました。直るまで、書いたノートは手元にだけあります。

```
{msg}
```

- 「拒否」と出ている時は、そのノートを直してください
- ネットワーク・権限の時は、社内ネットワークにつながっているかを確かめてから、workspace の notebase.cmd をダブルクリックしてください
- 直って保存できると、このお知らせは自動で消えます（このファイルは Git に入りません）
""")

def autosave(msg):
    """更新の前に、利用者の変更を退避（戻せるように）"""
    if os.path.isdir(os.path.join(VAULT, '.git')):
        git('add', '-A')
        if git('status', '--porcelain'): git('commit', '-q', '-m', msg)

def status():
    c = cfg() or {}
    st = json.loads(read(STATE)) if os.path.exists(STATE) else {}
    say(f"ユーザー: {c.get('user', '（未設定）')}  正本: {c.get('remote') or '（未設定）'}")
    say(f"notebase: {git('rev-parse', '--short', 'HEAD', cwd=ROOT, check=False)}（vault に適用済み: {st.get('notebase', '—')} {st.get('updated', '')}）")
    if os.path.isdir(os.path.join(VAULT, '.git')):
        say('未保存の変更:', len(git('status', '--porcelain').splitlines()), '件')
        say('最後の保存:', git('log', '-1', '--format=%cd %s', '--date=format:%Y-%m-%d %H:%M', check=False))
    launcher = os.path.join(WS, 'notebase.cmd')
    if os.path.exists(launcher) and sha(launcher) != sha(os.path.join(ROOT, 'client', 'notebase.cmd')):
        say('お知らせ: notebase.cmd に新しい版があります（.notebase/client/notebase.cmd を workspace にコピーしてください）')

def main():
    cmd, *args = sys.argv[1:] or ['sync']
    try:
        with Lock():
            if cmd == 'status': return status()
            if cmd == 'push':
                try: push(quiet=True)
                except (SystemExit, Exception) as e: notice(str(getattr(e, 'code', e))); raise
                notice(); refs(); view()   # 控え（閲覧.html）は中身が変わった時だけ作り直す
                return
            if not cfg(): return setup()
            if cmd == 'view': autosave('閲覧前の自動保存'); return view(open_it=True)
            if cmd == 'pdf':
                if not args: raise SystemExit('使い方：notebase.cmd pdf <ノートのid> [A4〜A0]')
                autosave('PDF出力前の自動保存'); return pdf(*args[:2])
            if cmd == 'copy':
                if not args: raise SystemExit('使い方：notebase.cmd copy <他人のノートの id>（スタブのプロパティ id）')
                import kv
                if not os.path.exists(kv.DB): raise SystemExit('サーバの索引に届かないので、コピーできません')
                autosave('コピー前の自動保存')
                made, msg = kv.cmd_copy(VAULT, cfg()['user'], args[0])
                git('add', '--', *made); git('commit', '-q', '-m', msg)
                for m in made: say('コピーしました：', os.path.relpath(m, VAULT))
                say(msg); return
            if cmd in ('sync', 'update'):
                autosave('更新前の自動保存'); update_vault()
                if cmd == 'sync':
                    try: push()
                    except (SystemExit, Exception) as e: notice(str(getattr(e, 'code', e))); raise
                    notice(); refs(); view()
                status()
            else: print(__doc__)
    except SystemExit as e:
        if e.code not in (None, 0): say(str(e.code)); sys.exit(1)
    except Exception as e:
        say('エラー:', e); sys.exit(1)

if __name__ == '__main__':
    main()
