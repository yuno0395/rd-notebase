"""Web閲覧のページ生成。1ページ＝1関数。共通部品は render.py、権限は access.py"""
import difflib
from core import *
from access import *
from render import *
import pm_pages

CUSTOMER_WORDS = None  # 顧客名など、公開前に注意すべき語（台帳の customer_words）

def caution(text):
    """公開の確認時に「顧客情報の可能性」を出すか"""
    return any(w in (text or '') for w in CUSTOMER_WORDS or [])

def frame_text(n, fid):
    frs, els = frames_of(n)
    f = next((f for f in frs if (f.get('customData') or {}).get('kvFrame') == fid), None)
    return f, ' '.join(str(e.get('text', '')) for e in els if f and e.get('frameId') == f['id'])

CHECK = ('<p class="rl">確認項目</p><label class="chk"><input type="checkbox" class="ck" value="顧客情報なし"> 顧客情報なし</label>')
def reason_box(key):
    return (CHECK + f'<label class="rl" for="r-{key}">コメント（確認項目にチェックがない場合は必須）</label>'
            f'<textarea id="r-{key}" rows="2"></textarea>')
RESULT = '<p class="gmsg" aria-live="polite"></p><pre class="gout" hidden></pre>'

class Site:
    def __init__(self, user):
        self.user = user; self.c = db(); self.r = reg(); self.notes = all_notes(self.c)
        global CUSTOMER_WORDS; CUSTOMER_WORDS = self.r.get('customer_words', [])
        self.mgr = is_mgr(user)
        self.owned = {t for t, g in self.r['tags'].items() if user in (g['owner'], g.get('deputy'))}
        self.vis = {}
        for i, n in self.notes.items():
            if n['type'] in ('attachment', 'grant'): continue
            if can_see(user, n['access']): self.vis[i] = n
            else:
                gv = granted(user, self.notes, i)
                if gv: m = dict(at_version(n, gv)); m['granted'] = gv; self.vis[i] = m   # 公開された時点の版を表示
        self.pages = {}; self.todo = 0; self.pm_summary = {}
        self.uname = lambda u: self.r['users'].get(u, u)
        self.rv = {}   # 対象ノートID → 見られるコメント
        for n in self.vis.values():
            if n['type'] == 'comment': self.rv.setdefault(json.loads(n['fm'])['about'].split('#')[0], []).append(n)

    # ---------- コメント（やること付き＝指摘も含む） ----------
    TASK_RE = re.compile(r'^- \[( |x)\] (.*?) 📅 (\S+)', re.M)
    @staticmethod
    def is_open(n): return bool(re.search(r'^- \[ \]', n['body'], re.M))
    def rv_item(self, n, with_target=False):
        fm = json.loads(n['fm']); m = self.TASK_RE.search(n['body'])
        if m: st, text = ('対応済み', 'done') if m.group(1) == 'x' else ('未対応', 'open'), m.group(2)
        else:
            st = ('コメント', 'note'); text = re.sub(r'^!\[\[.*$', '', n['body'].split('## 内容', 1)[-1], flags=re.M).strip()
        pics = thumb_html(n, self.notes)
        tgt = fm['about'].replace('#', '.')
        where = f'<a href="#n-{tgt}">{esc(fm.get("about_label"))}</a>' if with_target or '#' in fm['about'] else ''
        task = (f'担当 {esc(self.uname(fm.get("assignee")))} ・ 期限 <span class="mono">{esc(fm.get("due"))}</span> ・ ' if m else '')
        return (f'<li class="rv {st[1]}"><div><span class="rvst">{st[0]}</span> {where}</div>'
                f'<div class="rvt">{esc(text)}</div>'
                f'<div class="sub">{task}{esc(self.uname(n["owner"]))} {esc(n["updated"])} ・ <a href="#n-{n["id"]}">コメントのノート</a></div>'
                f'<div class="rvpics">{pics}</div></li>')

    def rv_targets(self, n):
        """コメントの対象にできるもの：ノート自体、図のフレーム、埋め込んだ添付・引用フレーム"""
        out = [{'t': n['id'], 'l': f'このノート全体（{n["title"]}）'}]
        if has_drawing(n):
            for f in frames_of(n)[0]:
                fid = (f.get('customData') or {}).get('kvFrame'); out.append({'t': f"{n['id']}#{fid}", 'l': f"フレーム #{fid} {f.get('name', '')}"})
        hm = by_hash(self.notes); seen = {o['t'] for o in out}
        for row in self.c.execute("select dst, frame from links where src=? and kind='cites'", (n['id'],)):
            tn = hm.get(row['dst'])
            if not tn: continue
            t = tn['id'] + (row['frame'] or '')
            if t in seen or not (ok(self.user, self.notes, tn) or granted(self.user, self.notes, t)): continue
            seen.add(t)
            out.append({'t': t, 'l': ('添付 ' if tn['type'] == 'attachment' else '引用 ') + tn['title'] + (f' {row["frame"]}' if row['frame'] else '')})
        return out

    def rv_button(self, n):
        d = esc(json.dumps(self.rv_targets(n), ensure_ascii=False))
        return f'<button type="button" class="rvb rvmain" data-rv="{d}" data-owner="{esc(n["owner"])}">＋ コメント</button>'

    def rv_box(self, nid):
        rs = sorted(self.rv.get(nid, []), key=lambda r: (not self.is_open(r), r['updated']))
        if not rs: return ''
        o = len([r for r in rs if self.is_open(r)])
        return (f'<section class="rvbox"><h2>コメント（{len(rs)}件{f"・未対応のやること {o}件" if o else ""}）</h2><ul class="rvs">'
                + ''.join(self.rv_item(r) for r in rs) + '</ul></section>')

    def fr_rv(self, n, f):
        fid = (f.get('customData') or {}).get('kvFrame'); t = f"{n['id']}#{fid}"
        c = len([r for r in self.rv.get(n['id'], []) if json.loads(r['fm'])['about'] == t])
        return (f' <span class="rvn">コメント {c}</span>' if c else '') + f' <button type="button" class="rvb" data-pre="{esc(t)}">＋ コメント</button>'

    def reviews(self):
        allr = [n for n in self.vis.values() if n['type'] == 'comment']
        if not allr: return
        opn = sorted([n for n in allr if self.is_open(n)], key=lambda n: json.loads(n['fm']).get('due', ''))
        mine = [n for n in opn if json.loads(n['fm']).get('assignee') == self.user]
        rest = sorted([n for n in allr if n not in opn], key=lambda n: n['updated'], reverse=True)
        li = lambda ns: '<ul class="rvs">' + ''.join(self.rv_item(n, True) for n in ns) + '</ul>'
        self.pages['comments'] = ('<p class="crumb"><a href="#home">案件</a> / コメント</p><h1>コメント</h1>'
            + (f'<h2>あなたのやること（{len(mine)}件）</h2>{li(mine)}' if mine else '')
            + (f'<h2>未対応のやること（{len(opn)}件・期限の近い順）</h2>{li(opn)}' if opn else '')
            + f'<details class="done" open><summary>コメント・対応済み（{len(rest)}件）</summary>{li(rest)}</details>')

    # ---------- 部品 ----------
    def scope(self, n, frame=None):
        return scope_html(self.notes, self.notes[n['id']], frame) if self.mgr else ''

    def prog(self, n):
        pg = n.get('progress') or ''
        return f'<span class="prog {PROG.get(pg, "")}">{esc(pg)}</span>' if pg else ''

    def note_row(self, n, lvl=0, kind=''):
        ind = f' style="padding-left:{10 + lvl * 22}px"' if lvl else ''
        lab = f'<span class="kind">{KIND_JA.get(kind, kind)}</span>' if kind else ''
        cls = ' class="parent"' if n['type'] == 'report' else ' class="child"' if lvl else ''
        return (f'<tr{cls}><td{ind}>{"└ " if lvl else ""}<span class="type">{TYPE_JA.get(n["type"], n["type"])}</span>{lab}</td>'
                f'<td><a href="#n-{n["id"]}">{esc(n["title"])}</a> {self.scope(n)}<div class="sum">{esc(n["summary"])}</div></td>'
                f'<td>{esc(self.uname(n["owner"]))}</td><td>{self.prog(n)}</td><td>{esc(n["next"])}</td><td>{upd_html(n, n.get("granted"))}</td></tr>')

    # ---------- 案件 ----------
    def home_and_projects(self):
        home = []
        if self.mgr and self.todo:
            home.append(f'<a class="todo" href="#grants">確認待ちが {self.todo} 件あります</a>')
        if SELF:   # 自分の vault だけを見る時：自分のノートを全部、更新の新しい順に
            mine = sorted([n for n in self.vis.values() if n['type'] not in ('comment', 'grant', 'attachment')], key=lambda n: (str(n['updated']), n['id']), reverse=True)
            unsorted = [n for n in mine if not n['type']]
            home.append(f'<h1>自分のノート</h1><p class="lead">{len(mine)} 件・更新の新しい順' + (f'（未分類 {len(unsorted)} 件）' if unsorted else '') + '。Obsidian がなくても読める控えです</p>'
                        '<div class="tablewrap"><table class="cardable"><thead><tr><th>種類</th><th>ノート</th><th>担当</th><th>状況</th><th>次にやること</th><th>更新</th></tr></thead><tbody>'
                        + ''.join(self.note_row(n) for n in mine) + '</tbody></table></div>')
        cards = []
        for pid, p in self.r['projects'].items():
            ns = [n for n in self.vis.values() if n['project'] == pid and n['type'] not in ('comment', 'schedule', 'planreq', 'weekly') and not json.loads(n['fm']).get('gantt')]
            if SELF and not ns: continue
            wait = len([n for n in ns if n.get('progress') == 'レビュー待ち'])
            cards.append(f'<a class="card" href="#p-{pid}"><span class="mono">{pid} ・ {esc(p.get("short", ""))}</span><b>{esc(p["name"])}</b>'
                        f'<span>{len(ns)} 件のノート{f" ・ レビュー待ち {wait} 件" if wait else ""}</span>'
                        + (f'<span class="pmsum">{esc(self.pm_summary[pid])}</span>' if pid in self.pm_summary else '') + '</a>')
            rows, used = [], set()
            for rp in sorted([n for n in ns if n['type'] == 'report'], key=lambda n: n['updated'], reverse=True):
                rows.append(self.note_row(rp)); used.add(rp['id'])
                for cid, kind, d in children(self.c, self.notes, rp['id']):
                    ch = self.notes[cid]
                    if ok(self.user, self.notes, ch): rows.append(self.note_row(self.vis.get(cid, ch), d, kind)); used.add(cid)
                    else: rows.append(f'<tr class="child"><td style="padding-left:{10 + d * 22}px" colspan="6">└ {lock_html(ch["access"], "非公開の資料", ch["title"], ch["id"])}</td></tr>')
            rest = [n for n in ns if n['id'] not in used]
            if rest:
                rows.append('<tr class="sep"><td colspan="6">報告に使われていない作業ノート</td></tr>')
                rows += [self.note_row(n) for n in sorted(rest, key=lambda n: n['updated'], reverse=True)]
            self.pages[f'p-{pid}'] = (f'<p class="crumb"><a href="#home">案件</a> / {pid}</p><h1>{esc(p["name"])}</h1>'
                f'<p class="lead">状態 {esc(p["status"])} ・ 責任者 {esc(self.uname(p["owner"]))}</p>'
                + ''.join(f'<p><a class="btn" href="#g-{s["id"]}">工程表を見る</a></p>' for s in self.vis.values() if s['type'] == 'schedule' and s['project'] == pid)
                + '<div class="tablewrap"><table class="cardable"><thead><tr><th>種類</th><th>ノート</th><th>担当</th><th>状況</th><th>次にやること</th><th>更新</th></tr></thead><tbody>'
                + ''.join(rows) + '</tbody></table></div>')
        if cards or not SELF: home.append('<h1>案件</h1><div class="cards">' + ''.join(cards) + '</div>')
        home.append('<p><a class="btn" href="#week">今週の更新を見る</a></p>')
        self.pages['home'] = ''.join(home)

    # ---------- 今週の更新：確認待ちを先頭に ----------
    def week(self):
        ws = str(week_start())
        wk = sorted([n for n in self.vis.values() if n['updated'] >= ws and n['type'] in ('study', 'report', 'req', 'calc', 'meeting', 'drawing')],
                    key=lambda n: n['updated'], reverse=True)
        def li(n):
            nx = f'<div class="nx">{self.prog(n)} {esc(n["next"])}</div>' if n.get('progress') else ''
            return (f'<li>{nx}<span class="type">{TYPE_JA.get(n["type"])}</span><a href="#n-{n["id"]}">{esc(n["title"])}</a> '
                    f'<span class="who">{esc(self.uname(n["owner"]))}</span><div class="sum">{esc(n["summary"])}</div></li>')
        waits = [n for n in wk if n.get('progress') == 'レビュー待ち']; others = [n for n in wk if n not in waits]
        self.pages['week'] = (f'<p class="crumb"><a href="#home">案件</a> / 今週</p><h1>今週の更新</h1><p class="lead">{ws} 以降 {len(wk)} 件</p>'
            + (f'<h2>レビュー待ち（{len(waits)}件）</h2><ul class="updates wait">{"".join(map(li, waits))}</ul>' if waits else '')
            + f'<h2>その他の更新（{len(others)}件）</h2><ul class="updates">{"".join(map(li, others))}</ul>')

    # ---------- ノート ----------
    def note_pages(self):
        back = {}
        for row in self.c.execute('select src,dst,kind from links'):
            back.setdefault(row['dst'], []).append((row['src'], row['kind']))
        for nid, n in self.vis.items():
            fm = json.loads(n['fm']); u = self.user
            if has_drawing(n):
                frs, els = frames_of(n)
                body = '<div class="slides">' + ''.join(
                    f'<figure class="slide" id="fr-{(f.get("customData") or {}).get("kvFrame", "")}"><div class="scopebar">{self.scope(n, "#" + (f.get("customData") or {}).get("kvFrame", ""))}</div>'
                    f'{svg_frame(n, f, els, u, self.notes)}<figcaption>{"#" + (f.get("customData") or {}).get("kvFrame") + " " if (f.get("customData") or {}).get("kvFrame") else ""}{esc(f.get("name", ""))}{self.fr_rv(n, f)}</figcaption></figure>'
                    for f in frs) + '</div>'
                txt = text_part(n['body'])          # 図付きノート：前半の文章も本文として出す
                if txt: body = render_body(dict(n, body=txt), u, self.notes) + '<h2 class="figh">図</h2>' + body
            else:
                LOCKS.clear(); body = render_body(n, u, self.notes)
                if LOCKS:
                    acc = sorted({t for a in LOCKS for t in json.loads(a)})
                    body = f'<div class="lockbox">{lock_html(acc, f"非公開の資料 {len(LOCKS)} 件")} 非公開の資料 {len(LOCKS)} 件</div>' + body
            link = lambda i: (f'<a href="#n-{i}">{esc(self.notes[i]["title"])}</a>' if ok(u, self.notes, self.notes[i])
                              else lock_html(self.notes[i]['access'], '非公開の資料', self.notes[i]['title'], i))
            rel = ''
            for k, ja in (('derived_from', '元の要求'), ('based_on', '根拠'), ('verifies', '検証')):
                ids = [by_hash(self.notes).get(hash_of(str(v).strip('[]'))) for v in fm.get(k) or []]
                if ids: rel += f'<div><span class="k">{ja}</span> ' + '、'.join(link(x['id']) for x in ids if x) + '</div>'
            parts = ' '.join(f'<a class="chip" href="#part-{esc(p)}">品番 {esc(p)}</a>' for p in fm.get('parts') or [])
            fam = ''
            if n['type'] == 'report':
                ch = children(self.c, self.notes, nid)
                fam = (f'<div class="family"><b>この報告の補足資料（{len(ch)}件）</b><ul>'
                       + ''.join(f'<li><span class="kind">{KIND_JA.get(k, k)}</span>{link(i)}</li>' for i, k, d in ch) + '</ul></div>')
            else:
                ps = [p for p in parents(self.c, self.notes, nid) if ok(u, self.notes, p)]
                if ps: fam = '<div class="family up">この資料を使っている報告：' + '、'.join(f'<a href="#n-{p["id"]}">{esc(p["title"])}</a>' for p in ps) + '</div>'
            bl = [self.notes.get(s) for s in dict.fromkeys(s for s, k in back.get(nid.split('-')[1], []) if s != nid)]   # 同じノートからの複数のリンクは1つに
            bl_html = ''.join(f'<li>{link(b["id"])}</li>' for b in bl if b and b['type'] not in ('grant', 'comment'))
            self.pages[f'n-{nid}'] = (
                f'<p class="crumb"><a href="#home">案件</a> / <a href="#p-{n["project"]}">{esc(n["project"])}</a></p>'
                f'<h1>{"<span class=badge>報告</span>" if n["type"] == "report" else ""}{esc(n["title"])} {self.scope(n)}</h1>'
                f'<dl class="meta"><div><dt>種類</dt><dd>{TYPE_JA.get(n["type"])}</dd></div><div><dt>担当</dt><dd>{esc(self.uname(n["owner"]))}</dd></div>'
                f'<div><dt>更新</dt><dd>{upd_html(n, n.get("granted"))}</dd></div>'
                + (f'<div><dt>状況</dt><dd>{self.prog(n)} {esc(n["next"])}</dd></div>' if n.get('progress') else '')
                + f'<div><dt>ID</dt><dd class="mono">{nid}</dd></div></dl>' + (f'<div class="acts">{self.rv_button(n)}</div>' if n['type'] != 'comment' else '') + fam
                + self.rv_box(nid)
                + (f'<p class="summary">{esc(n["summary"])}</p>' if n['summary'] else '') + (f'<div class="rel">{rel}{parts}</div>' if rel or parts else '')
                + f'<article>{body}</article>' + (f'<h2>このノートを参照しているノート</h2><ul>{bl_html}</ul>' if bl_html else ''))

    # ---------- 公開の相談先（鍵の管理者） ----------
    def keys(self):
        cnt = {}
        for nn in self.notes.values():
            for t in json.loads(nn['access']): cnt[t] = cnt.get(t, 0) + 1
        self.pages['keys'] = ('<p class="crumb"><a href="#home">案件</a> / 相談先</p><h1>公開の相談先</h1>'
            '<p class="lead">🔒の資料を見たい時は、その鍵の管理者（不在なら代理）に文書IDを伝えて依頼してください。</p>'
            '<div class="tablewrap"><table class="cardable"><thead><tr><th>鍵</th><th>管理者</th><th>代理</th><th>期限</th><th>資料</th></tr></thead><tbody>'
            + ''.join(f'<tr><td><span class="tag">{esc(t)}</span></td><td>{esc(self.uname(g["owner"]))}</td><td>{esc(self.uname(g.get("deputy", "")) or "未設定")}</td>'
                      f'<td class="mono">{esc(g.get("expires", "—"))}</td><td class="mono">{cnt.get(t, 0)} 件</td></tr>'
                      for t, g in self.r['tags'].items() if not g.get('hide')) + '</tbody></table></div>')

    # ---------- 確認待ち：更新後の再確認と、部下からの公開申請 ----------
    def approver_of(self, fm):
        return self.user in (fm.get('approvers') or []) + [self.r['tags'][t].get('deputy') for t in self.r['tags']]

    def item(self, t, label, prev, cautious, extra=''):
        badge = '<span class="warn">顧客情報の可能性</span>' if cautious else ''
        return (f'<div class="gitem"><label class="gl"><input type="checkbox" class="gt" value="{esc(t)}" data-label="{esc(label)}" checked> '
                f'<b>{esc(label)}</b> {badge}</label>{extra}{prev}</div>')

    def stale_section(self):
        items = []
        for g in approved_grants(self.notes):
            if not self.approver_of(g): continue
            for t in g.get('approved_targets') or []:
                nid, _, fid = t.partition('#'); tn = self.notes.get(nid)
                if not tn or tn['type'] == 'attachment': continue
                av = g.get('approved_version')
                if ver_info(tn, av)['hash'] == ver_info(tn)['hash']: continue
                if fid and frame_sig(tn, av, fid) == frame_sig(tn, tn['commit_'], fid): continue
                new = ver_info(tn)
                if has_drawing(tn) and fid:
                    f, txt = frame_text(tn, fid); frs, els = frames_of(tn)
                    prev = svg_frame(tn, f, els, self.user, self.notes) if f else ''; summ = '図が更新されました'
                else:
                    d = [l for l in difflib.unified_diff(at_version(tn, av)['body'].splitlines(), tn['body'].splitlines(), lineterm='', n=0)
                         if l[:1] in '+-' and not l.startswith(('+++', '---'))]
                    txt = '\n'.join(l for l in d if l[0] == '+')
                    add, dele = len([l for l in d if l[0] == '+']), len([l for l in d if l[0] == '-'])
                    summ = f'追記 {add} 行・削除 {dele} 行・顧客名 {"あり" if caution(txt) else "なし"}'
                    prev = '<pre class="diff">' + ''.join(f'<span class="{"add" if l[0] == "+" else "del"}">{esc(l)}</span>\n' for l in d[:20]) + '</pre>'
                lab = tn['title'] + (f' #{fid}' if fid else '')
                items.append(self.item(t, lab, prev, caution(txt),
                                       f'<div class="sum"><b>{esc(summ)}</b> ・ {esc(self.uname(new["who"]))} {esc(new["at"])}</div>'))
        if not items: return ''
        self.todo += len(items)
        return ('<section class="grant" data-gid="reapprove"><h2>更新後の再確認（' + str(len(items)) + '件）</h2>'
                '<p class="lead">社内には公開した時点の版を見せています。変更点を確認し、最新版を社内に公開してよいものを選んでください。</p>'
                '<div class="gitems">' + ''.join(items) + '</div>' + reason_box('reapprove')
                + '<div class="gbtns"><button class="ok" data-act="approve">選択した資料の最新版を社内に公開する</button></div>' + RESULT + '</section>')

    def request_section(self, g):
        fm = json.loads(g['fm']); items = []
        for t in fm['targets']:
            nid, _, fid = t.partition('#'); tn = self.notes.get(nid)
            if not tn: continue
            if has_drawing(tn) and fid:
                f, txt = frame_text(tn, fid); frs, els = frames_of(tn)
                prev = svg_frame(tn, f, els, self.user, self.notes) if f else ''; label = f'{tn["title"]} #{fid} {(f or {}).get("name", "")}'
            else:
                txt = tn['body'] if tn['type'] != 'attachment' else tn['title']; prev = ''
                label = (f'添付 {json.loads(tn["fm"]).get("file", tn["title"])}' if tn['type'] == 'attachment' else tn['title'])
            items.append(self.item(t, label, prev, caution(txt + ' ' + tn['title'])))
        aud = ' / '.join(fm.get('audience', []))
        return (f'<section class="grant" data-gid="{g["id"]}"><h2>{esc(fm["title"])}</h2>'
                f'<p class="memo">申請者のメモ：{esc(fm.get("purpose"))}</p>'
                f'<p class="lead">{esc(self.uname(fm.get("requested_by")))} から ・ 見せる相手 <span class="tag">{esc(aud)}</span> ・ {len(items)} 件</p>'
                f'<p><label><input type="checkbox" class="gall" checked> すべて選択</label></p><div class="gitems">{"".join(items)}</div>'
                + reason_box(g['id'])
                + f'<div class="gbtns"><button class="ok" data-act="approve">選択した資料を{esc(aud)}に公開する</button><button class="ng" data-act="reject">申請を却下する</button></div>' + RESULT + '</section>')

    def grants(self):
        mine = [g for g in self.notes.values() if g['type'] == 'grant' and self.approver_of(json.loads(g['fm']))]
        plan = pm_pages.plan_section(self)
        if not mine and not plan: return
        pending = [g for g in mine if json.loads(g['fm']).get('decision') == 'requested']
        done = [g for g in mine if g not in pending]
        stale = self.stale_section()
        self.todo += len(pending)
        state = {'approved': '公開', 'rejected': '却下', 'revoked': '公開をやめた'}
        done_html = ''.join(f'<li><span class="type">{state.get(json.loads(g["fm"]).get("decision"), "")}</span>{esc(json.loads(g["fm"])["title"])}'
                            f' <span class="sub">{esc(json.loads(g["fm"]).get("approved_at", ""))} 理由：{esc(json.loads(g["fm"]).get("reason", ""))}</span></li>'
                            for g in sorted(done, key=lambda g: json.loads(g['fm']).get('approved_at', ''), reverse=True))
        self.pages['grants'] = ('<p class="crumb"><a href="#home">案件</a> / 確認待ち</p><h1>確認待ち</h1>'
            + (plan + stale + ''.join(self.request_section(g) for g in pending) or '<p class="lead">確認待ちはありません。</p>')
            + f'<details class="done"><summary>処理済み（{len(done)}件）</summary><ul>{done_html}</ul></details>')

    # ---------- 見せる相手：検索して変更 ----------
    def scope_tab(self):
        cand = [n for n in self.vis.values() if set(json.loads(n['access'])) & self.owned and not n.get('granted')]
        if not cand: return
        def aud_of(t):
            return sorted({a for g in approved_grants(self.notes) if t in (g.get('approved_targets') or []) for a in g.get('audience', [])})
        def row(t, title, typ, owner, base, au, sub=False):
            q = f'{t} {title} {" ".join(base)} {" ".join(au)}'.lower()
            cur = ' / '.join(base) + (f' ＋公開 {" / ".join(au)}' if au else '')
            return (f'<tr data-q="{esc(q)}" class="{"fr" if sub else ""}"{" hidden" if sub else ""}><td><input type="checkbox" class="sn" value="{esc(t)}" data-label="{esc(title)}" data-before="{esc(cur)}" '
                    f'data-base="{esc(json.dumps(base, ensure_ascii=False))}" data-aud="{esc(json.dumps(au, ensure_ascii=False))}" aria-label="{esc(title)}を選択"></td>'
                    f'<td><span class="type">{esc(typ)}</span><b><a href="#n-{t.replace("#", ".")}">{esc(title)}</a></b><div class="mono idc">{esc(t)}</div></td>'
                    f'<td>{esc(owner)}</td><td>{esc(cur)}</td></tr>')
        rows = []
        for n in sorted(cand, key=lambda n: (n['project'] or '', n['type'])):
            base = json.loads(n['access']); owner = self.uname(n['owner'])
            frs = frames_of(n)[0] if has_drawing(n) else []
            tog = f' <button type="button" class="frtog">フレーム {len(frs)} 件</button>' if frs else ''
            rows.append(row(n['id'], n['title'], TYPE_JA.get(n['type'], n['type']), owner, base, aud_of(n['id'])).replace('</b>', '</b>' + tog, 1))
            for f in frs:
                fid = (f.get('customData') or {}).get('kvFrame'); t = f"{n['id']}#{fid}"
                rows.append(row(t, f"#{fid} {f.get('name', '')}", 'フレーム', owner, base, sorted(set(aud_of(t)) | set(aud_of(n['id']))), True))
        self.pages['scope'] = ('<p class="crumb"><a href="#home">案件</a> / 見せる相手</p><h1>見せる相手の変更</h1>'
            '<p class="lead">あなたが鍵を管理する資料です。文書ID・タイトル・タグで探して選び、見せる相手を変えてください。</p>'
            '<section class="grant" data-gid="scope"><div class="sqbar"><label class="rl" for="sq">探す（文書ID・タイトル・タグ）</label>'
            '<input id="sq" class="sq" type="search" placeholder="例：261004-gzz7r#F02、要求"><p class="sqn"></p></div>'
            '<div class="tablewrap"><table class="cardable"><thead><tr><th><input type="checkbox" class="gall" aria-label="表示中をすべて選択"></th><th>資料</th><th>担当</th><th>今の見せる相手</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div><p class="rl">見せる相手（選んだ資料に共通の設定）</p><div class="tagbox"><p class="sub">資料を選ぶと表示されます</p></div>'
            + reason_box('scope') + '<div class="gbtns"><button class="ok" data-act="scope">見せる相手を変更する</button></div>' + RESULT + '</section>')

    # ---------- 品番 ----------
    def parts(self):
        for row in self.c.execute("select distinct ref from ext where ref like 'part:%'"):
            pn = row['ref'][5:]
            srcs = [self.notes[s['src']] for s in self.c.execute('select distinct src from ext where ref=?', (row['ref'],))
                    if self.notes[s['src']]['type'] not in ('grant', 'attachment')]
            self.pages[f'part-{pn}'] = (f'<p class="crumb"><a href="#home">案件</a> / 品番</p><h1 class="mono">{esc(pn)}</h1><p class="lead">この品番を参照しているノート</p><ul>'
                + ''.join(f'<li><span class="type">{TYPE_JA.get(n["type"])}</span><a href="#n-{n["id"]}">{esc(n["title"])}</a></li>' if ok(self.user, self.notes, n)
                          else f'<li>{lock_html(n["access"], "非公開の資料", n["title"], n["id"])}</li>' for n in srcs) + '</ul>')

    # ---------- 出力 ----------
    def build(self, outname):
        ASSETS.clear()
        pm_pages.schedule_pages(self); self.grants(); self.home_and_projects(); self.week(); self.note_pages(); self.keys(); self.scope_tab(); self.parts(); self.reviews()
        r = self.r
        nav = (('<a href="#pm">工程</a>' if 'pm' in self.pages else '') + ('<a href="#comments">コメント</a>' if 'comments' in self.pages else '') + '<a href="#keys">相談先</a>' + ('<a href="#scope">見せる相手</a>' if 'scope' in self.pages else '')
               + (f'<a href="#grants">確認待ち <span class="cnt">{self.todo}</span></a>' if 'grants' in self.pages else ''))
        if SELF:   # 自分の vault だけの時は、先頭のページは「自分のノート」
            self.pages = {k: v.replace('<a href="#home">案件</a>', '<a href="#home">自分のノート</a>') for k, v in self.pages.items()}
        rep = {'/*PAGES*/': json.dumps(self.pages, ensure_ascii=False), '/*ASSETS*/': json.dumps(ASSETS, ensure_ascii=False),
               '/*MYTAGS*/': json.dumps([t for t, g in r['tags'].items() if self.user in g['members']], ensure_ascii=False),
               '/*TAGS*/': json.dumps([t for t, g in r['tags'].items() if not g.get('hide')], ensure_ascii=False),
               '/*USERS*/': json.dumps(r['users'], ensure_ascii=False),
               '/*HOL*/': json.dumps(r.get('holidays', [])),
               '/*EDITOR_JS*/': open(os.path.join(os.path.dirname(__file__), 'editor.js'), encoding='utf-8').read(),
               '<!--NAV-->': nav, '{{UID}}': self.user, '{{USER}}': esc(self.uname(self.user)),
               '{{TITLE}}': '開発ノート閲覧' if outname == 'index.html' else '開発ノート閲覧 一般社員表示',
               '{{BUILT}}': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
        out = open(os.path.join(os.path.dirname(__file__), 'site_template.html'), encoding='utf-8').read()
        for k, v in rep.items(): out = out.replace(k, v)
        os.makedirs(os.path.join(OUT, 'site'), exist_ok=True)
        open(os.path.join(OUT, 'site', outname), 'w', encoding='utf-8').write(out)
        self.dump_text(outname)
        print('サイト生成', len(self.pages), 'ページ', f'（{self.user} が閲覧できるノート {len(self.vis)} 件）', f'{len(out)//1024}KB')

    def dump_text(self, outname):
        """エージェント評価用のテキスト版"""
        def txt(h):
            h = re.sub(r'<x-a k="[^"]+"></x-a>', '[図]', h)
            h = re.sub(r'<(tr|li|h1|h2|p|div|figure|section|details)[^>]*>', '\n', h)
            return html.unescape(re.sub(r'<[^>]+>', ' ', h))
        open(os.path.join(OUT, 'site', outname + '.txt'), 'w', encoding='utf-8').write(
            '\n\n'.join(f'===== ページ #{k} =====\n' + re.sub(r'\n\s*\n+', '\n', txt(v)) for k, v in self.pages.items()))

def build(user, outname='index.html'):
    Site(user).build(outname)
