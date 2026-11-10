"""LLM arm skeleton (NOT executed in this task): NL routing sheet -> JSON model via NVIDIA NIM (OpenAI-compatible).
Needs env var NVIDIA_API_KEY (read from the environment only; this code never stores or prints it).
The validator does NOT compare against ground truth: it only checks schema and that precedence is a DAG.
Failures are fed back to the model for up to --max-rounds rounds.

usage: NVIDIA_API_KEY=... python llm_modeler.py --model <model-name-from-build.nvidia.com> data/salbp_nl/x.md [--out DIR]
"""
import os, sys, json, argparse, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MODEL = os.environ.get("NIM_MODEL", "nvidia/nemotron-placeholder-set-me")  # parametrised: set via --model or NIM_MODEL

SCHEMA_TEXT = """Return ONLY one JSON object, no prose, with exactly these keys:
{"tasks":[{"id":1,"time_s":12}], "precedence":[[1,3]], "same_station":[[4,5]], "incompatible":[[2,9]],
 "objective":"SALBP-1", "cycle_time_s":54}
Rules: ids are the task numbers in the sheet; ALL times and the cycle time must be converted to integer seconds;
precedence [a,b] means task a must be finished before task b starts (list the relations stated in the sheet);
same_station / incompatible hold unordered pairs of task ids (empty lists if none); objective is always "SALBP-1"."""

SYSTEM = "You convert industrial-engineering routing sheets into exact optimisation-model data. Be precise; never invent tasks or relations."


def extract_json(text):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    else:
        i, j = text.find("{"), text.rfind("}")
        if i < 0 or j < 0:
            raise ValueError("no JSON object found")
        text = text[i:j + 1]
    return json.loads(text)


def validate_model(obj):
    """Schema + DAG check only (no ground truth). Returns list of error strings (empty = ok)."""
    errs = []
    if not isinstance(obj, dict):
        return ["top level must be an object"]
    for k in ("tasks", "precedence", "same_station", "incompatible", "objective", "cycle_time_s"):
        if k not in obj:
            errs.append(f"missing key '{k}'")
    if errs:
        return errs
    ids = []
    for t in obj["tasks"]:
        if not (isinstance(t, dict) and isinstance(t.get("id"), int) and isinstance(t.get("time_s"), int) and t["time_s"] > 0):
            errs.append(f"bad task entry {t!r} (need int id and positive int time_s)")
        else:
            ids.append(t["id"])
    if len(ids) != len(set(ids)):
        errs.append("duplicate task ids")
    if not isinstance(obj["cycle_time_s"], int) or obj["cycle_time_s"] <= 0:
        errs.append("cycle_time_s must be a positive integer")
    if obj["objective"] != "SALBP-1":
        errs.append('objective must be "SALBP-1"')
    idset = set(ids)
    for key in ("precedence", "same_station", "incompatible"):
        for p in obj[key]:
            if not (isinstance(p, list) and len(p) == 2 and all(isinstance(x, int) for x in p)):
                errs.append(f"{key}: bad pair {p!r}")
            elif p[0] not in idset or p[1] not in idset:
                errs.append(f"{key}: pair {p!r} references an unknown task id")
            elif p[0] == p[1]:
                errs.append(f"{key}: self pair {p!r}")
    if not errs:  # DAG check (Kahn)
        indeg = {i: 0 for i in idset}
        adj = {i: [] for i in idset}
        for a, b in obj["precedence"]:
            adj[a].append(b); indeg[b] += 1
        q = [i for i in idset if indeg[i] == 0]; seen = 0
        while q:
            u = q.pop(); seen += 1
            for v in adj[u]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
        if seen != len(idset):
            errs.append("precedence graph contains a cycle")
    return errs


def run(md_path, model, max_rounds=3, temperature=0.0):
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        print("NVIDIA_API_KEY is not set in the environment; nothing was called. "
              "Export it yourself (never paste it into files), then rerun.")
        return None
    from openai import OpenAI  # not installed in the experiment venv by design; install only when running this arm
    client = OpenAI(base_url=BASE_URL, api_key=key)
    sheet = open(md_path).read()
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{sheet}\n\n---\n{SCHEMA_TEXT}"}]
    result, rounds_log = None, []
    for r in range(1, max_rounds + 1):
        resp = client.chat.completions.create(model=model, messages=msgs, temperature=temperature)
        txt = resp.choices[0].message.content
        try:
            obj = extract_json(txt)
            errs = validate_model(obj)
        except Exception as e:  # noqa
            obj, errs = None, [f"could not parse JSON: {e}"]
        rounds_log.append(dict(round=r, errors=errs))
        if not errs:
            result = obj
            break
        msgs += [{"role": "assistant", "content": txt},
                 {"role": "user", "content": "The JSON failed validation:\n- " + "\n- ".join(errs[:20]) + "\nFix these problems and return the full corrected JSON only."}]
    return dict(model=obj if result else None, valid=result is not None, rounds=rounds_log)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = run(a.md, a.model, a.max_rounds)
    if out is not None:
        s = json.dumps(out, indent=1)
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            open(os.path.join(a.out, os.path.basename(a.md).replace(".md", ".pred.json")), "w").write(s)
        else:
            print(s)
