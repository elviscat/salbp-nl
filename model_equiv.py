"""Equivalence check between a predicted SALBP-NL JSON model and the ground truth.
Equivalent iff: same task ids, same task times, same transitive closure of precedence,
same same_station / incompatible sets (unordered pairs), same objective and cycle time."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from salbp_io import transitive_closure


def _pairs(lst):
    return {tuple(sorted((int(a), int(b)))) for a, b in (lst or [])}


def _closure_pairs(ids, prec):
    """Transitive closure as a set of (i,j). Raises ValueError on cycle / unknown ids."""
    idmap = {t: k + 1 for k, t in enumerate(sorted(ids))}
    inv = {v: k for k, v in idmap.items()}
    edges = [(idmap[int(a)], idmap[int(b)]) for a, b in prec]
    succ, _ = transitive_closure(len(ids), edges)
    return {(inv[u], inv[v]) for u, vs in succ.items() for v in vs}


def check_equivalent(pred, truth):
    """Return (ok: bool, diffs: list[dict]). Each diff: {kind, detail}."""
    diffs = []
    pt = {int(t["id"]): t.get("time_s") for t in pred.get("tasks", [])}
    tt = {int(t["id"]): t["time_s"] for t in truth["tasks"]}
    for i in sorted(set(tt) - set(pt)):
        diffs.append(dict(kind="missing_task", detail=i))
    for i in sorted(set(pt) - set(tt)):
        diffs.append(dict(kind="extra_task", detail=i))
    for i in sorted(set(pt) & set(tt)):
        if pt[i] != tt[i]:
            diffs.append(dict(kind="wrong_time", detail=dict(id=i, pred=pt[i], truth=tt[i])))
    ids_ok = set(pt) == set(tt)
    if ids_ok:
        try:
            pc = _closure_pairs(pt.keys(), pred.get("precedence", []))
        except (ValueError, KeyError, TypeError) as e:
            pc = None
            diffs.append(dict(kind="invalid_precedence", detail=str(e)))
        tc = _closure_pairs(tt.keys(), truth["precedence"])
        if pc is not None:
            for p in sorted(tc - pc):
                diffs.append(dict(kind="precedence_missing", detail=list(p)))
            for p in sorted(pc - tc):
                diffs.append(dict(kind="precedence_extra", detail=list(p)))
    else:
        # ids differ: still report precedence edges that reference unknown ids
        for a, b in pred.get("precedence", []):
            if int(a) not in tt or int(b) not in tt:
                diffs.append(dict(kind="precedence_unknown_id", detail=[a, b]))
    for key in ("same_station", "incompatible"):
        p, t = _pairs(pred.get(key)), _pairs(truth.get(key))
        for x in sorted(t - p):
            diffs.append(dict(kind=f"{key}_missing", detail=list(x)))
        for x in sorted(p - t):
            diffs.append(dict(kind=f"{key}_extra", detail=list(x)))
    for key in ("objective", "cycle_time_s"):
        if pred.get(key) != truth.get(key):
            diffs.append(dict(kind=f"wrong_{key}", detail=dict(pred=pred.get(key), truth=truth.get(key))))
    return (len(diffs) == 0), diffs


def transitive_reduction(ids, prec):
    """Hasse diagram edges of the closure of prec."""
    cl = _closure_pairs(ids, prec)
    succ = {}
    for a, b in cl:
        succ.setdefault(a, set()).add(b)
    red = []
    for a, b in sorted(cl):
        if not any(b in succ.get(m, ()) for m in succ.get(a, ()) if m != b):
            red.append((a, b))
    return red
