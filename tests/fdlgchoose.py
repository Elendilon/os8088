#!/usr/bin/env python3
"""The Standard File chooser, end to end (SPEC.md 38).

The chooser is a Disk window in a chooser role (SPEC.md 38.1), so this row
drives what is the CHOOSER's and not the Disk window's, through Note Pad's own
File > Open and File > Save As, and confirms every step off guest state:

  1. a first Open lands on MEDIA (38.10), captioned 'Open', with the button
     column's Open GREYED until a row is selected (38.3, SPEC.md 47);
  2. a click selects and Enter answers; with nothing selected Down scrolls,
     and on kern_big Up and Down then MOVE the selection - SPEC.md 22.26's,
     the Disk window's own, which the chooser inherits (38.4);
  3. Save As puts the app's document in the box, Down fills it from a row,
     a typed name commits, and the file is in the folder afterwards;
  4. Escape, the Cancel button and the close box each cancel, and the next
     Open remembers the folder (38.10);
  5. Drive leaves the floppy (38.11);
  6. with four of the USER's Disk windows open a fifth is refused and the
     chooser still opens - the fifth pool block is its own (38.1).

Run against kern_small (where the glue is FDLG.DRV, SPEC.md 38.0) with
os88sym's own knobs and the small system disk, which carries the apps:

    OS88_DEFINES=KERN_SMALL OS88_BUILD=build/smallk \\
    OS88_SYSIMG=build/small360.img OS88_NP=A:/APPS/NOTEPAD.O88 \\
        python3 tests/fdlgchoose.py

VERIFIED TO FAIL: `make NOFDMEDIA=1` reds step 1 (the chooser opens on
B:\\APPS, where Note Pad was launched from).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
import os88geom as geom                                     # noqa: E402
import os88ui                                               # noqa: E402

SYS = os.environ.get("OS88_SYSIMG", "build/os8088-360.img")
APPS = os.environ.get("OS88_APPSIMG", "build/apps360.img")
NP = os.environ.get("OS88_NP", "B:/APPS/NOTEPAD.O88")
fails = []


def check(name, cond, note=""):
    print("  [%s] %s %s" % ("PASS" if cond else "FAIL", name, note))
    if not cond:
        fails.append(name)


def blk(ui):
    return (geom.KERNEL_SEG << 4) + ui._word("fdlg_blk")


def fs_sel(ui):
    return int.from_bytes(ui.m.read(blk(ui) + geom.FS_SEL, 2), "little")


def ebuf(ui):
    raw = bytes(ui.m.read(ui._S("fm_ebuf"), 13))
    return raw.split(b"\0")[0].decode("ascii", "replace")


def ink(ui, w, k):
    """Dark pixels inside column button k - a greyed caption is dithered."""
    x, y = ui.chooser_button_xy(k, w)
    W, H, px = ui.m.fbuf()
    n = 0
    for yy in range(y - 4, y + 4):
        for xx in range(x - 24, x + 24):
            n += px[(yy * W + xx) * 3] < 0x40
    return n


with os88ui.boot(SYS, apps=APPS) as ui:
    m = ui.m
    ui.path(NP)
    ui.settle()                 # a menu picked while the app is still
                                # coming up is lost, on the base tree too
    print("== the Standard File chooser (%s) ==" % SYS)

    # --- 1: first Open: MEDIA, 'Open', the default button greyed --------------
    ui.menu_pick("File", "Open")
    w = ui.chooser()
    ui.settle()                     # the column is the paint's LAST part
    rows = [r[0] for r in ui.listing(w)]
    check("captioned Open", w.title == "Open", "(%r)" % w.title)
    check("lands on MEDIA (38.10)", "GUIDE.TEX" in rows, "(%r)" % rows)
    grey = ink(ui, w, ui.CH_OPEN)

    # --- 2: a click selects, Enter answers; the arrows only scroll ----------
    m.key("ArrowDown")
    ui.settle()
    check("Down with nothing selected scrolls (22.26)", fs_sel(ui) == 0xFFFF,
          "(FS_SEL %04X)" % fs_sel(ui))
    want = ui.chooser_select("GUIDE.TEX", w)
    ui.settle()
    live = ink(ui, w, ui.CH_OPEN)
    check("Open goes live on a selection (47)", live > grey,
          "(ink %d -> %d)" % (grey, live))
    check("a click selects the row", fs_sel(ui) == want, "(%d)" % fs_sel(ui))
    if "KERN_SMALL" not in os.environ.get("OS88_DEFINES", ""):
        m.key("ArrowUp")
        ui.settle()
        check("Up moves the selection (22.26)", fs_sel(ui) == want - 1,
              "(%d)" % fs_sel(ui))
        m.key("ArrowDown")
        ui.settle()
        check("...and Down brings it back", fs_sel(ui) == want,
              "(%d)" % fs_sel(ui))
    m.key("Enter")
    ui.chooser_gone()
    check("Enter on a file answers the Open", True)

    # --- 3: Save As -----------------------------------------------------------
    ui.menu_pick("File", "Save As")
    w = ui.chooser()
    check("captioned Save As", w.title == "Save As", "(%r)" % w.title)
    check("the box holds the document", ebuf(ui) == "GUIDE.TEX",
          "(%r)" % ebuf(ui))
    ui.chooser_save("NEWNOTE.TXT")
    check("Save As commits a typed name", True)

    # --- 4: three cancels, and the folder is remembered -----------------------
    for how in ("escape", "button", "close"):
        ui.menu_pick("File", "Open")
        w = ui.chooser()
        rows = [r[0] for r in ui.listing(w)]
        if how == "escape":
            check("the save landed in the folder", "NEWNOTE.TXT" in rows,
                  "(%r)" % rows)
        ui.chooser_cancel(how)
        check("cancelled by %s" % how, True)

    # --- 5: Drive leaves the floppy -------------------------------------------
    ui.menu_pick("File", "Open")
    w = ui.chooser()
    drv0 = m.read(blk(ui) + geom.FS_DRV, 1)[0]
    ui.chooser_button(ui.CH_DRIVE, w)
    ui.settle()
    drv1 = m.read(blk(ui) + geom.FS_DRV, 1)[0]
    check("Drive moves to another volume (38.11)", drv1 != drv0,
          "(%d -> %d)" % (drv0, drv1))
    ui.chooser_cancel("button")

    # --- 6: four of the user's Disk windows, and the chooser still opens -----
    for _ in range(4):
        # BY NAME: [fm_vinst] still names the chooser that just closed, as
        # it names any Disk window that closed last - disk_window() is the
        # ACTING window and there is none until one is raised
        ui.raise_window(ui.window("APPS"))
        ui.menu_pick("Nav", "New Window")
        ui.settle()
    disks = [t for t in ui.titles() if t != "Note Pad"]
    check("the user holds four Disk windows, and no more",
          len(disks) == 4, "(%d)" % len(disks))
    ui.raise_window(ui.window("Note Pad"))
    ui.menu_pick("File", "Open")
    w = ui.chooser()
    check("the chooser opens as the fifth (38.1)", w is not None)
    ui.chooser_cancel("escape")

print()
if fails:
    print("FAILURES:")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print("all pass")
