# Slice 23: the UI language, not the palette

Planned and built 2026-09-20, after the theme attempt was scrapped the same day.
**All seven steps done and proved in the browser; not yet accepted by the owner on a device.**

Five passes were spent on palettes and the owner did not like any of them. Shown screenshots of
an earlier build of their own, the actual diagnosis came out: *"the problem i see the font, border
with accent color, chips, button style, like over all ui is better than our, then may be theme
looks good"*. The colours were never the problem. The app is grey system-sans with plain-text
labels and flat controls; no palette rescues that.

So this slice changes the language and stops choosing colours: **one theme, bronze**, and the
component vocabulary from that earlier build.

## What that vocabulary is

Read off the screenshots, not invented:

- **Monospace everywhere.** Nav, labels, titles, body, numbers. It is the single biggest reason
  those screenshots read as a different app.
- **Uppercase, letter-spaced, muted section labels** -- `AREAS`, `LIBRARY`, `RECENT NOTES`.
  Muted, not accent: the accent lives in chips, bars and buttons.
- **Chips with a coloured border and a tinted fill**, in the tone of what they say --
  `DEVELOPMENT` amber, `LIBRARIAN PROPOSED → REVIEW` green -- and **status pills with a leading
  dot**, `● Needs you · failed`.
- **Pill buttons with a border**, one filled accent button for the primary action.
- **A breadcrumb eyebrow**: `HERMES-HQ // SECOND-BRAIN` above the page title.
- **Bordered stat tiles**: a big number over a mono caps label.
- **A list with thin bars**: each area with a bar sized by what is in it, and a count.

## Decided with the owner

- **Mono everywhere**, including note bodies, accepting that mono is wider and slower in
  paragraphs. Bundled, self-hosted, no CDN -- which is what the backlog's "UI polish" entry
  already asked for.
- **Bronze only, no picker.** `#0d0f12` ground, `#b98a44` accent. The theme system comes out
  entirely: one palette in `:root`, no `theme.tsx`, no Appearance card. A picker can come back
  once the look is settled.
- **All of it, desktop and phone.** A half-restyled app looks worse than either end, and slice 22
  just made the phone the primary surface.
- **All four elements**: chips and pill buttons, the breadcrumb eyebrow, the stat tiles row, and
  the per-space bars.

No backend work: `SpaceSummary` already carries `total`, `open`, `notes` and `overdue` per space,
and `/api/today` already returns `sessions.total`. This is a frontend slice.

## Step 1 — the type

JetBrains Mono 400 and 600 as self-hosted woff2 (~21KB each), `@font-face` with `font-display:
swap`, `--font-mono` on `body`. The scale is re-cut for mono, which is wider than the system sans
at the same size: titles come down, labels take letter-spacing, and the 16px floor on inputs
stays (slice 18 put it there so iOS stops zooming).

## Step 2 — bronze, and the end of the theme system

One palette in `:root`. `theme.tsx`, `ThemeContext`, `readTheme`, the `data-theme` attribute, the
Appearance card and the two `theme-color` metas all go; `index.html` and the manifest take
`#0d0f12`. Semantic tones come with it -- `--ok`, `--info`, `--warn`, `--danger` -- taken from
that build's own bronze block, because chips need tones and one accent is not enough.

This also fixes a live defect recorded in the backlog: `.session-bar .primary` hardcodes
`color: #fff` over `var(--session)`, which is 2.53:1 in the dark theme today. The session colour
gets an ink token, the way `--accent`/`--accent-ink` already work.

## Step 3 — the controls

Buttons become pills with a 1px border, mono, uppercase, letter-spaced; the primary is filled
with the accent and carries `--accent-ink`. Chips take a border in their own tone with a ~10%
tint behind. Status pills gain a leading dot. Inputs and the capture box take the same border and
radius language. Every target stays at or above 44px on a phone (slice 22).

## Step 4 — the page furniture

The eyebrow becomes a breadcrumb -- `TARTIB // TODAY` -- in mono caps. Section labels go mono
caps with wide tracking, muted. The nav pill bar takes the active tab as a filled light pill with
dark text, the way the screenshots show.

