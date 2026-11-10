"""Editable PPTX of the filled poster (Spec 12).
Input: the filled, standalone poster HTML (fill_poster.py --standalone), numbers.json, the two figure SVGs.
Step 1: headless Chrome loads the HTML at 4128 x 2304 px and a small script walks the DOM: every text container (runs with
        size / weight / colour), every box (fill, border, radius), every grid table, every SVG with its rectangle -> layout JSON.
        Text therefore comes from the filled HTML, nothing is typed in here.
Step 2: python-pptx writes one 43 x 24 in slide. 1 px = 9525 EMU = 1/96 in, so 4128 px = 43 in and px * 0.75 = pt.
        Text = editable text boxes (Arial, Courier New for monospace), tables = PPT tables, flow boxes = rounded rectangles + arrows,
        figures 2 and 3 = PNG (Chrome renders the SVG at 3.6x, about 300 dpi at the placed size).
Run: .venv/bin/python -I poster_fill/build_pptx.py --html H --numbers N --fig2 SVG --fig3 SVG --out OUT.pptx
"""
import os, sys, re, json, html, argparse, subprocess, tempfile, hashlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE, MSO_ANCHOR
from pptx.enum.dml import MSO_LINE
from pptx.oxml.ns import qn
from lxml import etree

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PX = 9525
PAGE_W, PAGE_H = 4128, 2304
MARGIN = 96
PANEL_MODE = os.environ.get('PPTX_BADGE_IN_MARGIN') == '1'   # Spec 16: the panel layout keeps the removable label in the top margin (y = 24), where the HTML has it

