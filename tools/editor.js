// ---------- 工程表の編集画面：追加・削除・名前・担当・見積・親・前のタスク・並べ替え・分割・段階に分解・ドラッグ ----------
// 正本は工程表ノート（計画だけ）。ここでは計画の下書きを作り、元との差分を「申請」にする（承認が要るものは確認待ちへ）
const ED={};
function initEditor(){const root=document.querySelector('#view .ged');if(!root)return;
  ED.root=root;ED.sid=root.dataset.sid;ED.orig=JSON.parse(root.dataset.plan);ED.info=JSON.parse(root.dataset.info);ED.me=root.dataset.me;
  ED.tasks=JSON.parse(root.dataset.plan);ED.scrolled=0;ED.undo=[];ED.redo=[];ED.sel=null;ED.view='m3';ED.chain=true;ED.used=JSON.parse(root.dataset.used||'[]');
  edRender();}
const ePPD={m1:22,m3:7,m6:3.5};const eRH=30;
const eAdd=(s,k)=>iso(new Date(+pd(s)+k*DAY));
function eNextWd(s){let d=new Date(+pd(s)+DAY);while(!isWork(d))d=new Date(+d+DAY);return iso(d);}
function eFwd(s){let d=pd(s);while(!isWork(d))d=new Date(+d+DAY);return iso(d);}
function eBack(s){let d=pd(s);while(!isWork(d))d=new Date(+d-DAY);return iso(d);}
function eAddWd(s,k){let d=pd(s);while(k>0){d=new Date(+d+DAY);if(isWork(d))k--;}while(k<0){d=new Date(+d-DAY);if(isWork(d))k++;}return iso(d);}
const eT=id=>ED.tasks.find(t=>t.id===id);
const eKids=id=>ED.tasks.filter(t=>t.parent===id);
function eSpan(t){if(t.milestone)return [t.date,t.date];if(!t.group)return [t.start,t.end];
  const ks=eKids(t.id).map(eSpan).filter(x=>x[0]);if(!ks.length)return [null,null];return [ks.map(x=>x[0]).sort()[0],ks.map(x=>x[1]).sort().pop()];}
function eEnd(id){const t=eT(id);return t?eSpan(t)[1]:null;}
function eDepth(t){let n=0,p=t.parent;while(p&&n<5){n++;p=(eT(p)||{}).parent;}return n;}
function eSnap(){ED.undo.push(JSON.stringify(ED.tasks));if(ED.undo.length>80)ED.undo.shift();ED.redo=[];}
function eNewId(kind){const all=new Set([...ED.used,...ED.orig.map(t=>t.id),...ED.tasks.map(t=>t.id)]);let n=1;
  const p=kind==='m'?'M':kind==='g'?'G':'T';while(all.has(p+String(n).padStart(2,'0')))n++;return p+String(n).padStart(2,'0');}
// 後ろへの連鎖（サーバの ripple と同じ決まり：食い込む分だけ押す）
function eRipple(){if(!ED.chain)return;for(let pass=0;pass<3;pass++)for(const t of ED.tasks){if(t.group)continue;
  const lat=(t.after||[]).map(eEnd).filter(Boolean).sort().pop();if(!lat)continue;
  if(t.milestone){if(lat>=t.date)t.date=eNextWd(lat);}
  else if(lat>=t.start){const ns=eNextWd(lat);const k=wdays(t.start,ns);t.start=ns;t.end=eAddWd(t.end,k);}}}
