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

  3. THE DIRTY RECT BUYS SOMETHING. It is TITHE-PLAN 3.4.1's lever and it
     measured +0.6% while the charge was flat. Anything under +20% here
     means the wheel has stopped pricing what it draws, which is the defect
     that makes every later optimisation look worthless.

  4. THE SPRITE ARMS DIFFER. Three sizes that commit at the same rate are
     three sizes nobody can choose between (TITHE-PLAN 18.1).

  5. A PROJECTILE COSTS AND DOES NOT STALL. It is the most expensive thing
     in the renderer (3.9.1), so it must take commits away from the idle -
     and the frame must still hold, because four lanes stopping to pay for
     it is the concession 3.8 already made.
"""
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SYMS = ("ti_ncommit", "ti_nframe", "ti_npj", "ti_bw", "ti_bh",
        "ti_calfull", "ti_calone", "ti_drect")
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
        os88marty.guest_sleep(m, 2.0)

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
        print("  base: %.1f commits/s, %.1f frames/s" % (base_c, base_f))
        check(base_f >= 16.0,
              "the wheel holds one pass a tick (>= 16 frames/s of 18.2)",
              "%.1f" % base_f)

        m.key("KeyX")                                  # the dirty-rect arm
        os88marty.guest_sleep(m, 1.5)
        d_c, d_f, _ = rate()
        gain = 100.0 * (d_c - base_c) / base_c
        print("  dirty rect: %.1f commits/s (%+.1f%%)" % (d_c, gain))
        check(gain >= 20.0, "the dirty rect buys at least 20%",
              "%+.1f%%" % gain)

        m.key("KeyA")                                  # ...and a projectile
        os88marty.guest_sleep(m, 1.5)
        p_c, p_f, p_p = rate()
        print("  + projectile: %.1f commits/s, %.1f frames/s, %.1f bolts/s"
              % (p_c, p_f, p_p))
        check(p_p > 1.0, "a projectile commits frames of its own",
              "%.1f/s" % p_p)
        check(p_c < d_c, "...and it costs the idle something",
              "%.1f vs %.1f" % (p_c, d_c))
        check(p_f >= 15.0, "...and the frame still holds", "%.1f" % p_f)
        m.key("KeyA")
        m.key("KeyX")
        os88marty.guest_sleep(m, 1.5)

        m.key("KeyS")                                  # the sprite arms
        os88marty.guest_sleep(m, 1.5)
        a0_c, _, _ = rate()
        w0 = rw(m, seg, "ti_bw")
        m.key("KeyS")
        os88marty.guest_sleep(m, 1.5)
        a1_c, _, _ = rate()
        w1 = rw(m, seg, "ti_bw")
        print("  arms: %d px %.1f/s, %d px %.1f/s, 64 px %.1f/s"
              % (w0, a0_c, w1, a1_c, base_c))
        check(w0 < w1 < 64, "the three arms are three sizes",
              "%d %d 64" % (w0, w1))
        check(a0_c > a1_c > base_c * 1.05,
              "...and a smaller sprite commits more often",
              "%.1f %.1f %.1f" % (a0_c, a1_c, base_c))

    print("titheframe: %d check(s) FAILED" % len(fails) if fails
          else "titheframe: ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
