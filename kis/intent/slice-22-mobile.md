# Slice 22: the phone comes first (approved 2026-09-20)

Measured at 390x844 before starting: the header (104px), the capture box (70px) and the ask bar
(116px) are always on screen -- 290px of 844. With a session live that is 439px, **52% of the
screen**; on Home, where the session card is larger, 527px, **62%**. What you touch most, the nav
and capture, sits at the top, furthest from the thumb; the bottom is held by the ask bar, which
is used least. Page headings repeat the nav (a space costs four lines: Back, SPACES, name,
subtitle). Between 16 and 30 controls per screen are under 40px, against the 44px guidance.

Decided with the user: bottom nav with capture as a button, phone first and the desktop follows
where the change helps both. Ask lives inside the capture sheet as a second mode rather than
taking a sixth tab -- five is what fits at 390px, and Spaces cannot be dropped.

## Step 1 — a bottom bar under the thumb

**Done 2026-09-20.** `TabBar` on phones only, wearing the top nav's own shape: a rounded glass
pill floating clear of the edges, the active tab in a panel-coloured pill, the ⊕ in the accent.
Safe areas on all three sides that matter -- with a 34px home indicator emulated it sits 42px
above the screen edge, 10px in from each side. the top header is hidden there entirely, since the
page's own title says where you are. It publishes `--tabbar-h`, so the ask bar, the floating
session card, the toast and the page's bottom padding all stack above it. Proof: 390x844 --
header 0 (was 104), tab bar 65, the ask bar sitting exactly on top of it, chrome down from 439
to 400 with a session live (the rest is step 2's); tapping Spaces navigates and marks the tab;
⊕ focuses the capture box for now. At 1280px the header is still there and the bar is not.

On phones only: Home, Inbox, ⊕, Spaces, Settings, fixed at the bottom, glass like the rest, with
the bottom safe-area inset, 44px targets and the active tab marked. The top keeps a slim bar:
the page title and its actions, nothing else. The desktop nav does not change.

## Step 2 — the ⊕ sheet: capture, or ask

**Done 2026-09-20.** The ask form left `AskBar` into `AskForm`, so the bar (wide) and the sheet
(phone) share it and only one is ever mounted -- App renders the capture bar and the ask bar
above 641px, the tab bar and the sheet below. Two modes in the sheet, Escape or the scrim
closes it, capture closes it on success. One thing the plan missed: with the sheet shut, a phone
has no ask form at all, so a question handed over from a space's search box was dropped; App now
catches `tartib:ask` on phones, opens the sheet in Ask mode and hands the question to the form,
which asks it on mount. Proof at 390x844: with the sheet closed, capture bar 0, ask bar 0, tab
bar 65 -- chrome 439 -> 214 with a session live, Inbox content 786 -> 973; ⊕ opens focused on the
box, "Captured from the sheet" reached the server and the sheet closed; Ask mode shows question
and space; scrim and Escape both close; a question typed in a space opened the sheet in Ask mode
holding it.

⊕ opens a sheet from the bottom, most of the screen tall, with two modes: Capture (the box, the
mic, Add -- the offline queue and every existing behaviour unchanged) and Ask (the question, the
space, the answer in place). Escape, a tap outside, or the handle closes it; opening focuses the
field. With the sheet closed there is no capture box and no ask bar on a phone, which is where
the ~190px comes from.

## Step 3 — one line of heading

**Done 2026-09-20.** On phones the eyebrow and the subtitle are hidden and the title drops to
20px: the tab bar already says which section this is. A row whose actions are buttons keeps them
beside the title (`:not(:has(.tabs))`); the Inbox's tab strip still gets its own full-width row,
because three tabs do not fit beside a title at 390px. Proof: the heading block is 30px on Home,
Inbox, a space and Settings (was 100-130); a space's title row is 41px holding "+ Add" and "…";
no horizontal overflow.

On a phone the eyebrow and subtitle go; a screen shows its title and its actions on one row, with
Back where there is somewhere to go back to. The space page keeps its name, "+ Add" and "…" on
that row. The desktop keeps its headings.

## Step 4 — targets worth hitting

**Done 2026-09-20.** Minimums on phones for every control: icon buttons, pills, chips, segmented
buttons, the star, accordion toggles, "View all" and the other inline links, the proposal
sentence's tappable words, and the row and line buttons. The checkboxes keep their 22px look
inside a 44px label, so the hit area is real without a giant box. Rows settled at 48px (a line)
and 52px (a card row) -- a first pass gave the title its own 44px and rows came out at 125px,
which read as a list of five things on a screen. Proof: the audit that found 16 to 30 controls
under 44px a screen now finds none on Home, Inbox, Recent, a space, an item or Settings, with
rows at 48px and nine of them on one screen.

Every control reaches 44x44 on a phone: the row checkbox and star, the "…" buttons, the pills,
the brief strip, the session card's buttons. Counted before and after.

## Step 5 — the session, smaller

**Done 2026-09-20 with step 4.** The floating card is tighter on a phone: 8px padding, a 34px
ring, 17px clock. Running it is one line. Asking for an outcome is 134px, because three outcome
buttons cannot sit on one 390px row and still be 44px tall -- that is the two lines the plan
allowed.

While floating on a phone the session card is one line -- ring, time, task, Stop -- and the
outcome buttons wrap to a second only when it is asking. Home's card is unchanged.

## Step 6 — what the desktop takes

**Done 2026-09-20.** Above 641px: icon buttons, the star and the accordion toggles reach 36px,
a card row 46px, a line 40px. Nothing else moves -- the header, the capture bar, the ask bar,
the eyebrow and the subtitle are all still there, confirmed by measurement (header 67, capture
46, ask 64, no tab bar, eyebrow and subtitle present).

Whatever improved both: the 44px targets, and headings trimmed where they only repeated the nav.
The desktop keeps its top nav, its capture bar and its ask bar.

## Proof, 2026-09-20

Measured at 390x844 after all six steps. Fixed furniture: **65px**, the tab bar alone, against
290px before (header 104 + capture 70 + ask 116) -- and the target was "under 130". Content
grew: Home 1198 -> 1366, Inbox 786 -> 1200. With a session live the total chrome is 199 on the
Inbox against 439. No control is under 44px on Home, Inbox, Recent, a space, an item or
Settings, where the audit had found 16 to 30 a screen. Capture, ask, the hand-off from a space's
search box, navigation and sessions all work from the new bar; offline, a capture made in the
sheet toasted "Saved offline", showed as "waiting to send" on Home, and went up when the network
came back. Screenshots in light and dark. The desktop is unchanged but for the larger targets.

## After the first look, 2026-09-20

The top safe area was gone: the only `env(safe-area-inset-top)` was on the header, which phones
no longer render, so an installed app would have drawn its first line under the status bar. The
page itself now reserves it (`.app` padding-top on phones) -- with a 47px notch emulated, the
first thing on the page sits at 47.

And an item is read in a sheet on a phone: a row puts `?item={id}` on the current URL and the
sheet opens over the list, which keeps its place and its scroll; Back, Escape, the scrim and ✕
all close it. The item page is the same component inside, so editing, thoughts and the menu work
there. The desktop still opens `/items/{id}` as its own page, and a wide space page still uses
its side pane. Proof: a row on a space and a row on Home each opened the sheet with the right
item; Back closed it and cleared the URL; a thought added inside the sheet stuck; on a desktop
the same row navigated to `/items/13` with no sheet.

Then, same day, three from the device: the Inbox tabs stretched to equal widths on a phone, which
cut "Needs attention 18" through its own count -- each pill keeps its own width now and the strip
scrolls if it must. On a decision card, "Tell it why…" left the "…" menu for the row of buttons
where the decision is made, and the capture's own words became the way into the item (a link on a
wide screen, the sheet on a phone), which emptied the menu, so it is gone. Proof: the three tabs
measure 148/82/66px with their counts inside and no page overflow; a card shows Approve, Not now
and Tell it why… with no menu, the reason field opens from the button, and the title opened
`?item=17` in the sheet on a phone and `/items/17` on a desktop.

## Out of scope

Backups, the deploy, slices 13 and 14, and anything that changes what the app does rather than
how it is reached.
