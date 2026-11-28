#!/usr/bin/env python3
"""COURSE 7, CLOCKWORK KEEP: the MEASURED numbers of ../KEEP.md section 3, on the tool's model
(tools/bbcourse.py's Physics and its camera; never an emulator).  Host-only; nothing in `make` runs it.

    python3 measure.py [COURSE.bbc] [--only SECTION,...]
        sections: start bridge gate stair spikes key cogs secret held soft phases view exits
    python3 measure.py [COURSE.bbc] --vault DIR
        DIR/BZDKEEP-VAULT.BIN: the run to the TREASURY (exit 1) as a demo log, for `bbcourse.py --guide --log`

Every place it names is read off the compiled course (the bridges, the plate, the gates, the see-saw, the
popspikes, the keys, the tables, the flags), so it follows the sketch.  RUBBER throughout.  "The pair" is two
arrows held together, which move the ball along a tile axis; "a phase" is the step of the 256-step cycle every
timer of the course reads (a play starts at 0).  A ball is put down with the channels a player would have open
there, as the engine keeps them (SPEC.md 137.41.1 D3).  The whole of it takes about ten minutes on four cores;
`held`, `soft` and `phases` are the long ones.
"""
import collections
import multiprocessing
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import bbcourse as B                                    # noqa: E402

K_L, K_R, K_U, K_D, K_HOP = B.K_L, B.K_R, B.K_U, B.K_D, B.K_HOP
PX, MX, PY, MY = K_R | K_D, K_L | K_U, K_L | K_D, K_R | K_U        # the pairs: +x, -x, +y, -y
NAMES = {0: "none", K_L: "L", K_R: "R", K_U: "U", K_D: "D", PX: "+x", MX: "-x", PY: "+y", MY: "-y"}
ALL8 = [K_L, K_R, K_U, K_D, PX, MX, PY, MY]
SEC = float(B.SEC_STEPS)
CH = {n: 1 << i for i, n in enumerate(B.GT_CHANNELS)}  # ring, plus, box, cross: a channel's bit


def ball(c, wx, wy, vx=0, vy=0, ch=0, n=0, gx=None, gy=None):
    """a rubber ball at rest on a tile's centre at phase n, the channels `ch` open (their gates' art at its
    last frame: the ball has waited it out)"""
    p = B.Physics(c, play=True)
    sb = p.fsl[p._fk[B.GT_KP]]
    sb[0] = ch
    for i in range(len(B.GT_CHANNELS)):
        if ch >> i & 1:
            sb[2 + i] = B.GT_AFR - 1
    p.nstep = n
    p._fhook(B.H_RESET, 1)                              # (a timed plate at its pose on this step)
    p.poke(wx, wy, vx, vy)
    if gx is not None:
        p.gx = int(gx * 4096)
    if gy is not None:
        p.gy = int(gy * 4096)
    return p


def chans(p):
    return p.fsl[p._fk[B.GT_KP]][0]


def cell(p):
    return (p.gx >> 12, p.gy >> 12)


def run(p, keys, n, stop=None):
    """n steps of `keys` (a key byte, or f(p, i)) -> ('FELL' | 'GOAL' | 'stop' | 'end', the step)"""
    nf = p.nfall
    for i in range(n):
        p.step(keys(p, i) if callable(keys) else keys)
        if p.nfall != nf:
            return "FELL", i
        if p.goal:
            return "GOAL", i
        if stop and stop(p):
            return "stop", i
    return "end", n


def spans(ds, per):
    """the phases in `ds` (of 0 .. per - 1, cyclic) as runs 'a - b'"""
    s = sorted(ds)
    if not s:
        return "none"
    step = min(b - a for a, b in zip(s, s[1:])) if len(s) > 1 else 1
    out, a, prev = [], s[0], s[0]
    for d in s[1:] + [None]:
        if d is None or d != prev + step:
            out.append((a, prev))
            a = d
        prev = d
    if len(out) > 1 and out[0][0] == 0 and out[-1][1] + step >= per:
        out = [(out[-1][0], out[0][1])] + out[1:-1]
    return ", ".join("%d - %d" % ab for ab in out)


