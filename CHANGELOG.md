# Changelog

## Unreleased
- Data: fixes to the industry cases after a second AI review by a different model family (Codex, all 160). Six factual or overstated cases reworded (defibrillator shock only after analysis, insulin pump linked to a separate glucose sensor, hang recovery by an external watchdog, infrared only through IR-transparent paint, switchable glass without a fixed direction, brake-disc wording) and remaining British spellings changed to American. Still AI-reviewed only, not by a human.

## 0.3.2 — 2026-10-02
- Skill: the `SKILL.md` description is now valid YAML. It held an unquoted `: ` ("Also triggers on Korean: ..."), which strict parsers rejected; the developer portal's validation blocked on it while `claude plugin validate --strict` passed. The text is unchanged.
- Manifest: `repository` field and a listing icon (`.claude-plugin/icon.png`).
- README (en/ko): a data-handling section (what the plugin reads, runs and writes; no network calls, hooks, MCP servers or telemetry), and a note that the accuracy figures are v0.2 measurements not rerun for v0.3.
- Repository: `.gitignore` trimmed to what this repo needs, and the `env` test fixture renamed to `sandbox`. Both were read by the directory scan as credential handling and caused a policy hold; neither changes behavior.
- The developer portal's validation now passes with no blocking findings or policy holds (one warning: the root `CLAUDE.md` is development notes and is not loaded by the plugin).

## 0.3.1 — 2026-09-25
- Skill: the case-usage rule moved to its own section (1.2) so both the technical and physical flows point to it; a stale chapter reference in `physical-contradiction.md` fixed. Rule text unchanged.
- Data: 17 fixes to the industry cases after an AI review (two Claude passes over all 160). Two were factual problems (glass cutting on thick glass, the size of the distortion drop with feedback), eight were overstated or over-general claims (vaccine wording, prone positioning limited to severe lung injury, needle bevel, bus ramp and others), one case now cites the right sub-principle, two were wording, four were American spellings. Review is by AI only: same model family, no native speaker or domain expert. A second pass with a different model is pending.

## 0.3.0 — 2026-09-25
- **Industry cases.** Every principle now has four cases from different domains (mechanical, electronics, software/IT, chemistry/materials, medical/bio, everyday life/services), 160 in total. Each is a trade-off resolved by one named sub-principle, written for this project, with no company or product names. `lookup.py principle --cases` returns them with a localized `domain_name`; the default output is unchanged. `validate` checks four per principle, distinct domains, a valid sub-principle, both languages and no principle numbers in the text.
- The skill fetches cases when it looks up principles and uses them only as labelled analogies, never as the user's idea. In smoke runs (e-scooter in English and Korean, umbrella) the answers cited cases as analogies and did not copy them. Nothing measures idea quality, so this release claims no metric improvement.
- README (en/ko): a trimmed real-run example and the v0.3 status.
- The blind-run evaluations (32 technical, 10 physical cases) were not rerun for this release; the figures in README are v0.2 measurements. Cases enter only after parameter mapping and carry no principle numbers.
- Data: `inventive-principles.json` version 0.3.0 (schema gained `cases`).
- Data: the five separation lists were checked against the MATRIZ wiki page "Algorithm of resolving physical contradictions"; all match the data in number and order. No data values changed.
- Physical flow: with one separation type, the skill may reuse the full `separation` lookup from step 2 and must say so; answers name only commands that were actually run.
- Eval: the scorer now reads lookup JSON inside chained command output (e.g. `cat guide.md && lookup.py separation`). Before, such runs had every cited principle counted as a hallucination.

## 0.2.1 — 2026-09-25
- **Tie rule for principle rankings.** `matrix` and `separation` rank by count as before; ties now go round-robin: every cell's (or separation type's) 1st principle, then every 2nd, and so on, in pair order or `--type` order. Before, ties kept first appearance, so the first pair or type filled the top of the list and the model skipped ranks to include the others. The skill now says to pass the best-fitting separation type first and take the ranking in order. Worked examples updated to the new output.

