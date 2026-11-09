# Humanizer Skills Evaluation Guide & Benchmark

This directory provides the methodology, data sources, reference catalogs, and evaluation tools used to benchmark automated editing skills against a direct prompt baseline.

The evaluation examines a central question for AI-assisted writing workflows: **Do specialized "humanizer" skills improve upon a direct prompt when editing AI-generated drafts, and do they preserve authentic human voice?**

---

## Executive Summary & Core Insights

In reference evaluations, seven community editing skills were benchmarked alongside an unspecialized control prompt across 200 passages (50 pre-LLM human texts across 5 federal genres, and 150 fact-matched model rewrites) over multiple independent trials on `claude-sonnet-5-5`.

```text
                  THE EDITORIAL PARETO FRONTIER

  Human Text      ▲
  Preserved (%)   │  High-Preservation (Verbatim Focus)
             100% ┤     [•]
                  │        \
                  │         [•] Formatting & Contextual Cleanup
              90% ┤            \
                  │             [★] Direct Prompt Control (Baseline)
                  │                \
              80% ┤                 [•] Multi-Pass Pattern-Gated
                  │                    \
                  │                     [•] Transformative Restructuring
              70% ┤
                  └────────────────────────────────────────►
                  0%        20%       40%       60%
                              AI Tells Removed (%)
```

### Key Empirical Findings

1. **The Direct Prompt Baseline is Tough to Beat:**
   Simply instructing a modern frontier model (_"Edit `input.md` to remove signs of AI writing, if there are any. Keep the meaning, facts, and register..."_) removed **one third of all AI tells** while leaving **92% of authentic human writing untouched** with **97.1% fact retention**.
2. **The Frontier Trade-Off (Preservation vs. Tell Removal):**
   Skills do not escape the Pareto frontier; they move along it. Techniques that cut more AI tells consistently rewrite more human text, while conservative approaches preserve voice by leaving subtle tells behind.
3. **Editorial Archetypes, Not Leaderboards:**
   The primary differentiator between editing approaches is not their banned-word lists (which are largely similar), but their **threshold of evidence** before rewriting:
   - **High-Preservation / Verbatim Archetype:** Leaves ambiguous sentences alone and edits only blatant tells. Retains ~98.5% of human phrasing (ideal for legal, compliance, or technical API docs).
   - **Contextual & Formatting-Focused Archetype:** Flags stylistic habits only when multiple cues co-occur. Highly effective at stripping Markdown formatting clutter (bolded bullet lead-ins and decorative emoji) at ~93% preservation.
   - **Multi-Pass Pattern-Gated Archetype:** Evaluates text across multiple editorial passes and requires overlapping signals before intervening. Achieves deeper cleanup (~39% tell reduction) while retaining ~88% of human phrasing.
   - **Transformative / Brand-Voice Archetype:** Reconstructs prose around active hooks and conversational cadence (~40% tell removal, ~85% preservation).
   - **Rule-Enforced / Constraint Archetype:** Zero-tolerance imperatives (such as blanket bans on passive voice) frequently rewrite authentic human cadences and invent ungrounded subjects.
4. **Agents Rely on In-Context Rules (Scripts are Skipped):**
   Across sandboxed test runs with full Bash access, models invoked bundled Python scanner scripts **0 of 600 times**. Models consistently audit text directly in context and skip external relative script calls or passive reference links. Guidance must be inline or explicitly loaded upfront.
5. **The Initial Drafting Model Matters Far More than the Skill:**
   Moving from a lightweight or open-weight model to a high-end reasoning model eliminates ~6.6 tells per 1,000 words _before editing_. In contrast, upgrading from a plain prompt to the cleanest editing skill gains only 0.6 to 1.1 tells per 1,000 words.

---

## Directory Contents

