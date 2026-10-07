<%*
// Name the file "YYMMDD_title" (rename it freely later). The id property "YYMMDD-hash" is what stays unique (hash: 5 chars from 32, excluding 0/o/1/l)
const A = 'abcdefghijkmnpqrstuvwxyz23456789'; let h = ''; for (let i = 0; i < 5; i++) h += A[Math.floor(Math.random() * A.length)];
const d = tp.date.now("YYMMDD");
let title = /^(無題|Untitled)/.test(tp.file.title) ? await tp.system.prompt("Title (max 40 characters)") : tp.file.title;
title = (title || "Untitled").replace(/[\\/:*?"<>|#^\[\]]/g, "_").slice(0, 40);
const dir = tp.file.folder(true); let name = `${d}_${title}`;
for (let n = 2; await app.vault.adapter.exists(`${dir ? dir + "/" : ""}${name}.md`); n++) name = `${d}_${title} ${n}`;   // same name exists -> add 2, 3 ...
await tp.file.rename(name);   // drawings are plain .md too (Excalidraw recognises them by the excalidraw-plugin property)
tp.hooks.on_all_templates_executed(async () => {   // open again once written, so it shows as a drawing (not as text)
  await new Promise(r => setTimeout(r, 300)); const f = app.vault.getAbstractFileByPath(`${dir ? dir + "/" : ""}${name}.md`);
  if (f) await app.workspace.getLeaf(false).openFile(f);
});
-%>
---
id: <% d %>-<% h %>
type: ""         # empty = unsorted (see 00_分類.base). Set later: study / calc / req / memo ...
title: "<% title %>"
owner: ""        # your user ID (filled automatically on push)
project: ""      # project ID (e.g. P00001). Setting it applies the project's default keys
status: draft
access: []       # keys (confidentiality tags). Empty = only you
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
progress: ""     # 検討中 / レビュー待ち / 完了 / 保留 (for studies)
next: ""
excalidraw-plugin: parsed
---

## Purpose

## Conclusion

## Rejected options and why

## To-do
<!-- - [ ] what to do 📅 YYYY-MM-DD   (empty checkboxes would show up in the to-do lists) -->

%%
# Excalidraw Data
## Text Elements

## Embedded Files

## Drawing
```json
{"type":"excalidraw","version":2,"elements":[],"appState":{},"files":{}}
```
%%
