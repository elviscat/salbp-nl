"""CP-SAT model for SALBP-1 (assignment model, station-index precedence)."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ortools.sat.python import cp_model
from salbp_io import transitive_closure, validate_solution
from solve_rpw import rpw


def solve_salbp1(inst, c, time_limit=60.0, workers=8, extra_same=(), extra_incompat=(), ub_hint=None, seed=0):
    """Minimise number of stations. Returns dict(status, m, assign, time_s, lb, ub_start).
    extra_same / extra_incompat: optional same-station / incompatible-pair constraints (used by gen_nl)."""
    n = inst.n
    t0 = time.time()
    succ, pred = transitive_closure(n, inst.prec)
    if ub_hint is None:
        try:
            m_rpw, a_rpw = rpw(inst, c)
            if extra_same or extra_incompat:
                try:
                    validate_solution(inst, c, a_rpw, extra_same, extra_incompat)
                except ValueError:
                    m_rpw, a_rpw = None, None
        except ValueError:
            m_rpw, a_rpw = None, None
    else:
        m_rpw, a_rpw = ub_hint
    if m_rpw is None:
        M = n  # trivially valid upper bound (one task per station)
    else:
        M = m_rpw
    tsum = sum(inst.times)
    lb0 = -(-tsum // c)
    # earliest / latest station per task (classical tightening)
    E, L = {}, {}
    for i in range(1, n + 1):
        ti = inst.times[i - 1]
        E[i] = max(1, -(-(ti + sum(inst.times[p - 1] for p in pred[i])) // c))
        L[i] = M + 1 - -(-(ti + sum(inst.times[s - 1] for s in succ[i])) // c)
    model = cp_model.CpModel()
    x = {}
    for i in range(1, n + 1):
        for k in range(E[i], L[i] + 1):
            x[i, k] = model.NewBoolVar(f"x{i}_{k}")
    y = {k: model.NewBoolVar(f"y{k}") for k in range(1, M + 1)}
    for i in range(1, n + 1):
        ks = [k for k in range(E[i], L[i] + 1)]
        if not ks:
            return dict(status="INFEASIBLE_BOUNDS", m=None, assign=None, time_s=time.time() - t0, lb=lb0)
        model.AddExactlyOne(x[i, k] for k in ks)
    for k in range(1, M + 1):
        terms = [(inst.times[i - 1], x[i, k]) for i in range(1, n + 1) if (i, k) in x]
        model.Add(sum(t * v for t, v in terms) <= c * y[k])
        for i in range(1, n + 1):
            if (i, k) in x:
                model.AddImplication(x[i, k], y[k])
    for k in range(1, M):
        model.Add(y[k] >= y[k + 1])  # symmetry breaking: stations opened in order

    def sidx(i):
        return sum(k * x[i, k] for k in range(E[i], L[i] + 1))

    for a, b in inst.prec:
        model.Add(sidx(a) <= sidx(b))
    for a, b in extra_same:
        model.Add(sidx(a) == sidx(b))
    for a, b in extra_incompat:
        for k in range(1, M + 1):
            if (a, k) in x and (b, k) in x:
                model.Add(x[a, k] + x[b, k] <= 1)
    model.Add(sum(y.values()) >= lb0)
    model.Minimize(sum(y.values()))
    if a_rpw is not None:
        for (i, k), v in x.items():
            model.AddHint(v, 1 if a_rpw[i - 1] == k else 0)
        for k, v in y.items():
            model.AddHint(v, 1 if k <= m_rpw else 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.random_seed = seed
    st = solver.Solve(model)
    name = solver.StatusName(st)
    out = dict(status=name, time_s=time.time() - t0, lb=None, m=None, assign=None)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assign = [0] * n
        for (i, k), v in x.items():
            if solver.Value(v):
                assign[i - 1] = k
        m = validate_solution(inst, c, assign, extra_same, extra_incompat)  # raises if invalid
        out.update(m=m, assign=assign, lb=int(round(solver.BestObjectiveBound())))
    return out


if __name__ == "__main__":
    from salbp_io import load_graph
    g = load_graph("MERTENS")
    print(solve_salbp1(g, 6, 10, 2))