// 描画（編集用。計画だけを描く。当初計画・実績・見込みは閲覧のガント図で見る）
function edRender(){const R=ED.root;const ts=ED.tasks;const ppd=ePPD[ED.view];
  const ds=ts.flatMap(t=>eSpan(t)).filter(Boolean).sort();const today=iso(new Date());
  let s0=pd(ds[0]<today?ds[0]:today);s0=new Date(+s0-((s0.getUTCDay()+6)%7)*DAY-7*DAY);const s=iso(s0);
  const e=iso(new Date(+pd(ds[ds.length-1])+21*DAY));const days=Math.round((pd(e)-pd(s))/DAY);const W=days*ppd,HH=40+ts.length*eRH;
  const X=x=>(pd(x)-pd(s))/DAY*ppd;ED.X=X;ED.s=s;ED.ppd=ppd;
  let o=`<svg class="gesvg" width="${W}" height="${HH}" viewBox="0 0 ${W} ${HH}" xmlns="http://www.w3.org/2000/svg"><defs><marker id="ea" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10z" fill="#9aa3ad"/></marker></defs>`;
  for(let i=0;i<days;i++){const d=new Date(+pd(s)+i*DAY);const x=i*ppd;
    if(!isWork(d)&&ED.view!=='m6')o+=`<rect x="${x}" y="20" width="${ppd}" height="${HH-20}" fill="#f2f4f6"/>`;
    if(d.getUTCDate()===1)o+=`<line x1="${x}" y1="0" x2="${x}" y2="${HH}" stroke="#c9d1d9"/><text x="${x+3}" y="13" font-size="11" fill="#5a6672">${d.getUTCFullYear()}/${d.getUTCMonth()+1}</text>`;
    if(ED.view==='m1')o+=`<text x="${x+ppd/2}" y="33" font-size="10" text-anchor="middle" fill="${isWork(d)?'#1c2631':'#c0392b'}">${d.getUTCDate()}</text>`;
    else if(d.getUTCDay()===1)o+=`<line x1="${x}" y1="20" x2="${x}" y2="${HH}" stroke="#eef1f4"/><text x="${x+2}" y="33" font-size="10" fill="#5a6672">${d.getUTCMonth()+1}/${d.getUTCDate()}</text>`;}
  o+=`<line x1="0" y1="40" x2="${W}" y2="40" stroke="#1c2631"/>`;
  const Y={};ts.forEach((t,i)=>Y[t.id]=40+i*eRH);
  ts.forEach((t,i)=>{const y=Y[t.id],m=y+eRH/2;if(t.id===ED.sel)o+=`<rect x="0" y="${y}" width="${W}" height="${eRH}" fill="#e2eff3"/>`;
    o+=`<rect class="erow" x="0" y="${y}" width="${W}" height="${eRH}" fill="transparent" data-id="${t.id}"/>`;
    const [a,b]=eSpan(t);if(!a)return;
    if(t.milestone)o+=`<path class="ems" data-id="${t.id}" d="M${X(a)},${m-8}L${X(a)+8},${m}L${X(a)},${m+8}L${X(a)-8},${m}Z" fill="#1c2631"/><text x="${X(a)+11}" y="${m+4}" font-size="11" fill="#1c2631">${t.name}</text>`;
    else if(t.group)o+=`<rect x="${X(a)}" y="${m-3}" width="${X(b)+ppd-X(a)}" height="6" fill="#4a5560" rx="2"/>`;
    else{const x=X(a),w=X(b)+ppd-x;const chg=eChanged(t);
      o+=`<rect class="ebar" data-id="${t.id}" x="${x}" y="${m-8}" width="${w}" height="16" rx="3" fill="${chg?'#fdf3e1':'#fff'}" stroke="${chg?'#b7791f':'#5a6672'}" stroke-width="${chg?2:1}"/>`
       +`<rect class="eh" data-id="${t.id}" data-edge="start" x="${x-3}" y="${m-8}" width="7" height="16" fill="transparent"/><rect class="eh" data-id="${t.id}" data-edge="end" x="${x+w-4}" y="${m-8}" width="7" height="16" fill="transparent"/>`
       +(w>40?`<text x="${x+4}" y="${m+4}" font-size="10" fill="#5a6672" pointer-events="none">${md(a)}〜${md(b)}</text>`:'');}});
  ts.forEach(t=>(t.after||[]).forEach(p=>{const q=eT(p);if(!q||t.group)return;const pe=eSpan(q)[1],ts_=eSpan(t)[0];if(!pe||!ts_)return;
    const x1=X(pe)+(q.milestone?0:ppd),x2=X(ts_),y1=Y[p]+eRH/2,y2=Y[t.id]+eRH/2;o+=`<polyline points="${x1},${y1} ${x1+4},${y1} ${x1+4},${y2} ${Math.max(x2,x1+6)},${y2}" fill="none" stroke="#9aa3ad" marker-end="url(#ea)"/>`;}));
  if(today>=s&&today<e)o+=`<line x1="${X(today)}" y1="20" x2="${X(today)}" y2="${HH}" stroke="#c0392b" stroke-width="1.5"/>`;
  o+='</svg>';
  const left=ts.map(t=>`<div class="ern${t.id===ED.sel?' on':''}${eChanged(t)?' chg':''}" data-id="${t.id}" style="padding-left:${6+eDepth(t)*14}px">${t.milestone?'◆ ':t.group?'▾ ':''}<span>${t.name}</span><small>${t.id}${t.owner?' ・ '+(USERS[t.owner]||t.owner).split('（')[0]:''}</small></div>`).join('');
  R.querySelector('.gel').innerHTML='<div class="ehd">タスク</div>'+left;R.querySelector('.ger').innerHTML=o;
  if(!ED.scrolled){ED.scrolled=1;R.querySelector('.gegrid').scrollLeft=Math.max(0,X(today)-60);}
  R.querySelector('.eundo').disabled=!ED.undo.length;R.querySelector('.eredo').disabled=!ED.redo.length;
  edPanel();edChanges();}
