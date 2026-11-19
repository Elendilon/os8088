#!/usr/bin/env python3
"""BONANZA's FIELD CELLS in the guest (SPEC.md 130.28, wave C3): the package's
own routines under unicorn against tools/bbcourse.py's model, on courses with
chutes and pits - the host half of bonanzaphys's field leg.  It is
tests/bonanza_dsplit.py's method, and borrows its harness (Guest, start, poke,
run): after EVERY step the guest's state is read out of its own bss and
compared EXACTLY with the model's.

    make bonanza && python3 tests/bonanza_dfield.py [--runs N] [--seed S] [--reds]

  1  CELLS: bz_cexp on each field course's STORED form equals its RAM form
     (bz_cxcel's V of a FIELD cell, bz_cxsafe's FIELD edge neighbour).
  2  HOSTILE: on MANY (17 tables), a FIELD cell whose shape is 31 and one whose
     +1's bit 7 (the shape's fifth bit, SPEC.md 130.28.2) takes it past
     section F are made OPEN, every good one - shape 16, bit 7 set, among
     them - is untouched, and nothing outside the part is read or written.
  3  SCRIPTED runs: a 2-wide corner carried round, a 1-wide corner flown out
     of, a rest at a chute's bottom, a pit ridden round and out, a pit fallen
     through, the lift against a raised floor beside a lip (and none against
     one at the lip's height), a sloped leg, a chute on a bridge left over its
     lip into the void, and MANY's falling leg over its shape-16 cells.
  4  FUZZ: N runs from random states near field cells, every step.
  6  AUTOPILOT (SPEC.md 130.28.10): SHAPE's and PITS's routes through their shapes, the guest's bz_auto
     under bz_apilot against Physics.auto, every step, to the goal (and the CELLS leg on their stored forms:
     bz_cxway's FIELD ways).
  5  HUMPS (SPEC.md 130.44): the BZHUMP=1 test course, HUMP - FIELD cells RAISED over the plate round them, which
     no chute or pit lays (a dome's middle above every edge) and which the guest runs with no code of their own:
     a LOW dome rolled over from rest and stalled at by steel, the HIGH open ridge climbed by steel from the
     bridge's start and crossed at the speed cap, the HIGH dome crossed off its crest line, the LOW ridge's
     crest, a drop onto the HIGH dome's flank - and the fuzz's share near HUMP's raised cells.
"""
import argparse
import os
import random
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bbcourse as BB          # noqa: E402
import bonanza_dsplit as DS    # noqa: E402
import bonanza_ring as R       # noqa: E402

PS, CS, SS = DS.PS, DS.CS, DS.SS

# the three FIELD courses are the tool's own (bbcourse --selfcheck's _field_checks steps the model on them):
# THE CHUTES (a 2-wide chute set in the ground, a 1-wide one with a sloped leg, a floor raised beside a lip),
# THE PIT (a bowl round a hole), THE BRIDGE (a chute over the void) and MANY (17 tables: shape 16's cells
# carry the +1's bit 7, SPEC.md 130.28.2)
CHUTES, PIT, BRIDGE, MANY = BB._FCHUTE, BB._FPIT, BB._FBRIDGE, BB._FMANY


def courses():
    cs = {k: BB.compile_course(t, "<%s>" % k.upper(), _hack={"no_finish": True})
          for k, t in (("chute", CHUTES), ("pit", PIT), ("bridge", BRIDGE), ("many", MANY))}
    cs["hump"] = BB.compile_course(BB.HM_TEST)      # SPEC.md 130.44: HUMP, the BZHUMP=1 knob's test course
    for k in ("shapes", "pits"):                    # SPEC.md 130.28.10: the BZSHAPES=1 courses, whose routes
        f = os.path.join(BB.COURSE_DIR, k + ".bbc")   # name FIELD ways (the CELLS leg: bz_cxway's form)
        cs[k] = BB.compile_course(open(f).read(), f)
    return cs


