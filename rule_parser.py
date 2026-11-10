"""Zero-LLM rule parser for SALBP-NL sheets (Spec 04, B5). Parses an L1..L4 sheet back into the same JSON schema the
LLM arms must produce. Any line it cannot parse raises ParseError (the job is then a failure; nothing is guessed).
The sentence patterns are shared with tests/test_l3_l4_edges.py (which imports this module)."""
import re

E3 = r"Task \d+(?:, Task \d+)*(?: and Task \d+)?"
E4 = r'"[^"]+"(?:, "[^"]+")*(?: and "[^"]+")?'
A3, A4 = r"\d+", r'"[^"]+"'
TIME = r"([0-9]*\.?[0-9]+ (?:s|seconds|ms|min))"


class ParseError(Exception):
    pass


def parse_time(s):
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+)\s*(s|seconds|ms|min)\s*", s)
    if not m:
        raise ParseError("time: " + s)
    v, u = float(m.group(1)), m.group(2)
    sec = {"s": v, "seconds": v, "ms": v / 1000.0, "min": v * 60.0}[u]
    r = round(sec)
    if abs(sec - r) > 1e-6:
        raise ParseError("non-integer seconds: " + s)
    return int(r)


def pred_pats(E):
    return [rf"({E}) must follow ({E})", rf"({E}) requires ({E}) beforehand",
            rf"({E}) cannot be scheduled before ({E}) (?:is|are) finished",
            rf"({E}) may only begin once ({E}) (?:is|are) done",
            rf"Do not start ({E}) until ({E}) (?:has|have) been completed",
            rf"({E}) does not start before ({E}) (?:is|are) finished",
            rf"({E}) comes after ({E}) in the process flow"]


def succ_pats(E):
    return [rf"({E}) has to be finished before ({E}) can start", rf"({E}) is a prerequisite of ({E})", rf"({E}) precedes ({E})"]


def succ2_pats(E):  # group 1 = successors S, group 2 = I
    return [rf"({E}) must not start earlier than ({E}) ends"]


def pair_pats(A):
    same = [rf"Tasks ({A}) and ({A}) both use the .+ fixture and must be done at the same station",
            rf"Zone rule: task ({A}) and task ({A}) share the .+ and therefore have to be assigned to the same station",
            rf"Because of the shared .+, tasks ({A}) and ({A}) must not be split across stations"]
    inc = [rf"Tasks ({A}) and ({A}) cannot be performed at the same station",
           rf"Incompatibility: task ({A}) and task ({A}) must never share a station \(contamination risk\)",
           rf"Do not put tasks ({A}) and ({A}) together at one station"]
    return same, inc


def closure(edges, ids):
    succ = {i: set() for i in ids}
    for a, b in edges:
        succ[a].add(b)
    changed = True
    while changed:
        changed = False
        for i in ids:
            new = set().union(*[succ[j] for j in succ[i]]) - succ[i] if succ[i] else set()
            if new:
                succ[i] |= new
                changed = True
    return {(a, b) for a in ids for b in succ[a]}


def detect_level(md):
    if "| ID | Operation |" in md:
        return 1
    if "## Sequence rules" in md:
        return 2
    if "## Process-flow notes" in md:
        flow = md.split("## Process-flow notes")[1].split("## Station rules")[0]
        return 4 if re.search(r'"[^"]+"', flow) else 3
    raise ParseError("unknown sheet layout")


def parse_ops(md, level):
    """Return (times {id: seconds}, names {name: id} for L4)."""
    times, names = {}, {}
    if level == 1:
        for ln in md.splitlines():
            m = re.match(r"\| (\d+) \| (.*) \| " + TIME + r" \| ([\d, \-]+) \|$", ln)
            if m:
                times[int(m.group(1))] = parse_time(m.group(3))
    elif level == 2:
        for ln in md.splitlines():
            m = re.match(r"- Task (\d+): (.*)\. Standard time " + TIME + r"\.$", ln)
            if m:
                times[int(m.group(1))] = parse_time(m.group(3))
    else:
        for ln in md.split("## Process-flow notes")[0].splitlines():
            m = re.match(r"- Task (\d+) - (.*) - " + TIME + r"$", ln)
            if m:
                i = int(m.group(1))
                times[i] = parse_time(m.group(3))
                if m.group(2) in names:
                    raise ParseError("duplicate name " + m.group(2))
                names[m.group(2)] = i
    if not times:
        raise ParseError("no operations found")
    return times, names


