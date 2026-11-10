"""Experiment B: LLM arms on SALBP-NL (NVIDIA NIM, OpenAI-compatible API).

Arms
  dprime : single-shot NL -> JSON model, no feedback            (d')
  d      : same, but validator feedback, up to --max-rounds     (d)
  c      : LLM outputs the station assignment directly          (c)
For d / d' the predicted model is compared with the truth (model_equiv), solved with CP-SAT (60 s) and the
resulting assignment is re-checked on the TRUTH constraints. The validator never sees the truth.

Results are appended row by row to results/expB.csv; reruns skip finished (arm, id, seed) rows.
Real mode needs NVIDIA_API_KEY in the environment (read by the openai client only; never printed or stored).
--dry-run uses a built-in FakeClient and writes to results/dryrun/ instead.
"""
import os, sys, re, csv, json, time, glob, argparse, threading, random
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from salbp_io import Instance, validate_solution
from model_equiv import check_equivalent, transitive_reduction
from solve_cpsat import solve_salbp1
import llm_modeler as LM
import rule_parser as RP

NL_DIR = os.environ.get("SALBP_NL_DIR", os.path.join(HERE, "data", "salbp_nl"))
RES = os.path.join(HERE, "results")
TEMPERATURE = 0.2
ARM_NAMES = {"c": "c", "d": "d", "dprime": "dprime", "r": "r"}  # r = rule parser, zero LLM (Spec 04 B5)
COLS = ["arm", "id", "level", "seed", "equiv", "valid", "diff", "rounds", "prompt_tokens", "completion_tokens",
        "latency_s", "finish_reason", "solve_s", "stations", "feasible_on_truth", "truth_m", "gap", "hit_best", "error",
        "hit_le", "hit_eq", "trivial_lb", "truth_m_min", "truth_m_max", "oracle_unstable",
        "diff_taskset", "diff_time", "diff_closure", "diff_zone"]  # hit_best == hit_le (kept for compatibility)

STATION_REQ = ("""Now assign every operation to a station directly. Return ONLY one JSON object, no prose:
{"stations": [[ids of the operations at station 1], [ids at station 2], ...]}
Every task id must appear exactly once; stations are numbered in the order listed; a station's total standard time
(in seconds, convert units first) must not exceed the cycle time; all precedence, same-station and incompatibility
rules in the sheet must hold; use as few stations as possible.""")


# ------------------------------------------------------------------ retry + clients
class TransientError(Exception):
    def __init__(self, status_code, msg=""):
        super().__init__(f"{status_code} {msg}")
        self.status_code = status_code


def is_transient(e):
    sc = getattr(e, "status_code", None)
    if sc is not None:
        return sc == 429 or sc >= 500
    return type(e).__name__ in ("APIConnectionError", "APITimeoutError", "RateLimitError", "InternalServerError")


def with_retry(fn, retries=3, base_delay=2.0):
    """Call fn(); on transient errors (429 / 5xx / connection) retry up to `retries` times with exponential backoff."""
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:  # noqa
            if attempt < retries and is_transient(e):
                time.sleep(base_delay * (2 ** attempt) * (0.5 + random.random() / 2))
                continue
            raise


class RealClient:
    def __init__(self, model, max_tokens):
        key = os.environ.get("NVIDIA_API_KEY")
        if not key:
            print("NVIDIA_API_KEY is not set in the environment; nothing was called. "
                  "Export it yourself (never paste it into files), then rerun.")
            sys.exit(0)
        from openai import OpenAI
        self.c = OpenAI(base_url=LM.BASE_URL, api_key=key, max_retries=0, timeout=300)
        self.model, self.max_tokens = model, max_tokens
        self.seed_ok = True

    def chat(self, messages, seed, meta=None):
        def go():
            kw = dict(model=self.model, messages=messages, temperature=TEMPERATURE, max_tokens=self.max_tokens)
            if self.seed_ok:
                kw["seed"] = seed
            try:
                return self.c.chat.completions.create(**kw)
            except Exception as e:  # noqa
                if self.seed_ok and getattr(e, "status_code", None) == 400 and "seed" in str(e).lower():
                    self.seed_ok = False  # endpoint rejects seed: seeds then only index repeated samples
                    kw.pop("seed")
                    return self.c.chat.completions.create(**kw)
                raise
        t0 = time.time()
        r = with_retry(go)
        u = r.usage
        fr = getattr(r.choices[0], "finish_reason", None) or ""
        return (r.choices[0].message.content or ""), (u.prompt_tokens if u else 0), (u.completion_tokens if u else 0), time.time() - t0, fr


