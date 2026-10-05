<%*
// Name the file "YYMMDD_title_hash" and put the same value in the id property (hash: 5 chars from 32, excluding 0/o/1/l)
const A = 'abcdefghijkmnpqrstuvwxyz23456789'; let h = ''; for (let i = 0; i < 5; i++) h += A[Math.floor(Math.random() * A.length)];
const d = tp.date.now("YYMMDD");
let title = /^(無題|Untitled)/.test(tp.file.title) ? await tp.system.prompt("Title (max 40 characters)") : tp.file.title;
title = (title || "Untitled").replace(/[\\/:*?"<>|#^\[\]]/g, "_").slice(0, 40);
await tp.file.rename(`${d}_${title}_${h}`);
-%>
---
id: <% d %>-<% h %>
type: report
title: "<% title %>"
owner: ""        # your user ID (filled automatically by the plugin in production)
project: ""      # project ID (e.g. P00001). Setting it applies the project's default keys
status: draft
access: []       # keys (confidentiality tags). Empty = only you
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
progress: 検討中   # 検討中 / レビュー待ち / 完了 / 保留
next: ""
based_on: []
---

## Summary
<!-- 3 lines. Conclusion and requests first -->

## Slides (exported to PDF in this order)
<!-- Embed frames from each note's drawing, e.g. ![[YYMMDD_title_hash.excalidraw#F02]] -->

## Conclusion and requests

## Supporting material
