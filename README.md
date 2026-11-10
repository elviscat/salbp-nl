# SALBP-NL

Code for the GTC 2027 poster *LLM-Built Solver Models for Assembly Line Balancing, Validated on Public SALBP Benchmarks* (Elvis Hsin-Hui Wu, Joel Tso-Wei Chang, Ray Chen; Hon Hai Technology Group).

SALBP-NL is a test set of 200 generated process sheets: 50 SALBP-1 instances, each written in four wording conditions (L1 table, L2 prose, L3 shuffled with mixed units and redundant edges, L4 name-only references). Every sheet is generated from a known model, so a program can check whether a language model recovered that model.

## What is here

| Path | Content |
|---|---|
| `gen_nl.py`, `gen_nl_l4.py`, `strip_names.py`, `make_lexicon.py`, `nl_lexicon.json` | Sheet generator and the 139-name lexicon |
| `llm_modeler.py` | System prompt, JSON schema and the rule-based validator |
| `model_equiv.py` | Equivalence test (task set, times, transitive closure of precedence, station rules) |
| `rule_parser.py` | Template-aware parser used as an ablation (no LLM) |
| `run_expB.py`, `summarize_expB.py` | Experiment runner and the frozen summarizer |
| `solve_cpsat.py`, `solve_rpw.py`, `salbp_io.py` | CP-SAT model, ranked-positional-weight heuristic, instance reader |
| `poster_fill/` | Scripts that compute every number and figure on the poster from the result CSV |
| `tests/` | Unit tests |
| `results/freeze_manifest.json` | sha256 of the 200 sheets, their ground-truth files and the frozen code (commit `be44916` in the working repository) |
| `docs/analysis_plan_prereg_zh.md` | Analysis plan v1.0 to v1.4, in Chinese, including the deviations logged during the run |
| `docs/DATA_SOURCES.md` | URLs and sha256 of the source files |

## What is not here yet

- **The source data and the 200 sheets.** The precedence graphs and task times come from the Scholl (1993) and Otto et al. (2013) data sets at assembly-line-balancing.de. We have not confirmed their redistribution terms, so neither the raw files nor the sheets derived from them are in this repository. `docs/DATA_SOURCES.md` lists the URLs and hashes; the manifest lets you check a regenerated set. The sheets are available on request.
- **The `--no-think` switch.** After the smoke test the runner got one switch that turns reasoning off for the direct-assignment arm (commit `1a60d2f` on the run machine). The runner here is the earlier frozen version; the patched file will be added.
- **Result files.** They will be added when the re-run of the requests lost to API timeouts is complete.

## Run

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -I -m unittest discover -s tests
```

The runner reads `NVIDIA_API_KEY` and `NIM_MODEL` from the environment. Never put a key in a file.

## Scope

Sheets are template-generated. The benchmark measures how a model copes with changes in wording, order, units and references when the ground truth is exact. It says nothing about real shop-floor documents. Station rules are synthetic additions. One model, one zero-shot prompt and one hosted endpoint were used.

No licence has been chosen yet; all rights reserved until one is added.
