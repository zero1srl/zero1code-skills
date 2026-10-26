#!/usr/bin/env python3
"""Create and check agent skills for zero1code (and any tool that reads ~/.agents/skills).

  python skill_tool.py new NAME --description "When to use it" [--scope global|local] [--license MIT] [--body-file FILE]
  python skill_tool.py check NAME_OR_PATH

`new` writes <folder>/SKILL.md (body from --body-file or stdin) and never overwrites an existing skill:
  --scope local   (default) only zero1code:   $DSH_HOME/skills/NAME   (DSH_HOME defaults to ~/.dsh)
  --scope global  shared library:             ~/.agents/skills/NAME, plus a link in $DSH_HOME/skills so zero1code uses it
`check` validates the SKILL.md the same way the app does and prints advice; exit code 1 on errors.
Standard library only.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MAX_NAME, MAX_DESCRIPTION, MAX_TEXT = 64, 1024, 200_000


def home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or Path.home())


def active_root() -> Path:
    return Path(os.environ.get("DSH_HOME") or home() / ".dsh") / "skills"


def library_root() -> Path:
    return home() / ".agents" / "skills"


def yaml_string(text: str) -> str:
    """One-line YAML scalar; JSON strings are valid YAML, so quotes and colons are safe."""
    return json.dumps(" ".join(text.split()), ensure_ascii=False)


def compose(name: str, description: str, body: str, license_: str = "") -> str:
    head = ["---", f"name: {name}", f"description: {yaml_string(description)}"]
    if license_.strip():
        head.append(f"license: {yaml_string(license_)}")
    return "\n".join([*head, "---", "", body.strip(), ""])


def frontmatter(text: str) -> dict:
    """name / description / license from the first frontmatter block (scalars and > | blocks)."""
    match = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    out = {}
    if not match:
        return out
    lines = match.group(1).splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", lines[i])
        i += 1
        if not m:
            continue
        key, raw = m.groups()
        children = []
        while i < len(lines) and re.match(r"^\s+\S", lines[i]):
            children.append(lines[i].strip())
            i += 1
        if re.fullmatch(r"[>|][+-]?", raw):
            out[key] = (" " if raw[0] == ">" else "\n").join(children)
        else:
            raw = raw.strip()
            try:
                out[key] = json.loads(raw) if raw.startswith('"') else raw.strip("'\"")
            except json.JSONDecodeError:
                out[key] = raw.strip("'\"")
    return out


def problems(name: str, text: str) -> list:
    errors = []
    if not NAME.match(name) or len(name) > MAX_NAME:
        errors.append("name: lowercase letters, digits, '.', '_' and '-' only, at most 64 characters")
    if len(text) > MAX_TEXT:
        errors.append("SKILL.md is larger than 200 KB")
    meta = frontmatter(text)
    if not meta:
        errors.append("SKILL.md must start with a --- frontmatter block containing name and description")
        return errors
    if meta.get("name") != name:
        errors.append(f"frontmatter name {meta.get('name')!r} must equal the folder name {name!r}")
    description = meta.get("description", "")
    if not description.strip():
        errors.append("description is required: it tells the agent when to load the skill")
    elif len(description) > MAX_DESCRIPTION:
        errors.append("description is longer than 1024 characters")
    return errors


def advice(name: str, text: str) -> list:
    notes = []
    meta = frontmatter(text)
    description = meta.get("description", "")
    body = re.sub(r"^---\r?\n.*?\r?\n---\s*", "", text, count=1, flags=re.S)
    if description and not re.search(r"\b(quando|use when|when the user|usa questa|usare quando|if the user)\b", description, re.I):
        notes.append("the description should say WHEN to use the skill (a request, a file type, a situation), not only what it is")
    if len(description) < 60 and description:
        notes.append("the description is very short: add the situations or phrases that should trigger it")
    if body.count("\n") > 500:
        notes.append("the body is over 500 lines: move long reference material to files next to SKILL.md and link them")
    if not re.search(r"^#{1,3} ", body, re.M):
        notes.append("add headings so the steps are easy to find")
    if re.search(r"(api[_-]?key|password|secret|token)\s*[:=]\s*\S{8,}", body, re.I):
        notes.append("the text looks like it contains a credential: remove it; skills are plain files that may be shared")
    return notes


def link_dir(link: Path, target: Path) -> None:
    """Directory link without admin rights: a junction on Windows, a symlink elsewhere."""
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"could not create the link {link}: {result.stderr.strip() or result.stdout.strip()}")
    else:
        link.symlink_to(target, target_is_directory=True)


def cmd_new(args) -> int:
    body = Path(args.body_file).read_text(encoding="utf-8") if args.body_file else sys.stdin.read()
    if not body.strip():
        raise SystemExit("the instructions are empty: pass --body-file or pipe them on stdin")
    text = compose(args.name, args.description, body, args.license or "")
    errors = problems(args.name, text)
    if errors:
        print("not created:", *errors, sep="\n  - ")
        return 1
    folders = [library_root() / args.name, active_root() / args.name, active_root() / ".disabled" / args.name]
    if any(p.exists() or p.is_symlink() for p in folders):
        raise SystemExit(f"a skill named {args.name!r} already exists: edit its SKILL.md instead")
    dest = (library_root() if args.scope == "global" else active_root()) / args.name
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text(text, encoding="utf-8")
    if args.scope == "global":
        link_dir(active_root() / args.name, dest)
    print(f"created {dest / 'SKILL.md'}")
    if args.scope == "global":
        print(f"linked into {active_root() / args.name} so zero1code uses it; other tools read {library_root()}")
    for note in advice(args.name, text):
        print("advice:", note)
    return 0


def cmd_check(args) -> int:
    target = Path(args.target)
    if not target.exists():
        for root in (active_root(), library_root()):
            if (root / args.target).exists():
                target = root / args.target
                break
    folder = target.parent if target.is_file() else target
    skill = folder / "SKILL.md"
    if not skill.exists():
        raise SystemExit(f"no SKILL.md in {folder}")
    text = skill.read_text(encoding="utf-8")
    errors = problems(folder.name, text)  # the folder's own name, also when it is a link into the library
    for error in errors:
        print("error:", error)
    for note in advice(folder.name, text):
        print("advice:", note)
    print("ok" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new")
    new.add_argument("name")
    new.add_argument("--description", required=True)
    new.add_argument("--scope", choices=["local", "global"], default="local")
    new.add_argument("--license")
    new.add_argument("--body-file")
    new.set_defaults(run=cmd_new)
    check = sub.add_parser("check")
    check.add_argument("target")
    check.set_defaults(run=cmd_check)
    args = ap.parse_args()
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