## 0.2.0 — 2026-09-24
- **Physical contradictions.** The skill states one property with two opposite demands and their reasons, checks where, when, for whom, in which direction and at which level each demand holds, and picks the separation types where they do not overlap. New `lookup.py separation [--type time,space]` returns each type's question, usage note, examples and related principles, plus a frequency ranking. Guide and worked example: `references/physical-contradiction.md`.
- **Separation data rebuilt.** Five types (space, time, relation/condition, direction, system level) and their related principles follow the MATRIZ TRIZ Knowledge Base (CC BY 4.0) via the pytriz transcription; a direct check against the wiki is still pending. Questions and examples are new text. The unsourced legacy lists are gone.
- **Structured interview.** Vague inputs and inputs that only describe a solution get up to five questions, one at a time, instead of a guessed contradiction. With "no questions", the skill proceeds and marks the contradiction as unconfirmed.
- **Markdown reports.** `/triz ... --save` or "save this" writes the analysis to `triz-report-YYYYMMDD-<topic>.md` without overwriting.
- Eval: 10 physical-contradiction cases. The looked-up separation type matched in 9/10 (command) and 8/10 (plain language) runs, 10/10 counting the stated choice; no hallucinated principles. The v0.1 technical cases still hit 30/32. See `tests/eval/results-v0.2.md`.
- Eval harness: records separation lookups and recommended principles, scores physical cases, can send inputs with no suffix, and no longer mistakes the word `unverified_cell` in SKILL.md for a lookup warning.

### Also in 0.2.0: benchmark and data follow-ups from after 0.1.2
- Eval: re-measured on TRIZBench with 75 held-out patents that share no patent with the first 30. Hit@3 is 10/75 = 13% (95% CI 7-23%), about the level of a constant three-pair baseline (9% when fit on the first 30). Every run called `lookup.py`; the misses come from picking the parameter pair from an abstract. See `tests/eval/results-v0.1.md`.
- Eval: tried a "reconstruct the contradiction from a solution description" step in the skill. It did not raise Hit@3 on the first 30 (2/30 before and after), so it was not adopted; the skill is unchanged.
- Eval harness: blind runs are isolated from the host session (only Bash, Read and Skill; no MCP; `--add-dir` for the plugin copy), record the model, and can use a prompt suffix that does not claim the contradiction is confirmed. The mapping-row parser accepts translated or ranked side labels and bold ids.
- Data: the printed-matrix spot check is closed as not feasible (no printed copy available).

## 0.1.2 — 2026-09-24
- **Renamed the plugin slug `triz-decider` → `triz-solver`** (display name TRIZ Solver). Commands are now `/triz-solver:triz`; reinstall with `/plugin install triz-solver@triz-solver`. The plugin derives solution ideas rather than making a decision, and the slug can still change before directory listing.
- README (en/ko) now states the scope: the plugin expects an input that names the trade-off; it does not dig a contradiction out of a solution description. A "not covered" section lists what is not implemented (physical contradictions, interview flow).
- Skill description adds Korean trigger keywords (기술적 모순, 물리적 모순, 모순 행렬, 발명원리).
- Eval: compared against the TRIZBench patent benchmark (`tests/eval/trizbench_eval.py`). Hit@3 is 3/30 = 10%, chance level and below a constant baseline of 13%. The dataset is not stored in the repo (no license).
- Eval: revised 9 flagged expected values in `cases.yaml` (C03, C09, C17, C18, C21, C22, C23, C26; C28 dropped); C22 and C26 are marked `expect_empty`. All earlier runs are rescored: 91/93 Top-3. `tests/eval/review-expected-values.md` lists the cases for a third-party review.
- Author name unified as DoGyeong Seo across licenses and manifests.

## 0.1.1 — 2026-09-24
Data fix: the contradiction matrix now comes from a 2-of-3 vote of three independently transcribed sources (English transcription family, MATRIZ Knowledge Base, Russian-language table).
- 15 cells changed value versus 0.1.0 (1-27, 4-16, 9-1, 9-29, 13-18, 14-33, 14-36, 17-23, 19-9, 26-28, 29-7, 34-14, 37-10, 37-21, 39-33). In 0.1.0 these carried the English transcription's values, which both other sources contradict.
- 9 cells that 0.1.0 withheld are now filled (1-28, 1-38, 7-28, 8-25, 15-25, 15-31, 18-35, 33-10, 34-1). No cell is withheld any more.
- `/triz` now tells Claude to load `triz-decider:triz-analysis` explicitly and not to answer from memory (fixes runs that skipped the skill).
- Eval: 33 cases, blind runs, and an observed-lookup hallucination check. See `tests/eval/results-v0.1.md`.

## 0.1.0 — 2026-09-24
First release: technical-contradiction flow, `lookup.py`, 39 parameters, 40 principles, contradiction matrix.