JS = r"""
<script>
function cs(e){return getComputedStyle(e)}
function rgb(s){const m=s.match(/rgba?\(([^)]+)\)/);if(!m)return null;const p=m[1].split(',').map(x=>parseFloat(x));const a=p.length>3?p[3]:1;if(a===0)return null;
  return '#'+[0,1,2].map(i=>Math.round(p[i]).toString(16).padStart(2,'0')).join('')}
function R(e){const r=e.getBoundingClientRect();return {x:r.left+scrollX,y:r.top+scrollY,w:r.width,h:r.height}}
function isInline(e){return cs(e).display==='inline'}
function hasText(e){
  for(const n of e.childNodes){if(n.nodeType===3&&n.textContent.trim()!=='')return true}
  for(const c of e.children){if(isInline(c)&&c.tagName.toLowerCase()!=='svg'&&c.textContent.trim()!=='')return true}
  return false}
function styleOf(e){const s=cs(e);return {size:parseFloat(s.fontSize),bold:parseInt(s.fontWeight)>=600,color:rgb(s.color)||'#000000',
  mono:/mono|menlo|courier/i.test(s.fontFamily),sup:e.tagName.toLowerCase()==='sup',upper:s.textTransform==='uppercase'}}
function supSize(e){return e.tagName.toLowerCase()==='sup'?parseFloat(cs(e.parentElement).fontSize):null}
function runs(e,pre,acc){
  for(const n of e.childNodes){
    if(n.nodeType===3){let t=n.textContent;if(!pre)t=t.replace(/[ \t\n\r\f]+/g,' ');if(t==='')continue;const st=styleOf(e);if(st.sup)st.size=supSize(e);if(st.upper)t=t.toUpperCase();acc.push(Object.assign({text:t},st))}
    else if(n.nodeType===1&&n.tagName.toLowerCase()==='br'){acc.push({text:'',br:true,size:parseFloat(cs(e).fontSize),bold:false,color:'#000000',mono:false,sup:false})}
    else if(n.nodeType===1&&isInline(n)&&n.tagName.toLowerCase()!=='svg')runs(n,pre,acc)}
  return acc}
const items=[];window._pidc=0;
function walk(e){
  const tag=e.tagName.toLowerCase();
  if(['script','style','link','head','helmet'].includes(tag))return;
  const s=cs(e);
  if(tag==='svg'){const r=R(e);items.push({t:'svg',rect:r,html:e.outerHTML.length<4000?e.outerHTML:''});return}
  if(s.display==='none')return;
  const r=R(e);
  const bw=['Top','Right','Bottom','Left'].map(k=>parseFloat(s['border'+k+'Width'])||0);
  const bg=rgb(s.backgroundColor);
  const page=r.w>4100&&r.h>2300;
  const hasBox=!page&&tag!=='body'&&tag!=='html'&&(bg||bw.some(x=>x>0));
  // grid table: all four borders
  if(s.display==='grid'&&bw.every(x=>x>0)){
    const cols=s.gridTemplateColumns.split(' ').length;const cells=[...e.children];
    items.push({t:'table',rect:r,cols:cols,border:{w:bw[0],color:rgb(s.borderTopColor)},cells:cells.map(c=>{const cc=cs(c);const pr=R(c);
      return {rect:pr,bg:rgb(cc.backgroundColor),bt:parseFloat(cc.borderTopWidth)||0,btc:rgb(cc.borderTopColor),
        pad:[parseFloat(cc.paddingTop),parseFloat(cc.paddingRight),parseFloat(cc.paddingBottom),parseFloat(cc.paddingLeft)],
        align:cc.textAlign,lh:parseFloat(cc.lineHeight)||parseFloat(cc.fontSize)*1.3,runs:runs(c,false,[])}})});
    return}
  if(hasBox){items.push({t:'box',rect:r,bg:bg,bw:bw,bc:['Top','Right','Bottom','Left'].map(k=>rgb(s['border'+k+'Color'])),bs:['Top','Right','Bottom','Left'].map(k=>s['border'+k+'Style']),
    radius:parseFloat(s.borderTopLeftRadius)||0,abs:s.position==='absolute',tag:tag})}
  if(hasText(e)){
    const pre=/pre/.test(s.whiteSpace);const rs=runs(e,pre,[]);
    if(rs.length&&!pre){rs[0].text=rs[0].text.replace(/^ +/,'');rs[rs.length-1].text=rs[rs.length-1].text.replace(/ +$/,'')}
    const pad=[parseFloat(s.paddingTop),parseFloat(s.paddingRight),parseFloat(s.paddingBottom),parseFloat(s.paddingLeft)];
    let list=null;
    if(tag==='li'){const par=e.parentElement;if(!par._pid)par._pid=++window._pidc;list={kind:par.tagName.toLowerCase(),index:[...par.children].indexOf(e)+1,left:parseFloat(cs(par).paddingLeft),pid:par._pid,gap:parseFloat(cs(par).rowGap)||0}}
    items.push({t:'text',tag:tag,rect:r,pad:pad,runs:rs,align:s.textAlign,lh:parseFloat(s.lineHeight)||parseFloat(s.fontSize)*1.3,pre:pre,list:list,abs:s.position==='absolute'});
    return}
  for(const c of e.children)walk(c)}
window.addEventListener('load',()=>setTimeout(()=>{
  walk(document.body);
  const pre=document.createElement('pre');pre.id='layout_json';pre.textContent=JSON.stringify(items);document.body.appendChild(pre)},2500));
</script>
"""


def chrome_layout(html_path, work):
    s = open(html_path, encoding="utf-8").read()
    tmp = os.path.join(work, "_layout_probe.html")
    open(tmp, "w", encoding="utf-8").write(s.replace("</body>", JS + "</body>"))
    out = subprocess.run([CHROME, "--headless=new", "--disable-gpu", f"--user-data-dir={work}/chrome_prof", f"--window-size={PAGE_W},{PAGE_H}",
                          "--virtual-time-budget=12000", "--dump-dom", "file://" + tmp], capture_output=True, text=True, timeout=180).stdout
    os.remove(tmp)
    m = re.search(r'<pre id="layout_json">(.*?)</pre>', out, re.S)
    if not m:
        raise SystemExit("layout probe produced no JSON")
    return json.loads(html.unescape(m.group(1)))


