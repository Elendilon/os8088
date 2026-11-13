#!/usr/bin/env python3
"""arenagen - WireArena's host-built tables (docs/plans/MULTIPLAYER-FPS-PLAN.md).

Writes one NASM include, deterministic byte for byte. Its constants are
always defined; each DATA block is assembled only where the includer asks for
it (docs/plans/WIREARENA-PARTS-PLAN.md: the primary and the renderer part
each take what they read):

  WA_TAB_SIN     wa_sin
  WA_TAB_ARENAS  every arena's tables and wa_arenas
  WA_TAB_PATHS   wa_pathtab and the patrols
  WA_TAB_POSE    wa_pose

  wa_sin        1024 words, sin in Q14 (16384 = 1.0); cos(a) = wa_sin[a+256]
  wa_boxes      the arena's solid blocks, axis-aligned, in world units
  wa_room       the room's inner bounds
  wa_paths      each dummy's patrol: waypoints with the leg's heading and
                step count precomputed, so the guest needs no atan2
  wa_pose       the stick figure's keyframes, PRE-PROJECTED for 16 view
                facings: per frame, per facing, 11 joints of (lateral, height)
                as signed bytes in world units

World units are 1/64 m. Angles are 1024 to a turn, counter-clockwise from
+x, the map's y axis pointing "north".

    python3 tools/arenagen.py build/watab.inc
"""
import math
import sys

UNIT = 64.0                     # world units a metre
NFACE = 16                      # view facings a pose is projected for
SPEED = 8                       # a dummy's run, units a 30 Hz tick (~4.8 m/s)

# --- the arena: a 32 m room with blocks in it (x0, y0, x1, y1), units ------
ROOM = (0, 0, 2048, 2048)
BOXES = [
    (448, 448, 576, 576),       # four pillars round the middle
    (1472, 448, 1600, 576),
    (448, 1472, 576, 1600),
    (1472, 1472, 1600, 1600),
    (896, 960, 1152, 1088),     # a long block across the centre
    (192, 960, 256, 1088),      # stubs off the west and east walls
    (1792, 960, 1856, 1088),
    (960, 192, 1088, 320),      # and off the south and north ones
    (960, 1728, 1088, 1856),
]
# The open arena: the same room, only the four pillars - the sparser level
# that asks how much of a frame the scene's own complexity costs.
OPEN_BOXES = BOXES[:4]
# x, y, angle. NOT (1024, 256), where Wave 0 started: that is inside the
# south stub, so every step collided and WASD looked dead. arenas() checks.
PLAYER_START = (1024, 480, 256)  # facing north, the patrols crossing ahead

def arenas():
    return [("a0", "Arena", BOXES, PLAYER_START),
            ("a1", "Open", OPEN_BOXES, PLAYER_START)]

# --- the dummies' patrols: closed loops of waypoints clear of every block ----
PATHS = [
    [(320, 384), (1728, 384), (1728, 768), (320, 768)],
    [(768, 1280), (1280, 1280), (1280, 1664), (768, 1664)],
    [(1728, 1664), (1728, 1280), (1344, 800), (704, 800), (320, 1280),
     (320, 1664)],
]

# --- the skeleton ------------------------------------------------------------
# joints: 0 head, 1 neck, 2 pelvis, 3 L elbow, 4 L hand, 5 R elbow, 6 R hand,
#         7 L knee, 8 L foot, 9 R knee, 10 R foot
# local frame: x right, y up, z forward (metres)
NJ = 11
assert NJ == 11, "wrender.inc's WA_LIMB calls and WA_MINMAX are written for 11"
THIGH, SHIN, UARM, FARM = 0.46, 0.46, 0.30, 0.28


def rot_x(p, about, ang):
    """Rotate point p round the x axis through `about` by ang (radians);
    positive tips +y toward +z (forward)."""
    x, y, z = p
    ay, az = about[1], about[2]
    dy, dz = y - ay, z - az
    c, s = math.cos(ang), math.sin(ang)
    return (x, ay + dy * c + dz * s, az - dy * s + dz * c)


