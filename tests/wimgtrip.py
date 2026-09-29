#!/usr/bin/env python3
"""Does Write Img... put an image on a floppy, byte for byte?

    python3 tests/wimgtrip.py

SPEC.md 18.99.8 and 38.6.2, and docs/FIELD-NOTES.md 32. `tests/diskclone.py`
drives the command as far as the dialog and a cancel, and says why it stops
there: an image of a 360KB disk is 720 sectors and a 360KB volume's data area
is 708, so on a machine whose drives are all 360KB there is nowhere to put the
FILE. This row is the other half, on `os8088_5150_cga_720b_gla` - a 360KB A:
and a 720KB B:, which is also the reporter's own 5150.

The fixture is two artefacts `make all` already builds: `apps360.img` put as a
FILE on a 720KB data disk in B:, and the 360KB system disk in A: as the
target. The apps disk is not the system disk, so the assertion cannot pass by
the write doing nothing - that is checked before the write, as the positive
control, and after it drive 0 must BE the apps image, every one of its 720
sectors.

What it caught first, before it existed: the Standard File dialog handed its
callback a size of 0:0 (SPEC.md 38.6.2), and Write Img sizes the geometry off
that figure alone, so every image was refused as 'Not a disk image'. The leg
that reads CL_TOT after the dialog is that regression, asserted on the job
block rather than inferred from a toast.
"""
import os
import re
import sys

sys.path.insert(0, "tools")
sys.path.insert(0, "tests/unit")
import os88marty as M                                     # noqa: E402
import os88ui                                             # noqa: E402
import os88build                                          # noqa: E402
from os88geom import WIN_SIZE, MAX_WIN, W_X, W_Y, W_TITLE, W_FLAGS  # noqa
from harness import check, done                           # noqa: E402

MACHINE = "os8088_5150_cga_720b_gla"
SYS = "build/os8088-360.img"
IMAGE = "build/apps360.img"
IMGNAME = "APPS360.IMG"


def equ(path, name):
    src = open(path).read()
    m = re.search(r"^%s\s+equ\s+(\d+)" % name, src, re.M)
    if not m:
        sys.exit("%s: no `%s equ`" % (path, name))
    return int(m.group(1))


FS_EDIT = equ("kernel/files.inc", "FS_EDIT")
FS_SIZE = equ("kernel/files.inc", "FS_SIZE")
CL_STEP = equ("kernel/clone.inc", "CL_STEP")
CL_TOT = equ("kernel/clone.inc", "CL_TOT")
CL_SPT = equ("kernel/clone.inc", "CL_SPT")
CLS_WIMG = equ("kernel/clone.inc", "CLS_WIMG")
FD_BX1 = equ("kernel/fdlg.inc", "FD_BX1")
FD_BX2 = equ("kernel/fdlg.inc", "FD_BX2")
FD_BY2 = equ("kernel/fdlg.inc", "FD_BY2")
FD_BH = equ("kernel/fdlg.inc", "FD_BH")
FD_ROW0 = equ("kernel/fdlg.inc", "FD_ROW0")
FD_ROWH = equ("kernel/fdlg.inc", "FD_ROWH")
FD_TEXTX = equ("kernel/fdlg.inc", "FD_TEXTX")
TITLE_H = 18            # SPEC.md 11: a window's content starts 18 below it


def u16(b, o=0):
    return b[o] | (b[o + 1] << 8)


def dialog(m):
    """The Open dialog's (x, y), or None - found by its TITLE pointer."""
    want = m.sym("fdlg_s_topen") - (M.KERNEL_SEG << 4)
    blob = m.read(m.sym("wm_wins"), WIN_SIZE * MAX_WIN)
    for i in range(MAX_WIN):
        r = blob[i * WIN_SIZE:(i + 1) * WIN_SIZE]
        if u16(r, W_FLAGS) & 2 and u16(r, W_TITLE) == want:
            return u16(r, W_X), u16(r, W_Y)
    return None


def edit(m):
    pool = m.sym("fm_pool")
    for slot in range(4):
        b = m.read(pool + slot * FS_SIZE, FS_SIZE)
        if b[FS_EDIT]:
            return b[FS_EDIT]
    return 0


def job(m, off, n=1):
    seg = u16(m.read(m.sym("clo_seg"), 2))
    if not seg:
        return None
    b = m.readseg(seg, off, n)
    return b[0] if n == 1 else u16(b)


