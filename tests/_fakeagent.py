"""A fake coding agent for tests: reads the prompt on stdin, then

  - if the prompt contains "FAIL"  -> exit 1 (a crash)
  - if the prompt contains "NOOP"  -> exit 0, change nothing
  - otherwise                      -> create <first declared file> (or made.txt)

Used via GenericDriver(template=[sys.executable, THIS_FILE]).
"""
import re
import sys
from pathlib import Path

prompt = sys.stdin.read()

if "FAIL" in prompt:
    sys.stderr.write("fake agent: deliberate failure\n")
    sys.exit(1)
if "NOOP" in prompt:
    sys.exit(0)

m = re.search(r"^  - (.+)$", prompt, re.M)
target = Path(m.group(1).strip()) if m else Path("made.txt")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(f"generated for: {prompt.splitlines()[0]}\n", encoding="utf-8")
