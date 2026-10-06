<%*
// Name the file "YYMMDD_title_hash" and put the same value in the id property (hash: 5 chars from 32, excluding 0/o/1/l)
const A = 'abcdefghijkmnpqrstuvwxyz23456789'; let h = ''; for (let i = 0; i < 5; i++) h += A[Math.floor(Math.random() * A.length)];
const d = tp.date.now("YYMMDD");
let title = /^(無題|Untitled)/.test(tp.file.title) ? await tp.system.prompt("Title (max 40 characters)") : tp.file.title;
title = (title || "Untitled").replace(/[\\/:*?"<>|#^\[\]]/g, "_").slice(0, 40);
await tp.file.rename(`${d}_${title}_${h}.excalidraw`);
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
