#!/usr/bin/env python3
"""Lista templates/JS com classes DaisyUI clássicas (fora prefixos cx-/crm-v3-/etc.)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = [
    ROOT / "aicentralv2/templates",
    ROOT / "aicentralv2/static/js",
]

FORBIDDEN = re.compile(
    r"^(?:"
    r"modal(?:-(?:box|action|backdrop|open))?|"
    r"btn(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|sm|xs|lg))?|"
    r"form-control|input-bordered|select-bordered|textarea-bordered|"
    r"alert(?:-(?:error|success|warning|info))?|"
    r"drawer(?:-(?:toggle|content|side))?|"
    r"menu(?:-(?:title|horizontal|vertical))?|"
    r"navbar|"
    r"badge(?:-(?:primary|secondary|accent|ghost|outline|error|success|warning|info|sm|xs|lg))?|"
    r"toggle(?:-(?:primary|success|warning|error|sm|xs|lg))?|"
    r"checkbox(?:-(?:primary|success|warning|error|sm|xs|lg))?|"
    r"loading(?:-(?:spinner|dots|ring|xs|sm|md|lg))?"
    r")$"
)
SKIP_PREFIX = ("cx-", "crm-v3-", "pi-op-", "cot-op-", "camp-")


def scan_file(path: Path) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    found: set[str] = set()
    for match in re.finditer(r"""class\s*=\s*(['"])(.*?)\1""", source, re.DOTALL):
        for token in match.group(2).split():
            if not token or token.startswith(SKIP_PREFIX):
                continue
            if FORBIDDEN.fullmatch(token) or token in ("btn", "modal", "drawer", "menu"):
                found.add(token)
    return found


def main() -> int:
    rows: list[tuple[str, list[str]]] = []
    for base in DIRS:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in (".html", ".js"):
                continue
            tokens = scan_file(path)
            if tokens:
                rel = path.relative_to(ROOT).as_posix()
                rows.append((rel, sorted(tokens)))
    for rel, tokens in rows:
        print(f"{rel}: {', '.join(tokens)}")
    print(f"\nTotal: {len(rows)} arquivos com tokens Daisy clássicos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
