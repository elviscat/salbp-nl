"""Poster asset generator (Spec 07). Reads an expB CSV, writes numbers.json, fig2_equivalence.svg, fig3_failures.svg,
results_table.md, results_table.html. Every number comes from the CSV via summarize_expB.py functions (imported, not rewritten):
base_scores, cells_of, paired_cells, cluster_boot (10,000 base-cluster resamples, seed 20261109), fail_kind, is_fail, n_of.
No estimated value is built in.  Run: .venv/bin/python -I poster_fill/make_poster_assets.py --csv X --out-dir D"""
import os, sys, csv, re, json, hashlib, argparse, datetime
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, EXP)          # -I mode does not add the script dir / cwd; summarize_expB lives in exp/
import summarize_expB as S      # main() sits under __main__, import has no side effects

LEVELS = S.LEVELS
PREREG = os.path.join(EXP, "..", "prereg.md")
FONT = "Inter, -apple-system, 'Helvetica Neue', Arial, sans-serif"
C_D, C_DP, C_R = "#1F4E79", "#8FB3D9", "#9A9A9A"
FAIL_KINDS = ["truncated", "parse", "taskset_time", "prec_zone"]
FAIL_COL = {"truncated": "#1F4E79", "parse": "#8FB3D9", "taskset_time": "#C9892B", "prec_zone": "#7A7A7A"}
FAIL_LABEL = {"truncated": "truncated", "parse": "JSON invalid", "taskset_time": "tasks or times", "prec_zone": "closure or zones"}


def ci_pct(cells):
    r = S.cluster_boot(cells)
    if r is None:
        return None
    return dict(value=100 * r[0], ci=[100 * r[2], 100 * r[3]], n_bases=r[4])


def rate(cells):
    """a bootstrap summary in percent, or None."""
    return ci_pct(cells)


def read_prereg():
    """H lines copied verbatim from prereg.md -> {key: text}."""
    out = {}
    if not os.path.exists(PREREG):
        return out
    for ln in open(PREREG, encoding="utf-8"):
        m = re.match(r"^- (H\d(?: 補充（[^）]*）)?)（([^）]*)）：(.*)$", ln.strip())
        if m:
            out[m.group(1)] = ln.strip()[2:].replace("**", "")
        elif ln.startswith("- **H5**"):
            out["H5"] = ln.strip()[2:].replace("**", "")
        elif ln.startswith("- **零 LLM 基線**"):
            out["parser"] = ln.strip()[2:].replace("**", "")
        elif ln.startswith("- H3 補充"):
            out["H3s"] = ln.strip()[2:]
    txt = open(PREREG, encoding="utf-8").read() if os.path.exists(PREREG) else ""
    i = txt.find("## v1.3 補記")
    for ln in (txt[i:].splitlines() if i >= 0 else []):
        m = re.match(r"^- \*\*([^*]+)\*\*：", ln.strip())
        if m:
            out["v13:" + m.group(1)] = ln.strip()[2:].replace("**", "")
    return out


def fmt(x, d=1):
    return "n/a" if x is None else f"{x:.{d}f}"


def fmtci(d, n=1):
    return "n/a" if d is None or d.get("value") is None else f"{d['value']:.{n}f}% [{d['ci'][0]:.{n}f}, {d['ci'][1]:.{n}f}]"


def cb(cells):
    r = ci_pct(cells)
    return r or dict(value=None, ci=None, n_bases=0)


def is_api_fail(x):
    e = (x.get("error") or "")
    return e.startswith("FAIL:")


