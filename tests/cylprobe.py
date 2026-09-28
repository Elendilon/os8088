#!/usr/bin/env python3
"""A machine booted off its HARD DISK earns the cylinder run too (SPEC.md 18.93.4).

    make && python3 tests/cylprobe.py [yes|no|undecided ...]

`boot_cylrun` is the FLOPPY boot sector's finding: its canary crosses a head
and checks the bytes, and only then may `dsk_xfer` carry a floppy run across
a head (18.91.1, 18.93.1). A machine that boots from its hard disk never runs
that sector, so before 18.93.4 it read 0 for the whole session and EVERY
floppy transfer on an installed machine went a track at a time - which the
owner met as a 100KB copy from a floppy to C: taking 17 seconds.

The kernel now asks the question itself, at the first floppy read that would
cross a head, and this row drives all three answers through the user's own
gesture - select, Edit > Copy, open C:, Edit > Paste - on a machine booted off
a fixture VHD:

  yes        random data. One dsk_cylchk, the verdict is YES, boot_cylrun is
             1 afterwards, and the floppy side reaches an 18-sector call
  no         the same, with a byte of each of the first TWO sectors past the
             head flip corrupted at the breakpoint - which is what a failing
             FDC hands back. The verdict must be NO, the run must be made
             again, and no floppy call after the probe may be longer than a
             track
  undecided  a file of ZEROS: every sector is one byte repeated and proves
             nothing, so DSK_CYLTRIES probes come back undecided, the question
             closes unanswered, and nothing crosses

In EVERY arm the copy on C: must be byte for byte the file on the floppy,
read back off the VHD on the host by tests/instdeep.py's FAT reader - which is
the assertion that matters for `no`: a probe that said no and then kept the
bad bytes would pass every other check here.

VERIFIED TO FAIL: with the verdict forced to YES whatever the fingerprints say
(`jne .no` after the compare taken out), `no` reports the YES verdict, 18
floppy reads where a NO takes ~30, and the copy on C: corrupt at the second
sector's flipped byte. With the `.hard` arm no longer opening the question,
all three arms report dsk_cyltry 0 at the desktop and `yes` a longest floppy
run of 9.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M                                       # noqa: E402
import os88ui                                               # noqa: E402
import instdeep as ID                                       # noqa: E402

MACHINE = "os8088_xt_hdd"
TEMPLATE = os.path.join(M.base_run_dir(), "media/hdds/default_xtide.vhd")
SIZE = 100000               # the owner's file was ~100KB: two copy chunks
NAME = "BIG.V88"
TRIES = 4                   # disk.inc's DSK_CYLTRIES
fails = []


def say(s):
    print("cylprobe: " + s, flush=True)


def fixture(tmp, data):
    src = os.path.join(tmp, NAME)
    open(src, "wb").write(data)
    vhd = os.path.join(tmp, "c.vhd")
    flop = os.path.join(tmp, "b.img")
    subprocess.check_call(
        ["python3", "tools/os88hdd.py", "--template", TEMPLATE, "--out", vhd,
         "--kernel", "build/kernel.sys", "--vbr", "build/boothd.bin",
         "--mbr", "build/mbr.bin", "--file", "HDD.DRV=build/hdd.drv"],
        cwd=ROOT, stdout=subprocess.DEVNULL)
    subprocess.check_call(["python3", "tools/os88disk.py", "-o", flop,
                           "--size", "360", src], cwd=ROOT,
                          stdout=subprocess.DEVNULL)
    return vhd, flop


def select(ui, name, win):
    i, _ = ui.entry(name, win)
    row = ui.scroll_to(i, win=win)
    ui.mo.click(*ui.row_xy(win, row))
    ui.settle(limit=10.0)


def corrupt(m, rec):
    """At dsk_cylchk: what a failing FDC hands back, past the head flip.

    TWO sectors, for two different reasons. The FIRST one past the flip is
    the one the probe fingerprints, so a byte there is what makes the verdict
    NO. The SECOND is the one nothing re-reads unless the whole run is made
    again - dsk_cylchk's own single-sector read repairs the first whatever it
    decides - so it is what makes the host-side compare of the copy able to
    fail: a NO that kept the run would leave this byte in the file on C:.
    """
    r = m.regs()
    k = m.read(m.sym("dsk_cylprb"), 1)[0]
    n = int.from_bytes(m.read(m.sym("dsk_run"), 2), "little")
    base = (r["es"] << 4) + r["bx"]
    for s in range(k, min(k + 2, n)):
        at = (base + s * 512 + 100) & 0xFFFFF
        m.write(at, bytes([m.read(at, 1)[0] ^ 0x5A]))
    return (k, n)


def arm(kind):
    say("--- %s ---" % kind)
    data = bytes(SIZE) if kind == "undecided" else os.urandom(SIZE)
    tmp = tempfile.mkdtemp(prefix="cylprobe-")
    try:
        vhd, flop = fixture(tmp, data)
        m = M.launch(None, apps=flop, machine=MACHINE,
                     extra=["--mount", "hd:0:" + vhd])
        try:
            ui = os88ui.UI(m)
            ui.ready(limit=240)
            s_run, s_try = m.sym("dsk_cylrun"), m.sym("dsk_cyltry")
            s_boot = m.sym("boot_cylrun")
            before = m.read(s_try, 1)[0]
            if before != TRIES:
                fails.append("%s: a hard-disk boot left dsk_cyltry at %d, not "
                             "%d - the question was never opened" %
                             (kind, before, TRIES))
            src = ui.open_drive("B")
            select(ui, NAME, src)
            ui.menu_pick("Edit", "Copy")
            ui.open_drive("C")
            m.disk(reset=True)
            hit = corrupt if kind == "no" else None
            with M.bp_trace(m, "dsk_cylchk", on_hit=hit) as tr:
                ui.menu_pick("Edit", "Paste")
                M.until(m, lambda mm: mm.read(mm.sym("fcp_busy"), 1)[0] == 0,
                        "the paste to finish", guest=120.0, poll=0.5)
                ui.settle(limit=60)
            d = m.disk()
            run, tries = m.read(s_run, 1)[0], m.read(s_try, 1)[0]
            boot = int.from_bytes(m.read(s_boot, 2), "little")
            say("probes %d, dsk_cylrun %d, dsk_cyltry %d, boot_cylrun %d, "
                "floppy reads %d, longest run %d"
                % (tr.n, run, tries, boot, d["reads"], d["longest_run"]))
            err = m.read(m.sym("fcp_err"), 1)[0]
            if err:
                fails.append("%s: the paste ended with fcp_err %d" % (kind, err))
        finally:
            m.quit()

        if kind == "yes":
            if tr.n != 1 or not run or not boot or tries:
                fails.append("yes: want one probe and a YES verdict, got %d "
                             "probes, cylrun %d, boot_cylrun %d, tries %d"
                             % (tr.n, run, boot, tries))
            if d["longest_run"] != 18:
                fails.append("yes: the longest floppy call was %d sectors, "
                             "not a cylinder's 18" % d["longest_run"])
        elif kind == "no":
            if tr.n != 1 or run or boot or tries:
                fails.append("no: want one probe and a NO verdict, got %d "
                             "probes, cylrun %d, boot_cylrun %d, tries %d"
                             % (tr.n, run, boot, tries))
            # the probe itself was one 18-sector call; everything after it
            # must be a track or less. The FDC counter's longest run cannot
            # say which call it was, so count the probe's own call instead:
            # a NO that went on crossing reads the file in about 12 calls, a
            # NO that stopped reads it in about 23
            if d["reads"] < 20:
                fails.append("no: only %d floppy reads - the transfer went on "
                             "crossing heads after a NO" % d["reads"])
        else:
            if tr.n != TRIES or run or boot or tries:
                fails.append("undecided: want %d undecided probes and the "
                             "question closed, got %d probes, cylrun %d, "
                             "boot_cylrun %d, tries %d"
                             % (TRIES, tr.n, run, boot, tries))

        got = ID.partition(vhd).read(NAME)
        if got != data:
            if got is None:
                fails.append("%s: %s is not on C: at all" % (kind, NAME))
            else:
                bad = next((i for i in range(min(len(got), len(data)))
                            if got[i] != data[i]), min(len(got), len(data)))
                fails.append("%s: the copy on C: is %d bytes and differs from "
                             "the floppy's %d at byte %d"
                             % (kind, len(got), len(data), bad))
        else:
            say("%s: the copy on C: is the floppy's %d bytes exactly"
                % (kind, len(data)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    kinds = sys.argv[1:] or ["yes", "no", "undecided"]
    for k in kinds:
        arm(k)
    for f in fails:
        say("FAIL: " + f)
    say("FAILED" if fails else "ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
