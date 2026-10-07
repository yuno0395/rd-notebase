"""Web閲覧：工程（ガント図・タスクの経過・遅れ・計画変更の確認）。pages.Site から呼ぶ"""
import json, datetime
from core import esc, reg
import gantt as G
import re
from render import render_body, asset, upd_html

VIEW_ORDER = ['m1', 'm3', 'm6']
def md(x): x = G.d(x); return f'{x.month}/{x.day}'

def task_info(r, hist, uname, names=None):
    """棒を押した時に出す「タスクの経過」の材料"""
    plan = md(r['date']) if r.get('milestone') else f"{md(r['start'])}〜{md(r['end'])}" if r.get('start') else ''
    b = r.get('base') or {}
    base = (md(b['date']) if b.get('date') else f"{md(b['start'])}〜{md(b['end'])}" if b.get('start') else '—')
    return {'name': r['name'], 'id': r['full'], 'plan': plan, 'base': base, 'state': r.get('state', ''),
            'act': (f"{md(r['actual_start'])}〜{md(r['actual_end']) if r.get('actual_end') else '（実行中）'}" if r.get('actual_start')
                    else f"{md(r['actual_end'])} 実施" if r.get('actual_end') else '—'),
            'fc': md(r['fc']) if r.get('fc') else '', 'delay': r.get('delay', 0), 'cnt': f"{r.get('done', 0)}/{r.get('total', 0)}",
            'owner': uname(r.get('owner', '')), 'milestone': bool(r.get('milestone')), 'group': bool(r.get('group')),
            's': str(r.get('start', r.get('date', ''))), 'e': str(r.get('end', r.get('date', ''))), 'after': r.get('after') or [],
            'todos': [[dn, t] for dn, t, _ in r.get('todos', [])],
            'weekly': [{'w': G.week_name(w['week']), 'cnt': w.get('count', ''), 'did': w.get('did', ''), 'issue': w.get('issue', ''),
                        'fc': md(w['forecast_end']) if w.get('forecast_end') else '', 'who': uname(w['who']),
                        'act': ' '.join(x for x in [f"開始 {md(w['actual_start'])}" if w.get('actual_start') else '', f"終了 {md(w['actual_end'])}" if w.get('actual_end') else ''] if x)}
                       for w in r.get('weekly', [])],
            'hist': [{'at': h['at'], 'what': h['what'], 'by': uname(h['meta'].get('承認', '')), 'code': h['meta'].get('区分', ''), 'why': h['meta'].get('理由', '')}
                     for h in hist.get(r['id'], [])],
            'req': ({'why': '、'.join(r['req'].get('why') or []), 'by': uname(r['req'].get('requested_by')), 'code': r['req'].get('code'), 'reason': r['req'].get('reason'),
                     'ch': [f"{(names or {}).get(c['task'], c['task'])} " + (md(c['date']) if 'date' in c else f"{md(c['start'])}〜{md(c['end'])}") + ('（連動）' if c.get('auto') else '')
                            for c in r['req']['changes']]} if r.get('req') else None)}