def secondary(rows, rs, BS, small, base_n, arms, args):
    """Spec 08 keys. rs = rows of n<=100 bases; BS = per-arm base scores restricted to n<=100."""
    N = {}
    A = lambda a: [x for x in rs if x["arm"] == a]
    # 1 H1 components
    comp = {}
    dp, dd = A("dprime"), {(x["id"], x["seed"]): x for x in A("d")}
    if dp:
        c = {}
        for x in dp:
            c.setdefault(S.base_of(x["id"]), []).append(1 if int(x["valid"] or 0) == 0 else 0)
        comp["dprime_invalid_rate"] = dict(cb(c), n_rows=len(dp), source="row-level: arm dprime, n<=100 rows, valid==0 share (percent); base-cluster CI; fills [V] (100 - this)")
        c, k = {}, 0
        for x in dp:
            if int(x["valid"] or 0) == 0 and (x["id"], x["seed"]) in dd:
                c.setdefault(S.base_of(x["id"]), []).append(int(dd[(x["id"], x["seed"])]["equiv"] or 0)); k += 1
        comp["repair_success_rate"] = dict(cb(c), n_rows=k, source="rows with dprime valid==0 and an arm-d row at the same (id, seed); success = d equiv==1 (percent)")
        c, k = {}, 0
        for x in dp:
            if int(x["valid"] or 0) == 1 and (x["id"], x["seed"]) in dd:
                c.setdefault(S.base_of(x["id"]), []).append(1 if int(dd[(x["id"], x["seed"])]["rounds"] or 0) == 1 else 0); k += 1
        comp["same_seed_consistency"] = dict(cb(c), n_rows=k, source="rows with dprime valid==1 and an arm-d row at the same (id, seed); consistent = d rounds==1 (percent)")
        byid = {}
        for x in dp:
            byid.setdefault(x["id"], []).append(int(x["valid"] or 0))
        c = {}
        for i, v in byid.items():
            c.setdefault(S.base_of(i), []).append(1 if any(v) else 0)
        comp["no_feedback_resample"] = dict(cb(c), n_sheets=len(byid), source="per sheet id: any dprime seed with valid==1 (percent); base-cluster CI")
    N["h1_components"] = dict(value=comp, source="Spec 08 item 1; arms d and dprime, n<=100; each entry {value, ci, n_bases, n_rows} in percent")
    # 2 hit_le vs truth_m_max
    if "d" in BS:
        per = {}
        for x in A("d"):
            ok = int(x["feasible_on_truth"] or 0) == 1 and x["stations"] != "" and x["truth_m_max"] != "" and float(x["stations"]) <= float(x["truth_m_max"])
            per.setdefault((x["level"], S.base_of(x["id"])), []).append(1 if ok else 0)
        c = {}
        for (lv, b), v in per.items():
            c.setdefault(b, []).append(float(np.mean(v)))
        N["hit_le_vs_truth_m_max"] = dict(cb(c), source="arm d, n<=100: stations <= truth_m_max and feasible_on_truth==1, seeds averaged per (level, base), S.cluster_boot (percent); compare hit_le_d")
    else:
        N["hit_le_vs_truth_m_max"] = dict(value=None, ci=None, source="arm d missing")
    # 3 oracle statuses
    opath = args.oracle_json or os.path.join(os.path.dirname(os.path.abspath(args.csv)), "truth_cpsat_w4_t60.json")
    if os.path.exists(opath):
        orc = json.load(open(opath, encoding="utf-8"))
        have = sorted(b for b in small if b in orc)
        both = [b for b in have if len(orc[b].get("status", [])) >= 2 and all(s == "OPTIMAL" for s in orc[b]["status"])]
        N["oracle_both_optimal"] = dict(value=len(both), bases=both, n_bases_with_status=len(have), n_bases_le100=len(small),
                                        source=f"status lists in {os.path.basename(opath)}; both runs OPTIMAL; n<=100 bases present in the file")
        N["oracle_not_proven_optimal_count"] = dict(value=len(have) - len(both), source="n<=100 bases in the oracle file minus both-OPTIMAL")
        bs = set(both)
        if "d" in BS:
            N["hit_le_d_both_optimal"] = dict(cb(S.cells_of({k: v for k, v in BS["d"].items() if k[1] in bs}, "hit_le")),
                                              source="arm d hit_le restricted to both-OPTIMAL bases, S.cluster_boot (percent)")
        else:
            N["hit_le_d_both_optimal"] = dict(value=None, ci=None, source="arm d missing")
    else:
        for k in ("oracle_both_optimal", "oracle_not_proven_optimal_count", "hit_le_d_both_optimal"):
            N[k] = dict(value=None, ci=None, source=f"null: {opath} not found")
    # 4 API failures
    af = {}
    for a in ("d", "dprime"):
        if a in BS:
            af[a] = dict(rows_le100=sum(1 for x in A(a) if is_api_fail(x)),
                         rows_all=sum(1 for x in rows if x["arm"] == a and is_api_fail(x)), n_rows_le100=len(A(a)))
    N["api_failures"] = dict(value=af, source="rows whose error starts with 'FAIL:' (run_expB.py wraps any exception, incl. API errors after 3 retries, as 'FAIL:<Type>:<msg>') (coordinator ruling: 'FAIL:' prefix only); arms d and dprime")
    bad = {S.base_of(x["id"]) for x in rs if x["arm"] in ("d", "dprime") and is_api_fail(x)}
    if "d" in BS and "dprime" in BS:
        r = S.cluster_boot(S.paired_cells({k: v for k, v in BS["d"].items() if k[1] not in bad},
                                          {k: v for k, v in BS["dprime"].items() if k[1] not in bad}, "equiv"))
        N["paired_d_minus_dprime_excl_api"] = (dict(value=100 * r[1], point=100 * r[0], ci=[100 * r[2], 100 * r[3]], n_bases=r[4], n_bases_excluded=len(bad),
                                                    source="paired d - dprime equivalence (pp) after dropping bases where d or dprime has an API-failure row")
                                               if r else dict(value=None, ci=None, n_bases_excluded=len(bad), source="no bases left"))
    else:
        N["paired_d_minus_dprime_excl_api"] = dict(value=None, ci=None, source="arm d or dprime missing")
    # 5 by size / source
    sz = lambda n: "n<=20" if n <= 20 else ("21-50" if n <= 50 else "51-100")
    src = lambda b: "Otto" if b.startswith("otto") else ("Scholl" if b.startswith("scholl") else "other")
    def stratify(fn, names):
        out = {}
        for nm in names:
            bs = {b for b in small if fn(b) == nm}
            out[nm] = {}
            for a in ("d", "dprime", "r"):
                if a in BS:
                    out[nm][a] = dict(cb(S.cells_of({k: v for k, v in BS[a].items() if k[1] in bs}, "equiv")), n_instances=len({k[1] for k in BS[a] if k[1] in bs}))
        return out
    N["by_size"] = dict(value=stratify(lambda b: sz(base_n[b]), ["n<=20", "21-50", "51-100"]), source="equivalence (percent, L1-L4 pooled) by base size; S.cluster_boot; n from truth.json _meta")
    N["by_source"] = dict(value=stratify(src, ["Otto", "Scholl"]), source="equivalence (percent, L1-L4 pooled) by base id prefix (otto / scholl); S.cluster_boot")
    # 6 diff flags by level
    fl = {}
    for lv in LEVELS:
        ne = [x for x in A("d") if x["level"] == lv and int(x["equiv"] or 0) == 0]
        fl[lv] = dict(n_nonequiv_rows=len(ne), **{col: (100 * sum(1 for x in ne if int(S.g(x, col, 0) or 0) == 1) / len(ne) if ne else None)
                                                  for col in ("diff_taskset", "diff_time", "diff_closure", "diff_zone")})
    N["diff_flags_by_level"] = dict(value=fl, source="arm d, n<=100, rows with equiv==0; percent with each diff_* flag ==1 (not mutually exclusive)")
    # 7 invalid reasons
    ir = {}
    for a in arms:
        g_ = {}
        for x in A(a):
            if x["error"].startswith("invalid:"):
                g_[x["error"][:30]] = g_.get(x["error"][:30], 0) + 1
        if g_:
            tot = sum(g_.values())
            ir[a] = dict(total=tot, groups=dict(sorted(g_.items(), key=lambda kv: -kv[1])), need_int_count=sum(v for k, v in g_.items() if "need int" in k),
                         need_int_share_pct=100 * sum(v for k, v in g_.items() if "need int" in k) / tot)
    N["invalid_reasons"] = dict(value=ir, source="rows (n<=100) with error starting 'invalid:', grouped by the first 30 characters of the error; need_int = group text contains 'need int' (truncated at 30 chars)")
    # 8 trivial_lb subset
    tl = {}
    dbases = {S.base_of(x["id"]) for x in rs if x["arm"] == "d"}
    for x in rs:
        if x["trivial_lb"] != "" and S.base_of(x["id"]) in dbases:
            tl[S.base_of(x["id"])] = int(x["trivial_lb"])
    N["trivial_lb_subset"] = dict(value=dict(k_nontrivial_of_N=f"{sum(1 for v in tl.values() if v == 0)}/{len(dbases)}", k=sum(1 for v in tl.values() if v == 0),
                                             N=len(dbases), n_bases_with_flag=len(tl)),
                                  source="bases with trivial_lb==0 among n<=100 bases that have arm-d data (denominator = their number; all n<=100 bases once the run is complete)")
    # 9 non-equivalent examples
    ex = [dict(id=x["id"], level=x["level"], seed=x["seed"], diff=x["diff"], diff_taskset=x["diff_taskset"], diff_time=x["diff_time"],
               diff_closure=x["diff_closure"], diff_zone=x["diff_zone"]) for x in A("d") if int(x["equiv"] or 0) == 0 and int(x["valid"] or 0) == 1][:5]
    N["nonequiv_examples"] = dict(value=ex, source="first 5 arm-d rows (CSV order, n<=100) with equiv==0 and valid==1; diff text as in CSV")
    # table support: H2 and H5
    if "d" in BS and "c" in BS:
        r = S.cluster_boot(S.paired_cells(BS["d"], BS["c"], "hit_le"))
        N["h2_d_minus_c_hit_le"] = dict(value=100 * r[1], point=100 * r[0], ci=[100 * r[2], 100 * r[3]], n_bases=r[4],
                                        source="paired d - c hit_le (pp), n<=100, S.paired_cells + S.cluster_boot") if r else dict(value=None, ci=None, source="no pairs")
    else:
        N["h2_d_minus_c_hit_le"] = dict(value=None, ci=None, source="arm d or c missing")
    if "d" in BS:
        c = {}
        for (lv, b), v in BS["d"].items():
            if lv == "L4" and (("L3", b) in BS["d"]):
                c.setdefault(b, []).append(v["equiv"] - BS["d"][("L3", b)]["equiv"])
        r = S.cluster_boot(c)
        N["h5_l4_minus_l3"] = dict(value=100 * r[1], point=100 * r[0], ci=[100 * r[2], 100 * r[3]], n_bases=r[4],
                                   source="paired L4 - L3 equivalence of arm d (pp), n<=100, base-cluster bootstrap") if r else dict(value=None, ci=None, source="no pairs")
    else:
        N["h5_l4_minus_l3"] = dict(value=None, ci=None, source="arm d missing")
    # all six paired level differences of arm d (pp), for the Takeaway 3 selection rule (situation library section 0)
    lp = {}
    if "d" in BS:
        for i1, l1 in enumerate(LEVELS):
            for l2 in LEVELS[i1 + 1:]:
                c = {}
                for (lv, b), v in BS["d"].items():
                    if lv == l1 and (l2, b) in BS["d"]:
                        c.setdefault(b, []).append(v["equiv"] - BS["d"][(l2, b)]["equiv"])
                r = S.cluster_boot(c)
                lp[f"{l1}-{l2}"] = (dict(point=100 * r[0], median=100 * r[1], ci=[100 * r[2], 100 * r[3]], n_bases=r[4]) if r else None)
    N["equiv_level_pairs"] = dict(value=lp, source="arm d, n<=100: paired (earlier level) - (later level) equivalence in pp per base, base-cluster bootstrap; point = mean, median = bootstrap median, ci = percentile interval")
    # R3 additions
    N_uncond = lambda a: cb(S.cells_of(BS[a], 'equiv'))
    cond = {}
    for a in ("d", "dprime"):
        if a in BS:
            c, k = {}, 0
            for x in A(a):
                if int(x["valid"] or 0) == 1:
                    c.setdefault(S.base_of(x["id"]), []).append(int(x["equiv"] or 0)); k += 1
            cond[a] = dict(cb(c), n_valid_rows=k, unconditional=N_uncond(a))
    N["conditional_equiv_rate"] = dict(value=cond, source="arms d and dprime, n<=100: share of valid==1 rows with equiv==1 (percent, row-weighted, base-cluster CI); 'unconditional' = the L1-L4 pooled equivalence rate for comparison")
    pats = ("4, 5", "[4,5]", "(4, 5)", "2, 9", "[2,9]", "(2, 9)")
    sus = [x for x in rs if x["arm"] in ("d", "dprime") and int(S.g(x, "diff_zone", 0) or 0) == 1 and any(t in x["diff"] for t in pats)]
    N["example_copy_suspects"] = dict(value=dict(count=len(sus), by_arm={a: sum(1 for x in sus if x["arm"] == a) for a in ("d", "dprime")},
                                                 first5=[dict(arm=x["arm"], id=x["id"], seed=x["seed"], diff=x["diff"]) for x in sus[:5]]),
                                      source="arms d, dprime, n<=100 rows with diff_zone==1 whose diff text contains any of: 4, 5 / [4,5] / (4, 5) / 2, 9 / [2,9] / (2, 9) (SCHEMA_TEXT example same_station [[4,5]], incompatible [[2,9]]); possible example copying, not proof")
    fr = {}
    for x in rows:
        if x["error"].startswith("FAIL:"):
            t = "FAIL:" + x["error"].split(":")[1]
            fr.setdefault(x["arm"], {})
            fr[x["arm"]][t] = fr[x["arm"]].get(t, 0) + 1
    N["fail_rows_by_type"] = dict(value=fr, source="all rows (all n) with error starting 'FAIL:', counted by 'FAIL:<ExceptionType>' per arm")
    tb = {a: {lv: sum(1 for x in rows if x["arm"] == a and x["level"] == lv and x["finish_reason"] == "length") for lv in LEVELS} for a in arms}
    N["truncated_by_level_arm"] = dict(value=tb, source="all rows (all n) with finish_reason=='length', per arm and level")
    return N


