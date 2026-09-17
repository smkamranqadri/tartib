# Slice 10: one header convention, one component per pattern (approved 2026-09-17)

## Header rules
- **Eyebrow** names the page only when the title does not. Home's title is a date, so it keeps DASHBOARD. Inbox, Spaces, and Settings say their own name and drop it. Drill-downs keep it for context next to Back.
- **Subtitle** says what the page is for, on every page, and never carries a count. Counts live in the card header that owns them.
- **Back** is one control, `BackLink`, history-aware with a per-page fallback. No hand-rolled links, no breadcrumb trails.

```text
Route              Back    Eyebrow    Title                    Subtitle
/                  —       DASHBOARD  <today's date>           Today, what needs you, and what you captured.
/inbox             —       —          Inbox                    Approve what the classifier proposed, or file it yourself.
/spaces            —       —          Spaces                   Where things live. Search across all, or end with ? to ask.
/settings          —       —          Settings                 How this copy of Tartib is set up.
/inbox/attention   Back    INBOX      Everything waiting       Every item that needs a decision.
/inbox/recent      Back    INBOX      Everything you captured  Newest first, filed or not.
/spaces/{name}     Back    SPACES     <space name>             Brief, tasks, and notes in this space.
/items/{id}        Back    —          —                        — (the card holds the item)
```

Old paths redirect: `/attention` -> `/inbox`, `/attention/all` -> `/inbox/attention`, `/recent` -> `/inbox/recent`. Recent belongs to Inbox. `/api/attention` unchanged.

## One component per pattern
`Row` (the list row primitive; `ItemRow` and the capture row compose it), `Menu` (the "…" dropdown, closing on outside click and Escape), `Confirm` (inline delete confirmation), `NameForm` (create and rename), `Card` gains collapsible/open/onToggle for accordions, `Loading` and `ErrorLine`. One primary button class; `.ask-btn` removed. `formatCreated` deleted.

Leading glyph vocabulary: checkbox = filed task, alert = needs a decision, note = note.

## Status
- [x] components + screens
- [x] proof + deploy (2026-09-17, see kis/state/current.md)
