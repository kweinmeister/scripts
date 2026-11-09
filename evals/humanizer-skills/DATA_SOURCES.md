# Data Sources & Corpus Design

A rigorous evaluation of automated editing requires an untainted ground truth: passages where human authorship is provably authentic, paired with model drafts that cover the exact same underlying facts.

---

## 1. The Pre-LLM Temporal Cutoff

To evaluate how editing tools treat authentic human writing, the human baseline corpus is pinned to documents published before **November 30, 2022**.

### Proving Authentic Human Provenance

Establishing that an online text predates modern large language models requires verification beyond the visible publication date:

- **CMS Migrations Invalidate Publication Timestamps:** Web platforms frequently
  touch older content during site redesigns. In early sampling, older posts accessed
  through live APIs frequently reported 2023 or 2024 modification dates despite a
  2021 byline. A passage should only be accepted if either an immutable archive
  record or an explicit server-level `modified_gmt` timestamp confirms that the
  prose itself was fixed before late 2022.
- **Immutable Public Records:** Certain public record collections are legally or
  operationally fixed upon issuance:
  - **Federal Register** final rules and preambles are permanent legal records.
  - **National Weather Service** Area Forecast Discussions (AFDs) archived in
    meteorological repositories (such as the Iowa Environmental Mesonet) are
    append-only historical records.
- **Extraction Artifacts Become Edit Targets:** Web scrapers often leave subtle
  artifacts: spaces before punctuation from stripped hyperlinks, leftover image
  caption markers, or footnote superscripts. If left uncleaned, editing agents
  "fix" these extraction bugs rather than editing authentic prose. Normalizing
  these artifacts upfront ensures the evaluation measures editorial cleanup
  rather than HTML sanitation.

---

## 2. Five Public-Domain US Federal Sources

To avoid evaluating a single institutional or academic style, the baseline corpus incorporates 50 primary passages (10 each) across five distinct public-domain federal genres:

| Source                                                    | Genre / Domain                      | Editorial Voice & Characteristics                                                                                |
| :-------------------------------------------------------- | :---------------------------------- | :--------------------------------------------------------------------------------------------------------------- |
| **Library of Congress** (_Folklife Today_)                | Cultural Narrative & History        | Rich personal voice, narrative storytelling, historical nuance, and conversational cadence.                      |
| **Federal Reserve Board** (_FEDS Notes_)                  | Macroeconomics & Finance            | Analytical argumentation, statistical rigor, formal institutional register, and dense causal logic.              |
| **Government Publishing Office** (_Government Book Talk_) | Non-Fiction Reviews & History       | Narrative non-fiction, curated literature summaries, and accessible civic educational tone.                      |
| **National Weather Service** (_IEM AFD Archive_)          | Meteorology & Technical Discussions | Real-time technical jargon, active reasoning under uncertainty, and terse observational prose.                   |
| **Federal Register** (_Rules & Preambles_)                | Law & Public Policy                 | High-complexity administrative preambles (filtered to significant regulatory actions, omitting templated forms). |

### Corpus Filtering Rules

- **Contiguous Paragraph Windows:** Instead of taking arbitrary prefixes (which often contain opening boilerplate like _"Today's post comes from..."_), the corpus extracts cohesive paragraph sequences sharing thematic terms with the article title.
- **Cap on Direct Quotations:** Passages with over 30% quoted speech are excluded, ensuring the text represents the author's own cadence rather than interview subjects.
- **Exclusion of Missing Visual References:** Any passage containing orphan references to visual media (e.g. _"the chart above"_, _"this map shows"_) is excluded so editing agents are not forced to reconcile missing figures.

---

## 3. Atomic Fact Extraction & Reconciled Knowledge Base

To isolate _style_ from _content_, each human passage undergoes comprehensive atomic fact extraction:

1. **Independent Dual Extraction:** Two distinct models (`gemini-4-argon` and `claude-sonnet-5-5`, both at medium reasoning effort) independently extract discrete atomic facts from each passage.
2. **Reconciliation & Deduplication:** Extracted fact lists are merged into atomic claims, classifying items by origin (shared vs. single-extractor).
3. **Adjudication:** Disagreements or ambiguous claims are adjudicated by an independent model (`gemini-3.1-pro-preview`) with final human spot-checking, yielding over 1,400 atomic reference facts across the 50 passages.

---

## 4. Controlled Model Rewriting (150 Parallel Drafts)

Using _only_ the extracted atomic facts and a neutral brief (specifying target word count matching the original), three distinct model tiers generated parallel drafts:

1. **Frontier Reasoning Tier:** `claude-opus-5-5` (low-cliché stress test).
2. **Open-Weight Tier:** `google/gemma-4-26b-a4b-it-maas` (compact open weights, thinking disabled).
3. **Lightweight Fast Tier:** `gemini-3.5-flash-lite` (rapid everyday drafting).

### Why This Design Matters

This 200-passage matrix (50 human originals + 150 fact-controlled model drafts) enables two independent, uncompromised measurement tracks:

- **Voice Preservation Track (Human Text):** Tested on the 50 pre-LLM human passages. The agent does not know whether the text is human or machine-generated. Measures whether the editor respects authentic human voice or aggressively rewrites it.
- **Slop Removal Track (Model Text):** Tested on the 150 model drafts. Measures whether the editor successfully strips modern tells without losing underlying facts.
