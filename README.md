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

## Results

| Path | Content |
|---|---|
| `results/expB.csv` | Modelling arms `d`, `dprime`, `r`: 1,400 rows, no API failures after the re-run |
| `results/c_nothink/expB.csv` | Direct-assignment arm `c` (reasoning off): 600 rows |
| `results/truth_cpsat_w4_t60.json` | Oracle station counts (CP-SAT, 4 threads, 60 s, solved twice) |
| `results/expB_summary.md`, `results/c_nothink/expB_summary.md` | Output of the frozen summarizer (all 50 instances) |
| `results/timeouts_history/` | The result file before each re-run, with the failed rows still in it |
| `results/freeze_manifest_run_machine_70e5e78.json` | Manifest written on the run machine after the last runner change |

The poster reports the 46 instances with at most 100 tasks; the summarizer output covers all 50, so its headline figures are lower.

### How the run went

- Main run: 9 to 10 November 2026, 27.5 hours. 131 of 1,400 modelling rows ended in a client timeout (300 s); 109 of them were instances with more than 70 tasks.
- First re-run with a 1,200 s timeout: 11 of 13 rows lost the connection, because a non-streamed request sends no bytes while the model reasons.
- Second re-run with streaming and a 1,200 s timeout: all 127 remaining rows completed.
- So 131 rows were obtained with streaming and the longer timeout, the other 1,069 without. Prompt, model, temperature and token cap were the same.
- The poster submitted for review counts the 131 timeouts as failures (equivalence with feedback 58.7%, single pass 56.2%, paired difference +2.5 points, 95% CI −1.8 to 6.7). With the re-run rows the figures are 58.9%, 56.2% and +2.7 points (−1.6 to 6.9). The conclusions are the same.

### Read the numbers with these limits in mind

- The feedback arm may use up to three attempts of 32,000 tokens each; the single-pass arm gets one. Most extra attempts were triggered by truncated output and stayed truncated. The paired difference therefore mixes feedback with output budget.
- For three instances (barthol2, scholl, wee-mag) CP-SAT stopped at 60 s with a feasible, unproven solution. "Oracle" means the best station count found, not a proven optimum.
- Truncated outputs count as failures.
- "No more stations than the oracle" is a loose measure: most plans that pass it without an equivalent model have the right station count but miss a precedence relation.
- The template-aware parser scores 100% because it inverts the generator. It checks the test set, not a method.
- The endpoint accepts a seed but does not reproduce outputs. Three seeds are three samples.

## What is not here

- **The source data and the 200 sheets.** The precedence graphs and task times come from the Scholl and Otto et al. (2013) data sets at assembly-line-balancing.de. The site's legal notice (checked 11 November 2026) prohibits redistribution without written permission, so neither the raw files nor the sheets derived from them are in this repository. `docs/DATA_SOURCES.md` lists the URLs and hashes; the manifest lets you check a regenerated set.
- **The patched runner.** On the run machine `run_expB.py` gained three switches, each off by default: `--no-think` (reasoning off for arm `c`), `--timeout` and `--stream`. The runner in this repository is the earlier frozen version (`be44916`); the patched file will be added from the run machine.

## Run

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -I -m unittest discover -s tests
```

The runner reads `NVIDIA_API_KEY` and `NIM_MODEL` from the environment. Never put a key in a file.

## Scope

Sheets are template-generated. The benchmark measures how a model copes with changes in wording, order, units and references when the ground truth is exact. It says nothing about real shop-floor documents. Station rules are synthetic additions. One model, one zero-shot prompt and one hosted endpoint were used.

No licence has been chosen yet; all rights reserved until one is added.
