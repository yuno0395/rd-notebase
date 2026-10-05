"""工程管理の試験データ：案件リポジトリ・工程表（当初計画→承認済みの変更1回）・ロードマップ・やること・週報"""
import os, sys, glob, yaml, json
sys.path.insert(0, os.path.dirname(__file__))
from kv import ROOT, REG, cmd_new, read_note, join_fm, cmd_push, cmd_index
import pm

r = yaml.safe_load(open(REG, encoding='utf-8'))
r['tags']['技術ロードマップ'] = {'owner': 'boss', 'deputy': 'bucho', 'members': ['boss', 'bucho'], 'pdf': True, 'ai': False}
r['holidays'] = ['2026-10-12', '2026-11-03', '2026-11-23', '2026-12-29', '2026-12-30', '2026-12-31', '2027-01-01', '2027-01-04',
                 '2027-01-05', '2027-01-11', '2027-02-11', '2027-02-23', '2027-03-22']
yaml.safe_dump(r, open(REG, 'w', encoding='utf-8'), allow_unicode=True, sort_keys=False)

PV = 'proj-P00001'
pm.make_vault(PV, 'boss')

base = [
 {'id': 'T01', 'name': 'ボトルネック分析', 'start': '2026-09-01', 'end': '2026-09-25', 'owner': 'yamada', 'est': 15},
 {'id': 'M01', 'name': '中間DR', 'date': '2026-10-09', 'milestone': True, 'after': ['T01']},
 {'id': 'G1', 'name': '試作', 'group': True},
 {'id': 'T02', 'name': '案A 試作設計', 'start': '2026-09-28', 'end': '2026-10-23', 'owner': 'yamada', 'est': 15, 'after': ['T01'], 'parent': 'G1'},
 {'id': 'T03', 'name': '試作品製作（外注）', 'start': '2026-10-26', 'end': '2026-11-20', 'owner': 'yamada', 'est': 3, 'alloc': 20, 'after': ['T02'], 'parent': 'G1'},
 {'id': 'T04', 'name': '評価試験', 'start': '2026-11-24', 'end': '2026-12-11', 'owner': 'yamada', 'est': 12, 'after': ['T03'], 'parent': 'G1'},
 {'id': 'M02', 'name': '試作DR', 'date': '2026-12-15', 'milestone': True, 'after': ['T04']},
 {'id': 'T05', 'name': '量産図面', 'start': '2027-01-06', 'end': '2027-02-26', 'owner': 'yamada', 'est': 30, 'after': ['M02']},
 {'id': 'M03', 'name': '量産移管', 'date': '2027-03-15', 'milestone': True, 'after': ['T05']},
]
p = cmd_new(PV, 'schedule', 'P00001 工程表', project='P00001')
fm, _ = read_note(p); sid = fm['id']
fm['tasks'] = base; fm['baselines'] = [{'name': '当初計画', 'approved_by': 'boss', 'at': '2026-09-01', 'reason': '着手時の計画', 'tasks': base}]
open(p, 'w', encoding='utf-8').write(join_fm(fm, '工程表の正本（計画だけ）。進捗・実績は週報とやることから集計する。\n'))
pm.commit(PV, '計画作成|承認:boss|理由:着手時の計画')
cur = json.loads(json.dumps(base))
for t in cur:
    if t['id'] == 'T01': t['end'] = '2026-10-02'
    if t['id'] == 'T02': t.update(start='2026-10-05', end='2026-10-30')
    if t['id'] == 'T03': t.update(start='2026-11-02', end='2026-11-27')
    if t['id'] == 'T04': t.update(start='2026-11-30', end='2026-12-18')
    if t['id'] == 'M02': t['date'] = '2026-12-22'
fm['tasks'] = cur; open(p, 'w', encoding='utf-8').write(join_fm(fm, '工程表の正本（計画だけ）。進捗・実績は週報とやることから集計する。\n'))
pm.commit(PV, '計画変更|承認:boss|区分:見積の誤り|理由:分析対象に駆動部を追加')

