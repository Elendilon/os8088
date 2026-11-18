#!/usr/bin/env python3
"""The sound debug disk, booted (SPEC.md 127.2-127.4).

    python3 tests/snddiag.py [--keep]

Boots build/debug-sound-720.img on MartyPC's 5150 with a Sound Blaster
(os8088_5150_herc_sb_720_gla), touches nothing, and reads what SNDDIAG.O88
put on the screen - not off the pixels but out of the package's own text
buffer, sd_txt, which is exactly what its rows draw (sd_refresh copies it to
the glass row by row). The buffer is found by its header row, so the row needs
no map of the package.

What it asserts is the whole promise of the disk with nobody at the machine:
\\AUTOSTRT opened the program, the -DSNDDIAG driver answered SNDV_DIAG, the
play test started by itself, ran ten seconds and named nothing as stopped,
and pages 1 and 3 show the probe record (the DSP at 220h, a BLASTER= line,
the version command in the DSP write log). Then the DMA lab (SPEC.md 127.4.1)
ran to Done by itself: on an emulated 8237 that wraps, every run that ran
played on - except NOAUTO, the control, which must FREEZE at the end of its
cycle, so a lab that can no longer see a frozen 8237 goes red here. And the
two benchlib reports are on the disk, read back off the guest's floppy
(os88flush), the B one complete.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)
import os88marty as M          # noqa: E402
import os88geom as G           # noqa: E402
import os88flush as F          # noqa: E402

IMG = "build/debug-sound-720.img"
APPS = "build/apps720.img"
MACHINE = "os8088_5150_herc_sb_720_gla"
HDR = re.compile(rb" os8088 Sound Debug  build \d")
ROWS, LW = 17, 79
RATE = 22050


def page(m):
    wins = [w for w in G.windows(m) if str(w.title).startswith("Sound Debug")]
    if not wins:
        raise M.MartyError("no Sound Debug window: \\AUTOSTRT did not open it")
    data = M.pkg_read(m, wins[0], 0, 0xFE00)
    # The FIRST header row laid out at the page stride, its keys row last: the
    # benchlib report arena holds the same rows packed (no stride), and
    # sd_shown follows sd_txt, which is the one built
    for hit in HDR.finditer(data):
        o = hit.start()
        if data[o + (ROWS - 1) * LW:].startswith(b"Keys:"):
            return [data[o + i * LW:o + i * LW + LW - 1].decode("latin-1")
                    .rstrip() for i in range(ROWS)]
    raise M.MartyError("Sound Debug's text buffer has no header row")


def show(rows, what):
    print("---- %s" % what)
    for r in rows:
        print("  |" + r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    fails = []

    def check(cond, what):
        print("  %s %s" % ("ok  " if cond else "FAIL", what))
        if not cond:
            fails.append(what)

    for p in (IMG, APPS):
        if not os.path.exists(p):
            print("snddiag: %s missing - make" % p)
            return 1
    with M.launch(IMG, apps=APPS, machine=MACHINE) as m:
        rows = None
        for _ in range(240):                # the play test, then the lab
            m.advance(frames=50)
            try:
                rows = page(m)
            except M.MartyError:
                continue
            if "REFUSED" in rows[1] or "NOT RUN" in rows[1]:
                break
            if rows[1].startswith("DMA lab") and rows[1].endswith("Done."):
                break
        if rows is None:
            print("snddiag: FAIL - the program never appeared")
            return 1
        show(rows, "page 4, the lab, as the run left it")
        check(rows[1].endswith("Done."), "the DMA lab ran to Done by itself")
        lab = {}
        for r in rows[3:16]:
            f = r.split()
            if len(f) >= 2 and f[0].isdigit():
                lab[f[1]] = r[48:].strip()
        m.key("Digit5")
        m.advance(frames=25)
        p5 = page(m)
        show(p5, "page 5")
        for r in p5[2:5]:
            f = r.split()
            if len(f) >= 2 and f[0].isdigit():
                lab[f[1]] = r[48:].strip()
        check(len(lab) == 16, "sixteen lab rows (%d)" % len(lab))
        check(lab.get("NOAUTO", "").startswith("FROZE"),
              "NOAUTO, the control, froze at its terminal count (%r)"
              % lab.get("NOAUTO"))
        for name, res in sorted(lab.items()):
            if name == "NOAUTO" or res.startswith("skipped"):
                continue
            check(res.startswith("ran"), "lab %s ran on (%r)" % (name, res))
        check("SOUNDA1.TXT saved" in p5[15] and "SOUNDB1.TXT saved" in p5[15],
              "both reports saved (%r)" % p5[15])
        m.key("Digit2")
        m.advance(frames=25)
        rows = page(m)
        show(rows, "page 2, as the play test left it")
        check("Done." in rows[1], "the play test started by itself and "
              "finished (row 1 says Done.)")
        table = {}
        for r in rows[4:14]:
            f = r.split()
            if len(f) >= 3 and f[0].isdigit():
                table[int(f[0])] = (int(f[1]), f[2])
        check(sorted(table) == list(range(1, 11)), "ten one-second rows")
        for s in range(2, 10):
            b, irq = table.get(s, (0, "0"))
            check(abs(b - RATE) <= RATE // 10,
                  "second %d played %d bytes, within 10%% of %d" % (s, b, RATE))
            check(irq.isdigit() and int(irq) > 0,
                  "second %d took block IRQs (%s)" % (s, irq))
        check("watchdog 0" in rows[14], "no watchdog stop")
        check("steady" in rows[15], "the verdict names nothing as stopped")

        m.key("Digit1")
        m.advance(frames=25)
        p1 = page(m)
        show(p1, "page 1")
        check("debug build" in p1[2], "the -DSNDDIAG driver answered "
              "SNDV_DIAG")
        check("base 220h" in p1[4], "the DSP at 220h")
        check(p1[11].startswith("BLASTER=A220"), "a BLASTER= line")
        check("tier attached" in p1[13], "the verdict says the tier is up")

        m.key("Digit3")
        m.advance(frames=25)
        p3 = page(m)
        show(p3, "page 3")
        check("DSP writes" in p3[10], "the DSP write log is shown")

        m.pause()
        vol = F.Flush(marty=m).volume(0)
        names = set(vol.names())
        for n in ("SOUNDA1.TXT", "SOUNDB1.TXT"):
            check(n in names, "%s is on the guest's floppy" % n)
        if "SOUNDA1.TXT" in names:
            txta = vol.read("SOUNDA1.TXT").decode("latin-1")
            log = txta[txta.find("DSP writes"):][:400].split()
            check("E1" in log, "the A report's page 3 has the version "
                  "command E1h in the DSP write log (the lab's own writes "
                  "have pushed it out of the live log by the end)")
        if "SOUNDB1.TXT" in names:
            txt = vol.read("SOUNDB1.TXT").decode("latin-1")
            check(txt.startswith("THIS REPORT SAVES AS A TEXT FILE"),
                  "the B report opens with benchlib's banner")
            check("== end of report" in txt and "TRUNCATED" not in txt,
                  "the B report is complete (%d bytes)" % len(txt))
            check(txt.count("DMA lab") >= 1 and "NOAUTO" in txt,
                  "the B report carries the lab")
    if fails:
        print("snddiag: %d FAILED" % len(fails))
        return 1
    print("snddiag: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
