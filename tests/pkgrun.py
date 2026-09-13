#!/usr/bin/env python3
"""OSAPI_PKG_RUN runs an image out of memory, and refuses two (SPEC.md 21.5).

    make && make pkgrun && python3 tests/pkgrun.py

The slot exists for the Wire (SPEC.md 26.7), which fetches a `.O88` over the
network into a claim and has no file to name. This is the gate on it, and it
is the `mseg`/`covl` shape: a TEST package that no shipped floppy carries,
built by `make pkgrun`, booted in B: and asked three questions.

**MARTYPC, THROUGH `os88ui`, AND IT USED TO BE HAND-ROLLED QEMU.** This row's
own header argued the other way - *"nothing here is a time, and the three
answers are all state; MartyPC would do as well and costs ten times the wall
clock"* - and that is exactly the argument docs/TESTING.md refuses: `pkgrun`
is on none of the seven entries of the QEMU list, and "it is quicker" is not
one of them. It also did not survive its own evidence. What it cost instead
was a row that FLAKES, and in the worst way a row can:

  * it drove the desktop with REMEMBERED COORDINATES - `dbl(600, 110)` for the
    B: zone, `time.sleep(8)`, then `dbl(160, 144)` for "the second row" - so
    every wait was a host sleep on a guest whose rate moves with the box's
    load (docs/plans/SOAK-PARALLEL.md 1), and a miss raised nothing;
  * and it read `inst_tab` - 384 bytes - off a RUNNING machine in its poll
    loop. A record is 32 bytes the kernel writes field by field, so a read
    landing mid-write returns a live record with a torn name. That is what a
    soak caught: `instances: Disk@D1E4, KBR@N@9F00, ...`, two names of
    garbage, reported as `no live instance named PKGRUN: the gate's own
    package did not launch` - while the SCREENSHOT saved beside it showed
    PKGRUN's window with all three answers `ok` and HELLO's window open
    behind it. The machine was right and the reading was wrong, which is the
    single most expensive shape a test failure can have.

So the navigation is `ui.path("B:/PKGRUN.O88")` - every step confirmed against
the guest's own tables, no coordinate anywhere - and every read of the
instance table goes through `os88marty.quiesce`, which is `settle`'s signal
applied to those bytes: identical readings a GUEST interval apart, so a torn
record cannot be the one that is believed.

WHAT IT ASSERTS, and the first one is asserted against the KERNEL:

  A  an instance named HELLO is LIVE in `inst_tab` - the kernel's own table,
     read through the symbol map, so the pass does not rest on the test
     package's opinion of what happened - AND the region that instance names
     is byte-for-byte `build/hello.o88`. The second half is not belt and
     braces: the slot's first version lost the source OFFSET (it read it out
     of the caller's segment instead of the kernel's) and copied from
     whatever was next to the caller's claim, which still passed
     `ld_check_hdr`, still registered an instance, and then far-called a
     dispatcher that was not one. `hello.o88` is the shipped one and not a
     fixture: the claim is that the slot runs an ORDINARY package.
  B  a spoiled magic answers CF=1 with AL = LD_EBAD.
  C  header flags bit 2 - a package carrying PARTS (SPEC.md 20.12), which are
     read out of a FILE that does not exist here - answers CF=1 / LD_EBAD too,
     and by a different route: the flags test is made before ld_check_hdr,
     which allows the bit.

B and C also say something A cannot: the region and the instance record a
refused load reserved were given back. Three loads happen in this session and
the heap is small; a leak of either shows up as C failing with LD_ENOMEM.

HOW THE VERDICT IS READ. The test package writes a 14-byte block at offset 32
of its own image - immediately after the header, before any code - opening
with the tag 'PR'. The host finds the live instance named PKGRUN in
`inst_tab`, takes its `I_SPTR` (the region's base segment, SPEC.md 20.1) and
reads the block there. No map of the test package is needed and none can go
stale; the tag is the check that the pointer was followed correctly.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import os88build                                             # noqa: E402
import os88marty                                             # noqa: E402
import os88ui                                                # noqa: E402

# THE GLaBIOS TWIN BY NAME, which is what t_machines requires: the period
# 5150 ROM is not in this tree (CONTRIBUTING.md 6), so naming it runs on
# the twin anyway on a box without a private copy - and says nothing.
MACHINE = sys.argv[1] if len(sys.argv) > 1 else "os8088_5150_cga_gla"

# kernel/instance.inc, mirrored - the record layout is ABI (SPEC.md 20.9)
I_STATE, I_SPTR, I_NAME, I_RECSZ, INST_MAX = 0, 6, 12, 32, 12

PR_OFF = 32                     # the verdict block, at the head of the image
PR_LEN = 14
LD_EBAD = 2                     # SPEC.md 21.4


fails = []


def say(msg):
    print("  " + msg)
    sys.stdout.flush()


def build():
    """The kernel under test and the gate's own disk. The row is builds=True
    (tests/suite.py) precisely so this may write build/, and a reader running
    the script by hand should not have to know the target's name."""
    subprocess.run(["make", "-s", "build/os8088-360.img", "pkgrun"], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL)


