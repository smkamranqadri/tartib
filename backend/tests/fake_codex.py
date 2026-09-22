"""Stand-in for the Codex CLI. Behaviour is driven by env so tests stay real subprocess runs.

FAKE_CODEX_REPLY_CLASSIFY  reply for classify prompts
FAKE_CODEX_REPLY_ASK       reply for ask prompts (prompt starts with "You answer")
FAKE_CODEX_REPLY_TERMS     reply for the search-term expansion call ("You propose search terms")
FAKE_CODEX_REPLY_PICK      reply for Pick for me ("You pick what")
FAKE_CODEX_REPLY           fallback for either
FAKE_CODEX_EXIT            exit code (default 0)
FAKE_CODEX_ERROR           the failure message, delivered as an error event under --json
FAKE_CODEX_USAGE           JSON usage object for turn.completed
FAKE_CODEX_NO_USAGE        emit turn.completed with no usage at all
FAKE_CODEX_QUOTA           JSON rate_limits object for a token_count event
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
is_pick = prompt.startswith("You pick what")
if os.environ.get("FAKE_CODEX_RECORD"):
    with open(os.environ["FAKE_CODEX_RECORD"], "a") as f:
        f.write(
            json.dumps(
                {
                    "argv": argv,
                    "stdin_is_tty": sys.stdin.isatty(),
                    "ask": is_ask,
                    "terms": is_terms,
                    "pick": is_pick,
                }
            )
            + "\n"
        )
if os.environ.get("FAKE_CODEX_SLEEP"):
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
code = int(os.environ.get("FAKE_CODEX_EXIT", "0"))
if code:
    message = os.environ.get("FAKE_CODEX_ERROR") or "fake codex: simulated failure"
    if "--json" in argv:
        # The real CLI reports the windows and *then* fails, which is the case that matters:
        # a call refused because the quota is gone is when its level is most worth knowing.
        if os.environ.get("FAKE_CODEX_QUOTA"):
            print(
                json.dumps(
                    {
                        "type": "token_count",
                        "rate_limits": json.loads(os.environ["FAKE_CODEX_QUOTA"]),
                    }
                )
            )
        # The real CLI puts the useful text here, not on stderr. Losing it is the regression
        # this slice has to avoid.
        print(json.dumps({"type": "error", "message": message}))
        print(json.dumps({"type": "turn.failed", "error": {"message": message}}))
    else:
        print(message, file=sys.stderr)
    sys.exit(code)
if is_pick:
    key = "FAKE_CODEX_REPLY_PICK"
elif is_terms:
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

# With --json the real CLI prints the turn as events on stdout, and `turn.completed` is where
# the token counts live. FAKE_CODEX_USAGE overrides the counts; FAKE_CODEX_NO_USAGE drops the
# usage object entirely, which is the case where a row must record zeroes and say so.
if "--json" in argv:
    print(json.dumps({"type": "thread.started", "thread_id": "fake"}))
    print(json.dumps({"type": "turn.started"}))
    if os.environ.get("FAKE_CODEX_QUOTA"):
        print(
            json.dumps(
                {"type": "token_count", "rate_limits": json.loads(os.environ["FAKE_CODEX_QUOTA"])}
            )
        )
    if os.environ.get("FAKE_CODEX_NO_USAGE"):
        print(json.dumps({"type": "turn.completed"}))
    else:
        usage = json.loads(
            os.environ.get("FAKE_CODEX_USAGE")
            or '{"input_tokens": 1200, "cached_input_tokens": 400,'
            ' "cache_write_input_tokens": 100, "output_tokens": 90,'
            ' "reasoning_output_tokens": 30, "total_tokens": 1390}'
        )
        print(json.dumps({"type": "turn.completed", "usage": usage}))
sys.exit(0)
