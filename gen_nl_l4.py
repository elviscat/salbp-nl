"""Build L4 sheets (name-only references) from the existing L3 sheets + truth.
usage: gen_nl_l4.py [--dir data/salbp_nl]
L4 = L3 with every 'Task <id>' in process-flow notes and station rules replaced by the quoted operation name.
The Operations list keeps ids, names and times (reshuffled, seed = 20261109 + base index), so the model must map names
back to ids itself. Truth is identical to L3 except _meta.level."""
import os, re, sys, json, glob, random, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model_equiv import transitive_reduction
from salbp_io import transitive_closure
from gen_nl import PRED_T3, SUCC_T3, SAME_T, INC_T, ZONES

HERE = os.path.dirname(os.path.abspath(__file__))
OP_RE = re.compile(r"^- Task (\d+) - (.*) - ([0-9]*\.?[0-9]+ (?:s|seconds|ms|min))$")


def q(name):
    return f'"{name}"'


def join_names(names):
    s = [q(x) for x in names]
    return s[0] if len(s) == 1 else ", ".join(s[:-1]) + " and " + s[-1]


def build(md3, truth, rng):
    head, rest = md3.split("## Operations", 1)
    ops = [OP_RE.match(ln) for ln in rest.split("## Process-flow notes")[0].splitlines() if ln.startswith("- Task")]
    assert all(ops)
    name = {int(m.group(1)): m.group(2) for m in ops}
    oplines = [m.group(0) for m in ops]
    rng.shuffle(oplines)
    n = len(name)
    prec = [tuple(p) for p in truth["precedence"]]
    ids = list(range(1, n + 1))
    hasse = transitive_reduction(ids, prec)
    hs = set(hasse)
    succ, _ = transitive_closure(n, prec)
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
        sents.append(rng.choice(PRED_T3).format(J=q(name[j]), P=join_names([name[p] for p in P]),
                                                be="are" if len(P) > 1 else "is", have="have" if len(P) > 1 else "has"))
    for i, S in byi.items():
        S = sorted(S)
        sents.append(rng.choice(SUCC_T3).format(I=q(name[i]), S=join_names([name[s] for s in S])))
    rng.shuffle(sents)
    lines = [head.rstrip("\n"), "", "## Operations", ""] + oplines
    lines += ["", "## Process-flow notes", "",
              "Only the immediate sequence relations are listed; relations that follow by chaining them are not repeated "
              "(some listed relations may nevertheless be redundant).", ""] + [f"- {s}" for s in sents]
    same, inc = truth["same_station"], truth["incompatible"]
    if same or inc:
        lines += ["", "## Station rules", ""]
        for a, b in same:
            lines.append("- " + rng.choice(SAME_T).format(a=q(name[a]), b=q(name[b]), z=rng.choice(ZONES)))
        for a, b in inc:
            lines.append("- " + rng.choice(INC_T).format(a=q(name[a]), b=q(name[b])))
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(HERE, "data", "salbp_nl"))
    a = ap.parse_args()
    l3 = sorted(glob.glob(os.path.join(a.dir, "*_L3.md")))
    for k, f in enumerate(l3):
        base = os.path.basename(f)[:-6]
        truth = json.load(open(f[:-3] + ".truth.json"))
        md = build(open(f).read(), truth, random.Random(20261109 + k))
        truth["_meta"]["level"] = "L4"
        open(os.path.join(a.dir, base + "_L4.md"), "w").write(md)
        json.dump(truth, open(os.path.join(a.dir, base + "_L4.truth.json"), "w"), indent=1)
    print("L4 files:", len(l3))


if __name__ == "__main__":
    main()
