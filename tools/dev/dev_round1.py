"""ロールプレイ1周目：開発担当者（山田）の作業"""
import os, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
import kv
from kv import cmd_new, cmd_attach, read_note, join_fm, ROOT
from draw import Drawing
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; import numpy as np
V = 'vault-yamada'; VP = os.path.join(ROOT, V)

def write(p, body=None, **fm_upd):
    fm, b = read_note(p); fm.update(fm_upd)
    open(p, 'w', encoding='utf-8').write(join_fm(fm, body if body is not None else b))

def link(p):  # ノートへのリンク文字列（ファイル名からID部分つき）
    return '[[' + os.path.basename(p).replace('.excalidraw.md', '').replace('.md', '') + ']]'

# --- 素材（測定グラフ、顧客提供図面） ---
tmp = os.path.join(ROOT, 'tmp'); os.makedirs(tmp, exist_ok=True)
t = np.linspace(0, 1, 400)
plt.figure(figsize=(6, 3)); plt.plot(t, 40*np.exp(-3*t)*np.sin(2*np.pi*18*t), lw=1)
plt.xlabel('時間 [s]' if False else 'time [s]'); plt.ylabel('amplitude [um]'); plt.title('X100 residual vibration (measured)')
plt.tight_layout(); plt.savefig(os.path.join(tmp, '現行X100残留振動.png'), dpi=110); plt.close()
from reportlab.pdfgen import canvas
cv = canvas.Canvas(os.path.join(tmp, 'A社取付部仕様.pdf')); cv.drawString(72, 750, 'A-sha mounting interface spec (confidential)'); cv.save()

# 1. デイリー（本人のみ）
d1 = cmd_new(V, 'daily', f'{datetime.date.today()} デイリー')
write(d1, "## 今日やること\n- A社打合せ\n- 現行X100の振動データ整理\n\n## メモ\n- 打合せでA社が整定時間を強く気にしていた。理由は未確認\n")

# 2. 議事録（顧客情報を含むのでA社NDAタグも付与）
mt = cmd_new(V, 'meeting', 'A社 X200要求ヒアリング', project='P00001')
write(mt, "## 参加者\nA社 設計部 2名、山田\n\n## 決定事項\n- 停止後の残留振動を現行X100比で30%以上低減\n- 整定時間 0.3s 以内\n- 重量増加は5%以内、コスト増加は3%以内\n- 取付部の寸法はA社仕様を維持（添付参照）\n\n## 宿題\n- ボトルネックの洗い出し（山田、来週）\n",
      access=['P00001-team', 'A社-NDA'], summary='A社からX200の要求を聞き取り。残留振動30%低減、整定0.3s以内が主要求')
cmd_attach(V, os.path.join(tmp, 'A社取付部仕様.pdf'), mt, origin='顧客提供（A社、NDA-2026-015）')

# 3. 要求（顧客名を除いて目標値だけにし、チームに公開）
rq = cmd_new(V, 'req', '残留振動30%低減', project='P00001', parts=['482011-ST2A'])
write(rq, f"## 要求\n停止後の残留振動振幅を、現行X100比で30%以上低減する。整定時間は0.3s以内。\n\n## 出所\n顧客要求（議事録 {link(mt)}）\n\n## 合否判定基準\n| 項目 | 現行X100 | 目標 |\n|---|---|---|\n| 残留振動振幅 | 40 um | 28 um 以下 |\n| 整定時間 | 0.45 s | 0.30 s 以下 |\n| 重量 | 12.0 kg | 12.6 kg 以下 |\n",
      summary='残留振動 40→28um以下、整定 0.45→0.30s以下、重量+5%以内', derived_from=[link(mt)])

# 4. ボトルネック分析の図
bn = cmd_new(V, 'drawing', 'X200ボトルネック分析', project='P00001', parts=['482011-ST2A', '482015-BR1C'])
img = cmd_attach(V, os.path.join(tmp, '現行X100残留振動.png'), bn, origin='社内測定')
d = Drawing()
f1 = d.frame('現行構造と振動', 0, 0)
d.text(f1, 30, 20, '現行X100：残留振動の測定結果', 28)
d.image(f1, 30, 80, 480, 240, img)
d.text(f1, 540, 100, '18Hzで振動\n約0.45sで整定\n振幅 40um', 22)
d.rect(f1, 30, 360, 740, 160, bg='#eef3f8')
d.text(f1, 50, 380, '支配的な振動モード：ステージ全体のピッチング\nガイド支持スパンが短く、ブラケットがたわむ', 22)
f2 = d.frame('ボトルネック候補', 900, 0)
d.text(f2, 30, 20, 'ボトルネック候補', 28)
for i, (name, ev) in enumerate([('ブラケット剛性', '寄与 大（計算で確認）'), ('ガイド支持スパン', '寄与 大'), ('モータ制御ゲイン', '寄与 小（制御側で別途）')]):
    d.rect(f2, 40, 90 + i*140, 300, 90, bg='#fff4e5' if i < 2 else 'transparent')
    d.text(f2, 60, 115 + i*140, name, 24)
    d.arrow(f2, 340, 135 + i*140, 440, 135 + i*140)
    d.text(f2, 460, 120 + i*140, ev, 22)
