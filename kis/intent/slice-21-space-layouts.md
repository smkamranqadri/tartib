# Slice 21: four other space pages (closed 2026-09-20)

**Closed: Panes won and is the space page.** Classic (the card column) and Tree are deleted, as Board and Timeline were before them; `/spaces/{name}/panes` and `/spaces/{name}/tree` redirect to `/spaces/{name}`, and the View picker and its stored preference are gone with them. The manage menu (filing policy, rename, delete) moved onto the new page, which keeps the brief strip, the scoped search, "+ Add", the filter chips with a Sessions tab, `j`/`k`, and the item beside the list.

Proof of the final page: headless Chrome at 1280px and 390px, no page errors -- the space page is Panes with no View picker, chips All/Tasks/Notes/Done/Sessions, "+ Add" and Manage space present, the item pane at 1280px and none at 390px, both old layout URLs redirecting to the space, the manage menu listing the three policies with the current one ticked, Rename, and Delete disabled while the space holds items. No horizontal overflow.

What was tried, and why it went:

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