def limb(base, ang, length):
    """A limb from base hanging DOWN, swung forward by ang (radians)."""
    return (base[0], base[1] - length * math.cos(ang),
            base[2] + length * math.sin(ang))


def pose(hipL, kneeL, hipR, kneeR, shL, elL, shR, elR, lean=0.0, bob=0.0,
         fall=0.0, sink=0.0):
    """Angles in degrees. hip/shoulder: forward swing of the upper limb;
    knee: backward bend of the shin; elbow: forward bend of the forearm.
    lean tips the torso forward about the pelvis; fall tips the WHOLE body
    backward about the feet's line; sink lowers the pelvis (bent knees)."""
    r = math.radians
    pel = (0.0, 0.96 + bob - sink, 0.0)
    neck = (0.0, pel[1] + 0.52, 0.0)
    head = (0.0, neck[1] + 0.22, 0.0)
    shoulderL = (-0.17, neck[1] - 0.04, 0.0)
    shoulderR = (0.17, neck[1] - 0.04, 0.0)
    eL = limb(shoulderL, r(shL), UARM)
    hL = limb(eL, r(shL + elL), FARM)
    eR = limb(shoulderR, r(shR), UARM)
    hR = limb(eR, r(shR + elR), FARM)
    upper = [head, neck, eL, hL, eR, hR]
    if lean:
        upper = [rot_x(p, pel, r(lean)) for p in upper]
    head, neck, eL, hL, eR, hR = upper
    hipLp = (-0.10, pel[1], 0.0)
    hipRp = (0.10, pel[1], 0.0)
    kL = limb(hipLp, r(hipL), THIGH)
    fL = limb(kL, r(hipL - kneeL), SHIN)
    kR = limb(hipRp, r(hipR), THIGH)
    fR = limb(kR, r(hipR - kneeR), SHIN)
    pts = [head, neck, pel, eL, hL, eR, hR, kL, fL, kR, fR]
    if fall:
        pts = [rot_x(p, (0, 0, 0), -r(fall)) for p in pts]
        low = min(p[1] for p in pts)
        if low < 0:             # nothing sinks through the floor
            pts = [(p[0], p[1] - low, p[2]) for p in pts]
    return pts


def run_frame(i, n):
    t = 2 * math.pi * i / n
    sw = math.sin(t)
    return pose(hipL=38 * sw, kneeL=15 + 55 * max(0.0, -math.sin(t + 0.6)),
                hipR=-38 * sw, kneeR=15 + 55 * max(0.0, math.sin(t + 0.6)),
                shL=-35 * sw, elL=75, shR=70, elR=10,   # R arm: the pistol
                lean=10, bob=0.05 * abs(math.cos(t)))


def idle_frame(i, n):
    b = 0.012 * math.sin(2 * math.pi * i / n)
    return pose(4, 6, -4, 6, 6, 15, 80, 5, bob=b)


def flinch_frame(i, n):
    k = [0.6, 1.0, 0.5][i]
    return pose(10 * k, 20 * k, -6 * k, 20 * k, -50 * k, 40, 40 - 60 * k, 30,
                lean=-22 * k, sink=0.06 * k)


def death_frame(i, n):
    k = (i + 1) / n
    e = k * k                   # gathers speed as it goes over
    return pose(25 * k, 70 * k, 10 * k, 90 * k, -60 * k - 20, 30 + 40 * k,
                -40 * k, 50 * k, lean=-15 * k, fall=88 * e, sink=0.3 * k)


ANIMS = [                       # name, keyframes, builder
    ("IDLE", 4, idle_frame),
    ("RUN", 8, run_frame),
    ("FLINCH", 3, flinch_frame),
    ("DEATH", 8, death_frame),
]


def project(pts, k):
    rel = 2 * math.pi * k / NFACE
    c, s = math.cos(rel), math.sin(rel)
    out = []
    for (x, y, z) in pts:
        lat = x * c - z * s
        out.append((int(round(lat * UNIT)), int(round(y * UNIT))))
    return out


