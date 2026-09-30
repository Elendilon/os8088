"""The two handle defects docs/plans/DOS-STREAM-PLAN.md 3 found, as a row.

tests/dostrap/dosfix.asm opens SUB\\X.DAT from the ROOT and reads it past the
box's 8KB window, with a DECOY X.DAT in the root whose bytes are all 0xEE -
so a refill that looks the bare name up where the program STANDS, rather
than in the folder the name was opened in, reads the decoy and the probe
prints `FDIR BAD at <offset>`. Then it writes 3,000 bytes to NOCLOSE.DAT and
exits WITHOUT AH=3Eh, and this reads the floppy back: DOS closes every
handle of a terminating process, so all 3,000 must be on the disk.

WHAT IT WOULD CATCH: the handle forgetting its folder (FDIR BAD at 8192, the
first refill), and the window left dirty at exit (NOCLOSE.DAT missing or
empty - the box never flushed it). Both failed before SPEC.md 96.52.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import os88build                                               # noqa: E402
import os88fat                                                 # noqa: E402
import os88marty                                               # noqa: E402
import os88ui                                                  # noqa: E402

SYS = os88build.at("build/os8088-360.img")
GATE = os88build.at("build/dosfix360.img")
SCRATCH = os88build.at("build/dosfix-run.img")


def fail(msg):
    print("dosfix: FAIL: %s" % msg)
    sys.exit(1)


def main():
    for p in (SYS, GATE):
        if not os.path.exists(p):
            fail("%s is missing - `make build/dosfix360.img`" % p)
    shutil.copyfile(GATE, SCRATCH)
    bad = []
    with os88ui.boot(SYS, apps=SCRATCH) as ui:
        m = ui.m
        if not ui.path("B:/DOSFIX.COM"):
            fail("double-clicking DOSFIX.COM opened no window")
        rows = []

        def done(mm):
            rows[:] = mm.screen() or []
            return any(r.startswith("READY") for r in rows)
        try:
            os88marty.until(m, done, "the probe's READY line", poll=0.5,
                            limit=240.0)
        except os88marty.MartyError:
            fail("the probe never finished; the last text screen was %r"
                 % ([r.rstrip() for r in rows if r.strip()],))
        text = [r.rstrip() for r in rows if r.strip()]
        for r in text:
            print("   | %s" % r)
        if any(r.startswith("FAILED") for r in text):
            fail("the probe could not run: %r" % [r for r in text
                                                  if r.startswith("FAILED")])
        if not any(r.startswith("FDIR ok") for r in text):
            bad.append("a handle opened as SUB\\X.DAT refilled from the WRONG "
                       "FOLDER: %r (DOS-STREAM-PLAN 3.1)"
                       % [r for r in text if r.startswith("FDIR")])
        m.type_text("x")                    # ...and it exits, unclosed
        os88marty.until(m, lambda mm: "Disk" in ui.titles(),
                        "the desktop to come back", guest=60.0, poll=0.5)
        os88marty.quiesce(m, lambda: (m.disk().get("writes"),
                                      m.disk().get("write_sectors")),
                          guest=2.0, what="the floppy's writes to stop")
        m.flush(1, os.path.abspath(SCRATCH))

    v = os88fat.Fat12(SCRATCH)
    try:
        got = v.read("NOCLOSE.DAT")
    except Exception:                                          # noqa: BLE001
        got = None
    if got is None:
        bad.append("NOCLOSE.DAT is not on the disk: a file written and never "
                   "closed was lost at the exit (DOS-STREAM-PLAN 3.2)")
    elif got != b"N" * 3000:
        bad.append("NOCLOSE.DAT holds %d bytes, not the 3,000 written: the "
                   "exit did not flush the window (DOS-STREAM-PLAN 3.2)"
                   % len(got))
    else:
        print("dosfix: NOCLOSE.DAT holds all 3,000 bytes after an exit with "
              "no close")
    if bad:
        for b in bad:
            print("dosfix: FAIL: %s" % b)
        return 1
    print("dosfix: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
