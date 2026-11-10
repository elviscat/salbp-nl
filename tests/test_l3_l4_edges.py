"""Edge-level check of L3 and L4 sheets: parse every sentence of 'Process-flow notes' and 'Station rules' back into
edges, compare the transitive closure with the truth closure; same-station and incompatible sets must match exactly.
Any unparseable line fails. L4 maps quoted operation names back to ids through the Operations list."""
import os, re, sys, json, glob, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get("SALBP_NL_DIR", os.path.join(HERE, "..", "data", "salbp_nl"))

sys.path.insert(0, os.path.join(HERE, ".."))
from rule_parser import closure, parse_sheet as _ps


def parse_sheet(md, level):
    return _ps(md, level)


class T(unittest.TestCase):
    def test_edges(self):
        for level in (3, 4):
            files = sorted(glob.glob(os.path.join(D, f"*_L{level}.md")))
            self.assertEqual(len(files), 50, f"L{level} file count")
            for f in files:
                tr = json.load(open(f[:-3] + ".truth.json"))
                self.assertEqual(tr["_meta"]["level"], f"L{level}")
                ids = [t["id"] for t in tr["tasks"]]
                edges, same, inc, bad = parse_sheet(open(f).read(), level)
                self.assertEqual(bad, [], f)
                self.assertEqual(closure(edges, ids), closure([tuple(p) for p in tr["precedence"]], ids), f)
                self.assertEqual(same, {tuple(sorted(p)) for p in tr["same_station"]}, f)
                self.assertEqual(inc, {tuple(sorted(p)) for p in tr["incompatible"]}, f)

    def test_no_bad_phrase(self):
        for f in glob.glob(os.path.join(D, "*_L3.md")):
            self.assertNotIn("is not before", open(f).read(), f)

    def test_l4_has_no_task_refs_outside_operations(self):
        for f in glob.glob(os.path.join(D, "*_L4.md")):
            body = open(f).read().split("## Process-flow notes")[1]
            self.assertIsNone(re.search(r"(?i)\btasks? \d+", body), f)


if __name__ == "__main__":
    unittest.main(verbosity=2)
