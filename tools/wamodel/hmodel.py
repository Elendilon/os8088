"""hmodel - a host model of WireArena's wall renderer, today's and the heights
one (WIREARENA-HEIGHTS-PLAN). Counts per frame what the renderer does, and
prices it with unit costs MEASURED on a4edcb7f (trace.py / anal.py)."""
import math, sys
sys.path.insert(0, '/home/user/wt/heights-plan/tools')
import arenagen as A

ROOM = (0, 0, 2048, 2048)
NEAR = 16
FOVF = {90: 256, 75: 334, 60: 443}
KYQ = 133

# --- unit costs, guest clk (Measured, P bench 40 col, a4edcb7f: anal.py) ---
C = dict(setup=13538, leaf_cull=705, leaf_in=1546, face_box_drew=3752,
         face_box_end=2229, face_room_drew=4745, face_room_end=2681,
         span=5041, col=662, fig=15800, cross=1693, glue=1429,
         present_loop=33071, cell_present=138)
# --- Forecast increments for the heights renderer ---
CF = dict(col_clip=120,       # per visited column: load, compare, update clip
          col_hidden=90,      # a column visited, nothing visible (below clip)
          top_span=3800,      # a far top edge's span setup (one edge pass)
          top_col=420,        # ...a column of it
          face_h=250,         # per face: the box's own top height (imul/vertex)
          stack=40,           # per clip change: the depth stack push
          fig_cell=120,       # per figure cell: the stack walk
          height_setup=200,   # per distinct box height a frame (numt)
          # the OUTLINE path for a box lower than the tallest (variant D):
          lowbox=5200,        # its corners: transforms, columns, tops, bottoms
          edge=700,           # an outline edge's setup (one divide)
          ecol=180,           # ...a column of it, clip-tested and plotted
          ehid=60)            # ...a column of it, hidden or shut


class Box:
    def __init__(s, x0, y0, x1, y1, h, name=""):
        s.x0, s.y0, s.x1, s.y1, s.h, s.name = x0, y0, x1, y1, h, name

    def t(s):
        return (s.x0, s.y0, s.x1, s.y1)


def faces(b):
    c = [(b.x0, b.y0), (b.x1, b.y0), (b.x1, b.y1), (b.x0, b.y1)]
    return [(c[0], c[1], 'S'), (c[1], c[2], 'E'), (c[2], c[3], 'N'), (c[3], c[0], 'W')]


def outside(b, px, py):
    """front faces (the player is outside of), back faces"""
    fr = []
    if py < b.y0: fr.append('S')
    elif py > b.y1: fr.append('N')
    if px > b.x1: fr.append('E')
    elif px < b.x0: fr.append('W')
    return fr


class Arena:
    def __init__(s, boxes, room_h, name):
        s.boxes, s.room_h, s.name = boxes, room_h, name
        s.nodes = []
        A.box_tree(list(range(len(boxes))), s.nodes, [b.t() for b in boxes])
        s.hmax = max([room_h] + [b.h for b in boxes])

    def order(s, px, py):
        out = []
        def n(i):
            k, box, v, lo, hi, ids = s.nodes[i]
            if k == 2:
                out.append(box); return
            p = px if k == 0 else py
            a, b = (lo, hi) if p < v else (hi, lo)
            n(a); n(b)
        n(0)
        return out


class View:
    def __init__(s, px, py, ang, eye, pitch=0, fov=75, W=40):
        s.px, s.py, s.eye, s.W = px, py, eye, W
        a = ang * 2 * math.pi / 1024
        s.s, s.c = math.sin(a), math.cos(a)
        f = FOVF[fov]
        s.k16 = (8 * W * f) >> 8
        s.c16 = 8 * W
        s.kyq = (KYQ * f) >> 8
        s.hq = pitch + 96
        s.t = 256.0 / f
        s.tc = {90: 1.0, 75: 25 / 32, 60: 19 / 32}[fov]

    def cam(s, p):
        dx, dy = p[0] - s.px, p[1] - s.py
        return dx * s.s - dy * s.c, dx * s.c + dy * s.s

    def row(s, h, z):           # half-row of height h at depth z
        return int(math.floor((s.hq - (h - s.eye) * s.kyq / z + 2) / 4))


