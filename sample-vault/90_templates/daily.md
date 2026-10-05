<%*
// Daily note. The file name stays the date set by Periodic Notes ("2026-10-05") so "today's note" can be opened
const A = 'abcdefghijkmnpqrstuvwxyz23456789'; let h = ''; for (let i = 0; i < 5; i++) h += A[Math.floor(Math.random() * A.length)];
const d = tp.date.now("YYMMDD");
const day = /^\d{4}-\d{2}-\d{2}$/.test(tp.file.title) ? window.moment(tp.file.title, "YYYY-MM-DD") : window.moment();   // date from the file name (today if none)
const title = "Daily " + day.format("YYYY-MM-DD");
-%>
---
id: <% d %>-<% h %>
type: daily
title: "<% title %>"
owner: ""        # your user ID (filled automatically by the plugin in production)
project: ""
status: draft
access: []       # keys (confidentiality tags). Empty = only you
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
---

# <% day.format("YYYY-MM-DD (ddd)") %>

## Schedule
<!-- Day Planner: write items with a time range. When logging afterwards (e.g. an experiment), use the same form and check it off -->
- [ ] 09:00 - 10:00 
- [ ] 13:00 - 15:00 

## Open to-dos
```tasks
path does not include 90_templates
not done
sort by due
group by filename
```

## Unsorted (to be classified)
![[未分類.base]]

## Notes