def v5_keys(rows, rs, small):
    """Spec 11 keys. Unit conventions are written into each 'source' string."""
    N = {}
    llm = [x for x in rows if x["arm"] in ("c", "d", "dprime")]
    n_req = sum(1 for x in llm if x["arm"] != "d") + sum(int(x["rounds"] or 0) for x in llm if x["arm"] == "d")
    N["n_requests"] = dict(value=n_req, source="rows of arms c and dprime (one request each) plus the sum of 'rounds' over arm d rows; all n; arm r makes no request")
    # per-request statistics. Arm d rows cover several repair rounds, so latency and tokens are divided by the row's rounds.
    # Rows with rounds == 0 (error FAIL:..., no completed request, recorded as 0) are left out, for d' as well.
    ok = [x for x in llm if int(x["rounds"] or 0) >= 1 and not x["error"].startswith("FAIL:")]
    div = lambda x: int(x["rounds"]) if x["arm"] == "d" else 1
    lat = [float(x["latency_s"]) / div(x) for x in ok if x["latency_s"] != ""]
    tok = [float(x["completion_tokens"]) / div(x) for x in ok if x["completion_tokens"] != ""]
    per_req = ("per request: arm d row value / that row's rounds (rounds >= 1); arms c and d' row value; rows with rounds == 0 or error FAIL:... excluded; "
               f"{len(ok)} rows, all n")
    N["run_latency_median_s"] = dict(value=float(np.median(lat)) if lat else None, source="column latency_s, " + per_req + "; median")
    N["run_latency_p90_s"] = dict(value=float(np.percentile(lat, 90)) if lat else None, source="column latency_s, " + per_req + "; 90th percentile (numpy linear interpolation)")
    N["run_tokens_median"] = dict(value=float(np.median(tok)) if tok else None, source="column completion_tokens, " + per_req + "; median")
    N["run_tokens_max"] = dict(value=float(np.max(tok)) if tok else None, source="column completion_tokens, " + per_req + "; maximum")
    d_ok = [x for x in rows if x["arm"] == "d" and int(x["rounds"] or 0) >= 1 and not x["error"].startswith("FAIL:")]
    N["rounds_mean_d_all"] = dict(value=float(np.mean([int(x["rounds"]) for x in d_ok])) if d_ok else None,
                                  source=f"column rounds, arm d rows with rounds >= 1 and no FAIL: error ({len(d_ok)} rows), all n; mean")
    # sheet-level counts (unit = sheet id, n <= 100; a sheet counts if at least one of its seeds meets the condition)
    dr = [x for x in rs if x["arm"] == "d"]
    dpr = [x for x in rs if x["arm"] == "dprime"]
    sheets = sorted({x["id"] for x in dr})
    lvl = lambda i: i.rsplit("_", 1)[-1]
    fl = {c: set() for c in ("diff_taskset", "diff_time", "diff_closure", "diff_zone")}
    ne, trunc, parse, api = set(), set(), set(), set()
    for x in dr:
        if int(x["equiv"] or 0) == 0:
            ne.add(x["id"])
            for c in fl:
                if int(S.g(x, c, 0) or 0) == 1:
                    fl[c].add(x["id"])
            k = S.fail_kind(x, "d")
            if k == "truncated": trunc.add(x["id"])
            elif k == "parse": parse.add(x["id"])
        if is_api_fail(x):
            api.add(x["id"])
    per = {lv: dict(k_ne=len([i for i in ne if lvl(i) == lv]), **{c: len([i for i in fl[c] if lvl(i) == lv]) for c in fl}) for lv in LEVELS}
    inv = {x["id"] for x in dpr if int(x["valid"] or 0) == 0}
    dv = {}
    for x in dr:
        dv[(x["id"], x["seed"])] = int(x["valid"] or 0)
    rep_ = {i for i in inv if all(dv.get((x["id"], x["seed"]), 0) == 1 for x in dpr if x["id"] == i and int(x["valid"] or 0) == 0)}
    N["sheet_counts"] = dict(value=dict(n_sheets=len(sheets), k_ne=len(ne), k_inv=len(inv), m_rep=len(rep_),
                                        f1=len(fl["diff_taskset"]), f2=len(fl["diff_time"]), f3=len(fl["diff_closure"]), f4=len(fl["diff_zone"]),
                                        t=len(trunc), p=len(parse), api=len(api), per_level=per),
                             source=("unit = sheet id (n<=100); a sheet counts if at least one seed meets the condition. k_ne: arm d, any seed equiv==0; f1..f4: any non-equivalent d seed with diff_taskset/time/closure/zone==1 "
                                     "(not exclusive); t, p: any non-equivalent d seed whose S.fail_kind is truncated / parse; api: any d seed with error starting 'FAIL:'; "
                                     "k_inv: arm dprime, any seed valid==0; m_rep: those sheets where arm d is valid at every seed where dprime was invalid (same id, same seed). Seed handling is Fable's call to confirm."))
    n_le = len({x["id"] for x in rs if x["arm"] == "d"})   # sheets with arm-d data (= all n<=100 sheets once the run is complete)
    N["invalid_sheet_rate"] = dict(value=(100 * len(inv) / n_le if n_le else None), n_sheets=n_le, k_inv=len(inv),
                                   source="sheet-level: 100 * k_inv / n_sheets_with_data (n<=100 sheets with arm-d data; any dprime seed valid==0 counts); same population as [k_inv]; fills [I]. The row-level rate stays in h1_components.dprime_invalid_rate")
    N["repair_sheet_rate"] = dict(value=(100 * len(rep_) / len(inv) if inv else None), m_rep=len(rep_), k_inv=len(inv),
                                  source="sheet-level: 100 * m_rep / k_inv; fills [P]. The row-level rate stays in h1_components.repair_success_rate")
    return N