def schedule_pages(site):
    uname = lambda u: site.uname(u).split('（')[0] if u else ''
    out_links = []
    for n in [n for n in site.vis.values() if n['type'] == 'schedule']:
        fm = json.loads(n['fm']); pid = fm['project']; pname = site.r['projects'][pid]['name']
        rows = G.build(n, site.notes)
        for r in rows: r['owner_ja'] = uname(r.get('owner'))
        hist = G.history(n)
        svgs, tabs = [], []
        for v in VIEW_ORDER:
            P, geo = G.layout(f'{pid} {pname} 工程表', rows, v, sub='比較：当初計画')
            svgs.append(f'<div class="gview" data-v="{v}"{"" if v == "m3" else " hidden"}>{G.to_svg(P, geo, interactive=True)}</div>')
            tabs.append(f'<button type="button" class="gtab{" on" if v == "m3" else ""}" data-v="{v}">{G.VIEWS[v][0]}</button>')
        names = {r['id']: r['name'] for r in rows}
        info = {r['id']: task_info(r, hist, uname, names) for r in rows}
        for r in rows:                     # 名前を押すと出す「まとめ」ノート（指定がなければ、紐づくノートの最新）
            nid = r.get('note')
            if not nid:
                cand = [x for x in site.notes.values() if f"[task:: {r.get('full')}]" in (x['body'] or '') and x['type'] not in ('weekly', 'comment')]
                nid = max(cand, key=lambda x: (x['type'] == 'report', x['updated']))['id'] if cand else None
            if nid and nid in site.vis:
                nn = site.vis[nid]
                k = re.search(r'k="([^"]+)"', asset(f'<div class="mdprev"><p class="sub">{esc(nn["title"])} ・ 更新 {upd_html(nn, nn.get("granted"))}</p><article>{render_body(nn, site.user, site.notes)}</article></div>')).group(1)
                info[r['id']]['note'] = {'id': nid, 'title': nn['title'], 'k': k}
            elif nid: info[r['id']]['note'] = {'id': nid, 'title': site.notes[nid]['title'], 'k': '', 'lock': 1}
        late = [r for r in rows if r.get('delay', 0) > 0 and not r.get('group')]
        nlate = [r for r in late if r.get('state') != '完了']
        ms = sorted([r for r in rows if r.get('milestone') and not r.get('actual_end')], key=lambda r: r['fc'])
        t0 = datetime.date.today()
        nxt = (f"次の節目：{ms[0]['name']} {md(ms[0]['fc'])}（あと{(ms[0]['fc'] - t0).days}日）" if ms else '')
        mx = max([r['delay'] for r in rows if not r.get('group')] or [0])
        site.pm_summary[pid] = f"{nxt} ・ 最大 +{mx}日（実働）" if mx > 0 else nxt
        can_edit = any(r.get('owner') == site.user for r in rows)
        late_html = ''.join(f'<tr><td><button type="button" class="tlink" data-task="{r["id"]}">{esc(r["name"])}</button></td><td><span class="ml">当初 </span>{esc(info[r["id"]]["base"])}</td>'
                            f'<td><span class="ml">見込み </span>{esc(info[r["id"]]["fc"])}</td><td class="late"><span class="ml">遅れ </span>+{r["delay"]}日</td><td>{esc(r.get("state", ""))}</td></tr>' for r in late)
        reqs = [x for x in site.notes.values() if x['type'] == 'planreq' and json.loads(x['fm']).get('schedule') == n['id']]
        req_html = ''.join(
            f'<li><span class="type">{ {"requested": "申請中", "approved": "承認", "rejected": "却下", "auto": "記録のみ"}.get(json.loads(x["fm"]).get("decision"), "")}</span>'
            f'{esc(json.loads(x["fm"])["code"])}：{esc(json.loads(x["fm"])["reason"])} <span class="sub">{esc(uname(json.loads(x["fm"]).get("requested_by")))} {esc(x["updated"])}</span></li>' for x in reqs)
        sid = n['id']
        mgrs = '、'.join(uname(u) for u in (site.r['projects'][pid].get('managers') or []))   # 日程は取りまとめ役が Obsidian の dotpm で直す
        site.pages[f'g-{sid}'] = (
            f'<p class="crumb"><a href="#home">案件</a> / <a href="#p-{pid}">{pid}</a> / 工程</p><h1>{esc(pname)} 工程表</h1>'
            f'<p class="lead"><b>{esc(site.pm_summary[pid])}</b><br>当初計画より遅れ：進行中・未着手 {len(nlate)} 件、完了 {len(late) - len(nlate)} 件 ・ 比較：当初計画（{esc((fm.get("baselines") or [{}])[0].get("at", ""))} 承認）</p>'
            f'<section class="gantt-wrap" data-sid="{sid}" data-name="{pid}_工程表" data-mgr="{1 if site.mgr else 0}" data-tasks="{esc(json.dumps(info, ensure_ascii=False))}">'
            f'<div class="gbar">{"".join(tabs)}<span class="gsp"></span>'
            + f'<span class="gscroll">横にスクロールできます →</span>'
            + '<button type="button" class="gsave">画像を保存</button></div>'
            + (f'<p class="sub">日程・タスクの変更は、取りまとめ役（{esc(mgrs)}）が Obsidian の dotpm で行います。承認が要る変更は確認待ちに並びます。</p>' if mgrs else '')
            + ''.join(svgs) + '<p class="sub">タスク名を押すと「まとめ」のノート、棒・行を押すと「タスクの経過」（週報・やること・計画変更の履歴）を表示します。</p>'
            + (('<p class="sub">書き込みのあるガント図（Excalidraw）：' + '、'.join(f'<a href="#n-{x["id"]}">{G.VIEWS[json.loads(x["fm"])["gantt"]["view"]][0]}</a>' for x in exl) + '</p>') if (exl := [x for x in site.vis.values() if x['type'] == 'drawing' and (json.loads(x['fm']).get('gantt') or {}).get('schedule') == sid]) else '')
            + '</section>'
            + (f'<h2>遅れ（当初計画より後ろ）</h2><div class="tablewrap"><table class="cardable"><thead><tr><th>タスク</th><th>当初計画</th><th>見込み</th><th>遅れ</th><th>状態</th></tr></thead><tbody>{late_html}</tbody></table></div>' if late else '')
            + (f'<h2>計画変更の申請</h2><ul class="plain">{req_html}</ul>' if req_html else ''))
        out_links.append((pid, f'g-{sid}', len(late)))
    for n in [n for n in site.vis.values() if n['type'] == 'roadmap']:
        rows = G.build_roadmap(n, site.notes)
        for r in rows: r['owner_ja'] = ''
        svgs, tabs = [], []
        for v in ('y5', 'y10'):
            P, geo = G.layout(n['title'], rows, v, sub='目標期間（影）と見込み', base_label='目標期間', roadmap=True)
            svgs.append(f'<div class="gview" data-v="{v}"{"" if v == "y5" else " hidden"}>{G.to_svg(P, geo)}</div>')
            tabs.append(f'<button type="button" class="gtab{" on" if v == "y5" else ""}" data-v="{v}">{G.VIEWS[v][0]}</button>')
        rv = [r for r in rows if r.get('review')]
        site.pages[f'rm-{n["id"]}'] = (f'<p class="crumb"><a href="#home">案件</a> / ロードマップ</p><h1>{esc(n["title"])}</h1>'
            + (f'<p class="todo">見直しが必要：{"、".join(esc(r["name"]) for r in rv)}（案件の見込みが半期をまたいで遅れています）</p>' if rv else '')
            + f'<section class="gantt-wrap" data-name="ロードマップ" data-tasks="{{}}"><div class="gbar">{"".join(tabs)}<span class="gsp"></span><button type="button" class="gsave">画像を保存</button></div>{"".join(svgs)}</section>')
        out_links.append(('ロードマップ', f'rm-{n["id"]}', len(rv)))
    if out_links:
        site.pages['pm'] = ('<p class="crumb"><a href="#home">案件</a> / 工程</p><h1>工程</h1><ul class="updates">'
            + ''.join(f'<li><a href="#{k}">{esc(p)} {esc(site.r["projects"][p]["name"]) if p in site.r["projects"] else ""}</a>'
                      f'<div class="sum">{esc(site.pm_summary.get(p, ""))}{f" ・ <span class=late>見直し {c} 件</span>" if c and p not in site.r["projects"] else ""}</div></li>' for p, k, c in out_links) + '</ul>')
    return out_links

