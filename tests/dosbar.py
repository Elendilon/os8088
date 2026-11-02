#!/usr/bin/env python3
"""dosbar - launching a DOS program is ONE operation of the file widget, and
no more bars than it was measured at (SPEC.md 12.8.10, 96.44.5.4).

    make && make doscom && python3 tests/dosbar.py

A double-click on B:DOSHELLO.EXE launches DOS.O88 off the 360KB system disk
(the LZB build, SPEC.md 96.44.18) and the row traces the kernel's widget until
the program's READY prompt:

  1. `dsl_entry` opens ONE operation (`fpg_opbegin`) over the carve and the
     core's fetch, and EVERY by-name read of DOS.O88 lands inside it
     (`[fpg_on]` has FPG_OP) - so the launch's reads fill the bar once
     instead of once per part;
  2. that operation fills the trough: `[fpg_done]` reaches 90% of `[fpg_opt]`
     before its end (a scale cut from the wrong rows stops short or runs
     over);
  3. the number of times the widget comes UP between the double-click and
     READY is at most BARS_MAX - the count measured on this disk at 8f18e5f3
     and unchanged back to e7bd353b, where the one-bar operation landed: the
     launch (the kernel's read of the loader part, then the operation), a
     flash as the window is made, HIBER.DRV, and the program's own read.

VERIFIED TO FAIL: with dsl_entry's `call OSAPI_FS_OP` (the begin) taken out,
leg 1 reports 0 operations and DOS.O88's reads outside one.
"""
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88ui                                               # noqa: E402
import os88marty as M                                       # noqa: E402

SYS = "build/os8088-360.img"
EXE = "build/dosexe360.img"
FPG_SHOWN = 4
FPG_OP = 8
BARS_MAX = 4


def fail(msg):
    print("dosbar: FAIL: %s" % msg, flush=True)
    sys.exit(1)


def main():
    os.chdir(ROOT)
    for p in (SYS, EXE):
        if not os.path.exists(p):
            fail("%s is missing - `make && make doscom` builds it" % p)

    def on(m, rec):
        f = m.read(m.sym("fpg_on"), 1)[0]
        name = ""
        if rec["name"] == "dskw_read_at_x":
            r = m.regs()
            raw = m.read(r["ds"] * 16 + r["si"], 16)
            name = raw.split(b"\0")[0].decode("latin1").upper()
        done = opt = 0
        if rec["name"] == "fpg_show" and f & FPG_OP:
            done = int.from_bytes(m.read(m.sym("fpg_done"), 2), "little")
            opt = int.from_bytes(m.read(m.sym("fpg_opt"), 2), "little")
        return (f, name, done, opt)

    with os88ui.boot(SYS, apps=EXE, quick=True) as ui:
        m = ui.m
        ui.open_drive("B")
        M.settle(m)
        with M.bp_trace(m, "fpg_show", "fpg_hide", "fpg_opbegin", "fpg_finish",
                        "dskw_read_at_x", on_hit=on, cap=8000) as tr:
            ui.path("B:/DOSHELLO.EXE")
            M.until(m, lambda mm: any("READY" in r
                                      for r in (mm.screen() or [])),
                    "the program's READY prompt", guest=90.0, poll=0.2)
        m.type_text("x")

    ups, shown, ops, outside, inside, best = 0, False, 0, [], 0, None
    for h in tr.hits:
        n, (f, name, done, opt) = h["name"], h["hit"]
        if n == "fpg_show" and (f & FPG_OP) and opt:
            best = max(best or 0, done * 100 // opt)
        if n == "fpg_show" and (f & FPG_SHOWN) and not shown:
            shown = True
            ups += 1
        elif n == "fpg_hide":
            shown = False
        elif n == "fpg_opbegin":
            ops += 1
        elif n == "dskw_read_at_x" and name == "DOS.O88":
            if f & FPG_OP:
                inside += 1
            else:
                outside.append(f)
    print("dosbar: %d operation(s), DOS.O88 read %d time(s) inside one and "
          "%d outside, the operation filled to %s%%, the widget came up %d "
          "time(s) (at most %d)" % (ops, inside, len(outside),
                                    best if best is not None else "-", ups,
                                    BARS_MAX), flush=True)
    if ops != 1:
        fail("%d fpg_opbegin calls during the launch, not one - dsl_entry's "
             "OSAPI_FS_OP (SPEC.md 12.8.10) did not open the operation" % ops)
    if outside or not inside:
        fail("DOS.O88 was read %d time(s) outside the launch's operation "
             "(and %d inside): each such read fills the bar again"
             % (len(outside), inside))
    if best is not None and best < 90:
        fail("the operation ended with the bar at %d%% of its scale" % best)
    if ups > BARS_MAX:
        fail("the widget came up %d times between the double-click and READY "
             "against the %d measured: something the launch reads is a bar of "
             "its own again" % (ups, BARS_MAX))
    print("dosbar: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