def svg_to_png(svg_path, png_path, work, scale=3.6):
    s = open(svg_path, encoding="utf-8").read()
    w = int(re.search(r'width="(\d+)"', s).group(1))
    h = int(re.search(r'height="(\d+)"', s).group(1))
    page = os.path.join(work, "_svg_wrap.html")
    open(page, "w", encoding="utf-8").write(
        '<!doctype html><html><head><meta charset="utf-8"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'
        f'<style>body{{margin:0;background:#fff}}</style></head><body>{s}</body></html>')
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work}/chrome_prof", f"--window-size={w},{h}",
                    f"--force-device-scale-factor={scale}", "--virtual-time-budget=8000", f"--screenshot={png_path}", "file://" + page],
                   capture_output=True, text=True, timeout=120)
    os.remove(page)
    assert os.path.exists(png_path), "SVG render failed"
    return w, h


E = lambda v: Emu(int(round(v * PX)))
hexrgb = lambda h: RGBColor.from_string(h.lstrip("#").upper())
ALIGN = {"center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT, "end": PP_ALIGN.RIGHT}


def style_run(run, r):
    f = run.font
    f.name = "Courier New" if r["mono"] else "Arial"
    f.size = Pt(r["size"] * 0.75)
    f.bold = bool(r["bold"])
    f.color.rgb = hexrgb("#000000" if r["mono"] else r["color"])    # Courier New is much thinner than the PNG's Menlo: black keeps the visual weight
    if not r["mono"] and r["size"] < 30:                                               # Arial is about 3.5 % narrower than Inter: a little tracking keeps the line breaks of the PNG
        run._r.get_or_add_rPr().set("spc", str(int(round(r["size"] * 0.75 * 100 * 0.022))))
    if r["sup"]:
        run._r.get_or_add_rPr().set("baseline", "30000")
    if r["mono"]:                      # Courier New advances 0.6 em; the poster's Menlo with letter-spacing -0.5 px is about 12.7 px at 22 px
        run._r.get_or_add_rPr().set("spc", "-38")


def fill_paragraphs(tf, runs, align, lh, pre, list_info=None, space_before=0, started=False):
    """one paragraph per text container; for white-space: pre the text is split into one paragraph per line;
    started = the text frame already holds a paragraph (merged list items); <br> becomes a line break"""
    paras, cur = [], []
    for r in runs:
        parts = r["text"].split("\n") if pre else [r["text"]]
        for i, t in enumerate(parts):
            if i > 0:
                paras.append(cur); cur = []
            if t != "" or r.get("br"):
                cur.append(dict(r, text=t))
    paras.append(cur)
    first = True
    for rs in paras:
        p = tf.add_paragraph() if (started or not first) else tf.paragraphs[0]
        p.alignment = ALIGN.get(align, PP_ALIGN.LEFT)
        p.line_spacing = Pt(lh * 0.75)
        p.space_before = Pt(space_before * 0.75 if first else 0)
        p.space_after = Pt(0)
        for r in rs:
            if r.get("br"):
                p.add_line_break()
                continue
            run = p.add_run()
            run.text = r["text"]
            style_run(run, r)
        if list_info and first:
            ind = 30 if list_info["kind"] == "ol" else 24     # bullet / number sits just left of the text, as in the PNG
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(int(ind * PX)))
            pPr.set("indent", str(-int(ind * PX)))
            if list_info["kind"] == "ol":
                bu = etree.SubElement(pPr, qn("a:buFont")); bu.set("typeface", "Arial")
                bu = etree.SubElement(pPr, qn("a:buAutoNum"))
                bu.set("type", "arabicPeriod")
                bu.set("startAt", str(list_info["index"]))
            else:
                bu = etree.SubElement(pPr, qn("a:buFont")); bu.set("typeface", "Arial")
                bu = etree.SubElement(pPr, qn("a:buChar"))
                bu.set("char", "\u2022")
        first = False


