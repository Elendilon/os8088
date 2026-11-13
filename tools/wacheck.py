#!/usr/bin/env python3
"""wacheck - WireArena's wall edges against a host reference, pose by pose.

A DEVELOPMENT INSTRUMENT, not a suite row (docs/plans/MULTIPLAYER-FPS-PLAN.md
16.5). It boots the system disk and WARENA under MartyPC, opens 40 columns,
then for each random pose (clear of every box) writes the player's position
and angle straight into the package's BSS, lets half a guest second draw, and
reads text VRAM at B800 - `screen()` drops the box-drawing glyphs, so it would
miss every `─` edge. Per column it compares the topmost and bottommost edge
glyph (`─` 0xC4, `_` 0x5F) with a reference: the nearest front-facing wall a
ray through the column's centre meets, projected with the guest's own scales
(75 degrees - the default - eye 1.6 m, pitch 0). A column with a figure in it is skipped. A
pose is reported when an edge is two rows or more off.

The BSS addresses come from a map of the build it boots, assembled here and
compared byte for byte with build/wirearena.bin - an address from an older
map writes the pose into the wrong bytes, and that once made a fix look like
a regression for an hour.

    make wirearenadisk && python3 tools/wacheck.py [--seed N] [--poses N]

It found the far-wall precision bug: 15 poses in 30 with an edge two rows or
more off before the fix, 5 in 30 after (single columns at a near corner).
"""
import argparse, math, os, random, struct, subprocess, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import arenagen as A                      # noqa: E402
import os88ui                             # noqa: E402
from os88pkg import PKG_FMT              # noqa: E402

W = 40
FOVF = 334                  # 75 degrees, the default (wa_fovf): the guest's
K16 = (8 * W * FOVF) >> 8   # own integer arithmetic, from wa_setfov
KYQ = (133 * FOVF) >> 8
HQ = 96
NUMT = (192 - 102) * KYQ
NUMB = 102 * KYQ
SIN = [int(round(16384 * math.sin(2 * math.pi * j / 1024))) for j in range(1024)]
VARS = dict(px="wa_px", py="wa_py", ang="wa_ang", pitch="wa_pitch",
            jz="wa_jz", jv="wa_jv", eye="wa_eye")
GLYPH = {0xC4: '-', 0x5F: '_', 0xB3: '|', 0x2F: '/', 0x5C: '\\'}
FIGURE = (0xDB, 0xDF, 0xDC, 0xDD, 0xDE)


def offsets():
    d = tempfile.mkdtemp(prefix="wacheck")
    mp, bn = os.path.join(d, "wa.map"), os.path.join(d, "wa.bin")
    subprocess.check_call(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                           "-I", "apps/wirearena/", "-I", "build/", "--before",
                           "[map all %s]" % mp, "-o", bn,
                           "apps/wirearena/wirearena.asm"], cwd=ROOT)
    if open(bn, "rb").read() != open(os.path.join(ROOT, "build/wirearena.bin"), "rb").read():
        raise SystemExit("wacheck: build/wirearena.bin is not this source - "
                         "make wirearenadisk first")
    out = {}
    for line in open(mp):
        f = line.split()
        if len(f) == 3 and f[2] in VARS.values():
            out[[k for k, v in VARS.items() if v == f[2]][0]] = int(f[0], 16)
    if len(out) != len(VARS):
        raise SystemExit("wacheck: the map lacks %r" % (set(VARS) - set(out)))
    return out


def walls():
    x0, y0, x1, y1 = A.ROOM
    out = [((x0, y0), (x0, y1)), ((x0, y1), (x1, y1)),
           ((x1, y1), (x1, y0)), ((x1, y0), (x0, y0))]
    for (a, b, c, d) in A.BOXES:
        out += [((a, b), (c, b)), ((c, b), (c, d)), ((c, d), (a, d)),
                ((a, d), (a, b))]
    return out


