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
type: study
title: "<% title %>"
owner: ""        # your user ID (filled automatically by the plugin in production)
project: ""      # project ID (e.g. P00001). Setting it applies the project's default keys
status: draft
access: []       # keys (confidentiality tags). Empty = only you
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
progress: 検討中   # 検討中 / レビュー待ち / 完了 / 保留 (fixed values read by the system)
next: ""
---

## Purpose
<!-- What this study decides or clarifies -->

## Assumptions and conditions

## Study
<!-- Compare the options. If the drawing is the main content, use "study-drawing" -->

## Conclusion

## Rejected options and why

## To-do
<!-- To link to a schedule task, add [task:: scheduleID#T02] -->
- [ ] 
