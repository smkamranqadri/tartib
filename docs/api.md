# API

Every route except `/api/login`, `/api/logout` and `/api/health` needs either the session cookie or the password as a bearer token. See [Deploying](deploying.md#security) for what that means.

```text
POST   /api/login                {password}      sets the session cookie
POST   /api/logout
GET    /api/health                               public
POST   /api/capture              {text, client_id?}  -> 201 {id}, or 200 for a client_id already seen
GET    /api/captures/{id}                        capture, its items, answer if any
GET    /api/today                                items, today's sessions, recent captures
GET    /api/attention                            waiting items, plus 14-day stale tasks
GET    /api/recent?limit=&before=                captures, keyset paging
GET    /api/items?q=&space=&shape=&status=&limit=&before=
GET    /api/items/{id}
PATCH  /api/items/{id}           any of text, shape, space, title, due, remind_at, starred, status
DELETE /api/items/{id}                           removes the item; its capture stays
POST   /api/items/{id}/approve   optional overrides, same fields
POST   /api/items/{id}/reject
POST   /api/ask                  {question, space?} -> {answer, item_ids, items}   read-only
GET    /api/spaces               POST /api/spaces {name}
PUT    /api/spaces/{name}/description {description, updated_at}  409 on stale token
PATCH  /api/spaces/{name}        {name}          rename, cascading to items and briefs
DELETE /api/spaces/{name}                        409 unless the space is empty
GET    /api/spaces/summary
GET    /api/spaces/{space}/brief[?refresh=true]
GET    /api/config                               read-only view of how this copy is set up
POST   /api/subscriptions        {endpoint, keys}    DELETE and GET on the same path
POST   /api/sessions             {item_id?}      -> 201; 409 while one is running
GET    /api/sessions/current
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
