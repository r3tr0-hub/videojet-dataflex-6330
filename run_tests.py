"""Run the published offline test groups in isolated module namespaces."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
for group in ("binary", "deep/jobs", "deep/session", "tools"):
    print(f"\n== {group} ==", flush=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", group],
                   check=True, cwd=root)
