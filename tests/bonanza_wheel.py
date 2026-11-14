#!/usr/bin/env python3
"""BONANZA: the wheel - lanes paced by the retrace wait (SPEC.md 128.12.4, 128.12.5, 128.12.13.2, 128.12.15).

    make bonanzadisk && python3 tests/bonanza_wheel.py [--adapter cga|herc|both] [--leg bench|low|corner|stale|gate|all]
    python3 tests/bonanza_wheel.py --red NAME      (a red arm, below)
    python3 tests/bonanza_wheel.py --check         (the host half: the gate logs proved, every red arm assembled)

On MartyPC's CGA and Hercules XTs, five legs a card:

  BENCH  the benchmark on MILL ([bz_crs] poked at bz_launch's entry, [bz_hvoff]
         0: the shipped camera), its 1,200 frames under breakpoints - STOPS
         on the two instructions that write bz_ldrw (bz_lsync's and
         bz_wcommit's `mov [bz_ldrw + bx], al`, found by their bytes in the
         assembled image), on bz_wcommit's entry (which way the commit
         reaches the glass, from its RETURN address, and the rectangles
         bz_lclip left: bz_lra, bz_lrb) and on bz_presented; LOGGED (no
         stop, MartyPC's own cycle count) at bz_tw, bz_tv, bz_tf, bz_vr's
         .rose and .high and inside bz_wcore at its CLI, the pass's call
         and return (bz_wpass, SPEC.md 128.13.5.1) and its POPF.  From frame HOLD_FROM, one frame in
         HOLD_EVERY is made LATE on purpose: [bz_hold] poked (bz_t0 then spins
         bz_hold x 256 PIT counts, past the frame's first sync).
  LOW    bonanza_ring's LOW SCENARIO (play mode on MILL, the ball HELD above a
         post a centred window puts at line 160, the post's lit frames poked
         every 6 frames): the commits the route never makes - AHEAD of the
         beam, the CGA's LEAD, a 2-word lane's - judged as BENCH's are; (3)'s
         and (5)'s "each kind at least once" are over BENCH's and LOW's
         commits together (the final pass).  Then THE BEAM SWEEP (SPEC.md
         128.13.7 item 2): every 8 frames the post is KICKED ([bz_pkick] + 1),
         and on the frame after its lit frames are poked to 0 (DUE) and that
         frame made late by [bz_hold] 24 - 40 (x 256 counts), so the wheel
         decides with the beam crossing the post's lines; at least 15 of the 17
         due frames have the post a wheel candidate at bz_tw, ASSERTED.
  CORNER play mode on MILL, a LIGHT diagonal step (SPEC.md 128.13.7 item 5):
         [bz_cmode] 1 (TRICKLE, wave 0's camera), the ball poked so a CENTRED
         full write puts the window's bottom edge through a lane's middle row
         and its left edge one word inside it, held (the wheel never runs on
         the frame after a full write); then poked onto the band's foot and
         the dead zone's left edge exactly (two ball boxes, no camera step),
         HELD there one frame (no box), then moved 2 px over both in its cell:
         the step frame takes one row before its wait and the column after it,
         and the lane is made due on it by its [bz_ldrw] poked one pose on.
         The wheel's commit of it is read at bz_wcommit, the card's banks
         before and after the pass (bz_wcore + 2, + 5) - every changed byte
         must be a cell the commit may write - and the step frame's bz_tw
         after the sync's rise is REPORTED each try (about 57 - 60k on the
         CGA, PREDICTED).  The bottom-RIGHT corner where no window reaches the
         left; on the Hercules no window reaches either (its 45 words hold
         every MILL lane's columns): REPORTED there.
  STALE  play mode on MILL, TRICKLE (SPEC.md 128.13.7 item 4): a centred full
         write puts a ROTOR wholly above the window's top (its last card row
         R0 - 1) with the ball held; after 16 steps, on a frame whose true pose
         has a different lowest row from the full write's, the ball is poked
         just over the band's top edge: the camera steps up a row and the row
         brings the rotor's lowest cells in from the map - (9) judges them.
         Where no window puts a rotor so, the leg SKIPS naming the course.
  GATE   the REPLAYS of bonanzaphys's `knock` and `pass` logs (written into
         bz_rlog, R, the ball poked at the first bz_t0), the windmill's drawn
         pose read at every bz_presented and the model stepped beside it.

THE CHECKS (SPEC.md 128.12.13.2's bonanzawheel), each failure line opening
with its number:

  (1)  every write to bz_ldrw CHANGES its value, and every lane-writer commit
       (bz_wcommit) makes one - TITHE's titheframe property;
  (2)  a shown rotor's drawn pose is never AHEAD of its true one (the true
       pose of the frame's last step, 128.12.15 item 1: the first step on
       which the drawn pose comes round again is not nearer than the last on
       which it was true), and the results' bz_wlate 0;
  (3)  no pass's write while the beam is in the window lines it writes,
       wait commits and LEADs alike, off MartyPC's cycle counter: the pass's
       span (bz_wcore + 2 to + 5: its call to its return) ends before the beam reaches the
       lane's first shown line - (38 + F) lines of 304 clocks after the sync's
       rise on the CGA, the rise read at bz_vr.rose and carried across
       refreshes by the period those rises measure - or starts after it passed
       the last; and no wait commit on a frame made late (bz_hold), whose
       candidates bz_wskip counts.  ASSERTED on the CGA; on the Hercules
       REPORTED, the guest's verdict (its pass) beside the counter's at 98
       lines and 63.4 counts a line (SPEC.md 128.12.15 item 5);
  (4)  every wait commit ends by its deadline - the results' bz_wover 0 - and
       the wait after a frame's wait commits finds the sync RISING (.rose);
  (5)  each commit's calibrated cost - its OWN cost' (bz_wcst: bz_lcf's for a
       whole lane, else warr + (words (wcw + lines wlw)) >> 4 and its terms,
       SPEC.md 128.13.5.2), the trim's scale apart - within CAL_TOL of its whole span on the cycle
       counter (from the TEST's clock sample - bz_wnow's entry before the
       commit, where the calibration's span starts - to bz_wcore's POPF, the
       closing latch a few instructions before), over 2-word lanes (posts) and 3-word lanes (rotors): a
       WHOLE-LANE commit's (bz_lcf's price) within CAL_TOL, a CLIPPED
       commit's span at most (1 + CAL_TOL) times its price, asserted on the
       CGA, reported on the Hercules (item 5); a commit priced at NOTHING
       fails on both; each kind's pass span REPORTED against 128.13.5.1;
  (6)  no commit's cells outside the SHOWN window and 128.2 rule 1's row cells
       (the entering rows LESS the entering column), the allowed cells
       derived here from the window words, and none left out; on the CORNER
       leg's LIGHT down-and-left step the commit LANDS (ASSERTED on the CGA)
       and every byte the pass changed on the card is one of those cells'
       (the corner cell (R0 + H, c0 - 1) aliases the old window's last shown
       cell);
  (7)  each shown rotor's drawn pose changes - by any route - at least
       RATE_MIN of the times its true pose does while it is shown, and never
       more often (one carry-in a shown spell allowed);
  (8)  the trim back at 100 at the leg's end;
  (9)  a lane brought onto the glass by an ENTERING strip - wholly outside the
       window the frame began with - shows its TRUE pose of that frame, on
       the card, not its bz_ldrw (a lane brought in stale agrees with its own
       stale bz_ldrw: bonanzaring's oracle cannot see it);
  (10) at every knock-back and doorway capture of the GATE replays the rotor's
       drawn pose at that frame's bz_presented is closed or open to match -
       but (128.12.15 item 1) a step other than the frame's last, on a frame
       of two or more steps, may be one phase off what is shown;
  (11) a LEAD only for the lane the wait marked ([bz_wld]), at most one a
       frame, never on a heavy frame;
  (12) the owner's preview, TIGHTENED (SPEC.md 128.13.12): every KICK
       ([bz_pkick] changing between two presented frames) has its post drawn
       LIT ([bz_ldrw] 1) on the KICK's frame - the next only when a second
       lighting post took the slot, a strip met the slab or the slab's box
       could not wait (each REPORTED by reason; any other delay fails) - lit
       for at least BZ_PLITF (8) presented frames unless it left the shown
       window (or a harness cut them), and drawn DARK again within BZ_WPRF + 1
       frames of its lit frames running out while shown; on BENCH and LOW;
  (13) after every walk, each rotor in the walk's range has bz_lnext equal to
       the model's next change step - the step at which its pose, from the
       seed and the mask, next differs (SPEC.md 128.13.5.3);

--red NAME builds a broken package in a temporary directory (never build/)
and PASSES only if the row FAILS at its own check:
  repeat     every lane in the walk's range committed every visit: (1)
  ahead      bz_wcommit records the pose one PAST the true one: (2)
  nobeam     the AHEAD test and the BEHIND spin taken out: (3), the CGA
  kmod       the first-sync rule taken out - the deadline never reached, so a
             frame made late commits at once, reckoned as if no sync had
             passed: (3) on a bz_hold frame, the CGA
  halfcal    the calibration's bz_wlw halved after it runs: priced 30% under (5)
  alias      bz_lclip's window clip taken out - the whole lane: (6) on the
             LIGHT corner step's commit (the corner leg), the CGA
  corner     the commit's entering-row cells include the entering column's:
             (6) on the corner leg's diagonal step
  lanestale  the walk's RAM sync of a lane wholly outside the window left out:
             (9) on the STALE scene
  costtab    bz_lcf left unfilled (0): a whole lane priced at nothing - (5) on
             the LOW leg's whole posts, the CGA
  lnext      bz_lnext one STEP late: (13) on BENCH
  pskip      the post's skip without its drawn-dark clause: the sweep's post,
             its lit frames poked out, never goes dark - (12) on the LOW leg
  gatelate   a rotor whose gate state changes is skipped by the walk (the
             must-draw rule taken out, the wheel told to skip it): (10)
  litsteps   the post's lit hold never counted down by the walk but cleared
             after its first frame (wave 3's first rule, a few STEPS lit, the
             preview's "rarely lights up"): (12)

WAVE 5B (SPEC.md 128.15.13): unchanged in logic.  The course parts are BZC2's
now - stored compact, expanded in place at the fetch - and every model here
reads the TOOL'S RAM FORM (bbcourse's compile: the prop records, the lanes'
pose maps and the cells at that form's offsets, which moved with the header
and D's 4-byte records), the form the guest holds after the expansion; the
legs re-run on the new parts.  Every red tree packs its parts in the shipped
build's format (bonanza_ring.build_tree, SPEC.md 128.15.9).  (Wave 4's check
(14), the HUD's rect, and its red arm `hudrect` went in wave 5a with the HUD.)
"""
import argparse
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_phys as P       # noqa: E402

BENCH = 1200                   # bzgame.inc BZ_BENCH
LSH = {"cga": 1, "herc": 2}    # card rows to lines: rl = 1 << lsh
TO0 = {"cga": 38, "herc": 98}  # lines from the sync's rise to window line 0 (SPEC.md 128.12.5.3)
LINE = {"cga": 304.0, "herc": 63.4 * 4}     # clocks a line (76 counts; the Hercules about 63.4)
P0 = {"cga": 79648.0, "herc": 93790.0}      # a refresh, clocks, NOMINAL: refined from the rises
SPIN_TOL = R.SPIN_TOL          # clocks: bz_vr's tight spin turn (the rise to the .rose stop)
HOLD_FROM, HOLD_EVERY = 120, 9
HOLD_VALS = tuple(range(72, 124, 4))        # x 256 PIT counts: 0.93 - 1.56 CGA refreshes late
CAL_TOL = 0.15
RATE_MIN = 0.90
VRAM = {"cga": (0xB8000, 0x4000), "herc": (0xB0000, 0x8000)}
CORNER_TRIES = 6                                # (SPEC.md 128.13.7 item 5, restated: admitted while bz_tw <= ~58k)
CORNER_STEP = 4                                 # the corner leg's poke onto the edges: bz_first poked at the
                                                # first bz_t0 makes the NEXT frame the full write, and the
                                                # wheel skips the frame after a full write (bz_wvok: the final
                                                # pass); then one frame held, then the step (CORNER_STEP + 2)


