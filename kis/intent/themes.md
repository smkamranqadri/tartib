# Themes

Approved 2026-09-19, not yet built. Slice 13 implements this; until then `frontend/src/styles.css`
still carries the teal light/dark pair and `frontend/src/theme.tsx` still types `Theme` as
`"light" | "dark"`.

## The rules

- Three themes -- **slate**, **bronze**, **nous** -- each in a dark and a light variant, so six
  entries. **`slate` dark is the default.**
- The current teal light and dark themes are **dropped**, not kept alongside. Decision 2026-09-19:
  the owner does not want them.
- **No OS following.** The picker lists the six; the choice is stored and stays. The system can
  only say light or dark, so it cannot choose between three hues, and a half-automatic picker is
  worse than an honest manual one.
- Every value below is a flat colour. Tartib's surfaces are opaque and have no backdrop blur, so
  the translucent surfaces these palettes came from are composited against their own background
  here and stored solid.

## Contrast

Measured, not assumed. Body text clears WCAG AA (4.5:1) in all six; white on the accent clears AA
in all six, which the **current light theme does not** -- it is 3.5:1, so today's primary button
fails and these replace something worse, not something better.

| theme | fg on bg | muted on bg | ink on accent |
|---|---|---|---|
| slate dark | 12.3:1 | 6.2:1 | 9.1:1 |
| bronze dark | 16.7:1 | 5.5:1 | 6.2:1 |
| nous dark | 14.7:1 | 5.9:1 | 9.4:1 |
| slate light | 17.0:1 | 4.6:1 | 4.6:1 |
| bronze light | 16.8:1 | 4.6:1 | 4.6:1 |
| nous light | 13.9:1 | 4.6:1 | 4.5:1 |

The dark variants use the theme's own background as accent ink; the light variants use white. The
light variants sit close to the 4.5:1 line by construction -- they were derived by darkening until
they cleared it -- so a later tweak to a light accent or grey has to be re-measured, not eyeballed.

## Dark

```css
:root[data-theme="slate"] {
  --bg: #0d1117; --panel: #151a20; --head: #1c2128; --fg: #c9d1d9; --muted: #8b949e;
  --line: #30363d; --accent: #7eb8f6; --accent-ink: #0d1117; --danger: #f47067;
  --warn: #e6a855; --star: #e6a855; --field: #0a0d12; --pill: #1c2128;
  --shadow: none; color-scheme: dark;
}
:root[data-theme="bronze"] {
  --bg: #0d0f12; --panel: #12161b; --head: #1a2026; --fg: #eceff4; --muted: #7f8a96;
  --line: #332a1d; --accent: #b98a44; --accent-ink: #0d0f12; --danger: #d9534f;
  --warn: #c28a2e; --star: #d3a45a; --field: #0b0d10; --pill: #1a2026;
  --shadow: none; color-scheme: dark;
}
:root[data-theme="nous"] {
  --bg: #041c1c; --panel: #062628; --head: #083031; --fg: #ffe6cb; --muted: #9b9585;
  --line: #36443f; --accent: #ffac02; --accent-ink: #041c1c; --danger: #ff7b7b;
  --warn: #ffac02; --star: #ffe6cb; --field: #031717; --pill: #083031;
  --shadow: none; color-scheme: dark;
}
```

## Light

Derived from each dark theme's accent hue: the accent is darkened until white text on it clears
4.5:1, and the greys are the theme's ink mixed into white so each light variant keeps its parent's
temperature instead of all three collapsing to the same neutral.

```css
:root[data-theme="slate-light"] {
  --bg: #f8f8f8; --panel: #ffffff; --head: #f3f3f4; --fg: #101720; --muted: #6d7177;
  --line: #dedfe0; --accent: #1074e0; --accent-ink: #ffffff; --danger: #a53b31;
  --warn: #a66e1c; --star: #d6a100; --field: #ffffff; --pill: #eeefef;
  --shadow: 0 1px 2px rgba(0, 0, 0, 0.04); color-scheme: light;
}
:root[data-theme="bronze-light"] {
  --bg: #f8f8f8; --panel: #ffffff; --head: #f4f3f3; --fg: #1a1712; --muted: #73716e;
  --line: #dfdfde; --accent: #946e36; --accent-ink: #ffffff; --danger: #a53b31;
  --warn: #a66e1c; --star: #d6a100; --field: #ffffff; --pill: #efefee;
  --shadow: 0 1px 2px rgba(0, 0, 0, 0.04); color-scheme: light;
}
:root[data-theme="nous-light"] {
  --bg: #f8f9f9; --panel: #ffffff; --head: #f4f4f4; --fg: #1c2b2b; --muted: #697373;
  --line: #dfe1e1; --accent: #a06c00; --accent-ink: #ffffff; --danger: #a53b31;
  --warn: #a66e1c; --star: #d6a100; --field: #ffffff; --pill: #eff0f0;
  --shadow: 0 1px 2px rgba(0, 0, 0, 0.04); color-scheme: light;
}
```

## Notes for whoever builds it

- `--accent-ink` is the text colour that sits **on** the accent, not beside it. Getting these two
  the wrong way round is how the current primary button ended up at 3.5:1.
- `nous` light reads as amber-brown rather than the teal-and-amber of its dark parent: a light
  theme cannot keep a near-black teal background, so only the accent hue survives the translation.
  If that looks wrong in the app, change the accent and re-measure rather than lightening the
  background.
- Keep the token names. Every one of the fourteen already exists in `styles.css`, so adding a
  theme is adding a block, not touching a component.
