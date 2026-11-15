#!/usr/bin/env python3
"""Check every skill in skills/ against the Agent Skills spec (agentskills.io).

  python3 scripts/validate_skills.py [--skills DIR]

Per skill: SKILL.md has frontmatter with name and description; name is 1-64 chars of [a-z0-9-] and equals
the folder name; description is non-empty and <= 400 chars (Codex shares a small budget across skills);
SKILL.md is <= 500 lines; every references/, assets/ or scripts/ path it mentions exists; scripts compile;
JSON assets parse. Exit 1 on any error.
"""
from __future__ import annotations

import argparse
import json
import py_compile
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PATH_RE = re.compile(r"(?<![\w/.-])((?:references|assets|scripts)/[\w./-]+\.\w+)")


def frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    out = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m and not line.startswith(" "):
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out, text[end + 4:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skills", default=str(Path(__file__).resolve().parent.parent / "skills"))
    root = Path(ap.parse_args().skills)
    errors = []
    for d in sorted(x for x in root.iterdir() if x.is_dir()):
        sk = d / "SKILL.md"
        if not sk.exists():
            errors.append(f"{d.name}: no SKILL.md")
            continue
        text = sk.read_text(encoding="utf-8")
        fm, body = frontmatter(text)
        name, desc = fm.get("name", ""), fm.get("description", "")
        if not NAME_RE.match(name) or len(name) > 64:
            errors.append(f"{d.name}: invalid name {name!r}")
        if name != d.name:
            errors.append(f"{d.name}: name {name!r} must equal the folder name")
        if not desc:
            errors.append(f"{d.name}: description missing")
        elif len(desc) > 400:
            errors.append(f"{d.name}: description is {len(desc)} chars (max 400)")
        if text.count("\n") > 500:
            errors.append(f"{d.name}: SKILL.md is over 500 lines")
        for p in sorted(set(PATH_RE.findall(text))):
            if not (d / p).exists():
                errors.append(f"{d.name}: mentions {p}, which does not exist")
        for py in (d / "scripts").glob("*.py"):
            try:
                py_compile.compile(str(py), doraise=True)
            except py_compile.PyCompileError as ex:
                errors.append(f"{d.name}: {py.name} does not compile: {ex}")
        for js in (d / "assets").glob("*.json"):
            try:
                json.loads(js.read_text(encoding="utf-8"))
            except json.JSONDecodeError as ex:
                errors.append(f"{d.name}: {js.name} is not valid JSON: {ex}")
        print(f"{d.name}: description {len(desc)} chars, SKILL.md {text.count(chr(10))} lines")
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