def writers(src=None, art=None, sym=None):
    """the image offsets of every `mov [bz_ldrw + bx], al` (88 87 disp16), out
    of the package assembled as R.symbols() assembles it: -> sorted offsets"""
    d = src or os.path.join(ROOT, "apps", "bonanza")
    art = art or R.at("build/bonanza-art")
    sym = sym or R.symbols(src, art)
    with tempfile.TemporaryDirectory() as td:
        b = os.path.join(td, "w.bin")
        R.assemble(d, art, b)
        img = open(b, "rb").read()
    pat = b"\x88\x87" + struct.pack("<H", sym["bz_ldrw"])
    out, i = [], img.find(pat)
    while i >= 0:
        out.append(i)
        i = img.find(pat, i + 1)
    return out


class Snap(object):
    """NAMES of the package's bss read in ONE debug-server read (their span)"""

    def __init__(self, g, names):
        self.g = g
        offs = [g.sym[n] for n in names]
        self.lo, self.hi = min(offs), max(offs) + 32
        self.raw = g.m.read(g.base + self.lo, self.hi - self.lo)

    def b(self, n, k=0):
        return self.raw[self.g.sym[n] - self.lo + k]

    def w(self, n, k=0):
        return struct.unpack_from("<H", self.raw, self.g.sym[n] - self.lo + 2 * k)[0]

    def s(self, n):
        return struct.unpack_from("<h", self.raw, self.g.sym[n] - self.lo)[0]

    def bytes(self, n, k):
        o = self.g.sym[n] - self.lo
        return self.raw[o:o + k]


WIN = ("bz_full", "bz_S", "bz_R0", "bz_c0", "bz_R0n", "bz_c0n", "bz_dr", "bz_dc")
WHL = ("bz_hold", "bz_heavy", "bz_wld", "bz_wcn", "bz_nlane", "bz_ldrw", "bz_ltru", "bz_lhold", "bz_lra", "bz_lrb",
       "bz_wlw", "bz_wcw", "bz_warr", "bz_trim", "bz_wcst", "bz_ctype", "bz_cln", "bz_cT")


def cells(rect):
    """card rows [r0, r1) x words [x0, x1) -> {(row, word)}"""
    r0, r1, x0, x1 = rect
    return {(r, x) for r in range(r0, r1) for x in range(x0, x1)} if r1 > r0 and x1 > x0 else set()


def clip(a, b):
    return (max(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), min(a[3], b[3]))


def lane_cells(rects, lane, lsh):
    col, brow, w, h = rects[lane][:4]
    return ((8 * brow) >> lsh, (8 * (brow + h)) >> lsh, col, col + w)


def allowed(cm, lane_rect, H, Wc):
    """SPEC.md 128.12.4.4 rule 1a / rule 5, from the window words alone: ->
    (the shown cells' rect, the entering rows' rect).  A wheel commit (before
    the flip) writes the lane's cells in the SHOWN window (bz_R0, bz_c0) and in
    this frame's entering rows less the entering column; the LEAD (after it,
    bz_R0 / bz_c0 the new window) only the shown ones."""
    R0, c0 = cm["R0"], cm["c0"]
    shown = clip(lane_rect, (R0, R0 + H, c0, c0 + Wc))
    if cm["kind"] == "lead" or not cm["dr"]:
        return shown, (0, 0, 0, 0)
    dr, dc, R0n, c0n = cm["dr"], cm["dc"], cm["R0n"], cm["c0n"]
    rows = (R0n + H - dr, R0n + H) if dr > 0 else (R0n, R0n - dr)
    cols = (c0n, c0n + Wc - 1) if dc > 0 else (c0n + 1, c0n + Wc) if dc < 0 else (c0n, c0n + Wc)
    return shown, clip(lane_rect, rows + cols)


def rotor_pose(rec, n):
    return ((n + rec["seed"]) & rec["mask"] & 0xFFFF) >> rec["shift"]


def ahead_of(rec, drawn, n_last):
    """is DRAWN a pose the rotor reaches AFTER step n_last sooner than one it
    held at or before it?  -> (ahead, steps back, steps on)"""
    P_ = rec["mask"] + 1
    back = next((d for d in range(P_) if rotor_pose(rec, n_last - d) == drawn), P_)
    on = next((k for k in range(1, P_ + 1) if rotor_pose(rec, n_last + k) == drawn), P_)
    return on < back, back, on


