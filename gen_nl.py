"""SALBP-NL generator: Instance -> English IE routing sheet (L1/L2/L3) + ground-truth JSON model.
usage: gen_nl.py [--out data/salbp_nl] [--n-otto 25]
Names/constraints are seeded per base instance (so L1/L2/L3 of one instance are a paired comparison);
unit mixing and sentence templates are seeded per (instance, level)."""
import os, sys, json, random, zlib, argparse, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import salbp_io
from model_equiv import transitive_reduction
from solve_cpsat import solve_salbp1

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = json.load(open(os.path.join(HERE, "nl_lexicon.json")))
P_ZONE, P_INCOMPAT = 0.30, 0.30


def seed_of(*parts):
    return zlib.crc32("|".join(map(str, parts)).encode()) & 0xFFFFFFFF


# ------------------------------------------------------------------ time expressions
def fmt_time(t, level, rng):
    """Return a string for integer seconds t; guaranteed to parse back to t (see parse_time)."""
    if level == 1:
        kinds, wts = ["s", "seconds"], [0.5, 0.5]
    elif level == 2:
        kinds, wts = ["s", "seconds", "ms", "min"], [0.35, 0.35, 0.15, 0.15]
    else:
        kinds, wts = ["s", "seconds", "ms", "min"], [0.25, 0.25, 0.25, 0.25]
    k = rng.choices(kinds, wts)[0]
    if k == "s":
        return f"{t} s"
    if k == "seconds":
        return f"{t} seconds"
    if k == "ms":
        return f"{t * 1000} ms"
    # minutes: only if a short decimal round-trips exactly to t seconds
    s = f"{t / 60:.4f}".rstrip("0").rstrip(".")
    if abs(float(s) * 60 - t) < 1e-6 and len(s) <= 7:  # exact round trip only (t multiple of 3 s)
        return f"{s} min"
    return f"{t} s"


def parse_time(s):
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(s|seconds|ms|min)\s*", s)
    v, u = float(m.group(1)), m.group(2)
    sec = {"s": v, "seconds": v, "ms": v / 1000.0, "min": v * 60.0}[u]
    r = round(sec)
    assert abs(sec - r) < 1e-6, s
    return int(r)


# ------------------------------------------------------------------ naming
def make_names(n, rng):
    pool = LEX[:]
    rng.shuffle(pool)
    names, used = [], {}
    for i in range(n):
        base = pool[i % len(pool)]
        cnt = used.get(base, 0) + 1
        used[base] = cnt
        names.append(base if cnt == 1 else f"{base} #{cnt}")
    return names


def join_ids(ids, word="task"):
    ids = list(ids)
    s = [str(i) for i in ids]
    body = s[0] if len(s) == 1 else ", ".join(s[:-1]) + " and " + s[-1]
    return f"{word}{'s' if len(s) > 1 else ''} {body}"


def join_task_list(ids):
    s = [f"Task {i}" for i in ids]
    return s[0] if len(s) == 1 else ", ".join(s[:-1]) + " and " + s[-1]


