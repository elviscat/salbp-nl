"""Summarise results/expB.csv (or any --csv) -> expB_summary.md next to it.  Spec 04 version.
Unit of analysis = BASE instance. For each (arm, level, base) the seeds are averaged. Headline rates = mean of base scores;
95% CI = bootstrap over bases (10,000 resamples, seed 20261109). The 'all' row resamples bases as clusters (a base brings
its levels along), it is NOT a pooled row-level rate. hit_le = stations <= truth_m, hit_eq = stations == truth_m
(hit_best in the CSV == hit_le). A non-trivial subset (trivial_lb=0: ceil(sum T / c) != truth_m) is reported separately.
Paired differences (d - d', d - c) use the same base-cluster bootstrap: median and 95% percentile CI
(BCa needs scipy, which the venv does not have, so percentile is used everywhere). Layers with n > 100 get counts only.
Failures: truncated / parse / taskset_time / prec_zone (+ 'other' for API / solver / infeasible-assignment rows)."""
import os, sys, csv, json, math, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ARM_ORDER = ["c", "d", "dprime", "r"]
NL_DIR = os.environ.get("SALBP_NL_DIR", os.path.join(HERE, "data", "salbp_nl"))
LEVELS = ["L1", "L2", "L3", "L4"]
SEED = 20261109
B = 10000


def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, ctr - half), min(1.0, ctr + half))


def fmt_rate(k, n):
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({100 * k / n:.1f}%) [{100 * lo:.1f}, {100 * hi:.1f}]"


def med_p90(v):
    v = [float(x) for x in v if x != ""]
    return "n/a" if not v else f"{np.median(v):.1f} / {np.percentile(v, 90):.1f}"


def base_of(rid):
    return rid.rsplit("_L", 1)[0]


def n_of(rid, cache={}):
    if rid not in cache:
        cache[rid] = json.load(open(os.path.join(NL_DIR, rid + ".truth.json")))["_meta"]["n"]
    return cache[rid]


def g(x, k, default=""):
    v = x.get(k, default)
    return default if v is None else v


def cluster_boot(cells, B=B, seed=SEED):
    """cells: dict base -> list of numbers (one per level present). Resample bases with replacement; statistic = mean of all
    numbers in the resampled bases. Returns (point, median, lo, hi, n_bases)."""
    bases = [b for b in cells if cells[b]]
    if not bases:
        return None
    s = np.array([sum(cells[b]) for b in bases], float)
    k = np.array([len(cells[b]) for b in bases], float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(bases), size=(B, len(bases)))
    stat = s[idx].sum(axis=1) / k[idx].sum(axis=1)
    return s.sum() / k.sum(), float(np.median(stat)), float(np.percentile(stat, 2.5)), float(np.percentile(stat, 97.5)), len(bases)


def fmt_cb(cells):
    r = cluster_boot(cells)
    return "n/a" if r is None else f"{100 * r[0]:.1f}% [{100 * r[2]:.1f}, {100 * r[3]:.1f}] (B={r[4]})"


def base_scores(rows, arm):
    """rows of one arm -> {(level, base): dict of seed-mean scores}."""
    by = {}
    for x in rows:
        by.setdefault((x["level"], base_of(x["id"])), []).append(x)
    out = {}
    for key, xs in by.items():
        gap = [float(x["gap"]) for x in xs if x["gap"] != ""]
        hl = [int(g(x, "hit_le", g(x, "hit_best", 0)) or 0) for x in xs]
        he = [int(g(x, "hit_eq", 0) or 0) for x in xs]
        out[key] = dict(equiv=None if arm == "c" else float(np.mean([int(x["equiv"] or 0) for x in xs])),
                        feas=float(np.mean([int(x["feasible_on_truth"] or 0) for x in xs])),
                        hit_le=float(np.mean(hl)), hit_eq=float(np.mean(he)),
                        gap=float(np.mean(gap)) if gap else None,
                        trivial=int(g(xs[0], "trivial_lb", 0) or 0) if g(xs[0], "trivial_lb", "") != "" else None)
    return out