class Rises(object):
    """the sync's rises a leg's .rose stops logged, and the refresh they measure"""

    def __init__(self, cyc, tag):
        self.c = sorted(cyc)
        self.P = P0[tag]
        if len(self.c) >= 2:
            span = self.c[-1] - self.c[0]
            n = max(1, int(round(span / self.P)))
            self.P = span / float(n)

    def at(self, cyc):
        """the last rise at or before CYC: the latest logged one carried by whole
        refreshes - or None, before the first"""
        i = None
        lo, hi = 0, len(self.c)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.c[mid] <= cyc:
                i, lo = mid, mid + 1
            else:
                hi = mid
        if i is None:
            return None
        rh = self.c[i]
        return rh + int((cyc - rh) // self.P) * self.P


def boot_pkg(tag, apps, src):
    sym = R.symbols(src)
    ui = os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"), machine=R.MACHINE[tag])
    return ui, sym


def launch_mill(g, key, hvoff):
    """KEY (B or Enter) on the desktop, stopped at bz_launch's entry: MILL into
    [bz_crs], [bz_hvoff] HVOFF; the guest left STOPPED there"""
    m = g.m
    m.bp_exec(g.a("bz_launch"))
    g.key(key)
    assert m.wait_stop(60) == "breakpoint", "%s did not reach bz_launch" % key
    g.putb("bz_crs", R.CRS_K["mill"])
    g.putb("bz_hvoff", hvoff)
    m.bp_exec()


# ---- the BENCH leg ---------------------------------------------------------------
def pres_snap(g):
    """at bz_presented: the window, the lanes' drawn poses, the posts' kicks and
    lit frames, the contact group, and (13)'s walk - its range and each lane's
    bz_lnext - read off the paused guest"""
    w = Snap(g, WIN)
    h = Snap(g, WHL)
    cnt = Snap(g, ("bz_frames", "bz_wcom", "bz_wover", "bz_wlate", "bz_wlead", "bz_wskip", "bz_wtmin"))
    ph = Snap(g, ("bz_nstep", "bz_pkick", "bz_tube"))
    n = h.b("bz_nlane")
    pn = BB.PROP_MAX
    out = {"frames": cnt.w("bz_frames"), "R0": w.w("bz_R0"), "c0": w.w("bz_c0"), "S": w.w("bz_S"),
           "full": w.b("bz_full"), "nstep": struct.unpack_from("<I", ph.bytes("bz_nstep", 4))[0],
           "pkick": [ph.w("bz_pkick", k) for k in range(pn)], "drawn": list(h.bytes("bz_ldrw", n)),
           "hold": list(h.bytes("bz_lhold", pn)), "wcn": h.b("bz_wcn"), "wskip": cnt.w("bz_wskip"),
           "heavy": h.b("bz_heavy"), "ctype": h.b("bz_ctype"), "cln": h.b("bz_cln"), "mustp": g.b("bz_mustp")}
    if "bz_lnext" in g.sym:                     # (13): the walk's range and bz_lnext (SPEC.md 128.13.5.3)
        out["lnext"] = list(struct.unpack("<%dH" % n, g.m.read(g.a("bz_lnext"), 2 * n))) if n else []
        out["lrw"] = list(struct.unpack("<%dh" % n, g.m.read(g.a("bz_lrw"), 2 * n))) if n else []
        out["lhh"] = list(g.m.read(g.a("bz_lhh"), n)) if n else []
        out["range"] = (g.b("bz_lr0"), g.b("bz_lr1"), g.s("bz_pra"), g.s("bz_prb"))
    return out


def enter_check(g, ref, prev, out, rects, recs):
    """(9) at bz_presented: every lane an ENTERING strip brought onto the glass
    (wholly outside the window PREV began with, partly in OUT's) shows its TRUE
    pose of the frame on the card.  -> [(frame, lane, true pose, its bz_ldrw,
    pixels wrong)]"""
    if prev is None or out["full"]:
        return []
    tag, crs = g.tag, ref.c
    lsh = LSH[tag]
    Wc, H = BB.CARDS[tag == "herc"][:2]
    res = []
    for i in rects:
        q = lane_cells(rects, i, lsh)
        was = cells(clip(q, (prev["R0"], prev["R0"] + H, prev["c0"], prev["c0"] + Wc)))
        now = clip(q, (out["R0"], out["R0"] + H, out["c0"], out["c0"] + Wc))
        if was or not cells(now):
            continue
        tq = R.true_pose(recs[i], out["nstep"], out["pkick"], out["hold"])
        lk, _ = g.look(crs)
        lanes = dict(enumerate(out["drawn"]))
        lanes[i] = tq
        view = ref.rule((lanes, g.slab()), lk)
        exp = ref.picture(out["R0"], out["c0"], lk, view)
        got = g.decode(out["S"])
        y0, y1 = (now[0] - out["R0"]) << lsh, (now[1] - out["R0"]) << lsh
        x0, x1 = 8 * (now[2] - out["c0"]), 8 * (now[3] - out["c0"])
        bad = sum(1 for y in range(y0, y1) for x in range(x0, x1) if got[y][x] != exp[y][x])
        res.append((out["frames"], i, tq, out["drawn"][i] if i < len(out["drawn"]) else None, bad))
    return res


def rotor_next(rec, nstep):
    """(13)'s MODEL: the bz_nstep value at which a rotor's true pose - judged at
    n_last = nstep - 1 - next changes: nstep + k for the least k whose pose at
    n_last + k is not the pose at n_last (from the seed and the mask alone)"""
    n_last = nstep - 1
    q = rotor_pose(rec, n_last)
    k = next(k for k in range(1, rec["mask"] + 2) if rotor_pose(rec, n_last + k) != q)
    return (nstep + k) & 0xFFFF


def lnext_check(frames, recs, fails, rep, label=""):
    """(13): after every walk, each rotor in the walk's range has bz_lnext equal
    to the model's next change step (SPEC.md 128.13.5.3, 128.13.12)"""
    nj = nbad = 0
    for fi, fr in enumerate(frames):
        pr = fr.get("pr")
        if not pr or "lnext" not in pr:
            continue
        r0, r1, ra, rb = pr["range"]
        for i in range(r0, min(r1, len(pr["lnext"]))):
            if i not in recs or recs[i]["kind"] != BB.PK_WINDMILL:
                continue
            if not (pr["lrw"][i] < rb and pr["lrw"][i] + pr["lhh"][i] > ra):
                continue                        # (outside the range's exact test: not walked)
            nj += 1
            want = rotor_next(recs[i], pr["nstep"] & 0xFFFF)
            if pr["lnext"][i] != want:
                nbad += 1
                if nbad <= 4:
                    fails.append("(13)%s frame %d: rotor %d's bz_lnext %d after the walk, the model's next change "
                                 "step %d (bz_nstep %d)" % (label, fi + 1, i, pr["lnext"][i], want,
                                                            pr["nstep"] & 0xFFFF))
    if not nj:
        fails.append("(13)%s no rotor was in the walk's range at a presented frame: bz_lnext never judged" % label)
    rep.append("(13)%s %d rotor-frames in the walk's range judged, bz_lnext the model's next change step on %d" % (
        label, nj, nj - nbad))


def post_checks(frames, rects, recs, lsh, H, Wc, fails, rep, label="", cuts=False):
    """(12), tightened (SPEC.md 128.13.12): every KICK ([bz_pkick] changing
    between two presented frames) has its post drawn LIT ([bz_ldrw] 1) on the
    KICK's frame - one frame later only when that frame's contact slot went to a
    second lighting post (bz_mustp another), a strip meeting the slab (bz_ctype
    3) or the slab's box that could not wait (bz_ctype 2), each REPORTED by
    reason; any other delay fails - lit for at least BZ_PLITF presented frames
    unless it left the shown window; and once its lit frames run out ([bz_lhold]
    reaching 0) while it is shown and drawn lit, drawn DARK again within
    BZ_WPRF + 1 frames (a new kick or the window leaving it apart)"""
    posts = [i for i in rects if recs[i]["kind"] == BB.PK_BUMPER]
    nk, lags, runs, why1, darks = 0, [], [], {}, []

    def shown(fr, i):
        pr = fr["pr"]
        return bool(cells(clip(lane_cells(rects, i, lsh), (pr["R0"], pr["R0"] + H, pr["c0"], pr["c0"] + Wc))))
    for i in posts:
        prk = None
        for fi, fr in enumerate(frames):
            pr = fr.get("pr")
            if not pr or i >= len(pr["drawn"]):
                prk = None
                continue
            k = pr["pkick"][i]
            if prk is not None and k != prk:
                nk += 1
                f1 = next((f for f in range(fi, len(frames)) if frames[f].get("pr")
                           and frames[f]["pr"]["drawn"][i] == 1), None)
                reason = None
                if f1 == fi + 1:
                    ct, mp = pr.get("ctype"), pr.get("mustp", 0)
                    reason = ("a second lighting post took the slot" if mp and mp != i + 1 else
                              "a strip met the slab" if ct == 3 else
                              "the slab's box could not wait" if ct == 2 else None)
                if f1 is None or f1 > fi + 1 or (f1 == fi + 1 and reason is None):
                    fails.append("(12)%s frame %d: post %d kicked, its LIT pose %s" % (
                        label, fi + 1, i, "never drawn" if f1 is None else
                        "drawn %d frame%s after the kick's frame, for no reason allowed (bz_ctype %s, bz_mustp %s)"
                        % (f1 - fi, "s" if f1 - fi > 1 else "", pr.get("ctype"), pr.get("mustp"))))
                    prk = k
                    continue
                if reason:
                    why1[reason] = why1.get(reason, 0) + 1
                lags.append(f1 - fi)
                f2 = next((f for f in range(f1, len(frames)) if not frames[f].get("pr")
                           or frames[f]["pr"]["drawn"][i] != 1), len(frames))
                left = any(not shown(frames[f], i) for f in range(f1, min(f2 + 1, len(frames)))
                           if frames[f].get("pr"))
                runs.append(f2 - f1)
                # (a HARNESS's cut - the LOW leg's sweep pokes [bz_lhold] 0 - drops the count by more than
                # the one a frame the walk counts off: that run is the harness's, not the rule's.  CUTS: only
                # on a leg that pokes it - the final pass of wave 3b: on BENCH, which pokes nothing, the
                # exemption swallowed `litsteps`, whose broken walk drops the count to 0 itself)
                cut = cuts and any(frames[f]["pr"]["hold"][i] + 1 < frames[f - 1]["pr"]["hold"][i]
                          for f in range(f1 + 1, min(f2 + 1, len(frames)))
                          if frames[f].get("pr") and frames[f - 1].get("pr"))
                if f2 - f1 < BB.PLITF and not left and not cut and f2 < len(frames):
                    fails.append("(12)%s frame %d: post %d lit for only %d presented frames, not %d" % (
                        label, f1 + 1, i, f2 - f1, BB.PLITF))
            prk = k
            # ...and DARK again once its lit frames run out, while shown and drawn lit
            if fi and frames[fi - 1].get("pr") and i < len(frames[fi - 1]["pr"]["drawn"]):
                p0 = frames[fi - 1]["pr"]
                if p0["hold"][i] and not pr["hold"][i] and p0["drawn"][i] == 1 and shown(fr, i):
                    f3 = next((f for f in range(fi, len(frames)) if not frames[f].get("pr")
                               or frames[f]["pr"]["drawn"][i] != 1 or frames[f]["pr"]["pkick"][i] != k
                               or not shown(frames[f], i)), None)
                    lag = None if f3 is None else f3 - fi
                    if f3 is None and len(frames) - fi <= BB.WPRF + 1:
                        continue                # (the leg ended first)
                    darks.append(lag)
                    if lag is None or lag > BB.WPRF + 1:
                        fails.append("(12)%s frame %d: post %d's lit frames ran out while it was shown and drawn lit, "
                                     "and it is %s (BZ_WPRF + 1 = %d frames at most)" % (
                                         label, fi + 1, i, "never drawn dark" if lag is None else
                                         "drawn dark only %d frames later" % lag, BB.WPRF + 1))
    if not nk:
        fails.append("(12)%s no post was kicked on the leg: the lit rule was never judged" % label)
    rep.append("(12)%s %d kicks: each post drawn LIT on its kick's frame or (by reason) the next - lags %s, the "
               "next frame's reasons %s - and lit for %s presented frames (at least %d); %d posts' lit frames ran "
               "out while shown, drawn dark within %s frames (at most %d)" % (
                   label, nk, sorted(set(lags)), why1 or "none", sorted(set(runs)), BB.PLITF, len(darks),
                   sorted(set(d for d in darks if d is not None)), BB.WPRF + 1))


def commit_snap(g, r):
    """at bz_wcommit's entry (REGS R): the commit, as commit_checks judges it"""
    kind, lane = R.commit_kind(g, r)
    w = Snap(g, WIN)
    h = Snap(g, WHL)
    return {"kind": kind, "lane": lane, "R0": w.w("bz_R0"), "c0": w.w("bz_c0"), "R0n": w.w("bz_R0n"),
            "c0n": w.w("bz_c0n"), "dr": w.s("bz_dr"), "dc": w.s("bz_dc"),
            "lra": struct.unpack("<4h", h.bytes("bz_lra", 8)), "lrb": struct.unpack("<4h", h.bytes("bz_lrb", 8)),
            "wlw": h.w("bz_wlw"), "wcw": h.w("bz_wcw"), "warr": h.w("bz_warr"), "trim": h.w("bz_trim"),
            "wcst": h.w("bz_wcst"), "wld": h.b("bz_wld"), "heavy": h.b("bz_heavy"),
            "drawn": h.b("bz_ldrw", lane), "true": h.b("bz_ltru", lane)}


def bench_leg(g, ref, wr):
    """-> (failures, reports, the commits judged: {"beam", "cost"})"""
    m, tag, crs = g.m, g.tag, ref.c
    recs = {r["i"]: r for r in crs.part["props"]}
    rects = R.lane_rects(crs)
    rotors = [i for i in rects if recs[i]["kind"] == BB.PK_WINDMILL]
    wc = g.a("bz_wcore")
    code = m.read(wc, 10)
    assert (code[0], code[1], code[2], code[5], code[8], code[9]) == (0x9C, 0xFA, 0xE8, 0xE8, 0x9D, 0xC3), \
        "bz_wcore is not PUSHF CLI CALL(bz_wpass) CALL(bz_clk_sample) POPF RET (SPEC.md 128.13.12): the row's " \
        "logged offsets moved (%s)" % code.hex()
    wa = [g.base + o for o in wr]
    site_wc = [i for i, o in enumerate(wr) if g.sym["bz_wcommit"] <= o < g.sym["bz_wcore"]]
    assert len(site_wc) == 1, "bz_ldrw's writers: %s (bz_wcommit's must be one of them)" % wr
    A = {n: g.a(n) for n in ("bz_presented", "bz_wcommit", "bz_tw", "bz_tv", "bz_tf", "bz_vr.rose", "bz_vr.high",
                             "bz_wnow")}
    # bz_wnow's entry: the instruction after the clock sample a commit's TEST is made on (bz_wtest's, bz_lead's)
    # - where the calibration's span starts too, so (5) times what the price covers (the review of wave 3b, C5)
    logged = [A["bz_tw"], A["bz_tv"], A["bz_tf"], A["bz_vr.rose"], A["bz_vr.high"], wc + 1, wc + 2, wc + 5, wc + 8,
              A["bz_wnow"]]
    Wc, H = BB.CARDS[tag == "herc"][:2]
    st = {"pr": None, "holds": {}, "enter": []}

    def on_hit(mm, rec):
        a, r = rec["addr"], rec.get("regs") or {}
        if a in wa:
            lane = r["bx"] & 0xFF
            return {"lane": lane, "new": r["ax"] & 0xFF, "old": mm.read(g.a("bz_ldrw") + lane, 1)[0],
                    "site": wa.index(a)}
        if a == A["bz_wcommit"]:
            return commit_snap(g, r)
        # bz_presented
        out = pres_snap(g)
        prev = st["pr"]
        # (9): a lane brought onto the glass by an entering strip shows its TRUE pose
        st["enter"] += enter_check(g, ref, prev, out, rects, recs)
        st["pr"] = out
        # a frame made LATE on purpose: the NEXT frame's bz_t0 spins (SPEC.md 128.12.5.6)
        f = out["frames"] + 1
        if f >= HOLD_FROM and f % HOLD_EVERY == 0:
            v = HOLD_VALS[(f // HOLD_EVERY) % len(HOLD_VALS)]
            g.putb("bz_hold", v)
            st["holds"][f] = v
        return out

    launch_mill(g, "KeyB", 0)
    stops = wa + [A["bz_wcommit"], A["bz_presented"]]
    with M.bp_trace(m, *(stops + logged), log=logged, regs=True, on_hit=on_hit, cap=BENCH * 60 + 40000) as tr:
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 1, "the MILL benchmark starts", guest=60)
        M.until(m, lambda _: g.b("bz_fs") == 0, "the MILL benchmark's %d frames" % BENCH, guest=600)
        m.pause()
        hits = tr.hits
        assert not tr.overflowed, "the trace overflowed its cap: hits are missing"
        res = {n: g.w(n) for n in ("bz_rwcom", "bz_rwover", "bz_rwlate", "bz_rwlead", "bz_rwskip", "bz_rwtmin",
                                   "bz_rframes")}
        res["trim"] = g.w("bz_trim")
        res["cT"] = struct.unpack("<3H", m.read(g.a("bz_cT"), 6))
        res["cal"] = (g.w("bz_wlw"), g.w("bz_wcw"), g.w("bz_warr"))
        m.run()
    R.dropped(g, "the MILL benchmark")
    return judge_bench(g, ref, hits, res, st, A, wa, site_wc[0], wc, rects, recs, rotors, H, Wc)


def commit_checks(g, frames, rises, held, rects, H, Wc, fails):
    """(3) the beam, (5) the cost, (6) the cells, (11) the lead over a leg's commits (FRAMES as
    judge_bench groups them): -> (beam, under-the-beam count, cost by lane width, leads by frame)"""
    tag = g.tag
    lsh, rl = LSH[tag], R.RL[tag]
    beam, nbad3, cost, leads = [], 0, {2: [], 3: []}, {}
    for fi, fr in enumerate(frames):
        for cm in fr["commits"]:
            kind = cm.get("kind", "?")
            lane = cm.get("lane")
            if lane not in rects:
                fails.append("(1) frame %d: a commit of %r, not a lane" % (fi + 1, lane))
                continue
            q = lane_cells(rects, lane, lsh)
            # (6)
            sh, en = allowed(cm, q, H, Wc)
            want = cells(sh) | cells(en)
            got = cells(cm["lra"]) | cells(cm["lrb"])
            if got != want:
                fails.append("(6) frame %d: the %s commit of lane %d writes cells %s outside the shown window and "
                             "rule 1's row cells, and leaves %s out (window R0 %d c0 %d, step %+d,%+d)" % (
                                 fi + 1, kind, lane, sorted(got - want)[:4], sorted(want - got)[:4], cm["R0"], cm["c0"],
                                 cm["dr"], cm["dc"]))
            # (11)
            if kind == "lead":
                leads[fi] = leads.get(fi, 0) + 1
                if cm["wld"] != lane + 1 or cm["heavy"]:
                    fails.append("(11) frame %d: a LEAD of lane %d, the wait marked %d, the frame heavy %d" % (
                        fi + 1, lane, cm["wld"] - 1, cm["heavy"]))
            if kind not in ("ahead", "behind", "lead"):
                fails.append("(3) frame %d: a commit returning to %s, neither the wheel's two passes nor the lead"
                             % (fi + 1, kind))
                continue
            if held(fr) and kind != "lead":
                fails.append("(3) frame %d: a %s commit of lane %d on a frame made LATE by bz_hold %d: the wheel "
                             "must skip a frame past its first sync" % (fi + 1, kind, lane, held(fr)))
            wcx = cm["wcore"]
            # (5) its calibrated cost against its span: the commit's OWN cost' (its slot's, bz_wcst, read at
            # bz_wcommit), the trim apart - bz_lcf's for a whole lane, the model's otherwise (SPEC.md 128.13.5.2)
            if 1 in wcx and 8 in wcx:
                lines_ = sum(((r[1] - r[0]) << lsh) * 1 for r in (cm["lra"], cm["lrb"]) if r[1] > r[0] and r[3] > r[2])
                cst = cm["wcst"] * 4 * (cm["trim"] / 100.0 if cm["trim"] < 100 else 1.0)
                # from the TEST's clock sample (bz_wnow's entry before the commit) to the closing one, as the
                # calibration times it (bz_wspan: sample, bz_wnow, bz_wload, bz_wcore) - not CLI to POPF, which
                # leaves out the reckoning and the slot copy every price carries (about 1.1 - 1.3k clk)
                now = cm.get("now")
                span = wcx[8] - now if now is not None and now < wcx[1] else wcx[8] - wcx[1]
                wd = rects[lane][2]
                whole = tuple(cm["lra"]) == q and not cells(cm["lrb"])     # (bz_lwhole: priced from bz_lcf)
                pspan = wcx[5] - wcx[2] if 2 in wcx and 5 in wcx else None
                cost.setdefault(wd, []).append((fi + 1, lane, span, cst, lines_, whole, pspan))
            # (3) the beam: the pass, bz_wcore + 2 to + 5
            if 2 not in wcx or 5 not in wcx:
                continue
            s, e = wcx[2], wcx[5]
            top = cm["R0"] * rl
            l0, l1 = max(q[0] << lsh, top), min(q[1] << lsh, top + 200)
            if l1 <= l0 or not cells(sh):
                continue                            # nothing on the glass: the slack's cells alone
            F, L = l0 - top, l1 - 1 - top
            rise = rises.at(s)
            if rise is None:
                continue
            ln, b0 = LINE[tag], TO0[tag]
            ahead_m = (rise - SPIN_TOL + (b0 + F) * ln) - e
            behind_m = s - (rise + (b0 + L + 1) * ln)
            nxt = (rise + rises.P + (b0 + F) * ln) - e
            ok = ahead_m >= 0 or (behind_m >= 0 and nxt >= 0)
            beam.append((fi + 1, kind, lane, F, L, ahead_m, behind_m, ok))
            if not ok:
                nbad3 += 1
                if tag == "cga" and nbad3 <= 4:
                    fails.append("(3) frame %d: the %s commit of lane %d wrote window lines %d - %d UNDER the beam: "
                                 "it ended %d clk after the beam reached line %d, began %d clk before it passed "
                                 "line %d" % (fi + 1, kind, lane, F, L, -ahead_m, F, -behind_m, L))
        if leads.get(fi, 0) > 1:
            fails.append("(11) frame %d: %d LEADs, one a frame at most" % (fi + 1, leads[fi]))
    return beam, nbad3, cost, leads

PASS_PRED = {("cga", 3): 7000, ("herc", 3): 7000, ("cga", 2): 5100, ("herc", 2): 5100}
                               # 128.13.5.1 (128.13.14 item 6): a whole rotor's (3 x 3) and post's (2 x 3: MILL's
                               # shape) pass, PREDICTED clk


def cost_checks(cost, tag, fails, rep, label=""):
    """(5) with wave 3b's model (SPEC.md 128.13.5.2, 128.13.12): each commit's
    OWN cost' (its slot's bz_wcst, the trim apart) against its span from the
    TEST's clock sample (bz_wnow's entry) to the closing one, what the
    calibration times and so what the price covers - a WHOLE-LANE commit's (bz_lcf's price) within CAL_TOL of its
    span, a CLIPPED commit's span at most (1 + CAL_TOL) times its cost - both
    ASSERTED on the CGA, the ratios REPORTED by kind; a commit priced at
    NOTHING fails on either; and each kind's PASS span (bz_wcore + 2 to + 5)
    REPORTED against 128.13.5.1's prediction"""
    for wd in sorted(cost):
        xs = cost[wd]
        if not xs:
            continue
        kind = {2: "post", 3: "rotor"}.get(wd, "%d-word" % wd)
        for whole in (True, False):
            ys = [x for x in xs if x[5] == whole]
            if not ys:
                continue
            free = [x for x in ys if not x[3]]
            rs = [x[2] / float(x[3]) for x in ys if x[3]]
            if whole:
                off = [x for x in ys if x[3] and abs(x[2] / float(x[3]) - 1) > CAL_TOL]
            else:
                off = [x for x in ys if x[3] and x[2] > (1 + CAL_TOL) * x[3]]
            rep.append("(5)%s %s commits, %s: %d, span / its cost' %s, %d %s, %d priced at nothing" % (
                label, kind, "WHOLE (bz_lcf)" if whole else "CLIPPED (the model)", len(ys),
                "%.3f - %.3f (mean %.3f)" % (min(rs), max(rs), sum(rs) / len(rs)) if rs else "-", len(off),
                "past %.0f%%" % (100 * CAL_TOL) if whole else "over %.2f x" % (1 + CAL_TOL), len(free)))
            for x in free[:3]:
                fails.append("(5)%s frame %d lane %d: a %s commit priced at NOTHING (its cost' 0) against its span "
                             "%d clk" % (label, x[0], x[1], "whole" if whole else "clipped", x[2]))
            if tag == "cga":
                for x in off[:3]:
                    fails.append("(5)%s frame %d lane %d: a %s commit's span %d clk, its cost' %d clk (%d lines): "
                                 "%.1f%% %s" % (label, x[0], x[1], "whole" if whole else "clipped", x[2], x[3], x[4],
                                                100 * (x[2] / float(x[3]) - 1),
                                                "off" if whole else "over its price"))
        ps = [x[6] for x in xs if x[5] and x[6]]
        if ps:
            rep.append("(5)%s a whole %s's PASS (bz_wcore + 2 to + 5): %d commits, mean %.0f clk, %d - %d "
                       "(PREDICTED about %d, SPEC.md 128.13.5.1)" % (label, kind, len(ps), sum(ps) / float(len(ps)),
                                                                     min(ps), max(ps), PASS_PRED.get((tag, wd), 0)))


def judge_bench(g, ref, hits, res, st, A, wa, wsite, wc, rects, recs, rotors, H, Wc):
    tag = g.tag
    lsh = LSH[tag]
    fails, rep = [], []
    rises = Rises([h["cycles"] for h in hits if h["addr"] == A["bz_vr.rose"]], tag)
    frames, cur, pend = [], {"commits": [], "writes": [], "vr": []}, None
    last_now = None
    for h in hits:
        a, c, d = h["addr"], h["cycles"], h.get("hit")
        if a == A["bz_tw"]:
            cur["tw"] = c
        elif a == A["bz_tv"]:
            cur["tv"] = c
        elif a == A["bz_tf"]:
            cur["tf"] = c
        elif a in (A["bz_vr.rose"], A["bz_vr.high"]):
            cur["vr"].append(("rose" if a == A["bz_vr.rose"] else "high", c))
        elif a == A.get("bz_wnow"):
            last_now = c
        elif a == A["bz_wcommit"]:
            pend = dict(d or {}, c=c, wcore={}, now=last_now)
            cur["commits"].append(pend)
        elif a in (wc + 1, wc + 2, wc + 5, wc + 8):
            if pend is not None and (a - wc) not in pend["wcore"]:
                pend["wcore"][a - wc] = c
        elif a in wa:
            wd = dict(d or {}, c=c)
            cur["writes"].append(wd)
            if wd.get("site") == wsite and pend is not None:
                pend["ldrw"] = wd
        elif a == A["bz_presented"]:
            cur["pr"], cur["prc"] = d, c
            frames.append(cur)
            cur, pend = {"commits": [], "writes": [], "vr": []}, None

    def held(fr):
        """the bz_hold value FR was made late by, or None: the hold poked at the
        last frame's bz_presented spins at THIS frame's bz_t0, and this frame's
        bz_presented reads bz_frames = that frame's + 1, the key st["holds"]
        was banked under (never the list index: the trace may start earlier)"""
        pr = fr.get("pr")
        return st["holds"].get(pr["frames"]) if pr else None

    # (1) every write changes; every commit makes one
    nw = nsame = 0
    for fi, fr in enumerate(frames):
        for wd in fr["writes"]:
            nw += 1
            if wd.get("new") == wd.get("old"):
                nsame += 1
                if nsame <= 3:
                    fails.append("(1) frame %d: a write of pose %d over bz_ldrw[%d] = %d, NO change (at %s)" % (
                        fi + 1, wd["new"], wd["lane"], wd["old"], "bz_wcommit" if wd["site"] == wsite else "bz_lsync"))
        for cm in fr["commits"]:
            if "ldrw" not in cm:
                fails.append("(1) frame %d: a %s commit of lane %d wrote no bz_ldrw" % (fi + 1, cm.get("kind"),
                                                                                       cm.get("lane", -1)))
    ncom = sum(len(fr["commits"]) for fr in frames)
    rep.append("(1) %d writes to bz_ldrw, %d without a change; %d commits, each with its write: %s" % (
        nw, nsame, ncom, "yes" if all("ldrw" in cm for fr in frames for cm in fr["commits"]) else "NO"))
    # (2) drawn never ahead; bz_wlate 0
    nah, nj = 0, 0
    for fi, fr in enumerate(frames):
        pr = fr.get("pr")
        if not pr:
            continue
        for i in rotors:
            q = lane_cells(rects, i, lsh)
            if not cells(clip(q, (pr["R0"], pr["R0"] + H, pr["c0"], pr["c0"] + Wc))) or i >= len(pr["drawn"]):
                continue
            nj += 1
            ah, back, on = ahead_of(recs[i], pr["drawn"][i], pr["nstep"] - 1)
            if ah:
                nah += 1
                if nah <= 3:
                    fails.append("(2) frame %d: rotor %d drawn at pose %d, AHEAD of the true %d (reached %d steps on, "
                                 "last true %d steps back)" % (fi + 1, i, pr["drawn"][i],
                                                               rotor_pose(recs[i], pr["nstep"] - 1), on, back))
    if res["bz_rwlate"]:
        fails.append("(2) bz_wlate %d: a lane due and shown for 8 frames (SPEC.md 128.12.5.2)" % res["bz_rwlate"])
    rep.append("(2) %d shown-rotor frames judged, %d ahead; bz_wlate %d" % (nj, nah, res["bz_rwlate"]))
    # (3) the beam, (5) the cost, (6) the cells, (11) the lead
    beam, nbad3, cost, leads = commit_checks(g, frames, rises, held, rects, H, Wc, fails)
    for fi, fr in enumerate(frames):
        if fr.get("pr") and fi > 0 and frames[fi - 1].get("pr"):
            dsk = fr["pr"]["wskip"] - frames[fi - 1]["pr"]["wskip"]
            if held(fr) and fr["pr"]["wcn"] and dsk < 1:
                fails.append("(3) frame %d: made late by bz_hold %d with %d candidates, and bz_wskip did not count it"
                             % (fi + 1, held(fr), fr["pr"]["wcn"]))
    hc = sum(1 for fr in frames if held(fr) and fr["pr"]["wcn"])
    if not hc:
        fails.append("(3) no frame made late by bz_hold had a wheel candidate: the skip was never judged")
    nb = len(beam)
    rep.append("(3) %d commits with lines on the glass judged against the cycle counter (the refresh %.1f clk from "
               "%d rises), %d under the beam%s; %d frames made late by bz_hold, %d of them with candidates" % (
                   nb, rises.P, len(rises.c), nbad3, " (the Hercules: REPORTED, SPEC.md 128.12.15 item 5)"
                   if tag == "herc" else "", len(st["holds"]), hc))
    for b in [x for x in beam if not x[7]][:6] + beam[:3]:
        rep.append("    frame %d %s lane %d lines %d-%d: ahead by %d clk, behind by %d clk: %s" % (
            b[0], b[1], b[2], b[3], b[4], b[5], b[6], "clear" if b[7] else "UNDER THE BEAM"))
    # (4)
    if res["bz_rwover"]:
        fails.append("(4) bz_wover %d: a commit ended past its deadline (the calibration or BZ_WMARG is wrong)"
                     % res["bz_rwover"])
    nhigh = 0
    for fi, fr in enumerate(frames):
        if [cm for cm in fr["commits"] if cm.get("kind") in ("ahead", "behind")] and fr["vr"] and \
                fr["vr"][0][0] != "rose" and not held(fr):
            nhigh += 1
            if nhigh <= 3:
                fails.append("(4) frame %d: the wait after its wait commits found the sync already HIGH" % (fi + 1))
    rep.append("(4) bz_wover %d; frames whose wait after wait commits found the sync high: %d" % (
        res["bz_rwover"], nhigh))
    # (5)
    cost_checks(cost, tag, fails, rep)
    rep.append("(5) the calibration: T1, T3, T3n %s counts -> wlw %d, wcw %d, warr %d" % ((res["cT"],) + res["cal"]))
    # (7) each shown rotor's pose rate
    rated = 0
    for i in rotors:
        seg = drawn_ch = true_ch = 0
        last = None
        for fr in frames:
            pr = fr.get("pr")
            if not pr or i >= len(pr["drawn"]):
                last = None
                continue
            q = lane_cells(rects, i, lsh)
            shown = bool(cells(clip(q, (pr["R0"], pr["R0"] + H, pr["c0"], pr["c0"] + Wc))))
            if not shown:
                last = None
                continue
            if last is None:
                seg += 1
            else:
                drawn_ch += pr["drawn"][i] != last[0]
                true_ch += sum(1 for k in range(last[1], pr["nstep"])
                               if rotor_pose(recs[i], k) != rotor_pose(recs[i], k - 1))
            last = (pr["drawn"][i], pr["nstep"])
        rep.append("(7) rotor %d: shown in %d spells, its drawn pose changed %d times, its true pose %d" % (
            i, seg, drawn_ch, true_ch))
        rated += true_ch > 0
        if true_ch and (drawn_ch < RATE_MIN * true_ch - seg or drawn_ch > true_ch + seg):
            fails.append("(7) rotor %d: its drawn pose changed %d times while shown, its true pose %d (at least %.0f%% "
                         "and never more, a carry-in a spell)" % (i, drawn_ch, true_ch, 100 * RATE_MIN))
    if not rated:
        fails.append("(7) no rotor was shown long enough to judge its rate")
    # (8)
    if res["trim"] != 100:
        fails.append("(8) the trim %d at the leg's end, not 100 (its lowest %d)" % (res["trim"], res["bz_rwtmin"]))
    rep.append("(8) the trim %d at the end, its lowest %d" % (res["trim"], res["bz_rwtmin"]))
    # (9)
    ent = st["enter"]
    for e in ent:
        if e[4]:
            fails.append("(9) frame %d: lane %d brought in by a strip shows %d px that are not its TRUE pose %d "
                         "(its bz_ldrw %s)" % (e[0], e[1], e[4], e[2], e[3]))
    if not ent:
        fails.append("(9) no lane entered the window from wholly outside it: the strip's pose was never judged")
    rep.append("(9) lanes brought in by a strip: %d, %d of them wrong (%s)" % (
        len(ent), sum(1 for e in ent if e[4]), ", ".join("frame %d lane %d" % e[:2] for e in ent[:6])))
    # (12) the owner's preview, tightened: a kicked post LIGHTS on its kick's frame, stays lit, goes dark
    post_checks(frames, rects, recs, lsh, H, Wc, fails, rep)
    # (13) the walk's skip: each rotor's bz_lnext
    lnext_check(frames, recs, fails, rep)
    # (11)
    rep.append("(11) LEADs %d (bz_wlead %d) on %d frames, none on a heavy frame or for an unmarked lane: %s" % (
        sum(leads.values()), res["bz_rwlead"], len(leads),
        "yes" if not [f for f in fails if f.startswith("(11)")] else "NO"))
    rep.append("the results: %d frames, commits %d, overruns %d, late %d, leads %d, skips %d, the trim's lowest %d" % (
        res["bz_rframes"], res["bz_rwcom"], res["bz_rwover"], res["bz_rwlate"], res["bz_rwlead"], res["bz_rwskip"],
        res["bz_rwtmin"]))
    if res["bz_rwcom"] != ncom:
        fails.append("(1) the results count %d commits, the breakpoints %d" % (res["bz_rwcom"], ncom))
    return fails, rep, {"beam": beam, "cost": cost}


# ---- the LOW leg: bonanza_ring's LOW SCENARIO, AHEAD of the beam and the LEAD ----
# THE BEAM SWEEP (SPEC.md 128.13.7 item 2), after the LOW cycles: every SWEEP_CYCLE frames the LOW post is
# KICKED (bz_pkick + 1: it lights as the frame's must-draw), and on the frame after, at bz_t0, its lit frames
# are poked to 0 (true dark, drawn lit: DUE, a wheel candidate) and [bz_hold] set to the sweep's next value -
# SWEEP_HOLD (x 256 PIT counts: a spin of 24.6k - 41k clk in bz_t0), so bz_tw falls about 52 - 69k clk after
# the rise and the beam (window lines 133 - 189) crosses the post's 160 - 175 while the wheel decides.  The
# right build commits after the beam or leaves the lane; `nobeam` commits under it: (3).  The rest of the
# cycle leaves the post room to go dark (BZ_WPRF + 1) before the next kick: (12)
SWEEP_HOLD = tuple(range(24, 41))   # 17 due frames
SWEEP_CYCLE = 8
SWEEP_MIN = 15                      # sweep frames on which the post must be a wheel candidate (at bz_tw)


def sweep_poke(g, lane, k0, k):
    """the BEAM SWEEP's pokes at the LOW leg's K-th bz_t0 (its first at K0): ->
    ('kick', j), ('due', j) or None"""
    if k < k0:
        return None
    j, r = divmod(k - k0, SWEEP_CYCLE)
    if j >= len(SWEEP_HOLD):
        return None
    if r == 0:
        a = g.a("bz_pkick") + 2 * lane
        n = struct.unpack("<H", g.m.read(a, 2))[0]
        g.m.write(a, struct.pack("<H", (n + 1) & 0xFFFF))     # a kick (128.13.14 item 10)
        return ("kick", j)
    if r == 1:
        g.m.write(g.a("bz_lhold") + lane, b"\0")              # its lit frames out: DUE
        g.putb("bz_hold", SWEEP_HOLD[j])                       # ...and the frame late by the sweep's value
        return ("due", j)
    return None


def low_leg(g, ref):
    """bonanza_ring.low_plan / low_poke on MILL in play mode (the heavy rule on): a post low in a centred
    window, lit and gone dark every LOW_CYCLE frames - the dark frame starts late after the lit box (the
    CGA's LEAD, the Hercules's BEHIND), and every other cycle it is held past the wheel's room, so the
    next, light frame commits AHEAD - each commit judged as the benchmark's are: (3), (5), (6), (11).  MILL's
    route gives neither an AHEAD commit nor a 2-word one on the CGA (its lanes high in the window, its frames
    heavy: the final pass).  Then THE BEAM SWEEP (SWEEP_HOLD): at least SWEEP_MIN of its due frames have the
    post a wheel candidate at bz_tw, ASSERTED; their commits judged by (3); and (12) over the whole leg -
    every kick lit on its frame, every post whose lit frames ran out drawn dark in time.
    -> (failures, reports, {"beam", "cost"})"""
    m, tag, crs = g.m, g.tag, ref.c
    lsh = LSH[tag]
    rects = R.lane_rects(crs)
    recs = {r["i"]: r for r in crs.part["props"]}
    wc = g.a("bz_wcore")
    A = {n: g.a(n) for n in ("bz_t0", "bz_tw", "bz_presented", "bz_wcommit", "bz_vr.rose", "bz_vr.high",
                             "bz_wnow")}
    # bz_wnow logged as the benchmark's is: (5) times a commit from its TEST's clock sample, what the price
    # covers - without it the span fell back to CLI .. POPF and every LOW post read ~16% under its price
    logged = [A["bz_vr.rose"], A["bz_vr.high"], wc + 1, wc + 2, wc + 5, wc + 8, A["bz_wnow"]]
    Wc, H = BB.CARDS[tag == "herc"][:2]
    k0 = R.LOW_FRAMES
    st = {"k": -1, "plan": None, "what": {}, "sweep": {}, "cand": {}}
    nfr = k0 + SWEEP_CYCLE * len(SWEEP_HOLD) + 2
    launch_mill(g, "Enter", 0)
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the MILL play runs", guest=60)
    m.pause()
    st["plan"] = R.low_plan(g, crs)             # (before the trace: its predicate must never see k 0 unplanned)

    def on_hit(mm, rec):
        a, r = rec["addr"], rec.get("regs") or {}
        if a == A["bz_t0"]:
            st["k"] += 1
            if st["plan"]:
                w = R.low_poke(g, st["plan"], st["k"])
                if w:
                    st["what"][st["k"]] = w
                s = sweep_poke(g, st["plan"][0], k0, st["k"])
                if s:
                    st["sweep"][st["k"]] = s
            return {"k": st["k"]}
        if a == A["bz_tw"]:                     # the wheel's candidates, as it starts
            n = g.b("bz_wcn")
            st["cand"][st["k"]] = list(mm.read(g.a("bz_wcl"), n)) if n else []
            return None
        if a == A["bz_wcommit"]:
            return commit_snap(g, r)
        out = pres_snap(g)
        out["k"] = st["k"]
        return out
    stops = [A["bz_t0"], A["bz_tw"], A["bz_wcommit"], A["bz_presented"]]
    with M.bp_trace(m, *(stops + logged), log=logged, regs=True, on_hit=on_hit, cap=40000) as tr:
        m.run()
        M.until(m, lambda _: st["k"] >= nfr or not st["plan"], "the LOW scenario's frames and the BEAM sweep",
                guest=120)
        m.pause()
        hits = tr.hits
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the LOW leg's play ends on Esc", guest=60)
    R.dropped(g, "the LOW leg")
    if not st["plan"]:
        return ["(3) the LOW leg found no post a centred window puts at line %d" % R.LOW_F], [], \
            {"beam": [], "cost": {2: [], 3: []}}
    lane = st["plan"][0]
    rises = Rises([h["cycles"] for h in hits if h["addr"] == A["bz_vr.rose"]], tag)
    frames, cur, pend = [], {"commits": [], "vr": []}, None
    last_now = None
    for h in hits:
        a, c, d = h["addr"], h["cycles"], h.get("hit")
        if a in (A["bz_vr.rose"], A["bz_vr.high"]):
            cur["vr"].append(("rose" if a == A["bz_vr.rose"] else "high", c))
        elif a == A["bz_wnow"]:
            last_now = c
        elif a == A["bz_wcommit"]:
            pend = dict(d or {}, c=c, wcore={}, now=last_now)
            cur["commits"].append(pend)
        elif a in (wc + 1, wc + 2, wc + 5, wc + 8):
            if pend is not None and (a - wc) not in pend["wcore"]:
                pend["wcore"][a - wc] = c
        elif a == A["bz_presented"]:
            cur["pr"] = d
            frames.append(cur)
            cur, pend = {"commits": [], "vr": []}, None
    fails, rep = [], []
    beam, nbad3, cost, leads = commit_checks(g, frames, rises, lambda fr: None, rects, H, Wc, fails)
    kinds = {}
    for fr in frames:
        for cm in fr["commits"]:
            kinds[cm.get("kind")] = kinds.get(cm.get("kind"), 0) + 1
    rep.append("(3) the LOW leg: post %d at window line %d, %d cycles (%s): commits %s; %d with lines on the glass "
               "judged against the cycle counter, %d under the beam%s" % (
                   lane, R.LOW_F, R.LOW_CYCLES, ", ".join("%d %s" % (k_, w_) for k_, w_ in
                                                          sorted(st["what"].items())[:4]) + " ...",
                   ", ".join("%s %d" % kv for kv in sorted(kinds.items())) or "none", len(beam), nbad3,
                   " (the Hercules: REPORTED)" if tag == "herc" else ""))
    for b in [x for x in beam if not x[7]][:4] + beam[:4]:
        rep.append("    LOW frame %d %s lane %d lines %d-%d: ahead by %d clk, behind by %d clk: %s" % (
            b[0], b[1], b[2], b[3], b[4], b[5], b[6], "clear" if b[7] else "UNDER THE BEAM"))
    # THE BEAM SWEEP: the post a candidate on its due frames, and what the wheel did with it
    due = sorted(k for k, s in st["sweep"].items() if s[0] == "due")
    cand = [k for k in due if lane in st["cand"].get(k, ())]
    kof = {fr["pr"]["k"]: fi for fi, fr in enumerate(frames) if fr.get("pr")}
    sw = []
    for k in due:
        fi = kof.get(k)
        cms = [cm for cm in frames[fi]["commits"] if cm.get("lane") == lane] if fi is not None else []
        sw.append("%d:%s" % (SWEEP_HOLD[st["sweep"][k][1]], cms[0]["kind"] if cms else "left"))
    rep.append("(3) the BEAM sweep: %d due frames (bz_hold %d - %d x 256 counts), the post a wheel candidate at bz_tw "
               "on %d (at least %d); the wheel's answer by hold: %s" % (
                   len(due), SWEEP_HOLD[0], SWEEP_HOLD[-1], len(cand), SWEEP_MIN, " ".join(sw)))
    if len(cand) < SWEEP_MIN:
        fails.append("(3) the BEAM sweep: the post a wheel candidate on %d of its %d due frames, at least %d "
                     "asserted (SPEC.md 128.13.7 item 2): the beam was never put in front of the wheel" % (
                         len(cand), len(due), SWEEP_MIN))
    cost_checks(cost, tag, fails, rep, " the LOW leg's")
    post_checks(frames, rects, recs, lsh, H, Wc, fails, rep, " the LOW leg:", cuts=True)
    rep.append("(11) the LOW leg's LEADs %d, none on a heavy frame or for an unmarked lane: %s" % (
        sum(leads.values()), "yes" if not [f for f in fails if f.startswith("(11)")] else "NO"))
    return fails, rep, {"beam": beam, "cost": cost}


# ---- the CORNER leg: a LIGHT down-and-left step across a lane at the bottom-left ---
def corner_leg(g, ref):
    """the corner leg on a LIGHT diagonal step (SPEC.md 128.13.7 item 5, 128.13.14
    item 9): TRICKLE ([bz_cmode] 1: wave 0's camera steps a row and a column on
    the frame the ball crosses the band's foot and the dead zone's edge, and
    nothing before); the centred full write, the ball HELD at the window's
    centre; then poked to just inside the dead zone's left (right) edge and the
    band's foot (that frame two ball boxes); HELD there one frame (no box: the
    step frame's predecessor writes nothing after the rise); then moved 2 px
    across both, in its cell (no refill) - so the step frame takes one row
    before its wait and the column after it, with the lane made due on it (its
    [bz_ldrw] poked one pose on).  -> (failures, reports)"""
    m, tag, crs = g.m, g.tag, ref.c
    lsh, rl = LSH[tag], R.RL[tag]
    recs = {r["i"]: r for r in crs.part["props"]}
    rects = R.lane_rects(crs)
    grid = BB.Grid(crs.cga)
    fails, rep = [], []
    launch_mill(g, "Enter", 0)
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the MILL play runs", guest=60)
    m.pause()
    g.putb("bz_cmode", 1)                         # TRICKLE (it persists: put back at the leg's end)
    H, Wc, rmax, cmax = g.w("bz_H"), g.w("bz_W"), g.w("bz_rmax"), g.w("bz_cmax")
    L = 200                                       # bzvideo.inc BZ_LINES
    plan = None
    # a rotor first, then a POST (a 2-word lane made due the same way: drawn lit over a true dark, due
    # and not a lighting must-draw); the bottom-LEFT corner first, else its mirror, the bottom-RIGHT,
    # where the step is down and right and the entering column on the right (rule 1's same exclusion)
    for side in (-1, 1):
        for i in sorted(rects, key=lambda j: (recs[j]["kind"] != BB.PK_WINDMILL, j)):
            if recs[i]["kind"] not in (BB.PK_WINDMILL, BB.PK_BUMPER):
                continue
            q = lane_cells(rects, i, lsh)
            # the window's bottom edge through the lane's middle row, its left (right) edge one word
            # inside the lane: the down step brings in the lane's next row, the side step its column
            c0 = q[2] + 1 if side < 0 else q[3] - 1 - Wc
            R0 = q[0] + (q[1] - q[0]) // 2 - H
            if not (0 <= R0 <= rmax - 1 and (1 <= c0 <= cmax if side < 0 else 0 <= c0 <= cmax - 1)):
                continue
            top, left = R0 << lsh, 8 * c0
            cen = hold = None
            for dy in range(rl):                  # the centred full write's window: R0, c0 exactly
                for dx in range(8):
                    cen = cen or R.probe_ground(crs, left + 4 * Wc - 8 + dx, top + 92 + dy, grid, 1, clear=16,
                                                flags=BB.FL_OCC | BB.FL_OCCG)
            # HELD on the band's foot and the dead zone's edge exactly: the ball's centre line 2L/3
            # below the window's top (TRICKLE steps down past it), its centre px 2 W words in (6 W on
            # the right: it steps past them), drifting the way the step goes (in its cell)
            hx = left + 2 * Wc - 8 if side < 0 else left + 6 * Wc - 8
            hold = R.probe_ground(crs, hx, top + 2 * L // 3 - 8, grid, side, clear=8,
                                  flags=BB.FL_OCC | BB.FL_OCCG)
            if cen and hold:
                plan = (i, R0, c0, cen, hold, side)
                break
        if plan:
            break
    if plan is None:
        g.putb("bz_cmode", 0)
        m.run()
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0, "the corner leg's play ends on Esc", guest=60)
        R.dropped(g, "the corner leg")
        why = ("(6) the corner leg found no rotor or post it can put across the window's bottom-left or "
               "bottom-right corner (H %d, W %d, rmax %d, cmax %d)" % (H, Wc, rmax, cmax))
        if tag == "herc":                         # the Hercules's 45-word window: cmax 19 against MILL's lanes in
            return [], [why + ": REPORTED - no window on this card can (SPEC.md 128.12.13.2)"]   # columns 21 - 35
        return [why], rep
    lane, R0w, c0w, cen, hold, side = plan
    # the step: 2 px down and 2 px across, gx - gy by 2 px and gz 2 px lower - the drift
    # probe_ground left room for, so the poke stays in the cell (same_cell: no refill)
    stp = (hold[0] + 256 * side, hold[1] - 256 * side, hold[2] - 512)
    q = lane_cells(rects, lane, lsh)
    wc = g.a("bz_wcore")
    code = m.read(wc, 10)
    assert (code[0], code[1], code[2], code[5], code[8], code[9]) == (0x9C, 0xFA, 0xE8, 0xE8, 0x9D, 0xC3), \
        "bz_wcore is not PUSHF CLI CALL(bz_wpass) CALL(bz_clk_sample) POPF RET (SPEC.md 128.13.12): %s" % code.hex()
    A = {n: g.a(n) for n in ("bz_t0", "bz_wcommit", "bz_tw", "bz_vr.rose")}
    vb, vn = VRAM[tag]
    STEP = CORNER_STEP + 2                        # centred (1 - 3), the poke (4), held (5), the step (6)
    judged, tries, tws_seen = [], 0, []
    while tries < CORNER_TRIES and not judged:
        tries += 1
        fr = {"step": 0}
        got = []

        def on_hit(mm, rec):
            a, r = rec["addr"], rec.get("regs") or {}
            if a == A["bz_t0"]:
                fr["step"] += 1
                k = fr["step"]
                if k < CORNER_STEP:               # centred: a full write (its frame is the one after the
                    R.poke_ball(g, cen[0], cen[1], cen[2], 0, 0, 0, air=1)       # first poke), then held
                    if k == 1:                    # (the frame after a full write has no wheel)
                        g.putb("bz_first", 1)
                elif k == CORNER_STEP:            # on the band's foot and the dead zone's edge: two ball
                    R.poke_ball(g, hold[0], hold[1], hold[2], 0, 0, 0, air=1)     # boxes, no camera step
                elif k == CORNER_STEP + 1:        # HELD: no box
                    R.poke_ball(g, hold[0], hold[1], hold[2], 0, 0, 0, air=1, same_cell=True)
                else:                             # THE STEP: 2 px over both edges, in the cell; the lane
                    R.poke_ball(g, stp[0], stp[1], stp[2], 0, 0, 0, air=1, same_cell=True)  # due on it
                    if k == STEP:
                        pose = mm.read(g.a("bz_ldrw") + lane, 1)[0]
                        mm.write(g.a("bz_ldrw") + lane, bytes([(pose + 1) % recs[lane]["lane"]["poses"]]))
                return {"t0": k}
            if a == A["bz_wcommit"]:
                kind, ln = R.commit_kind(g, r)
                w = Snap(g, WIN)
                h = Snap(g, WHL)
                d = {"kind": kind, "lane": ln, "R0": w.w("bz_R0"), "c0": w.w("bz_c0"), "R0n": w.w("bz_R0n"),
                     "c0n": w.w("bz_c0n"), "dr": w.s("bz_dr"), "dc": w.s("bz_dc"), "step": fr["step"],
                     "lra": struct.unpack("<4h", h.bytes("bz_lra", 8)),
                     "lrb": struct.unpack("<4h", h.bytes("bz_lrb", 8))}
                got.append(d)
                return d
            if a in (wc + 2, wc + 5) and got and "after" not in got[-1]:
                got[-1]["before" if a == wc + 2 else "after"] = mm.read(vb, vn)
            return None
        logged = [A["bz_tw"], A["bz_vr.rose"]]
        with M.bp_trace(m, A["bz_t0"], A["bz_wcommit"], wc + 2, wc + 5, *logged, log=logged, regs=True,
                        on_hit=on_hit, cap=8000) as tr:
            m.run()
            M.until(m, lambda _: fr["step"] >= STEP + 3, "the corner leg's frames", guest=30)
            m.pause()
            hits = tr.hits
        # bz_tw on the step frame, after the sync's last rise before it (the wait it follows)
        t0s = [h["cycles"] for h in hits if h["addr"] == A["bz_t0"]]
        tws = [h["cycles"] for h in hits if h["addr"] == A["bz_tw"]]
        ros = [h["cycles"] for h in hits if h["addr"] == A["bz_vr.rose"]]
        tw_after = None
        if len(t0s) >= STEP:
            c0_, c1_ = t0s[STEP - 1], t0s[STEP] if len(t0s) > STEP else None
            tw = [c for c in tws if c > c0_ and (c1_ is None or c < c1_)]
            if tw:
                rise = [c for c in ros if c <= tw[0]]
                if rise:
                    tw_after = tw[0] - rise[-1]
        tws_seen.append(tw_after)
        step_cm = [d for d in got if d["lane"] == lane and d["step"] == STEP]
        rep.append("(6) corner try %d: the step frame's bz_tw %s clk after the sync's rise (PREDICTED about "
                   "57 - 60k on the CGA, admitted while about 58k or less, SPEC.md 128.13.7 item 5); lane %d's "
                   "commit on it: %s" % (
                       tries, "%d" % tw_after if tw_after is not None else "?", lane,
                       "%s, the window stepping %+d,%+d" % (step_cm[0]["kind"], step_cm[0]["dr"], step_cm[0]["dc"])
                       if step_cm else "NONE"))
        for d in step_cm:
            if judged:
                break
            if not (d["dr"] > 0 and d["dc"] * side > 0):
                rep.append("(6) corner try %d: the step was %+d,%+d, not down and %s" % (
                    tries, d["dr"], d["dc"], "left" if side < 0 else "right"))
                continue
            judged.append(d)
    if not judged:
        msg = ("(6) the corner leg's LIGHT step made no wheel commit of lane %d on a down-and-%s step in %d tries "
               "- the step frame's bz_tw %s clk after the sync's rise (PREDICTED 57 - 60k): the scene is to be made "
               "lighter, never the check weakened, SPEC.md 128.13.14 item 9" % (
                   lane, "left" if side < 0 else "right", tries, ", ".join("?" if x is None else "%d" % x
                                                                           for x in tws_seen)))
        if tag == "herc":
            rep.append(msg + ": REPORTED on the Hercules")
        else:
            fails.append(msg)
    rb = R.RB[tag]
    for d in judged:
        d["kind"] = d["kind"] if d["kind"] == "lead" else "wheel"
        sh, en = allowed(d, q, H, Wc)
        want = cells(sh) | cells(en)
        gotc = cells(tuple(d["lra"])) | cells(tuple(d["lrb"]))
        corner = (d["R0"] + H, d["c0"] - 1 if side < 0 else d["c0"] + Wc)
        ok_rect = gotc == want
        offs = set()
        for (r_, c_) in want:
            o = (rb * r_ + 2 * c_) % 8192
            offs |= {o, (o + 1) % 8192}
        ch = []
        if "before" in d and "after" in d:
            b0, b1 = d["before"], d["after"]
            ch = [k for k in range(len(b0)) if b0[k] != b1[k]]
        stray = [k for k in ch if (k & 0x1FFF) not in offs]
        rep.append("(6) corner: lane %d, the window R0 %d c0 %d stepping %+d,%+d: the commit's cells %d (shown %s, "
                   "entering rows %s), the corner cell %s %s; %d bytes changed on the card, %d outside its cells" % (
                       lane, d["R0"], d["c0"], d["dr"], d["dc"], len(gotc), d["lra"], d["lrb"], corner,
                       "WRITTEN" if corner in gotc else "not written", len(ch), len(stray)))
        if not ok_rect:
            fails.append("(6) corner: the commit of lane %d on the %+d,%+d step writes cells %s outside the shown "
                         "window and rule 1's row cells (the corner %s aliases the old window's last cell), leaves %s "
                         "out" % (lane, d["dr"], d["dc"], sorted(gotc - want)[:4], corner, sorted(want - gotc)[:4]))
        if stray:
            fails.append("(6) corner: the pass changed %d card bytes outside its cells (bank offsets %s)" % (
                len(stray), ["%04X" % k for k in stray[:6]]))
    g.putb("bz_cmode", 0)
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the corner leg's play ends on Esc", guest=60)
    R.dropped(g, "the corner leg")
    return fails, rep


# ---- the STALE leg: (9) on a rotor brought in by a row after its pose changed off the glass ----
STALE_STEPS = 16                # steps after the full write before the row (its true pose changed off screen)
STALE_AFTER = 3                 # frames held at the new point after the step
STALE_MAX = 120                 # frames at most waiting for a pose whose lowest row differs from the full write's


def stale_plan(g, ref):
    """-> (rotor, R0, c0, the centre's point, the point just over the band's top), or None: a CENTRED full write
    whose window's top is the rotor's last card row + 1 (wholly above it, its last row R0 - 1)"""
    tag, crs = g.tag, ref.c
    lsh = LSH[tag]
    recs = {r["i"]: r for r in crs.part["props"]}
    rects = R.lane_rects(crs)
    grid = BB.Grid(crs.cga)
    Wc, rmax, cmax = g.w("bz_W"), g.w("bz_rmax"), g.w("bz_cmax")
    rl = R.RL[tag]
    L = 200
    for i in sorted(rects):
        if recs[i]["kind"] != BB.PK_WINDMILL:
            continue
        q = lane_cells(rects, i, lsh)
        R0 = q[1]
        if not 0 <= R0 <= rmax:
            continue
        mid = (q[2] + q[3]) // 2 - Wc // 2
        for c0 in sorted(range(0, cmax + 1), key=lambda c: abs(c - mid)):
            if not (c0 <= q[2] and q[3] <= c0 + Wc):
                continue
            top, left = R0 << lsh, 8 * c0
            cen = up = None
            for dy in range(rl):
                for dx in range(8):
                    cen = cen or R.probe_ground(crs, left + 4 * Wc - 8 + dx, top + 92 + dy, grid, 1, clear=16,
                                                flags=BB.FL_OCC | BB.FL_OCCG)
            # just over the band's TOP edge: the centre line 2 lines above L/3 (TRICKLE steps up past it, one
            # row, and the ball is back inside the band), the centre column as the full write's (no column)
            for dx in range(0, 8):
                up = up or R.probe_ground(crs, left + 4 * Wc - 8 + dx, top + L // 3 - 8 - 2, grid, 1, clear=16,
                                          flags=BB.FL_OCC | BB.FL_OCCG)
            if cen and up:
                return i, R0, c0, cen, up
    return None


def stale_leg(g, ref):
    """THE STALE SCENE (SPEC.md 128.13.7 item 4): [bz_cmode] 1 (TRICKLE); a
    centred full write puts a ROTOR wholly above the window's top (its last
    card row R0 - 1, in the walk's range) with the ball HELD at the centre;
    after STALE_STEPS steps, on a frame whose true pose shows a different
    lowest row from the full write's, the ball is poked just over the band's
    top edge, so the camera steps UP one row and the entering row brings the
    rotor's lowest cells in from the map: (9) judges them (the TRUE pose on the
    card).  `lanestale` leaves the map stale.  Where no window puts a rotor so,
    the leg SKIPS naming the course, and says the arm is unjudged.
    -> (failures, reports)"""
    m, tag, crs = g.m, g.tag, ref.c
    lsh = LSH[tag]
    recs = {r["i"]: r for r in crs.part["props"]}
    rects = R.lane_rects(crs)
    fails, rep = [], []
    launch_mill(g, "Enter", 0)
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the MILL play runs", guest=60)
    m.pause()
    g.putb("bz_cmode", 1)                         # TRICKLE (put back at the leg's end)
    plan = stale_plan(g, ref)
    if plan is None:
        rep.append("(9) the STALE scene: SKIP - no window on this card puts a MILL rotor wholly above its top with "
                   "the ball centred on a floor (the `lanestale` arm is UNJUDGED here)")
    else:
        lane, R0w, c0w, cen, up = plan
        rec = recs[lane]
        q = lane_cells(rects, lane, lsh)
        pics = ref._lanes[lane]["pics"]
        lo = ((q[1] - 1) << lsh) - 8 * rects[lane][1]      # the lowest card row's lines in the lane's picture
        lines = range(lo, lo + R.RL[tag])

        def low_rows(pose):
            return [bytes(pics[pose][y]) for y in lines] if pose in pics else None
        st = {"k": -1, "fw": None, "n0": None, "step": None, "pr": None, "enter": [], "win": []}

        def on_hit(mm, rec_):
            a = rec_["addr"]
            if a == A["bz_t0"]:
                st["k"] += 1
                k = st["k"]
                if st["step"] is None:
                    R.poke_ball(g, cen[0], cen[1], cen[2], 0, 0, 0, air=1, same_cell=k > 0)
                    if k == 0:
                        g.putb("bz_first", 1)     # the NEXT frame is the centred full write
                    elif k == 2:                  # (after it: the pose it drew, and the steps from there)
                        st["fw"] = mm.read(g.a("bz_ldrw") + lane, 1)[0]
                        st["n0"] = g.d("bz_nstep")
                    elif k > 2:
                        n = g.d("bz_nstep")
                        far = [rotor_pose(rec, x) for x in (n - 1, n, n + 1)]
                        if n - st["n0"] >= STALE_STEPS and all(low_rows(p) != low_rows(st["fw"]) for p in far):
                            st["step"] = k        # THE ROW: just over the band's top edge
                            R.poke_ball(g, up[0], up[1], up[2], 0, 0, 0, air=1)
                else:
                    R.poke_ball(g, up[0], up[1], up[2], 0, 0, 0, air=1, same_cell=True)
                return None
            out = pres_snap(g)
            out["k"] = st["k"]
            if st["step"] is not None and st["k"] == st["step"]:
                st["win"].append((st["pr"]["R0"] if st["pr"] else None, out["R0"], st["pr"]["c0"] if st["pr"]
                                  else None, out["c0"]))
                st["enter"] += enter_check(g, ref, st["pr"], out, rects, recs)
            st["pr"] = out
            return None
        A = {n: g.a(n) for n in ("bz_t0", "bz_presented")}
        with M.bp_trace(m, A["bz_t0"], A["bz_presented"], on_hit=on_hit, cap=4000):
            m.run()
            M.until(m, lambda _: (st["step"] is not None and st["k"] >= st["step"] + STALE_AFTER) or
                    st["k"] >= STALE_MAX, "the STALE scene's frames", guest=60)
            m.pause()
        ent = [e for e in st["enter"] if e[1] == lane]
        rep.append("(9) the STALE scene: rotor %d (card rows %d - %d) above a centred window R0 %d c0 %d; the full "
                   "write drew pose %s; the row %s; the window then %s; the rotor brought in by the row: %s" % (
                       lane, q[0], q[1] - 1, R0w, c0w, st["fw"], "on frame %s, %s steps after it" % (
                           st["step"], None if st["n0"] is None else g.d("bz_nstep") - st["n0"])
                       if st["step"] is not None else "NEVER (no pose with a different lowest row)",
                       "R0 %s -> %s, c0 %s -> %s" % st["win"][0] if st["win"] else "-",
                       ", ".join("true pose %d, its bz_ldrw %s, %d px wrong" % (e[2], e[3], e[4]) for e in ent)
                       or "NONE"))
        if not ent:
            fails.append("(9) the STALE scene: rotor %d was not brought onto the glass by an entering row (the "
                         "window %s): the stale map was never judged" % (lane, st["win"] or "never stepped"))
        for e in ent:
            if e[4]:
                fails.append("(9) the STALE scene, frame %d: rotor %d brought in by the row shows %d px that are not "
                             "its TRUE pose %d (its bz_ldrw %s): the map was left stale while it was off the glass"
                             % (e[0], e[1], e[4], e[2], e[3]))
    g.putb("bz_cmode", 0)
    m.run()
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the STALE leg's play ends on Esc", guest=60)
    R.dropped(g, "the STALE leg")
    return fails, rep


# ---- the GATE leg: (10) on the knock and pass replays --------------------------
def gate_leg(g, scen):
    """-> (failures, reports)"""
    m = g.m
    fails, rep = [], []
    crs = R.course("mill")
    recs = {r["i"]: r for r in crs.part["props"]}
    for s in scen:
        log = R.make_log(s["keys"], R.CRS_K["mill"], s["mat"])
        m.pause()
        g.write_log(log)
        wk = R.Walker(g, t0=True)
        m.bp_exec(wk.t0)
        m.run()
        g.key("KeyR")
        assert m.wait_stop(60) == "breakpoint", "R did not start the %s replay" % s["name"]
        pk = s["poke"]
        R.poke_ball(g, pk["gx"], pk["gy"], pk["gz"], pk["gvx"], pk["gvy"], pk["gvz"], air=pk["air"],
                    ztop=pk["ztop"], lvl=pk["lvl"])
        p = P.model("mill", s["mat"], pk)
        wk.arm()
        n0, judged = 0, []
        while True:
            k = wk.next()
            if k == "t0":
                if g.b("bz_goal") or not (g.b("bz_rn") or g.w("bz_rruns")):
                    break
                continue
            if k != "pr":
                continue
            n = g.d("bz_nstep")
            ev = P.advance(p, n, s["keys"])
            drawn = list(m.read(g.a("bz_ldrw"), g.b("bz_nlane")))
            for e in ev:
                if e[0] not in ("knock", "capture") or e[2] not in recs:
                    continue
                W = recs[e[2]]
                c0p, c1p = W["closed"][0] >> W["shift"], W["closed"][1] >> W["shift"]
                dq = drawn[e[2]]
                shut = c0p <= dq < c1p
                want = e[0] == "knock"
                jq = rotor_pose(W, e[1] - 1)
                ok = shut == want
                excuse = (not ok and n - n0 >= 2 and e[1] != n and
                          min((jq - dq) % 8, (dq - jq) % 8) <= 1)
                judged.append((e[0], e[1], n - n0, dq, jq, ok, excuse))
                if not ok and not excuse:
                    fails.append("(10) %s: the %s at step %d (gate %s at its n %d) shows the rotor at pose %d, %s, "
                                 "on the frame of steps %d - %d" % (s["name"], e[0], e[1], "closed" if want else "open",
                                                                    e[1] - 1, dq, "closed" if shut else "open",
                                                                    n0 + 1, n))
            n0 = n
        m.bp_exec()
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 0, "the %s replay ends" % s["name"], guest=60)
        R.dropped(g, s["name"])
        rep.append("(10) %s: %s" % (s["name"], ", ".join(
            "%s@%d (frame of %d steps) drawn %d gate-pose %d %s" % (j[0], j[1], j[2], j[3], j[4],
                                                                    "ok" if j[5] else "one phase off, allowed"
                                                                    if j[6] else "WRONG") for j in judged) or "none"))
        if not judged:
            fails.append("(10) %s: no knock-back or capture to judge" % s["name"])
    return fails, rep