| Path                                                                         | Purpose                                                                                                                                     |
| :--------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------ |
| **[`DATA_SOURCES.md`](DATA_SOURCES.md)**                                     | Pre-LLM historical cutoff verification, five US federal genres, artifact cleanup, and atomic fact extraction.                               |
| **[`METHODOLOGY.md`](METHODOLOGY.md)**                                       | Sandboxed execution harness (`claude plugin eval`), double-blind judging with Gemini 4 Argon, metric definitions, and statistical controls. |
| **[`config/skills_reference.toml`](config/skills_reference.toml)**           | Pinned repository commits and paths for community skills evaluated in the benchmark.                                                        |
| **[`config/tells_wikipedia.toml`](config/tells_wikipedia.toml)**             | Authoritative 22 signs of AI writing from Wikipedia's WikiProject AI Cleanup, with regexes, taxonomies, and audit terms.                    |
| **[`config/tells_reference.toml`](config/tells_reference.toml)**             | Empirical frequency rates for modern overused tokens versus Wikipedia structural tell patterns.                                             |
| **[`scripts/detect_wikipedia_tells.py`](scripts/detect_wikipedia_tells.py)** | Standalone scanner detecting the 22 Wikipedia tell patterns, computing removal rate and introduced tells.                                   |
| **[`scripts/score_metrics.py`](scripts/score_metrics.py)**                   | Deterministic scoring for token preservation, change amount, length ratio, change summary check, and edit precision.                        |
| **[`scripts/audit_skill_overlap.py`](scripts/audit_skill_overlap.py)**       | Audits candidate skills for circularity by checking whether their instructions explicitly target the tell patterns.                         |
| **[`scripts/scaffold_eval_cases.py`](scripts/scaffold_eval_cases.py)**       | Generates isolated test cases (`case.yaml`, `scaffold.sh`, `prompt.md`, `graders/`) for `claude plugin eval`.                               |

---

## Modern Tells vs. Historical Memes

Static banned-word lists often target early generative AI clichés that current frontier models have largely abandoned:

- **Historical Memes (Rare in Modern Models):** In fact-grounded drafts, _delve_ appeared only ~0.04 times per 1,000 words (~1 per 25,000 words), and _tapestry_ only ~0.02 times.
- **Modern High-Frequency Tells:** Overuse has shifted toward ordinary emphasis connectors and evaluative modifiers:
  - **`specifically`**: 5.4× overrepresented vs. human baseline (0.64 vs. 0.12 per 1k words).
  - **`essential`**: 8.3× overrepresented vs. human baseline (0.49 vs. 0.06 per 1k words).
  - **`though`**: 5.0× overrepresented vs. human baseline (1.40 vs. 0.28 per 1k words).
  - **`furthermore`**, **`vital`**, **`alongside`**: Prominent in model drafts, virtually absent in authentic pre-LLM federal prose.

See [`config/tells_reference.toml`](config/tells_reference.toml) for the complete reference catalog.

---

## Step-by-Step Reproduction Guide

To run a similar benchmark or evaluate your own custom editing skill:

### Step 1: Install & Package Skills as Local Plugins

Clone candidate skills at pinned commits and place each in a standalone plugin directory with a valid `plugin.json` descriptor:

```bash
# Refer to config/skills_reference.toml for pinned commits
git clone https://github.com/<author>/<repo> ./plugins/<skill-id>
```

### Step 2: Prepare Input Passages

Collect paired passages following the guidelines in [`DATA_SOURCES.md`](DATA_SOURCES.md):

- A set of verified pre-LLM human passages (to measure voice preservation).
- A matching set of model drafts covering the identical underlying facts (to measure tell removal).

### Step 3: Scaffold Test Cases

Use [`scripts/scaffold_eval_cases.py`](scripts/scaffold_eval_cases.py) to generate isolated case directories:

```bash
# Scaffold test cases across skills and baseline control from a folder of drafts
python3 scripts/scaffold_eval_cases.py \
  --inputs-dir ./drafts \
  --output-dir ./eval_suite \
  --skills-config config/skills_reference.toml
```

### Step 4: Run the Evaluation Suite

Run the test cases using `claude plugin eval`, wrapping long suites in `caffeinate -i` to prevent system sleep:

```bash
caffeinate -i claude plugin eval ./eval_suite \
  --plugin ./plugins/<skill-id> \
  --concurrency 4
```

### Step 5: Score Outputs

Use the provided standalone tools to measure outcomes:

```bash
# 1. Deterministic edit preservation and length ratio
python3 scripts/score_metrics.py --before input.md --after output.md

# 2. Tell removal rate and newly introduced tells
python3 scripts/detect_wikipedia_tells.py --before input.md --after output.md

# 3. Check for circularity (overlap between skill instructions and tell list)
python3 scripts/audit_skill_overlap.py ./plugins/<skill-id>
```

---

## Practical Takeaways for Developers & Writers

1. **Start with a Plain Prompt:** For routine editorial cleanup, a direct prompt on a frontier model provides the cleanest baseline, removing a third of repetitive phrasing with minimal distortion to human voice.
2. **Match Skills to Specific Editorial Jobs:**
   - Reach for a **high-preservation skill** when phrasing cannot drift (technical documentation, contracts, regulations).
   - Reach for a **formatting-focused skill** when cleaning Markdown drafts cluttered with bold lead-ins and emoji.
   - Reach for a **multi-pass pattern-gated skill** only when an AI draft requires heavier prose intervention than a standard prompt provides.
3. **Draft with Strong Models First:** Prioritize initial drafting quality over post-hoc editing tools; stronger models produce fewer structural tells from the start.
