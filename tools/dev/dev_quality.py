"""試作環境に、要求・試験・ゲート・不具合・文書の承認の例を足す台本（tools/setup_demo.py から呼ぶ。何度実行してもよい）
  - 要求「残留振動30%低減」に出所・合否基準を入れ、レビュー待ちに
  - 要求「重量増 5%以内」（新規）。試験なし → 対応表で「試験なし」
  - 試験「案A試作 整定時間の測定」（verifies・合格）
  - ゲート「試作DR」（M02）：要求と検討を items に。上司が要求を承認（承認ノート）→ 1/2 承認済み
  - 不具合「試作機のガイド摩耗」（affects 要求）
"""
import os, sys, glob, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import kv, approve

ROOT = kv.ROOT
def find(vp, nid):
    for p in glob.glob(os.path.join(ROOT, vp, '**', '*.md'), recursive=True):
        fm, body = kv.read_note(p)
        if fm.get('id') == nid: return p, fm, body
    return None, None, None

def put(vp, name, fm, body):
    p = os.path.join(ROOT, vp, '10_notes', name)
    if not os.path.exists(p): kv.write_note(p, fm, body)
    return p

def main():
    y = 'vault-yamada'; base = {'owner': 'yamada', 'project': 'P00001', 'access': ['P00001-team'], 'created': '2026-10-08', 'updated': '2026-10-08'}
    p, fm, body = find(y, '261004-nn7zu')   # 要求：残留振動30%低減
    if fm and not fm.get('criteria'):
        fm.update(source_kind='顧客', source='要求ヒアリング（議事録）', criteria='残留振動 28um 以下・整定 0.30s 以下・重量 12.6kg 以下', priority='高', status='review')
        kv.write_note(p, fm, body)
    put(y, '261008_重量増 5%以内.md', {'id': '261008-wght2', 'type': 'req', **base, 'status': 'draft', 'summary': '剛性を上げても重量増は5%以内',
        'source_kind': '社内', 'source': '設計標準', 'criteria': '12.6kg 以下', 'priority': '中'},
        '## Requirement\n剛性を上げる対策でも、可動部の重量増は現行比 5% 以内。\n')
    put(y, '261008_案A試作 整定時間の測定.md', {'id': '261008-tst2a', 'type': 'test', **base, 'status': 'draft', 'summary': '整定 0.27s・残留振動 25um で合格',
        'verifies': ['[[261004_残留振動30%低減]]'], 'test_result': '合格', 'tested': str(__import__('datetime').date.today())},
        '## Conditions\nストローク 200mm・最大加速度\n\n## Result\n整定 0.27s、残留振動 25um\n')
    p, fm, body = find(y, '261004-a6msx')   # 案A 試作設計の検討 → 要求から派生
    if fm and not fm.get('derived_from'):
        fm['derived_from'] = ['[[261004_残留振動30%低減]]', '[[261008_重量増 5%以内]]']; kv.write_note(p, fm, body)
    put(y, '261008_試作DR.md', {'id': '261008-gate2', 'type': 'gate', **base, 'status': 'review', 'summary': '試作に進めるかの判断',
        'milestone': 'M02', 'items': ['[[261004_残留振動30%低減]]', '[[261004_案A 試作設計の検討]]']},
        '## Criteria to pass\n要求と設計の検討が承認済みであること\n')
    put(y, '261009_試作機のガイド摩耗.md', {'id': '261009-wear2', 'type': 'issue', **base, 'status': 'draft', 'summary': '試作機の評価でガイドに摩耗痕',
        'affects': ['[[261004_残留振動30%低減]]'], 'parts': ['482011-ST2A'], 'state': 'open'}, '## What happened\n1万回の往復でガイドに摩耗痕\n')
    # 上司が要求を承認（上司の vault に承認ノート）。承認の版は今の要求の版
    have = [kv.read_note(q)[0] for q in glob.glob(os.path.join(ROOT, 'vault-boss', '10_notes', '*.md'))]
    if not any(f.get('type') == 'approval' and f.get('about') == '261004-nn7zu' for f in have):
        return 'need-approval'
    return 'ok'

def approve_req():
    import sqlite3
    c = sqlite3.connect(kv.DB); t = approve.find_target(c, '261004-nn7zu')
    approve.write(os.path.join(ROOT, 'vault-boss'), 'boss', t, '承認', '基準は顧客と合意済み')

if __name__ == '__main__':
    if sys.argv[1:] == ['approve']: approve_req()
    else: print(main())
