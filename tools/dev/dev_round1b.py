"""1周目の続き：上司の指示への対応（山田）"""
import os, sys, glob, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from kv import cmd_attach, cmd_push, read_note, join_fm, ROOT, sh
import draw
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt; from matplotlib.patches import Rectangle, Polygon
V='vault-yamada'; VP=os.path.join(ROOT,V); tmp=os.path.join(ROOT,'tmp')
f=lambda pat: glob.glob(os.path.join(VP,'**',pat),recursive=True)[0]
stem=lambda p: os.path.basename(p).replace('.excalidraw.md','').replace('.md','')
sl=f('*中間報告スライド_*'); bn=f('*ボトルネック分析_*'); rp=f('*X200中間報告_*'); st=f('*解決策比較_*'); cl=f('*ブラケット剛性比較_*')

# 設計物の画像（ブラケット 現行／案A）
fig,ax=plt.subplots(1,2,figsize=(7,3))
for a,t,rib in [(ax[0],'current bracket',False),(ax[1],'plan A: rib added',True)]:
    a.add_patch(Rectangle((0,0),1,0.12,fc='#b8c4d0',ec='k')); a.add_patch(Rectangle((0,0),0.12,0.8,fc='#b8c4d0',ec='k'))
    if rib: a.add_patch(Polygon([[0.12,0.12],[0.12,0.6],[0.7,0.12]],fc='#e8a87c',ec='k'))
    a.set_xlim(-.1,1.1); a.set_ylim(-.1,.9); a.set_aspect('equal'); a.axis('off'); a.set_title(t)
plt.tight_layout(); plt.savefig(os.path.join(tmp,'ブラケット案A構造.png'),dpi=110); plt.close()
# 根拠のグラフ（剛性）
plt.figure(figsize=(5,3)); plt.bar(['current','plan A','plan C'],[0.84,2.24,1.64],color=['#9aa3ad','#2f855a','#b7791f'])
plt.ylabel('stiffness [N/um]'); plt.title('bracket stiffness (cantilever model)'); plt.tight_layout()
plt.savefig(os.path.join(tmp,'ブラケット剛性グラフ.png'),dpi=110); plt.close()

img1=cmd_attach(V,os.path.join(tmp,'ブラケット案A構造.png'),sl,origin='社内CAD')
d=draw.load(sl); s5=d.frame('案Aの構造（設計案）',3600,0)
d.text(s5,40,30,'案A：ブラケットにリブを追加',30); d.image(s5,40,90,700,300,img1)
d.text(s5,40,420,'リブで張り出し部のたわみを抑える\n取付部の寸法は変えない（A社仕様を維持）',22); d.save(sl)

img2=cmd_attach(V,os.path.join(tmp,'ブラケット剛性グラフ.png'),bn,origin='社内計算')
d=draw.load(bn); f3=d.frame('根拠：剛性計算',1800,0)
d.text(f3,30,20,'根拠：ブラケット剛性が支配的',28); d.image(f3,30,80,450,270,img2)
d.text(f3,500,100,'片持ちはりで計算\n現行 0.84 N/um\n案A 2.24 N/um\n（約2.6倍）',22)
d.text(f3,30,390,'測定のピッチングモード（18Hz）と\n計算上の固有振動数がほぼ一致\n→ ブラケットのたわみが主因と判断',22); d.save(bn)

cmd_push(V,'上司指示：構造図と根拠を追加')
c=sh('git rev-parse --short HEAD',VP)
S,B=stem(sl),stem(bn)
fm,b=read_note(rp)
body=f"""## 要旨
残留振動のボトルネックはブラケット剛性。案A（リブ追加）で剛性約2.6倍、重量+3%で要求を満たす見込み。試作で整定時間を確認したい。

## スライド（この順でPDFに出力）
![[{S}#F01@{c}]]
![[{S}#F02@{c}]]
![[{B}#F01@{c}]]
![[{B}#F02@{c}]]
![[{B}#F03@{c}]]
![[{S}#F03@{c}]]
![[{S}#F05@{c}]]
![[{S}#F04@{c}]]

## 補足資料
- 解決策の比較と却下理由：[[{stem(st)}]]
- ボトルネック分析：[[{B}]]
- 剛性計算：[[{stem(cl)}]]
"""
fm['based_on']=[f'[[{stem(st)}]]',f'[[{B}]]',f'[[{stem(cl)}]]']
fm['next']='上司の確認後、DRシステムに提出'
open(rp,'w',encoding='utf-8').write(join_fm(fm,body))
cmd_push(V,'報告：根拠のスライドを版固定で引用')
