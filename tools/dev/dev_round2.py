"""2周目：山田が社内に見せてよい資料を選んで開示申請"""
import os, sys, glob
sys.path.insert(0, os.path.dirname(__file__))
from kv import cmd_request, read_note, cmd_push, ROOT
V='vault-yamada'; VP=os.path.join(ROOT,V)
g=lambda pat: glob.glob(os.path.join(VP,'**',pat),recursive=True)[0]
bn=read_note(g('*ボトルネック分析_*'))[0]['id']; sl=read_note(g('*中間報告スライド_*'))[0]['id']
cmd_request(V, g('*X200中間報告_*'), [f'{bn}#F02', f'{bn}#F03', f'{sl}#F03', f'{sl}#F05'],
            ['社内'], '他チームの剛性設計の参考に。顧客要求の数値（スライド#F02）と測定データ（#F01）は含めない')
cmd_push(V, '開示申請')
