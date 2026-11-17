import sys, collections
W = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "../../../.."))
sys.path.insert(0, W + "/tools")
import bbcourse as B
VOID = -32768
names = sys.argv[1:]
print("course | surfaced blocks | occluding blocks | records | distinct masks | today occ RAM (I+R+K+O) | per-pixel 2bpp (occluding blocks, +palette) | 4x4 2bpp (occluding blocks, +palette) | 4x4 2bpp whole picture | max keys/block")
for n in names:
    c = B.compile_course(W + "/apps/bonanza/courses/" + n)
    blocks = collections.defaultdict(list)
    for r in c.records: blocks[(r["brow"], r["col"])].append(r)
    surf = sum(1 for br in range(c.brows) for bc in range(c.cols)
               if any(c.sbuf[y][x] != VOID for y in range(br*8, min(br*8+8, c.lines)) for x in range(bc*8, min(bc*8+8, c.width))))
    nmask = len({r["mask"] for r in c.records})
    nocc = len(blocks)
    pal = sum(min(3, len(v)) * 2 for v in blocks.values())      # a (row, top) byte pair per palette entry
    today = 2*(c.brows+1) + 4*len(c.records) + 16*nmask + 2*nmask
    full = 16*nocc + pal
    coarse = 1*nocc + pal
    whole = c.cols*c.brows + 3*2*surf
    print("%s | %d | %d | %d | %d | %d | %d | %d | %d | %d" % (c.name, surf, nocc, len(c.records), nmask, today, full, coarse, whole, max(len(v) for v in blocks.values())))
