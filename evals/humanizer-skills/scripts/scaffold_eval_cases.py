#!/usr/bin/env python3
"""Generate `claude plugin eval` benchmark test case directories.

Ported directly from the humanizer evaluation harness (src/bakeoff/cases.py).

Each generated case directory contains:
- prompt.md:   YAML frontmatter (plugins, tools, turn limits, timeout) and user prompt
- case.yaml:   Evaluation harness hook referencing scaffold.sh
- scaffold.sh: Deterministic bash script that writes input.md byte-for-byte using a unique heredoc
- graders/:    Deterministic offline sanity checks (output.md exists, no appended change summaries, skill tool fired)

Usage:
    # Scaffold from a folder of markdown files (*.md)
    python3 scaffold_eval_cases.py \
        --inputs-dir /path/to/drafts \
        --output-dir ./eval_suite \
        --skills-config ../config/skills_reference.toml
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

SKILL_TOOLS = ["Read", "Write", "Bash", "Skill"]
CONTROL_TOOLS = ["Read", "Write", "Bash"]
CHANGE_SUMMARY_PATTERN = r"^\s*(#{1,6}\s*|\*\*)(changes|what changed)\b"

DEFAULT_SKILL_TEMPLATE = (
    "Use /{skill} to edit `input.md` to remove signs of AI writing, if there are any. "
    "Keep the meaning, facts, and register. Don't ask clarifying questions. "
    "Write only the final text to `output.md`, with no change summary or notes."
)
DEFAULT_CONTROL_TEMPLATE = (
    "Edit `input.md` to remove signs of AI writing, if there are any. "
    "Keep the meaning, facts, and register. Don't ask clarifying questions. "
    "Write only the final text to `output.md`, with no change summary or notes."
)


@dataclass(frozen=True)
class Passage:
    id: str
    title: str
    body: str


@dataclass(frozen=True)
class EvalArm:
    id: str
    skill: str
    plugin_rel_path: str | None = None


@dataclass(frozen=True)
class EvalCase:
    case_dir: Path
    case_name: str
    title: str
    body: str
    arm_id: str
    skill_name: str | None
    prompt: str
    plugin_rel_path: str | None
    runs: int = 1
    max_turns: int = 5
    timeout_seconds: int = 180


def staged_text(title: str, body: str) -> str:
    """Return canonical input.md content: title line, blank line, then body."""
    return f"{title.strip()}\n\n{body.strip()}\n"


def scaffold_script(text: str) -> str:
    """Return a bash script that writes text to input.md byte for byte without shell interpolation."""
    delimiter = f"BAKEOFF_INPUT_{secrets.token_hex(8).upper()}"
    while delimiter in text:
        delimiter = f"BAKEOFF_INPUT_{secrets.token_hex(8).upper()}"
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"cat > input.md <<'{delimiter}'\n"
        f"{text}"
        f"{delimiter}\n"
    )


def skill_fired_pattern(skill: str) -> str:
    """Return regex matching a Skill tool call invocation for this skill."""
    return rf'"skill"\s*:\s*"(?:[\w-]+:)?{re.escape(skill)}"'


def format_frontmatter(fields: Mapping[str, object]) -> str:
    """Render a clean YAML frontmatter block from a dictionary."""
    lines = ["---"]
    for k, v in fields.items():
        lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def write_case(case: EvalCase) -> Path:
    """Write an isolated case directory matching the Claude plugin evaluation schema."""
    if case.case_dir.exists():
        shutil.rmtree(case.case_dir)
    case.case_dir.mkdir(parents=True, exist_ok=True)
    graders_dir = case.case_dir / "graders"
    graders_dir.mkdir(parents=True, exist_ok=True)

    is_control = case.arm_id == "control" or not case.skill_name

    frontmatter = {
        "name": case.case_name,
        "tags": [case.arm_id],
        "plugins": [case.plugin_rel_path] if case.plugin_rel_path else [],
        "runs": case.runs,
        "max_turns": case.max_turns,
        "timeout_seconds": case.timeout_seconds,
        "allowed_tools": CONTROL_TOOLS if is_control else SKILL_TOOLS,
    }

    (case.case_dir / "prompt.md").write_text(
        format_frontmatter(frontmatter) + "\n" + case.prompt.strip() + "\n", "utf-8"
    )
    (case.case_dir / "case.yaml").write_text(
        'schema_version: "1.1"\n'
        f"name: {json.dumps(case.case_name)}\n"
        "context:\n"
        "  scaffold_script: scaffold.sh\n",
        "utf-8",
    )

    script_path = case.case_dir / "scaffold.sh"
    script_path.write_text(scaffold_script(staged_text(case.title, case.body)), "utf-8")
    script_path.chmod(0o755)

    (graders_dir / "output_exists.md").write_text(
        format_frontmatter({"type": "file_exists", "path": "output.md"}), "utf-8"
    )
    (graders_dir / "no_change_summary.md").write_text(
        format_frontmatter(
            {
                "type": "regex",
                "target": {"source": "file", "path": "output.md"},
                "pattern": CHANGE_SUMMARY_PATTERN,
                "flags": "im",
                "match": "not_contains",
            }
        ),
        "utf-8",
    )
    if not is_control and case.skill_name:
        (graders_dir / "skill_fired.md").write_text(
            format_frontmatter(
                {
                    "type": "tool_used",
                    "tool": "Skill",
                    "input_match": skill_fired_pattern(case.skill_name),
                }
            ),
            "utf-8",
        )

    return case.case_dir


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold eval suite directories for claude plugin eval."
    )
    parser.add_argument(
        "--inputs-dir", help="Directory containing input markdown files (*.md)"
    )
    parser.add_argument(
        "--data",
        help='Optional JSON file containing passages [{"id": ..., "title": ..., "body": ...}]',
    )
    parser.add_argument(
        "--output-dir", required=True, help="Destination directory for evaluation suite"
    )
    parser.add_argument("--skills-config", help="Optional skills_reference.toml")
    parser.add_argument(
        "--prompt",
        default=None,
        help="Explicit prompt text override (defaults to template from skills-config)",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    passages: list[Passage] = []

    if args.inputs_dir:
        idir = Path(args.inputs_dir)
        for md_file in sorted(idir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8").strip()
            lines = text.splitlines()
            first_line = lines[0].lstrip("#").strip() if lines else md_file.stem
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else text
            passages.append(Passage(id=md_file.stem, title=first_line, body=body))
    elif args.data:
        data_path = Path(args.data)
        raw_items = json.loads(data_path.read_text(encoding="utf-8"))
        for item in raw_items:
            p_id = item.get("id") or item.get("passage_id", "passage-unknown")
            title = item.get("title", p_id)
            drafts = item.get("ai_drafts") or item.get("model_drafts")
            if isinstance(drafts, dict) and drafts:
                for model_key, draft_text in drafts.items():
                    passages.append(
                        Passage(id=f"{p_id}__{model_key}", title=title, body=draft_text)
                    )
            else:
                body = (
                    item.get("body")
                    or item.get("human_baseline_text")
                    or item.get("human_baseline", "")
                )
                passages.append(Passage(id=p_id, title=title, body=body))
    else:
        parser.error(
            "Must specify either --inputs-dir (folder of markdown files) or --data (JSON file)"
        )

    skill_template = DEFAULT_SKILL_TEMPLATE
    control_template = DEFAULT_CONTROL_TEMPLATE
    arms: list[EvalArm] = [EvalArm(id="control", skill="")]

    if args.skills_config and Path(args.skills_config).is_file():
        with open(args.skills_config, "rb") as f:
            cfg = tomllib.load(f)
            prompt_cfg = cfg.get("prompt", {})
            skill_template = prompt_cfg.get("skill_template", DEFAULT_SKILL_TEMPLATE)
            control_template = prompt_cfg.get(
                "control_template", DEFAULT_CONTROL_TEMPLATE
            )
            entries = cfg.get("arm", cfg.get("skills", []))
            for item in entries:
                arm_id = item["id"]
                skill = item.get("skill", item.get("skill_name", arm_id))
                plugin_rel = item.get("plugin_rel_path", f"../../plugins/{arm_id}")
                arms.append(EvalArm(id=arm_id, skill=skill, plugin_rel_path=plugin_rel))

    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for item in passages:
        for arm in arms:
            is_control = arm.id == "control"
            case_name = f"{item.id}__{arm.id}"
            case_dir = out_dir / case_name

            if args.prompt:
                prompt_text = args.prompt
            elif is_control:
                prompt_text = control_template
            else:
                prompt_text = skill_template.format(skill=arm.skill)

            case = EvalCase(
                case_dir=case_dir,
                case_name=case_name,
                title=item.title,
                body=item.body,
                arm_id=arm.id,
                skill_name=arm.skill if not is_control else None,
                prompt=prompt_text,
                plugin_rel_path=arm.plugin_rel_path if not is_control else None,
            )
            write_case(case)
            count += 1

    print(f"Scaffolded {count} evaluation cases in {out_dir}")


if __name__ == "__main__":
    main()
