# Slice 21: four other space pages (approved 2026-09-20)

**Built 2026-09-20; waiting on the user's judgement.** Proof: headless Chrome at 1280px, no page
errors -- Classic opens with `?item=11` in the pane and 16px between the search box and the
brief; each layout renders its lines and the five-way switcher with no horizontal overflow;
`j` in Panes moved the selection to the next item, the brief strip opened; a tree leaf and a
timeline row each opened the item in place.

The space page works, but it is a column of cards and the user wants to see what else it could
be. Four alternatives, each at its own URL beside the current one, which does not change:

- `/spaces/{name}` — **Classic**, today's page. Untouched.
- `/spaces/{name}/panes` — **Panes**: no card frames. A collapsible brief strip, filter chips,
  one dense list of tasks and notes, the item open beside it. `j`/`k` move down and up the list.
- `/spaces/{name}/board` — **Board**: columns by state (Today, Open, Notes, Done); a click opens
  the item beside the board on a wide screen, or its own page on a phone.
- `/spaces/{name}/timeline` — **Timeline**: one stream newest first under day headings, tasks and
  notes together; a row expands in place to hold the whole item.
- `/spaces/{name}/tree` — **Tree**: everything as a tree -- Tasks (Open, Done), Notes -- each
  branch counted and collapsible, a leaf expanding to the item.

Every layout shares the same data (`/api/items` for the space), the same row actions where it has
them, and a switcher linking the five. Judgement is the user's: these exist to be tried, and
whichever wins can replace Classic in a later slice. Nothing else in the app changes.

Chosen by the user 2026-09-20: separate URLs over a toggle, and all four directions rather than
one. Also in this slice, on Classic: the search box and the brief no longer touch (the column
had no gap), and on a wide screen a space opens with its newest item already in the pane.