class FakeClient:
    """Deterministic stand-in: seed%3==1 truth model, 2 drops one Hasse edge (non-equivalent), 0 starts with a cyclic
    (invalid) model and returns the truth after validator feedback. Also fails once with a 429 to exercise the retry."""
    def __init__(self):
        self.lock = threading.Lock(); self.failed_once = False

    def chat(self, messages, seed, meta=None):
        t0 = time.time()
        with self.lock:
            inject = not self.failed_once
            self.failed_once = True
        if inject:
            calls = []

            def flaky():
                calls.append(1)
                if len(calls) == 1:
                    raise TransientError(429, "fake rate limit")
                return True
            with_retry(flaky, retries=2, base_delay=0.01)  # first attempt fails, retry succeeds
        truth = {k: v for k, v in meta.items() if not k.startswith("_")}
        prompt = "".join(m["content"] for m in messages)
        if '"stations"' in messages[-1]["content"]:
            text = self._assign(truth, seed)
        else:
            text = self._model(truth, seed, feedback=len(messages) > 2)
        return "```json\n" + text + "\n```", len(prompt) // 4, len(text) // 4, time.time() - t0, "stop"

    @staticmethod
    def _model(truth, seed, feedback):
        m = json.loads(json.dumps(truth))
        ids = [t["id"] for t in m["tasks"]]
        if seed % 3 == 2:
            red = transitive_reduction(ids, m["precedence"])
            if red:
                m["precedence"] = [p for p in m["precedence"] if tuple(p) != red[0]]
        elif seed % 3 == 0 and not feedback and m["precedence"]:
            a, b = m["precedence"][0]
            m["precedence"] = m["precedence"] + [[b, a]]  # creates a cycle -> validator rejects
        return json.dumps(m)

    @staticmethod
    def _assign(truth, seed):
        ids = [t["id"] for t in truth["tasks"]]
        tm = {t["id"]: t["time_s"] for t in truth["tasks"]}
        c = truth["cycle_time_s"]
        preds = {i: set() for i in ids}
        for a, b in truth["precedence"]:
            preds[b].add(a)
        done, order = set(), []
        while len(order) < len(ids):  # greedy topological packing (ignores same/incompatible rules)
            ready = [i for i in ids if i not in done and preds[i] <= done]
            order.append(ready[0]); done.add(ready[0])
        sts, cur, load = [], [], 0
        for i in order:
            if load + tm[i] > c and cur:
                sts.append(cur); cur, load = [], 0
            cur.append(i); load += tm[i]
        sts.append(cur)
        if seed % 3 == 2:  # drop a task -> infeasible
            sts[-1] = sts[-1][:-1] or sts[-1]
            if len(sts[-1]) == 1 and len(order) == sum(map(len, sts)):
                sts[-1] = []
        return json.dumps({"stations": sts})


# ------------------------------------------------------------------ helpers
def load_items(levels, limit):
    items = []
    for md in sorted(glob.glob(os.path.join(NL_DIR, "*.md"))):
        stem = os.path.basename(md)[:-3]
        truth = json.load(open(md[:-3] + ".truth.json"))
        lv = truth["_meta"]["level"]
        if lv in levels:
            items.append(dict(id=stem, base=re.sub(r"_L\d$", "", stem), level=lv, sheet=open(md).read(), truth=truth))
    if limit:
        items = items[:limit]
    return items