def gate_scen():
    return [s for s in P.mill_replays() if s["name"] in ("knock", "pass")]


LEGS = ("bench", "low", "corner", "stale", "gate")


def run(tag, legs=LEGS, apps=None, src=None):
    fails, rep = [], []
    booted, sym = boot_pkg(tag, apps, src)
    wr = writers(src, sym=sym) if "bench" in legs else None
    scen = gate_scen() if "gate" in legs else None
    with booted as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym)
        ui.settle()
        if "bzs_mode" in sym:
            # THE WHEEL AT EQUAL CONTENT: the sound OFF (S's own choice, SPEC.md 128.20.4). Its idle time is
            # what the wheel spends, and with the music on the rotors show ~2 poses in 36 fewer (SPEC.md
            # 128.20.7): a trade the owner weighs, priced by bonanzasound, not this row's verdict
            g.m.pause()
            g.putb("bzs_mode", 3)
            g.m.run()
        ref = R.Ref(tag, R.course("mill"))
        cover = {"beam": [], "cost": {2: [], 3: []}}
        for leg, fn in (("bench", lambda: bench_leg(g, ref, wr)), ("low", lambda: low_leg(g, ref))):
            if leg in legs:
                f, r, cv = fn()
                fails += f
                rep += r
                cover["beam"] += cv["beam"]
                for wd, xs in cv["cost"].items():
                    cover["cost"].setdefault(wd, []).extend(xs)
        if "bench" in legs and "low" in legs:   # (3) and (5) over both legs' commits
            beam = cover["beam"]
            if not [b for b in beam if b[1] == "ahead"] or not [b for b in beam if b[1] == "behind"]:
                (fails if tag == "cga" else rep).append(
                    "(3) the beam judged on %d AHEAD and %d BEHIND commits: each kind at least once" % (
                        sum(1 for b in beam if b[1] == "ahead"), sum(1 for b in beam if b[1] == "behind")))
            for wd in (2, 3):
                if not cover["cost"].get(wd):
                    (fails if tag == "cga" else rep).append("(5) no %d-word lane's commit was timed" % wd)
                elif not [x for x in cover["cost"][wd] if x[5]]:
                    (fails if tag == "cga" else rep).append("(5) no WHOLE %d-word lane's commit was timed: bz_lcf's "
                                                            "price never judged" % wd)
        if "stale" in legs:
            f, r = stale_leg(g, ref)
            fails += f
            rep += r
        if "corner" in legs:
            f, r = corner_leg(g, ref)
            fails += f
            rep += r
        if "gate" in legs:
            f, r = gate_leg(g, scen)
            fails += f
            rep += r
    for line in rep:
        print("%s %s" % (tag, line), flush=True)
    return fails


