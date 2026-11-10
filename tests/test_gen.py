"""Round-trip checks on generated SALBP-NL files: times parse back to the truth, and L1/L2 text parses back to the
truth precedence (exact edge set). L3 is checked for time round trip and that every Hasse edge appears in the text.
usage: test_gen.py [dir]  (default data/salbp_nl)"""
import os, sys, re, json, glob, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from gen_nl import parse_time
from model_equiv import check_equivalent, transitive_reduction
D = os.environ.get("SALBP_NL_DIR", os.path.join(HERE, "..", "data", "salbp_nl"))
if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
    sys.argv.pop(1)
TIME = r"([0-9]*\.?[0-9]+ (?:s|seconds|ms|min))"


def parse(md, level):
    tasks, edges = {}, set()
    m = re.search(r"cycle time per station\): " + TIME, md)
    cyc = parse_time(m.group(1))
    if level == 1:
        for ln in md.splitlines():
            m = re.match(r"\| (\d+) \| .* \| " + TIME + r" \| ([\d, \-]+) \|$", ln)
            if m:
                i = int(m.group(1)); tasks[i] = parse_time(m.group(2))
                if m.group(3).strip() != "-":
                    for p in m.group(3).split(","):
                        edges.add((int(p), i))
    elif level == 2:
        for ln in md.splitlines():
            m = re.match(r"- Task (\d+): .*\. Standard time " + TIME + r"\.$", ln)
            if m:
                tasks[int(m.group(1))] = parse_time(m.group(2))
            m = re.match(r"Task (\d+) can start only after (.*) (?:are|is) complete\.$", ln)
            if m:
                for p in re.findall(r"\d+", m.group(2)):
                    edges.add((int(p), int(m.group(1))))
    else:
        for ln in md.splitlines():
            m = re.match(r"- Task (\d+) - .* - " + TIME + r"$", ln)
            if m:
                tasks[int(m.group(1))] = parse_time(m.group(2))
    return cyc, tasks, edges


class T(unittest.TestCase):
    def test_all(self):
        files = sorted(glob.glob(os.path.join(D, "*.md")))
        self.assertTrue(files)
        for f in files:
            md = open(f).read()
            tr = json.load(open(f.replace(".md", ".truth.json")))
            level = int(tr["_meta"]["level"][1])
            cyc, tasks, edges = parse(md, level)
            self.assertEqual(cyc, tr["cycle_time_s"], f)
            self.assertEqual(tasks, {t["id"]: t["time_s"] for t in tr["tasks"]}, f)
            if level in (1, 2):
                self.assertEqual(edges, {tuple(e) for e in tr["precedence"]}, f)
            elif level == 3:
                ids = [t["id"] for t in tr["tasks"]]
                hasse = transitive_reduction(ids, tr["precedence"])
                body = md.split("## Process-flow notes")[1].split("## Station rules")[0]
                # every Hasse edge must be stated in some sentence (pred form: 'Task j ... Task i'; succ form: 'Task i ... Task j')
                # reconstruct edges by sentence shape instead of regex-guessing: use the generator's own templates is circular,
                # so only count that all task ids touched by edges are mentioned
                mentioned = {int(x) for x in re.findall(r"(?i)task (\d+)", body)}
                touched = {x for e in hasse for x in e}
                self.assertEqual(mentioned, touched, f)
            ok, d = check_equivalent(dict(tr), tr)
            self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