def sb(v):
    if not -128 <= v <= 127:
        raise SystemExit("arenagen: %d does not fit a signed byte" % v)
    return v & 0xFF


def angle_of(dx, dy):
    a = math.atan2(dy, dx)
    return int(round(a * 1024 / (2 * math.pi))) & 1023


# --- the BSP (docs/plans/MULTIPLAYER-FPS-PLAN.md section 16, lever 1) --------
# Over BOXES, not segments: a box's faces never hide one another (it is
# convex), so the tree only has to order the boxes, front to back, and the
# room - which encloses everything - is drawn last. Every split is an
# axis-aligned line that separates the boxes WITHOUT cutting one, so the
# guest's node test is one compare and a leaf is one box; an arena with no
# such line is refused here, at build time.
#
# A wall face is one-sided: drawn when the player is on its outer side, and
# p1 -> p2 runs left to right seen from the front. A box's corners are
# c0 (x0,y0), c1 (x1,y0), c2 (x1,y1), c3 (x0,y1); its faces are south c0->c1,
# east c1->c2, north c2->c3, west c3->c0. The room's run the other way.

def box_tree(ids, nodes, BOXES):
    """-> node index. nodes: [kind, box, value, low, high]; kind 0 splits on
    x, 1 on y, 2 is a leaf holding one box."""
    me = len(nodes)
    nodes.append(None)
    if len(ids) == 1:
        nodes[me] = [2, ids[0], 0, -1, -1, ids]
        return me
    best = None
    for axis in (0, 1):
        for v in sorted({BOXES[i][axis] for i in ids} |
                        {BOXES[i][axis + 2] for i in ids}):
            low = [i for i in ids if BOXES[i][axis + 2] <= v]
            high = [i for i in ids if BOXES[i][axis] >= v]
            if low and high and len(low) + len(high) == len(ids):
                score = abs(len(low) - len(high))
                if best is None or score < best[0]:
                    best = (score, axis, v, low, high)
    if best is None:
        raise SystemExit("arenagen: no axis-aligned line separates boxes %r "
                         "without cutting one - move a box" % ids)
    _, axis, v, low, high = best
    lo = box_tree(low, nodes, BOXES)
    hi = box_tree(high, nodes, BOXES)
    nodes[me] = [axis, 0, v, lo, hi, ids]
    return me


def inside(x, y, boxes, r):
    if not (ROOM[0] + r < x < ROOM[2] - r and ROOM[1] + r < y < ROOM[3] - r):
        return True
    return any(a - r < x < c + r and b - r < y < d + r
               for (a, b, c, d) in boxes)


MAXKS = 8          # distinct steps between coordinates (wa_products)