def merge_lists(items):
    """consecutive <li> text items of the same list become one text box (paragraph spacing = the list's gap), so the PPTX
    does not keep the PNG's per-item heights when Arial wraps to fewer lines"""
    out = []
    for it in items:
        li = it.get("list") if it["t"] == "text" else None
        prev = out[-1] if out else None
        if li and prev and prev["t"] == "text" and prev.get("members") and prev["list"]["pid"] == li["pid"]:
            prev["members"].append(it)
            r, q = prev["rect"], it["rect"]
            x0, y0 = min(r["x"], q["x"]), min(r["y"], q["y"])
            x1, y1 = max(r["x"] + r["w"], q["x"] + q["w"]), max(r["y"] + r["h"], q["y"] + q["h"])
            prev["rect"] = dict(x=x0, y=y0, w=x1 - x0, h=y1 - y0)
        elif li:
            it = dict(it, members=[it])
            out.append(it)
        else:
            out.append(it)
    return out


def add_box(slide, it, geo):
    r = it["rect"]
    x, y, w, h = r["x"], r["y"], r["w"], r["h"]
    bw, bc, bs = it["bw"], it["bc"], it["bs"]
    uniform = len(set(bw)) == 1 and bw[0] > 0 and len(set(bc)) == 1 and len(set(bs)) == 1
    shp_t = MSO_SHAPE.ROUNDED_RECTANGLE if it["radius"] > 0 else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shp_t, E(x), E(y), E(w), E(h))
    shp.shadow.inherit = False
    if it["radius"] > 0:
        shp.adjustments[0] = min(0.5, it["radius"] / min(w, h))
    if it["bg"]:
        shp.fill.solid(); shp.fill.fore_color.rgb = hexrgb(it["bg"])
    else:
        shp.fill.background()
    if uniform:
        shp.line.width = Pt(bw[0] * 0.75)
        shp.line.color.rgb = hexrgb(bc[0])
        if bs[0] == "dashed":
            shp.line.dash_style = MSO_LINE.DASH
    else:
        shp.line.fill.background()
    shp.text_frame.text = ""
    if not it["abs"]:
        geo.append((x, y, w, h, "box"))
    if not uniform:   # per-side borders as thin rectangles
        sides = [(0, x, y, w, bw[0]), (1, x + w - bw[1], y, bw[1], h), (2, x, y + h - bw[2], w, bw[2]), (3, x, y, bw[3], h)]
        for i, sx, sy, sw, sh in sides:
            if bw[i] > 0 and bc[i]:
                b = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, E(sx), E(sy), E(sw), E(sh))
                b.shadow.inherit = False
                b.fill.solid(); b.fill.fore_color.rgb = hexrgb(bc[i]); b.line.fill.background()
                geo.append((sx, sy, sw, sh, "side"))


def add_text(slide, it, geo):
    if PANEL_MODE and it.get("tag") == "h1":     # Spec 16: Arial Bold is wider than Space Grotesk; 0.88 x size keeps the two-line title on two lines
        it = dict(it, runs=[dict(r, size=r["size"] * 0.88) for r in it["runs"]])
    r, pad = it["rect"], it["pad"]
    x, y, w, h = r["x"] + pad[3], r["y"] + pad[0], r["w"] - pad[1] - pad[3], r["h"] - pad[0] - pad[2]
    li = it.get("list")
    ind = 0
    if li:                                  # the bullet / number hangs just left of the text
        ind = 30 if li["kind"] == "ol" else 24
        x, w = x - ind, w + ind
    tb = slide.shapes.add_textbox(E(x), E(y), E(w + (16 if it["pre"] else 0)), E(max(h, 10)))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    if it.get("members"):
        for k, m in enumerate(it["members"]):
            fill_paragraphs(tf, m["runs"], m["align"], m["lh"], m["pre"], m["list"], space_before=(li["gap"] if k else 0), started=k > 0)
    else:
        fill_paragraphs(tf, it["runs"], it["align"], it["lh"], it["pre"], li)
    if not it.get("abs"):
        geo.append((x, y, w, h, "text"))


