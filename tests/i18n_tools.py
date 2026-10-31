"""Helpers to extract translatable strings (used by tests/test_i18n.py)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "cmtracker"
TEMPLATE_RE = re.compile(r"""\b_\(\s*(['"])(.*?)\1\s*\)""")


def python_msgids() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in SRC.rglob("*.py"):
        if "locales" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found[node.args[0].value] = f"{path.relative_to(SRC)}:{node.lineno}"
    return found


def template_msgids() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in list(SRC.rglob("*.html")) + list(SRC.rglob("*.j2")):
        text = path.read_text(encoding="utf-8")
        for match in TEMPLATE_RE.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            found[match.group(2)] = f"{path.relative_to(SRC)}:{line}"
    return found


def all_msgids() -> dict[str, str]:
    return {**python_msgids(), **template_msgids()}
