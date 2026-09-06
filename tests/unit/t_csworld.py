#!/usr/bin/env python3
"""NOTHING IN PARIS STANDS IN THE SEINE (SPEC.md 88.6.3).

The Eiffel Tower's object sat at the map's origin, and the tower's base is
124 m across: one corner of it was 15.7 m inside the near bank of
`cs_m_rivc0`, and from the air the tower was drawn dipping into the river.
The object moved 60 m back along that bank's normal (§88.6.3) - and the
next person to move either the tower or a river piece has no way of
noticing they have put it back, because the two are declared 200 lines
apart in `csworld.inc` and neither mentions the other.

So this walks the world as the game reads it: the object table and the
models are decoded out of `build/skies.bin`, at the offsets the package's
own equates give, and every collidable building's ground footprint is held
against every river polygon. Host-side, no emulator, one second.

It is deliberately about the WATER and not about buildings overlapping each
other: two blocks sharing a corner is a skyline, and a basilica standing in
a river is a bug.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import dispapps                                             # noqa: E402

MARGIN = 5                              # metres of daylight a base must keep


def equates(src):
    """The `NAME equ N` lines of skies.asm - the layout constants, which are
    equates and so are not in the map dispapps builds."""
    out = {}
    for line in open(src):
        m = re.match(r"^(CS[MOIF]_[A-Z0-9_]+)\s+equ\s+(-?\d+)", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def main():
    img = open(os.path.join(ROOT, "build", "skies.bin"), "rb").read()
    mp = dispapps._map("skies")
    E = equates(os.path.join(ROOT, "apps", "skies", "skies.asm"))
    need = ["CSM_TYPE", "CSM_NV", "CSM_NF", "CSM_RAD", "CSM_VERTS", "CSM_FACES",
            "CSM_FLAT", "CSM_STACK", "CSO_MODEL", "CSO_X", "CSO_Z", "CSO_FLAGS",
            "CSO_SIZE", "CSO_COLLIDE", "CSI_RIVER"]
    miss = [n for n in need if n not in E]
    if miss:
        sys.exit("t_csworld: skies.asm no longer defines %s" % ", ".join(miss))

    def w(off):
        v = int.from_bytes(img[off:off + 2], "little")
        return v - 65536 if v >= 32768 else v

    def model(at):
        return {"type": img[at + E["CSM_TYPE"]], "nv": img[at + E["CSM_NV"]],
                "nf": img[at + E["CSM_NF"]], "rad": w(at + E["CSM_RAD"]),
                "verts": w(at + E["CSM_VERTS"]), "faces": w(at + E["CSM_FACES"])}

    rivers, bases = [], []
    for o in range(mp["cs_objtab"], mp["cs_objend"], E["CSO_SIZE"]):
        md = model(w(o + E["CSO_MODEL"]))
        ox, oz = w(o + E["CSO_X"]), w(o + E["CSO_Z"])
        if md["type"] == E["CSM_FLAT"]:
            f = md["faces"]
            for _ in range(md["nf"]):
                n, ink = img[f], img[f + 1]
                idx = list(img[f + 3:f + 3 + n])
                if ink == E["CSI_RIVER"]:
                    rivers.append([(ox + w(md["verts"] + 4 * i),
                                    oz + w(md["verts"] + 4 * i + 2)) for i in idx])
                f += 3 + n
        elif md["type"] == E["CSM_STACK"] and (w(o + E["CSO_FLAGS"]) & E["CSO_COLLIDE"]):
            wx, wz = w(md["verts"]), w(md["verts"] + 4)      # the first level
            bases.append((o, ox, oz, abs(wx), abs(wz)))

    def seg_dist(p, a, b):
        (px, pz), (ax, az), (bx, bz) = p, a, b
        dx, dz = bx - ax, bz - az
        L2 = dx * dx + dz * dz
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
        return ((px - ax - t * dx) ** 2 + (pz - az - t * dz) ** 2) ** 0.5

    def inside(p, poly):
        sign = None
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            c = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
            if c == 0:
                continue
            if sign is None:
                sign = c > 0
            elif (c > 0) != sign:
                return False
        return True

    def turn(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 0) - (v < 0)

    def crosses(a, b, c, d):
        return (turn(a, b, c) != turn(a, b, d)) and (turn(c, d, a) != turn(c, d, b))

    # CORNERS ARE NOT ENOUGH, and that is not hypothetical: the Louvre is
    # 500 m long and lies ALONG the quay, so the river crossed its footprint
    # with all four of its corners dry. A corner-only version of this file
    # passed it - and would pass a bridge lying across the water - which is
    # docs/WRITING-TESTS.md 1's failure exactly. Overlap is therefore every
    # edge PAIR plus containment either way, and the distance reported when
    # they are apart is vertex-to-edge over both.
    def gap(A, B):
        for i in range(len(A)):
            for j in range(len(B)):
                if crosses(A[i], A[(i + 1) % len(A)], B[j], B[(j + 1) % len(B)]):
                    return -1.0
        if any(inside(p, B) for p in A) or any(inside(p, A) for p in B):
            return -1.0
        d = 1e9
        for P, Q in ((A, B), (B, A)):
            for p in P:
                d = min(d, min(seg_dist(p, Q[i], Q[(i + 1) % len(Q)])
                               for i in range(len(Q))))
        return d

    worst, where, bad = 1e9, None, []
    for o, ox, oz, hx, hz in bases:
        name = img[w(o + 14):].split(b"\0")[0].decode("ascii", "replace")
        foot = [(ox + hx, oz + hz), (ox - hx, oz + hz),
                (ox - hx, oz - hz), (ox + hx, oz - hz)]
        for poly in rivers:
            d = gap(foot, poly)
            if d < worst:
                worst, where = d, name
            if d < MARGIN:
                bad.append("%s (%d,%d, %dx%d m) is %s the Seine"
                           % (name, ox, oz, 2 * hx, 2 * hz,
                              "IN" if d < 0 else "%.1f m from" % d))

    if bad:
        for b in sorted(set(bad)):
            print("  " + b)
        sys.exit("t_csworld: %d building corner(s) in or against the water "
                 "(SPEC.md 88.6.3 wants %d m of daylight)" % (len(set(bad)), MARGIN))
    print("  csworld: %d collidable bases against %d river polygons, nearest "
          "%s at %.1f m (SPEC.md 88.6.3)" % (len(bases), len(rivers), where, worst))


if __name__ == "__main__":
    main()
