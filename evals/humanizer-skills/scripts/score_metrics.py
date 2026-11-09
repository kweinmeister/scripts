#!/usr/bin/env python3
"""Deterministic per-output metrics for humanizer evaluations.

Ported directly from the humanizer evaluation harness (src/bakeoff/metrics.py and src/bakeoff/corpus/text.py).

Metrics:
- Tokens: words, with each punctuation mark as its own token, case-sensitive.
- Change amount: token-level Levenshtein distance / the longer text's token count.
- Preservation: 1.0 - change amount (1.0 means completely untouched).
- Length ratio: output tokens / input tokens.
- Edit precision: changed tokens falling in input sentences that contained an AI tell,
  divided by all changed tokens. Undefined (None) when nothing changed.
- Appended change summary: checks if the model appended meta-commentary ("# Changes", "**What changed**").
- Tell density: tells per 100 tokens.

Usage:
    python3 score_metrics.py --before input.md --after output.md
    python3 score_metrics.py --before input.md --after output.md --json
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Try rapidfuzz for C-accelerated Levenshtein; fallback to pure Python
try:
    from rapidfuzz.distance import Levenshtein as _rf_Levenshtein  # type: ignore
except ImportError:
    _rf_Levenshtein = None


@dataclass(frozen=True)
class _OpCode:
    tag: str
    src_start: int
    src_end: int
    dest_start: int
    dest_end: int


def _token_levenshtein(a: list[str], b: list[str]) -> int:
    if _rf_Levenshtein is not None:
        return int(_rf_Levenshtein.distance(a, b))
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for x in a:
        curr = [prev[0] + 1] + [0] * len(b)
        for j, y in enumerate(b):
            cost = 0 if x == y else 1
            curr[j + 1] = min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost)
        prev = curr
    return prev[len(b)]


def _token_opcodes(a: list[str], b: list[str]) -> Any:
    if _rf_Levenshtein is not None:
        return _rf_Levenshtein.opcodes(a, b)
    matcher = difflib.SequenceMatcher(None, a, b)
    return [_OpCode(*op) for op in matcher.get_opcodes()]


_TOKEN = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]")
CHANGE_SUMMARY_PATTERN = r"^\s*(#{1,6}\s*|\*\*)(changes|what changed)\b"
_CHANGE_SUMMARY = re.compile(CHANGE_SUMMARY_PATTERN, re.I | re.M)

_SENTENCE_END = re.compile(r"(?<=[.!?])[\"”’)]?\s+(?=[A-Z“\"(‘])")
_ABBREVIATIONS = {
    "u.s.",
    "u.k.",
    "u.n.",
    "d.c.",
    "mr.",
    "mrs.",
    "ms.",
    "dr.",
    "st.",
    "no.",
    "inc.",
    "co.",
    "corp.",
    "jr.",
    "sr.",
    "e.g.",
    "i.e.",
    "vs.",
    "etc.",
    "fig.",
    "gen.",
    "gov.",
    "sen.",
    "rep.",
    "jan.",
    "feb.",
    "mar.",
    "apr.",
    "aug.",
    "sept.",
    "sep.",
    "oct.",
    "nov.",
    "dec.",
}


@dataclass(frozen=True)
class Token:
    """One token and its character span in the source text."""

    text: str
    start: int
    end: int


def tokenize(text: str) -> list[Token]:
    """Split text into word and punctuation tokens with character offsets."""
    return [Token(m.group(0), m.start(), m.end()) for m in _TOKEN.finditer(text)]


def change_amount(before: str, after: str) -> float:
    """Return token-level edit distance divided by the longer text's token count."""
    a = [t.text for t in tokenize(before)]
    b = [t.text for t in tokenize(after)]
    longest = max(len(a), len(b))
    if not longest:
        return 0.0
    return _token_levenshtein(a, b) / longest


def preservation(before: str, after: str) -> float:
    """Return 1.0 - change amount (1.0 means completely untouched)."""
    return 1.0 - change_amount(before, after)


def length_ratio(before: str, after: str) -> float:
    """Return output tokens / input tokens."""
    n = len(tokenize(before))
    return len(tokenize(after)) / n if n else 0.0


def sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences, avoiding breaking after abbreviations or initials."""
    out: list[str] = []
    for piece in (p.strip() for p in _SENTENCE_END.split(paragraph)):
        if not piece:
            continue
        last = out[-1].split()[-1].lower() if out else ""
        if out and (last in _ABBREVIATIONS or re.fullmatch(r"[a-z]\.", last)):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return out


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return character spans of each sentence, paragraph by paragraph."""
    spans: list[tuple[int, int]] = []
    for block in re.finditer(r"[^\n]+", text):
        cursor = block.start()
        for sent in sentences(block.group(0)):
            start = text.find(sent, cursor, block.end())
            if start < 0:
                continue
            spans.append((start, start + len(sent)))
            cursor = start + len(sent)
    return spans


