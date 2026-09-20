"""Stand-in for the Codex CLI. Behaviour is driven by env so tests stay real subprocess runs.

FAKE_CODEX_REPLY_CLASSIFY  reply for classify prompts
FAKE_CODEX_REPLY_ASK       reply for ask prompts (prompt starts with "You answer")
FAKE_CODEX_REPLY_TERMS     reply for the search-term expansion call ("You propose search terms")
FAKE_CODEX_REPLY           fallback for either
FAKE_CODEX_EXIT            exit code (default 0)
FAKE_CODEX_SLEEP           seconds to sleep before replying
FAKE_CODEX_RECORD          path; one JSON line per invocation with argv and stdin tty state
FAKE_CODEX_REPLY_FILE      path to a JSON file {"classify": ..., "ask": ...}; wins over the env
                           replies when present, so a long-running server can be steered
"""

import json
import os
import sys
import time

argv = sys.argv[1:]
prompt = argv[-1] if argv else ""
is_ask = prompt.startswith("You answer one person's question")
is_terms = prompt.startswith("You propose search terms")
if os.environ.get("FAKE_CODEX_RECORD"):
    with open(os.environ["FAKE_CODEX_RECORD"], "a") as f:
        f.write(
            json.dumps(
                {
                    "argv": argv,
                    "stdin_is_tty": sys.stdin.isatty(),
                    "ask": is_ask,
                    "terms": is_terms,
                }
            )
            + "\n"
        )
if os.environ.get("FAKE_CODEX_SLEEP"):
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
code = int(os.environ.get("FAKE_CODEX_EXIT", "0"))
if code:
    print("fake codex: simulated failure", file=sys.stderr)
    sys.exit(code)
if is_terms:
    key = "FAKE_CODEX_REPLY_TERMS"
elif is_ask:
    key = "FAKE_CODEX_REPLY_ASK"
else:
    key = "FAKE_CODEX_REPLY_CLASSIFY"
reply = os.environ.get(key) or os.environ.get("FAKE_CODEX_REPLY", "")
if os.environ.get("FAKE_CODEX_REPLY_FILE") and os.path.exists(os.environ["FAKE_CODEX_REPLY_FILE"]):
    with open(os.environ["FAKE_CODEX_REPLY_FILE"]) as f:
        steer = json.load(f)
    chosen = steer.get("ask" if is_ask else "classify")
    if chosen is not None:
        reply = json.dumps(chosen)
if "--output-last-message" in argv:
    out = argv[argv.index("--output-last-message") + 1]
    with open(out, "w") as f:
        f.write(reply)
sys.exit(0)
