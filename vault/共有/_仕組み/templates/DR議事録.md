---
id: <%* const id = await tp.user.make_id(tp); tR += id; if (!/^[0-9A-Z]{6}[0-9A-Z]+_/.test(tp.file.title)) { await tp.file.rename(id + "_" + tp.file.title); } %>
type: 議事録
kind: DR              # DR の議事録。週報の行き詰まりの判定で、前回の DR の日に使う
aliases: [<%* const nm = tp.file.title.replace(/^[0-9A-Z]{6}[0-9A-Z]+_/, ""); if (nm && !nm.startsWith("無題")) tR += JSON.stringify(nm); %>]
date: <% tp.date.now("YYYY-MM-DD") %>
attendees: []         # 判定した人。例: [Yu, 佐藤]
parent: []            # 目的
---
## 議題
判定するイシュー(イシュー一覧の「DR 用」ビューから)
## 解像度の判定
1行に1つ、「- [[イシュー]]: 現象 → 設計空間(根拠)」の形で。決まったら、イシューの resolution も直す
## 絞り込み
一組の候補(ソリューション一覧の「候補の一組」ビューから)を、「- [[候補]]: 採用(どの条件なら勝つか)」の形で。決まったらソリューションの status も直す
## 出た指摘・懸念
impact 中以上はイシューにして [[ ]] で
## 決まったこと
タスクにするものは行で Ctrl+L を押して - [ ] に。期日は 📅 2026-10-31 の形で後ろに
