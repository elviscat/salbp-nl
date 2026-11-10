"""Ranked Positional Weight heuristic for SALBP-1 (Helgeson & Birnie 1961)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from salbp_io import transitive_closure, validate_solution


def rpw(inst, c):
    """Return (m, assign) where assign[i-1] is the station (1-based) of task i.
    Positional weight = own time + times of ALL (transitive) successors."""
    if max(inst.times) > c:
        raise ValueError("a task is longer than the cycle time: infeasible")
    n = inst.n
    succ, _ = transitive_closure(n, inst.prec)
    w = {i: inst.times[i - 1] + sum(inst.times[j - 1] for j in succ[i]) for i in range(1, n + 1)}
    order = sorted(range(1, n + 1), key=lambda i: (-w[i], i))
    preds_direct = {i: [] for i in range(1, n + 1)}
    for a, b in inst.prec:
        preds_direct[b].append(a)
    assign = [0] * n
    done = set()
    k = 0
    while len(done) < n:
        k += 1
        load = 0
        progress = True
        while progress:
            progress = False
            for i in order:
                if i in done:
                    continue
                t = inst.times[i - 1]
                if load + t <= c and all(p in done for p in preds_direct[i]):
                    assign[i - 1] = k
                    done.add(i)
                    load += t
                    progress = True
                    break  # restart scan from highest weight
    m = validate_solution(inst, c, assign)
    return m, assign


if __name__ == "__main__":
    from salbp_io import load_graph
    g = load_graph("MERTENS")
    print(rpw(g, 6))
