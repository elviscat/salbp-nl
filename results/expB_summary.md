# Experiment B summary

Source: `results/expB.csv`, 1400 rows. Unit of analysis = base instance: seeds averaged per (arm, level, base); headline rate = mean of base scores, 95% CI = bootstrap over bases (10000 resamples, seed 20261109). The `all` row resamples bases as clusters (a base brings its levels along), not a pooled row-level rate. `row-level (reference)` = k/n over all rows with Wilson CI (rows within a base are correlated, CI too narrow). hit_le = stations <= truth_m; hit_eq = stations == truth_m (CSV column hit_best == hit_le). Arm r = rule parser, zero LLM, seed 0.
gap = 100 x (stations - truth_m) / truth_m over rows feasible on the truth model, averaged per base first; mean [percentile CI over bases] (bases with a gap).

## 1. Headline table

| arm | level | rows | bases | equiv (d/d'/r) | feasible on truth | hit_le | hit_eq | gap mean % [CI] (bases) | row-level (reference): equiv / feasible | rounds mean | tokens in (med/p90) | tokens out (med/p90) | latency s (med/p90) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d | L1 | 150 | 50 | 62.7% [51.3, 73.3] (B=50) | 73.3% [62.7, 83.3] (B=50) | 72.7% [62.0, 82.7] (B=50) | 72.7% [62.0, 82.7] (B=50) | 0.06 [0.00, 0.18] (42) | 94/150 (62.7%) [54.7, 70.0] / 110/150 (73.3%) [65.7, 79.8] | 1.11 | 782.5 / 2351.2 | 8773.0 / 22772.9 | 123.1 / 577.7 |
| d | L2 | 150 | 50 | 66.7% [55.3, 77.3] (B=50) | 78.0% [68.0, 87.3] (B=50) | 77.3% [67.3, 86.7] (B=50) | 77.3% [67.3, 86.7] (B=50) | 0.22 [0.00, 0.67] (45) | 100/150 (66.7%) [58.8, 73.7] / 117/150 (78.0%) [70.7, 83.9] | 1.06 | 1001.5 / 3614.4 | 7362.0 / 21940.7 | 107.7 / 381.0 |
| d | L3 | 150 | 50 | 58.0% [47.3, 68.7] (B=50) | 70.7% [59.3, 81.3] (B=50) | 70.7% [59.3, 81.3] (B=50) | 70.7% [59.3, 81.3] (B=50) | 0.00 [0.00, 0.00] (40) | 87/150 (58.0%) [50.0, 65.6] / 106/150 (70.7%) [62.9, 77.4] | 1.23 | 1065.0 / 10818.0 | 10926.5 / 57306.1 | 169.3 / 1012.8 |
| d | L4 | 150 | 50 | 30.0% [20.0, 40.7] (B=50) | 48.7% [37.3, 60.0] (B=50) | 48.7% [37.3, 60.0] (B=50) | 48.7% [37.3, 60.0] (B=50) | 0.00 [0.00, 0.00] (33) | 45/150 (30.0%) [23.2, 37.8] / 73/150 (48.7%) [40.8, 56.6] | 1.37 | 1347.0 / 15868.5 | 14236.5 / 96000.0 | 213.5 / 1110.9 |
| d | all | 600 | 50 | 54.3% [46.0, 62.8] (B=50) | 67.7% [58.7, 76.0] (B=50) | 67.3% [58.3, 75.8] (B=50) | 67.3% [58.3, 75.8] (B=50) | 0.08 [0.00, 0.23] (48) | 326/600 (54.3%) [50.3, 58.3] / 406/600 (67.7%) [63.8, 71.3] | 1.19 | 1072.0 / 7427.4 | 10449.0 / 49674.0 | 155.7 / 860.4 |
| dprime | L1 | 150 | 50 | 67.3% [56.7, 78.0] (B=50) | 74.7% [64.0, 84.7] (B=50) | 74.7% [64.0, 84.7] (B=50) | 74.7% [64.0, 84.7] (B=50) | 0.00 [0.00, 0.00] (41) | 101/150 (67.3%) [59.5, 74.3] / 112/150 (74.7%) [67.2, 81.0] | 1.00 | 782.5 / 2351.2 | 8789.0 / 23548.4 | 130.6 / 495.4 |
| dprime | L2 | 150 | 50 | 63.3% [52.7, 74.0] (B=50) | 72.0% [62.0, 82.0] (B=50) | 70.7% [60.0, 80.7] (B=50) | 70.7% [60.0, 80.7] (B=50) | 0.49 [0.00, 1.24] (43) | 95/150 (63.3%) [55.4, 70.6] / 108/150 (72.0%) [64.3, 78.6] | 1.00 | 1001.5 / 3614.4 | 6984.5 / 23394.9 | 108.1 / 416.9 |
| dprime | L3 | 150 | 50 | 50.7% [38.7, 62.7] (B=50) | 65.3% [54.0, 76.7] (B=50) | 64.7% [53.3, 76.0] (B=50) | 64.7% [53.3, 76.0] (B=50) | 0.18 [0.00, 0.55] (39) | 76/150 (50.7%) [42.7, 58.6] / 98/150 (65.3%) [57.4, 72.5] | 1.00 | 1065.0 / 3751.8 | 11168.5 / 32000.0 | 177.8 / 427.2 |
| dprime | L4 | 150 | 50 | 25.3% [17.3, 34.7] (B=50) | 38.0% [28.7, 48.7] (B=50) | 38.0% [28.7, 48.7] (B=50) | 38.0% [28.7, 48.7] (B=50) | 0.00 [0.00, 0.00] (32) | 38/150 (25.3%) [19.0, 32.8] / 57/150 (38.0%) [30.6, 46.0] | 1.00 | 1337.0 / 4707.5 | 13525.5 / 32000.0 | 231.9 / 513.5 |
| dprime | all | 600 | 50 | 51.7% [43.3, 59.8] (B=50) | 62.5% [53.7, 71.0] (B=50) | 62.0% [53.2, 70.5] (B=50) | 62.0% [53.2, 70.5] (B=50) | 0.18 [0.00, 0.42] (47) | 310/600 (51.7%) [47.7, 55.6] / 375/600 (62.5%) [58.6, 66.3] | 1.00 | 1072.0 / 3724.2 | 10205.5 / 32000.0 | 149.3 / 479.1 |
| r | L1 | 50 | 50 | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 0.00 [0.00, 0.00] (50) | 50/50 (100.0%) [92.9, 100.0] / 50/50 (100.0%) [92.9, 100.0] | 0.00 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| r | L2 | 50 | 50 | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 98.0% [94.0, 100.0] (B=50) | -0.05 [-0.15, 0.00] (50) | 50/50 (100.0%) [92.9, 100.0] / 50/50 (100.0%) [92.9, 100.0] | 0.00 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| r | L3 | 50 | 50 | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 0.00 [0.00, 0.00] (50) | 50/50 (100.0%) [92.9, 100.0] / 50/50 (100.0%) [92.9, 100.0] | 0.00 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| r | L4 | 50 | 50 | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 0.00 [0.00, 0.00] (50) | 50/50 (100.0%) [92.9, 100.0] / 50/50 (100.0%) [92.9, 100.0] | 0.00 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| r | all | 200 | 50 | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 100.0% [100.0, 100.0] (B=50) | 99.5% [98.5, 100.0] (B=50) | -0.01 [-0.04, 0.00] (50) | 200/200 (100.0%) [98.1, 100.0] / 200/200 (100.0%) [98.1, 100.0] | 0.00 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |

## 2. Non-trivial subset (trivial_lb = 0: the bound ceil(sum T / c) is below the oracle optimum)

Trivial bases in this CSV: 28 of 50 (trivial_lb = 1).
Trivial bases are those where a station count equal to ceil(sum T / c) is already optimal, so hitting truth_m needs no real search. Same base-cluster bootstrap.

| arm | level | bases (non-trivial) | feasible on truth | hit_le | hit_eq |
|---|---|---|---|---|---|
| d | L1 | 22 | 60.6% [42.4, 78.8] (B=22) | 59.1% [40.9, 75.8] (B=22) | 59.1% [40.9, 75.8] (B=22) |
| d | L2 | 22 | 66.7% [48.5, 83.3] (B=22) | 66.7% [48.5, 83.3] (B=22) | 66.7% [48.5, 83.3] (B=22) |
| d | L3 | 22 | 51.5% [34.8, 69.7] (B=22) | 51.5% [34.8, 69.7] (B=22) | 51.5% [34.8, 69.7] (B=22) |
| d | L4 | 22 | 33.3% [18.2, 50.0] (B=22) | 33.3% [18.2, 50.0] (B=22) | 33.3% [18.2, 50.0] (B=22) |
| d | all | 22 | 53.0% [39.0, 66.7] (B=22) | 52.7% [38.6, 65.9] (B=22) | 52.7% [38.6, 65.9] (B=22) |
| dprime | L1 | 22 | 65.2% [48.5, 81.8] (B=22) | 65.2% [48.5, 81.8] (B=22) | 65.2% [48.5, 81.8] (B=22) |
| dprime | L2 | 22 | 60.6% [42.4, 77.3] (B=22) | 60.6% [42.4, 77.3] (B=22) | 60.6% [42.4, 77.3] (B=22) |
| dprime | L3 | 22 | 42.4% [24.2, 60.6] (B=22) | 42.4% [24.2, 60.6] (B=22) | 42.4% [24.2, 60.6] (B=22) |
| dprime | L4 | 22 | 19.7% [10.6, 30.3] (B=22) | 19.7% [10.6, 30.3] (B=22) | 19.7% [10.6, 30.3] (B=22) |
| dprime | all | 22 | 47.0% [34.8, 58.7] (B=22) | 47.0% [34.8, 58.7] (B=22) | 47.0% [34.8, 58.7] (B=22) |
| r | L1 | 22 | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) |
| r | L2 | 22 | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) | 95.5% [86.4, 100.0] (B=22) |
| r | L3 | 22 | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) |
| r | L4 | 22 | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) |
| r | all | 22 | 100.0% [100.0, 100.0] (B=22) | 100.0% [100.0, 100.0] (B=22) | 98.9% [96.6, 100.0] (B=22) |