def _sentence_of(position: int, spans: list[tuple[int, int]]) -> int:
    """Return the index of the sentence containing (or nearest before) a character position."""
    best = 0
    for i, (start, _end) in enumerate(spans):
        if start <= position:
            best = i
        else:
            break
    return best


def edit_precision(
    before: str, after: str, tell_spans: list[tuple[int, int]]
) -> tuple[float | None, int]:
    """Return (edit precision, changed token count) for an edit of `before` into `after`.

    Every replaced or deleted input token belongs to the sentence it was in; inserted
    tokens belong to the input sentence at the insertion point. A token counts as on
    target when its sentence overlaps any tell span. Precision is None when nothing
    changed, so untouched outputs are excluded from averages rather than scored 1.0.
    """
    a = tokenize(before)
    b = tokenize(after)
    spans = sentence_spans(before) or [(0, len(before))]
    tell_sentences = {
        i
        for i, (s, e) in enumerate(spans)
        if any(ts < e and s < te for ts, te in tell_spans)
    }
    on_target = changed = 0

    def credit(sentence: int, n: int) -> None:
        nonlocal on_target, changed
        changed += n
        if sentence in tell_sentences:
            on_target += n

    for op in _token_opcodes([t.text for t in a], [t.text for t in b]):
        if op.tag == "equal":
            continue
        if op.tag in ("replace", "delete"):
            for tok in a[op.src_start : op.src_end]:
                credit(_sentence_of(tok.start, spans), 1)
        if op.tag in ("replace", "insert"):
            extra = (op.dest_end - op.dest_start) - (
                (op.src_end - op.src_start) if op.tag == "replace" else 0
            )
            if extra > 0:
                anchor = (
                    a[op.src_start].start
                    if op.src_start < len(a)
                    else (a[-1].start if a else 0)
                )
                credit(_sentence_of(anchor, spans), extra)

    return (on_target / changed if changed else None), changed


def has_change_summary(text: str) -> bool:
    """Report whether an output carries an appended change-summary section."""
    return bool(_CHANGE_SUMMARY.search(text))


def tell_density(counts: Counter[str], text: str) -> float:
    """Return tells per 100 tokens."""
    n = len(tokenize(text))
    return 100 * sum(counts.values()) / n if n else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score deterministic preservation & edit metrics."
    )
    parser.add_argument("--before", required=True, help="Path to input.md (pre-edit)")
    parser.add_argument("--after", required=True, help="Path to output.md (post-edit)")
    parser.add_argument(
        "--tell-spans",
        help="Optional JSON file or string of tell spans [[start, end], ...] for edit precision",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    args = parser.parse_args()

    before_text = Path(args.before).read_text(encoding="utf-8")
    after_text = Path(args.after).read_text(encoding="utf-8")

    pres = preservation(before_text, after_text)
    chg = change_amount(before_text, after_text)
    lr = length_ratio(before_text, after_text)
    summary_appended = has_change_summary(after_text)

    prec = None
    changed_toks = 0
    if args.tell_spans:
        try:
            if Path(args.tell_spans).is_file():
                raw_data = json.loads(Path(args.tell_spans).read_text(encoding="utf-8"))
            else:
                raw_data = json.loads(args.tell_spans)

            # Unpack matches list if full detection JSON was passed
            if isinstance(raw_data, dict) and "matches" in raw_data:
                raw_spans = raw_data["matches"]
            elif isinstance(raw_data, list):
                raw_spans = raw_data
            else:
                raw_spans = []

            spans: list[tuple[int, int]] = []
            for s in raw_spans:
                if isinstance(s, (list, tuple)) and len(s) >= 2:
                    spans.append((int(s[0]), int(s[1])))
                elif isinstance(s, dict):
                    if "start" in s and "end" in s:
                        spans.append((int(s["start"]), int(s["end"])))
                    elif "span" in s and len(s["span"]) >= 2:
                        spans.append((int(s["span"][0]), int(s["span"][1])))

            prec, changed_toks = edit_precision(before_text, after_text, spans)
        except Exception as err:
            print(f"Warning: could not compute edit precision ({err})", file=sys.stderr)

    results = {
        "preservation": pres,
        "change_amount": chg,
        "length_ratio": lr,
        "appended_change_summary": summary_appended,
        "edit_precision": prec,
        "changed_tokens": changed_toks,
        "input_tokens": len(tokenize(before_text)),
        "output_tokens": len(tokenize(after_text)),
    }

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=== Deterministic Output Metrics ===")
        print(f"Preservation:             {pres:.1%} (1.0 = untouched)")
        print(f"Change amount:            {chg:.1%}")
        print(
            f"Length ratio:             {lr:.2f}x ({results['output_tokens']} / {results['input_tokens']} tokens)"
        )
        print(
            f"Appended change summary:  {'YES (penalty)' if summary_appended else 'NO (clean)'}"
        )
        if prec is not None:
            print(
                f"Edit precision:           {prec:.1%} of changed tokens on tell sentences ({changed_toks} changed)"
            )


if __name__ == "__main__":
    main()