def autopilot(binp, sym, cs):
    """SPEC.md 130.28.10: the AUTOPILOT under bz_apilot on SHAPE's and PITS's routes, through every chute, the
    dish and the deep pit, to the goal: the guest's keys (bz_auto) against Physics.auto's, every step's state
    and bz_wp equal -> [differences]"""
    out = []
    for k in ("shapes", "pits"):
        c = cs[k]
        g, p = DS.start(binp, sym, c, c.ball)
        g.w("bz_apilot", 1)
        n = 0
        while n < 8000 and not p.goal:
            g.call("bz_step")
            k_ = p.auto()
            p.step(k_)
            n += 1
            a, b = DS.gstate(g) + (g.r("bz_wp", 2), g.r("bz_kstep")), DS.mstate(p) + (p.wp, k_)
            if a != b:
                out.append("autopilot %s: step %d: guest %s model %s" % (c.name, n, a, b))
                break
        print("bonanza_dfield AUTOPILOT %-6s %4d steps, way %d of %d, goal %s, %d falls: %s" % (
            c.name, n, p.wp, len(p.route), bool(p.goal), p.nfall, "every step equal" if not out else "FAIL"))
        if not p.goal or p.nfall:
            out.append("autopilot %s: the model's route ends at way %d, goal %s, %d falls" % (
                c.name, p.wp, bool(p.goal), p.nfall))
    return out


def steer(n, before, after, turn_x):
    """a key byte a step: BEFORE while gx < turn_x, AFTER from then on - a player turning at a corner (the
    keys are a function of the step, so the guest and the model hold the same: the run is replayed once to
    find the step)"""
    return (before, after, turn_x, n)


def scripted():
    """(label, course, material, poke args, keys or a steer, the events it must raise, a check on the model)"""
    K = BB
    U, D, L, Rt, H = K.K_U, K.K_D, K.K_L, K.K_R, K.K_HOP
    rub, stl, gls = K.MAT_RUBBER, K.MAT_STEEL, K.MAT_GLASS
    return [
        ("corner2: a 2-wide corner carried round at 250", "chute", rub, (17, 12, 8 << 8, 0, 250, 0),
         steer(160, 0, D | L, 288), (), lambda p: p.gy >> 8 > 230 and 304 <= p.gx >> 8 < 336),
        ("corner2 steel: at 384", "chute", stl, (17, 12, 8 << 8, 0, 384, 0), steer(160, 0, D | L, 288), (),
         lambda p: p.gy >> 8 > 230),
        ("corner1: a 1-wide corner flown out of at 384", "chute", rub, (14, 26, 0, 8 << 8, 384, 0),
         steer(120, Rt | D, Rt | D, 0), (), lambda p: p.cell(p.gx >> 12, p.gy >> 12)[3] != K.KIND_FIELD),
        ("rest: settles at a chute's bottom, no dither", "chute", rub, (12, 11, 8 << 8, 3 << 8, 0, 160),
         DS.hold(0, 400), (), lambda p: p.gvx == 0 and p.gvy == 0),
        ("pit ride: round and out the far side", "pit", rub, (12, 21, 8 << 8, 8 << 8, 384, 0),
         DS.hold(Rt | D, 140), (), lambda p: p.nfall == 0),
        ("pit fall: through to the hole", "pit", rub, (12, 19, 8 << 8, 15 << 8, 250, 0), DS.hold(0, 140), (),
         lambda p: p.nfall == 1),
        ("lift: a floor above the lip blocks (a wall)", "chute", rub, (13, 11, 8 << 8, 6 << 8, 0, -300),
         DS.hold(U | Rt, 60), ("wall",), None),
        ("lip: a floor at the lip's height does not", "chute", rub, (17, 11, 8 << 8, 12 << 8, 0, -330),
         DS.hold(U | Rt, 40), (), lambda p: p.gy >> 8 < 176),
        ("field to field: across the pit's bank, no wall", "pit", rub, (14, 18, 1216, 1502, -137, -151),
         DS.hold(Rt, 20), (), lambda p: not any(e[0] in ("wall", "corner", "undo") for e in p.events)),
        ("slope: the 1-wide's sloped leg climbed", "chute", stl, (16, 27, 8 << 8, 0, 0, 300),
         DS.hold(D | L, 80), (), None),
        ("bridge: over the lip into the void", "bridge", rub, (16, 15, 8 << 8, 8 << 8, 0, -384),
         DS.hold(U | Rt, 80), (), lambda p: p.nfall == 1),
        ("bridge glass: a hop on a taper", "bridge", gls, (12, 16, 8 << 8, 8 << 8, 200, 0),
         DS.hold(Rt | D, 10) + [H] + DS.hold(Rt | D, 60), ("hop",), None),
        ("many: down a falling leg over shape 16 (bit 7)", "many", rub, (25, 6, 15 << 8, 2 << 8, 0, 200),
         DS.hold(D, 60), (), lambda p: p.gy >> 8 >= 8 * 16),
        # SPEC.md 130.44: HUMP's raised FIELD cells (the LOW dome at (8, 8), the HIGH open ridge on the bridge at
        # x 21 - 22, the HIGH dome at (13, 18), the LOW ridge along y 14)
        ("hump low: rubber over a LOW dome from rest", "hump", rub, (7, 8, 0, 0, 0, 0), DS.hold(Rt | D, 200), (),
         lambda p: p.gx >> 8 > 152),
        ("hump low: steel stalls at a LOW dome's foot", "hump", stl, (7, 8, 0, 0, 0, 0), DS.hold(Rt | D, 200), (),
         lambda p: p.gx >> 8 < 152),
        ("hump high: steel over the bump from the bridge's start", "hump", stl, (16, 7, 8 << 8, 0, 0, 0),
         DS.hold(Rt | D, 160), (), lambda p: p.gx >> 8 > 376 and p.nfall == 0),
        ("hump high: steel at the cap over the bump", "hump", stl, (16, 7, 8 << 8, 0, 384, 0), DS.hold(Rt | D, 80),
         (), lambda p: p.gx >> 8 > 376 and p.nfall == 0),
        ("hump dome: glass across the HIGH dome off its crest", "hump", gls, (11, 18, 0, 4 << 8, 200, 0),
         DS.hold(Rt | D, 100), (), None),
        ("hump ridge: rubber along the LOW ridge's crest", "hump", rub, (10, 14, 0, 0, 200, 0), DS.hold(Rt | D, 80),
         (), None),
        ("hump drop: rubber dropped onto the HIGH dome's flank", "hump", rub, (12, 17, 8 << 8, 8 << 8, 0, 0, 1,
                                                                               40 << 8), DS.hold(0, 120), (), None),
    ]