function eChanged(t){const o=ED.orig.find(x=>x.id===t.id);if(!o)return true;return ['name','start','end','date','owner','parent','est'].some(k=>(o[k]||'')!==(t[k]||''))||JSON.stringify(o.after||[])!==JSON.stringify(t.after||[]);}
// 選んだタスクの設定
function edPanel(){const P=ED.root.querySelector('.gepanel');const t=eT(ED.sel);
  if(!t){P.innerHTML='<p class="sub">タスクを押すと、ここで名前・日付・担当・前のタスクなどを変えられます。棒は中ほどをドラッグでずらし、端をドラッグで伸び縮みします。</p>';return;}
  const inf=ED.info[t.id]||{};const groups=ED.tasks.filter(g=>g.group&&g.id!==t.id);
  const preds=ED.tasks.filter(x=>x.id!==t.id&&!x.group);
  P.innerHTML=`<h3>${t.milestone?'◆ 節目':t.group?'グループ':'タスク'} <span class="mono sub">${t.id}</span></h3>
   <div class="epf"><label>名前<input class="ef" data-k="name" value="${t.name.replace(/"/g,'&quot;')}"></label>
   ${t.milestone?`<label>日付<input type="date" class="ef" data-k="date" value="${t.date}"></label>`:t.group?'':`<label>開始<input type="date" class="ef" data-k="start" value="${t.start}"></label><label>終了<input type="date" class="ef" data-k="end" value="${t.end}"></label>
    <label>担当<select class="ef" data-k="owner">${Object.entries(USERS).map(([k,v])=>`<option value="${k}" ${k===t.owner?'selected':''}>${v}</option>`).join('')}</select></label>
    <label>見積（人日）<input type="number" min="0" step="0.5" class="ef" data-k="est" value="${t.est||''}"></label>`}
   <label>グループ<select class="ef" data-k="parent"><option value="">（なし）</option>${groups.map(g=>`<option value="${g.id}" ${g.id===t.parent?'selected':''}>${g.name}</option>`).join('')}</select></label>
   ${t.group?'':`<fieldset><legend>前のタスク（終わってから始める）</legend>${preds.map(p=>`<label class="chk"><input type="checkbox" class="eaf" value="${p.id}" ${(t.after||[]).includes(p.id)?'checked':''}> ${p.name}</label>`).join('')}</fieldset>`}</div>
   ${inf.total||inf.weekly?`<p class="sub">紐づき：やること ${inf.done||0}/${inf.total||0}${inf.weekly?' ・ 週報 '+inf.weekly+' 件':''}</p>`:''}
   <div class="gbtns"><button type="button" class="eop" data-op="up">↑ 上へ</button><button type="button" class="eop" data-op="down">↓ 下へ</button>
   ${t.group||t.milestone?'':'<button type="button" class="eop" data-op="split">2つに分割</button><button type="button" class="eop" data-op="stages">段階に分解</button>'}
   <button type="button" class="eop ng" data-op="del">削除</button></div>`;}