REDS = {
    "repeat": [("bzwheel.inc", "    call bz_ltrue               ; 1. the true pose\n    cmp al, [bz_ldrw + bx]\n"
                "    jne .due\n",
                "    call bz_ltrue               ; 1. the true pose\n    cmp al, [bz_ldrw + bx]\n"
                "    jmp short .due              ; RED repeat: every lane committed every visit\n")],
    "ahead": [("bzwheel.inc", "    call bz_wcore\n    mov al, [bz_ltru + bx]\n    mov [bz_ldrw + bx], al\n",
               "    call bz_wcore\n    mov al, [bz_ltru + bx]\n    inc al                      ; RED ahead: a pose past\n"
               "    mov [bz_ldrw + bx], al\n")],
    "nobeam": [("bzwheel.inc", "    cmp dx, [si + 2 * BZ_WBLK]\n    ja .anf\n",
                "    nop                         ; RED nobeam: no AHEAD test\n"),
               ("bzwheel.inc", "    cmp dx, ax\n    jae .now\n",
                "    cmp dx, ax\n    jmp short .now              ; RED nobeam: no BEHIND spin\n")],
    "kmod": [("bzwheel.inc", "    sub ax, BZ_WMARG\n    mov [bz_wdl], ax\n",
              "    sub ax, BZ_WMARG\n    mov [bz_wdl], ax\n    mov word [bz_wdl], 0fff0h   ; RED kmod: no first sync\n")],
    "halfcal": [("bzwheel.inc", "    call .min1\n    mov [bz_warr], ax\n.lcf:\n",
                 "    call .min1\n    mov [bz_warr], ax\n    shr word [bz_wlw], 1        ; RED halfcal (before bz_lcf)\n"
                 ".lcf:\n")],
    "alias": [("bzwheel.inc", "    mov bx, [bz_R0]\n    mov cx, bx\n    add cx, [bz_H]\n    call bz_span\n"
               "    mov [bz_lra], ax\n",
               "    mov bx, [bz_R0]\n    mov cx, bx\n    add cx, [bz_H]\n    nop                         ; RED alias\n"
               "    mov [bz_lra], ax\n"),
              ("bzwheel.inc", "    mov bx, [bz_c0]\n    mov cx, bx\n    add cx, [bz_W]\n    call bz_span\n"
               "    mov [bz_lra + 4], ax\n",
               "    mov bx, [bz_c0]\n    mov cx, bx\n    add cx, [bz_W]\n    nop                         ; RED alias\n"
               "    mov [bz_lra + 4], ax\n")],
    "corner": [("bzwheel.inc", "    mov ax, [bz_dc]\n    or ax, ax\n    jz .cols\n    js .left\n    dec cx\n",
                "    jmp short .cols             ; RED corner: the entering column's cells too\n    js .left\n"
                "    dec cx\n")],
    "lanestale": [("bzwheel.inc", "    call bz_lsync               ; 2. wholly outside: the map now, in RAM\n",
                   "    nop                         ; RED lanestale: the map and bz_ldrw left stale\n")],
    "gatelate": [("bzwheel.inc", "    call bz_lmust               ; 4. a must-draw rotor or post ...\n    jnc .cont\n",
                  "    call bz_lmust               ; 4. a must-draw rotor or post ...\n    jnc .cont\n"
                  "    jmp .next                   ; RED gatelate: skipped while its gate changes\n")],
    "litsteps": [("bzwheel.inc", "    dec byte [bz_lhold + bx]\n",
                  "    mov byte [bz_lhold + bx], 0 ; RED litsteps: lit for one frame\n")],
    # wave 3b (SPEC.md 128.13.12).  bz_lcf left unfilled (0): a WHOLE lane priced at nothing: (5)
    "costtab": [("bzwheel.inc", "    mov [bz_lcf + si], ax\n    inc bx\n",
                 "    mov word [bz_lcf + si], 0   ; RED costtab: bz_lcf unfilled\n    inc bx\n")],
    # bz_lnext one STEP late (a pose change drawn a frame late, none skipped): (13)
    "lnext": [("bzwheel.inc", "    inc dx\n    add dx, [bz_nstep]\n",
               "    inc dx\n    inc dx                      ; RED lnext: one step late\n    add dx, [bz_nstep]\n")],
    # the post's skip without its drawn-DARK clause: a post drawn lit whose lit frames are out (the sweep's
    # poke) is skipped while bz_ltru still says lit, and never goes dark: (12)
    "pskip": [("bzwheel.inc", "    or al, al                   ; ...or a POST is drawn dark, its lit frames\n"
               "    jnz .w0                     ; none, every kick seen\n    cmp [bz_lhold + bx], al\n",
               "    xor al, al                  ; RED pskip: no drawn-dark clause\n    cmp [bz_lhold + bx], al\n")],
}
# each arm's leg is the one that puts its case in front of its check (SPEC.md 128.13.7): `nobeam` the LOW
# leg's BEAM sweep, `alias` and `corner` the LIGHT corner step, `lanestale` the STALE scene, `pskip` the
# sweep's poked lit frames, `costtab` the LOW leg's whole posts
RED_LEGS = {"repeat": ("bench",), "ahead": ("bench",), "nobeam": ("low",), "kmod": ("bench",),
            "halfcal": ("bench",), "alias": ("corner",), "corner": ("corner",), "lanestale": ("stale",),
            "gatelate": ("gate",), "litsteps": ("bench",), "costtab": ("low",), "lnext": ("bench",),
            "pskip": ("low",)}