def build(rows, args):
    for x in rows:
        x["finish_reason"] = S.g(x, "finish_reason", "")
        x["error"] = S.g(x, "error", "")
    arms = [m for m in S.ARM_ORDER if any(x["arm"] == m for x in rows)]
    base_n = {S.base_of(x["id"]): S.n_of(x["id"]) for x in rows}
    small = {b for b, n in base_n.items() if n <= 100}
    big = sorted(b for b, n in base_n.items() if n > 100)
    BS_all = {m: S.base_scores([x for x in rows if x["arm"] == m], m) for m in arms}
    BS = {m: {k: v for k, v in bs.items() if k[1] in small} for m, bs in BS_all.items()}
    rs = [x for x in rows if S.base_of(x["id"]) in small]           # rows of n <= 100 bases
    N = {}
    sheets = {x["id"] for x in rows}
    sheets_le = {x["id"] for x in rs}
    N["n_sheets"] = dict(value=len(sheets), source="distinct id in CSV")
    N["n_instances"] = dict(value=len(base_n), source="distinct base (id without _Lk suffix)")
    N["n_instances_le100"] = dict(value=len(small), source="bases with _meta.n <= 100 (truth.json via summarize_expB.n_of)")
    N["n_sheets_le100"] = dict(value=len(sheets_le), source="distinct id whose base has n <= 100")
    d_ids = {x["id"] for x in rs if x["arm"] == "d"}
    N["n_sheets_with_data"] = dict(value=len(d_ids), source="distinct sheet id with at least one arm-d row, bases with n<=100 (the population behind the equivalence headline)")
    N["n_bases_with_data"] = dict(value=len({S.base_of(i) for i in d_ids}), source="distinct base of those sheets (arm d, n<=100)")
    N["n_instances_gt100"] = dict(value=len(big), source="bases with n > 100 (counts only, no CI)")
    N["n_sheets_gt100"] = dict(value=len(sheets - sheets_le), source="distinct id whose base has n > 100")
    for a, key in (("d", "equiv_d"), ("dprime", "equiv_dprime"), ("r", "equiv_r")):
        res = rate(S.cells_of(BS[a], "equiv")) if a in BS else None
        N[key] = dict(res or dict(value=None, ci=None), source=f"S.cells_of(equiv, arm={a}), L1-L4 pooled over bases, n<=100, S.cluster_boot (percent)")
    eb = {}
    for lv in LEVELS:
        eb[lv] = {}
        for a, k in (("d", "d"), ("dprime", "dprime"), ("r", "r")):
            eb[lv][k] = (rate(S.cells_of(BS[a], "equiv", lv)) if a in BS else None)
    N["equiv_by_level"] = dict(value=eb, source="S.cells_of(equiv, level), n<=100, S.cluster_boot; each entry {value, ci, n_bases} in percent")
    if "d" in BS and "dprime" in BS:
        r = S.cluster_boot(S.paired_cells(BS["d"], BS["dprime"], "equiv"))
        N["paired_d_minus_dprime"] = dict(value=100 * r[1], median=100 * r[1], point=100 * r[0], ci=[100 * r[2], 100 * r[3]], n_bases=r[4],
                                          source="S.paired_cells(d, dprime, equiv) + S.cluster_boot; value = median = bootstrap median (pp), point = mean difference (= X - Y)")
    else:
        N["paired_d_minus_dprime"] = dict(value=None, ci=None, source="arm d or dprime missing")
    nt = lambda v: v["trivial"] == 0
    for key, arm, met, only in (("hit_le_d", "d", "hit_le", None), ("hit_eq_d", "d", "hit_eq", None),
                                ("hit_le_d_nontrivial", "d", "hit_le", nt), ("hit_le_c", "c", "hit_le", None)):
        res = rate(S.cells_of(BS[arm], met, None, only)) if arm in BS else None
        N[key] = dict(res or dict(value=None, ci=None),
                      source=f"S.cells_of({met}, arm={arm}{', trivial_lb=0' if only else ''}), n<=100, S.cluster_boot (percent)")
    ob = {}
    for x in rows:
        if S.g(x, "oracle_unstable", "") != "":
            ob[S.base_of(x["id"])] = int(x["oracle_unstable"])
    N["oracle_unstable_count"] = dict(value=sum(ob.values()), n_bases=len(ob), source="column oracle_unstable, distinct bases (all n)")
    fc = {}
    for a in ("d", "dprime"):
        if a not in BS:
            continue
        fc[a] = {}
        for lv in LEVELS:
            bad = [x for x in rs if x["arm"] == a and x["level"] == lv and S.is_fail(x, a)]
            k = dict.fromkeys(FAIL_KINDS + ["other"], 0)
            for x in bad:
                k[S.fail_kind(x, a)] += 1
            fc[a][lv] = dict(non_equivalent=len(bad), rows=len([x for x in rs if x["arm"] == a and x["level"] == lv]),
                             **{kk: dict(count=v, pct_of_non_equivalent=(100 * v / len(bad) if bad else None)) for kk, v in k.items()})
    N["failure_classes"] = dict(value=fc, source="S.fail_kind / S.is_fail on rows (not bases), n<=100; per arm and level; 'other' = API/solver rows, listed but not one of the four classes")
    sub = {}
    if "d" in BS:
        ok = [x for x in rs if x["arm"] == "d" and S.fail_kind(x, "d") not in ("truncated", "parse") and not x["error"]]
        for nm, col in (("tasks", "diff_taskset"), ("times", "diff_time"), ("closure", "diff_closure"), ("zones", "diff_zone")):
            sub[nm] = dict(pct=(100 * sum(1 for x in ok if int(S.g(x, col, 0) or 0) == 0) / len(ok)) if ok else None, n_rows=len(ok))
    N["subscores"] = dict(value=sub, source="arm d, n<=100 rows that returned a parseable, non-truncated, error-free model; pass = diff_taskset/time/closure/zone == 0")
    d_rows = [x for x in rs if x["arm"] == "d"]
    med = lambda col: float(np.median([float(x[col]) for x in d_rows if x[col] != ""])) if d_rows and any(x[col] != "" for x in d_rows) else None
    N["latency_median_s"] = dict(value=med("latency_s"), source="column latency_s, arm d, n<=100 rows")
    N["completion_tokens_median"] = dict(value=med("completion_tokens"), source="column completion_tokens, arm d, n<=100 rows")
    N["rounds_mean_d"] = dict(value=float(np.mean([int(x["rounds"] or 0) for x in d_rows])) if d_rows else None, source="column rounds, arm d, n<=100 rows")
    ceil_const = all(eb[lv]["r"] is not None and eb[lv]["r"]["ci"][0] == eb[lv]["r"]["ci"][1] for lv in LEVELS) if "r" in BS else False
    N["fig2_caption_note"] = dict(value=("Template parser (r): value is the same at every resample, so no error bars are drawn (CI collapses to the point)." if ceil_const else None),
                                  source="true if the r arm CI has zero width at every level")
    N["fig3_arm"] = dict(value="d", source="Figure 3 shows arm d (with feedback), n<=100, row counts per level")
    N.update(secondary(rows, rs, BS, small, base_n, arms, args))
    N.update(v5_keys(rows, rs, small))
    N["synthetic"] = dict(value=("synthetic" in os.path.basename(args.csv).lower()), source="true when the CSV file name contains 'synthetic' (numbers carry no information)")
    # run settings
    src = open(os.path.join(EXP, "run_expB.py"), encoding="utf-8").read()
    t = re.search(r"^TEMPERATURE\s*=\s*([\d.]+)", src, re.M)
    N["model"] = dict(value=args.model or "not recorded in CSV (pass --model)", source="--model argument (the CSV has no model column)")
    N["temperature"] = dict(value=float(t.group(1)) if t else None, source="TEMPERATURE constant in run_expB.py (read only)")
    N["max_tokens_modelling"] = dict(value=args.max_tokens_modelling, source="--max-tokens-modelling argument (modelling arms d, d'); not read from run_expB.py")
    N["max_tokens_direct"] = dict(value=args.max_tokens_direct, source="--max-tokens-direct argument (direct-assignment arm c); not read from run_expB.py")
    mtime = datetime.datetime.fromtimestamp(os.path.getmtime(args.csv), datetime.timezone.utc)
    N["run_date"] = dict(value=args.run_date or mtime.strftime("%Y-%m-%d"), source="--run-date argument, else CSV mtime (UTC)")
    N["csv_sha256"] = dict(value=hashlib.sha256(open(args.csv, "rb").read()).hexdigest(), source="sha256 of --csv")
    N["generated_at_utc"] = dict(value=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), source="system clock")
    return N, arms