// 差分 → 申請
function eDiff(){const ops=[],lines=[],O={};ED.orig.forEach(t=>O[t.id]=t);const N={};ED.tasks.forEach(t=>N[t.id]=t);
  const nm=(id)=>(N[id]||O[id]||{}).name||id;const dt=t=>t.milestone?md(t.date):t.group?'':md(t.start)+'〜'+md(t.end);
  for(const t of ED.tasks){const o=O[t.id];
    if(!o){ops.push({op:'add',task:t});if(t.parent&&N[t.parent]&&N[t.parent].group&&O[t.parent]&&!O[t.parent].group)continue;lines.push({k:'scope',s:`追加：${t.name}${dt(t)?'（'+dt(t)+'）':''}${t.owner?' 担当 '+(USERS[t.owner]||'').split('（')[0]:''}`});continue;}
    if(t.group&&!o.group){ops.push({op:'set',id:t.id,f:{group:true,start:'',end:'',owner:'',est:'',after:t.after||[]}});
      lines.push({k:'scope',s:`段階に分解：${t.name} → ${eKids(t.id).map(x=>x.name).join('・')}`});continue;}
    const f={};for(const k of ['name','start','end','date','owner','parent','est'])if((o[k]||'')!==(t[k]||''))f[k]=t[k]||'';
    if(JSON.stringify(o.after||[])!==JSON.stringify(t.after||[]))f.after=t.after||[];
    if(!Object.keys(f).length)continue;ops.push({op:'set',id:t.id,f});
    if(f.name)lines.push({k:'rec',s:`名前：${o.name} → ${t.name}`});
    if(f.start||f.end||f.date)lines.push({k:'date',id:t.id,s:`日程：${t.name} ${dt(o)} → ${dt(t)}`});
    if(f.owner)lines.push({k:'scope',s:`担当：${t.name} ${(USERS[o.owner]||'—').split('（')[0]} → ${(USERS[t.owner]||'').split('（')[0]}`});
    if('parent' in f)lines.push({k:'scope',s:`グループ：${t.name} → ${f.parent?nm(f.parent):'（なし）'}`});
    if(f.after)lines.push({k:'rec',s:`前のタスク：${t.name} ← ${(t.after||[]).map(nm).join('、')||'（なし）'}`});
    if('est' in f){const up=(+f.est||0)>(+o.est||0)*1.2;lines.push({k:up?'scope':'rec',s:`見積：${t.name} ${o.est||'—'} → ${f.est||'—'} 人日`});}}
  for(const o of ED.orig)if(!N[o.id]){ops.push({op:'del',id:o.id});lines.push({k:'scope',s:`削除：${o.name}`});}
  const oo=ED.orig.map(t=>t.id).filter(id=>N[id]).join(),no=ED.tasks.map(t=>t.id).filter(id=>O[id]).join();
  if(oo!==no){ops.push({op:'order',ids:ED.tasks.map(t=>t.id)});lines.push({k:'rec',s:'並び順の変更'});}
  // 承認が要るか（サーバでも同じ判定をする）
  const why=[];lines.forEach(l=>{if(l.k==='scope')why.push(l.s.split('：')[0]);});
  for(const t of ED.tasks){const o=O[t.id];if(!o)continue;
    if(t.milestone&&o.date!==t.date)why.push('節目の移動');else if(!t.milestone&&!t.group&&o.end&&wdays(o.end,t.end)>5)why.push(`${t.name} 実働${wdays(o.end,t.end)}日の遅れ`);}
  return {ops,lines,why:[...new Set(why)]};}
