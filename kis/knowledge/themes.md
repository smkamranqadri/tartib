# Theme

One, bronze. Seven were built on 2026-09-20 and taken out the same day -- the owner had spent
more time on palettes than the feature was worth, and said so. They are in git (`ab9433f`) if
they are ever wanted.

What survived is worth more than the palettes did: `frontend/tools/themes.py` still generates
these values and enforces the floors, and generating them fixed two things hand-written CSS had
missed.

## What choosing palettes established

Two attempts on 2026-09-20 -- six own palettes, then eight named ones, thirteen, ten, all
scrapped; then seven generated ones, built and removed the same day. What they settled is worth
keeping even though none of the palettes were:

- **The accent must not sit in the background's own hue family.** This decides whether a theme
  has character at all: a jade accent on a jade ground is 11 degrees apart and reads as one
  wash, green on indigo is 102 and reads as a theme. Dark teal with amber -- the pairing the
  owner already liked -- is the shape to aim for.
- **Palettes drawn for terminals do not map cleanly.** A terminal theme defines one background
  and this app needs four, and every such palette's own comment colour fails AA on its own
  background, because a comment is *meant* to recede.

Do not re-open the theme question without a reason that is not "more palettes".

## The floors, and the surfaces they are measured on

- **4.5:1** for anything read: body, muted, the four tones, `--accent` and `--accent-2` as text,
  and each ink on the fill it sits on.
- **3:1** for what is not text: the star glyph, and `--session` where it draws the session ring.
- Measured against **the surface the text actually sits on** -- the page, a card, a card header --
  and for a chip, against **its own colour at 12% over the card**, which is what a chip paints
  behind its text. That composite is worth about 0.4 of a ratio point.
- Text sitting directly on the page is measured **where the background glows overlap**, which is
  the brightest the page ever gets. At the obvious glow values muted lands at 4.04:1 there while
  reading 6.32:1 against the flat colour.
- The colour that goes **on** a filled control is the ground. A fill its ink cannot sit on is
  *brightened*, never darkened.

## What ships

```css
:root {
  --bg: #0d0f12; --panel: #181a1d; --head: #222427; --fg: #dfe2e6; --muted: #888b8f;
  --line: #2f3134; --accent: #b98a44; --accent-ink: #0d0f12; --accent-2: #d3a45a;
  --field: #080a0c; --pill: #222427;
  --ok: #4fa36c; --info: #6fa8c9; --warn: #c28a2e; --danger: #da6c69;
  --star: #d3a45a; --session: #e2574b; --session-ink: #0d0f12;
}
```

## The background

Not one flat fill: two soft glows in the accent and a 24px dot grid, all
`background-attachment: fixed` so they stay put while the page scrolls under them. The glow
colour is the accent mixed most of the way into black (75%), because a glow made of the raw
accent lightens the corner and washes the page out. `glow-1` sits at `20% 0%` at 0.50 alpha,
`glow-2` at `80% 40%` at 0.35, the grid is the text colour at 0.03.

The app bar paints **no fill at all** -- only its bottom border -- so the page's glow runs
through it. It can afford to: since 2026-09-20 the bar does not stick, so nothing ever scrolls
underneath it.

Unproved: `background-attachment: fixed` on a real iPhone, where it has historically been
ignored or expensive.

## Notes

- To change a value: change the input in `tools/themes.py`, re-run it, paste
  `tools/out/themes.css` into the palette block of `styles.css`. The floors live in that script
  and nowhere else.
- **Prove a colour by what the browser paints, not by the token.** `--session-ink` was correct
  while `.session-bar .primary` still hardcoded `color: #fff` at 3.69:1, and a probe comparing
  tokens called it fixed.
- An unchecked checkbox stays browser-grey: `accent-color` only paints the checked state.