# ---------------------------------------------------------------- SVG
def svg_open(w, h):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}" font-size="26">',
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>']


def txt(x, y, s, anchor="middle", fill="#333333", weight="400", size=26):
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" fill="{fill}" font-size="{size}" font-weight="{weight}">{s}</text>'


def legend(items, y, x0=70, W=1000, colx=None, fs=22):
    """one legend row, 22 px labels; colx = optional fixed x of each column (so several rows align); asserts the row ends inside the viewBox"""
    out, x = [], x0
    for i, (col, lab) in enumerate(items):
        if colx:
            x = colx[i]
        out.append(f'<rect x="{x}" y="{y - 17}" width="20" height="20" fill="{col}"/>')
        out.append(txt(x + 27, y, lab, "start", size=fs))
        x += 27 + int(len(lab) * 12.6 * fs / 22) + 22
    assert x - 22 <= W - 10, f"legend row at y={y} ends at x={x - 22}, outside the viewBox width {W}"
    return out


def legend_cols(rows, x0=20, fs=22):
    """x of each column so that the rows line up (column width = widest label in it)"""
    n = max(len(r) for r in rows)
    xs, x = [], x0
    for i in range(n):
        xs.append(x)
        x += 27 + max(int(len(r[i][1]) * 12.6 * fs / 22) for r in rows if i < len(r)) + 22
    return xs