def parse_sheet(md, level):
    """-> (edges, same, inc, bad). bad = lines that matched no known pattern."""
    names = parse_ops(md, level)[1] if level == 4 else {}
    ent, A, E = (r"Task (\d+)", A3, E3) if level != 4 else (r'"([^"]+)"', A4, E4)
    conv = (lambda s: names[s]) if level == 4 else int
    ids_of = lambda s: [conv(x) for x in re.findall(ent, s)]
    one = lambda s: conv(s.strip('"')) if level == 4 else int(s)
    edges, same, inc, bad = set(), set(), set(), []
    if level == 1:
        for ln in md.splitlines():
            m = re.match(r"\| (\d+) \| .* \| " + TIME + r" \| ([\d, \-]+) \|$", ln)
            if m and m.group(3).strip() != "-":
                for p in m.group(3).split(","):
                    edges.add((int(p), int(m.group(1))))
    elif level == 2:
        for ln in md.splitlines():
            m = re.match(r"Task (\d+) can start only after (.*) (?:are|is) complete\.$", ln)
            if m:
                for p in re.findall(r"\d+", m.group(2)):
                    edges.add((int(p), int(m.group(1))))
    else:
        flow = md.split("## Process-flow notes")[1].split("## Station rules")[0]
        for ln in flow.splitlines():
            if not ln.startswith("- "):
                continue
            s = ln[2:]
            s = s[:-1] if s.endswith(".") else s
            for p in pred_pats(E):
                m = re.fullmatch(p, s)
                if m:
                    (j,) = ids_of(m.group(1))
                    edges |= {(i, j) for i in ids_of(m.group(2))}
                    break
            else:
                for p in succ_pats(E):
                    m = re.fullmatch(p, s)
                    if m:
                        (i,) = ids_of(m.group(1))
                        edges |= {(i, j) for j in ids_of(m.group(2))}
                        break
                else:
                    for p in succ2_pats(E):
                        m = re.fullmatch(p, s)
                        if m:
                            (i,) = ids_of(m.group(2))
                            edges |= {(i, j) for j in ids_of(m.group(1))}
                            break
                    else:
                        bad.append(ln)
    rules = md.split("## Station rules")[1] if "## Station rules" in md else ""
    ps, pi = pair_pats(A)
    for ln in rules.splitlines():
        if not ln.startswith("- "):
            continue
        s = ln[2:]
        s = s[:-1] if s.endswith(".") else s
        for pats, dst in ((ps, same), (pi, inc)):
            for p in pats:
                m = re.fullmatch(p, s)
                if m:
                    dst.add(tuple(sorted((one(m.group(1)), one(m.group(2))))))
                    break
            else:
                continue
            break
        else:
            bad.append(ln)
    return edges, same, inc, bad


def sheet_to_model(md):
    """NL sheet -> JSON model in the LLM schema. Raises ParseError on anything unparseable."""
    try:
        level = detect_level(md)
        times, _ = parse_ops(md, level)
        edges, same, inc, bad = parse_sheet(md, level)
        if bad:
            raise ParseError("unparsed line: " + bad[0][:80])
        m = re.search(r"cycle time per station\): " + TIME, md)
        if not m:
            raise ParseError("no cycle time")
        return {"tasks": [{"id": i, "time_s": times[i]} for i in sorted(times)],
                "precedence": [list(e) for e in sorted(edges)],
                "same_station": [list(p) for p in sorted(same)], "incompatible": [list(p) for p in sorted(inc)],
                "objective": "SALBP-1", "cycle_time_s": parse_time(m.group(1))}
    except ParseError:
        raise
    except Exception as e:  # noqa  KeyError for an unknown quoted name etc. -> failure, not a guess
        raise ParseError(f"{type(e).__name__}:{e}")