def _table(ui):
    """The whole instance table, as bytes. ONE read, so every record in a
    snapshot came from one moment."""
    return ui.m.read(ui.sym("inst_tab"), I_RECSZ * INST_MAX)


def _decode(b):
    """[(name, sptr)] of every LIVE record in a snapshot."""
    out = []
    for i in range(INST_MAX):
        r = b[i * I_RECSZ:(i + 1) * I_RECSZ]
        if r[I_STATE] != 1:
            continue
        name = bytes(r[I_NAME:I_NAME + 16]).split(b"\0")[0].decode(
            "ascii", "replace")
        out.append((name, r[I_SPTR] | (r[I_SPTR + 1] << 8)))
    return out


def instances(ui, settled=True):
    """[(name, sptr)] of every LIVE instance record.

    `settled` reads it through `quiesce` - the same bytes twice a guest
    interval apart - because a 32-byte record is written field by field and a
    read that lands mid-write returns a live record with a torn name. That is
    not hypothetical; it is what this row used to fail as."""
    if settled:
        os88marty.quiesce(ui.m, lambda: _table(ui),
                          what="the instance table to stop changing")
    return _decode(_table(ui))


def slots(ui):
    """Every record, live or not, with its name - the diagnostic behind the
    entry-count note: two PKGRUN instances would show here even if the second
    had gone."""
    b = _table(ui)
    out = []
    for i in range(INST_MAX):
        r = b[i * I_RECSZ:(i + 1) * I_RECSZ]
        nm = bytes(r[I_NAME:I_NAME + 16]).split(b"\0")[0].decode(
            "ascii", "replace")
        if r[I_STATE] or nm:
            out.append("%d:%s/%d@%04X" % (i, nm or "-", r[I_STATE],
                                          r[I_SPTR] | (r[I_SPTR + 1] << 8)))
    return " ".join(out)


def seg_of(ui, want, settled=True):
    return dict(instances(ui, settled)).get(want, 0)