def truth_instance(truth):
    ids = sorted(t["id"] for t in truth["tasks"])
    assert ids == list(range(1, len(ids) + 1)), "truth ids must be 1..n"
    tm = {t["id"]: t["time_s"] for t in truth["tasks"]}
    return Instance("truth", len(ids), [tm[i] for i in ids], [tuple(p) for p in truth["precedence"]])


def truth_constraints(truth):
    return ([tuple(p) for p in truth["same_station"]], [tuple(p) for p in truth["incompatible"]])


def validate_full(obj):
    """Schema + DAG (llm_modeler.validate_model) + ids contiguous 1..n. Never looks at the ground truth."""
    errs = LM.validate_model(obj)
    if not errs:
        ids = sorted(t["id"] for t in obj["tasks"])
        if ids != list(range(1, len(ids) + 1)):
            errs.append("task ids must be consecutive integers 1..n")
    return errs


def model_user_msg(sheet):
    return f"{sheet}\n\n---\n{LM.SCHEMA_TEXT}"


def feedback_msg(errs):
    return "The JSON failed validation:\n- " + "\n- ".join(errs[:20]) + "\nFix these problems and return the full corrected JSON only."


def pred_instance(obj):
    ids = sorted(t["id"] for t in obj["tasks"])
    tm = {t["id"]: t["time_s"] for t in obj["tasks"]}
    return Instance("pred", len(ids), [tm[i] for i in ids], [tuple(p) for p in obj["precedence"]])


def compute_truth_cpsat(items, cache_path, tlimit, workers):
    """Oracle with the SAME CP-SAT settings as the LLM arms (Spec 04 B2); solved twice with different random seeds.
    truth_m = the smaller of the two (best known); oracle_unstable = the two runs disagree."""
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    for it in items:
        if it["base"] in cache:
            continue
        inst = truth_instance(it["truth"])
        same, inc = truth_constraints(it["truth"])
        rs = [solve_salbp1(inst, it["truth"]["cycle_time_s"], tlimit, workers, same, inc, seed=sd) for sd in (0, 1)]
        ms = [r["m"] for r in rs if r["m"] is not None]
        cache[it["base"]] = dict(m=min(ms) if ms else None, m_min=min(ms) if ms else None, m_max=max(ms) if ms else None,
                                 unstable=int(len(set(r["m"] for r in rs)) > 1), status=[r["status"] for r in rs],
                                 lb=rs[0].get("lb"), time_s=[round(r["time_s"], 2) for r in rs])
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        json.dump(cache, open(cache_path, "w"), indent=1)
    return cache


def diff_flags(diffs):
    k = [d["kind"] for d in diffs]
    return dict(diff_taskset=int(any(x in ("missing_task", "extra_task", "precedence_unknown_id", "wrong_objective") for x in k)),
                diff_time=int(any(x in ("wrong_time", "wrong_cycle_time_s") for x in k)),
                diff_closure=int(any(x.startswith("precedence_") and x != "precedence_unknown_id" or x == "invalid_precedence" for x in k)),
                diff_zone=int(any(x.startswith(("same_station_", "incompatible_")) for x in k)))


