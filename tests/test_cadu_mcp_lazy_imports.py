"""Tool handlers import services lazily, so a wrong relative path only fails when the tool runs."""
import ast
import importlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCANNED = ("aicentralv2/cadu_workspace", "aicentralv2/cadu_public_mcp")


def _unresolved():
    broken = []
    for folder in SCANNED:
        for path in sorted((ROOT / folder).rglob("*.py")):
            module = ".".join(path.relative_to(ROOT).with_suffix("").parts)
            package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
            if path.name == "__init__.py":
                package = ".".join(path.relative_to(ROOT).parent.parts)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.ImportFrom) or not node.level:
                    continue
                parts = package.split(".")
                if node.level - 1 >= len(parts):
                    broken.append((str(path.relative_to(ROOT)), node.lineno, "além da raiz"))
                    continue
                base = ".".join(parts[: len(parts) - (node.level - 1)])
                target = base + ("." + node.module if node.module else "")
                try:
                    importlib.import_module(target)
                except ModuleNotFoundError as exc:
                    if exc.name and (target == exc.name or target.startswith(exc.name + ".")):
                        broken.append((str(path.relative_to(ROOT)), node.lineno, target))
                except Exception:
                    pass  # an import-time error in a real module is a different failure
    return broken


def test_relative_imports_in_workspace_and_public_mcp_resolve():
    assert _unresolved() == []
