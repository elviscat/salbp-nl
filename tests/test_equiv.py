import os, sys, copy, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from model_equiv import check_equivalent, transitive_reduction
import solve_rpw, solve_cpsat, salbp_io

TRUTH = {"tasks": [{"id": i, "time_s": 10 + i} for i in range(1, 6)],
         "precedence": [[1, 2], [2, 3], [1, 3], [3, 4], [1, 5]],  # [1,3] is redundant (1->2->3)
         "same_station": [[4, 5]], "incompatible": [[2, 5]], "objective": "SALBP-1", "cycle_time_s": 40}


class T(unittest.TestCase):
    def test_self(self):
        ok, d = check_equivalent(copy.deepcopy(TRUTH), TRUTH)
        self.assertTrue(ok, d)

    def test_drop_nonredundant(self):
        p = copy.deepcopy(TRUTH); p["precedence"].remove([2, 3])  # 1->2->3 no longer implied; 1->3 still gives 1->3 but not 2->3
        ok, d = check_equivalent(p, TRUTH)
        self.assertFalse(ok)
        self.assertIn("precedence_missing", [x["kind"] for x in d])

    def test_drop_redundant(self):
        p = copy.deepcopy(TRUTH); p["precedence"].remove([1, 3])
        ok, d = check_equivalent(p, TRUTH)
        self.assertTrue(ok, d)

    def test_other_diffs(self):
        p = copy.deepcopy(TRUTH); p["tasks"][0]["time_s"] = 99; p["same_station"] = []; p["tasks"].pop()
        ok, d = check_equivalent(p, TRUTH)
        kinds = {x["kind"] for x in d}
        self.assertFalse(ok)
        self.assertTrue({"wrong_time", "same_station_missing", "missing_task"} <= kinds)

    def test_unordered_pairs(self):
        p = copy.deepcopy(TRUTH); p["same_station"] = [[5, 4]]
        self.assertTrue(check_equivalent(p, TRUTH)[0])

    def test_reduction(self):
        self.assertEqual(sorted(transitive_reduction([1, 2, 3, 4, 5], TRUTH["precedence"])),
                         [(1, 2), (1, 5), (2, 3), (3, 4)])


class SolverSanity(unittest.TestCase):
    def test_validator_rejects(self):
        g = salbp_io.Instance("t", 3, [5, 5, 5], [(1, 2), (2, 3)])
        with self.assertRaises(ValueError): salbp_io.validate_solution(g, 10, [2, 1, 1])   # precedence
        with self.assertRaises(ValueError): salbp_io.validate_solution(g, 9, [1, 1, 2])    # load
        self.assertEqual(salbp_io.validate_solution(g, 10, [1, 1, 2]), 2)

    def test_rpw_cpsat_agree_small(self):
        g = salbp_io.load_graph("MERTENS")
        m, _ = solve_rpw.rpw(g, 6)
        r = solve_cpsat.solve_salbp1(g, 6, 10, 2)
        self.assertEqual(r["status"], "OPTIMAL"); self.assertLessEqual(r["m"], m)


if __name__ == "__main__":
    unittest.main(verbosity=2)
