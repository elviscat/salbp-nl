"""Write data/SOURCES.md: URL, size, sha256 and timestamp for each downloaded file.
Files were downloaded with curl into data/raw/ (see REPORT.md). This script only hashes them."""
import hashlib, os, datetime, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
FILES = [
 ("https://assembly-line-balancing.de/", "index.html"),
 ("https://assembly-line-balancing.de/salbp/benchmark-data-sets-1993/", "benchmark-data-sets-1993.html"),
 ("https://assembly-line-balancing.de/salbp/benchmark-data-sets-2013/", "benchmark-data-sets-2013.html"),
 ("https://assembly-line-balancing.de/wp-content/uploads/2017/01/SALBP-data-sets.zip", "z1993/SALBP-data-sets.zip"),
 ("https://assembly-line-balancing.de/wp-content/uploads/2017/01/SALBP_benchmark.zip", "z2013/SALBP_benchmark.zip"),
 ("https://assembly-line-balancing.de/wp-content/uploads/2017/01/Scholl-1993-ALBData.pdf", "docs/Scholl-1993-ALBData.pdf"),
 ("https://assembly-line-balancing.de/wp-content/uploads/2017/01/format-ALB.pdf", "docs/format-ALB.pdf"),
]
lines = ["# Data sources", "", "All files downloaded from assembly-line-balancing.de (Scholl). Treated as untrusted data: only parsed, never executed.", "",
         "| URL | local path (under data/raw/) | bytes | sha256 | file mtime (local) |", "|---|---|---|---|---|"]
for url, rel in FILES:
    p = os.path.join(ROOT, "data", "raw", rel)
    b = open(p, "rb").read()
    mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).isoformat(timespec="seconds")
    lines.append(f"| {url} | {rel} | {len(b)} | {hashlib.sha256(b).hexdigest()} | {mt} |")
lines += ["", f"Log generated: {datetime.datetime.now().isoformat(timespec='seconds')}", "",
 "Extracted (not separately hashed): z1993/precedence graphs/*.IN2 (Scholl 1993 graphs), z1993/SALBP data sets.xlsx (best-known table, sheet 'SALBP-1 data set'), z2013/small/ and z2013/med/ (Otto et al. 2013 .alb files)."]
open(os.path.join(ROOT, "data", "SOURCES.md"), "w").write("\n".join(lines) + "\n")
print("ok")