def keys_of(c, ks, pk, mat):
    """a steer -> its key list, by running the model alone"""
    if not isinstance(ks, tuple):
        return ks
    before, after, turn_x, n = ks
    p = BB.Physics(c, play=True, mat=mat)
    p.tsec = 0

    class _G:
        def w(self, *a):
            pass
    DS.poke(_G(), p, *pk)
    out = []
    for _ in range(n):
        k = after if (p.gx >> 8) >= turn_x else before
        out.append(k)
        p.step(k)
    return out


def near_field(c, rnd):
    grid = BB.Grid(c.cga, c.wcga)
    cells = [(wx, wy) for wx in range(48) for wy in range(48) if grid.cell(wx, wy)[3] == BB.KIND_FIELD]
    wx, wy = rnd.choice(cells)
    return wx + rnd.randint(-1, 1), wy + rnd.randint(-1, 1), rnd.randrange(4096), rnd.randrange(4096)


def fuzz(binp, sym, cs, n, seed):
    rnd = random.Random(seed)
    bad, steps, kinds = [], 0, {}
    names = sorted(cs)
    for i in range(n):
        k = names[i % len(names)]
        c = cs[k]
        mat = rnd.choice((BB.MAT_RUBBER, BB.MAT_STEEL, BB.MAT_GLASS))
        g, p = DS.start(binp, sym, c, mat)
        for _ in range(30):
            wx, wy, pu, pv = near_field(c, rnd)
            rec = p.prec(wx, wy)
            if rec[3] in (BB.KIND_FLOOR, BB.KIND_GOAL, BB.KIND_FIELD):
                break
        else:
            continue
        p.gx, p.gy = (16 * wx << 8) + pu, (16 * wy << 8) + pv
        rec = p.prec(wx, wy)
        air = rnd.random() < 0.3
        gz = ((BB.Physics.h4(rec, pu >> 8, pv >> 8) << 6) + (rnd.randrange(1, 40) << 8)) if air else None
        v = BB.VMAXG
        DS.poke(g, p, wx, wy, pu, pv, rnd.randrange(-v, v + 1), rnd.randrange(-v, v + 1), int(air), gz)
        keys = []
        while len(keys) < 160:
            kb = rnd.choice((0, BB.K_U, BB.K_D, BB.K_L, BB.K_R, BB.K_U | BB.K_L, BB.K_U | BB.K_R, BB.K_D | BB.K_L,
                             BB.K_D | BB.K_R, BB.K_HOP, BB.K_GRIP))
            keys += [kb] * rnd.randrange(1, 30)
        err, ns, ev = DS.run(g, p, keys[:160], "fuzz %d (%s, %s, (%d, %d) %d %d)" % (i, k, BB.MAT_NAMES[mat], wx,
                                                                                       wy, pu, pv))
        steps += ns
        for e in ev:
            kinds[e[0]] = kinds.get(e[0], 0) + 1
        if err:
            bad.append(err)
    return bad, steps, kinds


