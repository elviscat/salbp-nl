"""Parsers for SALBP benchmark files and a loader for the published best-known table."""
import os, re, sys
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RAW = os.path.join(HERE, "data", "raw")
IN2_DIR = os.path.join(RAW, "z1993", "precedence graphs")
XLSX_1993 = os.path.join(RAW, "z1993", "SALBP data sets.xlsx")


@dataclass
class Instance:
    name: str
    n: int
    times: list            # times[i-1] is the time of task i (int)
    prec: list             # list of (i, j): i must precede j; tasks numbered 1..n
    cycle_time: int = None  # filled by .alb files


def read_in2(path, name=None):
    with open(path, "r", errors="replace") as f:
        toks = [ln.strip() for ln in f.read().splitlines() if ln.strip()]
    n = int(toks[0])
    times = [int(toks[1 + i]) for i in range(n)]
    prec = []
    for ln in toks[1 + n:]:
        a, b = [int(x) for x in ln.split(",")]
        if a == -1 and b == -1:
            break
        prec.append((a, b))
    name = name or os.path.splitext(os.path.basename(path))[0]
    return Instance(name, n, times, prec)


def read_alb(path, name=None):
    """Otto, Otto & Scholl (2013) .alb format (sections in <...> tags)."""
    with open(path, "r", errors="replace") as f:
        lines = f.read().splitlines()
    sec, cur = None, {}
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        m = re.fullmatch(r"<(.+)>", s)
        if m:
            sec = m.group(1).strip()
            cur[sec] = []
        elif sec is not None:
            cur[sec].append(s)
    n = int(cur["number of tasks"][0])
    c = int(cur["cycle time"][0])
    times = [0] * n
    for s in cur["task times"]:
        i, t = s.split()
        times[int(i) - 1] = int(t)
    prec = []
    for s in cur.get("precedence relations", []):
        a, b = s.split(",")
        prec.append((int(a), int(b)))
    name = name or os.path.splitext(os.path.basename(path))[0]
    return Instance(name, n, times, prec, cycle_time=c)


def load_graph(stem):
    """Load a Scholl-1993 graph by (case-insensitive) file stem."""
    for fn in os.listdir(IN2_DIR):
        if fn.upper().endswith(".IN2") and os.path.splitext(fn)[0].upper() == stem.upper():
            return read_in2(os.path.join(IN2_DIR, fn), name=os.path.splitext(fn)[0].capitalize() if False else stem)
    raise FileNotFoundError(stem)


def load_best_known_salbp1():
    """Parse the 'SALBP-1 data set' sheet of the published workbook.
    Returns list of dict(graph, c, m_best, lb, ub, proven_optimal). Columns (per sheet header):
    A graph, B c, C m* (best known), E m* or LB, F m* or UB, H optimum proven (1/0).
    Nothing is invented: values are copied from the published table."""
    import xlsx_dump
    sheets = xlsx_dump.load(XLSX_1993)
    rows = sheets["SALBP-1 data set"]
    out = []
    for r in rows:
        a, b, c = r.get("A"), r.get("B"), r.get("C")
        if not a or not b or not c:
            continue
        try:
            cyc = int(float(b))
            lb = int(float(r["E"])); ub = int(float(r["F"]))
            # C is m* when known; for the single open instance (Wee-mag c=47) it is a range "[LB,UB]":
            # use UB (best known feasible solution value) and keep proven_optimal=0.
            mbest = int(float(c)) if re.fullmatch(r"\d+(\.0+)?", c.strip()) else ub
        except (ValueError, KeyError, TypeError):
            continue
        out.append(dict(graph=a, c=cyc, m_best=mbest, lb=lb, ub=ub,
                        proven_optimal=int(float(r.get("H", "0") or 0))))
    return out


def graph_stem(sheet_name):
    """Map the sheet's graph name to an IN2 file stem."""
    for fn in os.listdir(IN2_DIR):
        if fn.upper().endswith(".IN2"):
            st = os.path.splitext(fn)[0]
            if st.upper() == sheet_name.upper():
                return st
    alias = {"ARCUS1": "ARC83", "ARCUS2": "ARC111", "BOWMAN": "BOWMAN8", "HESKIAOFF": "HESKIA", "KILBRIDGE": "KILBRID", "WEE-MAG": "WEE-MAG", "SAWYER": "SAWYER30", "TONGE": "TONGE70", "BARTHOLD2": "BARTHOL2", "BARTHOLDI": "BARTHOLD"}
    key = alias.get(sheet_name.upper().replace(" ", ""))
    if key:
        return key
    raise FileNotFoundError(sheet_name)


if __name__ == "__main__":
    bk = load_best_known_salbp1()
    print(len(bk), "rows")
    names = sorted(set(r["graph"] for r in bk))
    print(names)
    for nm in names:
        try:
            g = load_graph(graph_stem(nm)); print(nm, g.n, len(g.prec))
        except FileNotFoundError:
            print("MISSING", nm)


# ---------------------------------------------------------------- shared helpers
def transitive_closure(n, prec):
    """Return (succ_sets, pred_sets): dict task -> set of all transitive successors / predecessors."""
    direct = {i: set() for i in range(1, n + 1)}
    for a, b in prec:
        direct[a].add(b)
    succ = {}
    state = {}

    def dfs(u):
        if u in succ:
            return succ[u]
        if state.get(u) == 1:
            raise ValueError("precedence graph has a cycle")
        state[u] = 1
        s = set()
        for v in direct[u]:
            s.add(v)
            s |= dfs(v)
        state[u] = 2
        succ[u] = s
        return s

    sys.setrecursionlimit(10000)
    for i in range(1, n + 1):
        dfs(i)
    pred = {i: set() for i in range(1, n + 1)}
    for u, ss in succ.items():
        for v in ss:
            pred[v].add(u)
    return succ, pred


def validate_solution(inst, c, assign, extra_same=(), extra_incompat=()):
    """assign: list/dict giving station number (>=1) of each task 1..n.
    Checks: every task assigned exactly one station, station load <= c, no precedence violated
    (and optional same-station / incompatible-pair constraints). Raises ValueError if invalid.
    Returns number of stations used (= max station index; empty stations inside are not allowed)."""
    if isinstance(assign, dict):
        st = [assign.get(i) for i in range(1, inst.n + 1)]
        if set(assign) != set(range(1, inst.n + 1)):
            raise ValueError("assignment does not cover exactly tasks 1..n")
    else:
        st = list(assign)
    if len(st) != inst.n or any((s is None or int(s) != s or s < 1) for s in st):
        raise ValueError("every task must be assigned exactly one station >= 1")
    loads = {}
    for i, s in enumerate(st, 1):
        loads[s] = loads.get(s, 0) + inst.times[i - 1]
    for s, l in loads.items():
        if l > c:
            raise ValueError(f"station {s} load {l} exceeds cycle time {c}")
    for a, b in inst.prec:
        if st[a - 1] > st[b - 1]:
            raise ValueError(f"precedence {a}->{b} violated (stations {st[a-1]}>{st[b-1]})")
    for a, b in extra_same:
        if st[a - 1] != st[b - 1]:
            raise ValueError(f"same-station {a},{b} violated")
    for a, b in extra_incompat:
        if st[a - 1] == st[b - 1]:
            raise ValueError(f"incompatible {a},{b} share a station")
    return max(st)
