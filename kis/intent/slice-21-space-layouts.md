# Slice 21: four other space pages (approved 2026-09-20)

**Three kept, 2026-09-20, with a View picker.** No single winner: Classic, Panes and Tree all
stay, and the picker decides which one a space opens in. Proof: headless
Chrome, no page errors -- Classic opens with `?item=11` in its pane, 16px between search and
brief; the switcher reads Classic | Panes | Tree; `j` in Panes moves the selection and the brief
strip opens; a tree leaf sets `?item=7` and fills the pane, with nothing expanding in the tree
itself, and collapsing Notes removes its rows; `/board` and `/timeline` no longer resolve (they
fall through to Home); at 390px the tree has no pane and a leaf links to `/items/{id}`. Second pass: in Panes the
search sits above the chips (329 < 385) and Sessions is a tab (4 session lines, no item rows);
in Tree the brief strip, the search box and a Sessions branch (4, shut by default) are all
there; picking Classic stays on `/spaces/home` and the next space opens Classic too. Fixed 2026-09-20: picking Classic bounced back to Panes -- "classic" was stored as `""`, which
reads as nothing set, so the default took over. The slug is stored as `classic` now.
Search, Add and sessions: on both, "gate" cut Panes 7 rows to 3 and Tree 9 to 4, each has one
Sessions card and one "+ Add", and an item added from each appeared in its list. With nothing
stored, `/spaces/home` lands on `/spaces/home/panes`. Picker: Classic ->
Tree stores `tree` and moves there, another space then opens in Tree, picking Panes stores
`panes`, picking Classic stores `""` and Classic stays Classic.

The space page works, but it is a column of cards and the user wants to see what else it could
be. Four alternatives were built at their own URLs beside the current page, which does not
change. **2026-09-20, after trying them: Board and Timeline are out** -- deleted, not kept as
dead routes -- Tree opens its item in the pane instead of expanding in place, and all three that
remain are kept, chosen from a "View" select in the title row and remembered per device
(`tartib-space-view`), **Panes by default**, so the next space opens the same way. Panes and
Tree carry the same furniture as Classic, each in its own idiom: the search box above the filter
chips in Panes and above the tree in Tree, "+ Add" beside the picker, the brief as a strip in
both, and the space's sessions as a Panes tab and a Tree branch. What remains:

- `/spaces/{name}` — **Classic**, today's page. Untouched.
- `/spaces/{name}/panes` — **Panes**: no card frames. A collapsible brief strip, filter chips,
  one dense list of tasks and notes, the item open beside it. `j`/`k` move down and up the list.
- `/spaces/{name}/tree` — **Tree**: everything as a tree -- Tasks (Overdue, Open, Done), Notes
  -- each branch counted and collapsible, a leaf opening the item beside the tree.

Every layout shares the same data (`/api/items` for the space), the same row actions where it has
them, and a switcher linking the five. Judgement is the user's: these exist to be tried, and
whichever wins can replace Classic in a later slice. Nothing else in the app changes.

Chosen by the user 2026-09-20: separate URLs over a toggle, and all four directions rather than
one. Also in this slice, on Classic: the search box and the brief no longer touch (the column
had no gap), and on a wide screen a space opens with its newest item already in the pane.
