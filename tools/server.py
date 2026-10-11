#!/usr/bin/env python3
"""サーバの取り込み（索引・検査・工程の照合・Web 閲覧の作り直し）と保全（バックアップ・復旧の試験）

  server.py run [--interval 60]     取り込みを続ける（1分ごと。止めるまで動く）
  server.py once                    取り込みを1回だけ（タスクスケジューラ・cron から呼ぶ時）
  server.py backup <置き場> [--keep 30]   全リポジトリのミラー（LFS の中身も）と、索引・台帳の控え（日付ごと、30日分）
  server.py restore-test <置き場>          控えだけで索引を作り直せるかを試す（毎月など。数が合わなければ失敗で終わる）

取り込みの流れ（1回分）：
  1. 台帳の各リポジトリを取ってくる（registry.yml の remotes に URL があれば git fetch。なければサーバの <vault>.git をそのまま見る）
  2. main が前回から変わったリポジトリだけ、サーバ側で検査する（kv.check と同じ）。
     合格なら refs/rdnb/accepted をその版に進める。不合格なら一つ前の合格した版のまま（索引・Web 閲覧には出さない）
  3. 変わった vault だけ索引を入れ直す（差分の索引。リンクと承認は全体で引き直す）
  4. 承認ノートで判断された計画変更を工程表に反映、案件リポジトリの dotpm の変更を照合（申請にする）
  5. Web 閲覧を作り直す（registry.yml の sites。無ければ試作の3人分）
  6. 人ごとの状態（status/<ID>.json）を置く。notebase は push の後にこれを見て、不合格ならお知らせを置く
GitHub.com では push を拒否する仕組み（pre-receive）が使えないので、「受け取ってから、合格した版だけを有効にする」形にしている
"""
import os, sys, json, time, shutil, sqlite3, datetime, subprocess, glob
sys.path.insert(0, os.path.dirname(__file__))
import kv

STATE = os.path.join(kv.SRV, 'state.json')
STATUS = os.path.join(kv.SRV, 'status')
SITES = {'boss': 'index.html', 'yamada': 'yamada.html', 'staff': 'staff.html'}

def git(bare, *a, check=False):
    r = subprocess.run(['git', f'--git-dir={bare}', *a], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if check and r.returncode: raise RuntimeError(r.stderr.strip())
    return r

def now(): return datetime.datetime.now().isoformat(timespec='seconds')

def load(p, d):
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return d

def save(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True); tmp = p + '.tmp'
    json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); os.replace(tmp, p)

def fetch(vault, bare, url):
    """正本（GitHub など）から取ってくる。LFS の中身も（失敗しても続ける）"""
    if not os.path.isdir(bare): subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', bare], capture_output=True)
    r = git(bare, 'fetch', '-q', url, '+refs/heads/main:refs/heads/main')
    if r.returncode: return f'取ってこられません：{r.stderr.strip()[:200]}'
    git(bare, 'lfs', 'fetch', url, 'main')
    return None

def is_project(vault, r):
    return vault.startswith('proj-') or vault in {(p.get('repo') or '') for p in (r.get('projects') or {}).values()}

def check_commit(vault, bare, head):
    """その版をサーバ側で検査する → 拒否の一覧（案件リポジトリは dotpm の形なので検査しない）"""
    work = os.path.join(kv.SRV, 'check', vault)   # フォルダ名を vault 名にする（kv.check が他の vault との id の重なりを見るため）
    if os.path.exists(work): shutil.rmtree(work)
    os.makedirs(work)
    env = dict(os.environ, GIT_INDEX_FILE=os.path.join(kv.SRV, 'check', '.index'), GIT_LFS_SKIP_SMUDGE='1')
    for a in (['read-tree', head], ['checkout-index', '-a', '-f']):
        subprocess.run(['git', f'--git-dir={bare}', f'--work-tree={work}', *a], env=env, check=True, capture_output=True)
    errs, warns = kv.check(work)
    shutil.rmtree(work, ignore_errors=True)
    return errs, warns

def step(build_sites=True, say=print):
    """取り込みを1回 → 入れ直した vault の一覧"""
    r = kv.reg(); st = load(STATE, {}); changed = []; status = {}
    for vault, user in r['vaults'].items():
        bare = kv.bare_of(vault); url = (r.get('remotes') or {}).get(vault)
        s = st.setdefault(vault, {})
        if url:
            e = fetch(vault, bare, url)
            if e: s['error'] = e; say(f'{vault}: {e}'); continue
        h = git(bare, 'rev-parse', '-q', '--verify', 'main')
        if h.returncode: continue
        head = h.stdout.strip()
        if s.get('seen') == head: continue
        if is_project(vault, r): errs, warns = [], []
        else: errs, warns = check_commit(vault, bare, head)
        s.update(seen=head, checked_at=now(), errors=errs, warnings=warns[:50])
        if errs:
            say(f'{vault}: 検査で止めました（{head[:7]}）。一つ前の合格した版のまま：' + ' / '.join(errs[:3]))
        else:
            git(bare, 'update-ref', kv.ACCEPTED, head); s['accepted'] = head
            changed.append(vault); say(f'{vault}: 取り込みました（{head[:7]}）')
        if not is_project(vault, r): status[user] = {'vault': vault, 'commit': head, 'ok': not errs, 'errors': errs, 'warnings': warns[:20], 'at': now()}
    save(STATE, st)
    for u, d in status.items(): save(os.path.join(STATUS, f'{u}.json'), d)
    if not changed: return changed
    kv.cmd_index(changed)
    try:
        import pm
        n = pm.cmd_apply_approvals()
        if n: say(f'計画変更：承認ノートの判断を {n} 件、工程表に反映しました')
        for v in changed:
            if is_project(v, r) and os.path.isdir(os.path.join(kv.ROOT, v)):
                import dotpm
                if dotpm.project_file(os.path.join(kv.ROOT, v)): pm.cmd_sync(v)
    except SystemExit as e: say(f'工程の処理で止まりました：{e}')
    if build_sites:
        import contextlib, io, pages
        for u, f in (r.get('sites') or SITES).items():
            with contextlib.redirect_stdout(io.StringIO()): pages.build(u, f)
        say('Web 閲覧を作り直しました')
    return changed