class Course:
    """the places the measurements name, read off the compiled course"""

    def __init__(self, path):
        self.path = path
        self.c = c = B.compile_course(open(path).read(), fname=path, occluders=False)
        self.rm = rm = B.rec_map(c.tiles)
        self.start = tuple(c.src.start[0])
        pr = c.props
        self.flags = [tuple(q["at"]) for q in pr if q["kind"] == B.PK_CHECKPOINT]
        self.stand = sorted({k[:2] for k, t in rm.items() if t.kind in (B.KIND_FLOOR, B.KIND_GOAL)}
                            - {tuple(q["at"]) for q in pr if q["kind"] == B.PK_CLOCK})
        self.goals = {k[:2]: t.exit for k, t in rm.items() if t.kind == B.KIND_GOAL}
        tb = collections.defaultdict(list)
        for q in pr:
            if q["kind"] == B.GT_KB and q["gch"] == B.GT_TIMED:
                tb[(q["on"], q["smask"])].append(q)
        tbs = sorted(tb.values(), key=lambda qs: -len(qs))
        self.draw, self.traitor = tbs[0], tbs[1]        # the drawbridge (8 cells), the traitor's bridge (3)
        self.plate = [tuple(q["at"]) for q in pr if q["kind"] == B.GT_KP][0]
        self.keys = {B.GT_CHANNELS[q["gch"]]: tuple(q["at"]) for q in pr if q["kind"] == B.GT_KK}
        self.gates = collections.defaultdict(list)
        for q in pr:
            if q["kind"] == B.GT_KG:
                self.gates[B.GT_CHANNELS[q["gch"]]].append(tuple(q["at"]))
        self.saw = [q for q in pr if q["kind"] == B.FK_TILT][0]
        self.sawc = [(self.saw["at"][0] + i, self.saw["at"][1]) for i in range(self.saw["tlnx"])]
        sp = collections.defaultdict(list)
        for q in pr:
            if q["kind"] == B.SP_KP:
                sp[q["sseed"] & ~1].append(q)
        self.rows = [sp[k] for k in sorted(sp)]          # the north row (seed 0), the west row
        self.cogs = sorted({tuple(q["ttab"]["at"]) for q in pr if q["kind"] == B.TT_K and "ttab" in q})
        self.timed = ({tuple(q["at"]) for q in pr if q["kind"] in (B.GT_KB, B.SP_KP, B.TT_K)} | set(self.sawc))


def m_start(L):
    c = L.c
    print("THE START %s: each arrow and pair held 12 s from a play's first step" % (L.start,))
    for k in ALL8:
        p = ball(c, *L.start)
        r, i = run(p, k, 660, stop=lambda p: cell(p)[1] < L.plate[1] + 2 and not p.air)
        print("   %-2s: %s" % (NAMES[k], "FELL at %.1f s from %s" % (i / SEC, cell(p)) if r == "FELL" else
                               "in the gatehouse in %.1f s" % (i / SEC) if r == "stop" else "at rest on %s" % (cell(p),)))
    ok = []
    for d in range(0, 256, 2):
        p = ball(c, *L.start)
        r, i = run(p, lambda p, i: MY if i >= d else 0, d + 400, stop=lambda p: cell(p)[1] < L.plate[1] + 2 and not p.air)
        if r == "stop":
            ok.append(d)
    dn = [n for n in range(256) if all(B.gt_down(q, n, 0) for q in L.draw)]
    print("   the drawbridge is whole for steps %d - %d of 256 (%.1f s of %.1f); the pair toward it, first pressed on "
          "step d of the play: across for d in %s (%d of 256)" % (dn[0], dn[-1], len(dn) / SEC, 256 / SEC,
                                                                  spans(ok, 256), 2 * len(ok)))


