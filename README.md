# TRIZ Solver

[한국어](README.ko.md)

A Claude Code plugin that helps you resolve engineering and product trade-offs with **TRIZ**. It turns a problem into a contradiction and proposes ideas: a **technical contradiction** (improving one property worsens another) goes through the classic contradiction matrix and the 40 inventive principles; a **physical contradiction** (one property must be both high and low) goes through the separation principles.

No server, database or API key. Claude does the reasoning; every lookup is read from small JSON data files bundled with the plugin, so matrix cells, separation types and principle numbers are never recalled from memory. The plugin contains no scripts.

> **Status: v0.4 (pre-release).** The plugin now lives in the `plugin/` folder and has no scripts (see the [changelog](CHANGELOG.md)). Technical and physical contradictions, a guided interview for vague inputs, Markdown reports, and 160 industry cases (four per principle) used as analogies. See [Data status](#data-status) before relying on results.

## Install

```
/plugin marketplace add seogineer/triz-solver
/plugin install triz-solver@triz-solver
```

To try it from a local checkout: `claude --plugin-dir plugin`

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
3. Look up every candidate pair in the matrix (the skill reads `data/matrix/row-NN.json`)
4. Rank principles by how often they appear, following the step-by-step counting procedure in `SKILL.md`
5. Fetch each principle's definition and four industry cases (`data/principles/p-NN.json`)
6. Write ideas tailored to your system, one to three per principle

**Physical contradiction** ("X must be P for one reason and not-P for another"):

1. Restate it as one property with two opposite demands and their reasons
2. Check where, when, for whom, in which direction and at which level each demand holds (asking you one question at a time when the input does not say)
3. Pick the separation types where the demands do not overlap: space, time, relation (condition), direction or system level
4. Look up their related principles (`data/separation-principles.json`) and write ideas that implement the separation

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

This run is from v0.3.0, where a script did the lookups; from v0.4 the skill reads the same data from files. The "case" is one of the industry cases stored for a principle; the answer uses it as an analogy, not as the idea itself.

## How it works

| Step | Done by |
| --- | --- |
| Understanding the problem, typing the contradiction, mapping to parameters or separation types, writing ideas | Claude |
| Matrix, principle, parameter and separation lookup, ranking | The skill reads the `data/` files directly and counts by the procedure in `SKILL.md` |

The data is split into small JSON files under `plugin/skills/triz-analysis/data/`: `matrix/row-01.json` to `row-39.json` (one row per improving parameter), `principles/p-01.json` to `p-40.json`, `parameters.json` and `separation-principles.json`. The skill reads only the files it needs. If a file cannot be read, it tells you instead of filling in a value from memory.

## Data handling

- **What you type.** The problem you describe is handled by Claude in your session, like any other message, under your own Claude account terms. The plugin does not collect, store or forward it anywhere else.
- **What the plugin reads.** The bundled `data/*.json` files, with Claude's Read tool. The plugin contains no scripts and runs no commands, so it makes no network calls and reads no environment variables or credentials.
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
| 39 parameters, 40 principles | Numbers and names cross-checked; definitions, sub-principles and examples written for this project. 160 industry cases (four per principle, six domains) written for this project as analogies, with no company or product names; reviewed by AI only (two Claude passes and one Codex pass), not yet by a human, a native speaker or a domain expert. Report errors as GitHub issues |
| Separation principles | Five types and their related principles follow the MATRIZ TRIZ Knowledge Base (CC BY 4.0), taken from a published transcription and checked against the MATRIZ wiki page (all five lists match). Questions and examples written for this project. Literature disagrees on these lists, so treat them as one reputable reading, not the only one |
| Mapping accuracy | v0.4 blind run (32 cases, the skill reads the data files): Top-3 hit rate 32/32 in command mode and 31/32 in plain-language mode; the hand-counted ranking matched the `lookup.py` reference in 32/32 in both modes; 0 hallucinated principle numbers. Small set with author-written expected values and some run-to-run variation,, so treat it as a smoke test. **On an independent patent benchmark (TRIZBench) the plugin scored Hit@3 = 10% on the first 30 patents and 13% on 75 held-out patents, about the level of always guessing the three most common answers (9-16%)**: it works best when you state the trade-off yourself, not when the input only describes a solution (see `tests/eval/results-v0.1.md`). The TRIZBench figures are from v0.1 and were not rerun |
| Physical contradictions | v0.4 blind run (10 cases): the separation type matched the expected one in 9/10 (command) and 10/10 (plain language) runs; 0 hallucinated principles. Author-written cases with clearly stated demands, so treat it as a smoke test |

The v0.4 figures use the same evaluation cases and the same model as earlier releases, but the way of measuring changed (Bash `lookup.py` calls became file reads), so they are a new measurement, not a continuation of the v0.2 figures. They come from `tests/eval/blind-run-*-v04/results.json`, scored with `tests/eval/score.py`. Industry cases enter only after parameter mapping and carry no principle numbers; no change in idea quality is claimed.

Sources, method and the disputed cells are listed in [DATA_SOURCES.md](DATA_SOURCES.md). TRIZ output is a source of ideas, not a verdict: check the mapping and validate ideas before acting on them.

## Development

The plugin is the `plugin/` folder. `data/` at the repository root holds the source data; `tools/build_plugin_data.py` generates the split files in `plugin/`. `tools/lookup.py` is a development reference (oracle) for tests and evaluation; it is not part of the plugin.

```
pip install pytest
pytest tests/
python3 tools/lookup.py validate
python3 tools/lookup.py matrix --improve 9 --worsen 19,22
python3 tools/build_plugin_data.py --check
claude plugin validate plugin
claude --plugin-dir plugin
```

## License

Code (development tools, tests, manifests): [MIT](LICENSE). Text written for this project (parameter definitions, principle descriptions, examples): CC BY 4.0, see [LICENSE-DATA.md](LICENSE-DATA.md). Matrix cell values follow the classic Altshuller matrix and are credited in DATA_SOURCES.md.