def expect(px, py, a, ws):
    s, c = SIN[a & 1023], SIN[(a + 256) & 1023]

    def cam(p):
        dx, dy = p[0] - px, p[1] - py
        return (dx * s - dy * c) / 16384.0, (dx * c + dy * s) / 16384.0
    res = []
    for col in range(W):
        r = (16 * col + 8 - 8 * W) / K16
        best = None
        for (p, q) in ws:
            if (px - p[0]) * (q[1] - p[1]) - (py - p[1]) * (q[0] - p[0]) <= 0:
                continue                      # seen from behind
            (x1, z1), (x2, z2) = cam(p), cam(q)
            den = (x2 - x1) - r * (z2 - z1)
            if abs(den) < 1e-9:
                continue
            t = (r * z1 - x1) / den
            if not 0 <= t <= 1:
                continue
            z = z1 + t * (z2 - z1)
            if z > 0.5 and (best is None or z < best):
                best = z
        if best is None:
            res.append(None)
            continue
        t, b = HQ - NUMT / best, HQ + NUMB / best
        res.append((math.floor((t * 8 + 16) / 32), math.floor((b * 8 + 16) / 32), best))
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--poses", type=int, default=30)
    ap.add_argument("--machine", default="os8088_5150_cga")
    a = ap.parse_args()
    off = offsets()
    ws = walls()
    random.seed(a.seed)
    F = 4772727
    bad = 0
    with os88ui.boot(os.path.join(ROOT, "build/os8088-360.img"),
                     apps=os.path.join(ROOT, "build/warena360.img"),
                     machine=a.machine) as ui:
        m = ui.m
        ui.path("B:/WARENA.O88")
        m.advance(cycles=F // 2)
        m.go()
        ui.menu_pick("Game", "Play, 40 columns")
        m.advance(cycles=F * 2)
        buf = m.read(0x10000, 0x90000)
        base = None
        for o in range(0, len(buf) - 32, 16):
            if buf[o:o + 2] == b'O8' and buf[o + 2] == PKG_FMT and \
                    buf[o + 16:o + 22] == b'WARENA':
                base = 0x10000 + o
        if base is None:
            raise SystemExit("wacheck: WARENA is not in memory")
        for n in range(a.poses):
            while True:
                px, py = random.randint(60, 1988), random.randint(60, 1988)
                if not A.inside(px, py, A.BOXES, 40):
                    break
            ang = random.randint(0, 1023)
            m.pause()
            for k, v in (('px', px), ('py', py), ('ang', (ang << 6) & 0xFFFF),
                         ('pitch', 0), ('jz', 0), ('jv', 0), ('eye', 102)):
                m.write(base + off[k], struct.pack('<H', v))
            m.advance(cycles=F // 2)
            vr = m.read(0xB8000, W * 25 * 2)
            exp = expect(px, py, ang, ws)
            worst = []
            for c in range(W):
                if exp[c] is None:
                    continue
                cells = [vr[(r * W + c) * 2] for r in range(24)]
                if any(ch in FIGURE for ch in cells):
                    continue
                edge = [r for r in range(24) if cells[r] in (0xC4, 0x5F)]
                if not edge:
                    continue
                ht, hb, z = exp[c]
                d = max(abs(edge[0] - (ht >> 1)) if 0 <= ht < 48 else 0,
                        abs(edge[-1] - (hb >> 1)) if 0 <= hb < 48 else 0)
                if d >= 2:
                    worst.append((c, ht >> 1, edge[0], hb >> 1, edge[-1], round(z)))
            if worst:
                bad += 1
                print("pose %d: px=%d py=%d a=%d  %d column(s) off, e.g. "
                      "(col, want top, got, want bottom, got, depth) %s"
                      % (n, px, py, ang, len(worst), worst[:4]))
    print("wacheck: %d poses, %d with an edge two rows or more off"
          % (a.poses, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
