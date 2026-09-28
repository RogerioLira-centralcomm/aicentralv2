import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chk", ROOT / "scripts/check_priority_daisyui.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)  # type: ignore

pat = re.compile(r"""class\s*=\s*(['"])(.*?)\1""", re.DOTALL)


def sem_bad(token: str) -> bool:
    if token.startswith(("bg-base-", "border-base-", "text-base-content", "rounded-box")):
        return True
    return token == "divider"


for path in chk.FILES:
    if not path.exists():
        continue
    src = path.read_text(encoding="utf-8")
    for m in pat.finditer(src):
        for t in re.split(r"\s+", m.group(2).strip()):
            if t and sem_bad(t):
                print(f"{path.relative_to(ROOT)}:{t}")
