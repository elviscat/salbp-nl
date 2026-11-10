"""Verify results/freeze_manifest.json without writing anything (Spec 10 item 2).
Recomputes the sha256 of every listed file and compares it with the manifest; also compares the manifest's hash list with the
copy stored in a git commit (git show <ref>:results/freeze_manifest.json) when exp/ is inside a git repo.
Run (from exp/): .venv/bin/python -I poster_fill/verify_manifest.py [--manifest results/freeze_manifest.json] [--ref be449169]"""
import os, sys, json, hashlib, argparse, subprocess

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=os.path.join("results", "freeze_manifest.json"))
    ap.add_argument("--ref", default="be449169")
    a = ap.parse_args()
    mp = a.manifest if os.path.isabs(a.manifest) else os.path.join(HERE, a.manifest)
    man = json.load(open(mp))
    files = man["files"]
    bad = []
    for rel, h in files.items():
        p = os.path.join(HERE, rel)
        if not os.path.exists(p):
            bad.append((rel, "missing"))
        elif hashlib.sha256(open(p, "rb").read()).hexdigest() != h:
            bad.append((rel, "hash differs"))
    ok = len(files) - len(bad)
    if not bad:
        print(f"OK {ok}/{len(files)}")
    else:
        print(f"MISMATCH {ok}/{len(files)} match; differing files:")
        for rel, why in bad:
            print(f"  {rel}: {why}")
    rc = 1 if bad else 0
    try:
        r = subprocess.run(["git", "-C", HERE, "show", f"{a.ref}:results/freeze_manifest.json"], capture_output=True, text=True)
    except OSError as e:
        r = None
        print(f"git comparison skipped (git not available: {e})")
    if r is not None:
        if r.returncode != 0:
            print(f"git comparison skipped (not a git repo, or {a.ref}:results/freeze_manifest.json not found): {r.stderr.strip()[:120]}")
        else:
            ref_files = json.loads(r.stdout)["files"]
            diff = sorted(k for k in set(files) | set(ref_files) if files.get(k) != ref_files.get(k))
            if not diff:
                print(f"git {a.ref}: manifest hash list identical ({len(ref_files)} files)")
            else:
                rc = 1
                print(f"git {a.ref}: manifest hash list DIFFERS in {len(diff)} entries:")
                for k in diff[:20]:
                    print(f"  {k}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
