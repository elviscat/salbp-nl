import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import run_expB as R


class T(unittest.TestCase):
    def test_retry_transient_then_ok(self):
        n = []

        def f():
            n.append(1)
            if len(n) < 3:
                raise R.TransientError(503)
            return "ok"
        self.assertEqual(R.with_retry(f, 3, 0.001), "ok")

    def test_retry_gives_up_and_nontransient(self):
        n = []

        def always():
            n.append(1)
            raise R.TransientError(429)
        with self.assertRaises(R.TransientError):
            R.with_retry(always, 3, 0.001)
        self.assertEqual(len(n), 4)  # 1 try + 3 retries
        m = []

        def bad():
            m.append(1)
            raise R.TransientError(400)
        with self.assertRaises(R.TransientError):
            R.with_retry(bad, 3, 0.001)
        self.assertEqual(len(m), 1)

    def test_validator_contiguous_ids(self):
        m = {"tasks": [{"id": 1, "time_s": 5}, {"id": 3, "time_s": 5}], "precedence": [], "same_station": [],
             "incompatible": [], "objective": "SALBP-1", "cycle_time_s": 10}
        self.assertTrue(any("consecutive" in e for e in R.validate_full(m)))


if __name__ == "__main__":
    unittest.main()
