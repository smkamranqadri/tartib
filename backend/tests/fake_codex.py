"""Stand-in for the Codex CLI. Behaviour is driven by env so tests stay real subprocess runs.

FAKE_CODEX_REPLY_CLASSIFY  reply for classify prompts
FAKE_CODEX_REPLY_ASK       reply for ask prompts (prompt starts with "You answer")
FAKE_CODEX_REPLY           fallback for either
FAKE_CODEX_EXIT            exit code (default 0)
FAKE_CODEX_SLEEP           seconds to sleep before replying
FAKE_CODEX_RECORD          path; one JSON line per invocation with argv and stdin tty state
"""

import json
import os
import sys
import time

argv = sys.argv[1:]
prompt = argv[-1] if argv else ""
is_ask = prompt.startswith("You answer one person's question")
if os.environ.get("FAKE_CODEX_RECORD"):
    with open(os.environ["FAKE_CODEX_RECORD"], "a") as f:
        f.write(
            json.dumps({"argv": argv, "stdin_is_tty": sys.stdin.isatty(), "ask": is_ask}) + "\n"
        )
if os.environ.get("FAKE_CODEX_SLEEP"):
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
code = int(os.environ.get("FAKE_CODEX_EXIT", "0"))
if code:
    print("fake codex: simulated failure", file=sys.stderr)
    sys.exit(code)
key = "FAKE_CODEX_REPLY_ASK" if is_ask else "FAKE_CODEX_REPLY_CLASSIFY"
reply = os.environ.get(key) or os.environ.get("FAKE_CODEX_REPLY", "")
if "--output-last-message" in argv:
    out = argv[argv.index("--output-last-message") + 1]
    with open(out, "w") as f:
        f.write(reply)
sys.exit(0)
