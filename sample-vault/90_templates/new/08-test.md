<%*
// Name the file "YYMMDD_title" (rename it freely later). The id property "YYMMDD-hash" is what stays unique (hash: 5 chars from 32, excluding 0/o/1/l)
const A = 'abcdefghijkmnpqrstuvwxyz23456789'; let h = ''; for (let i = 0; i < 5; i++) h += A[Math.floor(Math.random() * A.length)];
const d = tp.date.now("YYMMDD");
let title = /^(無題|Untitled)/.test(tp.file.title) ? await tp.system.prompt("Test title (max 40 characters)") : tp.file.title;
title = (title || "Untitled").replace(/[\\/:*?"<>|#^\[\]]/g, "_").slice(0, 40);
const dir = tp.file.folder(true); let name = `${d}_${title}`;
for (let n = 2; await app.vault.adapter.exists(`${dir ? dir + "/" : ""}${name}.md`); n++) name = `${d}_${title} ${n}`;   // same name exists -> add 2, 3 ...
await tp.file.rename(`${name}`);
-%>
---
type: test
id: <% d %>-<% h %>
owner: ""        # your user ID (filled automatically on push)
project: ""      # project ID (e.g. P00001)
status: draft    # draft -> review (required items are checked on push) -> approved only by an approval note of the approver
access: []       # keys (confidentiality tags). Empty = only you
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
verifies: []     # requirements this test verifies, e.g. ["[[YYMMDD_requirement]]"]
test_result: ""  # 合格 / 不合格 / 未実施
tested: ""       # date of the test (YYYY-MM-DD). Used to find tests done before the requirement changed
---

## Conditions

## Result

## Judgement against the criterion
