#!/usr/bin/env python3
"""Audit community humanizer skills for overlap with the Wikipedia signs of AI writing.

Ported directly from the humanizer evaluation harness (src/bakeoff/tells.py).
Checks whether a skill's prompt files / SKILL.md explicitly mention the audit terms
for each of the 22 Wikipedia tell patterns.

This audits whether a skill's benchmark tell removal is evaluating general editorial
improvement vs. "grading on its own test" (circularity).

Usage:
    # Audit a single skill directory
    python3 audit_skill_overlap.py /path/to/skill_folder

    # Audit multiple skills or a plugins directory
    python3 audit_skill_overlap.py --plugins-dir ~/.claude/plugins
    python3 audit_skill_overlap.py --json /path/to/skill_folder
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR.parent / "config" / "tells_wikipedia.toml"

_NOT_GUIDANCE = re.compile(
    r"(^|/)(evals?|tests?|docs|examples|assets|\.github)/|"
    r"(^|/)(readme|changelog|contributing|license|agents|claude)\.md$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TellAudit:
    id: str
    section: str
    audit_terms: list[str]


def load_tells(config_path: Path = DEFAULT_CONFIG) -> list[TellAudit]:
    if not config_path.is_file():
        raise FileNotFoundError(f"Tell config not found at: {config_path}")
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)
    return [
        TellAudit(
            id=t["id"],
            section=t["section"],
            audit_terms=[term.lower() for term in t["audit"]],
        )
        for t in data["tell"]
    ]


def skill_text(plugin_dir: Path) -> tuple[str, list[Path]]:
    """Return the Markdown guidance a skill gives the agent, lowercased.

    Includes SKILL.md and reference/preset files; excludes eval fixtures, tests,
    docs, READMEs, and changelogs.
    """
    if plugin_dir.is_file():
        return plugin_dir.read_text(encoding="utf-8", errors="replace").lower(), [
            plugin_dir
        ]

    files = [
        p
        for p in sorted(plugin_dir.rglob("*.md"))
        if not _NOT_GUIDANCE.search(p.relative_to(plugin_dir).as_posix())
    ]
    combined = "\n".join(p.read_text("utf-8", "replace").lower() for p in files)
    return combined, files


def audit_skill(tells: list[TellAudit], plugin_dir: Path) -> dict[str, dict[str, Any]]:
    text, files = skill_text(plugin_dir)
    results: dict[str, dict[str, Any]] = {}
    for tell in tells:
        matched_terms = [term for term in tell.audit_terms if term in text]
        results[tell.id] = {
            "targeted": len(matched_terms) > 0,
            "matched_terms": matched_terms,
            "section": tell.section,
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit skills against Wikipedia tell list."
    )
    parser.add_argument("path", nargs="?", help="Path to skill folder or SKILL.md")
    parser.add_argument(
        "--plugins-dir", help="Directory containing multiple skill plugins"
    )
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="Path to tells_wikipedia.toml"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    args = parser.parse_args()

    tells = load_tells(Path(args.config))

    skills_to_audit: dict[str, Path] = {}
    if args.plugins_dir:
        pdir = Path(args.plugins_dir)
        for child in sorted(pdir.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                skills_to_audit[child.name] = child
    elif args.path:
        p = Path(args.path)
        skills_to_audit[p.name] = p
    else:
        parser.print_help()
        sys.exit(1)

    full_report: dict[str, Any] = {}
    for name, path in skills_to_audit.items():
        report = audit_skill(tells, path)
        targeted_count = sum(1 for v in report.values() if v["targeted"])
        full_report[name] = {
            "path": str(path),
            "total_tells_targeted": targeted_count,
            "share_targeted": targeted_count / len(tells) if tells else 0.0,
            "details": report,
        }

    if args.json:
        print(json.dumps(full_report, indent=2))
    else:
        for name, data in full_report.items():
            print(f"=== Skill Overlap Audit: {name} ===")
            targeted = data["total_tells_targeted"]
            share = data["share_targeted"]
            print(
                f"Tells explicitly targeted: {targeted} / {len(tells)} ({share:.1%})\n"
            )
            print(f"{'Tell ID':<28} {'Targeted?':<12} {'Matched Terms'}")
            print("-" * 65)
            for tid, info in data["details"].items():
                status = "YES" if info["targeted"] else "no"
                terms = (
                    ", ".join(info["matched_terms"]) if info["matched_terms"] else "-"
                )
                print(f"{tid:<28} {status:<12} {terms}")
            print("\n")


if __name__ == "__main__":
    main()