function edChanges(){const C=ED.root.querySelector('.gechg');const {ops,lines,why}=eDiff();
  if(!ops.length){C.innerHTML='<p class="sub">まだ変更はありません。</p>';ED.root.querySelector('.ecnt').textContent='';return;}
  ED.root.querySelector('.ecnt').textContent=` ${lines.length}`;
  C.innerHTML=`<h3>変更（${lines.length}件）</h3><ul class="ttl">${lines.map(l=>`<li>${l.k==='scope'?'<b>':''}${l.s}${l.k==='scope'?'</b>':''}</li>`).join('')}</ul>
   <p class="${why.length?'late':'sub'}">${why.length?'上司の承認が必要：'+why.join('、'):'承認は不要（記録だけ残ります）'}</p>
   <label class="rl" for="ecode">理由の区分（必須）</label><select id="ecode"><option value="">選んでください</option>${['見積の誤り','仕様変更','外部待ち（部品・外注・顧客）','不具合・やり直し','人の都合（他案件・休み）','その他'].map(x=>`<option>${x}</option>`).join('')}</select>
   <label class="rl" for="ewhy">理由（必須）</label><textarea id="ewhy" rows="2"></textarea>
   <div class="gbtns"><button type="button" class="ok esubmit">${why.length?'承認を依頼する':'変更を記録する'}</button><button type="button" class="ereset">すべて取り消す</button></div><p class="smsg" aria-live="polite"></p><pre class="gout" hidden></pre>`;}
// 操作
function eSel(id){ED.sel=id;edRender();}
function eSet(t,k,v){eSnap();if(k==='est')v=v===''?'':+v;t[k]=v;
  if(k==='start'&&t.end<t.start)t.end=t.start;if(k==='end'&&t.end<t.start)t.start=t.end;
  if(['start','end','date'].includes(k)){if(t.start)t.start=eFwd(t.start);if(t.end)t.end=eBack(t.end);if(t.date)t.date=eFwd(t.date);eRipple();}
  if(k==='parent'&&v===''){delete t.parent;}edRender();}
