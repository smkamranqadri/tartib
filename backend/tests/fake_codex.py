"""Stand-in for the Codex CLI. Behaviour is driven by env so tests stay real subprocess runs.

FAKE_CODEX_REPLY      text written to the --output-last-message file
FAKE_CODEX_EXIT       exit code (default 0)
FAKE_CODEX_SLEEP      seconds to sleep before replying
FAKE_CODEX_RECORD     path to write the received argv as JSON
"""

import json
import os
import sys
import time

argv = sys.argv[1:]
if os.environ.get("FAKE_CODEX_RECORD"):
    with open(os.environ["FAKE_CODEX_RECORD"], "w") as f:
        json.dump({"argv": argv, "stdin_is_tty": sys.stdin.isatty()}, f)
if os.environ.get("FAKE_CODEX_SLEEP"):
    time.sleep(float(os.environ["FAKE_CODEX_SLEEP"]))
code = int(os.environ.get("FAKE_CODEX_EXIT", "0"))
if code:
    print("fake codex: simulated failure", file=sys.stderr)
    sys.exit(code)
if "--output-last-message" in argv:
    out = argv[argv.index("--output-last-message") + 1]
    with open(out, "w") as f:
        f.write(os.environ.get("FAKE_CODEX_REPLY", ""))
sys.exit(0)