## Step 5 — the stat tiles

A row of bordered tiles on Home: today, needs attention, sessions today, recent. Big mono number,
mono caps label under it. All four numbers already arrive with the data Home loads.

## Step 6 — the per-space bars

The Spaces page lists each space with a thin accent bar sized by its `total` against the largest,
and the count beside it. Rule 4 bans charts and history; this is a count of what exists right
now, not a series over time, and the owner was asked directly.

## Step 7 — the phone

The tab bar, the ⊕ sheet, the item sheet and the rows take the same language, with the 44px floor
and the safe areas slice 22 established held exactly.

## Verification

`playwright-core` on channel chrome against the local container: Home, Inbox, Spaces, a space, an
item and Settings, each at 390px and 1280px. Checked rather than assumed: the font actually loads
and is what renders (not a fallback), every control clears 44px on a phone, contrast for the new
tones on their own surfaces, no horizontal scroll at 390px. Then `npm run typecheck && npm run
build`, and `uv run pytest -q` once as a regression check.

## Risk

The owner has sent five passes back. This one changes the language rather than the colours, which
is what they asked for -- but the way to find out early is to build steps 1 to 4, look at it, and
only then do 5 to 7. That is the order.


---

## What was built, step by step

**Step 1 — the type. Done.** JetBrains Mono 400 and 600 as self-hosted woff2 in
`frontend/public/fonts`, `font-display: swap`, preloaded from `index.html` and added to the
service worker's shell precache -- without that an offline launch falls back to whatever mono the
device has and every measurement in this layout shifts. The base size went 15px to 14px and the
line height 1.5 to 1.6: mono sets wider, and the old size overflowed rows that used to fit.
Proof: `document.fonts` reports both weights `loaded`, and `getComputedStyle` on the page's
heading and body both resolve to JetBrains Mono -- not a fallback.

**Step 2 — bronze, and the end of the theme system. Done.** One palette in `:root`.
`theme.tsx` deleted, `ThemeContext`, `readTheme`, the `data-theme` attribute, the Appearance card
and the two `prefers-color-scheme` metas all gone; `index.html` and the manifest carry `#0d0f12`.
Four tones came with it -- `--ok`, `--info`, `--warn`, `--danger` -- because chips say what state
a thing is in and one accent cannot. The live defect is fixed: `--session` has an ink token and
`.session-bar .primary` uses it, so the button that was **2.53:1** is now **5.21:1**.

**Step 3 — the controls. Done.** One shape: a pill with a border. `.primary` is the only filled
control on a screen, `.ghost` is bordered and muted, both mono uppercase and tracked. `.chip` and
`.tone` share one rule -- the tone as text, at 45% as the border, at 12% as the fill -- so a new
state is a class, not a component. `.tone` carries a leading dot.

**Step 4 — the page furniture. Done.** The eyebrow became a breadcrumb, `TARTIB // TODAY`, in
`PageHead` with a `crumb` prop; all five screens pass one. Section labels are mono caps at
`.18em` tracking, muted -- the accent stays in chips, bars and buttons, which is what the
reference does. The active nav tab is a filled light pill with dark text, top and bottom.

**Step 5 — the stat tiles. Done.** `Tiles.tsx`: due today, needs you, sessions, captured. Each
links to the screen that explains it, and shows `…` until its data lands rather than a 0 that is
about to change. No backend change -- every number was already in what Home loads.

**Step 6 — the per-space bars. Done.** The grid of space cards became a list: name, a bar sized
against the fullest space, the count, and when it was last touched. Rule 4 bans charts and
history; this is the present, sized, and the owner was asked directly before it was built.

**Step 7 — the phone. Done.** The tab bar took mono caps labels and the same filled active pill.
Row titles came down to 14px because mono wraps where the old sans did not.

## Verification — what actually ran

- `npm run typecheck`, `npm run build` -- clean. `uv run pytest -q` -- **193 passed, 2
  deselected**, unchanged; this slice touches no backend.
