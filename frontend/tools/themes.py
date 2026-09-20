"""Build Tartib's theme blocks.

    python3 frontend/tools/themes.py

Prints a contrast table and every step taken, and writes tools/out/themes.css -- the block list
to paste into the palette section of src/styles.css -- plus tools/out/expected.json for the
proof harness. Changing a theme means changing its inputs here and re-running; never hand-edit a
hex in styles.css, where nothing enforces a floor.

A palette gives three or four colours. The app needs nineteen tokens on four surfaces, so the
rest is derived from that palette's own ground and text, and every derived value is checked
against the surface it will actually sit on.

Floors: 4.5:1 for anything read (body, muted, the tones as text, and each ink on its own fill),
3:1 for what is not text (the star glyph, and --session where it draws the session ring).
"""
import json
import pathlib

OUT = str(pathlib.Path(__file__).parent) + "/out/"
pathlib.Path(OUT).mkdir(exist_ok=True)


def h2r(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def r2h(r):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in r)


def mix(a, b, t):
    ra, rb = h2r(a), h2r(b)
    return r2h(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def lum(h):
    c = [x / 255 for x in h2r(h)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def cr(a, b):
    l1, l2 = sorted([lum(a), lum(b)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


STEPS = []


def lift(colour, surfaces, toward, target, name):
    """Step `colour` toward `toward` until it clears `target` on every surface it sits on."""
    worst = min(cr(colour, s) for s in surfaces)
    if worst >= target:
        return colour
    for i in range(1, 101):
        c = mix(colour, toward, i / 100)
        if min(cr(c, s) for s in surfaces) >= target:
            STEPS.append(f"{name}: {colour} -> {c} ({worst:.2f} -> {min(cr(c, s) for s in surfaces):.2f})")
            return c
    return toward


def dim(colour, bg, ceiling, name):
    """Muted must read as secondary: step back toward the ground while it stays above 4.6."""
    if cr(colour, bg) <= ceiling:
        return colour
    for i in range(1, 101):
        c = mix(colour, bg, i / 100)
        if cr(c, bg) <= ceiling:
            if cr(c, bg) < 4.6:
                break
            STEPS.append(f"{name}: {colour} -> {c} (dimmed to {cr(c, bg):.2f})")
            return c
    return colour


def lift_chip(colour, panel, fg, target, name):
    """A chip paints its own colour at 12% behind its text, so the surface moves as the colour
    does. Measure against that composite, not against the bare card -- the difference is about
    0.4 of a ratio point, which is exactly the margin these palettes have."""
    surface = mix(panel, colour, 0.12)
    if cr(colour, surface) >= target:
        return colour
    for i in range(1, 101):
        c = mix(colour, fg, i / 100)
        if cr(c, mix(panel, c, 0.12)) >= target:
            STEPS.append(f"{name}: {colour} -> {c} (on its own 12% fill, {cr(colour, surface):.2f} -> {cr(c, mix(panel, c, 0.12)):.2f})")
            return c
    return colour


# The tones every theme needs but no three-colour palette provides. Each is lifted per theme
# until it clears its floor on that theme's own surfaces.
TONES = {"ok": "#4fa36c", "info": "#6fa8c9", "warn": "#c28a2e", "danger": "#d9534f"}
SESSION = "#e2574b"

# id: (label, description, ground, accent, second accent, the palette's neutral)
T = {
    # The default, unchanged: the app's type, spacing and tones were all tuned against it.
    "bronze": ("Bronze", "Charcoal with a bronze accent", "#0d0f12", "#b98a44", "#d3a45a", "#eceff4"),
    # The six below come from the owner's palette list (2026-09-20). They were written as light
    # palettes -- neutral as the page, primary as the brand colour -- and are built here the
    # other way round: the primary is the ground and the accent stays the accent, which keeps
    # every pairing far apart in hue. Marketing Citrus is the exception: its primary #ea580c is
    # an orange, and an orange page is not a page, so it takes stone-900 as the ground and keeps
    # both of its colours as accents.
    "fintech": ("Fintech Classic", "Deep navy with a teal accent", "#0a2540", "#00d4b2", "#7dd3fc", "#ffffff"),
    "monochrome": ("Monochrome", "Near-black, one amber pop", "#111827", "#f59e0b", "#e5e7eb", "#ffffff"),
    "teal-navy": ("Teal & Navy", "Slate navy with orange and teal", "#1e293b", "#f97316", "#0d9488", "#f8fafc"),
    "earthy": ("Earthy Green", "Warm stone with amber and emerald", "#292524", "#d97706", "#059669", "#fefce8"),
    "security": ("Security Slate", "Lifted slate with emerald", "#374151", "#10b981", "#9ca3af", "#f9fafb"),
    "citrus": ("Marketing Citrus", "Near-black with citrus yellow", "#1c1917", "#facc15", "#ea580c", "#fff7ed"),
}

blocks, report = [], []
for tid, (label, desc, bg, accent, accent2, neutral) in T.items():
    # Text takes a trace of the ground so it never reads as pure white on a coloured page.
    fg = mix(neutral, bg, 0.06)
    # Four surfaces out of one ground: the page, a card, a card header, an input.
    panel = mix(bg, fg, 0.05)
    head = mix(bg, fg, 0.10)
    field = mix(bg, "#000000", 0.35)
    line = mix(bg, fg, 0.16)
    surfaces = [bg, panel, head]

    muted = dim(lift(mix(fg, bg, 0.45), surfaces, fg, 4.5, f"{tid} --muted"), bg, 6.5, f"{tid} --muted")

    # Every theme here is dark, so the colour that goes ON a filled control is the ground. A fill
    # the ground cannot sit on is brightened, never darkened: darkening it to satisfy its ink is
    # what collapsed the session ring to 1.15:1 against the card it is drawn on.
    def fill(colour, name):
        colour = lift(colour, surfaces, fg, 4.5, f"{tid} --{name} as text")
        return colour if cr(bg, colour) >= 4.5 else brighten(colour, name)

    def brighten(colour, name):
        for i in range(1, 101):
            c = mix(colour, fg, i / 100)
            if cr(bg, c) >= 4.5:
                STEPS.append(f"{tid} --{name}: {colour} -> {c} (brightened so the ground can sit on it, {cr(bg, colour):.2f} -> {cr(bg, c):.2f})")
                return c
        return colour

    accent_text = fill(accent, "accent")
    accent_ink = bg

    # Every tone is both plain text (an overdue date) and chip text (on 12% of itself), so it
    # has to clear both.
    tones = {k: lift_chip(lift(v, surfaces, fg, 4.5, f"{tid} --{k}"), panel, fg, 4.5, f"{tid} --{k} in a chip")
             for k, v in TONES.items()}
    # --accent-2 is not decoration: it paints tile numbers and space chips, which are text. It
    # was only ever checked as a star at 3:1, and four themes sat between 3.4 and 4.4 because of
    # it. Text floor first, then the star takes what that produced.
    accent2 = lift_chip(lift(accent2, surfaces, fg, 4.5, f"{tid} --accent-2 (it carries text)"),
                        panel, fg, 4.5, f"{tid} --accent-2 in a space chip")
    star = lift(accent2, [panel], fg, 3.0, f"{tid} --star")
    # The session red fills a button (its ink must clear it) and draws a ring on a card (3:1).
    session = lift(SESSION, [panel], fg, 3.0, f"{tid} --session on the panel")
    session = session if cr(bg, session) >= 4.5 else brighten(session, "session")
    session_ink = bg

    blocks.append(f"""[data-theme="{tid}"] {{
  --bg: {bg}; --panel: {panel}; --head: {head}; --fg: {fg}; --muted: {muted};
  --line: {line}; --accent: {accent_text}; --accent-ink: {accent_ink}; --accent-2: {accent2};
  --field: {field}; --pill: {head};
  --ok: {tones['ok']}; --info: {tones['info']}; --warn: {tones['warn']}; --danger: {tones['danger']};
  --star: {star}; --session: {session}; --session-ink: {session_ink};
  --shadow: none; color-scheme: dark;
}}""")
    report.append((label, tid, desc, [bg, accent_text, accent2],
                   cr(fg, bg), min(cr(muted, s) for s in surfaces), cr(accent_ink, accent_text),
                   min(cr(tones["danger"], s) for s in surfaces), min(cr(tones["warn"], s) for s in surfaces),
                   min(cr(tones["ok"], s) for s in surfaces), min(cr(tones["info"], s) for s in surfaces),
                   cr(star, panel), cr(session_ink, session), cr(session, panel), min(cr(accent2, x) for x in surfaces)))

print(f"{'theme':<19}{'fg':>6}{'muted':>7}{'a-ink':>7}{'danger':>7}{'warn':>6}{'ok':>6}{'info':>6}{'star':>6}{'s-ink':>7}{'s/pan':>7}{'acc-2':>7}")
bad = 0
FLOORS = [4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 4.5, 3.0, 4.5, 3.0, 4.5]
for r in report:
    vals = r[4:]
    line_bad = [v < f for v, f in zip(vals, FLOORS)]
    bad += any(line_bad)
    print(f"{r[0]:<19}" + "".join(f"{v:>6.2f}" if i not in (2, 8, 10) else f"{v:>7.2f}" for i, v in enumerate(vals))
          + ("   <-- FAILS" if any(line_bad) else ""))
print("\nderived steps (a palette colour that could not carry its job, and what it became):")
for s in STEPS:
    print("  " + s)

open(OUT + "themes.css", "w").write("\n".join(blocks) + "\n")
json.dump({r[1]: {"label": r[0], "desc": r[2], "swatch": r[3]} for r in report}, open(OUT + "meta.json", "w"), indent=1)
import re
exp = {}
for b in blocks:
    tid = re.search(r'data-theme="([^"]+)"', b).group(1)
    exp[tid] = dict(re.findall(r"--([a-z0-9-]+): (#[0-9a-fA-F]{6})", b))
json.dump(exp, open(OUT + "expected.json", "w"), indent=1)
print("\n" + ("ALL PASS" if not bad else f"{bad} themes failing"))
