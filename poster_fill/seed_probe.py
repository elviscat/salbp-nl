"""Seed probe (Spec 10 item 6): does the NIM endpoint honour `seed`? Sends the same tiny request twice (temperature 0.2, seed 1)
and reports whether the two replies are identical, whether the response has system_fingerprint / reasoning_content, and the token
counts. Reads NVIDIA_API_KEY and NIM_MODEL from the environment (never printed or stored). Writes results/seed_probe.txt.
Run on the Mac mini: .venv/bin/python -I poster_fill/seed_probe.py"""
import os, sys, datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = "https://integrate.api.nvidia.com/v1"
PROMPT = "Reply with one random 6-digit number."


def main():
    key, model = os.environ.get("NVIDIA_API_KEY"), os.environ.get("NIM_MODEL")
    if not key or not model:
        print("NVIDIA_API_KEY and NIM_MODEL must both be set in the environment (export them yourself; never paste them into files). Nothing was called.")
        return 0
    from openai import OpenAI
    c = OpenAI(base_url=BASE_URL, api_key=key, max_retries=0, timeout=120)
    outs = []
    for _ in range(2):
        r = c.chat.completions.create(model=model, messages=[{"role": "user", "content": PROMPT}], temperature=0.2, seed=1, max_tokens=20)
        msg = r.choices[0].message
        outs.append(dict(text=(msg.content or "").strip(), fp=getattr(r, "system_fingerprint", None),
                         has_fp_attr=hasattr(r, "system_fingerprint"),
                         has_reasoning=(getattr(msg, "reasoning_content", None) is not None) or ("reasoning_content" in (getattr(msg, "model_extra", None) or {})),
                         ct=r.usage.completion_tokens if r.usage else None))
    lines = [f"utc: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", f"model: {model}",
             f"prompt: {PROMPT} (temperature 0.2, seed 1, max_tokens 20)",
             f"reply 1: {outs[0]['text']!r}", f"reply 2: {outs[1]['text']!r}",
             f"replies identical: {outs[0]['text'] == outs[1]['text']}",
             f"system_fingerprint present: {any(o['fp'] for o in outs)} (values: {[o['fp'] for o in outs]})",
             f"reasoning_content present: {any(o['has_reasoning'] for o in outs)}",
             f"completion_tokens: {[o['ct'] for o in outs]}"]
    txt = "\n".join(lines) + "\n"
    print(txt, end="")
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    open(os.path.join(HERE, "results", "seed_probe.txt"), "w", encoding="utf-8").write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
