"""Spec 04 B4: freeze manifest. sha256 of the NL sheets + truth files, the modeler prompt code, the runner, the summarizer and
the rule parser; written to results/freeze_manifest.json (UTC time; git commit hash is added by freeze_commit step if present).
usage: freeze_manifest.py"""
import os, glob, json, hashlib, datetime, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    files = sorted(glob.glob(os.path.join(HERE, "data", "salbp_nl", "*.md")) + glob.glob(os.path.join(HERE, "data", "salbp_nl", "*.truth.json")))
    files += [os.path.join(HERE, n) for n in ("llm_modeler.py", "run_expB.py", "summarize_expB.py", "rule_parser.py")]
    man = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               note="llm_modeler.py contains SYSTEM and SCHEMA_TEXT; commit hash = the freeze commit in exp/ (see git log)",
               files={os.path.relpath(f, HERE): sha(f) for f in files})
    try:
        man["git_head_at_manifest_time"] = subprocess.run(["git", "-C", HERE, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa
        man["git_head_at_manifest_time"] = ""
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    out = os.path.join(HERE, "results", "freeze_manifest.json")
    if os.path.exists(out):
        old = json.load(open(out))
        if "git_commit" in old:
            man["git_commit"] = old["git_commit"]  # keep the hash recorded by an earlier freeze commit
    json.dump(man, open(out, "w"), indent=1)
    print(f"{len(man['files'])} files hashed -> {out}")


if __name__ == "__main__":
    main()
