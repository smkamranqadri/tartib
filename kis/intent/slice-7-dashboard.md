# Slice 7: dashboard restyle (approved 2026-09-17)

Inspiration: user's screenshots of another Tartib prototype. Take the structure and visual language; leave out pomodoro, push, projects (rules).

## Decisions
- Nav: Home · Inbox · Search · Settings. Capture bar in the header on every screen (input, mic when supported, Add). Chat bar stays on Home and Inbox only.
- Home: eyebrow DASHBOARD, title = today's date. Two columns from 900px: Today + Recent (last 10) | Needs Attention (top 3).
- Rows: title, muted meta "space · 2h ago" (or "needs attention"), "due Fri, Sep 18" at the right, overdue tint, hover actions.
- Inbox = the one-card queue ("Awaiting approval") + "Stale tasks" (open, filed, untouched 14+ days).
- Search absorbs Spaces: chips for space and shape; empty + All -> space cards; empty + a space -> that space's brief/tasks/notes; query -> grouped results. Old routes redirect.
- Settings: theme, voice capture availability, timezone, installed, spaces, sign out. Read-only except theme and sign out.
- Backend: GET /api/config; /api/attention gains `stale`; Recent returns 10.

## Acceptance
- Home two columns at 1280, one at 390; counts match the API; header capture from Search files with a toast.
- Inbox: Enter ×3 clears the queue; a 14-day-old open task shows under Stale tasks only.
- Search: chips filter; a space chip alone shows its brief; "?" answers scoped.
- Settings shows timezone and spaces; sign out returns to login.
- Mic button present in Chrome only; dictated text lands in the box.

## Status
- [x] phase 1 backend + tokens + shell + header capture
- [x] phase 2 home + rows + inbox
- [x] phase 3 search + settings + voice
- [x] phase 4 proof + deploy (2026-09-17, see kis/state/current.md)