def hostile(binp, sym, c):
    """130.28.2's bound, on MANY (17 tables): one FIELD cell's shape 31, one's +1 bit 7 set taking a shape
    of 1 - 15 to 17 - 31 -> OPEN; the good ones (shape 16, bit 7, among them) untouched; nothing read or
    written outside the part"""
    from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_READ
    st = bytearray(c.stored)
    diroff, nsec = struct.unpack_from("<HH", st, 38)
    sec = {}
    for j in range(nsec):
        tag, form, off, ln, dl = struct.unpack_from("<BBHHH", st, diroff + 8 * j)
        sec[chr(tag)] = (off, ln)
    co, cl = sec["C"]
    fields = [i for i in range(co, co + cl, 4) if st[i + 2] & 15 == BB.KIND_FIELD]
    hi = [i for i in fields if st[i + 1] & 0x80]
    assert len(c.ftabs) > 16 and hi, "the hostile leg wants a course with shape 16 (MANY)"
    a = fields[0]
    b = next(i for i in fields if i != a and 1 <= st[i + 1] & 15 and not st[i + 1] & 0x80)
    st[a + 1] |= 0x8F                                   # shape 31: past F
    st[b + 1] |= 0x80                                   # shape 17 - 31: past F (17 tables)
    g = DS.Guest(binp, sym, st)
    lo, hi = PS * 16, PS * 16 + len(st)
    bad = []

    def watch(mu, access, addr, size, value, ud):
        if 0x10000 <= addr < 0xF0000 and not lo <= addr < hi and not CS * 16 <= addr < CS * 16 + 0x10000 \
                and not SS * 16 <= addr < SS * 16 + 0x10000 \
                and not (access == UC_MEM_READ and DS.KS * 16 <= addr < DS.KS * 16 + 0x10000):    # (the kit, 130.37)
            bad.append("an access at %05Xh, outside the part" % addr)
    g.mu.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, watch)
    g.w("bz_cseg", PS, 2)
    g.call("bz_cexp")
    ram = bytes(g.mu.mem_read(PS * 16, len(st)))
    if ram[a:a + 4] != bytes((0x80, 0, 0, 0)) or ram[b:b + 4] != bytes((0x80, 0, 0, 0)):
        bad.append("the two bad FIELD cells are %s, %s - not OPEN" % (ram[a:a + 4].hex(), ram[b:b + 4].hex()))
    good = [i for i in fields if i not in (a, b) and ram[i:i + 4] != c.cga[i:i + 4]]
    if good:
        bad.append("a good FIELD cell changed: offsets %s" % good[:3])
    return bad[:4]


