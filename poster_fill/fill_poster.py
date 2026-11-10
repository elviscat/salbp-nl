"""Fill the numeric placeholders of the poster from numbers.json (Spec 07). Only the bracket placeholders listed in build_map()
are replaced; the orange colour of the span that wrapped a replaced placeholder becomes the body colour. All other text is
untouched. Text placeholders are listed in remaining_placeholders.txt (outputs go next to --out).
Run: .venv/bin/python -I poster_fill/fill_poster.py --numbers N --poster P --out O"""
import os, re, json, argparse

ORANGE, BODY = "#B8651B", "#1a1a1a"
MINUS = "\u2212"
GRAY_KEYS = ("[model id as served, temperature, max tokens: from prereg.md]", "[model id, date of run]", "[machine, from the run log]")
NBSP = "\u00a0"
GRAY = "#444444"


def fm(x, d=1):
    """number with U+2212 for negatives, no plus sign; -0.0 prints as 0.0"""
    r = round(x, d)
    if r == 0:
        r = 0.0
    return (MINUS if r < 0 else "") + f"{abs(r):.{d}f}"


def sg(x, d=1):
    """signed number: + or U+2212; zero prints without sign"""
    r = round(x, d)
    if r == 0:
        return f"{0:.{d}f}"
    return ("+" if r > 0 else MINUS) + f"{abs(r):.{d}f}"


def ci_txt(ci, d=1):
    return f"{fm(ci[0], d)} to {fm(ci[1], d)}"


def pct(e, d=0):
    return None if e is None or e.get("value") is None else f"{e['value']:.{d}f}"


def kfmt(n):
    return f"{n // 1000}k" if n % 1000 == 0 else str(n)


def select_sentences(N):
    """Situation library sections 0, 3, 4. Returns (selection dict, Takeaway 2 follow-up, Takeaway 3 follow-up, notes)."""
    pd_ = N["paired_d_minus_dprime"]
    lo, hi = pd_["ci"]
    D = "D+" if lo > 0 else ("D-" if hi < 0 else "D0")
    ebl = N["equiv_by_level"]["value"]
    e = [ebl[lv]["d"]["value"] for lv in ("L1", "L2", "L3", "L4")]
    pairs = N["equiv_level_pairs"]["value"]
    mono = e[0] >= e[1] >= e[2] >= e[3]
    p14 = pairs["L1-L4"]
    all_incl0 = all(v["ci"][0] <= 0 <= v["ci"][1] for v in pairs.values())
    if mono and not (p14["ci"][0] <= 0 <= p14["ci"][1]):
        T = "T\u2193"
    elif all_incl0:
        T = "T="
    else:
        T = "T~"
    eq_d = N["equiv_d"]["value"]
    S = "high" if eq_d >= 85 else ("medium" if eq_d >= 50 else "low")
    nb = N["n_bases_with_data"]["value"]
    R = f"{N['equiv_r']['value']:.0f}"
    t2 = {"D+": "Feedback helps, and only on format: the validator checks schema, integer times, id range and acyclicity, so the gain is repair of malformed output, not of semantics.",
          "D0": "The interval includes zero: on these sheets format repair does not detectably change equivalence; the validator cannot repair semantic errors by design.",
          "D-": "Equivalence is lower with feedback; the repair rounds change content as well as format. The validator cannot see the ground truth, so this is a model effect, not a leak."}[D]
    used = {"paired_d_minus_dprime.point": pd_["point"], "paired_d_minus_dprime.ci": pd_["ci"], "equiv_d": eq_d, "e1..e4": e,
            "L1-L4 pair": p14, "monotone e1>=e2>=e3>=e4": mono, "all six pair CIs include 0": all_incl0,
            "k_inv": N["sheet_counts"]["value"]["k_inv"]}
    if T == "T\u2193":
        t3 = (f"It falls by {p14['point']:.0f}{NBSP}points from tables to prose with name-only references (paired; 95% CI {ci_txt(p14['ci'])}); "
              f"the template-aware parser reads {R}%, so the drop is about the model, not the sheets.")
    elif T == "T=":
        t3 = f"The conditions do not differ detectably on these {nb} instances; the template-aware parser reads {R}%, so wording in this range is not the limiting factor."
    else:
        x = e.index(min(e)) + 1
        p34 = pairs["L3-L4"]
        diff, ci = -p34["point"], [-p34["ci"][1], -p34["ci"][0]]
        t3 = f"It is lowest at L{x}; L3 to L4 changes by {sg(diff, 0)}{NBSP}points (paired; 95% CI {ci_txt(ci)}). The template-aware parser reads {R}%."
        used["L3-L4 pair (earlier - later, sign flipped for e4 - e3)"] = p34
    notes = []
    if N["sheet_counts"]["value"]["k_inv"] < 10:
        notes.append("k_inv < 10: the library's short Takeaway 2 main sentence applies; this script does not rewrite the main sentence, do it by hand.")
    return dict(D=D, T=T, S=S, used=used), t2, t3, notes


