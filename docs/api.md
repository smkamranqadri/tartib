# API

Every route except `/api/login`, `/api/logout` and `/api/health` needs either the session cookie or the password as a bearer token. See [Deploying](deploying.md#security) for what that means.

```text
POST   /api/login                {password}      sets the session cookie
POST   /api/logout
GET    /api/health                               public
POST   /api/capture              {text, client_id?}  -> 201 {id}, or 200 for a client_id already seen
GET    /api/captures/{id}                        capture, its items, answer if any
POST   /api/captures/{id}/whole                  a split capture put back as one waiting note; 409 once a piece is started
GET    /api/today                                items, today's sessions, recent captures
GET    /api/attention                            waiting items, plus 14-day stale tasks
GET    /api/recent?limit=&before=                captures, keyset paging
GET    /api/items?q=&space=&shape=&status=&limit=&before=
POST   /api/items                {shape, space, text, due?}  -> 201; filed directly, no classifier
GET    /api/items/{id}                           the item with its links and what links to it
PATCH  /api/items/{id}           any of text, shape, space, title, due, remind_at, starred, status
DELETE /api/items/{id}                           removes the item; its capture stays
POST   /api/items/{id}/approve   optional overrides, same fields, plus links: [id] to keep (at most 5)
POST   /api/items/{id}/redo      {reason}        the classifier tries again with your reason
GET    /api/items/{id}/thoughts                  the thought log, oldest first
POST   /api/items/{id}/thoughts  {body}          -> 201 {thought, thought_count}
PATCH  /api/items/{id}/thoughts/{thought_id}  {body}   rewrites one; it is marked edited
DELETE /api/items/{id}/thoughts/{thought_id}           -> {ok, thought_count}
POST   /api/ask                  {question, space?} -> {answer, item_ids, items}   read-only
POST   /api/pick                 {steer?}        stars up to three open tasks -> {picks: [{item, reason}]}
GET    /api/links/suggest?q=&exclude=            up to 8 items whose first line matches, for the [[ picker
GET    /api/links/resolve?title=                 -> {id} of the item [[title]] opens; 404 if none
GET    /api/spaces               POST /api/spaces {name}
PUT    /api/spaces/{name}/description {description, updated_at}  409 on stale token
PUT    /api/spaces/{name}/policy {policy}        auto, ask or file
PATCH  /api/spaces/{name}        {name}          rename, cascading to items and briefs
DELETE /api/spaces/{name}                        409 unless the space is empty
GET    /api/spaces/summary
GET    /api/spaces/{space}/brief[?refresh=true]
GET    /api/spaces/{name}/linked                 items in other spaces that link here with [[space:name]]
GET    /api/config                               read-only view of how this copy is set up
PUT    /api/config/house-rules   {text}          your filing rules, at most 2,000 characters; empty clears
GET    /api/usage                                AI calls, tokens, estimated cost and the last quota reading
POST   /api/subscriptions        {endpoint, keys}    DELETE and GET on the same path
POST   /api/sessions             {item_id?}      -> 201; 409 while one is running
GET    /api/sessions/current
GET    /api/sessions/recent?space=&limit=        finished sessions, newest first (limit 1 to 50, default 3)
POST   /api/sessions/{id}/stop   POST /api/sessions/{id}/outcome {outcome}
```

Dates: `due` is `YYYY-MM-DD`. `remind_at` and `created_at` are ISO 8601 in UTC.

`GET /api/spaces` retains its ordered `spaces` names and `policies` map and adds a `descriptions`
map keyed by name. Each value is `{name, description, updated_at}`. Descriptions start empty.
The PUT normalizes CRLF/CR to LF, trims the ends, permits internal newlines, counts Unicode code
points and accepts at most 500 characters; blank text clears it. Other control characters are
422. `updated_at` must match the token read from GET. Every accepted write advances the token,
including unchanged text and clears. A stale token returns 409; an unknown space returns 404.
`GET /api/spaces/summary` includes `description` for each configured space; Unfiled has an empty
description.

There is no reject. **Redo** replaced it: a disagreement always gets another attempt, with your
reason, and never a discarded proposal. The reason is kept on the item. The new proposal follows
the normal rules, the space's policy included, so a confident one files itself. Redo answers 409
when the classifier is off or the item was already filed and only its links are in question, and
502 when the classifier fails.

`POST /api/pick` answers 503 when the classifier is off. Each pick takes back the previous pick's
stars (never a star you set yourself) and leaves its reason as a thought on the task.

A space's **policy** decides how it takes proposals: `auto` follows `TARTIB_AUTOFILE_CONFIDENCE`,
`ask` always waits for you, and `file` always files.

`/mcp`, when `TARTIB_MCP_TOKEN` is set, is a separate surface for coding agents and is not under
`/api`; the README describes it.