function eOp(op){const t=eT(ED.sel);if(!t)return;const i=ED.tasks.indexOf(t);
  if(op==='up'&&i>0){eSnap();[ED.tasks[i-1],ED.tasks[i]]=[ED.tasks[i],ED.tasks[i-1]];}
  else if(op==='down'&&i<ED.tasks.length-1){eSnap();[ED.tasks[i+1],ED.tasks[i]]=[ED.tasks[i],ED.tasks[i+1]];}
  else if(op==='del'){const inf=ED.info[t.id]||{};
    if(!confirm(`「${t.name}」を削除します。${inf.total?`\n紐づくやること ${inf.total} 件は行き先がなくなります。`:''}${t.group?'\n中のタスクはグループの外に出します。':''}`))return;
    eSnap();ED.tasks.forEach(x=>{if((x.after||[]).includes(t.id))x.after=[...new Set([...(x.after||[]).filter(a=>a!==t.id),...(t.after||[])])];if(x.parent===t.id){if(t.parent)x.parent=t.parent;else delete x.parent;}});
    ED.tasks.splice(i,1);ED.sel=null;}
  else if(op==='split'){const n=wdays(t.start,t.end)+1;if(n<2){alert('1日のタスクは分割できません');return;}eSnap();const half=Math.floor(n/2);
    const id=eNewId('t');const e1=eAddWd(t.start,half-1);const nt={id,name:t.name+'（2）',start:eNextWd(e1),end:t.end,owner:t.owner,after:[t.id],...(t.parent?{parent:t.parent}:{}),...(t.est?{est:Math.round(t.est/2*2)/2}:{})};
    ED.tasks.forEach(x=>{if((x.after||[]).includes(t.id)&&x.id!==id)x.after=x.after.map(a=>a===t.id?id:a);});
    t.name=t.name.replace(/（1）$/,'')+'（1）';t.end=e1;if(t.est)t.est=t.est-nt.est;ED.tasks.splice(i+1,0,nt);ED.sel=id;}
  else if(op==='stages'){const s=prompt('段階の名前を「、」区切りで入力（最後に◆を付けると節目）','設計検討、検討まとめ、詳細設計、小DR◆');if(!s)return;
    const names=s.split(/[、,]/).map(x=>x.trim()).filter(Boolean);if(!names.length)return;eSnap();
    const bars=names.filter(x=>!x.endsWith('◆'));const n=wdays(t.start,t.end)+1;let cur=t.start,prev=null;const kids=[];
    names.forEach((nm,k)=>{const id=nm.endsWith('◆')?eNewId('m'):eNewId('t');let x;
      if(nm.endsWith('◆')){x={id,name:nm.slice(0,-1),date:prev?eNextWd(eSpan(eT(prev)||kids[kids.length-1])[1]):cur,milestone:true,parent:t.id};}
      else{const bi=bars.indexOf(nm);const len=Math.max(1,Math.round(n*(bi+1)/bars.length)-Math.round(n*bi/bars.length));const st=prev?eNextWd(eSpan(kids[kids.length-1])[1]):cur;
        x={id,name:nm,start:st,end:eAddWd(st,len-1),owner:t.owner,parent:t.id,...(t.est?{est:Math.round(t.est*len/n*2)/2}:{})};}
      x.after=prev?[prev]:(t.after||[]);kids.push(x);ED.tasks.push(x);prev=id;});
    ED.tasks.splice(ED.tasks.indexOf(kids[0]),kids.length);ED.tasks.splice(i+1,0,...kids);
    t.group=true;delete t.start;delete t.end;delete t.owner;delete t.est;ED.sel=t.id;}
  edRender();}
function eAddNew(kind){eSnap();const s=eT(ED.sel);const id=eNewId(kind);const base=s?(eSpan(s)[1]||iso(new Date())):iso(new Date());
  let t;if(kind==='g')t={id,name:'新しいグループ',group:true};
  else if(kind==='m')t={id,name:'新しい節目',date:eNextWd(base),milestone:true,after:s&&!s.group?[s.id]:[]};
  else{const st=eNextWd(base);t={id,name:'新しいタスク',start:st,end:eAddWd(st,4),owner:(s&&s.owner)||ED.me,after:s&&!s.group?[s.id]:[]};}
  if(s&&s.parent&&kind!=='g')t.parent=s.parent;if(s&&s.group&&kind!=='g'){t.parent=s.id;t.after=[];}
  const i=s?ED.tasks.indexOf(s)+1+(s.group?eKids(s.id).length:0):ED.tasks.length;ED.tasks.splice(i,0,t);ED.sel=id;edRender();
  const f=ED.root.querySelector('.ef[data-k="name"]');if(f){f.focus();f.select();}}
// 画面のイベント
document.addEventListener('click',e=>{if(!ED.root||!e.target.closest('.ged'))return;
  const r=e.target.closest('[data-id]');const b=e.target.closest('button');
  if(b&&b.classList.contains('eadd')){eAddNew(b.dataset.kind);return;}
  if(b&&b.classList.contains('eop')){eOp(b.dataset.op);return;}
  if(b&&b.classList.contains('eundo')&&ED.undo.length){ED.redo.push(JSON.stringify(ED.tasks));ED.tasks=JSON.parse(ED.undo.pop());edRender();return;}
  if(b&&b.classList.contains('eredo')&&ED.redo.length){ED.undo.push(JSON.stringify(ED.tasks));ED.tasks=JSON.parse(ED.redo.pop());edRender();return;}
  if(b&&b.classList.contains('eview')){ED.view=b.dataset.v;ED.root.querySelectorAll('.eview').forEach(x=>x.classList.toggle('on',x===b));edRender();return;}
  if(b&&b.classList.contains('ereset')){if(confirm('すべての変更を取り消しますか？')){eSnap();ED.tasks=JSON.parse(JSON.stringify(ED.orig));ED.sel=null;edRender();}return;}
  if(b&&b.classList.contains('esubmit')){eSubmit();return;}
  if(b&&b.classList.contains('copy'))return;
  if(r&&!(Date.now()-(ED.dragEnd||0)<300&&e.target.closest('svg'))&&(r.classList.contains('ern')||r.classList.contains('erow')||r.classList.contains('ebar')||r.classList.contains('ems')||r.classList.contains('eh')))eSel(r.dataset.id);});