# ------------------------------------------------------------------ extra constraints
def inject_constraints(inst, c, rng):
    n = inst.n
    same, incompat = [], []
    from salbp_io import transitive_closure
    succ, pred = transitive_closure(n, inst.prec)
    t = inst.times

    def feasible(sa, ic):
        r = solve_salbp1(inst, c, time_limit=15, workers=8, extra_same=sa, extra_incompat=ic)
        return r["status"] in ("OPTIMAL", "FEASIBLE")

    if rng.random() < P_ZONE:
        for _ in range(60):
            k = rng.randint(1, min(3, max(1, n // 6)))
            cand = []
            tries = 0
            while len(cand) < k and tries < 200:
                tries += 1
                a = rng.randint(1, n)
                pool = list(succ[a]) + list(pred[a])
                near = [b for b in pool if t[a - 1] + t[b - 1] <= c]
                if near:
                    b = rng.choice(near)
                    p = tuple(sorted((a, b)))
                    if p not in cand:
                        cand.append(p)
            if cand and feasible(cand, []):
                same = cand
                break
    if rng.random() < P_INCOMPAT:
        for _ in range(60):
            k = rng.randint(1, min(3, max(1, n // 6)))
            cand = []
            tries = 0
            while len(cand) < k and tries < 200:
                tries += 1
                a, b = rng.sample(range(1, n + 1), 2)
                p = tuple(sorted((a, b)))
                if p not in cand and p not in same:
                    cand.append(p)
            if cand and feasible(same, cand):
                incompat = cand
                break
    return same, incompat


# ------------------------------------------------------------------ text rendering
ZONES = ["dispensing cell", "press cell", "screw-driving cell", "soldering cell", "test cell", "clean zone"]
SAME_T = [
    "Tasks {a} and {b} both use the {z} fixture and must be done at the same station.",
    "Zone rule: task {a} and task {b} share the {z} and therefore have to be assigned to the same station.",
    "Because of the shared {z}, tasks {a} and {b} must not be split across stations.",
]
INC_T = [
    "Tasks {a} and {b} cannot be performed at the same station.",
    "Incompatibility: task {a} and task {b} must never share a station (contamination risk).",
    "Do not put tasks {a} and {b} together at one station.",
]
PRED_T3 = [  # {J} = 'Task j', {j}, {P} = 'task 3 and task 7' style list of Task ids
    "{J} must follow {P}.",
    "{J} requires {P} beforehand.",
    "{J} cannot be scheduled before {P} {be} finished.",
    "{J} may only begin once {P} {be} done.",
    "Do not start {J} until {P} {have} been completed.",
    "{J} does not start before {P} {be} finished.",
    "{J} comes after {P} in the process flow.",
]
SUCC_T3 = [  # {I} = 'Task i', {S} = list of successors
    "{I} has to be finished before {S} can start.",
    "{S} must not start earlier than {I} ends.",
    "{I} is a prerequisite of {S}.",
    "{I} precedes {S}.",
]


def render(inst, c, level, names, same, incompat, rng, title):
    n, t = inst.n, inst.times
    ctxt = fmt_time(c, level, rng)
    lines = [f"# Routing sheet: {title}", "",
             f"Line takt (cycle time per station): {ctxt}.",
             "Goal: assign every operation to exactly one station so that no station's total standard time exceeds the cycle time "
             "and all precedence rules hold; use as few stations as possible.", ""]
    preds_direct = {j: sorted(a for a, b in inst.prec if b == j) for j in range(1, n + 1)}
    if level == 1:
        lines += ["| ID | Operation | Standard time | Predecessors |", "|---|---|---|---|"]
        for i in range(1, n + 1):
            p = ", ".join(map(str, preds_direct[i])) if preds_direct[i] else "-"
            lines.append(f"| {i} | {names[i-1]} | {fmt_time(t[i-1], level, rng)} | Predecessors: {p} |" if False else
                         f"| {i} | {names[i-1]} | {fmt_time(t[i-1], level, rng)} | {p} |")
        lines += ["", "(Predecessors column lists the operations that must be completed first; '-' means none.)"]
    elif level == 2:
        lines += ["## Operations", ""]
        for i in range(1, n + 1):
            lines.append(f"- Task {i}: {names[i-1]}. Standard time {fmt_time(t[i-1], level, rng)}.")
        lines += ["", "## Sequence rules", "", "Tasks that are not mentioned below have no predecessors.", ""]
        for j in range(1, n + 1):
            P = preds_direct[j]
            if P:
                lines.append(f"Task {j} can start only after {join_ids(P)} {'are' if len(P) > 1 else 'is'} complete.")
    else:
        lines += ["## Operations", ""]
        order = list(range(1, n + 1))
        rng.shuffle(order)
        for i in order:
            lines.append(f"- Task {i} - {names[i-1]} - {fmt_time(t[i-1], level, rng)}")
        hasse = transitive_reduction(list(range(1, n + 1)), inst.prec)
        hs = set(hasse)
        from salbp_io import transitive_closure
        succ, _ = transitive_closure(n, inst.prec)
        extra_pool = [(a, b) for a in succ for b in succ[a] if (a, b) not in hs]
        rng.shuffle(extra_pool)
        k_extra = min(len(extra_pool), max(1, round(0.15 * len(hasse)))) if extra_pool else 0
        edges = list(hasse) + extra_pool[:k_extra]
        rng.shuffle(edges)
        mode = {e: ("pred" if rng.random() < 0.6 else "succ") for e in edges}
        byj, byi = {}, {}
        for (a, b), m in mode.items():
            (byj if m == "pred" else byi).setdefault(b if m == "pred" else a, []).append(a if m == "pred" else b)
        sents = []
        for j, P in byj.items():
            P = sorted(P)
            T = rng.choice(PRED_T3)
            sents.append(T.format(J=f"Task {j}", P=join_task_list(P), be="are" if len(P) > 1 else "is", have="have" if len(P) > 1 else "has"))
        for i, S in byi.items():
            S = sorted(S)
            sents.append(rng.choice(SUCC_T3).format(I=f"Task {i}", S=join_task_list(S)))
        rng.shuffle(sents)
        lines += ["", "## Process-flow notes", "",
                  "Only the immediate sequence relations are listed; relations that follow by chaining them are not repeated "
                  "(some listed relations may nevertheless be redundant).", ""] + [f"- {s}" for s in sents]
    if same or incompat:
        lines += ["", "## Station rules", ""]
        for a, b in same:
            lines.append("- " + rng.choice(SAME_T).format(a=a, b=b, z=rng.choice(ZONES)))
        for a, b in incompat:
            lines.append("- " + rng.choice(INC_T).format(a=a, b=b))
    return "\n".join(lines) + "\n"


def build_truth(inst, c, same, incompat, level, src):
    return {"tasks": [{"id": i + 1, "time_s": inst.times[i]} for i in range(inst.n)],
            "precedence": [[a, b] for a, b in inst.prec],
            "same_station": [list(p) for p in same], "incompatible": [list(p) for p in incompat],
            "objective": "SALBP-1", "cycle_time_s": c,
            "_meta": {"source": src, "level": f"L{level}", "n": inst.n}}


def pick_c_scholl(graph_name, rows):
    cs = sorted(r["c"] for r in rows if r["graph"] == graph_name)
    return cs[len(cs) // 2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "data", "salbp_nl"))
    ap.add_argument("--n-otto", type=int, default=25)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    bk = salbp_io.load_best_known_salbp1()
    bases = []
    for gname in sorted(set(r["graph"] for r in bk)):
        inst = salbp_io.load_graph(salbp_io.graph_stem(gname))
        c = pick_c_scholl(gname, bk)
        bases.append((f"scholl_{gname.lower()}_c{c}", f"Scholl 1993 / {gname}", inst, c))
    if a.n_otto:
        d = os.path.join(salbp_io.RAW, "z2013", "small", "small data set_n=20")
        files = sorted(os.listdir(d))
        r0 = random.Random(20261109)
        for fn in r0.sample(files, a.n_otto):
            inst = salbp_io.read_alb(os.path.join(d, fn))
            nm = os.path.splitext(fn)[0].replace("instance_n=20_", "otto_n20_i")
            bases.append((nm, f"Otto et al. 2013 small / {fn}", inst, inst.cycle_time))
    count = 0
    sid = {b[0]: f"S{k:02d}" for k, b in enumerate(sorted(bases, key=lambda t: t[0]), 1)}  # Spec 04 B7: neutral sheet ids
    for base, src, inst, c in bases:
        rng0 = random.Random(seed_of(base, "base"))
        names = make_names(inst.n, rng0)
        same, incompat = inject_constraints(inst, c, rng0)
        for level in (1, 2, 3):
            rng = random.Random(seed_of(base, "L", level))
            did = f"{base}_L{level}"
            title = f"smartphone final assembly line - sheet {sid[base]} ({inst.n} operations)"
            md = render(inst, c, level, names, same, incompat, rng, title)
            open(os.path.join(a.out, did + ".md"), "w").write(md)
            json.dump(build_truth(inst, c, same, incompat, level, src), open(os.path.join(a.out, did + ".truth.json"), "w"), indent=1)
            count += 1
        print(base, "n=", inst.n, "same", same, "incompat", incompat, flush=True)
    print("files:", count)


if __name__ == "__main__":
    main()
