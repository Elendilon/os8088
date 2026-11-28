#!/usr/bin/env python3
"""Frotz's line editor draws its echo UNDER THE GFX LOCK (SPEC.md 61.18).

    make build/frotz.o88 build/zt/ZBIG.Z5 && python3 tests/zecholock.py

`@read`'s wait runs with the lock DROPPED - zxo_read parks it (zx_park), as
SPEC.md 20.6 rule 3 asks of a worker that waits - and the echo of each key
(`zw_typec`), the rub-out (`zw_rubc`) and the Enter's newline (`zw_newline`)
are drawn from inside that wait. They were called bare, so the worker drew
lock-free while the UI task drew under the lock. On one display that is a
race over the renderer's scratch; on an extended desktop it took the machine
down: the display context is the lock holder's (SPEC.md 39.14.3), a drag
switched it under the worker's half-drawn row, and the rest of the row went
through the other card's geometry (docs/reports/EXTENDED-DESKTOP-AUDIT-
2026-11-27.md; the crash needed a VGA primary, a Hercules beside it and a
drag at the moment of the Enter, and reproduced 2 of 2 on MartyPC).

THIS ROW ASKS THE QUESTION DIRECTLY, on one display, where it is
deterministic: an exec breakpoint on each of the three routines in the live
package, one key, one Backspace and one Enter typed at the story's prompt,
and at EVERY stop the kernel's [gfx_lock_flag] must be set and
[gfx_lock_own] must be the running task. Each routine must be stopped in at
least once (the positive control: a row whose breakpoints never fired would
otherwise pass), and the story must come back to its prompt after.

VERIFIED RED: with zi_readline calling the three bare again (the fix
reverted), every stop reads the lock FREE - "zw_typec ran with the gfx lock
free (flag 0, owner FF, running task 12)".
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "tests")]
import editmove                                         # noqa: E402
import os88geom                                         # noqa: E402
import os88marty                                        # noqa: E402
import os88sym                                          # noqa: E402
import os88ui                                           # noqa: E402

S = os88sym.linear
PKG = os.path.join(ROOT, "build", "frotz.o88")
STORY = os.path.join(ROOT, "build", "zt", "ZBIG.Z5")
ZIW_LINE = 1
ROUTINES = ("zw_typec", "zw_rubc", "zw_newline")
fails = []


def u16(b, i=0):
    return b[i] | b[i + 1] << 8


def check(cond, what):
    print("   %s  %s" % ("ok " if cond else "FAIL", what))
    if not cond:
        fails.append(what)
    return cond


def main():
    verbose = "-q" not in sys.argv
    p = editmove.pkg_syms(os.path.join(ROOT, "apps", "frotz", "frotz.asm"),
                          (os.path.join(ROOT, "apps") + "/",
                           os.path.join(ROOT, "apps", "frotz") + "/"),
                          ["zi_want", "zi_linen", "os88_image_end"])
    rel = {n: p[n] - p["os88_image_end"] for n in ("zi_want", "zi_linen")}
    tmp = tempfile.mkdtemp(prefix="zecholock-")
    try:
        shutil.copy(PKG, os.path.join(tmp, "FROTZ.O88"))
        shutil.copy(STORY, os.path.join(tmp, "ZBIG.Z5"))
        disk = os.path.join(tmp, "zel.img")
        subprocess.run([sys.executable,
                        os.path.join(ROOT, "tools", "os88disk.py"), "-o", disk,
                        "--size", "360", os.path.join(tmp, "FROTZ.O88"),
                        os.path.join(tmp, "ZBIG.Z5")],
                       check=True, stdout=subprocess.DEVNULL)
        with os88ui.boot(os.path.join(ROOT, "build", "os8088-360.img"),
                         apps=disk, quick=True, verbose=verbose) as ui:
            m = ui.m
            ui.open_drive("B")
            win = ui.open("ZBIG.Z5")

            def seg():
                return u16(m.read(os88geom.winptr(m, win.i, S)
                                  + os88geom.W_SEG, 2))

            def bss(name, n=1):
                s = seg()
                return m.read(s * 16 + u16(m.read(s * 16 + 8, 2))
                              + rel[name], n)

            os88marty.until(m, lambda _: bss("zi_want")[0] == ZIW_LINE,
                            "the story's first prompt", limit=240)
            base = seg() * 16
            where = {base + p[r]: r for r in ROUTINES}
            m.breakpoints([{"type": "exec", "addr": a} for a in where])
            seen = dict.fromkeys(ROUTINES, 0)
            lk, own, cur = S("gfx_lock_flag"), S("gfx_lock_own"), S("sch_cur")

            def stops(key, until_routine):
                """Inject `key`, then check every stop until `until_routine`
                has been seen; the machine is left running."""
                m.key(key)
                for _ in range(64):
                    if m.wait_stop(30) is None:
                        check(False, "no breakpoint after %s" % key)
                        return
                    r = m.regs()
                    flat = (r["cs"] << 4) + r["ip"]
                    name = where.get(flat, "%05X" % flat)
                    f, o = m.read(lk, 1)[0], m.read(own, 1)[0]
                    c = m.read(cur, 1)[0]
                    seen[name] = seen.get(name, 0) + 1
                    if f != 1 or o != c:
                        check(False, "%s ran with the gfx lock %s (flag %d, "
                              "owner %02X, running task %d)"
                              % (name, "free" if f == 0 else "held by another "
                                 "task", f, o, c))
                    m.run()
                    if name == until_routine:
                        return
                check(False, "%s never reached %s" % (key, until_routine))

            stops("KeyG", "zw_typec")       # the echo
            stops("Backspace", "zw_rubc")   # the rub-out
            stops("KeyX", "zw_typec")       # a word the story does not know...
            stops("Enter", "zw_newline")    # ...and the Enter's newline
            m.breakpoints([])
            m.run()
            for r in ROUTINES:
                check(seen[r] > 0, "%s stopped in %d time(s)" % (r, seen[r]))
            check(not [w for w in fails if "gfx lock" in w],
                  "every stop held the gfx lock, by the running task")
            os88marty.until(m, lambda _: bss("zi_want")[0] == ZIW_LINE and
                            u16(bss("zi_linen", 2)) == 0,
                            "the prompt after the command", limit=60)
            check(True, "the story came back to its prompt")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("zecholock: %s" % ("FAIL: " + "; ".join(fails) if fails else "ok"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