# the Hercules' beam checks are reported (128.12.15 item 5); the corner's (6) and (5) are asserted on the CGA
# ...and `halfcal` the CGA's: on the Hercules every MILL commit leaves more than the halved price's ~600
# counts before its deadline, so nothing overruns there (the final pass of wave 3b: bz_wover 0, (5)'s
# ratio 1.31 reported)
RED_TAGS = {"nobeam": ("cga",), "kmod": ("cga",), "corner": ("cga",), "alias": ("cga",), "costtab": ("cga",),
            "halfcal": ("cga",)}
# `halfcal` at (5) since wave 4's final pass: the halved word-line prices every whole rotor 30% under
# its span, which (5) asserts within 15%; wave 4's MILL frames leave no commit near its deadline, so
# (4)'s overrun no longer follows on the CGA (bonanzaperf's `halfcal` still meets bz_wover)
RED_WANT = {"repeat": "(1)", "ahead": "(2)", "nobeam": "(3)", "kmod": "(3)", "halfcal": "(5)", "alias": "(6)",
            "corner": "(6)", "lanestale": "(9)", "gatelate": "(10)", "litsteps": "(12)", "costtab": "(5)",
            "lnext": "(13)", "pskip": "(12)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--leg", choices=LEGS + ("all",), default="all")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true",
                    help="the host half only: the gate logs proved on the model, every red arm assembled")
    a = ap.parse_args()
    if a.check:
        S = gate_scen()
        bad = P.prove(S)
        for s in S:
            print("bonanza_wheel gate log %s: %d steps, %s" % (s["name"], len(s["keys"]), s["what"]))
        for b in bad:
            print("FAIL %s" % b)
        wr = writers()
        print("bonanza_wheel: bz_ldrw's writers at image offsets %s" % ", ".join("%04Xh" % o for o in wr))
        assert len(wr) == 2, "bz_ldrw has %d writers, not bz_lsync's and bz_wcommit's" % len(wr)
        for line in R.check_reds(REDS, "bonanza_wheel"):
            print(line)
        assert not bad, "%d gate log(s) not proved on the model" % len(bad)
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    legs = LEGS if a.leg == "all" else (a.leg,)
    if a.red:
        tags = tuple(t for t in tags if t in RED_TAGS.get(a.red, tags)) or RED_TAGS.get(a.red, tags)
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    bad = run(tag, RED_LEGS[a.red], apps=img, src=src)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(b.startswith(RED_WANT[a.red]) for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check %s: %s" % (a.red, tag, RED_WANT[a.red], bad)
                print("bonanza_wheel --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_wheel --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad = []
    for tag in tags:
        bad = run(tag, legs)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d wheel failure(s)" % len(allbad)
    print("bonanza_wheel (%s; %s): PASS" % (", ".join(tags), ", ".join(legs)))


if __name__ == "__main__":
    main()
