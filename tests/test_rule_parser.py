import os, sys, json, glob, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rule_parser as RP
from model_equiv import check_equivalent
import run_expB as R
D = os.environ.get("SALBP_NL_DIR", os.path.join(HERE, "..", "data", "salbp_nl"))


class T(unittest.TestCase):
    def test_parser_equivalent_on_all_sheets(self):
        files = sorted(glob.glob(os.path.join(D, "*.md")))
        self.assertEqual(len(files), 200)
        for f in files:
            tr = json.load(open(f[:-3] + ".truth.json"))
            obj = RP.sheet_to_model(open(f).read())
            self.assertEqual(R.validate_full(obj), [], f)
            ok, d = check_equivalent(obj, tr)
            self.assertTrue(ok, (f, d[:2]))

    def test_gibberish_flow_line_raises(self):
        md = open(os.path.join(D, "otto_n20_i106_L3.md")).read().replace("## Process-flow notes\n", "## Process-flow notes\n\n- Gibberish about tasks.\n", 1)
        with self.assertRaises(RP.ParseError):
            RP.sheet_to_model(md)


if __name__ == "__main__":
    unittest.main()
