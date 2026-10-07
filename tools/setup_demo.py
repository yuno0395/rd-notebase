#!/usr/bin/env python3
"""サンプルデータから試作環境を作る（サーバ側のGitリポジトリ・索引DB・Web閲覧）
  python3 tools/setup_demo.py          : 作る（既にあれば何もしない）
  python3 tools/setup_demo.py --reset  : 作り直す
作るもの（リポジトリ直下。Git管理外）:
  vault-yamada/ vault-boss/ vault-staff/ proj-P00001/   各人のvaultと案件リポジトリ（サンプルデータのコピー）
  server/      サーバ側のGitリポジトリ、タグ台帳（registry.yml）、索引DB
  site/        Web閲覧（上司用 index.html、山田用 yamada.html、一般社員用 staff.html）
"""
import os, sys, shutil, subprocess, glob, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SAMPLE = os.path.join(ROOT, 'sample-data'); SRV = os.path.join(ROOT, 'server')
GA = os.path.join(ROOT, 'sample-vault', '.gitattributes')

def sh(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if r.returncode: sys.exit(f'失敗: {cmd}\n{r.stderr}')
    return r.stdout

def main():
    vaults = sorted(d for d in os.listdir(SAMPLE) if os.path.isdir(os.path.join(SAMPLE, d)))
    if '--reset' in sys.argv:
        for d in vaults + ['server', 'site', 'out']: shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    if os.path.exists(SRV): sys.exit('既に作成済みです（作り直すには --reset）')
    sh('git lfs version')                      # Git LFS が必要
    os.makedirs(SRV)
    shutil.copy(os.path.join(ROOT, 'config', 'registry.yml'), os.path.join(SRV, 'registry.yml'))
    ids = set()
    import hashlib
    LFS_EXT = ('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.xlsx', '.docx', '.pptx', '.zip')
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1')
    for v in vaults:
        vp = os.path.join(ROOT, v); bare = os.path.join(SRV, v + '.git'); src = os.path.join(SAMPLE, v)
        bundle = os.path.join(SAMPLE, v + '.bundle')
        if os.path.exists(bundle):        # 履歴つき（版の固定・計画変更の経緯が再現される）
            sh(f'git init -q --bare -b main "{bare}"'); sh(f'git -C "{bare}" fetch -q "{bundle}" main:main')
            os.makedirs(vp); sh('git init -q -b main', vp); sh(f'git remote add origin "{bare}"', vp)
            subprocess.run('git fetch -q origin && git checkout -q -B main origin/main', cwd=vp, shell=True, check=True, env=env)
            for p in glob.glob(os.path.join(src, '**', '*'), recursive=True):   # LFSの中身をサーバ側に置き、手元にも実物を置く
                if os.path.isfile(p) and p.lower().endswith(LFS_EXT):
                    data = open(p, 'rb').read(); oid = hashlib.sha256(data).hexdigest()
                    od = os.path.join(bare, 'lfs', 'objects', oid[:2], oid[2:4]); os.makedirs(od, exist_ok=True)
                    open(os.path.join(od, oid), 'wb').write(data)
                    shutil.copy(p, os.path.join(vp, os.path.relpath(p, src)))
        else:
            shutil.copytree(src, vp)
            sh(f'git init -q --bare -b main "{bare}"')
            sh('git init -q -b main', vp); sh(f'git remote add origin "{bare}"', vp)
        shutil.copy(GA, os.path.join(vp, '.gitattributes'))
        shutil.rmtree(os.path.join(vp, '00_inbox'), ignore_errors=True)   # inboxは置かない（未分類はプロパティで見分ける）
        for f in ('01_daily', '10_notes', '30_calc', '40_attachments'):
            os.makedirs(os.path.join(vp, f), exist_ok=True)
            if not os.listdir(os.path.join(vp, f)): open(os.path.join(vp, f, '.gitkeep'), 'w').close()
        sh('git lfs install --local', vp)
        sh('git config user.name demo && git config user.email demo@example.com', vp)
        sh('git add -A', vp)
        if sh('git status --porcelain', vp).strip(): sh('git commit -qm "サンプルデータの初期設定"', vp)
        sh('git push -q origin main', vp)
        for p in glob.glob(os.path.join(vp, '**', '*.md'), recursive=True):
            m = re.search(r'^id: (\S+)', open(p, encoding='utf-8').read(), re.M)
            if m: ids.add(m.group(1).strip("'\""))
    open(os.path.join(SRV, 'allocated_ids.txt'), 'w').write('\n'.join(sorted(ids)) + '\n')
    py = sys.executable
    for v in vaults:   # サンプルデータは以前の名前の形（作成日_タイトル_hash）。利用者の PC と同じく末尾の乱数を外す（改名の履歴が残る）
        vp = os.path.join(ROOT, v)
        for step, msg in (('drop-hash', 'ファイル名の末尾の乱数と .excalidraw を外す'), ('drop-title', 'プロパティ title を外す（題名はファイル名）')):   # 改名と中身の変更は別のコミットに（改名の履歴が辿れるように）
            sh(f'"{py}" tools/kv.py {step} {v}', ROOT); sh('git add -A', vp)
            if sh('git status --porcelain', vp).strip(): sh(f'git commit -qm "{msg}"', vp)
        sh('git push -q origin main', vp)
    sh(f'"{py}" tools/kv.py index', ROOT)
    for v in vaults:   # 案件の工程表は dotpm の形（取りまとめ役が Obsidian で直す）にしておく
        if v.startswith('proj-') and not glob.glob(os.path.join(ROOT, v, '_tasks')): print(sh(f'"{py}" tools/pm.py migrate {v}', ROOT).strip().splitlines()[-1])
    for u, f in (('boss', 'index.html'), ('yamada', 'yamada.html'), ('staff', 'staff.html')):
        print(sh(f'"{py}" tools/view.py build {u} {f}', ROOT).strip())
    print('完了。site/index.html（上司）・site/yamada.html（山田）・site/staff.html（一般社員）をブラウザで開いてください')

if __name__ == '__main__':
    main()