def arena_tables(w, tag, boxes, start):
    """One arena's tables, every label prefixed wa_<tag>_; -> its counts."""
    if inside(start[0], start[1], boxes, 20):
        raise SystemExit("arenagen: arena %s starts the player INSIDE a wall "
                         "at %r - every step would collide" % (tag, start))
    for p in PATHS:
        for j in range(len(p)):
            (x0, y0), (x1, y1) = p[j], p[(j + 1) % len(p)]
            for k in range(33):
                x, y = x0 + (x1 - x0) * k / 32, y0 + (y1 - y0) * k / 32
                if inside(x, y, boxes, 12):
                    raise SystemExit("arenagen: arena %s: a patrol runs into "
                                     "a wall near (%d, %d)" % (tag, x, y))
    nodes = []
    box_tree(list(range(len(boxes))), nodes, boxes)
    pts = []
    for (a, b, c, d) in [ROOM] + boxes:
        pts += [(a, b), (c, b), (c, d), (a, d)]
    xs = sorted({p[0] for p in pts})
    ys = sorted({p[1] for p in pts})
    verts, vix = [], {}
    for p in pts:
        if p not in vix:
            vix[p] = len(verts)
            verts.append(p)
    if len(verts) * 2 > 255 or len(boxes) * 8 > 255 or len(xs) * 4 > 255 \
            or len(ys) * 4 > 255:
        raise SystemExit("arenagen: the arena outgrew a byte index")
    # wa_products makes a coordinate's products from the one before it, by
    # adding the products of the STEP between them, made once a frame: so
    # the distinct steps an arena has are few, and each fits x 4 in 16 bits
    steps = {b - a for vals in (xs, ys) for a, b in zip(vals, vals[1:])}
    if len(steps) > MAXKS or max(steps) * 4 > 32767:
        raise SystemExit("arenagen: arena %s: %d distinct coordinate steps, "
                         "largest %d - wa_products takes at most %d, each "
                         "under 8192" % (tag, len(steps), max(steps), MAXKS))
    for (a, b, c, d) in boxes:
        if not (ROOM[0] < a < c < ROOM[2] and ROOM[1] < b < d < ROOM[3]):
            raise SystemExit("arenagen: arena %s: a box outside the room - "
                             "WA_ZMAX assumes none is" % tag)
    P = "wa_%s_" % tag
    w(P + "xv:      dw " + ", ".join(str(x) for x in xs))
    w(P + "yv:      dw " + ", ".join(str(y) for y in ys))
    w(P + "vtx:                         ; x index x 4, y index x 4 (byte offsets")
    w("                                ; into the per-frame product tables)")
    for (x, y) in verts:
        w("    db %d, %d" % (xs.index(x) * 4, ys.index(y) * 4))
    w(P + "corn:                        ; per box (the room first): its corners")
    w("                                ; c0..c3 as vertex x 2")
    for (a, b, c, d) in [ROOM] + boxes:
        w("    db " + ", ".join(str(vix[p] * 2) for p in
                                [(a, b), (c, b), (c, d), (a, d)]))
    w(P + "bsp:                         ; kind (0 x, 1 y, 2 leaf), box x 8 (a")
    w("                                ; leaf's, into wa_boxes), value, low,")
    w("                                ; high (0 = none) - ABSOLUTE: the tree")
    w("                                ; is walked in place, not copied - and")
    w("                                ; the bounds of the boxes under it, x0")
    w("                                ; y0 x1 y1 as coordinate indices x 4,")
    w("                                ; for wa_node's view-cone test")
    for (kind, box, v, lo, hi, ids) in nodes:
        bb = (min(boxes[i][0] for i in ids), min(boxes[i][1] for i in ids),
              max(boxes[i][2] for i in ids), max(boxes[i][3] for i in ids))
        w("    db %d, %d" % (kind, box * 8))
        w("    dw %d, %s, %s" % (v, P + "bsp+%d" % (lo * 12) if lo >= 0 else "0",
                              P + "bsp+%d" % (hi * 12) if hi >= 0 else "0"))
        w("    db %d, %d, %d, %d" % (xs.index(bb[0]) * 4, ys.index(bb[1]) * 4,
                                    xs.index(bb[2]) * 4, ys.index(bb[3]) * 4))
    w(P + "bcol:                        ; per box (the room first): its colour")
    w("                                ; - 0 a boundary wall, 1 an item. The")
    w("                                ; owner's call: colour says WHAT a wall")
    w("                                ; is, not how far (two shades never read")
    w("                                ; as depth, and Hercules has none)")
    w("    db 0" + "".join(", 1" for _ in boxes))
    w(P + "boxes:                       ; x0, y0, x1, y1")
    for b in boxes:
        w("    dw %d, %d, %d, %d" % b)
    sys.stderr.write("arenagen: arena %s: %d boxes in a %d-node tree, %d "
                     "vertices, %d x and %d y values\n"
                     % (tag, len(boxes), len(nodes), len(verts), len(xs),
                        len(ys)))
    return len(xs), len(ys), len(verts), len(boxes)