## 3. Paired differences over bases

Difference of base scores (seed-averaged) on the same base, 10000 cluster resamples of bases (seed 20261109); reported as median and 95% percentile CI. BCa would need scipy (not in the venv), so percentile is used even for proportions near 0 or 1: read those intervals as approximate. Positive = first arm higher.

| contrast | metric | level | bases | point (pp) | bootstrap median (pp) | 95% CI (pp) |
|---|---|---|---|---|---|---|
| d - d' | equiv | L1 | 50 | -4.7 | -4.7 | [-11.3, +2.0] |
| d - d' | equiv | L2 | 50 | +3.3 | +3.3 | [-5.3, +11.3] |
| d - d' | equiv | L3 | 50 | +7.3 | +7.3 | [-0.7, +16.0] |
| d - d' | equiv | L4 | 50 | +4.7 | +4.7 | [-4.0, +14.0] |
| d - d' | equiv | all | 50 | +2.7 | +2.7 | [-1.3, +6.7] |
| d - d' | feas | L1 | 50 | -1.3 | -1.3 | [-8.7, +6.0] |
| d - d' | feas | L2 | 50 | +6.0 | +6.0 | [+0.0, +12.7] |
| d - d' | feas | L3 | 50 | +5.3 | +5.3 | [-1.3, +12.7] |
| d - d' | feas | L4 | 50 | +10.7 | +10.7 | [+1.3, +20.0] |
| d - d' | feas | all | 50 | +5.2 | +5.2 | [+1.8, +8.7] |
| d - d' | hit_le | L1 | 50 | -2.0 | -2.0 | [-9.3, +5.3] |
| d - d' | hit_le | L2 | 50 | +6.7 | +6.7 | [+0.0, +13.3] |
| d - d' | hit_le | L3 | 50 | +6.0 | +6.0 | [-0.0, +12.7] |
| d - d' | hit_le | L4 | 50 | +10.7 | +10.7 | [+1.3, +20.0] |
| d - d' | hit_le | all | 50 | +5.3 | +5.3 | [+2.0, +8.8] |