# ロードマップ（上司のvault、技術ロードマップの鍵）
rp = cmd_new('vault-boss', 'roadmap', '昇降ステージ 技術ロードマップ', items=[
 {'id': 'R01', 'name': 'X200 改良版', 'start': '2026-04-01', 'end': '2027-09-30', 'budget': 30, 'status': '実行中', 'project': 'P00001', 'gates': [{'name': '量産移管', 'date': '2027-03-15'}]},
 {'id': 'R02', 'name': '次世代 X300', 'start': '2027-10-01', 'end': '2030-03-31', 'budget': 120, 'status': '構想', 'gates': [{'name': '技術確認', 'date': '2028-09-30'}]},
 {'id': 'R03', 'name': '新駆動方式の研究', 'start': '2026-10-01', 'end': '2031-03-31', 'budget': 60, 'status': '計画中', 'gates': [{'name': '原理確認', 'date': '2027-09-30'}, {'name': '試作', 'date': '2029-03-31'}]},
 {'id': 'R04', 'name': 'X300 量産・展開', 'start': '2030-04-01', 'end': '2034-03-31', 'budget': 80, 'status': '構想'},
])
rfm, _ = read_note(rp); rfm['access'] = ['技術ロードマップ']; open(rp, 'w', encoding='utf-8').write(join_fm(rfm, ''))
cmd_push('vault-boss', 'ロードマップ作成')

# 工程表にロードマップ項目を紐づけ
fm, body = read_note(p); fm['roadmap'] = f"{rfm['id']}#R01"; open(p, 'w', encoding='utf-8').write(join_fm(fm, body))
pm.commit(PV, '紐づけ|ロードマップ:R01')

# やること（山田のノートに書く。task:: で工程タスクに紐づく）
V = 'vault-yamada'
T = lambda x: f'{sid}#{x}'
a = cmd_new(V, 'study', '案A 試作設計の検討', project='P00001')
afm, _ = read_note(a)
open(a, 'w', encoding='utf-8').write(join_fm(afm, f"""## 目的
案Aのリブ追加構造を試作図にする。

## やること
- [x] 構想スケッチ [task:: {T('T02')}]
- [x] 剛性の再計算（リブ厚3mm） [task:: {T('T02')}]
- [ ] 部品図 ブラケット 📅 2026-10-14 [task:: {T('T02')}]
- [ ] 部品図 リブ 📅 2026-10-16 [task:: {T('T02')}]
- [ ] 組図・干渉確認 📅 2026-10-23 [task:: {T('T02')}]
- [ ] 中間DR資料 📅 2026-10-08 [task:: {T('M01')}]
- [ ] 外注先へ見積依頼 📅 2026-10-20 [task:: {T('T03')}]
"""))
b = cmd_new(V, 'study', 'ボトルネック分析 作業メモ', project='P00001')
bfm, _ = read_note(b)
open(b, 'w', encoding='utf-8').write(join_fm(bfm, "## やること\n" + ''.join(f"- [x] {x} [task:: {T('T01')}]\n" for x in
     ['現行X100の振動測定', 'FFTで固有値の特定', '剛性計算', '駆動部の追加測定', '中間報告にまとめる'])))
cmd_push(V, 'やること')

# 週報（9月21日週・9月28日週）
pm.cmd_weekly(V, 'P00001', '2026-09-21', [
  {'task': T('T01'), 'forecast_end': '2026-10-02', 'did': '駆動部の追加測定', 'issue': '駆動部も影響。1週延長を申請済み'}])
pm.cmd_weekly(V, 'P00001', '2026-09-28', [
  {'task': T('T01'), 'actual_start': '2026-09-01', 'actual_end': '2026-10-02', 'did': '中間報告にまとめた'},
  {'task': T('T02'), 'actual_start': '2026-10-01', 'forecast_end': '2026-11-04', 'did': '構想スケッチ、剛性の再計算', 'issue': 'リブ形状で外注先と相談が要る'}])
cmd_push(V, '週報')
print('工程表', sid, 'ロードマップ', rfm['id'])
