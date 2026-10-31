---
id: <%* const id = await tp.user.make_id(tp); tR += id; if (!/^[0-9A-Z]{6}[0-9A-Z]+_/.test(tp.file.title)) { await tp.file.rename(id + "_" + tp.file.title); } %>
type: 議事録
kind: DR              # DR の議事録の印(ふつうの議事録と分ける)
aliases: [<%* const nm = tp.file.title.replace(/^[0-9A-Z]{6}[0-9A-Z]+_/, ""); if (nm && !nm.startsWith("無題")) tR += JSON.stringify(nm); %>]
date: <% tp.date.now("YYYY-MM-DD") %>
attendees: []         # 判定した人
parent: []            # 目的
project: [<%* tR += await tp.user.place_note(tp) %>] # 親がないときだけ。Ctrl+N で選んだプロジェクトが入る(親があれば空のまま)
---
## 議題
判定するイシュー(イシュー一覧の「DR 用」ビューから)
## 解像度の判定
1行に1つ、「- イシューのリンク: 現象 → 設計空間(根拠)」の形で。決まったら、イシューの resolution も直す
## 使ったトレードオフ曲線
絞り込みの根拠にしたナレッジ・設計案をリンクで。線が目標に届かない案は不採用の根拠になる
## 絞り込み
一組の候補(設計案一覧の「候補の一組」ビューから)を、「- 候補のリンク: 採用(どの条件なら勝つか)」の形で。決まったら設計案の status も直す
## 出た指摘・懸念
impact 中以上はイシューにしてリンクで
## 決まったこと
タスクにするものは行で Ctrl+L を押して - [ ] に。期日は 📅 と日付(年-月-日)を後ろに