- Phone checks at 390px across Home, Inbox, Spaces and Settings: **every target clears 44px** and
  there is no horizontal scroll on any of them. Two things that failed the first run: the
  harness was measuring a checkbox instead of the 44px `.tap-box` that wraps it, and a capture's
  text on a decision card was a full-width 22px target -- pre-existing, and given the floor here.
- Contrast measured from the running app across every surface a colour is used on:

  | | ratio | floor |
  |---|---|---|
  | body text on the page / on a card | 16.65 / 15.76 | 4.5 |
  | muted on the page / card / card header / field | 6.32 / 5.98 / 5.41 / 6.40 | 4.5 |
  | ADD button ink on accent | 6.20 | 4.5 |
  | tile number and space chip on a card | 7.98 | 4.5 |
  | ok / info / warn / danger chip on a card | 5.87 / 7.02 / 6.03 / 4.58 | 4.5 |
  | session button ink on session | 5.21 | 4.5 |
  | star glyph / session ring on a card | 7.98 / 4.93 | 3.0 |

- Looked at: Home, Spaces and Inbox at 1280 and 390.

## Still open

Everything was proved headless. What needs a device: whether mono at 14px is comfortable for a
long note on a phone -- the one decision in here taken knowingly against readability -- and
whether the wrapped two-line row titles are acceptable or want a smaller size again.


## Step 8 — the bar stops covering things (2026-09-20, after the owner looked)

The owner's report was two words -- *"space issue, navbar hids it"* -- and it was the real defect
behind three rounds of complaints about that bar. The header had been `position: sticky` since
slice 18, so everything scrolled underneath it and sat behind a translucent band: the capture
box, the update strip, the first card. Every previous attempt treated it as a colour problem --
match the page, add a border, raise the opacity -- and none of those could fix a bar that covers
what you are reading.

It is `position: relative` now. It scrolls away with the page, so nothing can be behind it; the
`::before` drops the glass for a solid `--bg` and keeps a 1px `--line` bottom border. On a phone
there is no header at all (slice 22) and the nav is the tab bar, so this changes nothing there.

Proof: at scroll 0, 200 and 500 the bar's computed position is `relative`, its bottom edge is
above the viewport once scrolled, and `elementFromPoint` at the top row of the viewport returns
the page's own content rather than the header. Screenshot at 500px shows content running to the
top edge. Phone checks, contrast and typecheck all still pass.


## Step 9 — the batch after the owner used it (2026-09-20)

Seven things, all of them specific.

**One control height.** Measured before touching anything: `.primary` was 39px, `.ghost` 37px,
the ADD button 39px, the mic 44px -- nothing agreed with anything. There is now a `--control`
token, 32px on a pointer and 44px on a phone, and every button, icon button and field control
takes it. Buttons dropped to 11px type with no vertical padding, which is what "bigger than
others in the app" actually was.

**The decision card uses its width.** It was a vertical stack in a 1198px card, so everything sat
in the first third and the rest was empty. The reading half is now a `.one-main` column and the
decisions sit beside it, right-aligned: the actions start 857px in and end 16px from the card's
right edge. On a phone it stacks again, controls at 44px.

**The ⋯ menus are gone**, both of them. The item page shows START SESSION, EDIT and DELETE as
pills; the space page shows its filing policy as a visible AUTO / ASK / FILE segment with RENAME
and DELETE beside it. Neither menu ever held more than five things, and the policy is a space's
most consequential setting -- it does not belong three taps deep.

**Spaces went back to cards**, as asked, but keeping what the list added: name and count on one
line, the bar underneath sized against the fullest space, then what is in it and when it was last
touched.

**Capture is a panel.** The field owns the top of a bordered box; under a rule sit the mic, a hint
("the first line becomes the title"), and the one filled button, right-aligned. As a single row
the field and the buttons were fighting for width.

**The nav's empty right third now carries readouts** rather than nothing: a `● N NEEDS YOU` chip
linking to the Inbox, and the clock. Readouts, not controls -- the nav is for going places.

Proof: every control measures 32px on a pointer; all four phone screens still clear 44px with no
horizontal scroll; typecheck and build clean; no page errors. Looked at: Home, Spaces and the
decision card at 1280, the card and Home at 390.