def set_cell_border(tc, top=None, others=None):
    """top = (width_px, hex) for the top edge; others = (width_px, hex) for left / right / bottom"""
    tcPr = tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        for old in tcPr.findall(qn(tag)):
            tcPr.remove(old)
    spec = [("a:lnL", others), ("a:lnR", others), ("a:lnT", top or others), ("a:lnB", others)]
    for i, (tag, val) in enumerate(spec):
        ln = etree.Element(qn(tag))
        if val and val[0] > 0:
            ln.set("w", str(int(val[0] * PX))); ln.set("cap", "flat"); ln.set("cmpd", "sng")
            sf = etree.SubElement(ln, qn("a:solidFill")); c = etree.SubElement(sf, qn("a:srgbClr")); c.set("val", val[1].lstrip("#").upper())
            etree.SubElement(ln, qn("a:prstDash")).set("val", "solid")
        else:
            ln.set("w", "0"); etree.SubElement(ln, qn("a:noFill"))
        tcPr.insert(i, ln)


def add_table(slide, it, geo):
    cols = it["cols"]
    cells = it["cells"]
    rows = (len(cells) + cols - 1) // cols
    r = it["rect"]
    bw = it["border"]["w"]
    inner_x, inner_y = r["x"] + bw, r["y"] + bw
    colw = [cells[i]["rect"]["w"] for i in range(cols)]
    rowh = [max(cells[ri * cols + ci]["rect"]["h"] for ci in range(cols) if ri * cols + ci < len(cells)) for ri in range(rows)]
    gf = slide.shapes.add_table(rows, cols, E(inner_x), E(inner_y), E(sum(colw)), E(sum(rowh)))
    tbl = gf.table
    tblPr = tbl._tbl.tblPr
    for a in ("firstRow", "bandRow", "firstCol", "lastRow", "lastCol", "bandCol"):
        tblPr.set(a, "0")
    for sid in tblPr.findall(qn("a:tableStyleId")):
        tblPr.remove(sid)
    for ci in range(cols):
        tbl.columns[ci].width = E(colw[ci])
    for ri in range(rows):
        tbl.rows[ri].height = E(rowh[ri])
    for i, c in enumerate(cells):
        ri, ci = divmod(i, cols)
        cell = tbl.cell(ri, ci)
        cell.margin_top, cell.margin_right, cell.margin_bottom, cell.margin_left = [E(v) for v in c["pad"]]
        cell.vertical_anchor = MSO_ANCHOR.TOP
        cell.fill.solid(); cell.fill.fore_color.rgb = hexrgb(c["bg"] or "#FFFFFF")
        tf = cell.text_frame
        tf.word_wrap = True
        fill_paragraphs(tf, c["runs"], c["align"], c["lh"], False)
        top = (c["bt"], c["btc"]) if c["bt"] and c["btc"] else None
        edge = (bw, it["border"]["color"] or "#333333")
        set_cell_border(cell._tc, top=top or ((0, "#FFFFFF") if ri == 0 else None), others=(0, "#FFFFFF"))
    # outer frame as a no-fill rectangle on top of the table
    fr = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, E(r["x"]), E(r["y"]), E(r["w"]), E(r["h"]))
    fr.shadow.inherit = False
    fr.fill.background(); fr.line.width = Pt(bw * 0.75); fr.line.color.rgb = hexrgb(it["border"]["color"] or "#333333")
    geo.append((r["x"], r["y"], r["w"], r["h"], "table"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", required=True)
    ap.add_argument("--numbers", required=True)
    ap.add_argument("--fig2", required=True)
    ap.add_argument("--fig3", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work-dir", default=None, help="folder for the Chrome profile and the PNGs (default: next to --out)")
    ap.add_argument("--layout-json", default=None, help="write the extracted layout here (debug)")
    a = ap.parse_args()
    out_dir = os.path.dirname(os.path.abspath(a.out))
    work = a.work_dir or os.path.join(out_dir, "pptx_work")
    os.makedirs(work, exist_ok=True)
    N = json.load(open(a.numbers, encoding="utf-8"))
    items = merge_lists(chrome_layout(a.html, work))
    if a.layout_json:
        json.dump(items, open(a.layout_json, "w", encoding="utf-8"), ensure_ascii=False)
    png2, png3 = os.path.join(work, "fig2.png"), os.path.join(work, "fig3.png")
    svg_to_png(a.fig2, png2, work)
    svg_to_png(a.fig3, png3, work)

    # the red label goes just inside the 1 in border at the top right; text boxes that run into it (the title) are made narrower
    badge = next((it for it in items if it.get("abs") and it["t"] == "text"), None)
    if badge and not PANEL_MODE:
        bx = badge["rect"]["x"]
        for it in items:
            if it["t"] == "text" and not it.get("abs") and it["rect"]["y"] < MARGIN + badge["rect"]["h"] + 20 and it["rect"]["x"] + it["rect"]["w"] > bx - 30:
                it["rect"]["w"] = bx - 30 - it["rect"]["x"]
    prs = Presentation()
    prs.slide_width, prs.slide_height = E(PAGE_W), E(PAGE_H)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    geo = []
    big = [png2, png3]
    n_arrow = n_pic = n_text = n_table = n_box = 0
    for it in items:
        t = it["t"]
        if it.get("abs") and not PANEL_MODE:                  # the red label sits in the HTML's top margin; in the PPTX it goes just inside the 1 in border
            it["rect"]["y"] = MARGIN
        if t == "box":
            add_box(slide, it, geo); n_box += 1
        elif t == "text":
            add_text(slide, it, geo); n_text += 1
        elif t == "table":
            add_table(slide, it, geo); n_table += 1
        elif t == "svg":
            r = it["rect"]
            if r["w"] < 60:                                    # pipeline arrow
                ar = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, E(r["x"]), E(r["y"] + r["h"] * 0.15), E(r["w"]), E(r["h"] * 0.7))
                ar.shadow.inherit = False
                ar.fill.solid(); ar.fill.fore_color.rgb = hexrgb("#333333"); ar.line.fill.background()
                geo.append((r["x"], r["y"], r["w"], r["h"], "arrow")); n_arrow += 1
            else:
                slide.shapes.add_picture(big.pop(0), E(r["x"]), E(r["y"]), E(r["w"]), E(r["h"]))
                geo.append((r["x"], r["y"], r["w"], r["h"], "picture")); n_pic += 1
    # provenance in the slide notes
    notes = slide.notes_slide.notes_text_frame
    notes.text = (f"Mock-up built from {os.path.basename(a.html)} and numbers.json (csv sha256 {N['csv_sha256']['value'][:16]}, "
                  f"{N['n_bases_with_data']['value']} of {N['n_instances_le100']['value']} instances with data, partial run, not final). "
                  "Orange text = placeholders still to be filled. Delete the red label before submission.")
    prs.save(a.out)
    # geometry check: everything inside the 1 in border (the removable red label is moved inside as well)
    bad = [g for g in geo if g[0] < MARGIN - 1 or g[1] < MARGIN - 1 or g[0] + g[2] > PAGE_W - MARGIN + 1 or g[1] + g[3] > PAGE_H - MARGIN + 1]
    print(f"shapes: {len(slide.shapes)} (boxes {n_box}, text boxes {n_text}, tables {n_table}, arrows {n_arrow}, pictures {n_pic}); outside the 1 in border: {len(bad)}")
    for g in bad:
        print("  outside:", [round(v, 1) for v in g[:4]], g[4])
    print("wrote", a.out)


if __name__ == "__main__":
    main()