def build_map(N, machine=None, model_short=None, authors=None, affiliation=None):
    v = lambda k: N[k]["value"]
    pd_ = N["paired_d_minus_dprime"]
    m = {"[X]": pct(N["equiv_d"]), "[Y]": pct(N["equiv_dprime"]), "[Z]": pct(N["hit_le_d"]), "[Z\u2032]": pct(N["hit_le_d_nontrivial"]),
         "[W]": pct(N["hit_le_c"]), "[R]": pct(N["equiv_r"])}
    if pd_.get("value") is not None:
        # mean paired difference (= X - Y), not the bootstrap median; the CI is the percentile interval
        m["[X\u2212Y]"] = sg(pd_.get("point", pd_["value"]), 0)
        m["[a, b]"] = ci_txt(pd_["ci"])
    h1 = (N.get("h1_components") or {}).get("value") or {}
    inv = (h1.get("dprime_invalid_rate") or {}).get("value")
    if inv is not None:
        m["[V]"] = f"{100 - inv:.0f}"
    # [I] and [P] are sheet-level (same population as [k_inv], [m_rep]); [V] stays row-level
    for ph_, key in (("[I]", "invalid_sheet_rate"), ("[P]", "repair_sheet_rate")):
        if key in N and N[key].get("value") is not None:
            m[ph_] = f"{N[key]['value']:.0f}"
    if machine:
        m["[machine, from the run log]"] = machine
    if authors:
        m["[co-authors, order to be confirmed]"] = authors
    if affiliation:
        m["[sub-unit name to be confirmed]"] = affiliation
    f0 = lambda e, d=0: None if e is None or e.get("value") is None else f"{e['value']:,.{d}f}"
    for ph_, key, d_ in (("[N_req]", "n_requests", 0), ("[lat_med]", "run_latency_median_s", 1), ("[lat_p90]", "run_latency_p90_s", 1),
                         ("[tok_med]", "run_tokens_median", 0), ("[tok_max]", "run_tokens_max", 0), ("[rounds]", "rounds_mean_d_all", 2),
                         ("[k_opt]", "oracle_not_proven_optimal_count", 0)):
        if key in N:
            m[ph_] = f0(N[key], d_)
    sc = (N.get("sheet_counts") or {}).get("value")
    if sc:
        for ph_, key in (("[k_inv]", "k_inv"), ("[m_rep]", "m_rep"), ("[k_ne]", "k_ne"), ("[f1]", "f1"), ("[f2]", "f2"), ("[f3]", "f3"),
                         ("[f4]", "f4"), ("[t]", "t"), ("[p]", "p"), ("[api]", "api")):
            m[ph_] = str(sc[key])
    ebl = (N.get("equiv_by_level") or {}).get("value")
    if ebl:
        for i_, lv in enumerate(("L1", "L2", "L3", "L4"), 1):
            e = (ebl.get(lv) or {}).get("d")
            if e and e.get("value") is not None:
                m[f"[e{i_}]"] = f"{e['value']:.0f}"
    tl = (N.get("trivial_lb_subset") or {}).get("value")
    if tl:
        m["[k_nt]"], m["[N_nt]"] = str(tl["k"]), str(tl["N"])
    bs = (N.get("by_size") or {}).get("value")
    if bs:
        for r_, nm in ((1, "n<=20"), (2, "21-50"), (3, "51-100")):
            e = bs.get(nm) or {}
            ni = next((x.get("n_instances") for x in e.values() if x), None)
            if ni is not None:
                m[f"[sz_{r_}_n]"] = str(ni)
            for c_, a_ in (("d", "d"), ("dp", "dprime"), ("r", "r")):
                x = e.get(a_)
                if x and x.get("value") is not None:
                    m[f"[sz_{r_}_{c_}]"] = f"{x['value']:.0f}%"
    mt = N.get("max_tokens_modelling", {}).get("value")
    temp = N.get("temperature", {}).get("value")
    if mt and temp is not None:
        short = model_short or v("model")
        m["[model id as served, temperature, max tokens: from prereg.md]"] = f"{short}; temperature {temp:g}; max {kfmt(mt)} tokens"
    m["[model id, date of run]"] = f"{v('model')}, {v('run_date')}"
    return {k: x for k, x in m.items() if x is not None}