def m_bridge(L):
    c = L.c
    y0 = max(q["at"][1] for q in L.draw) + 1
    ok = collections.defaultdict(list)
    for x in sorted({q["at"][0] for q in L.draw}):
        for d in range(0, 256, 2):
            p = ball(c, x, y0, n=d)
            r, i = run(p, MY, 300, stop=lambda p: cell(p)[1] < L.plate[1] + 2 and not p.air)
            if r == "stop":
                ok[x].append((d, i))
    for x, v in sorted(ok.items()):
        print("THE DRAWBRIDGE from rest on its edge (%d, %d), the pair held from phase d: across for d in %s (%d of 256), "
              "in %.1f s" % (x, y0, spans([d for d, _i in v], 256), 2 * len(v), v[0][1] / SEC))


def m_gate(L):
    c = L.c
    gx, gy = L.plate
    bars = sorted(L.gates["plus"])
    for x in sorted({b[0] for b in bars}):
        p = ball(c, x, gy + 1)
        r, i = run(p, MY, 400, stop=lambda p: cell(p)[1] < bars[0][1] and not p.air)
        if r == "stop":
            print("THE GATEHOUSE, lane x %d (the plate's): the pair toward the bars held from rest: over the plate, "
                  "through the portcullis in %.1f s" % (x, i / SEC))
            continue
        at = cell(p)
        q = ball(c, *at)
        r2, i2 = run(q, MX if gx < x else PX, 200, stop=lambda q: chans(q) & CH["plus"])
        r3, i3 = run(q, MY, 300, stop=lambda q: cell(q)[1] < bars[0][1] and not q.air)
        print("THE GATEHOUSE, lane x %d (the other): the pair held from rest: %s on %s, the bars shut, the plate the tile "
              "beside it; the pair toward the plate presses it in %.1f s and the pair at the bars is through %.1f s "
              "after that" % (x, "at rest" if r == "end" else r, at, i2 / SEC, i3 / SEC))


