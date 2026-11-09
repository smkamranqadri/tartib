"""Stand-in for the Codex CLI, for Pick for me only (slice 41).

It replaces the classification steering in fake_codex.py for pick tests: one mode per outcome,
all from the environment, so the subprocess path is exercised for real.

FAKE_PICK_MODE      success (default) | empty | junk | stale | failure | sleep
FAKE_PICK_PICKS     JSON [[label, reason], ...]: what a success, stale or sleep reply names
                    (empty: names none; junk: a reply that is not JSON at all)
FAKE_PICK_DB        stale: the database file the SQL below runs on
FAKE_PICK_SQL       stale: run before the reply, as the world changing while the model works
FAKE_PICK_SECONDS   sleep: how long to wait before the reply (default 30)
FAKE_PICK_ERROR     failure: the message (default "fake pick: simulated failure")
FAKE_PICK_PIDFILE   path; this process's id is written here the moment it starts
FAKE_PICK_RECORD    path; one JSON line per invocation with the argv
"""

import json
import os
import sqlite3
import sys
import time

argv = sys.argv[1:]
mode = os.environ.get("FAKE_PICK_MODE", "success")

if os.environ.get("FAKE_PICK_PIDFILE"):
    with open(os.environ["FAKE_PICK_PIDFILE"], "w") as f:
        f.write(str(os.getpid()))
if os.environ.get("FAKE_PICK_RECORD"):
    with open(os.environ["FAKE_PICK_RECORD"], "a") as f:
        f.write(json.dumps({"argv": argv}) + "\n")

if mode == "failure":
    message = os.environ.get("FAKE_PICK_ERROR") or "fake pick: simulated failure"
    print(json.dumps({"type": "error", "message": message}))
    print(json.dumps({"type": "turn.failed", "error": {"message": message}}))
    sys.exit(1)

if mode == "sleep":
    time.sleep(float(os.environ.get("FAKE_PICK_SECONDS", "30")))

if mode == "stale":
    db = sqlite3.connect(os.environ["FAKE_PICK_DB"], timeout=5)
    db.execute(os.environ["FAKE_PICK_SQL"])
    db.commit()
    db.close()

picks = [] if mode == "empty" else json.loads(os.environ.get("FAKE_PICK_PICKS") or "[]")
reply = json.dumps({"picks": [{"label": label, "reason": reason} for label, reason in picks]})
if mode == "junk":
    reply = "this is not json"
if "--output-last-message" in argv:
    with open(argv[argv.index("--output-last-message") + 1], "w") as f:
        f.write(reply)

print(json.dumps({"type": "thread.started", "thread_id": "fake"}))
print(json.dumps({"type": "turn.started"}))
print(
    json.dumps(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 1200,
                "cached_input_tokens": 400,
                "cache_write_input_tokens": 100,
                "output_tokens": 90,
                "reasoning_output_tokens": 30,
                "total_tokens": 1390,
            },
        }
    )
)
