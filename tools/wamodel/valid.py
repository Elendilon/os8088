import math, sys
sys.path.insert(0, '.')
from hmodel import *
today = Arena([Box(*b, 192) for b in A.BOXES], 192, "today")
def pposes(W=40):
    for i in range(32):
        ph = 2 * math.pi * i / 32
        yield View(224, 800, 32 + 17 * math.sin(ph), 102, int(16 * math.cos(ph)), 75, W)
def avg(ar, poses, heights):
    tot = {}; n = 0; ms = 0
    for v in poses:
        st = render(ar, v, heights); n += 1
        for k, x in st.items(): tot[k] = tot.get(k, 0) + x
        ms += frame_ms(st, heights=heights)
    return {k: x / n for k, x in tot.items()}, ms / n
st, ms = avg(today, pposes(), False)
for k in sorted(st): print("  %-12s %8.2f" % (k, st[k]))
print("frame ms %.1f  (render part %.1f)" % (ms, st['clk'] / 4772.727))
