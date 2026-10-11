<%*
// Name the file "YYMMDD_title" (rename it freely later). The id property "YYMMDD-hash" is what stays unique (hash: 5 chars from 32, excluding 0/o/1/l)
const A = 'abcdefghijkmnpqrstuvwxyz23456789'; let h = ''; for (let i = 0; i < 5; i++) h += A[Math.floor(Math.random() * A.length)];
const d = tp.date.now("YYMMDD");
let title = /^(無題|Untitled)/.test(tp.file.title) ? await tp.system.prompt("Project summary title (e.g. X200 昇降ステージ改良)") : tp.file.title;
title = (title || "Untitled").replace(/[\\/:*?"<>|#^\[\]]/g, "_").slice(0, 40);
const dir = tp.file.folder(true); let name = `${d}_${title}`;
for (let n = 2; await app.vault.adapter.exists(`${dir ? dir + "/" : ""}${name}.md`); n++) name = `${d}_${title} ${n}`;   // same name exists -> add 2, 3 ...
await tp.file.rename(`${name}`);
-%>
---
id: <% d %>-<% h %>
type: project    # 案件まとめ：この案件の起点。アーカイブ（notebase.cmd archive <案件ID>）はここからリンクをたどる
owner: ""        # your user ID (filled automatically on push)
project: ""      # project ID (e.g. P00001). Required for a project summary
status: draft
access: []       # keys (confidentiality tags). Empty = only you
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
---

## Purpose and goal

## Members and roles

## Schedule
<!-- The schedule itself is edited with dotpm (20_工程/<project>/). Put milestones and links here -->

## Key notes
<!-- Link the notes that make up this project: requirements, studies, calculations, reports, meeting minutes.
     Archiving follows these links (and the notes' project property) -->
- 

## Decisions and open issues
