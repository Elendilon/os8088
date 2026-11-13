import math, sys, random
sys.path.insert(0, '.')
from hmodel import *
from arena2 import arena2
today = Arena([Box(*b, 192) for b in A.BOXES], 192, "today")

def yaws(px, py, eye, n=16, pitch=0, W=40, fov=75, a0=0, span=1024):
    for i in range(n):
        yield View(px, py, a0 + span * i / n, eye, pitch, fov, W)

def pbench(W=40):
    for i in range(32):
        ph = 2 * math.pi * i / 32
        yield View(224, 800, 32 + 17 * math.sin(ph), 102, int(16 * math.cos(ph)), 75, W)

BASECELLS = {40: 134, 80: 0}
def run(ar, poses, heights=True, figs=2.7, outline=False):
    tot = {}; n = 0; ms = []
    for v in poses:
        st = render(ar, v, heights, outline=outline); n += 1
        for k, x in st.items(): tot[k] = tot.get(k, 0) + x
        ms.append(frame_ms(st, nfig=figs, heights=heights, extra_cells=max(0, st['cells'] - BASECELLS[v.W])))
    m = {k: x / n for k, x in tot.items()}
    m['ms'] = sum(ms) / n; m['msmax'] = max(ms)
    return m

def sets(ar, W=40, fov=75):
    E = 102
    S = {}
    S['floor (8 places x 16 yaws)'] = [v for (x, y) in [(800, 400), (800, 1650), (1000, 1024), (1600, 600),
                                                         (1600, 1450), (1500, 1024), (1250, 700), (1250, 1350)]
                                       for v in yaws(x, y, E, W=W, fov=fov)]
    S['floor, P-like: (800,400) looking NE'] = list(yaws(800, 400, E, 9, 0, W, fov, 64, 192))
    S['on the platform (16 yaws)'] = list(yaws(1248, 1024, 80 + E, W=W, fov=fov))
    S['platform, jump apex'] = list(yaws(1248, 1024, 80 + E + 64, W=W, fov=fov))
    S['on the tower, west +-45 deg, level'] = list(yaws(1952, 1024, 160 + E, 9, 0, W, fov, 384, 256))
    S['on the tower, west, looking down (pitch -60)'] = list(yaws(1952, 1024, 160 + E, 9, -60, W, fov, 384, 256))
    S['on a raised lift, west'] = list(yaws(1952, 768, 160 + E, 9, -30, W, fov, 384, 256))
    S['hallway (4 places x 16 yaws)'] = [v for (x, y) in [(576, 1024), (320, 1024), (448, 640), (448, 1408)]
                                         for v in yaws(x, y, E, W=W, fov=fov)]
    S['back room'] = list(yaws(96, 1200, E, W=W, fov=fov))
    return S

if __name__ == "__main__":
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    keys = ['ms', 'msmax', 'leaf_in', 'face_drew', 'face_end', 'top_faces', 'spans', 'top_spans', 'cols',
            'cols_hidden', 'top_cols', 'lowboxes', 'edges', 'ecols', 'cells', 'stack']
    print("%-46s" % "set" + "".join("%9s" % k[:9] for k in keys))
    def row(name, m):
        print("%-46s" % name[:46] + "".join("%9.1f" % m[k] for k in keys))
    tp = run(today, pbench(W), False)
    BASECELLS[W] = tp['cells']
    row("TODAY P bench", tp)
    for name, ps in sets(today, W).items():
        if 'floor' in name and 'P-like' not in name:
            row("TODAY " + name, run(today, ps, False))
    for label, kw, ol in [("A: hb 6m, 4 steps, spans", {}, False), ("B: hb 3m, 4 steps, spans", dict(hb=192), False),
                      ("C: hb 6m, 2 steps, spans", dict(steps=2), False),
                      ("D: hb 6m, 4 steps, OUTLINE path", {}, True),
                      ("E: hb 6m, 2 steps, OUTLINE path", dict(steps=2), True),
                      ("F: hb 3m, 4 steps, OUTLINE path", dict(hb=192), True),
                      ("G: hb 6m, 4-tread FLIGHT objects, OUTLINE", dict(flight=True), True)]:
        ar = arena2(**kw)
        print("--", label)
        for name, ps in sets(ar, W).items():
            row(name, run(ar, ps, outline=ol))