# PER-PROCESS, for docs/WRITING-TESTS.md 5.5: the runner runs rows side by
# side and scratch_disk would otherwise be one file three machines rebuild.
FIX = M.scratch_disk("build/wimgtrip-%d.img" % os.getpid(), IMAGE, size=720)
want = open(os88build.at(IMAGE), "rb").read()
flush = os.path.abspath(os88build.at("build/wimgtrip-%d.a" % os.getpid()))

try:
    with os88ui.boot(SYS, apps=FIX, machine=MACHINE) as ui:
        m = ui.m
        print("== %s : Write Img... round trip (SPEC.md 18.99.8) ==" % MACHINE)
        ui.open_drive("A")

        m.flush(0, flush)
        before = open(flush, "rb").read()
        check(before != want, "the target is NOT the image before the write",
              "the positive control: A: is the system disk and the image is "
              "the apps disk, so a write that did nothing cannot pass below")

        ui.menu_pick("File", "Write Img...")
        M.settle(m)
        d = dialog(m)
        check(d is not None, "Write Img... opens the Open dialog",
              "fm_c_wimg is fdlg_open_x and nothing else (SPEC.md 22.21.5)")
        if d is None:
            done("wimgtrip")
        cx, cy = d[0] + 1, d[1] + TITLE_H
        for _ in range(4):                  # Drive walks the volumes
            if m.read(m.sym("disk_drive"), 1)[0] == 1:
                break
            ui.mo.click(cx + (FD_BX1 + FD_BX2) // 2, cy + FD_BY2 + FD_BH // 2)
            M.settle(m)
        check(m.read(m.sym("disk_drive"), 1)[0] == 1,
              "...and its Drive button reaches B:", "",
              got=m.read(m.sym("disk_drive"), 1)[0], want=1)
        ui.mo.click(cx + FD_TEXTX + 24, cy + FD_ROW0 + FD_ROWH // 2)
        M.settle(m)
        name = bytes(m.read(m.sym("fdlg_name"), 13)).split(b"\0")[0]
        check(name == IMGNAME.encode(), "a click on the row names the image",
              "", got=name, want=IMGNAME.encode())

        m.key("Enter")
        M.settle(m)
        check(ui.toast()[0] != "Not a disk image",
              "the dialog's answer is NOT refused as 'Not a disk image'",
              "SPEC.md 38.6.2: fdlg_commit took the size AFTER fdlg_close had "
              "freed the listing it looks the name up in, so every Open "
              "reported 0:0 and clo_geom_img matched no layout",
              got=ui.toast()[0], want="(anything else)")
        check(edit(m) == 7 and job(m, CL_STEP) == CLS_WIMG,
              "...it arms the confirmation instead (CLS_WIMG)",
              "FS_EDIT 7 is the cloner's mode (SPEC.md 22.21.1)",
              got=(edit(m), job(m, CL_STEP)), want=(7, CLS_WIMG))
        check((job(m, CL_TOT, 2), job(m, CL_SPT, 2)) == (720, 9),
              "...with the geometry of a 360KB disk, from the SIZE",
              "clo_geom_img: 368,640 bytes is 720 sectors of 9 a track - "
              "this is the dialog's DX:CX arriving intact",
              got=(job(m, CL_TOT, 2), job(m, CL_SPT, 2)), want=(720, 9))

        m.key("Enter")
        M.settle(m, limit=400)
        check(ui.toast()[0] == "Wrote A:", "Enter writes it: 'Wrote A:'", "",
              got=ui.toast()[0], want="Wrote A:")
        check(edit(m) == 0 and u16(m.read(m.sym("clo_seg"), 2)) == 0,
              "...the mode ends and the claim goes back", "")

        m.flush(0, flush)
        after = open(flush, "rb").read()
        bad = [i // 512 for i in range(0, len(want), 512)
               if after[i:i + 512] != want[i:i + 512]]
        check(len(after) == len(want) and not bad,
              "drive 0 IS the image, every sector of it",
              "an image is the disk and nothing else: a wrong LBA, a lost "
              "sector 0 (SPEC.md 18.99.2) or a chunk read out of the file at "
              "the wrong offset all show here as sector numbers",
              got="%d sectors differ, first %s" % (len(bad), bad[:8]),
              want="0 sectors differ")
finally:
    for p in (FIX, FIX + ".args", flush):
        try:
            os.remove(p)
        except OSError:
            pass

done("wimgtrip")