def cone_out(b, v):
    pts = [v.cam(p) for p in ((b.x0, b.y0), (b.x1, b.y0), (b.x1, b.y1), (b.x0, b.y1))]
    if all(z < NEAR for x, z in pts): return True
    t = v.tc                    # wa_leaf: 90 degrees, then 1 - u (7/32, 13/32)
    if all(x > t * z + 4 for x, z in pts): return True
    if all(x < -t * z - 4 for x, z in pts): return True
    return False


def render(ar, v, heights=True, stats=None, outline=False):
    """-> dict of counts and clk. heights=False: today's renderer (every face
    shuts its columns)."""
    W = v.W
    shut = [False] * W
    clip = [48] * W            # rows >= clip are covered (half-rows)
    st = dict(leaf_cull=0, leaf_in=0, face_drew=0, face_end=0, rface_drew=0,
              rface_end=0, top_faces=0, top_end=0, spans=0, top_spans=0, cols=0,
              cols_hidden=0, top_cols=0, cells=0, stack=0, stackmax=0, clk=0,
              lowboxes=0, edges=0, ecols=0)
    depth = [0] * W
    clk = C['setup'] + C['glue']
    if heights:
        clk += CF['height_setup'] * len({b.h for b in ar.boxes})

    def left():
        return W - sum(shut)

    def span(p1, p2, h, kind, tall, cheap=False):
        """kind 'front' (top and bottom edges, corners) or 'top' (one edge)"""
        nonlocal clk
        (x1, z1), (x2, z2) = v.cam(p1), v.cam(p2)
        if z1 < NEAR and z2 < NEAR:
            return False
        if z1 < NEAR or z2 < NEAR:      # near clip
            t = (NEAR - z1) / (z2 - z1)
            xn = x1 + t * (x2 - x1)
            if z1 < NEAR: x1, z1 = xn, NEAR
            else: x2, z2 = xn, NEAR
        def col16(x, z):
            x = max(-8 * z, min(8 * z, x))
            return v.c16 + x * v.k16 / z
        c1, c2 = col16(x1, z1), col16(x2, z2)
        if c1 > c2:
            if kind == 'front':
                return False
            c1, c2, x1, z1, x2, z2 = c2, c1, x2, z2, x1, z1
        a = (int(c1) + 7) >> 4
        b = ((int(c2) + 7) >> 4) - 1
        a, b = max(a, 0), min(b, W - 1)
        if a > b:
            return False
        if all(shut[c] for c in range(a, b + 1)):
            return False
        # a span
        i1, i2 = 1 / z1, 1 / z2
        nvis = nhid = ncells = 0
        for c in range(a, b + 1):
            if shut[c]:
                continue
            u = (16 * c + 8 - c1) / max(c2 - c1, 1e-9)
            iz = i1 + (i2 - i1) * u
            z = 1 / iz
            t = v.row(h, z)
            bt = v.row(0, z)
            vis = 0
            if t < clip[c] and 0 <= t < 48: vis += 1
            if kind == 'front' and bt < clip[c] and 0 <= bt < 48 and bt != t: vis += 1
            if kind == 'front' and (c == a or c == b):     # a corner post
                lo, hi = max(t + 1, 0), min(bt, clip[c], 48)
                vis += max(0, hi - lo) // 2
            if vis == 0 and t >= clip[c]:
                nhid += 1
            else:
                nvis += 1
            ncells += vis
            if tall:
                shut[c] = True
            else:
                if t < clip[c]:
                    clip[c] = t
                    depth[c] += 1
                    st['stack'] += 1
                    st['stackmax'] = max(st['stackmax'], depth[c])
                # nothing behind can show above this row?
                hz = ar.hmax - v.eye
                lim = v.row(ar.hmax, z) if hz > 0 else v.row(v.eye, 1e9)
                if clip[c] <= max(lim, 0):
                    shut[c] = True
        st['cells'] += ncells
        if cheap:
            st['edges'] += 1 + (kind == 'front'); st['ecols'] += (nvis + nhid) * (1 + (kind == 'front'))
            clk += CF['edge'] * (1 + (kind == 'front')) + (CF['ecol'] * nvis + CF['ehid'] * nhid) * (1 + (kind == 'front'))
        elif kind == 'front':
            st['spans'] += 1; st['cols'] += nvis; st['cols_hidden'] += nhid
            clk += C['span'] + C['col'] * nvis
            if heights:
                clk += CF['col_clip'] * nvis + CF['col_hidden'] * nhid
        else:
            st['top_spans'] += 1; st['top_cols'] += nvis + nhid
            clk += CF['top_span'] + CF['top_col'] * nvis + CF['col_hidden'] * nhid
        return True

    for bi in ar.order(v.px, v.py):
        if left() == 0:
            break
        b = ar.boxes[bi]
        if cone_out(b, v):
            st['leaf_cull'] += 1; clk += C['leaf_cull']; continue
        st['leaf_in'] += 1; clk += C['leaf_in']
        fr = outside(b, v.px, v.py)
        fs = {f[2]: f for f in faces(b)}
        tall = (not heights) or (b.h >= ar.hmax and v.eye < b.h)
        cheap = outline and not tall
        if cheap:
            st['lowboxes'] += 1; clk += CF['lowbox'] - C['leaf_in'] + 600
            tr = getattr(b, 'treads', 0)
            if tr:                      # a flight: its treads, as extra edges
                (x1, z1), (x2, z2) = v.cam((b.x0, b.y0)), v.cam((b.x1, b.y0))
                if z1 > NEAR and z2 > NEAR:
                    ca = v.c16 + x1 * v.k16 / z1; cb = v.c16 + x2 * v.k16 / z2
                    ncol = max(0, min(W - 1, int(max(ca, cb)) >> 4) - max(0, int(min(ca, cb)) >> 4) + 1)
                    st['edges'] += tr; st['ecols'] += tr * ncol
                    clk += tr * (CF['edge'] + CF['ecol'] * ncol)
        for k in fr[:2]:
            p1, p2, _ = fs[k]
            ok = span(p1, p2, b.h, 'front', tall, cheap)
            if cheap: continue
            if ok: st['face_drew'] += 1; clk += C['face_box_drew']
            else: st['face_end'] += 1; clk += C['face_box_end']
            if heights: clk += CF['face_h']
        if heights and v.eye > b.h:     # the far top edges: the back faces' tops
            opp = {'S': 'N', 'N': 'S', 'E': 'W', 'W': 'E'}
            back = [k for k in 'SENW' if k not in fr]
            for k in back:
                if k in fr: continue
                p1, p2, _ = fs[k]
                st['top_faces'] += 1
                ok = span(p2, p1, b.h, 'top', False, cheap)
                if cheap: continue
                clk += C['face_box_drew'] if ok else C['face_box_end']
                if not ok: st['top_end'] += 1
    if left():
        r = ROOM
        rc = [(r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])]
        for p1, p2 in ((rc[0], rc[3]), (rc[3], rc[2]), (rc[2], rc[1]), (rc[1], rc[0])):
            ok = span(p1, p2, ar.room_h, 'front', True)
            if ok: st['rface_drew'] += 1; clk += C['face_room_drew']
            else: st['rface_end'] += 1; clk += C['face_room_end']
    st['clk'] = clk
    return st


def frame_ms(st, nfig=2.7, figcells=15, heights=True, extra_cells=0):
    clk = st['clk'] + C['fig'] * nfig + C['cross'] + C['present_loop']
    if heights:
        clk += CF['fig_cell'] * figcells + CF['stack'] * st['stack']
        clk += C['cell_present'] * 2 * extra_cells
    return clk / 4772.727
