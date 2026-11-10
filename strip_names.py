"""Spec 04 B7/B6 post-process: replace the title line of every L1..L4 sheet with a neutral one and drop the extra L4
hint sentence. Idempotent. usage: strip_names.py [--dir data/salbp_nl]"""
import os, re, sys, json, glob, argparse
HERE = os.path.dirname(os.path.abspath(__file__))
HINT = " Operations are referred to by name."


def names_for(truth, base):
    src = truth["_meta"]["source"]
    toks = {base}
    m = re.search(r"instance_n=\d+_\d+", src)
    if m:
        toks |= {m.group(0), m.group(0).replace("instance_n=", "")}
    else:
        toks.add(src.split("/")[-1].strip())
    return {t for t in toks if t}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(HERE, "data", "salbp_nl"))
    a = ap.parse_args()
    bases = sorted({re.sub(r"_L\d\.md$", "", os.path.basename(f)) for f in glob.glob(os.path.join(a.dir, "*_L[1-4].md"))})
    assert len(bases) == 50, len(bases)
    sid = {b: f"S{k:02d}" for k, b in enumerate(bases, 1)}
    titles = hints = leaks = 0
    for b in bases:
        for lv in (1, 2, 3, 4):
            f = os.path.join(a.dir, f"{b}_L{lv}.md")
            truth = json.load(open(f[:-3] + ".truth.json"))
            n = truth["_meta"]["n"]
            lines = open(f).read().split("\n")
            assert lines[0].startswith("# Routing sheet: "), f
            new = f"# Routing sheet: smartphone final assembly line - sheet {sid[b]} ({n} operations)"
            if lines[0] != new:
                lines[0] = new; titles += 1
            txt = "\n".join(lines)
            if lv == 4 and HINT in txt:
                txt = txt.replace(HINT, ""); hints += 1
            for nm in names_for(truth, b):
                if re.search(re.escape(nm), txt, re.I):
                    leaks += 1; print("LEAK", f, nm)
            open(f, "w").write(txt)
    print(f"title lines replaced: {titles}; L4 hint sentences removed: {hints}; instance-name leaks: {leaks}")
    json.dump(sid, open(os.path.join(a.dir, "..", "sid_map.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