def m_stair(L):
    c = L.c
    S = L.saw
    y = S["at"][1]
    per = S["tlmask"] + 1
    print("THE ROCKING STAIR %s - %s, period %d steps (%.1f s), level for %d of each %d: from rest on the courtyard "
          "tile beside each of its cells, the pair at the battlement held from phase d" % (
              L.sawc[0], L.sawc[-1], per, per / SEC, S["tlflat"], per // 2))
    for (x, _y) in L.sawc:
        ts = []
        for d in range(0, per, 4):
            p = ball(c, x, y + 1, n=d)
            r, i = run(p, MY, 500, stop=lambda p: cell(p)[1] < y and not p.air)
            ts.append(i if r == "stop" else None)
        got = [t for t in ts if t is not None]
        print("   beside (%d, %d): on the battlement on %d of %d phases%s" % (
            x, y, len(got), len(ts), ", in %.1f - %.1f s" % (min(got) / SEC, max(got) / SEC) if got else ""))
    n = fell = left = 0
    for (x, _y) in L.sawc:                               # nothing on it kills: every key from rest ON each cell, until
        for d in range(0, per, 16):                     # the ball is off the plate (or 6 s)
            for k in ALL8 + [0]:
                p = ball(c, x, y, n=d)
                r, _i = run(p, k, 330, stop=lambda p: not p.air and cell(p) not in L.sawc)
                n += 1
                fell += r == "FELL"
                left += r == "stop"
    print("   at rest ON each of its cells, each of 9 keys held from 8 phases until the ball is off the plate or 6 s are "
          "up: %d runs, off it onto a floor on %d, still on it on %d, falls %d" % (n, left, n - left - fell, fell))


def m_spikes(L):
    c = L.c
    for name, row in zip(("north", "west"), L.rows):
        cells = sorted(tuple(q["at"]) for q in row)
        alongx = cells[0][0] == cells[1][0]             # the row lies across a walk that runs along x
        per = row[0]["smask"] + 1
        dn = [n for n in range(per) if not any(B.sp_up(q, n) for q in row)]
        print("THE %s SPIKES %s, period %d, all down for steps %s (%.1f s of %.1f)" % (
            name.upper(), cells, per, spans(dn, per), len(dn) / SEC, per / SEC))
        for (sx, sy) in cells:
            for side, key in ((1, MX if alongx else MY), (-1, PX if alongx else PY)):
                a = (sx + side, sy) if alongx else (sx, sy + side)
                if a not in L.stand:
                    continue
                okw, okh = [], []
                for d in range(0, per, 2):
                    p = ball(c, *a, n=d)
                    r, _i = run(p, key, 120, stop=lambda p: not p.air and cell(p) != a and cell(p) not in cells)
                    if r == "stop":
                        okw.append(d)
                    for t in (0, 4, 8, 12, 16, 20):
                        p = ball(c, *a, n=d)
                        r, _i = run(p, lambda p, i: key | (K_HOP if i == t else 0), 160,
                                    stop=lambda p: not p.air and cell(p) != a and cell(p) not in cells)
                        if r == "stop":
                            okh.append(d)
                            break
                print("   from rest on %s toward %s: rolled across from %d of %d phases (%s); with a Hop in the first "
                      "0.4 s, from %d" % (a, (sx, sy), 2 * len(okw), per, spans(okw, per), 2 * len(okh)))


def m_key(L):
    c = L.c
    kx, ky = L.keys["ring"]
    door = L.gates["ring"][0]
    print("THE KEY %s AND THE DOOR %s (C11): the roll east off the battlement, the hay under it" % ((kx, ky), door))
    p = ball(c, door[0] - 6, ky)
    r, _i = run(p, PX, 400)
    print("   without the key: the pair east across the courtyard ends %s on %s" % ("at rest" if r == "end" else r, cell(p)))
    n = thru = fell = 0
    worst, ends = 0, collections.Counter()
    for vy in (-80, -40, 0, 40, 80):                    # (still drifting along the walk at this speed)
        for gy in (ky + .15, ky + .3, ky + .5, ky + .7, ky + .85):
            for t in (0, 6, 12):                        # the pair pressed this many steps after the ball is on the tile
                p = ball(c, kx, ky, vy=vy, gy=gy)
                air = [0]

                def keys(p, i, t=t):
                    air[0] += bool(p.air)
                    return PX if i >= t else 0
                r, i = run(p, keys, 500, stop=lambda p: cell(p)[0] > door[0] and not p.air)
                n += 1
                thru += r == "stop"
                fell += r == "FELL"
                worst = max(worst, air[0])
                if r != "stop":
                    ends[cell(p)] += 1
    print("   from the key's tile, 5 places across it, drifting along the walk at 0, 40 or 80 either way, the pair east "
          "pressed 0 - 0.2 s late and held: %d runs, through the door on %d, falls %d; the longest in the air %d steps "
          "(%.2f s); the others end at rest against the east curtain on %s" % (
              n, thru, fell, worst, worst / SEC, dict(ends) or "-"))
    n = thru = 0
    for vx in (120, 240, 384):                          # ...and a ball already rolling east when it takes the key
        for gy in (ky + .15, ky + .3, ky + .5, ky + .7, ky + .85):
            p = ball(c, kx, ky, vx=vx, gy=gy)
            r, _i = run(p, PX, 500, stop=lambda p: cell(p)[0] > door[0] and not p.air)
            n += 1
            thru += r == "stop"
    print("   rolling east over the key at 120, 240 and the cap, 5 places across: through the door on %d of %d" % (thru, n))
    p = ball(c, kx, ky)
    r, i = run(p, PX, 500, stop=lambda p: cell(p)[0] > door[0] and not p.air)
    print("   from rest on the key, the pair east held: through the door in %.1f s" % (i / SEC))


def m_cogs(L):
    c = L.c
    (ax, ay), (bx, by) = L.cogs
    isl = ax + 2
    print("THE COGS at %s and %s (a quarter turn every 64 steps, 1.17 s), the island x %d between" % ((ax, ay), (bx, by), isl))
    for name, sx, done in (("the hall's edge", ax - 1, lambda p: cell(p)[0] == isl and not p.air),
                           ("the island", isl, lambda p: cell(p)[0] >= bx + 2 and not p.air)):
        for y in (ay, ay + 1):
            ok, ts = [], []
            for d in range(0, 256, 2):
                p = ball(c, sx, y, ch=CH["ring"], n=d)
                r, i = run(p, PX, 200, stop=done)
                if r == "stop":
                    ok.append(d)
                    ts.append(i)
            print("   from rest on %s (%d, %d), the pair east held from phase d: across for d in %s (%d of 256)%s" % (
                name, sx, y, spans(ok, 256), 2 * len(ok), ", in %.1f s" % (statistics.median(ts) / SEC) if ts else ""))
    n = safe = 0
    for d in range(0, 256, 4):                           # the island is a rest: nothing takes a still ball off it
        for y in (ay, ay + 1):
            p = ball(c, isl, y, ch=CH["ring"], n=d)
            r, _i = run(p, 0, 300)
            n += 1
            safe += r == "end"
    print("   a ball at rest on the island for 5.5 s from each of 64 phases, both tiles: still there on %d of %d" % (safe, n))
    ok = []
    for d in range(0, 256, 4):                           # the brave line: a Hop from the island over the second cog
        for t in range(0, 40, 4):
            for again in (0, 2, 8):
                p = ball(c, isl, ay, ch=CH["ring"], n=d)
                hops = {t} | ({t + again} if again else set())
                r, _i = run(p, lambda p, i: PX | (K_HOP if i in hops else 0), 200,
                            stop=lambda p: cell(p)[0] >= bx + 2 and not p.air)
                if r == "stop":
                    ok.append(d)
                    break
            else:
                continue
            break
    print("   the island to the dais with ONE Hop (or the Hop and its \"and again\") in the first 0.7 s: from %d of 64 "
          "phases" % len(ok))


def m_secret(L):
    c = L.c
    cells = sorted(tuple(q["at"]) for q in L.traitor)
    y = cells[0][1]
    near, far = (cells[-1][0] + 1, y), (cells[0][0] - 1, y)
    dn = [n for n in range(256) if all(B.gt_down(q, n, 0) for q in L.traitor)]
    print("THE TRAITOR'S BRIDGE %s - %s, whole for steps %s (%.1f s of %.1f)" % (cells[0], cells[-1], spans(dn, 256),
                                                                            len(dn) / SEC, 256 / SEC))
    for name, a, key, done in (("out, from rest on flag %s" % (near,), near, MX, lambda p: cell(p)[0] < cells[0][0]),
                               ("back, from rest on flag %s" % (far,), far, PX, lambda p: cell(p)[0] > cells[-1][0])):
        ok, ts = [], []
        for d in range(0, 256, 2):
            p = ball(c, *a, n=d)
            r, i = run(p, key, 200, stop=lambda p: done(p) and not p.air)
            if r == "stop":
                ok.append(d)
                ts.append(i)
        early = sum(1 for d in ok if d not in dn)
        print("   %s, the pair held from phase d: across for d in %s (%d of 256: %.2f s of grace, %d of them before it "
              "has laid down), in %.1f s" % (name, spans(ok, 256), 2 * len(ok), 2 * len(ok) / SEC, 2 * early,
                                           statistics.median(ts) / SEC))
    gate = L.gates["cross"][0]
    for ch, what in ((CH["ring"], "without the cross key"), (CH["ring"] | CH["cross"], "with it")):
        p = ball(c, gate[0], gate[1] + 2, ch=ch)
        r, i = run(p, MY, 300)
        print("   the treasury's gate %s, the pair at it from two tiles off: %s" % (
            what, "in the treasury's goal (exit %d) in %.1f s" % (p.exit, i / SEC) if r == "GOAL" else
            "%s on %s" % ("at rest" if r == "end" else r, cell(p))))


def _held(a):
    path, k, phases, masks = a
    L = _held.L if getattr(_held, "L", None) is not None and _held.L.path == path else Course(path)
    _held.L = L
    out = []
    for key in ALL8:
        for ch in masks:
            for d in phases:
                p = ball(L.c, *k, ch=ch, n=d)
                last = [k]

                def keys(p, i, key=key):
                    if not p.air:
                        last[0] = cell(p)
                    return key
                r, _i = run(p, keys, 440)
                out.append((key, r, last[0], cell(p)))
    return k, out


def m_held(L):
    phases, masks = (0, 64, 128, 192), (0, CH["plus"] | CH["ring"], 15)
    cells = [k for k in L.stand if k not in L.goals and k not in L.gates["ring"] + L.gates["plus"] + L.gates["cross"]]
    with multiprocessing.Pool() as pool:
        res = pool.map(_held, [(L.path, k, phases, masks) for k in cells], chunksize=4)
    off, stuck, n = collections.Counter(), [], 0
    for k, out in res:
        n += len(out)
        if all(r == "end" and at == k for _key, r, _last, at in out):
            stuck.append(k)
        for _key, r, last, _at in out:
            if r == "FELL":
                off[last] += 1
    meant = L.timed | {(x + i, y + j) for (x, y) in L.cogs for i in (-1, 2) for j in (0, 1)}
    meant |= {(q["at"][0], q["at"][1] + s) for q in L.draw for s in (-1, 1)}
    meant |= {(q["at"][0] + s, q["at"][1]) for q in L.traitor for s in (-1, 1)}
    print("EVERY ARROW FROM REST ON EVERY TILE: %d tiles, each of 8 keys held 8 s from 4 phases with no channel, the "
          "plus and the ring, and all four open (%d runs): tiles no key leaves %s" % (len(cells), n, stuck))
    print("   a fall's last tile on the ground is a timed bridge's, a spike's, a cog's or the island's, or the tile "
          "before one, in %d of %d falls; any other: %s" % (
              sum(v for k, v in off.items() if k in meant), sum(off.values()),
              sorted((k, v) for k, v in off.items() if k not in meant) or "none"))


def _soft(a):
    path, st = a
    L = _soft.L if getattr(_soft, "L", None) is not None and _soft.L.path == path else Course(path)
    _soft.L = L
    k, ch = st
    out = set()
    for key in ALL8:
        for T in (30, 70, 140, 300):
            for d in (0, 64, 128, 192):
                p = ball(L.c, *k, ch=ch, n=d)
                r, _i = run(p, key, T)
                if r == "end":                           # let go: where does it come to rest?
                    last, still = None, 0
                    for _ in range(400):
                        nf = p.nfall
                        p.step(0)
                        if p.goal:
                            r = "GOAL"
                            break
                        if p.nfall != nf:
                            r = "FELL"
                            break
                        s = (p.gx >> 8, p.gy >> 8, p.air)
                        still = still + 1 if s == last else 0
                        last = s
                        if still > 12 and not p.air:
                            break
                out.add(("GOAL", p.exit) if r == "GOAL" else "FALL" if r == "FELL" else (cell(p), chans(p)))
    return st, out


def m_soft(L):
    """NO SOFTLOCK with the channels REMEMBERED: the states a player can be in are (tile, channels open)"""
    succ, todo = {}, [(L.start, 0)]
    with multiprocessing.Pool() as pool:
        while todo:
            new = []
            for st, out in pool.map(_soft, [(L.path, st) for st in todo], chunksize=2):
                succ[st] = out
                new.extend(o for o in out if isinstance(o[0], tuple) and o not in succ and o not in new)
            todo = [s for s in new if s not in succ and s[0] in L.stand]

    def closure(ok0):
        ok, more = set(), True
        while more:
            more = False
            for st, out in succ.items():
                if st not in ok and any(o in ok0 or o in ok for o in out):
                    ok.add(st)
                    more = True
        return ok
    g0, g1 = closure({("GOAL", 0)}), closure({("GOAL", 1)})
    anyg = closure({("GOAL", 0), ("GOAL", 1)})
    anyhow = closure({("GOAL", 0), ("GOAL", 1), "FALL"})
    masks = collections.Counter(ch for _k, ch in succ)
    print("NO SOFTLOCK, THE CHANNELS REMEMBERED: from the start with none open, moves of one arrow or pair held 0.5 - "
          "5.5 s from 4 phases and let go: %d states (tile, channels) reached; by channels %s" % (
              len(succ), ", ".join("%s: %d" % ("+".join(n for n in B.GT_CHANNELS if CH[n] & m) or "none", v)
                                   for m, v in sorted(masks.items()))))
    print("   a finish with NO fall from %d of them (the throne, exit 0, from %d; the treasury, exit 1, from %d); a "
          "finish or a fall from %d" % (len(anyg), len(g0), len(g1), len(anyhow)))
    print("   no finish without a fall from: %s; none at all from: %s" % (
        sorted(set(succ) - anyg) or "none", sorted(set(succ) - anyhow) or "none"))
    print("   the start reaches the throne: %s; the treasury: %s" % ((L.start, 0) in g0, (L.start, 0) in g1))


def _phase(a):
    path, d = a
    c = B.compile_course(open(path).read(), fname=path, occluders=False)
    p0 = B.Physics(c, play=True)
    p0.tsec = 0
    p0.nstep = d
    p0._fhook(B.H_RESET, 1)
    p0.fref = 1
    spent, tt = [0], B._plan_tt(c)
    stack = [([], B._plan_tries(p0, spent, False, True, None, tt))]
    while stack and spent[0] <= B.PLAN_BUDGET:
        keys, it = stack[-1]
        nxt = next(it, None)
        if nxt is None:
            stack.pop()
            continue
        k2, q = nxt
        if q.goal:
            return d, len(keys + k2), q.nhop, q.nfall
        stack.append((keys + k2, B._plan_tries(q, spent, False, True, None, tt)))
    return d, None, None, None


def m_phases(L):
    with multiprocessing.Pool() as pool:
        res = pool.map(_phase, [(L.path, d) for d in range(0, 256, 8)])
    ts = [n for _d, n, _h, _f in res if n]
    print("THE ROUTE FROM EVERY PHASE: the tool's own search (SPEC.md 137.14.7.4.6: it stands at each timer) from a "
          "play begun on step d of the timers' cycle, d 0, 8 .. 248: a route on %d of %d; %.1f - %.1f s, median %.1f, "
          "mean %.1f; Hops %d, falls %d; 35 s or more on %d" % (
              len(ts), len(res), min(ts) / SEC, max(ts) / SEC, statistics.median(ts) / SEC, statistics.mean(ts) / SEC,
              sum(h or 0 for _d, _n, h, _f in res), sum(f or 0 for _d, _n, _h, f in res),
              sum(1 for n in ts if n >= 35 * SEC)))


def m_view(L):
    """the SIGNATURE: while the ball is in the courtyard before the stair, are the door, the key and the stair's
    cells in the window?  On the route as the tool's search drives it, both cards"""
    c = L.c
    plan = B.route_plan(c)
    if plan is None:
        print("THE COURTYARD'S SCREEN: no route")
        return
    kx, ky = L.keys["ring"]
    door = L.gates["ring"][0]
    pts = {"the key": [(kx, ky)], "the door": [door], "the stair": L.sawc}
    yard = lambda p: cell(p)[1] > L.sawc[0][1] and cell(p)[1] < L.plate[1] - 1 and L.sawc[0][0] - 5 <= cell(p)[0] <= door[0] - 1
    for herc in (0, 1):
        W, _H, rl, _lsh = B.CARDS[herc]
        it = iter(plan)
        p = B.Physics(c, play=True)
        r = B.CamRun(c, herc, p)
        seen, n, first = collections.Counter(), 0, True

        def st():
            k = next(it, None)
            if k is None or p.goal:
                return False
            p.step(k)
        while r.frame(st) and first:
            f = r.rows[-1]
            if cell(p)[1] <= L.sawc[0][1]:
                first = False                           # on the stair: the yard's first visit is over
            elif yard(p):
                n += 1
                xa, ya = 8 * f["c0"], f["R0"] * rl
                got = 0
                for name, cs in pts.items():
                    xs = [B.way_xy(c.tiles[t], t[0], t[1], c.x0, c.y0) for t in cs]
                    if all(xa <= x < xa + 8 * W - 8 and ya <= y < ya + B.WIN_LINES - 8 for x, y in xs):
                        seen[name] += 1
                        got += 1
                seen["all"] += got == len(pts)
                if got == len(pts) and "first" not in seen:
                    seen["first"] = n
        print("THE COURTYARD'S SCREEN on the %s: of the %d frames from the gate to the stair's foot, in the window "
              "whole: %s; ALL THREE AT ONCE on %d, from frame %s" % (
                  "Hercules" if herc else "CGA", n, ", ".join("%s on %d" % (k, seen[k]) for k in pts), seen["all"],
                  seen.get("first", "-")))


def m_exits(L):
    c = L.c
    for name, br in (("the throne", None), ("the treasury", "VAULT")):
        r = B.autopilot_run(c, br)
        p = B.Physics(c, play=True)
        p.tsec = 0
        for k in r["keys"]:
            p.step(k)
        print("THE RUN TO %s (%s): %s, %d steps (%.1f s), exit %s, %d falls, %d Hops, %d of %d flags, the channels "
              "open at the end: %s" % (name.upper(), "the route" if br is None else "the branch " + br,
                                       "at the goal" if p.goal else "NOT at a goal (%s)" % r["reason"], len(r["keys"]),
                                       len(r["keys"]) / SEC, p.exit if p.goal else "-", p.nfall, p.nhop, p.nckpt,
                                       len(L.flags), "+".join(n for n in B.GT_CHANNELS if CH[n] & chans(p)) or "none"))


SECTIONS = collections.OrderedDict((("start", m_start), ("bridge", m_bridge), ("gate", m_gate), ("stair", m_stair),
                                    ("spikes", m_spikes), ("key", m_key), ("cogs", m_cogs), ("secret", m_secret),
                                    ("held", m_held), ("soft", m_soft), ("phases", m_phases), ("view", m_view),
                                    ("exits", m_exits)))


def vault(path, out):
    """the branch VAULT's run (the tool's own search over its way points) as a demo log: a two-exit course's second
    run for `--guide`, which reads the route demo and each log it is given.  Refused unless it ends at exit 1"""
    c = B.compile_course(path)                          # (the FULL compile: the log carries the course's identity)
    r = B.autopilot_run(c, "VAULT")
    p = B.Physics(c, play=True)
    p.tsec = 0
    for k in r["keys"]:
        p.step(k)
    if not p.goal or p.exit != 1:
        sys.exit("measure.py: the branch VAULT does not end at exit 1 (%s, exit %s)" % (
            r["reason"] or "a goal", p.exit if p.goal else "-"))
    fn = os.path.join(out, "BZD%s-VAULT.BIN" % c.name)
    with open(fn, "wb") as f:
        f.write(bytes(B.encode_log(r["keys"], 0, c.ball, True, c.ident)))
    print("%s: %d steps (%.1f s), exit %d, %d falls, %d Hops, %d flags" % (fn, len(r["keys"]), len(r["keys"]) / SEC,
                                                                        p.exit, p.nfall, p.nhop, p.nckpt))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only = None
    for i, a in enumerate(sys.argv):
        if a == "--only":
            only = sys.argv[i + 1].split(",")
            args = [x for x in args if x != sys.argv[i + 1]]
        elif a == "--vault":
            args = [x for x in args if x != sys.argv[i + 1]]
            return vault(args[0] if args else os.path.join(ROOT, "apps", "bonanza", "courses", "keep.bbc"),
                         sys.argv[i + 1])
    path = args[0] if args else os.path.join(ROOT, "apps", "bonanza", "courses", "keep.bbc")
    L = Course(path)
    for name, fn in SECTIONS.items():
        if only is None or name in only:
            fn(L)
            sys.stdout.flush()


if __name__ == "__main__":
    main()
