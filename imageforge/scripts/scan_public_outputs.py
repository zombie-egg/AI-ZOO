from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描公开目录，阻止母版/终图泄露")
    parser.add_argument("directory", type=Path, nargs="?", default=Path("data/public"))
    args = parser.parse_args()
    violations: list[str] = []
    for path in args.directory.rglob("*") if args.directory.exists() else []:
        if not path.is_file():
            continue
        if path.name in {"local_master.jpg", "gpt_final.jpg", "print_payload.html"}:
            violations.append(f"private artifact in public tree: {path}")
            continue
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            with Image.open(path) as image:
                if max(image.size) > 480:
                    violations.append(f"public image exceeds 480px: {path} {image.size}")
            if path.name != "preview.jpg":
                violations.append(f"unexpected public rendered image: {path}")
    if violations:
        print("\n".join(violations))
        return 1
    print("public output scan: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