def cells_of(bs, metric, level=None, only=None):
    """-> dict base -> [values] for one level (or all levels). only: predicate on the score dict."""
    c = {}
    for (lv, b), v in bs.items():
        if (level is None or lv == level) and v[metric] is not None and (only is None or only(v)):
            c.setdefault(b, []).append(v[metric])
    return c


def paired_cells(bs1, bs2, metric, level=None):
    c = {}
    for key in bs1:
        if key in bs2 and (level is None or key[0] == level) and bs1[key][metric] is not None and bs2[key][metric] is not None:
            c.setdefault(key[1], []).append(bs1[key][metric] - bs2[key][metric])
    return c


def fail_kind(x, arm):
    err = g(x, "error", "")
    if g(x, "finish_reason", "") == "length":
        return "truncated"
    if "could not parse JSON" in err or err.startswith("c_parse") or err.startswith("invalid:"):
        return "parse"
    if int(g(x, "diff_taskset", 0) or 0) or int(g(x, "diff_time", 0) or 0):
        return "taskset_time"
    if int(g(x, "diff_closure", 0) or 0) or int(g(x, "diff_zone", 0) or 0):
        return "prec_zone"
    return "other"


def is_fail(x, arm):
    return int(x["feasible_on_truth"] or 0) == 0 if arm == "c" else int(x["equiv"] or 0) == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "results", "expB.csv"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(a.csv), "expB_summary.md" if a.csv.endswith("expB.csv") else "expB_dry_summary.md")
    rows = list(csv.DictReader(open(a.csv, newline="")))
    for x in rows:
        x["finish_reason"] = g(x, "finish_reason", "")
        x["error"] = g(x, "error", "")
    arms = [m for m in ARM_ORDER if any(x["arm"] == m for x in rows)]
    BS = {m: base_scores([x for x in rows if x["arm"] == m], m) for m in arms}
    L = ["# Experiment B summary", "",
         f"Source: `{os.path.relpath(a.csv, HERE)}`, {len(rows)} rows. Unit of analysis = base instance: seeds averaged per (arm, level, base); "
         f"headline rate = mean of base scores, 95% CI = bootstrap over bases ({B} resamples, seed {SEED}). The `all` row resamples bases as clusters "
         "(a base brings its levels along), not a pooled row-level rate. `row-level (reference)` = k/n over all rows with Wilson CI (rows within a base are correlated, CI too narrow). "
         "hit_le = stations <= truth_m; hit_eq = stations == truth_m (CSV column hit_best == hit_le). Arm r = rule parser, zero LLM, seed 0.",
         "gap = 100 x (stations - truth_m) / truth_m over rows feasible on the truth model, averaged per base first; mean [percentile CI over bases] (bases with a gap).", "",
         "## 1. Headline table", "",
         "| arm | level | rows | bases | equiv (d/d'/r) | feasible on truth | hit_le | hit_eq | gap mean % [CI] (bases) | row-level (reference): equiv / feasible | rounds mean | tokens in (med/p90) | tokens out (med/p90) | latency s (med/p90) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for arm in arms:
        for lv in LEVELS + ["all"]:
            r = [x for x in rows if x["arm"] == arm and (lv == "all" or x["level"] == lv)]
            if not r:
                continue
            lvl = None if lv == "all" else lv
            bs = BS[arm]
            eq = "n/a" if arm == "c" else fmt_cb(cells_of(bs, "equiv", lvl))
            gc = cells_of(bs, "gap", lvl)
            gr = cluster_boot(gc)
            gs = "n/a" if gr is None else f"{gr[0]:.2f} [{gr[2]:.2f}, {gr[3]:.2f}] ({gr[4]})"
            rl = ("n/a" if arm == "c" else fmt_rate(sum(int(x["equiv"] or 0) for x in r), len(r))) + " / " + fmt_rate(sum(int(x["feasible_on_truth"] or 0) for x in r), len(r))
            nb = len({base_of(x["id"]) for x in r})
            L.append(f"| {arm} | {lv} | {len(r)} | {nb} | {eq} | {fmt_cb(cells_of(bs, 'feas', lvl))} | {fmt_cb(cells_of(bs, 'hit_le', lvl))} | {fmt_cb(cells_of(bs, 'hit_eq', lvl))} | {gs} | {rl} | "
                     f"{np.mean([int(x['rounds'] or 0) for x in r]):.2f} | {med_p90([x['prompt_tokens'] for x in r])} | {med_p90([x['completion_tokens'] for x in r])} | {med_p90([x['latency_s'] for x in r])} |")
    # ---- non-trivial subset
    L += ["", "## 2. Non-trivial subset (trivial_lb = 0: the bound ceil(sum T / c) is below the oracle optimum)", "",
          "Trivial bases are those where a station count equal to ceil(sum T / c) is already optimal, so hitting truth_m needs no real search. Same base-cluster bootstrap.", "",
          "| arm | level | bases (non-trivial) | feasible on truth | hit_le | hit_eq |", "|---|---|---|---|---|---|"]
    triv = {}
    for arm in arms:
        for (lv, b), v in BS[arm].items():
            if v["trivial"] is not None:
                triv[b] = v["trivial"]
    L.insert(L.index("## 2. Non-trivial subset (trivial_lb = 0: the bound ceil(sum T / c) is below the oracle optimum)") + 2,
             f"Trivial bases in this CSV: {sum(1 for v in triv.values() if v == 1)} of {len(triv)} (trivial_lb = 1).")
    nt = lambda v: v["trivial"] == 0
    for arm in arms:
        for lv in LEVELS + ["all"]:
            lvl = None if lv == "all" else lv
            c = cells_of(BS[arm], "hit_le", lvl, nt)
            if not c:
                continue
            L.append(f"| {arm} | {lv} | {len(c)} | {fmt_cb(cells_of(BS[arm], 'feas', lvl, nt))} | {fmt_cb(c)} | {fmt_cb(cells_of(BS[arm], 'hit_eq', lvl, nt))} |")
    # ---- paired differences
    L += ["", "## 3. Paired differences over bases", "",
          f"Difference of base scores (seed-averaged) on the same base, {B} cluster resamples of bases (seed {SEED}); reported as median and 95% percentile CI. "
          "BCa would need scipy (not in the venv), so percentile is used even for proportions near 0 or 1: read those intervals as approximate. "
          "Positive = first arm higher.", "",
          "| contrast | metric | level | bases | point (pp) | bootstrap median (pp) | 95% CI (pp) |", "|---|---|---|---|---|---|---|"]
    contrasts = [("d - d'", "d", "dprime", ["equiv", "feas", "hit_le"]), ("d - c", "d", "c", ["feas", "hit_le"])]
    for name, a1, a2, metrics in contrasts:
        if a1 not in BS or a2 not in BS:
            continue
        for met in metrics:
            for lv in LEVELS + ["all"]:
                c = paired_cells(BS[a1], BS[a2], met, None if lv == "all" else lv)
                r = cluster_boot(c)
                if r:
                    L.append(f"| {name} | {met} | {lv} | {r[4]} | {100 * r[0]:+.1f} | {100 * r[1]:+.1f} | [{100 * r[2]:+.1f}, {100 * r[3]:+.1f}] |")
    # ---- size
    all_n = sorted({base_of(x["id"]): n_of(x["id"]) for x in rows}.items())
    nv = np.array([v for _, v in all_n], float)
    L += ["", "## 4. Size: n <= 100 (main result, with CI) vs n > 100 (counts only)", "",
          f"Base-instance size distribution (n operations, {len(nv)} bases in this CSV): min {nv.min():.0f}, p25 {np.percentile(nv, 25):.0f}, median {np.median(nv):.0f}, "
          f"p75 {np.percentile(nv, 75):.0f}, p90 {np.percentile(nv, 90):.0f}, max {nv.max():.0f}; n <= 100: {int((nv <= 100).sum())} bases, n > 100: {int((nv > 100).sum())} bases.", "",
          "For n > 100 only counts and the raw mean are listed (too few bases for an interval).", "",
          "| arm | level | stratum | bases | equiv (d/d'/r) | feasible on truth |", "|---|---|---|---|---|---|"]
    for arm in arms:
        for lv in LEVELS:
            for name, pred in (("n<=100", lambda n: n <= 100), ("n>100", lambda n: n > 100)):
                bs = {k: v for k, v in BS[arm].items() if k[0] == lv and pred(n_of(k[1] + "_" + lv))}
                if not bs:
                    continue
                if name == "n<=100":
                    eq = "n/a" if arm == "c" else fmt_cb(cells_of(bs, "equiv", lv))
                    fe = fmt_cb(cells_of(bs, "feas", lv))
                else:
                    ev = [v["equiv"] for v in bs.values() if v["equiv"] is not None]
                    eq = "n/a" if arm == "c" else f"{100 * np.mean(ev):.1f}% (no CI)"
                    fe = f"{100 * np.mean([v['feas'] for v in bs.values()]):.1f}% (no CI)"
                L.append(f"| {arm} | {lv} | {name} | {len(bs)} | {eq} | {fe} |")
    # ---- failures
    L += ["", "## 5. Failure classes (all layers, row counts)", "",
          "Failure = not equivalent (d, d', r) or not feasible on truth (c). Attribution order: truncated (finish_reason=length), parse (JSON failure / schema invalid), "
          "taskset_time (task set or times differ), prec_zone (precedence closure or same-station/incompatible sets differ), other (API failure, solver status, "
          "infeasible assignment for arm c; also the rare case where an equivalent-model flag is missing).", "",
          "| arm | level | failed rows / rows | truncated | parse | taskset_time | prec_zone | other |", "|---|---|---|---|---|---|---|---|"]
    for arm in arms:
        for lv in LEVELS:
            r = [x for x in rows if x["arm"] == arm and x["level"] == lv]
            if not r:
                continue
            bad = [x for x in r if is_fail(x, arm)]
            k = dict.fromkeys(["truncated", "parse", "taskset_time", "prec_zone", "other"], 0)
            for x in bad:
                k[fail_kind(x, arm)] += 1
            L.append(f"| {arm} | {lv} | {len(bad)}/{len(r)} | {k['truncated']} | {k['parse']} | {k['taskset_time']} | {k['prec_zone']} | {k['other']} |")
    # ---- oracle
    ob = {}
    for x in rows:
        if g(x, "oracle_unstable", "") != "":
            ob[base_of(x["id"])] = int(x["oracle_unstable"])
    if ob:
        L += ["", f"Oracle (CP-SAT, two seeds per base, same time and workers as the arms): unstable bases (two runs disagree on m) = {sum(ob.values())} of {len(ob)}."]
    fails = [x for x in rows if x["error"].startswith("FAIL")]
    L += ["", f"API failures (counted as not equivalent / not feasible): {len(fails)}"]
    errs = {}
    for x in rows:
        if x["error"]:
            k = x["error"].split(":")[0] + ":" + (x["error"].split(":")[1] if ":" in x["error"] else "")
            errs[k] = errs.get(k, 0) + 1
    if errs:
        L += ["", "Error kinds: " + ", ".join(f"{k} x{v}" for k, v in sorted(errs.items()))]
    open(out, "w").write("\n".join(L) + "\n")
    print("\n".join(L)); print("->", out)


if __name__ == "__main__":
    main()
