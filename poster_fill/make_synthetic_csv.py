"""Spec 08: build a SYNTHETIC expB-style CSV (plus a matching oracle-status json) to exercise make_poster_assets.py.
50 bases (from data/salbp_nl/*.truth.json) x 4 levels x 3 seeds x arms c, d, dprime, r.  Values are random (fixed seed) but legal;
they carry no information.  Run: .venv/bin/python -I poster_fill/make_synthetic_csv.py"""
import os, sys, csv, json, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
OUT = os.path.join(EXP, "results", "dryrun2")
# column list copied from run_expB.COLS by reading the file text (run_expB.py is frozen and not imported)
src = open(os.path.join(EXP, "run_expB.py"), encoding="utf-8").read()
i = src.index("COLS = [")
COLS = eval(src[i + 7: src.index("]", i) + 1])
rng = np.random.default_rng(8)
LEVELS = ["L1", "L2", "L3", "L4"]
bases = sorted({os.path.basename(p).rsplit("_L", 1)[0] for p in glob.glob(os.path.join(EXP, "data", "salbp_nl", "*.truth.json"))})
oracle, rows = {}, []
for b in bases:
    m = int(rng.integers(5, 25))
    mmax = m + int(rng.integers(0, 2))
    triv = int(rng.integers(0, 2))
    st = ["OPTIMAL", "OPTIMAL"] if rng.random() < 0.8 else ["OPTIMAL", "FEASIBLE"]
    oracle[b] = dict(m=m, m_min=m, m_max=mmax, unstable=int(mmax != m), status=st, lb=m - 1 + triv, time_s=[1.0, 1.0])
    for lv in LEVELS:
        rid = f"{b}_{lv}"
        for arm in ("c", "d", "dprime", "r"):
            for seed in (1, 2, 3):
                r = dict.fromkeys(COLS, "")
                r.update(arm=arm, id=rid, level=lv, seed=0 if arm == "r" else seed, rounds=1, finish_reason="stop", truth_m=m,
                         truth_m_min=m, truth_m_max=mmax, oracle_unstable=int(mmax != m), trivial_lb=triv,
                         diff_taskset=0, diff_time=0, diff_closure=0, diff_zone=0, solve_s=0.5, latency_s=1.0,
                         prompt_tokens=500, completion_tokens=300)
                u = rng.random()
                if arm == "r":
                    p_ok = 1.0
                elif arm == "c":
                    p_ok = 0.7
                else:
                    p_ok = {"L1": .85, "L2": .75, "L3": .65, "L4": .5}[lv] + (0.08 if arm == "d" else 0)
                if arm == "d":
                    r["rounds"] = int(rng.integers(1, 4))
                bad = u > p_ok
                if arm == "c":
                    if rng.random() < 0.05:
                        r.update(valid=0, feasible_on_truth=0, error="FAIL:APIConnectionError:boom", hit_le=0, hit_eq=0, hit_best=0)
                    elif bad:
                        r.update(valid=0, feasible_on_truth=0, error="c:assignment does not cover exactly tasks 1..n", hit_le=0, hit_eq=0, hit_best=0)
                    else:
                        s = m + int(rng.integers(0, 3))
                        r.update(valid=1, stations=s, feasible_on_truth=1, gap=round(100.0 * (s - m) / m, 4),
                                 hit_le=int(s <= m), hit_eq=int(s == m), hit_best=int(s <= m))
                    rows.append(r); continue
                v = rng.random()
                if v < 0.03 and arm != "r":
                    r.update(valid=0, equiv=0, feasible_on_truth=0, error="FAIL:APITimeoutError:timeout", hit_le=0, hit_eq=0, hit_best=0)
                elif bad and v < 0.5:
                    r.update(valid=0, equiv=0, feasible_on_truth=0, hit_le=0, hit_eq=0, hit_best=0,
                             error=str(rng.choice(["invalid:time of task 3 need int, got 333.0 in model", "invalid:precedence graph contains a cycle",
                                                   "invalid:ids not consecutive 1..n"])))
                    if rng.random() < 0.2:
                        r["finish_reason"] = "length"
                else:
                    r.update(valid=1, equiv=0 if bad else 1, solve_s=0.5)
                    if bad:
                        k = int(rng.integers(0, 4))
                        r[["diff_taskset", "diff_time", "diff_closure", "diff_zone"][k]] = 1
                        r["diff"] = json.dumps([f"synthetic_diff_{k}"])
                    s = m + (int(rng.integers(0, 3)) if bad else 0)
                    r.update(stations=s, feasible_on_truth=1, gap=round(100.0 * (s - m) / m, 4),
                             hit_le=int(s <= m), hit_eq=int(s == m), hit_best=int(s <= m))
                rows.append(r)
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, "synthetic_for_spec08.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, COLS); w.writeheader(); w.writerows(rows)
json.dump(oracle, open(os.path.join(OUT, "synthetic_truth_cpsat_w4_t60.json"), "w"), indent=1)
print("wrote", len(rows), "rows,", len(bases), "bases")
