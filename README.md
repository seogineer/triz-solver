# TRIZ Solver

[한국어](README.ko.md)

A Claude Code plugin that helps you resolve engineering and product trade-offs with **TRIZ**. It turns a problem into a contradiction and proposes ideas: a **technical contradiction** (improving one property worsens another) goes through the classic contradiction matrix and the 40 inventive principles; a **physical contradiction** (one property must be both high and low) goes through the separation principles.

No server, database or API key. Claude does the reasoning; a small standard-library Python script does every lookup, so matrix cells, separation types and principle numbers are never recalled from memory.

> **Status: v0.3 (pre-release).** Technical and physical contradictions, a guided interview for vague inputs, Markdown reports, and 160 industry cases (four per principle) used as analogies. See [Data status](#data-status) before relying on results.

## Install

```
/plugin marketplace add seogineer/triz-solver
/plugin install triz-solver@triz-solver
```

To try it from a local checkout: `claude --plugin-dir .`

## Use

```
/triz An umbrella must be large to keep the rain off but small to carry
/triz Raising the top speed of my e-scooter drains the battery too fast --save
```

If `/triz` is not recognised in your session, use the full name `/triz-solver:triz`. Add `--save` (or ask "save this") to write the analysis to `triz-report-YYYYMMDD-<topic>.md` in the current directory.

You can also just describe the problem in plain language (English or Korean); the `triz-analysis` skill activates on its own. The answer follows the language you write in.

**Technical contradiction** ("improving X worsens Y"):

1. Restate the problem as "improving X worsens Y" and confirm it with you
2. Map X and Y to the 39 engineering parameters (1–3 candidates each, with reasons)
3. Look up every candidate pair in the matrix (`lookup.py matrix`)
4. Rank principles by how often they appear
5. Fetch each principle's definition and four industry cases (`lookup.py principle --cases`)
6. Write ideas tailored to your system, one to three per principle

**Physical contradiction** ("X must be P for one reason and not-P for another"):

1. Restate it as one property with two opposite demands and their reasons
2. Check where, when, for whom, in which direction and at which level each demand holds (asking you one question at a time when the input does not say)
3. Pick the separation types where the demands do not overlap: space, time, relation (condition), direction or system level
4. Look up their related principles (`lookup.py separation`) and write ideas that implement the separation

**Vague input, or a text that only describes a solution** (such as a patent abstract): the skill asks up to five questions, one at a time, to find the contradiction instead of guessing it. On an independent patent benchmark, guessing did no better than chance; see Data status.

## Example

A trimmed real run (v0.3.0, model `claude-opus-5-5`, contradiction confirmed up front). Only the first of the five principles' ideas is shown.

```
/triz Raising the top speed of my e-scooter drains the battery too fast.
```

> **Parameter mapping**
>
> | Role | Parameter | Why |
> | --- | --- | --- |
> | Improving | #9 Speed | The goal is a higher top speed. |
> | Worsening | #19 Use of energy (moving object) | Battery power draw of the moving scooter goes up. |
> | Worsening | #22 Loss of energy | At high speed, air drag and heat losses grow. |
> | Worsening | #15 Duration of action (moving) | Shorter range and runtime per charge. |
>
> **Recommended principles (matrix lookup)**: cells 9×19 → 8, 15, 35, 38 · 9×22 → 14, 20, 19, 35 · 9×15 → 3, 19, 35, 5
>
> | Rank | Principle | Count |
> | --- | --- | --- |
> | 1 | #35 Parameter Changes | 3 |
> | 2 | #19 Periodic Action | 2 |
> | 3 | #8 Anti-Weight (Counterweight) | 1 |
> | 4 | #14 Spheroidality (Curvature) | 1 |
> | 5 | #3 Local Quality | 1 |
>
> **#35 Parameter Changes**
> - *Manage motor and battery temperature (sub-principle 4).* Copper loss rises with winding temperature, and a cold or hot battery has higher internal resistance. Add a thermal path from the hub motor to the deck and warm the pack before winter rides.
> - *Make suspension and tyres adjustable by speed (sub-principle 3).* Firm them up in a high-speed mode to cut rolling losses, soften them for rough roads. Same idea as a robot finger whose stiffness is set by air pressure (case: mechanical).
>
> **Next steps**: log Wh/km at 25, 30 and 35 km/h. If consumption grows roughly with the square of speed, air drag dominates and #8/#14 come first; if motor or controller temperature climbs, #35/#19 come first. Check the local speed limit.

Every number in the tables comes from `lookup.py` output in that run. The "case" is one of the industry cases the script returns for a principle (`principle --cases`); the answer uses it as an analogy, not as the idea itself.

## How it works

| Step | Done by |
| --- | --- |
| Understanding the problem, typing the contradiction, mapping to parameters or separation types, writing ideas | Claude |
| Parameter/principle validation, matrix and separation lookup, ranking | `skills/triz-analysis/scripts/lookup.py` |

`lookup.py` (Python 3.9+, standard library only, no network) prints JSON:

```
python3 skills/triz-analysis/scripts/lookup.py matrix --improve 9 --worsen 19,22
python3 skills/triz-analysis/scripts/lookup.py principle --id 35,15 --cases
python3 skills/triz-analysis/scripts/lookup.py param --search speed --lang en
python3 skills/triz-analysis/scripts/lookup.py separation --type time,space --lang en
python3 skills/triz-analysis/scripts/lookup.py validate
```

Errors are JSON on stderr with exit codes 2 (bad argument or unknown separation type), 3 (id out of range), 4 (same parameter), 5 (data error). An empty matrix cell is not an error; it is reported in `empty_pairs`.

The skill folder is self-contained (`data/` and `scripts/` live inside it), so it can also be uploaded on its own to Claude.ai.

## Data handling

- **What you type.** The problem you describe is handled by Claude in your session, like any other message, under your own Claude account terms. The plugin does not collect, store or forward it anywhere else.
- **What the script does.** `lookup.py` only reads the bundled `data/*.json` files and prints JSON to your terminal. It makes no network calls, reads no environment variables or credentials, and writes no files.
- **What the plugin does not have.** No hooks, no MCP servers, no background processes, no telemetry, and no accounts or API keys.
- **Files it writes.** Only when you ask for a saved report (`/triz ... --save`, or "save it"): one Markdown file in the current directory (or the path you give), never overwriting an existing file.
- **Personal data.** The plugin is not designed to read or keep personal data. Avoid putting personal or confidential information into the problem description; it is sent to Claude like any other prompt.

## What it does not cover

TRIZ is much broader than this plugin. It covers technical contradictions (contradiction matrix, 40 inventive principles) and physical contradictions (separation principles). It does **not** do:

- problem analysis before the contradiction is known: function analysis, trimming, root-cause and hidden-resource analysis
- the 76 standard solutions and substance-field analysis
- ARIZ, technology evolution laws, or functional-oriented search

The 40 principles are a checklist for generating ideas, not a guarantee. If the results feel off, the mapping or the problem definition usually needs another look before the principles do.

## Data status

| Data | Status |
| --- | --- |
| Contradiction matrix | all 1248 cells settled by a 2-of-3 vote of three independently transcribed sources (an English transcription family, the MATRIZ Knowledge Base, a Russian-language table). Nothing is withheld now; the `unverified_cell` warning remains for any future dispute. Not compared with a printed original (no printed copy was available). |
| 39 parameters, 40 principles | Numbers and names cross-checked; definitions, sub-principles and examples written for this project. 160 industry cases (four per principle, six domains) written for this project as analogies, with no company or product names; reviewed by AI only (two Claude passes; a second pass with a different model is pending), not by a native speaker or a domain expert. Report errors as GitHub issues |
| Separation principles | Five types and their related principles follow the MATRIZ TRIZ Knowledge Base (CC BY 4.0), taken from a published transcription and checked against the MATRIZ wiki page (all five lists match). Questions and examples written for this project. Literature disagrees on these lists, so treat them as one reputable reading, not the only one |
| Mapping accuracy | 32 blind-run cases: Top-3 hit rate 96-100% across runs (91/93 overall after the expected values were revised), 0 hallucinated principle numbers, and 9/9 disclosures when a withheld cell was hit. Small set with author-written expected values and some run-to-run variation, so treat it as a smoke test. **On an independent patent benchmark (TRIZBench) the plugin scored Hit@3 = 10% on the first 30 patents and 13% on 75 held-out patents, about the level of always guessing the three most common answers (9-16%)**: it works best when you state the trade-off yourself, not when the input only describes a solution (see `tests/eval/results-v0.1.md`). The technical cases still hit 30/32 after the v0.2 changes |
| Physical contradictions | 10 blind-run cases: the separation type looked up matched the expected one in 9/10 (command) and 8/10 (plain language) runs, 10/10 counting the type the answer states; 0 hallucinated principles. Author-written cases with clearly stated demands, so treat it as a smoke test (`tests/eval/results-v0.2.md`) |

The accuracy figures above are v0.2 measurements. They were not rerun for v0.3, which added industry cases that enter only after parameter mapping and carry no principle numbers; no change in idea quality is claimed.

Sources, method and the disputed cells are listed in [DATA_SOURCES.md](DATA_SOURCES.md). TRIZ output is a source of ideas, not a verdict: check the mapping and validate ideas before acting on them.

## Development

```
pip install pytest
pytest tests/
python skills/triz-analysis/scripts/lookup.py validate
claude plugin validate .
```

## License

Code (scripts, tests, manifests): [MIT](LICENSE). Text written for this project (parameter definitions, principle descriptions, examples): CC BY 4.0, see [LICENSE-DATA.md](LICENSE-DATA.md). Matrix cell values follow the classic Altshuller matrix and are credited in DATA_SOURCES.md.
