"""Post-run check of an expB.csv (Spec 10 item 1). Prints a report and writes run_check.md next to the CSV.
Read-only on the CSV. Last line: READY / READY_WITH_WARNINGS / NOT_READY.
Run: .venv/bin/python -I poster_fill/check_run.py --csv results/expB.csv [--levels L1,L2,L3,L4 --seeds 1,2,3 --arms c,d,dprime,r]"""
import os, sys, csv, glob, json, argparse, collections

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# header of run_expB.py (COLS); a shorter or longer header means the CSV was not written by this runner
N_COLS = 29
CRITICAL = ("arm", "id", "level", "seed", "valid", "feasible_on_truth", "hit_le", "rounds")


def pctile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--levels", default="L1,L2,L3,L4")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--arms", default="c,d,dprime,r")
    ap.add_argument("--nl-dir", default=os.path.join(HERE, "data", "salbp_nl"))
    ap.add_argument("--token-cap", type=float, default=16000, help="max_tokens cap per request; warn when per-request completion_tokens reach 15/16 of it")
    ap.add_argument("--out", default=None, help="where to write run_check.md (default: next to the CSV)")
    ap.add_argument("--oracle", default=None, help="oracle json (default truth_cpsat_w4_t60.json next to the CSV)")
    a = ap.parse_args()
    levels, seeds, arms = a.levels.split(","), a.seeds.split(","), a.arms.split(",")
    out, warn, fatal, notready = [], [], [], []
    P = out.append

    bases = sorted(os.path.basename(p)[:-len("_L1.truth.json")] for p in glob.glob(os.path.join(a.nl_dir, "*_L1.truth.json")))
    n_base = len(bases) or 50
    llm_arms = [x for x in arms if x != "r"]
    exp_rows = n_base * len(levels) * (len(llm_arms) * len(seeds) + (1 if "r" in arms else 0))
    P(f"# run_check: {a.csv}")
    P(f"base instances (from {a.nl_dir}): {n_base}; levels {levels}; arms {arms}; seeds {seeds}")

    with open(a.csv, newline="") as f:
        rd = csv.reader(f)
        header = next(rd, [])
        raw = list(rd)
    P(f"header columns: {len(header)} (runner writes {N_COLS})")
    if len(header) != N_COLS:
        notready.append(f"header has {len(header)} columns, expected {N_COLS}")
    rows, ragged, blank = [], [], []
    for i, r in enumerate(raw, 2):
        if len(r) != len(header):
            ragged.append((i, len(r)))
            continue
        d = dict(zip(header, r))
        rows.append(d)
        miss = [c for c in CRITICAL if c in d and d[c] == ""]
        if miss:
            blank.append((i, miss))
    P("")
    P("## 1. Row count")
    P(f"expected {exp_rows}; actual data lines {len(raw)}; well-formed {len(rows)}")
    # expected keys; the rule-parser arm has exactly one row per id (its seed is whatever the runner wrote, normally 0)
    have = collections.Counter()
    have_r = collections.Counter()
    for d in rows:
        if d["arm"] == "r":
            have_r[d["id"]] += 1
        have[(d["arm"], d["id"], d["seed"])] += 1
    missing = []
    for b in bases:
        for lv in levels:
            sid = f"{b}_{lv}"
            for arm in arms:
                if arm == "r":
                    if have_r[sid] == 0:
                        missing.append((arm, sid, "-"))
                else:
                    for s in seeds:
                        if have[(arm, sid, s)] == 0:
                            missing.append((arm, sid, s))
    P(f"missing (arm, id, seed): {len(missing)}")
    for m in missing[:20]:
        P(f"  {m}")
    if len(missing) > 20:
        P(f"  ... {len(missing) - 20} more")
    if missing:
        notready.append(f"{len(missing)} expected rows missing (run not finished)")
    dup = {k: v for k, v in have.items() if v > 1}
    dup_rows = sum(v - 1 for v in dup.values())
    P("")
    P("## 2. Duplicates and damaged rows")
    P(f"duplicate (arm, id, seed) keys: {len(dup)} keys, {dup_rows} surplus rows")
    for k in list(dup)[:5]:
        P(f"  {k} x{dup[k]}")
    if dup:
        warn.append(f"{dup_rows} duplicate rows (the analysis expects one row per (arm, id, seed))")
    P(f"rows with wrong column count (possible half-written line): {len(ragged)}")
    for r in ragged[:10]:
        P(f"  line {r[0]}: {r[1]} fields")
    if ragged:
        notready.append(f"{len(ragged)} rows with wrong field count")
    P(f"rows with blank key columns {CRITICAL}: {len(blank)}")
    for r in blank[:10]:
        P(f"  line {r[0]}: blank {r[1]}")
    if blank:
        notready.append(f"{len(blank)} rows with blank key columns")

    P("")
    P("## 3. API failures (error starts with FAIL:)")
    fails = [d for d in rows if d.get("error", "").startswith("FAIL:")]
    by = collections.Counter((d["arm"], d["error"].split(":")[1] if d["error"].count(":") >= 1 else "?") for d in fails)
    P(f"FAIL rows: {len(fails)} of {len(rows)} ({100 * len(fails) / max(len(rows), 1):.1f}%)")
    for (arm, ty), n in sorted(by.items()):
        P(f"  arm {arm:7s} {ty}: {n}")
    if rows and len(fails) > 0.05 * len(rows):
        warn.append(f"WARNING: FAIL rows are {100 * len(fails) / len(rows):.1f}% of all rows (> 5%)")
        P("WARNING: FAIL rows exceed 5% of all rows")
    badmodel = [d for d in rows if "nemotron-placeholder" in d.get("error", "")
                or (d.get("error", "").startswith("FAIL:") and ("model_not_found" in d["error"] or "404" in d["error"]))]
    if badmodel:
        msg = f"FATAL: NIM_MODEL 未設定或錯誤 ({len(badmodel)} rows, e.g. {badmodel[0]['error'][:100]})"
        P(msg)
        fatal.append(msg)

    P("")
    P("## 4. Output truncated (finish_reason == length)")
    tl = collections.Counter((d["arm"], d["level"]) for d in rows if d.get("finish_reason") == "length")
    P("none" if not tl else ", ".join(f"{k[0]}/{k[1]}: {v}" for k, v in sorted(tl.items())))

    P("")
    P("## 5. Rule-parser arm r")
    if "r" in arms:
        rr = [d for d in rows if d["arm"] == "r"]
        per = {lv: [d["equiv"] for d in rr if d["level"] == lv] for lv in levels}
        P("equiv=1 share per level: " + ", ".join(f"{lv} {sum(x == '1' for x in v)}/{len(v)}" for lv, v in per.items()))
        if not rr or any(len(v) == 0 or any(x != "1" for x in v) for v in per.values()):
            warn.append("arm r is not equiv=1 on every level (parser and instance bank disagree)")
            P("WARNING: arm r is not equiv=1 on all four levels")
    else:
        P("arm r not requested")

    P("")
    P("## 6. Latency and tokens per arm")
    mx_tok = 0
    for arm in arms:
        rr = [d for d in rows if d["arm"] == arm]
        lat = [v for v in (fnum(d["latency_s"]) for d in rr) if v is not None]
        # arm d / d': completion_tokens is summed over all rounds of the row; judge per request = value / rounds
        tok = []
        for d in rr:
            v = fnum(d["completion_tokens"])
            if v is None:
                continue
            nr = fnum(d.get("rounds")) or 0
            tok.append(v / nr if arm in ("d", "dprime") and nr >= 1 else v)
        if not rr:
            P(f"arm {arm}: no rows"); continue
        mx_tok = max(mx_tok, max(tok) if tok else 0)
        P(f"arm {arm}: latency_s median {pctile(lat, .5):.2f} p90 {pctile(lat, .9):.2f}; completion_tokens{' per request (row total / rounds)' if arm in ('d', 'dprime') else ''} median {pctile(tok, .5):.0f} max {max(tok):.0f}")
    thr = a.token_cap * 15 / 16
    if mx_tok >= thr:
        warn.append(f"per-request completion_tokens max {mx_tok:.0f} is close to the {a.token_cap:.0f} cap")
        P(f"WARNING: per-request completion_tokens max is close to {a.token_cap:.0f}")

    P("")
    P("## 7. Oracle cache")
    opath = a.oracle or os.path.join(os.path.dirname(os.path.abspath(a.csv)), "truth_cpsat_w4_t60.json")
    if os.path.exists(opath):
        orc = json.load(open(opath))
        both = sum(1 for v in orc.values() if len(v.get("status", [])) >= 2 and all(s == "OPTIMAL" for s in v["status"]))
        unst = sum(int(v.get("unstable", 0) or 0) for v in orc.values())
        P(f"{opath}: {len(orc)} base instances (expected {n_base}); both runs OPTIMAL: {both}; unstable: {unst}")
        if len(orc) != n_base:
            warn.append(f"oracle file has {len(orc)} bases, expected {n_base}")
        if unst:
            warn.append(f"{unst} oracle bases are unstable (two CP-SAT runs disagree)")
    else:
        P(f"{opath}: NOT FOUND")
        notready.append("oracle cache truth_cpsat_w4_t60.json not found")

    P("")
    if fatal:
        verdict = "NOT_READY"
        reasons = fatal + notready + warn
    elif notready:
        verdict, reasons = "NOT_READY", notready + warn
    elif warn:
        verdict, reasons = "READY_WITH_WARNINGS", warn
    else:
        verdict, reasons = "READY", []
    P("## Verdict")
    for r in reasons:
        P(f"- {r}")
    P(f"{verdict}" + (": " + "; ".join(reasons) if reasons else ""))
    text = "\n".join(out) + "\n"
    print(text, end="")
    open(a.out or os.path.join(os.path.dirname(os.path.abspath(a.csv)), "run_check.md"), "w", encoding="utf-8").write(text)


if __name__ == "__main__":
    main()
