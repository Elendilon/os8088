#!/usr/bin/env python3
"""REALBOY.O88's log to file, written and read back.

    python3 tests/gblog.py

docs/REALBOY-SPEC.md section 14.1: Machine > Log keeps a record a second
and the close writes them as text to SYSTEM\\APPDATA\\REALBOY.LOG. This opens
GBDEMO.GB (tools/gbours.py, ours) on MartyPC's 5150 Hercules, turns the log
on, lets it run, closes the window, flushes B: and reads the file on the
host. It must hold the header naming the game, and at least eight records
whose seconds rise, whose speeds average the demo's full speed on this machine
(97-103%, tests/gbdemo.py) and which drew frames. Breaking the
record (rw_logsec never counting a record) leaves a file with no lines and
the row says so.
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88marty as M  # noqa: E402
import os88flush  # noqa: E402
import os88ui  # noqa: E402

LINE = re.compile(rb"^\s*(\d+)\.(\d)\s+(\d+)%\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+) ([WF])")


def main():
    rom = subprocess.check_output([sys.executable, os.path.join(ROOT, "tools", "gbours.py"),
                                   "gbdemo"], text=True).strip().splitlines()[-1]
    tmp = tempfile.mkdtemp(prefix="gblog-")
    gb = os.path.join(tmp, "GBDEMO.GB")
    with open(rom, "rb") as i, open(gb, "wb") as o:
        o.write(i.read())
    disk = os.path.join(tmp, "apps.img")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools", "os88disk.py"), "-o", disk,
                           "--size", "720", "--folder", "SYSTEM/APPDATA",
                           os.path.join(ROOT, "build", "realboy.o88"), gb],
                          stdout=subprocess.DEVNULL)
    after = disk + ".after"
    with os88ui.boot(os.path.join(ROOT, "build", "os8088-720.img"), apps=disk,
                     machine="os8088_5150_herc_sb_720_gla") as ui:
        w = ui.path("B:/GBDEMO.GB")
        M.guest_sleep(ui.m, 3)
        ui.menu_pick("Machine", "Log: Off")
        M.guest_sleep(ui.m, 12)
        ui.close(w)
        M.guest_sleep(ui.m, 4)                  # the log's and the save's writes
        os88flush.Flush(marty=ui.m).save(1, after)
    vol = os88flush.Volume(open(after, "rb").read())
    fails = []
    try:
        text = vol.read("SYSTEM/APPDATA/REALBOY.LOG")
    except Exception as e:                      # noqa: BLE001
        print("FAIL gblog: the close wrote no SYSTEM\\APPDATA\\REALBOY.LOG (%s)" % e)
        return 1
    lines = text.split(b"\r\n")
    print("gblog: REALBOY.LOG %d bytes, %d lines" % (len(text), len(lines)))
    for l in lines[:6]:
        print("   | " + l.decode("latin-1"))
    if not lines[0].startswith(b"REALBOY LOG - GBDEMO.GB"):
        fails.append("the header is %r" % lines[0][:60])
    recs = [LINE.match(l) for l in lines]
    recs = [r for r in recs if r]
    secs = [int(r.group(1)) * 10 + int(r.group(2)) for r in recs]
    if len(recs) < 8:
        fails.append("%d records, not at least 8" % len(recs))
    elif secs != sorted(secs):
        fails.append("the seconds do not rise: %s" % secs)
    else:
        mid = recs[2:-1]
        sp = [int(r.group(3)) for r in mid]
        dr = [int(r.group(5)) for r in mid]
        # a second at a time the speed jitters (frames run in bursts that
        # straddle a second's edge: 89-106 here, and the field run's "90 to
        # 110"); the run as a whole is the demo's full speed
        run = sum(int(r.group(4)) for r in mid)
        ticks = (secs[-2] - secs[1]) / 10.0
        avg = 100.0 * run / (ticks * 59.7275) if ticks else 0
        print("gblog: %d frames over %.1f s = %.1f%%; a second at a time %s" % (run, ticks, avg, sp))
        if not 97 <= avg <= 103:
            fails.append("the demo ran at %.1f%% over the log, not ~100%%" % avg)
        if not all(60 <= v <= 140 for v in sp):  # (a draw of ~0.4 s on this
            fails.append("a second's speed outside 60-140%%: %s" % sp)  # 8088)
        if not all(v > 0 for v in dr):
            fails.append("seconds with no frame drawn: %s" % dr)
    for f in fails:
        print("FAIL gblog: " + f)
    print("gblog: %s" % ("PASS" if not fails else "FAIL"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
