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
type: meeting
title: "<% title %>"
owner: ""        # your user ID (filled automatically on push)
project: ""      # project ID (e.g. P00001). Setting it applies the project's default keys
status: draft
access: []       # keys (confidentiality tags). Empty = only you
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
excalidraw-plugin: parsed
---

## Date and place

## Attendees

## Purpose

## Decisions

## Action items
<!-- Give each an owner and a due date. Action items appear in the owner's to-do list -->
<!-- - [ ] item 📅 YYYY-MM-DD -->

## Next meeting

%%
# Excalidraw Data
## Text Elements

## Embedded Files

## Drawing
```json
{"type":"excalidraw","version":2,"elements":[],"appState":{},"files":{}}
```
%%
