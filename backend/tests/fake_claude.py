"""Stand-in for the Claude CLI (`claude --print --output-format json --json-schema ...`).

FAKE_CLAUDE_REPLY_CLASSIFY / FAKE_CLAUDE_REPLY_ASK / FAKE_CLAUDE_REPLY  the structured reply
FAKE_CLAUDE_EXIT        non-zero exit code
FAKE_CLAUDE_IS_ERROR    envelope with is_error=true and this text as result
FAKE_CLAUDE_RECORD      path; one JSON line per invocation (argv, env marker presence)
"""

import json
import os
import sys

argv = sys.argv[1:]
prompt = argv[-1] if argv else ""
is_ask = prompt.startswith("You answer one person's question")
if os.environ.get("FAKE_CLAUDE_RECORD"):
    with open(os.environ["FAKE_CLAUDE_RECORD"], "a") as f:
        f.write(
            json.dumps({"argv": argv, "ask": is_ask, "claudecode": "CLAUDECODE" in os.environ})
            + "\n"
        )
code = int(os.environ.get("FAKE_CLAUDE_EXIT", "0"))
if code:
    print("fake claude: simulated failure", file=sys.stderr)
    sys.exit(code)
if os.environ.get("FAKE_CLAUDE_IS_ERROR"):
    print(
        json.dumps(
            {"type": "result", "is_error": True, "result": os.environ["FAKE_CLAUDE_IS_ERROR"]}
        )
    )
    sys.exit(0)
key = "FAKE_CLAUDE_REPLY_ASK" if is_ask else "FAKE_CLAUDE_REPLY_CLASSIFY"
reply = os.environ.get(key) or os.environ.get("FAKE_CLAUDE_REPLY", "{}")
print(
    json.dumps(
        {
            "type": "result",
            "is_error": False,
            "structured_output": json.loads(reply),
            "result": reply,
        }
    )
)