d.save(bn); write(bn, summary='現行X100の残留振動はピッチングモードが支配的。ブラケット剛性とガイド支持スパンが主なボトルネック')

# 5. 計算（試験運用ではPythonかExcel添付。ここはPython）
os.makedirs(os.path.join(VP, '30_calc'), exist_ok=True); cs = os.path.join(VP, '30_calc', 'bracket_stiffness.py')
open(cs, 'w').write("# 片持ちはりモデルでブラケット剛性を比較\nE=70e9  # A5052 [Pa]\nL=0.12\nfor name,b,h in [('現行',0.040,0.008),('案A リブ追加',0.040,0.011),('案C 板厚増',0.040,0.010)]:\n    I=b*h**3/12; k=3*E*I/L**3\n    print(f'{name}: k={k/1e6:.2f} N/um')\n")
import subprocess; res = subprocess.run(['python3', cs], capture_output=True, text=True).stdout
cl = cmd_new(V, 'calc', 'ブラケット剛性比較', project='P00001', parts=['482015-BR1C'])
write(cl, f"## 目的\nボトルネック候補のうち、ブラケット剛性の改善量を見積もる。\n\n## 条件\n片持ちはりモデル、A5052、張り出し120mm。スクリプト：`30_calc/bracket_stiffness.py`\n\n## 結果\n```\n{res}```\n案Aで剛性は約2.6倍。ただし重量は+3%。\n",
      summary='ブラケット剛性：案A リブ追加で約2.6倍、案C 板厚増で約1.95倍', based_on=[link(bn)])

# 6. 検討（解決策の比較）
st = cmd_new(V, 'study', 'X200残留振動の解決策比較', project='P00001', parts=['482015-BR1C'])
write(st, f"## 目的\n{link(rq)} を満たす構造を選ぶ。\n\n## 前提\n![[{os.path.basename(bn).replace('.excalidraw.md','')}#F02]]\n\n## 検討\n| 案 | 内容 | 剛性 | 重量 | コスト | 評価 |\n|---|---|---|---|---|---|\n| A | ブラケットにリブ追加 | 2.6倍 | +3% | +1% | ◎ |\n| B | ガイド支持スパン拡大 | 1.8倍相当 | +6% | +4% | △ |\n| C | ブラケット板厚増 | 1.95倍 | +4% | +1% | ○ |\n\n計算：{link(cl)}\n\n## 結論\n案Aを第一候補とし、試作で整定時間を確認する。\n\n## 却下した案と理由\n- 案B：重量+6%で要求（+5%以内）を超える。取付部の寸法もA社仕様から変わる\n- 案C：剛性向上が案Aより小さく、重量増は大きい\n",
      progress='レビュー待ち', next='案Aの試作手配と整定時間の測定計画', summary='案A（リブ追加）を第一候補。案Bは重量超過で却下',
      derived_from=[link(rq)], based_on=[link(bn), link(cl)])

# 7. 報告スライド（Excalidraw、PDF出力用）と報告ノート
sl = cmd_new(V, 'drawing', 'X200中間報告スライド', project='P00001')
d = Drawing()
s1 = d.frame('表紙', 0, 0); d.text(s1, 60, 200, 'X200 残留振動低減\n中間報告', 44); d.text(s1, 60, 400, '開発担当 山田', 22)
s2 = d.frame('要求', 900, 0); d.text(s2, 40, 30, '顧客要求（目標値）', 30)
d.text(s2, 60, 120, '残留振動  40um → 28um以下\n整定時間  0.45s → 0.30s以下\n重量      +5%以内\nコスト    +3%以内', 26)
s3 = d.frame('解決策の比較', 1800, 0); d.text(s3, 40, 30, '解決策の比較', 30)
for i, (n_, c_) in enumerate([('案A リブ追加  剛性2.6倍 重量+3%  ◎', '#e6f4ea'), ('案B スパン拡大  重量+6%  要求超過で却下', '#fde8e8'), ('案C 板厚増  剛性1.95倍 重量+4%  ○', 'transparent')]):
    d.rect(s3, 40, 110 + i*120, 720, 80, bg=c_); d.text(s3, 60, 135 + i*120, n_, 24)
s4 = d.frame('次のステップ', 2700, 0); d.text(s4, 40, 30, '次のステップ', 30)
d.text(s4, 60, 120, '1. 案Aの試作手配\n2. 整定時間の測定（目標0.30s）\n3. 結果を次回DRで報告', 26)
d.save(sl)
rp = cmd_new(V, 'report', 'X200中間報告', project='P00001')
write(rp, f"## 要旨\n残留振動のボトルネックはブラケット剛性とガイド支持スパン。案A（リブ追加）を第一候補とし、試作で確認する。\n\n## 内容\n![[{os.path.basename(sl).replace('.excalidraw.md','')}]]\n\n根拠：{link(st)}、{link(bn)}\n",
      progress='レビュー待ち', next='上司の確認後、DRシステムに提出', summary='案A（リブ追加）を第一候補に試作へ進めたい。確認をお願いします',
      based_on=[link(st)])
print('1周目 作業完了')