def main():
    os.chdir(ROOT)
    build()

    # THE 360KB PAIR, because the machine is a 5150 and a 5150 has 360KB
    # drives. `make pkgrun` builds both geometries; the QEMU version took the
    # 1.44MB one because QEMU's floppy will take any image, and handing it to
    # a period machine is a boot that never reaches a desktop.
    with os88ui.boot("build/os8088-360.img", apps="build/pkgrun360.img",
                     machine=MACHINE) as ui:
        # --- open B: and launch the gate's own package ----------------------
        # By NAME. The drive, the row and the launch are each confirmed against
        # the guest's own tables, so a miss raises HERE naming what it saw
        # rather than twenty steps later as a missing instance.
        ui.path("B:/PKGRUN.O88")

        # --- wait for the package to finish its three checks -----------------
        # On [pr_done] in its own image, on the GUEST's clock. The package
        # guards itself on its entry count, so what this waits for is the
        # checks being FINISHED and not merely the wake having arrived.
        def done():
            seg = seg_of(ui, "PKGRUN", settled=False)
            return bool(seg) and bool(ui.m.read(seg * 16 + PR_OFF, 3)[2])

        os88marty.until(ui.m, lambda _: done(),
                        "PKGRUN to finish its three checks", limit=180.0)

        # --- what the KERNEL says -------------------------------------------
        live = instances(ui)
        names = [n for n, _ in live]
        say("instances: " + (", ".join("%s@%04X" % (n, g) for n, g in live)
                             or "(none)"))
        say("slots: " + slots(ui))
        seg = dict(live).get("PKGRUN", 0)
        if not seg:
            fails.append("no live instance named PKGRUN: the gate's own "
                         "package did not launch, so nothing below ran")
        if "HELLO" not in names:
            fails.append("A: no live instance named HELLO - OSAPI_PKG_RUN did "
                         "not run the image (SPEC.md 21.5)")
        else:
            # --- AND THE COPY LANDED, byte for byte -------------------------
            # An instance existing says the slot returned; it does not say it
            # copied the RIGHT bytes. The first version of the slot read the
            # source OFFSET out of the caller's segment instead of the
            # kernel's and copied from whatever was there - which passed
            # ld_check_hdr (that reads the caller's bytes, before the copy),
            # registered an instance, and then far-called a dispatcher that
            # was not one. So the region is compared against the FILE.
            hseg = dict(live)["HELLO"]
            want = open(os88build.at("build/hello.o88"), "rb").read()
            got = bytes(ui.m.read(hseg * 16, min(len(want), 512)))
            if got != want[:len(got)]:
                n = next((i for i in range(len(got))
                          if got[i] != want[i]), 0)
                fails.append("A: the copy is wrong at byte %d - the region "
                             "holds %02X where build/hello.o88 has %02X. The "
                             "instance exists, so the slot RETURNED; what it "
                             "copied is not the image it was given "
                             "(SPEC.md 21.5)" % (n, got[n], want[n]))

        # --- ...and what the package recorded --------------------------------
        if seg:
            b = ui.m.read(seg * 16 + PR_OFF, PR_LEN)
            say("verdict raw: " + bytes(b).hex())
            if bytes(b[:2]) != b"PR":
                fails.append("the verdict block at PKGRUN:%04X is %r, not "
                             "'PR' - I_SPTR did not name the image"
                             % (PR_OFF, bytes(b[:2])))
            else:
                done_n, ok = b[2], b[3]
                cfa, cfb, cfc = b[4], b[5], b[6]
                ala, alb, alc = b[7], b[8], b[9]
                ferr, ln, ent = b[10], b[11] | (b[12] << 8), b[13]
                say("pkgrun: done %d ok %02X  A cf%d al%d  B cf%d al%d  "
                    "C cf%d al%d  ferr %d len %d entries %d"
                    % (done_n, ok, cfa, ala, cfb, alb, cfc, alc, ferr, ln,
                       ent))
                if ent != 1:
                    # REPORTED, NOT FAILED. More than one wake per post is the
                    # kernel putting one back that a drag or a launch ate
                    # (SPEC.md 74.1.1); the package's entry-count guard is what
                    # makes it harmless, and `done` says which entry finished.
                    say("note: the wake handler was entered %d times and the "
                        "checks finished on entry %d - the guard held"
                        % (ent, done_n))
                    say("note: every instance slot: " + slots(ui))
                if not done_n:
                    fails.append("the wake handler never ran to the end - the "
                                 "checks did not happen")
                elif ferr and not ok:
                    fails.append("OSAPI_FILE_READ of HELLO.O88 answered "
                                 "FERR %d, so no check ran" % ferr)
                else:
                    if not ln:
                        fails.append("HELLO.O88 read back as 0 bytes")
                    if (cfa, ala) != (0, 0):
                        fails.append("A: the slot answered CF=%d AL=%d, want "
                                     "CF=0 AL=0" % (cfa, ala))
                    if (cfb, alb) != (1, LD_EBAD):
                        fails.append("B: a spoiled magic answered CF=%d AL=%d, "
                                     "want CF=1 AL=%d (LD_EBAD)"
                                     % (cfb, alb, LD_EBAD))
                    if (cfc, alc) != (1, LD_EBAD):
                        fails.append("C: header flags bit 2 answered CF=%d "
                                     "AL=%d, want CF=1 AL=%d (LD_EBAD) - a "
                                     "package with PARTS reads them from its "
                                     "own FILE (SPEC.md 20.12)"
                                     % (cfc, alc, LD_EBAD))

        if fails:
            shot = os.path.join(ROOT, "build", "pkgrun.png")
            try:
                w, h, data = ui.m.fbuf()
                os88marty.write_png_rgb(shot, w, h, data)
                say("screen: " + shot)
            except Exception as e:                            # noqa: BLE001
                say("screen: could not be taken (%s)" % e)

    for f in fails:
        print("FAIL " + f)
    print("pkgrun: %s" % ("OK - the slot ran one and refused two"
                          if not fails
                          else "%d assertion(s) failed" % len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
