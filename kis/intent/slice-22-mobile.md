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

On phones only: Home, Inbox, ⊕, Spaces, Settings, fixed at the bottom, glass like the rest, with
the bottom safe-area inset, 44px targets and the active tab marked. The top keeps a slim bar:
the page title and its actions, nothing else. The desktop nav does not change.

## Step 2 — the ⊕ sheet: capture, or ask

⊕ opens a sheet from the bottom, most of the screen tall, with two modes: Capture (the box, the
mic, Add -- the offline queue and every existing behaviour unchanged) and Ask (the question, the
space, the answer in place). Escape, a tap outside, or the handle closes it; opening focuses the
field. With the sheet closed there is no capture box and no ask bar on a phone, which is where
the ~190px comes from.

## Step 3 — one line of heading

On a phone the eyebrow and subtitle go; a screen shows its title and its actions on one row, with
Back where there is somewhere to go back to. The space page keeps its name, "+ Add" and "…" on
that row. The desktop keeps its headings.

## Step 4 — targets worth hitting

Every control reaches 44x44 on a phone: the row checkbox and star, the "…" buttons, the pills,
the brief strip, the session card's buttons. Counted before and after.

## Step 5 — the session, smaller

While floating on a phone the session card is one line -- ring, time, task, Stop -- and the
outcome buttons wrap to a second only when it is asking. Home's card is unchanged.

## Step 6 — what the desktop takes

Whatever improved both: the 44px targets, and headings trimmed where they only repeated the nav.
The desktop keeps its top nav, its capture bar and its ask bar.

## Proof

Measured again at 390x844: fixed furniture under 130px with nothing open, content at least
doubled; every control 44px or more; capture, ask, the offline queue, sessions and navigation all
still work from the new bar; screenshots in light and dark; the desktop unchanged where it was
meant to be.

## Out of scope

Backups, the deploy, slices 13 and 14, and anything that changes what the app does rather than
how it is reached.