def fig2(N, arms, size=None):
    W, H, L, R, T, Bm = 1000, 244, 70, 990, 14, 204
    fs, bw, gap = 22, 70, 10
    if size:                          # Spec 16: taller panel version, bigger labels and bars; default output is unchanged
        W, H = size
        R, Bm, T = W - 10, H - 44, 14
        fs, bw, gap = 28, 90, 14
    YMAX = 120                       # axis goes to 120 so the bar labels clear the 100% line; ticks stay 0 / 50 / 100
    ph = Bm - T
    yy = lambda p: Bm - ph * p / YMAX
    o = svg_open(W, H)
    lg = legend([(C_D, "with feedback"), (C_DP, "single pass")], 34 if not size else 36, L + 10, W, fs=fs)   # legend sits in the 100-120 band above the 100% line
    o += lg
    # parser label: same row, right end at x = R (the right end of the dashed line below), with a dashed sample in front of it
    lab_w = int(len("template-aware parser (ablation)") * 12.6 * fs / 22)
    if not size:
        o.append(f'<line x1="{R - lab_w - 62:.1f}" x2="{R - lab_w - 10:.1f}" y1="27" y2="27" stroke="{C_R}" stroke-width="4" stroke-dasharray="14 8"/>')
        o.append(txt(R, 34, "template-aware parser (ablation)", "end", "#555555", size=fs))
        assert R - lab_w - 62 > 520, "parser label overlaps the legend"
    else:                              # Spec 16: with 28 px labels the parser entry needs its own row under the arm legend
        o.append(f'<line x1="{L + 10}" x2="{L + 62}" y1="66" y2="66" stroke="{C_R}" stroke-width="4" stroke-dasharray="14 8"/>')
        o.append(txt(L + 72, 74, "template-aware parser (ablation)", "start", "#555555", size=fs))
    for p in (0, 50, 100):
        o.append(f'<line x1="{L}" x2="{R}" y1="{yy(p):.1f}" y2="{yy(p):.1f}" stroke="#D9D9D9" stroke-width="2"/>')
        o.append(txt(L - 10, yy(p) + 9, str(p), "end", size=26 if not size else 28))
    eb = N["equiv_by_level"]["value"]
    gw = (R - L) / 4
    rv = [eb[lv].get("r") for lv in LEVELS]
    r_same = all(e is not None for e in rv) and max(e["value"] for e in rv) - min(e["value"] for e in rv) < 1e-9
    for i, lv in enumerate(LEVELS):
        cx = L + gw * (i + 0.5)
        o.append(txt(cx, Bm + 30 + (6 if size else 0), lv, size=26 if not size else 30))
        for j, (k, col) in enumerate((("d", C_D), ("dprime", C_DP))):
            e = eb[lv].get(k)
            if e is None:
                continue
            x = cx + (j - 0.5) * (bw + gap) - bw / 2
            v = e["value"]
            o.append(f'<rect x="{x:.1f}" y="{yy(v):.1f}" width="{bw}" height="{Bm - yy(v):.1f}" fill="{col}"/>')
            top = v
            lo, hi = e["ci"]
            if hi - lo > 1e-9:
                xm = x + bw / 2
                o.append(f'<g stroke="#222222" stroke-width="3"><line x1="{xm:.1f}" x2="{xm:.1f}" y1="{yy(lo):.1f}" y2="{yy(hi):.1f}"/>'
                         f'<line x1="{xm - 9:.1f}" x2="{xm + 9:.1f}" y1="{yy(lo):.1f}" y2="{yy(lo):.1f}"/>'
                         f'<line x1="{xm - 9:.1f}" x2="{xm + 9:.1f}" y1="{yy(hi):.1f}" y2="{yy(hi):.1f}"/></g>')
                top = hi
            o.append(txt(x + bw / 2, yy(top) - 5, f"{v:.0f}", size=fs).replace("<text ", '<text stroke="#ffffff" stroke-width="7" paint-order="stroke" ', 1))   # white halo so the label stays readable over the dashed parser line
        if not r_same and rv[i] is not None:
            y = yy(rv[i]["value"])
            o.append(f'<line x1="{L + gw * i + 8:.1f}" x2="{L + gw * (i + 1) - 8:.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{C_R}" stroke-width="4" stroke-dasharray="14 8"/>')
    if r_same:
        y = yy(rv[0]["value"])
        o.append(f'<line x1="{L}" x2="{R}" y1="{y:.1f}" y2="{y:.1f}" stroke="{C_R}" stroke-width="4" stroke-dasharray="14 8"/>')
    o.append(f'<line x1="{L}" x2="{R}" y1="{Bm}" y2="{Bm}" stroke="#333333" stroke-width="2"/>')
    o.append("</svg>")
    return "\n".join(o)


