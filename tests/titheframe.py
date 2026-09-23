#!/usr/bin/env python3
"""TITHE's wheel: does the frame hold, and do its two levers still work?

SPEC.md 97.5's gate, and the reason it is a row rather than a note in a
report: the rate was measured once and the three things that made it
measurable at all are exactly the kind that come back.

WHAT IT ASSERTS, and each one went red on purpose first:

  1. THE FRAME HOLDS. The wheel runs one pass a system tick - 18.2 Hz - and
     that is wave 1a's gate. A wheel whose frame overruns its tick reports a
     LOWER frame rate and nothing else fails, which is how it shipped
     overrunning for a whole increment.

  2. THE CALIBRATION RAN. `ti_calfull` and `ti_calone` must be non-zero and
     `ti_calfull` bigger - a band cannot cost less than one of its rows.
     Zero means the PIT span wrapped (TITHE-PLAN 3.9's own trap), and a
     credit of zero is one the wheel cannot divide by.

  3. THE IDLE HOLDS ITS TARGET RATE AND NO MORE (SPEC.md 97.5.2): at or
     under it by default, above it uncapped - so the cap is what binds and
     the credit is priced - and ON a lowered target this machine can beat,
     which is the 286's question asked on an XT.

  4. A PROJECTILE DOES NOT MOVE THE IDLE, AND THE FRAME HOLDS. Two bolts
     crossing are the busiest frame on the machine (SPEC.md 97.4.5); they
     are charged to the combat lane, so the idle's rate stays within a band
     of its own, and the frame must still hold at 15 passes a second.

  THE DIRTY RECT IS NOT AN ARM HERE ANY MORE. It is always on and the wheel
  charges it the WHOLE band (SPEC.md 97.4.3): its 6-15% per commit is the
  frame's headroom, not a faster idle, so the rate it would have been
  asserted on is the rate item 4 already holds.
"""
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402
import os88mouse                                          # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SYMS = ("ti_ncommit", "ti_nframe", "ti_npj", "ti_nbase", "ti_nbadv", "ti_bw", "ti_bh",
        "ti_panx", "ti_by", "ti_cardpitch", "ti_cardh", "ti_ccardus",
        "ti_calfull", "ti_calone", "ti_base", "ti_bslot",
        "TI_BASEPOSES", "ti_clock", "ti_bclock", "TI_ROWS", "TI_COLS",
        "ti_nlay", "ti_fps10")
SPAN = 5.0

fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    """Where each symbol lives in the package's image.

    Assembled from the SOURCE with the words appended, so the offsets cannot
    drift from the binary under test the way a hand-kept table would.
    """
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "titheframe-off.asm")
    out = os.path.join(ROOT, "build", "titheframe-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp],
                   cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def main():
    off = offsets()

    def rw(m, seg, name):
        return struct.unpack("<H", bytes(m.readseg(seg, off[name], 2)))[0]

    with os88ui.boot("build/os8088-360.img", apps="build/tithe360.img",
                     machine="os8088_xt_vga") as ui:
        m = ui.m
        ui.path("B:/TITHE.O88")
        win = [w for w in os88geom.windows(m) if w.title == "Tithe"][0]
        seg = struct.unpack(
            "<H", bytes(m.read(os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)
        # FIVE GUEST SECONDS AND NOT TWO. The art build composes every pose of
        # every surface at launch and TI_BASEPOSES is eight now, so two seconds
        # read the calibration as zero AND took the baseline window at 9.6
        # frames a second - which then made a bolt look like it had sped the
        # idle up by 92% when it had not moved it at all.
        os88marty.guest_sleep(m, 5.0)

        full = rw(m, seg, "ti_calfull")
        one = rw(m, seg, "ti_calone")
        check(full > 0 and one > 0 and full > one,
              "the calibration ran and its two heights are ordered",
              "full=%d one=%d" % (full, one))

        def rate():
            a = rw(m, seg, "ti_ncommit")
            f = rw(m, seg, "ti_nframe")
            p = rw(m, seg, "ti_npj")
            spent = os88marty.guest_sleep(m, SPAN)
            return (((rw(m, seg, "ti_ncommit") - a) & 0xFFFF) / spent,
                    ((rw(m, seg, "ti_nframe") - f) & 0xFFFF) / spent,
                    ((rw(m, seg, "ti_npj") - p) & 0xFFFF) / spent)

        base_c, base_f, _ = rate()
        TARGET = rw(m, seg, "ti_fps10")
        print("  base: %.1f commits/s, %.1f frames/s (target %.1f a feature "
              "= %.1f commits/s)" % (base_c, base_f, TARGET / 10.0,
                                     TARGET * 2.0))
        check(base_c <= TARGET * 2.0 * 1.08,
              "the idle does not run above its target rate",
              "%.1f vs %.1f" % (base_c, TARGET * 2.0))
        check(base_f >= 16.0,
              "the wheel holds one pass a tick (>= 16 frames/s of 18.2)",
              "%.1f" % base_f)

        m.key("KeyA")                                  # two bolts crossing
        os88marty.guest_sleep(m, 2.5)
        p_c, p_f, p_p = rate()
        print("  + projectile: %.1f commits/s, %.1f frames/s, %.1f bolts/s"
              % (p_c, p_f, p_p))
        check(p_p > 1.0, "a projectile commits frames of its own",
              "%.1f/s" % p_p)
        # AND IT DOES NOT MOVE THE IDLE - IN EITHER DIRECTION. This asserted
        # `p_c >= base_c` and passed at +55%, which is the defect the field
        # reported as "pressing A speeds all the idle animations back up": the
        # combat allowance was ADDED to the wheel's credit, so a bolt bought
        # the twenty figures a faster idle. The lanes are separate now
        # (SPEC.md 97.5.1) and the assertion is a BAND - the one thing a
        # one-sided check could not say.
        drift = 100.0 * (p_c - base_c) / base_c
        print("  idle with a bolt in flight: %.1f/s (%+.1f%%)" % (p_c, drift))
        check(abs(drift) <= 15.0, "...and a bolt does not move the idle's rate",
              "%+.1f%%" % drift)
        # THE BUSIEST FRAME ON THE MACHINE: two bolts crossing over the whole
        # board's idle, with the dirty rect committing every idle move (it is
        # always on - SPEC.md 97.4.3). It once ran at ~13 passes a second
        # against the wheel's 18.2, because the combat allowance was ADDED to
        # the idle's share; separate lanes (SPEC.md 97.5.1) fixed that and 15
        # is the floor that fix carried as its own gate.
        check(p_f >= 15.0, "...and the busiest frame holds its rate",
              "%.1f" % p_f)
        m.key("KeyA")
        os88marty.guest_sleep(m, 2.5)

        # THE CAP IS WHAT BINDS, AND THE CREDIT IS PRICED. Uncapped, this XT's
        # VGA buys MORE than the target - which is the headroom the dirty rect
        # (SPEC.md 97.4.3) is worth - so the default above is the cap holding
        # and not the credit running out. A rate that read the same both ways
        # would mean the target is unreachable here, or that a cheaper commit
        # stopped being priced as one.
        def target(v):
            m.write(seg * 16 + off["ti_fps10"], struct.pack("<H", v))
        target(200)
        os88marty.guest_sleep(m, 1.0)
        u_c, _, _ = rate()
        target(TARGET)
        print("  uncapped: %.1f commits/s against the target's %.1f"
              % (u_c, TARGET * 2.0))
        check(u_c > TARGET * 2.0 * 1.1,
              "uncapped, the credit buys more than the target",
              "%.1f vs %.1f" % (u_c, TARGET * 2.0))

        # THE BASE LANE (SPEC.md 97.5.1). One of the two bases a frame, so
        # its own commits are one a frame and each base plays at half the tick
        # rate. What makes it a LANE rather than a priority is that the idle's
        # rate cannot reach it, which is what the second half measures.
        def lane():
            b0 = rw(m, seg, "ti_nbase")
            c0 = rw(m, seg, "ti_ncommit")
            f0 = rw(m, seg, "ti_nframe")
            spent = os88marty.guest_sleep(m, SPAN)
            return tuple(((rw(m, seg, n) - v) & 0xFFFF) / spent for n, v in
                         (("ti_nbase", b0), ("ti_ncommit", c0),
                          ("ti_nframe", f0)))

        # AND EIGHT POSES MUST BE EIGHT PICTURES. This is the check the work
        # needed and did not have: the placeholder's keep moved only between
        # "centred" and "one pixel right", so raising TI_BASEPOSES from 2 to 8
        # bought four times the build cost and TWO distinct frames - an
        # animation that reads as a flick however many poses are paid for.
        # Read out of the band store, so it tests the ART and not the lane.
        n = off["TI_BASEPOSES"]
        slot = rw(m, seg, "ti_bslot")
        bands = {bytes(m.readseg(seg, off["ti_base"] + i * slot, slot))
                 for i in range(n)}
        print("  base art: %d distinct of %d poses (%d bytes each)"
              % (len(bands), n, slot))
        check(len(bands) >= (n + 1) // 2,
              "the base's poses are distinct pictures",
              "%d of %d" % (len(bands), n))

        # NEIGHBOURS ARE NEVER IN STEP. Every clock started at zero and the
        # wheel walks in INDEX order, so a pass gave a run of adjacent
        # features one step each and the board breathed as a block - twenty
        # figures moving together read as one animation with twenty copies.
        # The seed is 2D because adjacency here is not adjacency in the index:
        # a cell is column x 5 + row, so what a player sees stacked is i and
        # i+1 and what is side by side is i and i+5. Read straight after a
        # relayout, which is what re-seeds.
        # PAUSE FIRST. The wheel advances a feature's clock when it reaches it
        # and reaches only some of them a frame, so even half a second of
        # running has skewed the pattern - this read 5 collisions off a seed
        # that has none. `P` stops the wheel, so what is read back is the seed
        # and not the drift.
        # ...AND WAIT FOR THE RELAYOUT, NOT FOR A TIME. It composes four
        # column strips and eighty poses (SPEC.md 97.4.10) and is over a
        # second of an 8088; a fixed 0.8s read the clocks before the re-seed
        # and failed three runs in five on a seed with nothing wrong with it.
        m.key("KeyP")
        os88marty.guest_sleep(m, 0.6)
        n0 = rw(m, seg, "ti_nlay")
        m.key("KeyB")                                  # ...which re-seeds
        os88marty.until(m, lambda _: rw(m, seg, "ti_nlay") != n0,
                        "the relayout B asks for", poll=0.2, limit=60.0)
        rows, cols = off["TI_ROWS"], off["TI_COLS"]
        cl = bytes(m.readseg(seg, off["ti_clock"], rows * cols))
        grid = [[cl[c * rows + r] for c in range(cols)] for r in range(rows)]
        pairs = 0
        for c in range(cols):
            for r in range(rows):
                if r + 1 < rows and grid[r][c] == grid[r + 1][c]:
                    pairs += 1
                if c + 1 < cols and grid[r][c] == grid[r][c + 1]:
                    pairs += 1
        for r in grid:
            print("      ", r)
        print("  phase seed: %d touching pairs in step of %d"
              % (pairs, cols * (rows - 1) + rows * (cols - 1)))
        check(pairs == 0, "no two touching cells share a phase at the seed",
              "%d pairs" % pairs)

        # ...AND THE TWO BASES DO NOT MIRROR EACH OTHER. A phase offset alone
        # leaves them in lockstep a fixed distance apart, so what is asserted
        # is that the DISTANCE moves: identical cadences hold it constant
        # whatever the phases are.
        #
        # SAMPLE FAST. At one second apart this read base 1's clock as frozen
        # at 4 four times running and nearly had a defect filed against
        # working code: 7.5 poses a second against a 1 Hz sample is an ALIAS,
        # which is SCHED-IDLE-PLAN 2's warning one package along.
        m.key("KeyP")                                  # ...and running again
        os88marty.guest_sleep(m, 0.5)
        # AND NO COMMIT EVER REDRAWS THE POSE IT JUST DREW. The cadences were
        # built out of SKIPPED steps - one base advanced on four visits in
        # five - which is a different rate and is also a PAUSE: the fifth
        # visit redrew the same picture, so it held for four frames. That
        # reads as a beat on a bell and as broken on a flame. The split is in
        # the lane's TURN now, so an advance is unconditional and these two
        # counters are equal.
        adv0, com0 = rw(m, seg, "ti_nbadv"), rw(m, seg, "ti_nbase")
        os88marty.guest_sleep(m, 2.0)
        adv = (rw(m, seg, "ti_nbadv") - adv0) & 0xFFFF
        com = (rw(m, seg, "ti_nbase") - com0) & 0xFFFF
        print("  base lane: %d commits, %d of them advanced a pose" % (com, adv))
        # ...WITHIN ONE, because the two counters are read one after the other
        # and the lane increments them one after the other: a sample that lands
        # between them reads a commit whose advance has not been counted yet.
        # It is a straddle and not a skipped pose - the defect this is for
        # skipped ONE VISIT IN FIVE, which is 20% and not 3%.
        check(abs(adv - com) <= 1, "every base commit advances a pose",
              "%d of %d" % (adv, com))

        gaps = set()
        for _ in range(12):
            bc = bytes(m.readseg(seg, off["ti_bclock"], 2))
            gaps.add((bc[0] - bc[1]) % off["TI_BASEPOSES"])
            os88marty.guest_sleep(m, 0.2)
        print("  base cadences: %d distinct gaps in 12 samples" % len(gaps))
        check(len(gaps) >= 3, "the two bases drift rather than mirroring",
              "%d distinct gaps" % len(gaps))

        # --- WHAT ONE CARD COSTS TO COMPOSE (SPEC.md 97.4.1.1) -------------
        # The direct number, because a composition cannot be seen any other
        # way: the picture is identical whether the frame takes 3 ms or 40,
        # the wheel still commits, and every other row here still passes.
        # `ti_cb_frame` drew its ~320 pixels one at a time through a 16-bit
        # multiply - two thirds of a system tick to draw a RECTANGLE - and the
        # field reported it as a stutter on landing.
        #
        # IT IS A WINDOW AND NOT A CEILING, and the floor is the point: the
        # PIT counter is 16 bits and wraps at 54.9 ms, and the defect measured
        # ~54 - so the reading a regression gives is as likely to be a small
        # number as a large one. The tree reads 21.6 ms on VGA, 19.7 on
        # Hercules and 10.3 on CGA, and the pixel-at-a-time frame reads 38.4,
        # 40.2 and 30.8 - so the ceiling is 28 ms, which is 30% of headroom
        # over the worst real reading and still under the smallest defect one.
        cc = rw(m, seg, "ti_ccardus")
        print("  one card composes in %d us" % cc)
        check(3000 < cc < 28000, "a card composes in a sane fraction of a tick",
              "%d us" % cc)

        # --- A HOVER MUST NOT COST THE FRAME (SPEC.md 97.4.1.1) -------------
        # The card panel is composed by the package, and a composition that
        # goes quadratic is INVISIBLE in every other row here: the picture is
        # identical, the wheel still commits, nothing fails. `ti_cb_frame`
        # drew its ~320 pixels one at a time through a 16-bit multiply and
        # cost 36-44 ms - two thirds of a system tick to draw a RECTANGLE -
        # so the pointer landing on a card dropped two frames and the field
        # reported it as a stutter.
        #
        # TEN CHANGES BETWEEN TWO FIXED POINTS, and not a free sweep: how many
        # hover changes a sweep makes depends on mouse packet timing, and the
        # same build read 7.8 and 9.3 fps back to back that way.
        #
        # THE BAR IS LOOSE ON PURPOSE. It is a gate against a primitive going
        # quadratic, not a budget: the defect read 0.26 of the idle rate and
        # the tree reads 0.82, so 0.6 catches the thing it is for with room to
        # spare and cannot flake on a loaded box.
        mo = os88mouse.Mouse(marty=m)
        px, by = rw(m, seg, "ti_panx"), rw(m, seg, "ti_by")
        pitch, chh = rw(m, seg, "ti_cardpitch"), rw(m, seg, "ti_cardh")
        pts = [(px + 20, by + 1 * pitch + chh // 2),
               (px + 20, by + 4 * pitch + chh // 2)]
        mo.to(pts[0][0], pts[0][1])
        os88marty.guest_sleep(m, 1.5)
        tick = lambda: struct.unpack("<I", bytes(m.read(0x46C, 4)))[0]
        a, t0 = rw(m, seg, "ti_nframe"), tick()
        for i in range(10):
            mo.to(pts[i & 1][0], pts[i & 1][1])
        secs = (tick() - t0) / 18.2
        hov = ((rw(m, seg, "ti_nframe") - a) & 0xFFFF) / max(secs, 1e-6)
        mo.to(px // 2, by + 3 * pitch)
        os88marty.guest_sleep(m, 1.5)
        a, t0 = rw(m, seg, "ti_nframe"), tick()
        os88marty.guest_sleep(m, 3.0)
        idle = ((rw(m, seg, "ti_nframe") - a) & 0xFFFF) / max((tick() - t0) / 18.2, 1e-6)
        print("  hovering: %.1f fps over 10 changes, idle %.1f" % (hov, idle))
        check(hov >= 0.6 * idle, "a hover does not cost the frame",
              "%.1f of %.1f = %.2f" % (hov, idle, hov / idle if idle else 0))

        b_hi, c_hi, f_hi = lane()
        print("  base lane: %.1f commits/s of %.1f frames/s (idle %.1f/s)"
              % (b_hi, f_hi, c_hi))
        check(b_hi >= 0.85 * f_hi, "the base lane commits once a frame",
              "%.1f of %.1f" % (b_hi, f_hi))
        # THE RATE CAP (SPEC.md 97.5.2) - the 286's question asked on an XT.
        # A faster machine is one whose credit buys MORE than the target, and
        # so is a slower target on this one: 2.8 poses a second a feature
        # instead of the default 4.4 is well under what
        # the credit buys here, and the idle must land ON it - not above,
        # which is the hyperspeed a 286 would show, and not far below, which
        # would be a cap that also starves. The hand's feature takes a step
        # and commits nothing with no card hovered, so twenty commits are
        # twenty-one steps.
        fps = TARGET / 10.0
        target(TARGET - 16)
        os88marty.guest_sleep(m, 2.5)
        want = (rw(m, seg, "ti_fps10") / 10.0) * 20
        b_lo, c_lo, _ = lane()
        print("  target %.1f -> %.1f: idle %.1f commits/s (want %.1f), "
              "base %.1f/s (was %.1f)" % (fps, want / 20, c_lo, want, b_lo, b_hi))
        check(abs(c_lo - want) <= 0.08 * want,
              "the idle lands ON a target the machine can beat",
              "%.1f vs %.1f" % (c_lo, want))
        check(b_lo >= 0.85 * b_hi, "...and the BASE LANE stays where it was",
              "%.1f vs %.1f" % (b_lo, b_hi))
        target(TARGET)

    print("titheframe: %d check(s) FAILED" % len(fails) if fails
          else "titheframe: ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