document.addEventListener('change',e=>{if(!ED.root||!e.target.closest('.gepanel,.gebar'))return;const t=eT(ED.sel);
  if(e.target.classList.contains('echain')){ED.chain=e.target.checked;return;}if(!t)return;
  if(e.target.classList.contains('ef'))eSet(t,e.target.dataset.k,e.target.value);
  if(e.target.classList.contains('eaf')){eSnap();t.after=[...ED.root.querySelectorAll('.eaf:checked')].map(c=>c.value);eRipple();edRender();}});
let EDR=null;
document.addEventListener('pointerdown',e=>{const el=e.target.closest('.ged .ebar,.ged .eh,.ged .ems');if(!el)return;const t=eT(el.dataset.id);if(!t)return;
  e.preventDefault();EDR={t,edge:el.dataset.edge||'move',x0:e.clientX,o:JSON.stringify(t),dd:0};});
document.addEventListener('pointermove',e=>{if(!EDR)return;const snap=ED.view==='m1'?1:ED.view==='m3'?1:7;const dd=Math.round((e.clientX-EDR.x0)/ED.ppd/snap)*snap;if(dd===EDR.dd)return;
  EDR.dd=dd;const t=EDR.t,o=JSON.parse(EDR.o);
  if(t.milestone)t.date=eAdd(o.date,dd);else if(EDR.edge==='start')t.start=eAdd(o.start,Math.min(dd,Math.round((pd(o.end)-pd(o.start))/DAY)));
  else if(EDR.edge==='end')t.end=eAdd(o.end,Math.max(dd,-Math.round((pd(o.end)-pd(o.start))/DAY)));else{t.start=eAdd(o.start,dd);t.end=eAdd(o.end,dd);}
  const tmp=ED.chain;ED.chain=false;edRender();ED.chain=tmp;});
document.addEventListener('pointerup',e=>{if(!EDR)return;const R=EDR;EDR=null;if(!R.dd)return;ED.dragEnd=Date.now();const t=R.t,now=JSON.stringify(t);Object.assign(t,JSON.parse(R.o));eSnap();Object.assign(t,JSON.parse(now));
  if(t.start)t.start=eFwd(t.start);if(t.end)t.end=eBack(t.end);if(t.date)t.date=eFwd(t.date);eRipple();ED.sel=t.id;edRender();});
function eSubmit(){const C=ED.root.querySelector('.gechg');const code=C.querySelector('#ecode').value,why=C.querySelector('#ewhy').value.trim();
  if(!code||!why){C.querySelector('.smsg').textContent='理由の区分と理由を入れてください。';return;}
  const {ops,lines}=eDiff();const out=C.querySelector('.gout');
  out.textContent=`工程表の編集\n工程表: ${ED.sid}\n区分: ${code}\n理由: ${why}\n変更:\n${lines.map(l=>'- '+l.s).join('\n')}\n内容: ${JSON.stringify(ops)}`;out.hidden=false;
  C.querySelector('.smsg').innerHTML='申請を作りました（反映待ち）。試作では、この内容をチャットに貼ると反映されます。<button class="copy" type="button">コピー</button>';}
