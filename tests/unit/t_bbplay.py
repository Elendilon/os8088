#!/usr/bin/env python3
"""t_bbplay - TEST ROLL's model and frame (SPEC.md 130.58.16), on the host, no Tk, no emulator:

 1. THE PLAY-ONLY COMPILE: MILL compiled with no occluders and the block limit lifted
    (bbplay.compile_play) leaves bbcourse.BLK_MAX as it found it, and the AUTOPILOT from the start
    steps to the goal on it in the same world state, step for step, as on the full compile;
 2. A SCRIPTED RUN from the start - arrows held, a Hop, a Grip, a RETURN (Backspace) - frame by frame
    at the card's refresh (bbplay.Roll), in the same world state on both compiles after every frame,
    with the RETURN counted and the ball moved;
 3. FROM A POKED CELL (--start): the ball placed on cell (14, 18) grounded, then the same script, the
    two compiles again equal after every frame;
 4. THE FRAME: composited without Tk (bbplay.Art.window) on the full compile, the camera window holds
    the ball's footprint and every pixel of the ball's sprite() frame sits at (px, py) - except the
    pixels the occluder pass lays back (laid_at, card=True), which show the picture; at least one
    frame of the autopilot's run has such pixels, so the occluder path is exercised; the Hercules
    translation (bbplay.to_herc) equals bonanza_assets.herc_pair pixel for pixel;
 5. THE DEMO: the scripted run saved as the game's log (BZR1, course K of BZ_COURSES, the full
    compile's identity) passes the guest's checks 1 - 8 (bbcourse.check_log) and replays through
    Physics.run_log from the start to the run's own end state;
 6. REWIND: a run rewound 5 s goes back 5 s to 5.5 s (a rewind point every 27 steps), and driven
    again with the same keys ends where it ended.

Red by hand (2026-11-21): Art.window drawing the ball at px + 1 (item 4: 'the ball's pixel ... is
not the frame's'); Roll.frame not appending the RETURN pulse to the run's keys (item 5: 'replays
to ... the run ended at'); compile_play leaving BLK_MAX lifted (item 1).
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ["BB_CACHE"] = "0"                    # (writes nothing shared: no compile cache)
import bbcourse as B  # noqa: E402
import bonanza_assets as BA  # noqa: E402
import bbplay as P  # noqa: E402

MILL = os.path.join("apps", "bonanza", "courses", "mill.bbc")
SCRIPT = [(B.K_U, 40), (B.K_U | B.K_R, 30), (0, 20), (B.K_D | B.K_HOP, 25), (B.K_D, 30), ("ret", 1),
          (B.K_L | B.K_GRIP, 30), (B.K_R | B.K_D, 60), (0, 40)]


def drive(roll, script=SCRIPT, every=None):
    out = []
    for k, n in script:
        if k == "ret":
            roll.back_to_flag()
            k = 0
        for _ in range(n):
            roll.frame(k)
            if every:
                every(roll)
            out.append(P.wstate(roll.p))
    return out


def first_diff(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i, x[:8], y[:8]
    return None if len(a) == len(b) else (min(len(a), len(b)), "length", "length")


def main():
    bad = []
    with open(os.path.join(ROOT, MILL), "r", encoding="ascii", newline="") as f:
        text = f.read()
    held = B.BLK_MAX
    play = P.compile_play(text, MILL)
    if B.BLK_MAX != held:
        bad.append("1: compile_play left BLK_MAX at %d (was %d)" % (B.BLK_MAX, held))
    full = P.compile_full(text, MILL)

    # 1. the autopilot on both compiles
    def auto(c):
        p = B.Physics(c, play=True)
        tr = []
        while not p.goal and p.nstep < 4000:
            p.step_auto()
            tr.append(P.wstate(p))
        return tr
    ta, tb = auto(play), auto(full)
    d = first_diff(ta, tb)
    if d:
        bad.append("1: the autopilot differs at step %s: play-only %r, full %r" % d)
    if not tb or not tb[-1][10]:
        bad.append("1: the autopilot did not reach MILL's goal on the full compile (%d steps)" % len(tb))
    print("1: the autopilot reaches the goal in %d steps, the same on both compiles: %s" % (len(tb), not d))

    # 2. the scripted run from the start
    ra, rb = P.Roll(play), P.Roll(full)
    sa, sb = drive(ra), drive(rb)
    d = first_diff(sa, sb)
    if d:
        bad.append("2: the scripted run differs at frame %s: play-only %r, full %r" % d)
    p = rb.p
    if p.nret != 1:
        bad.append("2: the RETURN was counted %d times, not once" % p.nret)
    if p.nhop < 1:
        bad.append("2: no Hop in the scripted run")
    if (p.gx >> 12, p.gy >> 12) == tuple(rb.p.grid.start):
        bad.append("2: the ball ended on the start cell")
    print("2: %d frames, %d steps; hops %d, returns %d, falls %d; equal on both compiles: %s"
          % (rb.nframe, p.nstep, p.nhop, p.nret, p.nfall, not d))

    # 3. from a poked cell
    pa, pb = P.Roll(play, start=(14, 18)), P.Roll(full, start=(14, 18))
    if (pb.p.gx >> 12, pb.p.gy >> 12) != (14, 18) or pb.p.air:
        bad.append("3: the poke left the ball at cell (%d, %d), air %d" % (pb.p.gx >> 12, pb.p.gy >> 12, pb.p.air))
    d = first_diff(drive(pa), drive(pb))
    if d:
        bad.append("3: the poked run differs at frame %s: play-only %r, full %r" % d)
    print("3: poked at (14, 18); equal on both compiles: %s" % (not d))

    # 4. the frame
    art = P.Art(full)
    seen = {"frames": 0, "hidden": 0, "checked": 0}

    def look(roll):
        q = roll.p
        if q.tube:
            return
        win, (ox, oy) = art.window(roll)
        W, H = win.size
        if not (ox <= q.px and q.px + 16 <= ox + W and oy <= q.py and q.py + 16 <= oy + H):
            bad.append("4: frame %d: the ball (%d, %d) is outside the window at (%d, %d)" % (roll.nframe, q.px,
                                                                                              q.py, ox, oy))
            return
        pix = win.load()
        hid = set()
        cl = q.cell(q.gx >> 12, q.gy >> 12)
        if cl[4] & (B.FL_OCC if q.air else B.FL_OCCG):
            hid = B.laid_at(full, q.px, q.py, q.sb, q.zb, q.oair, card=True, cell=B.mcell(q.gx, q.gy))
        fr = art.ball(q.mat, B.sprite(q, False))
        for (dx, dy), v in fr.items():
            x, y = q.px + dx, q.py + dy
            got = pix[x - ox, y - oy]
            if (x, y) in hid:
                want = full.pic[y][x]
                seen["hidden"] += 1
            else:
                want = v
            if got != want and not ((x, y) in hid and got == v == want):
                bad.append("4: frame %d: the ball's pixel (%d, %d) is %d, not the %s's %d"
                           % (roll.nframe, x, y, got, "picture" if (x, y) in hid else "frame", want))
                return
            seen["checked"] += 1
        seen["frames"] += 1
    rc = P.Roll(full)
    while not rc.p.goal and rc.p.nstep < 4000:
        k = rc.p.auto()
        rc.frame(k)
        if rc.nframe % 3 == 0:
            look(rc)
    if seen["frames"] < 100:
        bad.append("4: only %d frames composited" % seen["frames"])
    if not seen["hidden"]:
        bad.append("4: no frame of the autopilot's run had a ball pixel behind an occluder (the path is untested)")
    win, org = art.window(rc)
    h = P.to_herc(win, org)
    wp, hp = win.load(), h.load()
    nh = 0
    for y in range(win.size[1]):
        for x in range(win.size[0]):
            pr = BA.herc_pair(wp[x, y], org[1] + y, org[0] + x)
            nh += (hp[2 * x, y] == 255) != bool(pr & 2) or (hp[2 * x + 1, y] == 255) != bool(pr & 1)
    if nh:
        bad.append("4: the Hercules translation differs from herc_pair at %d pixels" % nh)
    print("4: %d frames composited, %d ball pixels checked, %d of them behind an occluder; Hercules pixels "
          "wrong: %d" % (seen["frames"], seen["checked"], seen["hidden"], nh))

    # 5. the demo
    K = P.course_number(os.path.join(ROOT, MILL))
    if K is None:
        bad.append("5: MILL is not in BZ_COURSES")
    else:
        log = rb.log(K, full.ident)
        idents = [0] * (K + 1)
        idents[K] = full.ident
        chk = B.check_log(log, K + 1, idents)
        if chk:
            bad.append("5: the saved log fails the guest's check %d: %s" % chk)
        why = P.check_saved(log, full, P.wstate(rb.p))
        if why:
            bad.append("5: " + why)
        print("5: a %d-byte log, course %d, identity %04Xh: check_log %s, replay %s"
              % (len(log), K, full.ident, chk or "ok", why or "ends where the run ended"))

    # 6. rewind
    r1 = P.Roll(full)
    drive(r1, SCRIPT * 3)
    end = P.wstate(r1.p)
    n0 = len(r1.keys)
    tail = r1.fsteps[:]
    r1.rewind()
    back = len(r1.keys)
    for ks in tail[len(r1.fsteps):]:
        r1.frame(0, steps=ks)
    if P.wstate(r1.p) != end:
        bad.append("6: rewound and driven again it ends at %r, not %r" % (P.wstate(r1.p)[:8], end[:8]))
    lo = int(P.REWIND_S * B.STEP_HZ)
    if not lo <= n0 - back <= lo + P.SNAP_STEPS + 8:
        bad.append("6: the rewind went back %d steps, not %d - %d" % (n0 - back, lo, lo + P.SNAP_STEPS + 8))
    print("6: rewound %d steps (%.2f s) and driven again: %s" % (n0 - back, (n0 - back) / B.STEP_HZ,
                                                                  "the same end" if P.wstate(r1.p) == end else "DIFFERENT"))

    for b in bad:
        print("FAIL " + b)
    print("t_bbplay: %s" % ("ok" if not bad else "%d failure(s)" % len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
