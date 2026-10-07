<%*
// Weekly note: one per person per week. The file name stays the week set by Periodic Notes ("2026-W41") so "this week's note" can be opened
const A = 'abcdefghijkmnpqrstuvwxyz23456789'; let h = ''; for (let i = 0; i < 5; i++) h += A[Math.floor(Math.random() * A.length)];
const d = tp.date.now("YYMMDD");
const base = /^\d{4}-W\d{2}$/.test(tp.file.title) ? window.moment(tp.file.title, "GGGG-[W]WW") : window.moment();   // week from the file name (this week if none)
const mon = base.clone().isoWeekday(1), sun = base.clone().isoWeekday(7), next = base.clone().isoWeekday(8);
const title = "Week of " + mon.format("YYYY-MM-DD");
-%>
---
id: <% d %>-<% h %>
type: weeknote
owner: ""        # your user ID (filled automatically on push)
project: ""
status: draft
access: []       # only you. The weekly-report part is split by project into weekly reports (type: weekly) on Friday
created: <% tp.date.now("YYYY-MM-DD") %>
updated: <% tp.date.now("YYYY-MM-DD") %>
summary: ""
week: <% mon.format("YYYY-MM-DD") %>
---

# <% title %> (<% mon.format("M/D") %> - <% sun.format("M/D") %>)

## Goals this week (up to 3)
1. 
2. 
3. 

## Weekly report (fill in on Friday → split into per-project weekly reports)
<!-- One line = one schedule task. Only "forecast" is required. To-do counts (done/total) and hours are filled in automatically
     Format: - [task:: scheduleID#T02] forecast:: YYYY-MM-DD | did:: … | issue:: …
     To record actuals: start:: YYYY-MM-DD / end:: YYYY-MM-DD (dates after today are not allowed)
     Work not in the schedule: - [task:: unplanned] project:: P00001 | did:: … -->

### Project 
- [task:: ] forecast:: | did:: | issue:: 

## Done this week
```tasks
path does not include 90_templates
done on or after <% mon.format("YYYY-MM-DD") %>
done on or before <% sun.format("YYYY-MM-DD") %>
group by filename
```

## Next week (due next week)
```tasks
path does not include 90_templates
not done
due on or after <% next.format("YYYY-MM-DD") %>
due on or before <% base.clone().isoWeekday(14).format("YYYY-MM-DD") %>
sort by due
```

## Overdue
```tasks
path does not include 90_templates
not done
due before <% mon.format("YYYY-MM-DD") %>
```

## Unsorted (to be classified)
![[00_分類.base#未分類]]

## Retrospective (private, not included in the weekly report)
- What went well:
- What was hard:
- What to try next:
