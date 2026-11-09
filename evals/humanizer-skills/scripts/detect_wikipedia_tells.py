#!/usr/bin/env python3
"""Detect prose signs of AI writing from Wikipedia's "Signs of AI writing".

Ported directly from the humanizer evaluation harness (src/bakeoff/tells.py).
Evaluates text against the 22 standardized tell patterns in config/tells_wikipedia.toml.

Usage:
    # Scan a single text file
    python3 detect_wikipedia_tells.py draft.md

    # Compare an input against an edited output to measure removal and introduced tells
    python3 detect_wikipedia_tells.py --before input.md --after output.md

    # Output detailed JSON with match spans
    python3 detect_wikipedia_tells.py --json draft.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import Counter
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Literal

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR.parent / "config" / "tells_wikipedia.toml"

Taxonomy = Literal[
    "density", "relevance", "factuality", "bias", "structure", "coherence", "tone"
]


@dataclass(frozen=True)
class TellPattern:
    """One sign of AI writing as a regex, with its provenance and audit terms."""

    id: str
    kind: Literal["word", "structural", "formatting"]
    taxonomy: str
    section: str
    pattern: str
    audit: list[str]
    case_sensitive: bool = False
    exclude: str | None = None

    @cached_property
    def regex(self) -> re.Pattern[str]:
        """Return the compiled pattern, case-insensitive unless case_sensitive=True."""
        return re.compile(self.pattern, 0 if self.case_sensitive else re.IGNORECASE)

    @cached_property
    def exclude_regex(self) -> re.Pattern[str] | None:
        """Return the compiled exclusion pattern, if any."""
        return re.compile(self.exclude) if self.exclude else None

    def matches(self, text: str) -> list[re.Match[str]]:
        """Return pattern matches that survive the exclusion rule."""
        found = list(self.regex.finditer(text))
        if self.exclude_regex is None:
            return found
        return [m for m in found if not self.exclude_regex.search(m.group(0))]


@dataclass
class Detector:
    """A named set of tell patterns."""

    name: str
    tells: list[TellPattern]

    def counts(self, text: str) -> Counter[str]:
        """Return occurrence counts per pattern ID (zero counts omitted)."""
        out: Counter[str] = Counter()
        for tell in self.tells:
            n = len(tell.matches(text))
            if n:
                out[tell.id] = n
        return out

    def spans(self, text: str) -> list[tuple[int, int, str]]:
        """Return (start, end, pattern id) for every match, sorted by position."""
        found = [
            (m.start(), m.end(), t.id) for t in self.tells for m in t.matches(text)
        ]
        return sorted(found)


def load_wikipedia(path: Path = DEFAULT_CONFIG) -> Detector:
    """Load the Wikipedia-derived detector from its TOML data file."""
    if not path.is_file():
        raise FileNotFoundError(f"Tell config not found at: {path}")
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    tells = [
        TellPattern(
            id=t["id"],
            kind=t["kind"],
            taxonomy=t["taxonomy"],
            section=t["section"],
            pattern=t["pattern"],
            audit=t["audit"],
            case_sensitive=t.get("case_sensitive", False),
            exclude=t.get("exclude"),
        )
        for t in data["tell"]
    ]
    return Detector(name="wikipedia", tells=tells)


def removal(input_counts: Counter[str], output_counts: Counter[str]) -> float | None:
    """Return the share of input tell occurrences gone from the output, or None if input has 0 tells.

    Counted by occurrence per pattern: e.g. six em dashes cut to one is 5/6 (83.3%) removed.
    """
    total = sum(input_counts.values())
    if not total:
        return None
    gone = sum(max(0, c - output_counts.get(k, 0)) for k, c in input_counts.items())
    return gone / total


def introduced(input_counts: Counter[str], output_counts: Counter[str]) -> int:
    """Return tell occurrences in the output beyond what the input had, per pattern."""
    return sum(max(0, c - input_counts.get(k, 0)) for k, c in output_counts.items())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect Wikipedia signs of AI writing in prose."
    )
    parser.add_argument("file", nargs="?", help="File to scan")
    parser.add_argument("--before", help="Input file (pre-edit) for comparison")
    parser.add_argument("--after", help="Output file (post-edit) for comparison")
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="Path to tells_wikipedia.toml"
    )
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    args = parser.parse_args()

    detector = load_wikipedia(Path(args.config))

    if args.before and args.after:
        before_text = Path(args.before).read_text(encoding="utf-8")
        after_text = Path(args.after).read_text(encoding="utf-8")
        b_counts = detector.counts(before_text)
        a_counts = detector.counts(after_text)
        rem = removal(b_counts, a_counts)
        intro = introduced(b_counts, a_counts)

        if args.json:
            print(
                json.dumps(
                    {
                        "input_tells": dict(b_counts),
                        "input_total": sum(b_counts.values()),
                        "output_tells": dict(a_counts),
                        "output_total": sum(a_counts.values()),
                        "removal_rate": rem,
                        "introduced_tells": intro,
                    },
                    indent=2,
                )
            )
        else:
            print(f"=== Comparative Evaluation: {args.before} -> {args.after} ===")
            print(f"Input tells:      {sum(b_counts.values())}")
            print(f"Output tells:     {sum(a_counts.values())}")
            print(f"Removal rate:     {f'{rem:.1%}' if rem is not None else 'N/A'}")
            print(f"Introduced tells: {intro}\n")
            all_ids = sorted(set(b_counts.keys()) | set(a_counts.keys()))
            print(f"{'Tell ID':<28} {'Before':<8} {'After':<8}")
            print("-" * 46)
            for tid in all_ids:
                print(f"{tid:<28} {b_counts.get(tid, 0):<8} {a_counts.get(tid, 0):<8}")
        return

    if not args.file:
        parser.print_help()
        sys.exit(1)

    text = Path(args.file).read_text(encoding="utf-8")
    counts = detector.counts(text)
    spans = detector.spans(text)

    if args.json:
        matches_detail = [
            {"start": s, "end": e, "tell": tid, "matched_text": text[s:e]}
            for s, e, tid in spans
        ]
        print(
            json.dumps(
                {
                    "file": args.file,
                    "total_tells": sum(counts.values()),
                    "counts": dict(counts),
                    "matches": matches_detail,
                },
                indent=2,
            )
        )
    else:
        print(f"=== Detection Results: {args.file} ===")
        print(f"Total tells found: {sum(counts.values())}\n")
        if counts:
            print(f"{'Tell ID':<28} {'Count':<8}")
            print("-" * 38)
            for tid, count in sorted(counts.items(), key=lambda x: -x[1]):
                print(f"{tid:<28} {count:<8}")
            print("\nMatch excerpts:")
            for s, e, tid in spans:
                snippet = text[max(0, s - 20) : min(len(text), e + 20)].replace(
                    "\n", " "
                )
                print(f"  [{tid}] '{text[s:e]}' in: ...{snippet}...")
        else:
            print("No Wikipedia AI tells detected.")


if __name__ == "__main__":
    main()