def plan_section(site):
    """確認待ち：計画変更のリクエスト（公開の確認と同じ流れ）"""
    out = []
    for x in site.notes.values():
        if x['type'] != 'planreq': continue
        fm = json.loads(x['fm'])
        if fm.get('decision') != 'requested' or site.user not in (fm.get('approvers') or []): continue
        sn = site.notes.get(fm['schedule']); sfm = json.loads(sn['fm']); tasks = {t['id']: t for t in sfm['tasks']}
        base = {t['id']: t for t in (sfm.get('baselines') or [{}])[0].get('tasks', [])}; hol = G.holidays()
        def vs_base(tid, x):
            b = base.get(tid) or {}; k = 'date' if 'date' in x else 'end'
            return G.wdays(G.d(b[k]), G.d(x[k]), hol) if b.get(k) else 0
        cc = [c for c in fm['changes'] if c['task'] in tasks]
        after = max([vs_base(c['task'], c) for c in cc] or [0])
        now = max([vs_base(c['task'], tasks[c['task']]) for c in cc] or [0])
        msx = [f"{tasks[c['task']]['name']} {md(tasks[c['task']]['date'])}→{md(c['date'])}" for c in cc if 'date' in c]
        untouched = [t['name'] for t in sfm['tasks'] if t.get('milestone') and not any(c['task'] == t['id'] for c in cc)]
        impact = (f'<p class="impact">承認すると：当初比 最大 <b>+{after}日</b>（今の計画は +{now}日）<br>節目：{esc("、".join(msx) or "動かない")}'
                  + (f'<br>動かない節目：{esc("、".join(untouched))}' if untouched else '')
                  + f'<br>これまでの計画変更：{len({h["at"] for v in G.history(sn).values() for h in v})} 回（承認済み。ガント図の各タスクの経過で確認できます）</p>')
        li = ''.join(f'<li>{esc(x)}</li>' for x in fm.get('lines') or [])
        for ch in ([] if fm.get('lines') else fm['changes']):
            t = tasks[ch['task']]
            b4 = md(t['date']) if t.get('milestone') else f"{md(t['start'])}〜{md(t['end'])}"
            af = md(ch['date']) if 'date' in ch else f"{md(ch['start'])}〜{md(ch['end'])}"
            li += f'<li><b>{esc(t["name"])}</b>{"（連動）" if ch.get("auto") else ""}<br><span class="b4x">{b4}</span> → <span class="af">{af}</span></li>'
        out.append(f'<section class="grant" data-gid="{x["id"]}" data-kind="plan"><h2>計画変更：{esc(json.loads(sn["fm"])["project"])}</h2>'
                   + impact + f'<p class="memo">{esc(fm["code"])}：{esc(fm["reason"])}</p><p class="lead">{esc(site.uname(fm.get("requested_by")))} から ・ 承認が要る理由：{esc("、".join(fm.get("why") or []))}</p>'
                   f'<ul>{li}</ul><p><a href="#g-{fm["schedule"]}">ガント図で確認する</a></p>'
                   '<label class="rl">コメント（必須）</label><textarea rows="2"></textarea>'
                   '<div class="gbtns"><button class="ok" data-act="plan-ok">計画を変更する</button><button class="ng" data-act="plan-ng">申請を却下する</button></div>'
                   '<p class="gmsg" aria-live="polite"></p><pre class="gout" hidden></pre></section>')
    site.todo += len(out)
    return ''.join(out)