def outermost(text):
    """outermost [...] spans of a text node (handles nesting)."""
    out, d, st = [], 0, None
    for i, ch in enumerate(text):
        if ch == "[":
            if d == 0:
                st = i
            d += 1
        elif ch == "]" and d > 0:
            d -= 1
            if d == 0:
                out.append((st, i + 1))
    return out


def rep_text(text, M, cnt):
    res, last = [], 0
    for a, b in outermost(text):
        res.append(text[last:a])
        ph = text[a:b]
        if ph in M:
            res.append(M[ph]); cnt[0] += 1
        else:
            res.append(ph)
        last = b
    res.append(text[last:])
    return "".join(res)


def text_nodes(head, fn):
    return re.sub(r">([^<]*)<", lambda m: ">" + fn(m.group(1)) + "<", head)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", required=True)
    ap.add_argument("--poster", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--machine", default=None, help="text for [machine, from the run log]")
    ap.add_argument("--model", default=None, help="override model id from numbers.json (full id, goes to the footer)")
    ap.add_argument("--model-short", default=None, help="short model name for the pipeline box; default = the full id as is")
    ap.add_argument("--run-date", default=None, help="override run date from numbers.json")
    ap.add_argument("--authors", default=None, help="text for [co-authors, order to be confirmed]; placeholder kept if absent")
    ap.add_argument("--affiliation", default=None, help="text for [sub-unit name to be confirmed]; placeholder kept if absent")
    ap.add_argument("--accent", default=None, help="replace {{accent}} with this colour")
    ap.add_argument("--fig2", default=None, help="SVG file to embed in the Figure 2 frame")
    ap.add_argument("--fig3", default=None, help="SVG file to embed in the Figure 3 frame")
    ap.add_argument("--badge", default=None, help="small red label in the top-right margin")
    ap.add_argument("--note-pending", default=None, help="sentence appended (body colour) to the small print of result card 1")
    ap.add_argument("--fig3-caption-fix", action="store_true", help="shorten the Figure 3 caption by one word (flags can overlap -> flags overlap) so the last line is not a lone '0.'; old/new printed")
    ap.add_argument("--flow-fix", action="store_true", help="mock-up only: widen box 1 of the pipeline (flex 0.9 -> 1.1) and narrow box 5 (1.45 -> 1.25) so 'Process' and 'conditions' are not clipped; text untouched")
    ap.add_argument("--standalone", action="store_true", help="drop x-dc wrapper, helmet and the data script so the file renders as plain HTML")
    ap.add_argument("--selection-out", default=None, help="write the sentence-selection record (markdown) here")
    a = ap.parse_args()
    N = json.load(open(a.numbers, encoding="utf-8"))
    if a.model:
        N["model"] = dict(value=a.model)
    if a.run_date:
        N["run_date"] = dict(value=a.run_date)
    M = build_map(N, a.machine, a.model_short, a.authors, a.affiliation)
    sel, t2, t3, notes = select_sentences(N)
    M["[Takeaway 2 follow-up sentence, chosen by the data]"] = t2
    M["[Takeaway 3 follow-up sentence, chosen by the data]"] = t3
    s = open(a.poster, encoding="utf-8").read()
    cut = s.find('<script type="text/x-dc"')
    head, tail = (s[:cut], s[cut:]) if cut > 0 else (s, "")
    if a.accent:
        head = head.replace("{{accent}}", a.accent)
    # singular form: "[k_opt] instances" -> "1 instance"
    if M.get("[k_opt]") == "1":
        head = re.sub(r"(\[k_opt\]</span>)[ \u00a0]instances", lambda m: m.group(1) + NBSP + "instance", head)
    # counts that the poster text writes as the full-run values (184 sheets, 46 instances, 25 Otto / 21 Scholl) -> the values behind the numbers
    ns, nb = N["n_sheets_with_data"]["value"], N["n_bases_with_data"]["value"]
    src = (N.get("by_source") or {}).get("value") or {}
    cnt_src = lambda k: next((x.get("n_instances") for x in (src.get(k) or {}).values() if x), None)
    otto, scholl = cnt_src("Otto"), cnt_src("Scholl")
    def hard(t):
        t = re.sub(r"\b184\b", str(ns), t)
        if otto is not None and scholl is not None:
            t = t.replace("(25 Otto n = 20, 21 Scholl)", f"({otto} Otto n = 20, {scholl} Scholl)")
        return re.sub(r"\b46\b", str(nb), t)
    nle = N["n_sheets_le100"]["value"]
    card1 = "of 184 sheets (46 instances \u00d7 4, n \u2264 100)"
    if ns < nle:
        assert head.count(card1) == 1, "card 1 sheet-count phrase not found"
        head = head.replace(card1, "of 184 sheets with data (of \u00a7LE\u00a7: 46 instances \u00d7 4, n \u2264 100)")
    head = text_nodes(head, hard).replace("\u00a7LE\u00a7", str(nle))
    # number + unit never split across a line: placeholder, space, unit -> no-break space (also across a closing span)
    head = re.sub(r"(\[(?:lat_med|lat_p90|X\u2212Y|N_req|k_opt)\](?:</span>)?) (s|points|requests|instances|instance)\b", lambda m: m.group(1) + NBSP + m.group(2), head)
    if a.note_pending:
        anchor = "95% CI [a, b].</span>"
        assert head.count(anchor) == 1, "card 1 small print anchor not found"
        head = head.replace(anchor, f"95% CI [a, b]. {a.note_pending}</span>")
    cnt = [0]
    # pass 1: styled span/div (when every placeholder in it was replaced the orange becomes body colour, bold 600 becomes regular;
    # the 76 px result numbers keep their weight 700)
    def span_fn(m):
        pre, style, mid, body, post = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        spans = outermost(body)
        if not spans or not any(body[x:y] in M for x, y in spans):
            return m.group(0)
        all_done = all(body[x:y] in M for x, y in spans)
        # is the span inside a bold paragraph (Figure 3 caption)? then the filled value stays bold
        i0 = m.start()
        lp = head.rfind("<p ", 0, i0)
        bold_parent = lp >= 0 and "</p>" not in head[lp:i0] and "font-weight: 600" in head[lp:head.find(">", lp)]
        lead = ""
        nb_ = rep_text(body, M, cnt)
        if all_done and ORANGE.lower() in style.lower():
            gray = any(body[x:y] in GRAY_KEYS for x, y in spans)
            style = re.sub(re.escape(ORANGE), GRAY if gray else BODY, style, flags=re.I)
            if not bold_parent:
                style = style.replace("font-weight: 600", "font-weight: 400")
            if body.strip() == "[model id as served, temperature, max tokens: from prereg.md]":
                lead = "<br>"
        return lead + pre + style + mid + nb_ + post
    head = re.sub(r'(<(?:span|div) style=")([^"]*)(">)([^<]*)(</(?:span|div)>)', span_fn, head)
    # pass 2: any other text node
    head = text_nodes(head, lambda t: rep_text(t, M, cnt))
    # figures
    for key, path, h in (("fig2", a.fig2, 340), ("fig3", a.fig3, 185)):
        if not path:
            continue
        svg = open(path, encoding="utf-8").read().strip()
        svg = svg.replace("<svg ", '<svg style="width: 100%; height: auto; display: block" ', 1)
        pat = rf'<div style="box-sizing: border-box; height: {h}px;[^"]*">\s*<span[^>]*>\[[^<]*</span>\s*</div>'
        head, n_sub = re.subn(pat, lambda m: f'<div style="border: 3px solid #333333; border-radius: 10px; overflow: hidden; background: #ffffff">{svg}</div>', head, count=1)
        assert n_sub == 1, f"{key} frame not found"
    if a.flow_fix:
        for old, new in ():
            assert head.count(old) == 1, old
            head = head.replace(old, new)
    if a.fig3_caption_fix:
        old, new = "(any seed; flags can overlap)", "(any seed; flags overlap)"
        assert head.count(old) == 1, old
        head = head.replace(old, new)
        print(f"  TEXT CHANGE: {old!r} -> {new!r}")
    if a.badge:
        b = (f'<div style="position: absolute; top: 24px; right: 96px; padding: 6px 22px; border: 4px solid #C62828; border-radius: 8px; background: #ffffff; '
             f'color: #C62828; font-family: Inter, system-ui, sans-serif; font-size: 32px; font-weight: 700; letter-spacing: 0.02em; line-height: 1.2; z-index: 5">{a.badge}</div>')
        head = head.replace("<body>", "<body>" + b, 1) if "<body>" in head else b + head
    if a.standalone:
        head = head.replace('<script src="./support.js"></script>', "")
        head = re.sub(r"</?x-dc>", "", head)
        head = head.replace("<helmet>", "").replace("</helmet>", "")
        head = head.replace("<body>", '<body style="position: relative; width: 4128px; height: 2304px; margin: 0">', 1)
        tail = "</body>\n</html>\n"
    open(a.out, "w", encoding="utf-8").write(head + tail)
    # remaining placeholders in the final visible text (comments and SVG excluded)
    vis = re.sub(r"<svg.*?</svg>", "", re.sub(r"<!--.*?-->", "", head, flags=re.S), flags=re.S)
    remaining, total = [], 0
    for tn in re.finditer(r">([^<]*)<", vis):
        for x, y in outermost(tn.group(1)):
            total += 1
            remaining.append(tn.group(1)[x:y])
    d = os.path.dirname(os.path.abspath(a.out))
    with open(os.path.join(d, "remaining_placeholders.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(remaining) + "\n")
    if a.selection_out:
        u = sel["used"]
        lines = ["# Sentence selection (Spec 12)", "",
                 f"Rules: situation library `海報_結果情境句庫_v1.md` sections 0, 3, 4. Source: `{os.path.abspath(a.numbers)}` (partial data, {nb} of {N['n_instances_le100']['value']} instances, {ns} sheets; not final).", "",
                 f"- **D = {sel['D']}** (paired d - d' equivalence: mean {sg(u['paired_d_minus_dprime.point'], 1)} pp, 95% CI {ci_txt(u['paired_d_minus_dprime.ci'])}; D+ = CI lower bound > 0, D0 = CI includes 0, D- = CI upper bound < 0)",
                 f"- **T = {sel['T']}** (arm d equivalence L1..L4 = {' / '.join(f'{x:.1f}' for x in u['e1..e4'])}; monotone e1 >= e2 >= e3 >= e4: {u['monotone e1>=e2>=e3>=e4']}; "
                 f"L1 - L4 paired mean {sg(u['L1-L4 pair']['point'], 1)} pp, CI {ci_txt(u['L1-L4 pair']['ci'])}; all six pair CIs include 0: {u['all six pair CIs include 0']})",
                 f"- S = {sel['S']} (equiv_d = {u['equiv_d']:.1f}%; library section 1 subtitle variants are retired, so S is not used)", "",
                 "## Takeaway 2 follow-up (D selects)", t2, "",
                 "## Takeaway 3 follow-up (T selects)", t3, ""]
        if "L3-L4 pair (earlier - later, sign flipped for e4 - e3)" in u:
            q = u["L3-L4 pair (earlier - later, sign flipped for e4 - e3)"]
            lines += [f"T~ numbers: L3 - L4 paired mean {sg(q['point'], 1)} pp, CI {ci_txt(q['ci'])}; shown as e4 - e3 = {sg(-q['point'], 0)}, CI {ci_txt([-q['ci'][1], -q['ci'][0]])}.", ""]
        lines += [f"k_inv = {u['k_inv']} (>= 10: the standard Takeaway 2 main sentence stays).",
                  "Card 2: the poster text already carries the library's 'Plans can match the oracle without an equivalent model' sentence (rule in section 6 for Z > X); no change.", ""]
        lines += [f"NOTE: {x}" for x in notes]
        open(a.selection_out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    notrep = [k for k in ("[X]", "[Y]", "[V]", "[I]", "[X\u2212Y]", "[a, b]", "[Z]", "[Z\u2032]", "[W]", "[R]", "[N_req]", "[lat_med]", "[lat_p90]", "[tok_med]", "[tok_max]", "[rounds]",
                          "[k_opt]", "[k_inv]", "[m_rep]", "[k_ne]", "[f1]", "[f2]", "[f3]", "[f4]", "[t]", "[p]", "[api]", "[e1]", "[e2]", "[e3]", "[e4]", "[k_nt]", "[N_nt]")
              + tuple(f"[sz_{r}_{c}]" for r in (1, 2, 3) for c in ("n", "d", "dp", "r")) if k not in M]
    print(f"replaced {cnt[0]} places, remaining {len(remaining)} (of {total} bracket items left in the visible text); numeric keys with no value in numbers.json: {notrep}")
    for r in remaining:
        print("  remaining:", r)
    for x in notes:
        print("  NOTE:", x)


if __name__ == "__main__":
    main()