FLAG_COL = {"f1": "#1F4E79", "f2": "#8FB3D9", "f3": "#C9892B", "f4": "#7A7A7A", "t": "#2E7D5B", "p": "#A94442", "api": "#6A4C93"}
FLAG_LABEL = {"f1": "task set", "f2": "times", "f3": "precedence closure", "f4": "station rules", "t": "truncated", "p": "unparseable", "api": "API"}


def fig3(N, size=None):
    W, H, L, R, T, Bm = 1000, 176, 40, 990, 78, 136
    fs, bw, gap, vs = 22, 38, 5, 24
    if size:                          # Spec 16: taller version, bigger labels; default output is unchanged
        W, H = size
        R, Bm, T = W - 10, H - 40, 100
        fs, bw, gap, vs = 26, 40, 6, 26
    sc = N["sheet_counts"]["value"]
    keys = ("f1", "f2", "f3", "f4")
    colname = dict(f1="diff_taskset", f2="diff_time", f3="diff_closure", f4="diff_zone")
    vals = [[sc["per_level"][lv][colname[k]] for k in keys] for lv in LEVELS] + [[sc["t"], sc["p"], sc["api"]]]
    mx = max([v for g in vals for v in g] + [1])
    yy = lambda c: Bm - (Bm - T) * c / mx
    o = svg_open(W, H)
    r1 = [(FLAG_COL[k], FLAG_LABEL[k]) for k in ("f1", "f2", "f3", "f4")]
    r2 = [(FLAG_COL[k], FLAG_LABEL[k]) for k in ("t", "p", "api")]
    cx_ = legend_cols([r1, r2], fs=fs)
    o += legend(r1, 26 if not size else 32, 20, W, cx_, fs=fs)
    o += legend(r2, 56 if not size else 70, 20, W, cx_, fs=fs)
    o.append(f'<line x1="{L}" x2="{R}" y1="{Bm}" y2="{Bm}" stroke="#333333" stroke-width="2"/>')
    gw = (R - L) / 5
    names = LEVELS + ["other"]
    gkeys = [keys] * 4 + [("t", "p", "api")]
    for i, nm in enumerate(names):
        cx = L + gw * (i + 0.5)
        o.append(txt(cx, Bm + 30 if size else 166, nm, size=26 if not size else 28))
        n = len(gkeys[i])
        for j, k in enumerate(gkeys[i]):
            c = vals[i][j]
            x = cx + (j - (n - 1) / 2) * (bw + gap) - bw / 2
            o.append(f'<rect x="{x:.1f}" y="{yy(c):.1f}" width="{bw}" height="{Bm - yy(c):.1f}" fill="{FLAG_COL[k]}"/>')
            o.append(f'<text x="{x + bw / 2:.1f}" y="{yy(c) - 5:.1f}" text-anchor="middle" fill="#333333" font-size="{vs}">{c}</text>')
    o.append("</svg>")
    return "\n".join(o)