## 4. Size: n <= 100 (main result, with CI) vs n > 100 (counts only)

Base-instance size distribution (n operations, 50 bases in this CSV): min 7, p25 20, median 20, p75 42, p90 90, max 297; n <= 100: 46 bases, n > 100: 4 bases.

For n > 100 only counts and the raw mean are listed (too few bases for an interval).

| arm | level | stratum | bases | equiv (d/d'/r) | feasible on truth |
|---|---|---|---|---|---|
| d | L1 | n<=100 | 46 | 68.1% [57.2, 78.3] (B=46) | 79.7% [69.6, 88.4] (B=46) |
| d | L1 | n>100 | 4 | 0.0% (no CI) | 0.0% (no CI) |
| d | L2 | n<=100 | 46 | 71.7% [60.9, 81.9] (B=46) | 83.3% [73.9, 91.3] (B=46) |
| d | L2 | n>100 | 4 | 8.3% (no CI) | 16.7% (no CI) |
| d | L3 | n<=100 | 46 | 63.0% [52.9, 73.2] (B=46) | 76.8% [65.9, 87.0] (B=46) |
| d | L3 | n>100 | 4 | 0.0% (no CI) | 0.0% (no CI) |
| d | L4 | n<=100 | 46 | 32.6% [21.7, 44.2] (B=46) | 52.9% [41.3, 64.5] (B=46) |
| d | L4 | n>100 | 4 | 0.0% (no CI) | 0.0% (no CI) |
| dprime | L1 | n<=100 | 46 | 73.2% [62.3, 82.6] (B=46) | 81.2% [71.0, 89.9] (B=46) |
| dprime | L1 | n>100 | 4 | 0.0% (no CI) | 0.0% (no CI) |
| dprime | L2 | n<=100 | 46 | 68.8% [58.0, 79.0] (B=46) | 76.8% [66.7, 85.5] (B=46) |
| dprime | L2 | n>100 | 4 | 0.0% (no CI) | 16.7% (no CI) |
| dprime | L3 | n<=100 | 46 | 55.1% [42.8, 66.7] (B=46) | 71.0% [59.4, 81.9] (B=46) |
| dprime | L3 | n>100 | 4 | 0.0% (no CI) | 0.0% (no CI) |
| dprime | L4 | n<=100 | 46 | 27.5% [18.8, 37.0] (B=46) | 41.3% [31.2, 52.2] (B=46) |
| dprime | L4 | n>100 | 4 | 0.0% (no CI) | 0.0% (no CI) |
| r | L1 | n<=100 | 46 | 100.0% [100.0, 100.0] (B=46) | 100.0% [100.0, 100.0] (B=46) |
| r | L1 | n>100 | 4 | 100.0% (no CI) | 100.0% (no CI) |
| r | L2 | n<=100 | 46 | 100.0% [100.0, 100.0] (B=46) | 100.0% [100.0, 100.0] (B=46) |
| r | L2 | n>100 | 4 | 100.0% (no CI) | 100.0% (no CI) |
| r | L3 | n<=100 | 46 | 100.0% [100.0, 100.0] (B=46) | 100.0% [100.0, 100.0] (B=46) |
| r | L3 | n>100 | 4 | 100.0% (no CI) | 100.0% (no CI) |
| r | L4 | n<=100 | 46 | 100.0% [100.0, 100.0] (B=46) | 100.0% [100.0, 100.0] (B=46) |
| r | L4 | n>100 | 4 | 100.0% (no CI) | 100.0% (no CI) |

## 5. Failure classes (all layers, row counts)

Failure = not equivalent (d, d', r) or not feasible on truth (c). Attribution order: truncated (finish_reason=length), parse (JSON failure / schema invalid), taskset_time (task set or times differ), prec_zone (precedence closure or same-station/incompatible sets differ), other (API failure, solver status, infeasible assignment for arm c; also the rare case where an equivalent-model flag is missing).

| arm | level | failed rows / rows | truncated | parse | taskset_time | prec_zone | other |
|---|---|---|---|---|---|---|---|
| d | L1 | 56/150 | 9 | 0 | 5 | 42 | 0 |
| d | L2 | 50/150 | 6 | 0 | 18 | 26 | 0 |
| d | L3 | 63/150 | 17 | 0 | 5 | 41 | 0 |
| d | L4 | 105/150 | 27 | 1 | 3 | 74 | 0 |
| dprime | L1 | 49/150 | 9 | 1 | 6 | 33 | 0 |
| dprime | L2 | 55/150 | 7 | 1 | 15 | 32 | 0 |
| dprime | L3 | 74/150 | 19 | 3 | 5 | 47 | 0 |
| dprime | L4 | 112/150 | 26 | 10 | 7 | 69 | 0 |
| r | L1 | 0/50 | 0 | 0 | 0 | 0 | 0 |
| r | L2 | 0/50 | 0 | 0 | 0 | 0 | 0 |
| r | L3 | 0/50 | 0 | 0 | 0 | 0 | 0 |
| r | L4 | 0/50 | 0 | 0 | 0 | 0 | 0 |

Oracle (CP-SAT, two seeds per base, same time and workers as the arms): unstable bases (two runs disagree on m) = 0 of 50.

API failures (counted as not equivalent / not feasible): 0

Error kinds: invalid:could not parse JSON x99, invalid:precedence x2, invalid:precedence graph contains a cycle x10, solver:EXC x8, solver:INFEASIBLE x47, truth_infeasible:incompatible 10,19 share a station x13, truth_infeasible:incompatible 11,27 share a station x6, truth_infeasible:incompatible 17,19 share a station x4, truth_infeasible:incompatible 18,21 share a station x1, truth_infeasible:incompatible 2,21 share a station x7, truth_infeasible:incompatible 3,7 share a station x1, truth_infeasible:incompatible 69,72 share a station x1, truth_infeasible:incompatible 8,11 share a station x3, truth_infeasible:precedence 1->2 violated (stations 11>1) x1, truth_infeasible:precedence 1->2 violated (stations 2>1) x1, truth_infeasible:precedence 1->2 violated (stations 4>1) x1, truth_infeasible:precedence 1->2 violated (stations 5>3) x4, truth_infeasible:precedence 1->2 violated (stations 9>6) x1, truth_infeasible:precedence 1->3 violated (stations 13>10) x1, truth_infeasible:precedence 1->3 violated (stations 2>1) x1, truth_infeasible:precedence 1->4 violated (stations 4>3) x1, truth_infeasible:precedence 1->5 violated (stations 10>9) x1, truth_infeasible:precedence 1->5 violated (stations 11>8) x1, truth_infeasible:precedence 1->5 violated (stations 6>3) x1, truth_infeasible:precedence 1->5 violated (stations 9>5) x1, truth_infeasible:precedence 1->6 violated (stations 3>1) x1, truth_infeasible:precedence 1->7 violated (stations 3>2) x1, truth_infeasible:precedence 1->8 violated (stations 3>1) x1, truth_infeasible:precedence 1->8 violated (stations 3>2) x2, truth_infeasible:precedence 10->11 violated (stations 3>1) x2, truth_infeasible:precedence 10->12 violated (stations 6>3) x1, truth_infeasible:precedence 10->13 violated (stations 3>2) x1, truth_infeasible:precedence 10->14 violated (stations 4>3) x1, truth_infeasible:precedence 11->12 violated (stations 8>1) x2, truth_infeasible:precedence 11->15 violated (stations 4>2) x1, truth_infeasible:precedence 11->15 violated (stations 6>4) x1, truth_infeasible:precedence 12->15 violated (stations 6>4) x1, truth_infeasible:precedence 12->16 violated (stations 6>5) x2, truth_infeasible:precedence 12->18 violated (stations 7>3) x1, truth_infeasible:precedence 13->14 violated (stations 6>3) x1, truth_infeasible:precedence 13->15 violated (stations 11>10) x1, truth_infeasible:precedence 13->15 violated (stations 3>2) x1, truth_infeasible:precedence 13->15 violated (stations 4>2) x1, truth_infeasible:precedence 13->17 violated (stations 8>6) x1, truth_infeasible:precedence 13->23 violated (stations 9>3) x1, truth_infeasible:precedence 14->17 violated (stations 8>7) x1, truth_infeasible:precedence 14->18 violated (stations 6>4) x1, truth_infeasible:precedence 14->19 violated (stations 14>2) x1, truth_infeasible:precedence 14->25 violated (stations 3>1) x1, truth_infeasible:precedence 14->25 violated (stations 4>3) x1, truth_infeasible:precedence 141->142 violated (stations 7>6) x1, truth_infeasible:precedence 15->17 violated (stations 8>7) x1, truth_infeasible:precedence 15->19 violated (stations 5>4) x1, truth_infeasible:precedence 15->39 violated (stations 8>4) x1, truth_infeasible:precedence 16->18 violated (stations 3>2) x1, truth_infeasible:precedence 16->19 violated (stations 8>6) x1, truth_infeasible:precedence 16->75 violated (stations 4>1) x1, truth_infeasible:precedence 17->18 violated (stations 4>1) x1, truth_infeasible:precedence 17->18 violated (stations 9>6) x1, truth_infeasible:precedence 17->19 violated (stations 10>2) x1, truth_infeasible:precedence 17->19 violated (stations 14>8) x1, truth_infeasible:precedence 17->19 violated (stations 5>4) x1, truth_infeasible:precedence 18->19 violated (stations 4>2) x1, truth_infeasible:precedence 19->22 violated (stations 3>2) x2, truth_infeasible:precedence 2->3 violated (stations 10>9) x2, truth_infeasible:precedence 2->3 violated (stations 14>2) x1, truth_infeasible:precedence 2->3 violated (stations 3>1) x1, truth_infeasible:precedence 2->4 violated (stations 4>2) x1, truth_infeasible:precedence 2->5 violated (stations 5>1) x2, truth_infeasible:precedence 2->7 violated (stations 3>1) x1, truth_infeasible:precedence 20->21 violated (stations 6>4) x1, truth_infeasible:precedence 21->22 violated (stations 7>5) x1, truth_infeasible:precedence 21->44 violated (stations 13>11) x1, truth_infeasible:precedence 22->23 violated (stations 10>8) x1, truth_infeasible:precedence 23->32 violated (stations 15>4) x2, truth_infeasible:precedence 23->32 violated (stations 17>4) x1, truth_infeasible:precedence 25->26 violated (stations 9>8) x1, truth_infeasible:precedence 25->27 violated (stations 10>7) x1, truth_infeasible:precedence 25->29 violated (stations 29>2) x1, truth_infeasible:precedence 25->29 violated (stations 32>1) x1, truth_infeasible:precedence 25->29 violated (stations 33>2) x1, truth_infeasible:precedence 26->27 violated (stations 3>1) x1, truth_infeasible:precedence 27->28 violated (stations 8>7) x1, truth_infeasible:precedence 27->33 violated (stations 9>8) x1, truth_infeasible:precedence 27->35 violated (stations 14>10) x1, truth_infeasible:precedence 28->32 violated (stations 10>2) x1, truth_infeasible:precedence 29->35 violated (stations 14>10) x1, truth_infeasible:precedence 3->16 violated (stations 7>1) x1, truth_infeasible:precedence 3->22 violated (stations 14>9) x1, truth_infeasible:precedence 3->4 violated (stations 16>15) x1, truth_infeasible:precedence 3->4 violated (stations 6>4) x1, truth_infeasible:precedence 3->5 violated (stations 12>5) x1, truth_infeasible:precedence 3->5 violated (stations 8>6) x1, truth_infeasible:precedence 3->6 violated (stations 2>1) x1, truth_infeasible:precedence 3->7 violated (stations 2>1) x1, truth_infeasible:precedence 30->31 violated (stations 8>3) x1, truth_infeasible:precedence 33->41 violated (stations 50>48) x1, truth_infeasible:precedence 33->41 violated (stations 58>16) x1, truth_infeasible:precedence 35->40 violated (stations 6>5) x1, truth_infeasible:precedence 35->42 violated (stations 31>4) x1, truth_infeasible:precedence 37->38 violated (stations 8>1) x1, truth_infeasible:precedence 37->39 violated (stations 4>2) x4, truth_infeasible:precedence 39->40 violated (stations 19>5) x1, truth_infeasible:precedence 4->10 violated (stations 3>1) x1, truth_infeasible:precedence 4->11 violated (stations 7>6) x1, truth_infeasible:precedence 4->16 violated (stations 22>11) x1, truth_infeasible:precedence 4->5 violated (stations 3>2) x1, truth_infeasible:precedence 4->5 violated (stations 5>1) x2, truth_infeasible:precedence 4->6 violated (stations 10>2) x1, truth_infeasible:precedence 4->6 violated (stations 2>1) x2, truth_infeasible:precedence 4->6 violated (stations 5>2) x1, truth_infeasible:precedence 4->7 violated (stations 2>1) x1, truth_infeasible:precedence 4->7 violated (stations 5>2) x1, truth_infeasible:precedence 42->44 violated (stations 6>3) x1, truth_infeasible:precedence 43->50 violated (stations 30>18) x1, truth_infeasible:precedence 45->46 violated (stations 8>2) x1, truth_infeasible:precedence 47->54 violated (stations 6>3) x1, truth_infeasible:precedence 47->54 violated (stations 9>4) x1, truth_infeasible:precedence 48->50 violated (stations 14>3) x1, truth_infeasible:precedence 48->75 violated (stations 16>14) x1, truth_infeasible:precedence 49->59 violated (stations 23>16) x1, truth_infeasible:precedence 5->10 violated (stations 4>2) x1, truth_infeasible:precedence 5->11 violated (stations 4>3) x1, truth_infeasible:precedence 5->6 violated (stations 5>4) x1, truth_infeasible:precedence 5->7 violated (stations 3>1) x1, truth_infeasible:precedence 5->7 violated (stations 7>4) x1, truth_infeasible:precedence 5->8 violated (stations 4>3) x1, truth_infeasible:precedence 5->8 violated (stations 5>2) x1, truth_infeasible:precedence 5->8 violated (stations 5>3) x2, truth_infeasible:precedence 5->8 violated (stations 6>1) x1, truth_infeasible:precedence 52->53 violated (stations 25>19) x1, truth_infeasible:precedence 52->53 violated (stations 9>5) x1, truth_infeasible:precedence 54->56 violated (stations 21>14) x1, truth_infeasible:precedence 56->57 violated (stations 17>14) x1, truth_infeasible:precedence 57->66 violated (stations 21>20) x1, truth_infeasible:precedence 6->10 violated (stations 5>4) x1, truth_infeasible:precedence 6->10 violated (stations 6>4) x1, truth_infeasible:precedence 6->11 violated (stations 9>2) x1, truth_infeasible:precedence 6->14 violated (stations 4>1) x1, truth_infeasible:precedence 6->16 violated (stations 3>2) x2, truth_infeasible:precedence 6->8 violated (stations 10>2) x1, truth_infeasible:precedence 6->8 violated (stations 13>3) x1, truth_infeasible:precedence 6->8 violated (stations 5>3) x2, truth_infeasible:precedence 6->8 violated (stations 6>1) x1, truth_infeasible:precedence 63->77 violated (stations 19>8) x1, truth_infeasible:precedence 68->72 violated (stations 31>25) x1, truth_infeasible:precedence 7->10 violated (stations 3>2) x2, truth_infeasible:precedence 7->10 violated (stations 5>1) x1, truth_infeasible:precedence 7->10 violated (stations 5>4) x2, truth_infeasible:precedence 7->11 violated (stations 5>2) x1, truth_infeasible:precedence 7->12 violated (stations 3>2) x2, truth_infeasible:precedence 7->12 violated (stations 5>1) x4, truth_infeasible:precedence 7->12 violated (stations 9>6) x1, truth_infeasible:precedence 7->15 violated (stations 8>5) x1, truth_infeasible:precedence 7->18 violated (stations 3>2) x1, truth_infeasible:precedence 7->8 violated (stations 7>3) x1, truth_infeasible:precedence 7->9 violated (stations 3>1) x2, truth_infeasible:precedence 7->9 violated (stations 4>3) x1, truth_infeasible:precedence 71->73 violated (stations 16>8) x1, truth_infeasible:precedence 8->10 violated (stations 3>2) x2, truth_infeasible:precedence 8->10 violated (stations 9>6) x1, truth_infeasible:precedence 8->11 violated (stations 3>1) x1, truth_infeasible:precedence 8->18 violated (stations 13>5) x1, truth_infeasible:precedence 8->18 violated (stations 9>5) x1, truth_infeasible:precedence 8->44 violated (stations 15>13) x1, truth_infeasible:precedence 8->44 violated (stations 21>12) x1, truth_infeasible:precedence 8->71 violated (stations 20>16) x1, truth_infeasible:precedence 8->9 violated (stations 6>1) x1, truth_infeasible:precedence 8->9 violated (stations 6>5) x1, truth_infeasible:precedence 87->88 violated (stations 17>5) x1, truth_infeasible:precedence 89->105 violated (stations 16>15) x1, truth_infeasible:precedence 9->10 violated (stations 8>3) x1, truth_infeasible:precedence 9->11 violated (stations 19>3) x1, truth_infeasible:precedence 9->13 violated (stations 2>1) x1, truth_infeasible:precedence 9->26 violated (stations 10>5) x1, truth_infeasible:same-station 10,13 violated x1, truth_infeasible:same-station 12,29 violated x1, truth_infeasible:station 1 load 1278 exceeds cycle time 1000 x2, truth_infeasible:station 1 load 1919 exceeds cycle time 1883 x1, truth_infeasible:station 1 load 30 exceeds cycle time 8 x1, truth_infeasible:station 10 load 17 exceeds cycle time 16 x1, truth_infeasible:station 12 load 6043 exceeds cycle time 5853 x4, truth_infeasible:station 12 load 6201 exceeds cycle time 5853 x1, truth_infeasible:station 14 load 235 exceeds cycle time 234 x1, truth_infeasible:station 15 load 10256 exceeds cycle time 7916 x1, truth_infeasible:station 18 load 10297 exceeds cycle time 7916 x1, truth_infeasible:station 18 load 17 exceeds cycle time 16 x1, truth_infeasible:station 2 load 11392 exceeds cycle time 7916 x1, truth_infeasible:station 2 load 2829 exceeds cycle time 2806 x1, truth_infeasible:station 23 load 2043 exceeds cycle time 1883 x1, truth_infeasible:station 27 load 19 exceeds cycle time 16 x1, truth_infeasible:station 28 load 123 exceeds cycle time 112 x1, truth_infeasible:station 3 load 54 exceeds cycle time 36 x1, truth_infeasible:station 6 load 100 exceeds cycle time 92 x1, truth_infeasible:station 6 load 266 exceeds cycle time 251 x1, truth_infeasible:station 9 load 153 exceeds cycle time 112 x1, truth_infeasible:station 9 load 565 exceeds cycle time 564 x1, truth_infeasible:task count differs from truth x2