REDS = {
    # 130.28.10: the autopilot steers every way as a plane way (no ground frame, no cruise)
    "autoplane": [("bzgame.inc", "    and di, 1                   ; DI = 1 a FIELD way (130.28.10)\n    jz .plane\n",
                   "    and di, 1                   ; DI = 1 a FIELD way (130.28.10)\n    jmp .plane  ; RED\n")],
    # 130.28.10: the WAYS form writes a FIELD way as a plane's (no mark, its +1 read as slopes)
    "wayplane": [("bonanza.asm", "    cmp ch, BZ_KFIELD\n    je .fld\n", "    cmp ch, BZ_KFIELD  ; RED wayplane\n")],
    # 130.28.5.3: no lift - a FIELD centre's plane neighbour blocks by the start z alone
    "nolift": [("bzphys.inc", "    cmp bl, BZ_KFIELD\n    je .lift\n", "    cmp bl, BZ_KFIELD  ; RED nolift\n")],
    # 130.28.5.3: field to field blocks
    "ffblock": [("bzphys.inc", "    cmp bl, BZ_KFIELD\n    je .no\n.fpl:",
                 "    cmp bl, BZ_KFIELD\n    je .yes  ; RED ffblock\n.fpl:")],
    # 130.28.2: a symmetry's stride swapped (DU for DV)
    "symswap": [("bzphys.inc", "    add di, [bz_fsymt + bx + 2]\n", "    add di, [bz_fsymt + bx + 4]  ; RED symswap\n")],
    # 130.28.2: CELLS reads a FIELD edge neighbour as VOID
    "cellfield": [("bonanza.asm", "    cmp ah, BZ_KFIELD           ; SPEC.md 130.28.2: a FIELD neighbour is not VOID\n"
                   "    jne .vs2\n", "    jmp .vs2  ; RED cellfield\n")],
    # 130.28.2: the shape's fifth bit (the +1's bit 7) not read - shape 16 reads table 0
    "nofifth": [("bzphys.inc", "    or al, ah                   ; AL = the shape, 0 - 31 (SPEC.md 130.28.2)\n",
                 "    ; RED nofifth\n")],
    # 130.28.2: the hostile bound dropped
    "nofbound": [("bonanza.asm", "    cmp ax, [bz_ffe]\n    ja .co\n", "    cmp ax, [bz_ffe]  ; RED nofbound\n")],
}


def check(n=150, seed=1127, verbose=True, patches=()):
    out = []
    with tempfile.TemporaryDirectory() as td:
        binp, sym = DS.build(td, patches)
        cs = courses()
        b = DS.cells_check(binp, sym, cs)
        print("bonanza_dfield CELLS: bz_cexp on %s's stored forms -> %s" % (
            ", ".join(sorted(cs)), "; ".join(b) or "each its RAM form, byte for byte"))
        out += b
        b = hostile(binp, sym, cs["many"])
        print("bonanza_dfield HOSTILE: %s" % ("; ".join(b) or "the two bad FIELD cells OPEN, nothing outside the part"))
        out += b
        for label, ck, mat, pk, ks, want, ok in scripted():
            c = cs[ck]
            keys = keys_of(c, ks, pk, mat)
            g, p = DS.start(binp, sym, c, mat)
            DS.poke(g, p, *pk)
            err, ns, ev = DS.run(g, p, keys, label)
            got = sorted({e[0] for e in ev})
            miss = [w for w in want if w not in got]
            bad_ok = ok is not None and not err and not ok(p)
            if err:
                out.append(err)
            elif miss or bad_ok:
                out.append("%s: the model raised %s (missing %s), its outcome %s: the run does not do what it "
                           "names" % (label, got, miss, "wrong" if bad_ok else "right"))
            if verbose:
                print("bonanza_dfield %-48s %3d steps, events %s: %s" % (
                    label, ns, ",".join(got) or "-", "FAIL" if err or miss or bad_ok else "every step equal"))
        out += autopilot(binp, sym, cs)
        b, steps, kinds = fuzz(binp, sym, cs, n, seed)
        print("bonanza_dfield fuzz: %d runs, %d steps near field cells (seed %d), events %s: %s" % (
            n, steps, seed, kinds, "%d differ" % len(b) if b else "every step equal"))
        out += b[:10]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=150)
    ap.add_argument("--seed", type=int, default=1127)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--reds", action="store_true")
    a = ap.parse_args()
    R.dev()                             # the BZDEV=1 build (SPEC.md 130.26.6.1)
    if a.red or a.reds:
        for name in ([a.red] if a.red else sorted(REDS)):
            bad = check(a.runs, a.seed, verbose=False, patches=REDS[name])
            assert bad, "RED ARM %s: the check stayed GREEN against a broken package" % name
            print("bonanza_dfield --red %s: went red (%d): %s" % (name, len(bad), bad[0][:160]))
        return
    bad = check(a.runs, a.seed)
    for b in bad:
        print("FAIL %s" % b)
    assert not bad, "%d difference(s) between the guest and the model" % len(bad)
    print("bonanza_dfield: PASS")


if __name__ == "__main__":
    main()