# ---------------------------------------------------------------- table
def table(N):
    """-> (main rows (<= 12), full rows). Expectation column = prereg text copied verbatim."""
    P = read_prereg()
    none = "none registered"
    V = lambda k: N[k]
    eb = N["equiv_by_level"]["value"]
    pp = lambda d: "n/a" if d is None or d.get("value") is None else f"{d['value']:+.1f} [{d['ci'][0]:+.1f}, {d['ci'][1]:+.1f}]"
    ppm = lambda d: "n/a" if d is None or d.get("value") is None else f"{d.get('point', d['value']):+.1f} ({d['value']:+.1f}) [{d['ci'][0]:+.1f}, {d['ci'][1]:+.1f}]"
    tr = lambda a: " → ".join(fmt(eb[lv][a]["value"], 0) if eb[lv].get(a) else "n/a" for lv in LEVELS)
    af = N["api_failures"]["value"]
    afs = ", ".join(f"{a}: {v['rows_le100']} of {v['n_rows_le100']} rows" for a, v in af.items()) or "n/a"
    ob = N["oracle_both_optimal"]
    obs = "n/a (oracle status file not found)" if ob["value"] is None else (
        f"{ob['value']} of {ob['n_bases_with_status']} instances; hit_le d {fmtci(N['hit_le_d_both_optimal'])}; not proven optimal: {N['oracle_not_proven_optimal_count']['value']}")
    k = N["trivial_lb_subset"]["value"]
    main = [
        ("Paired difference d − d′ (primary), mean difference (bootstrap median in parentheses), pp [95% CI]", P.get("H1", none) + " | " + P.get("v13:H1 的解讀", ""), ppm(N["paired_d_minus_dprime"])),
        ("Model equivalence, L1–L4 pooled: d / d′ / r (%)", none, f"{fmtci(V('equiv_d'), 1)} / {fmtci(V('equiv_dprime'), 1)} / {fmtci(V('equiv_r'), 1)}"),
        ("End to end vs oracle, d: hit_le / hit_eq (%)", P.get("H2", none), f"{fmtci(V('hit_le_d'))} / {fmtci(V('hit_eq_d'))}"),
        ("H2 criterion: hit_le d − c, median pp [95% CI]", P.get("v13:H2 判準", none), pp(N["h2_d_minus_c_hit_le"])),
        (f"hit_le on non-trivial instances (trivial_lb = 0), d (%); non-trivial {k['k_nontrivial_of_N']}", P.get("v13:端到端敏感度", none), fmtci(V("hit_le_d_nontrivial"))),
        ("hit_le against truth_m_max, d (%)", P.get("v13:端到端敏感度", none), fmtci(V("hit_le_vs_truth_m_max"))),
        ("Both oracle runs OPTIMAL subset", P.get("v13:端到端敏感度", none), obs),
        ("Equivalence L1 → L4 (%), d; d′", P.get("v13:H3 判準", none), f"d: {tr('d')}; d′: {tr('dprime')}"),
        ("H5 criterion: L4 − L3 equivalence, d, median pp [95% CI]", P.get("v13:H5 判準", none), pp(N["h5_l4_minus_l3"])),
        ("Template parser ceiling r (%)", P.get("parser", none), fmtci(V("equiv_r"))),
        ("API failure rows (n ≤ 100)", P.get("v13:API 失敗", none), afs),
        ("Oracle unstable instances", none, f"{N['oracle_unstable_count']['value']} of {N['oracle_unstable_count']['n_bases']}"),
    ]
    full = list(main)
    full.append(("Instances with n > 100 (counts only)", none, f"{N['n_instances_gt100']['value']} instances, {N['n_sheets_gt100']['value']} sheets"))
    full.append(("d − d′ excluding bases with API-failure rows, median pp [95% CI]", P.get("v13:API 失敗", none),
                 pp(N["paired_d_minus_dprime_excl_api"]) + f" (bases excluded: {N['paired_d_minus_dprime_excl_api'].get('n_bases_excluded', 'n/a')})"))
    hc = N["h1_components"]["value"]
    for key, lab in (("dprime_invalid_rate", "d′ invalid rate (%)"), ("repair_success_rate", "d repair success rate (%)"),
                     ("same_seed_consistency", "same-seed consistency (%)"), ("no_feedback_resample", "no-feedback resample, any d′ seed valid (%)")):
        full.append((lab, P.get("v13:H1 的解讀", none), fmtci(hc[key]) if key in hc else "n/a"))
    for nm, e in N["by_size"]["value"].items():
        full.append((f"Equivalence, size {nm}: d / d′ / r (%)", P.get("v13:分層描述", none),
                     " / ".join(f"{fmtci(e[a])} (n={e[a]['n_instances']})" if a in e else "n/a" for a in ("d", "dprime", "r"))))
    for nm, e in N["by_source"]["value"].items():
        full.append((f"Equivalence, source {nm}: d / d′ / r (%)", P.get("v13:分層描述", none),
                     " / ".join(f"{fmtci(e[a])} (n={e[a]['n_instances']})" if a in e else "n/a" for a in ("d", "dprime", "r"))))
    for lv, e in N["diff_flags_by_level"]["value"].items():
        full.append((f"{lv} non-equivalent d rows: diff flags taskset / time / closure / zone (%)", P.get("v13:分層描述", none),
                     f"{e['n_nonequiv_rows']} rows: " + " / ".join(fmt(e[c], 0) for c in ("diff_taskset", "diff_time", "diff_closure", "diff_zone"))))
    for a, e in N["invalid_reasons"]["value"].items():
        full.append((f"invalid: reasons, arm {a}", none, f"{e['total']} rows, 'need int' share {e['need_int_share_pct']:.0f}%"))
    return main, full


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def table_md(rows):
    L = ["| Endpoint | Pre-specified expectation | Measured |", "|---|---|---|"]
    for a, b, c in rows:
        L.append(f"| {a} | {b.replace('|', '/')} | {c} |")
    return "\n".join(L) + "\n"


def table_html(rows):
    cell = "padding: 6px 16px; border-top: 2px solid #333333"
    o = ['<div style="width: 880px; box-sizing: border-box; display: grid; grid-template-columns: 250px minmax(0, 1fr) minmax(0, 1fr); '
         'border: 3px solid #333333; font-size: 26px; line-height: 1.3; font-family: Inter, sans-serif; color: #333333">']
    for h in ("Endpoint", "Pre-specified expectation", "Measured"):
        o.append(f'<div style="padding: 6px 16px; background: #333333; color: #ffffff; font-weight: 600">{h}</div>')
    for a, b, c in rows:
        o.append(f'<div style="{cell}; font-weight: 600">{esc(a)}</div><div style="{cell}">{esc(b)}</div><div style="{cell}">{esc(c)}</div>')
    o.append("</div>")
    return "\n".join(o) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default=None, help="model id as served (not in the CSV)")
    ap.add_argument("--max-tokens-modelling", type=int, default=None, help="token cap used for the modelling arms (d, d'); not read from run_expB.py")
    ap.add_argument("--max-tokens-direct", type=int, default=None, help="token cap used for the direct-assignment arm (c)")
    ap.add_argument("--run-date", default=None)
    ap.add_argument("--fig2-size", default=None, help="WxH of the Figure 2 SVG (Spec 16, e.g. 1000x580); default = the original 1000x244 design")
    ap.add_argument("--fig3-size", default=None, help="WxH of the Figure 3 SVG (Spec 16, e.g. 1000x320); default = the original 1000x176 design")
    ap.add_argument("--oracle-json", default=None, help="oracle status json; default truth_cpsat_w4_t60.json next to the CSV")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    rows = list(csv.DictReader(open(a.csv, newline="")))
    N, arms = build(rows, a)
    w = lambda n, s: open(os.path.join(a.out_dir, n), "w", encoding="utf-8").write(s)
    sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    opath = a.oracle_json or os.path.join(os.path.dirname(os.path.abspath(a.csv)), "truth_cpsat_w4_t60.json")
    N["inputs"] = dict(csv_path=os.path.abspath(a.csv), csv_sha256=sha(a.csv), csv_rows=len(rows),
                       oracle_json_path=os.path.abspath(opath) if os.path.exists(opath) else None,
                       oracle_json_sha256=sha(opath) if os.path.exists(opath) else None)
    w("numbers.json", json.dumps(N, indent=1, ensure_ascii=False))
    sz = lambda t: tuple(int(x) for x in t.lower().split("x")) if t else None
    w("fig2_equivalence.svg", fig2(N, arms, sz(a.fig2_size)))
    w("fig3_failures.svg", fig3(N, sz(a.fig3_size)))
    tm, tf = table(N)
    assert len(tm) <= 12
    w("results_table.md", table_md(tm))
    w("results_table_full.md", table_md(tf))
    w("results_table.html", table_html(tm))
    print("wrote", a.out_dir, "keys:", ", ".join(N))


if __name__ == "__main__":
    main()