def run(interval=60):
    print(f'取り込みを始めます（{interval} 秒ごと。止めるには Ctrl+C）', flush=True)
    while True:
        t = time.time()
        try: step(say=lambda m: print(f'{now()} {m}', flush=True))
        except Exception as e: print(f'{now()} エラー：{e}', flush=True)
        time.sleep(max(1, interval - (time.time() - t)))

# ---------- 保全 ----------
def backup(dest, keep=30):
    """全リポジトリのミラー（消えた枝も残す）と LFS の中身、索引と台帳の日付ごとの控え"""
    r = kv.reg(); day = datetime.date.today().strftime('%Y%m%d'); mirrors = os.path.join(dest, 'mirrors'); n = 0
    os.makedirs(mirrors, exist_ok=True)
    for vault in r['vaults']:
        bare = kv.bare_of(vault); m = os.path.join(mirrors, vault + '.git')
        if not os.path.isdir(bare): continue
        if not os.path.isdir(m): subprocess.run(['git', 'clone', '-q', '--mirror', bare, m], check=True, capture_output=True)
        else: git(m, 'fetch', '-q', bare, '+refs/*:refs/*', check=True)   # 消えた枝は消さない（prune しない）
        src = os.path.join(bare, 'lfs', 'objects')
        for p in glob.glob(os.path.join(src, '**', '*'), recursive=True):
            if os.path.isfile(p):
                q = os.path.join(m, 'lfs', 'objects', os.path.relpath(p, src))
                if not os.path.exists(q): os.makedirs(os.path.dirname(q), exist_ok=True); shutil.copy2(p, q)
        n += 1
    os.makedirs(os.path.join(dest, 'index'), exist_ok=True)
    if os.path.exists(kv.DB):
        out = sqlite3.connect(os.path.join(dest, 'index', f'index_{day}.db'))
        with out: sqlite3.connect(kv.DB).backup(out)
        out.close()
    shutil.copy2(kv.REG, os.path.join(dest, 'index', f'registry_{day}.yml'))
    old = sorted(glob.glob(os.path.join(dest, 'index', 'index_*.db')))[:-keep]
    for p in old:
        os.remove(p); y = p.replace('index_', 'registry_').replace('.db', '.yml')
        if os.path.exists(y): os.remove(y)
    open(os.path.join(dest, '最終バックアップ.txt'), 'w', encoding='utf-8').write(f'{now()} リポジトリ {n} 件・索引の控え {day}\n')
    return n

def restore_test(dest):
    """控え（ミラーと台帳）だけで、別の置き場に索引を作り直し、今の索引と件数を比べる → (合っているか, 文)"""
    import tempfile, yaml
    regs = sorted(glob.glob(os.path.join(dest, 'index', 'registry_*.yml')))
    if not regs: return False, '台帳の控えがありません（先に backup）'
    with tempfile.TemporaryDirectory() as tmp:
        r = yaml.safe_load(open(regs[-1], encoding='utf-8'))
        r['repos'] = {v: os.path.join(dest, 'mirrors', v + '.git') for v in r['vaults']}
        rp = os.path.join(tmp, 'registry.yml'); yaml.safe_dump(r, open(rp, 'w', encoding='utf-8'), allow_unicode=True)
        env = dict(os.environ, RDNB_SERVER=tmp, RDNB_REGISTRY=rp, RDNB_OUT=tmp)
        p = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'kv.py'), 'index'], env=env, capture_output=True, text=True)
        if p.returncode: return False, f'作り直せませんでした：{p.stderr.strip()[-300:]}'
        got = sqlite3.connect(os.path.join(tmp, 'index.db')).execute('select count(*) from notes').fetchone()[0]
    live = sqlite3.connect(kv.DB).execute('select count(*) from notes').fetchone()[0] if os.path.exists(kv.DB) else None
    ok = live is None or got == live
    return ok, f'控えから作り直した索引：ノート {got} 件（今の索引 {live} 件）' + ('。合っています' if ok else '。数が合いません')

if __name__ == '__main__':
    c, *a = sys.argv[1:] or ['once']
    if c == 'run': run(int(a[a.index('--interval') + 1]) if '--interval' in a else 60)
    elif c == 'once': step()
    elif c == 'backup': print('バックアップ：リポジトリ', backup(a[0], int(a[a.index('--keep') + 1]) if '--keep' in a else 30), '件')
    elif c == 'restore-test':
        ok, msg = restore_test(a[0]); print(msg); sys.exit(0 if ok else 1)
    else: print(__doc__)
