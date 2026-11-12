#!/usr/bin/env python3
"""arenagen - WireArena's host-built tables (docs/plans/MULTIPLAYER-FPS-PLAN.md).

Writes one NASM include, deterministic byte for byte:

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
PLAYER_START = (1024, 256, 256)  # x, y, angle (facing north)

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
    w("WA_START_X equ %d" % PLAYER_START[0])
    w("WA_START_Y equ %d" % PLAYER_START[1])
    w("WA_START_A equ %d" % PLAYER_START[2])
    w("WA_NBOX equ %d" % len(BOXES))
    w("wa_sin:")
    for i in range(0, 1024, 8):
        w("    dw " + ", ".join(str(int(round(16384 * math.sin(
            2 * math.pi * j / 1024)))) for j in range(i, i + 8)))
    w("wa_boxes:                       ; x0, y0, x1, y1")
    for b in BOXES:
        w("    dw %d, %d, %d, %d" % b)
    # paths: per dummy, a count and per leg (x, y, heading, steps)
    w("WA_NFIG equ %d" % len(PATHS))
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
    # poses
    first = 0
    for name, n, _ in ANIMS:
        w("WA_A_%s equ %d" % (name, first))
        w("WA_N_%s equ %d" % (name, n))
        first += n
    w("WA_NFRAMES equ %d" % first)
    w("WA_FRAMESZ equ %d                ; one frame: NFACE x NJ x 2 bytes"
      % (NFACE * NJ * 2))
    w("wa_pose:")
    for name, n, fn in ANIMS:
        for i in range(n):
            pts = fn(i, n)
            for k in range(NFACE):
                pr = project(pts, k)
                w("    db " + ", ".join("%d,%d" % (sb(a), sb(b))
                                         for a, b in pr) +
                  "   ; %s %d facing %d" % (name, i, k))
    with open(out, "w") as f:
        f.write("\n".join(L) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