def bsp_tables(w):
    """Every arena, then their descriptors (SPEC: wa_loadarena copies one into
    the working tables; the tree stays where it is) and the maxima the
    working tables are sized to."""
    counts = []
    w("%ifdef WA_TAB_ARENAS")
    for tag, name, boxes, start in arenas():
        counts.append(arena_tables(w, tag, boxes, start))
    w("%endif")
    w("WA_NARENA equ %d" % len(counts))
    w("WA_MXV equ %d" % max(c[0] for c in counts))
    w("WA_MYV equ %d" % max(c[1] for c in counts))
    w("WA_MVTX equ %d" % max(c[2] for c in counts))
    w("WA_MBOX equ %d" % max(c[3] for c in counts))
    w("WA_MAXKS equ %d" % MAXKS)
    # the deepest a point can be: the player and every wall are in the room,
    # so no z exceeds its diagonal (wa_rcp covers NEAR..WA_ZMAX-1)
    w("WA_ZMAX equ %d" % (int(math.hypot(ROOM[2] - ROOM[0],
                                         ROOM[3] - ROOM[1])) + 2))
    w("%ifdef WA_TAB_ARENAS")
    w("wa_arenas:                      ; xv, nxv, yv, nyv, vtx, nvtx, corn,")
    w("                                ; boxes, nbox, root, start x, y, angle,")
    w("                                ; colours")
    for (tag, name, boxes, start), (nx, ny, nv, nb) in zip(arenas(), counts):
        P = "wa_%s_" % tag
        w("    dw %sxv, %d, %syv, %d, %svtx, %d, %scorn" % (P, nx, P, ny, P, nv, P))
        w("    dw %sboxes, %d, %sbsp, %d, %d, %d, %sbcol" % (
            P, nb, P, start[0], start[1], start[2], P))
    w("%endif")
    w("WA_ARENASZ equ 28")

def main(out):
    L = []
    w = L.append
    w("; GENERATED by tools/arenagen.py - do not edit (docs/plans/"
      "MULTIPLAYER-FPS-PLAN.md)")
    w("WA_NJ equ %d" % NJ)
    w("WA_NFACE equ %d" % NFACE)
    w("WA_SPEED equ %d" % SPEED)
    w("WA_ROOM_X0 equ %d" % ROOM[0])
    w("WA_ROOM_Y0 equ %d" % ROOM[1])
    w("WA_ROOM_X1 equ %d" % ROOM[2])
    w("WA_ROOM_Y1 equ %d" % ROOM[3])
    w("%ifdef WA_TAB_SIN")
    w("wa_sin:")
    for i in range(0, 1024, 8):
        w("    dw " + ", ".join(str(int(round(16384 * math.sin(
            2 * math.pi * j / 1024)))) for j in range(i, i + 8)))
    w("%endif")
    bsp_tables(w)
    # paths: per dummy, a count and per leg (x, y, heading, steps)
    w("WA_NFIG equ %d" % len(PATHS))
    w("%ifdef WA_TAB_PATHS")
    w("wa_pathtab:")
    for i in range(len(PATHS)):
        w("    dw wa_path%d" % i)
    for i, p in enumerate(PATHS):
        w("wa_path%d:" % i)
        w("    dw %d                      ; legs" % len(p))
        for j, (x, y) in enumerate(p):
            nx, ny = p[(j + 1) % len(p)]
            dx, dy = nx - x, ny - y
            steps = max(1, int(round(math.hypot(dx, dy) / SPEED)))
            w("    dw %d, %d, %d, %d" % (x, y, angle_of(dx, dy), steps))
    w("%endif")
    # poses
    first = 0
    for name, n, _ in ANIMS:
        w("WA_A_%s equ %d" % (name, first))
        w("WA_N_%s equ %d" % (name, n))
        first += n
    w("WA_NFRAMES equ %d" % first)
    w("WA_FRAMESZ equ %d                ; one frame: NFACE x NJ x 2 bytes"
      % (NFACE * NJ * 2))
    w("%ifdef WA_TAB_POSE")
    w("wa_pose:")
    for name, n, fn in ANIMS:
        for i in range(n):
            pts = fn(i, n)
            for k in range(NFACE):
                pr = project(pts, k)
                w("    db " + ", ".join("%d,%d" % (sb(a), sb(b))
                                         for a, b in pr) +
                  "   ; %s %d facing %d" % (name, i, k))
    w("%endif")
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
