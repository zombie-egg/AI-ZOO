from __future__ import annotations

import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_finalize_pipeline.py", "-q"],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

