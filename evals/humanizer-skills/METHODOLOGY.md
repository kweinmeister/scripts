# Benchmark Methodology & Evaluation Framework

Evaluating whether automated editing skills improve text quality requires a rigorous, reproducible harness that prevents bias, isolates factual accuracy from stylistic changes, and applies sound statistical controls.

---

## 1. Experimental Design & Arms

The benchmark compares eight experimental arms across 200 input passages, repeated across $k=3$ independent trials:

- **Control Arm:** A direct, unspecialized editing prompt executed by the baseline model without external skills.
- **Seven Community Skill Arms:** Pinned versions of community open-source editing skills.

### Unified Prompting Structure

To ensure differences stem strictly from skill guidance rather than prompt engineering, the instructions are identical across all arms:

```text
# Skill Arms
Use /{skill} to edit `input.md` to remove signs of AI writing, if there are any.
Keep the meaning, facts, and register. Don't ask clarifying questions. Write only
the final text to `output.md`, with no change summary or notes.

# Control Baseline Arm
Edit `input.md` to remove signs of AI writing, if there are any. Keep the meaning,
facts, and register. Don't ask clarifying questions. Write only the final text to
`output.md`, with no change summary or notes.
```

The conditional framing (_"if there are any"_) replicates realistic production workflows where an automated editor processes drafts without prior knowledge of whether the text originated from a human or a model.

---

## 2. Sandboxed Execution Harness

Every trial runs within an isolated sandbox managed by `claude plugin eval`:

- **Agent Model:** `claude-sonnet-5-5`.
- **Clean State:** Each run executes inside a fresh containerized environment with access only to the staged `input.md` and the designated plugin.
- **Tool Access:** Bash and standard file manipulation tools are available.
- **Supervision & Execution Hygiene:**
  - Mac sleep prevention (`caffeinate -i`) during multi-hour test suites.
  - Per-run timeout set to 180 seconds (p90 run duration was under 30 seconds).
  - Automated fail-fast limits triggered if consecutive timeouts or system errors accumulate.

---

## 3. Conflict of Interest Rules & Independent Judging

To avoid self-evaluation bias, strict conflict-of-interest firewalls govern the scoring pipeline:

1. **Family Isolation:** No Claude-family model is permitted to judge or grade Claude Code's editing outputs.
2. **Dedicated Independent Evaluators:**
   - **Primary Judge:** `gemini-4-argon` (high reasoning effort).
   - **Secondary Judge:** `gemini-3.8-flash` (low reasoning effort).
3. **Double-Blind Fact Verification:** Judges receive the edited text alongside the reconciled atomic fact list for the passage, grading:
   - **Fact Retention:** Which atomic facts from the original remain present and accurate.
   - **Hallucination / Invention:** Whether the editor introduced new factual claims ungrounded in the source.

---

## 4. Evaluation Metrics Suite

Edits are evaluated across deterministic stylistic indicators and factual retention:

> [!NOTE]
> The scripts in [`scripts/`](scripts/) provide the standalone, zero-cost deterministic metric battery (Levenshtein preservation, Wikipedia tell catalog, edit precision, length ratio, and offline graders). LLM-as-a-judge fact verification (Atomic Fact Retention & Precision) and learned statistical classifiers are conducted via external API judge runs against benchmark corpora.

### A. AI Tell Removal Rate (%)

Measures the reduction in AI-characteristic phrasing across model-generated drafts:

- **Learned / Derived Detector:** A statistical classifier trained using 2-fold cross-fitting to detect overrepresented multi-token patterns without overfitting to specific prompts.
- **Wikipedia Heuristic Matcher:** A deterministic regex matcher implementing WikiProject AI Cleanup heuristics (staged rhetorical openers, colon questions, forced triads, _"not X, but Y"_ negative parallelism, copulative avoidance, and trailing participial phrases).
- **Tell Density:** Frequency of detected tell tokens per 100 words.

### B. Human Text Preservation (%)

Measures the proportion of original wording left intact when editing authentic pre-LLM human passages. High preservation indicates an editor that exercises restraint and respects the author's voice; low preservation indicates over-editing and text churn.

### C. Edit Precision (%)

Measures surgical focus: the proportion of changed tokens falling within input sentences that contained an identified AI tell, divided by all changed tokens. This separates precise edits from broad, indiscriminate text churn.

### D. Fact Retention & Precision (%)

Tracks retention of atomic facts (out of ~1,400 reference claims) across both human and model inputs. In the benchmark, all arms maintained strong fact retention (96.7% to 97.4%, closely matching the control's 97.1%).

### E. Secondary Stylistic Indicators

- **Length Ratio:** Output word count divided by input word count (monitors unauthorized expansion or aggressive pruning).
- **Part-of-Speech Densities:** Shifts in nominalization rates, passive verb structures, and participial modifiers.
- **Vocabulary Metrics:** Burstiness and Measure of Textual Lexical Diversity (MTLD).

---

## 5. Statistical Rigor

- **Paired Comparisons:** Every skill run is compared directly against the control prompt on the exact same passage and trial index.
- **Clustered Standard Errors:** Standard errors are clustered by passage ($N=50$ passage clusters) to account for correlation among runs sharing the same source text.
- **Holm-Bonferroni Correction:** Multiple-testing adjustments applied across the pairwise family ($m=28$ comparisons) to control family-wise error rates while preserving statistical power.
