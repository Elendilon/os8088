"""price a sketch's sections, 137.11.15's method (each instruction at max(EU + EA, 4.34 a byte), the sum x 1.05),
straight through each section (branches not taken unless named in TAKEN).  usage: price.py file.asm sec1 sec2 ..."""
import sys, os, re, subprocess, tempfile
sys.path.insert(0, "tests")
import bonanza_dsplit as D

src = sys.argv[1]
secs = sys.argv[2:]
td = tempfile.mkdtemp()
lst, out = os.path.join(td, "s.lst"), os.path.join(td, "s.bin")
subprocess.check_call(["nasm", "-f", "bin", "-o", out, "-l", lst, src])
size = os.path.getsize(out)
cur, tot, nb = None, {}, {}
for ln in open(lst):
    m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s+([0-9A-F\[\]()]+)\s+(.*)", ln.rstrip("\n"))
    if not m:
        m2 = re.match(r"\s*\d+\s+(.*)", ln.rstrip("\n"))
        t = m2.group(1).strip() if m2 else ""
        lab = re.match(r"(\w+):", t)
        if lab and lab.group(1) in secs:
            cur = lab.group(1)
        continue
    hexb, text = m.group(2), m.group(3)
    lab = re.match(r"(\w+):", text.strip())
    if lab and lab.group(1) in secs:
        cur = lab.group(1)
    n = len(re.sub(r"[^0-9A-F]", "", hexb)) // 2
    if cur is None or not text.split(";")[0].strip():
        continue
    tk = "TAKEN" in text
    eu = D.price_line(text, 0, taken=tk)
    tot[cur] = tot.get(cur, 0) + max(eu, 4.34 * n)
    nb[cur] = nb.get(cur, 0) + n
print("%s: %d bytes assembled" % (src, size))
for s in secs:
    print("  %-8s %5d bytes, %6.0f clk" % (s, nb.get(s, 0), 1.05 * tot.get(s, 0)))