# ------------------------------------------------------------------ one job
def run_job(client, arm, it, seed, max_rounds, cp_time, cp_workers, oracle):
    truth_m = oracle["m"]
    row = dict.fromkeys(COLS, "")
    row.update(arm=arm, id=it["id"], level=it["level"], seed=seed, rounds=0, prompt_tokens=0, completion_tokens=0,
               latency_s=0.0, truth_m=truth_m if truth_m is not None else "",
               truth_m_min=oracle["m_min"] if oracle["m_min"] is not None else "", truth_m_max=oracle["m_max"] if oracle["m_max"] is not None else "",
               oracle_unstable=oracle["unstable"], diff_taskset=0, diff_time=0, diff_closure=0, diff_zone=0)
    truth, sheet = it["truth"], it["sheet"]
    tinst, (tsame, tinc) = truth_instance(truth), truth_constraints(truth)
    tc = truth["cycle_time_s"]
    if truth_m:
        row["trivial_lb"] = int(-(-sum(t["time_s"] for t in truth["tasks"]) // tc) == truth_m)
    try:
        if arm == "c":
            msgs = [{"role": "system", "content": LM.SYSTEM}, {"role": "user", "content": f"{sheet}\n\n---\n{STATION_REQ}"}]
            txt, pt, ct, lat, fr = client.chat(msgs, seed, meta=truth)
            row.update(rounds=1, prompt_tokens=pt, completion_tokens=ct, latency_s=round(lat, 3), finish_reason=fr)
            try:
                try:
                    obj = LM.extract_json(txt)
                    obj["stations"]
                except Exception as e:  # noqa
                    raise ValueError(f"parse:{type(e).__name__}")
                assign = {}
                for k, st in enumerate(obj["stations"], 1):
                    for t in st:
                        if t in assign:
                            raise ValueError("task assigned twice")
                        assign[t] = k
                m = validate_solution(tinst, tc, assign, tsame, tinc)
                if m != len(obj["stations"]):
                    raise ValueError("empty station in the middle")
                row.update(valid=1, feasible_on_truth=1, stations=m)
            except Exception as e:  # noqa
                row.update(valid=0, feasible_on_truth=0, error=f"c_parse:{str(e)[:110]}" if str(e).startswith("parse:") else f"c:{str(e)[:120]}")
        else:
            if arm == "r":  # rule parser: no LLM call, one deterministic attempt
                try:
                    obj = RP.sheet_to_model(sheet); errs = validate_full(obj)
                except RP.ParseError as e:
                    obj, errs = None, [f"could not parse JSON: rule parser: {e}"]
            else:
                msgs = [{"role": "system", "content": LM.SYSTEM}, {"role": "user", "content": model_user_msg(sheet)}]
                obj, errs = None, ["not started"]
                for r in range(1, (max_rounds if arm == "d" else 1) + 1):
                    txt, pt, ct, lat, fr = client.chat(msgs, seed + 1000 * (r - 1), meta=truth)
                    if fr == "length" or row["finish_reason"] != "length":
                        row["finish_reason"] = fr  # 'length' (output truncated) in any round sticks
                    row["rounds"] = r; row["prompt_tokens"] += pt; row["completion_tokens"] += ct
                    row["latency_s"] = round(row["latency_s"] + lat, 3)
                    try:
                        obj = LM.extract_json(txt); errs = validate_full(obj)
                    except Exception as e:  # noqa
                        obj, errs = None, [f"could not parse JSON: {e}"]
                    if not errs:
                        break
                    msgs += [{"role": "assistant", "content": txt}, {"role": "user", "content": feedback_msg(errs)}]
            if errs:
                row.update(valid=0, equiv=0, feasible_on_truth=0, error=("invalid:" + errs[0])[:120])
            else:
                row["valid"] = 1
                ok, diffs = check_equivalent(obj, truth)
                row["equiv"] = int(ok)
                row.update(diff_flags(diffs))
                row["diff"] = json.dumps([f"{d['kind']}:{d['detail']}" for d in diffs[:5]], ensure_ascii=False) if diffs else ""
                t0 = time.time()
                pinst = pred_instance(obj)
                ps = [tuple(p) for p in obj["same_station"]]; pi = [tuple(p) for p in obj["incompatible"]]
                try:
                    sol = solve_salbp1(pinst, obj["cycle_time_s"], cp_time, cp_workers, ps, pi)
                except Exception as e:  # noqa
                    sol = dict(m=None, assign=None, status=f"EXC:{e}"[:60])
                row["solve_s"] = round(time.time() - t0, 2)
                if sol["m"] is None:
                    row.update(feasible_on_truth=0, error=f"solver:{sol['status']}")
                else:
                    row["stations"] = sol["m"]
                    try:
                        if pinst.n != tinst.n:
                            raise ValueError("task count differs from truth")
                        validate_solution(tinst, tc, sol["assign"], tsame, tinc)
                        row["feasible_on_truth"] = 1
                    except ValueError as e:
                        row.update(feasible_on_truth=0, error=f"truth_infeasible:{str(e)[:90]}")
        if row["feasible_on_truth"] == 1 and truth_m:
            row["gap"] = round(100.0 * (row["stations"] - truth_m) / truth_m, 4)
            row["hit_le"] = int(row["stations"] <= truth_m)
            row["hit_eq"] = int(row["stations"] == truth_m)
        else:
            row["hit_le"] = row["hit_eq"] = 0
        row["hit_best"] = row["hit_le"]
    except Exception as e:  # noqa  (API failure after retries etc.) -> failure counted in the denominator
        row.update(valid=0, equiv=0 if arm != "c" else "", feasible_on_truth=0, hit_best=0, hit_le=0, hit_eq=0, error=f"FAIL:{type(e).__name__}:{str(e)[:100]}")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="c,d,dprime,r")
    ap.add_argument("--levels", default="L1,L2,L3,L4")
    ap.add_argument("--limit", type=int, default=0, help="first N (sorted by id) instances after level filter")
    ap.add_argument("--model", default=LM.DEFAULT_MODEL)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--workers", type=int, default=2, help="parallel LLM jobs")
    ap.add_argument("--cp-workers", type=int, default=4, help="CP-SAT threads per job")
    ap.add_argument("--cp-time", type=float, default=60.0)
    ap.add_argument("--max-rounds", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--dry-run", action="store_true", help="FakeClient, output under results/dryrun/")
    ap.add_argument("--out", default=None)
    ap.add_argument("--out-dir", default=None, help="results directory (default results/, or results/dryrun with --dry-run); resume reads only its CSV")
    a = ap.parse_args()
    arms = [x for x in a.arms.split(",") if x]
    assert all(x in ARM_NAMES for x in arms), "arms must be from c,d,dprime,r"
    seeds = [int(s) for s in a.seeds.split(",")]
    client = FakeClient() if a.dry_run else RealClient(a.model, a.max_tokens)  # real mode without key exits here
    res_dir = (a.out_dir if os.path.isabs(a.out_dir) else os.path.join(HERE, a.out_dir)) if a.out_dir else (os.path.join(RES, "dryrun") if a.dry_run else RES)
    os.makedirs(res_dir, exist_ok=True)
    out = a.out or os.path.join(res_dir, "expB_dry.csv" if a.dry_run else "expB.csv")
    import fcntl
    lock = open(out + ".lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(f"another process already writes {out}; refusing to start a second writer")
    items = load_items(set(a.levels.split(",")), a.limit)
    done = set()
    if os.path.exists(out):
        with open(out, newline="") as f:
            done = {(r["arm"], r["id"], r["seed"]) for r in csv.DictReader(f)}
    cache = compute_truth_cpsat(items, os.path.join(res_dir, f"truth_cpsat_w{a.cp_workers}_t{a.cp_time:g}.json"), a.cp_time, a.cp_workers)
    jobs = [(arm, it, s) for it in items for arm in arms for s in ([0] if arm == "r" else seeds) if (arm, it["id"], str(s)) not in done]
    print(f"{len(items)} instances, {len(jobs)} jobs to run ({len(done)} already done), out={out}", flush=True)
    new = not os.path.exists(out) or os.path.getsize(out) == 0
    with open(out, "a", newline="") as f, ThreadPoolExecutor(a.workers) as ex:
        w = csv.DictWriter(f, COLS)
        if new:
            w.writeheader()
        futs = [ex.submit(run_job, client, arm, it, s, a.max_rounds, a.cp_time, a.cp_workers, cache[it["base"]]) for arm, it, s in jobs]
        for k, fu in enumerate(as_completed(futs), 1):
            w.writerow(fu.result()); f.flush()
            if k % 10 == 0 or k == len(futs):
                print(f"  {k}/{len(futs)}", flush=True)
    print("done ->", out)


if __name__ == "__main__":
    main()
