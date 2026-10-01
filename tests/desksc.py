#!/usr/bin/env python3
"""SPEC.md 26.8: DESKTOP SHORTCUTS, end to end on an XT.

    make && python3 tests/desksc.py [--shots DIR] [--machine NAME]

One boot of the shipped 360KB pair on a VGA XT (os8088_xt_vga), and every
claim 26.8 makes is asked of the GUEST'S OWN STATE rather than of a picture:

  A  a drag of B:\\APPS\\CALC.O88 out of its Disk window onto bare desktop
     makes ONE shortcut: the table claim exists, its row 0 names volume 1,
     the WHOLE path `\\APPS\\CALC.O88`, kind 1 (a package), the header-name
     caption `CALCULATOR`, the BADGE drawn beside the picture to the
     pixel (inverted with it when selected), and the
     cell nearest the drop. The Cut the drag armed is DISARMED, and the
     toast says the settings were saved.
  B  SYSTEM.CFG on A: carries the TRAILER: the live row verbatim, then
     'SC', SC_VER, a count of 1 - read straight off the host's copy of the
     floppy image, which is the file the guest wrote.
  C  a double-click on the shortcut OPENS the Calculator.
  D  a drag of the shortcut moves it to the nearest free cell under the
     release, and only that.
  E  after a REBOOT the shortcut is back, cell and caption and all - the
     boot reader in .ovl, through the trailer.
  F  Delete with the shortcut selected removes it; the claim goes with the
     last one, and SYSTEM.CFG goes back to having no trailer at all.
  G  a FOLDER's shortcut (B:\\MEDIA) is kind 2 and captioned with its name,
     and Enter on it, selected, opens a Disk window there.
  H  a DOCUMENT's (MEDIA\\GUIDE.TEX) keeps its full 8.3 caption and a
     double-click opens it in its program, through the association.
  I  a shortcut whose target is GONE (the folder's, its path rewritten in
     guest memory to one that does not exist) says `Shortcut not found (B:)`
     on a double-click, naming its drive.
  J  a right-click on the document's and `Remove Shortcut` removes that one
     only.
  K  Locator's File > Remove Shortcut (its label exact) removes the selected
     one, the last, and the claim goes with it.

**BREAK IT ON PURPOSE** (docs/WRITING-TESTS.md 1): take `call sc_m_ser` out
of driver.inc's CFG_SAVE and B fails (no trailer) and E fails (nothing comes
back); take the `mov byte [fcp_cbop], FCP_NONE` out of files.inc and A fails
on the clipboard.

The floppies are COPIED to a scratch directory first: the guest writes
SYSTEM.CFG, and the shipped images must not be the ones it writes to.
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import os88ui      # noqa: E402
import os88fat     # noqa: E402
import os88marty   # noqa: E402

ROOT = os.path.join(HERE, "..")
SC_REC = 128
SC_MAX = 16
DESK_SC0 = 16
SC_PX, SC_X0, SC_W, SC_H = 104, 4, 96, 30
DESK_ZY0 = 32
FCP_NONE = 0

fails = []


def check(cond, what):
    print("   %s  %s" % ("ok " if cond else "FAIL", what))
    if not cond:
        fails.append(what)
    return cond


def cfg_bytes(img):
    """SYSTEM.CFG off a 360KB image, by the independent FAT12 reader."""
    try:
        return bytes(os88fat.Fat12(img).read("SYSTEM.CFG"))
    except KeyError:                    # the shipped disk carries none until
        return b""                      # something is saved


def trailer(data):
    """(count, rows) of SYSTEM.CFG's shortcut trailer, or (0, []) for none."""
    if len(data) < 4 or data[-4:-2] != b"SC":
        return 0, []
    n = data[-1]
    rows = data[-4 - n * SC_REC:-4]
    return n, [rows[i * SC_REC:(i + 1) * SC_REC] for i in range(n)]


def live_cfg(m, tmp):
    """SYSTEM.CFG as the GUEST's drive A: holds it now. MartyPC writes no
    image back on its own (os88marty.flush), so it is flushed - paused, so
    a commit in flight cannot be caught half-written - to a file of ours."""
    out = os.path.join(tmp, "flushed.img")
    m.pause()
    try:
        m.flush(0, out)
    finally:
        m.run()
    return cfg_bytes(out)


def shot(m, path):
    w, h, data = m.fbuf()
    os88marty.write_png_rgb(path, w, h, data)


def cstr(b):
    return bytes(b).split(b"\0")[0].decode("latin-1")


def table(ui):
    seg = ui._word("sc_seg")
    n = ui._byte("sc_nrows")
    if not seg:
        return seg, n, []
    raw = bytes(ui.m.read(seg << 4, n * SC_REC))
    return seg, n, [raw[i * SC_REC:(i + 1) * SC_REC] for i in range(n)]


# sc_bdg's ten rows, MSB leftmost: drawn with its bottom on the picture's
# and one column clear of its left edge (SPEC.md 26.8.3)
BADGE = (0xFFC0, 0x8040, 0x8740, 0x8340, 0x8540,
         0xB840, 0xA040, 0xA040, 0x8040, 0xFFC0)


def badge_on_glass(m, cx, cy, inverted):
    """The badge's 10x10 pixels, against BADGE. A 1bpp card is read out of
    guest MEMORY (`vram`, a lit bit is white): MartyPC's rendered Hercules
    frame starts some pixels into the screen, so `fbuf` coordinates are not
    the kernel's there. VGA has no flat framebuffer, so it is the card's own
    rasterised frame - which is 1:1 on that card."""
    bx, by = cx + (SC_W - 16) // 2 - 11, cy + 16 - 10
    if m.cmd(cmd="video")["type"] == "vga":
        w, _h, data = m.fbuf()
        black = lambda x, y: sum(data[(y * w + x) * 3:(y * w + x) * 3 + 3]) \
            < 384
    else:
        _w, _h, rows = m.vram()
        black = lambda x, y: not rows[y][x]
    bad = 0
    for r in range(10):
        for c in range(10):
            want = bool(BADGE[r] >> (15 - c) & 1) != inverted
            bad += black(bx + c, by + r) != want
    return bad


def cell_xy(col, row, zstep, x0):
    return (x0 + SC_X0 + col * SC_PX, DESK_ZY0 + row * zstep)


def saved(ui):
    """Wait for THIS gesture's save. toast_buf is not cleared when a strip
    goes away (os88ui.toast), so an earlier 'Settings Saved' would answer
    at once - and the next check would run while CTRL.DRV is still being
    read. So the buffer is cleared before each gesture (`fresh`)."""
    return ui.wait_toast(says="Saved", limit=90)


def fresh(ui):
    ui.m.write(ui._S("toast_buf"), b"\0")


def bare_point(ui, want):
    """`want` if no window covers it, else raise - the test aims at bare
    desktop and a window there would turn a drop into a MOVE (SPEC.md 22.4)."""
    x, y = want
    for w in ui.windows():
        if w.visible and w.x <= x < w.x + w.w and w.y <= y < w.y + w.h:
            raise os88ui.UIError("window %r covers the drop point %r"
                                 % (w.title, want))
    return want


def main():
    shots = None
    machine = "os8088_xt_vga"
    if "--machine" in sys.argv:         # a 1bpp adapter is where a drawing
        machine = sys.argv[sys.argv.index("--machine") + 1]  # change is LOOKED at
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="desksc-")
    sysimg = os.path.join(tmp, "os8088-360.img")
    appimg = os.path.join(tmp, "apps360.img")
    bdir = os.path.join(ROOT, os.environ.get("OS88_BUILD", "build"))
    shutil.copy(os.path.join(bdir, "os8088-360.img"), sysimg)
    shutil.copy(os.path.join(bdir, "apps360.img"), appimg)
    before = cfg_bytes(sysimg)
    print("SYSTEM.CFG before: %d bytes, trailer %r" % (len(before),
                                                       trailer(before)[0]))

    with os88ui.boot(sysimg, apps=appimg, machine=machine) as ui:
        m = ui.m
        zstep = ui._word("desk_zstep")
        x0 = ui._word("vid_band_x0")

        # --- A: create ----------------------------------------------------
        print("A: drag B:\\APPS\\CALC.O88 onto the desktop")
        ui.open_drive("B")
        ui.open("APPS")
        win = ui.disk_window()
        idx, _ty = ui.entry("CALC.O88", win)
        row = ui.scroll_to(idx, win=win)
        px, py = ui.row_xy(win, row)
        # the bottom-left cell's centre, which the default windows leave bare
        tx, ty = cell_xy(0, ui._word("desk_rows") - 1, zstep, x0)
        tx, ty = bare_point(ui, (tx + SC_W // 2, ty + SC_H // 2))
        fresh(ui)
        ui.mo.drag(px, py, tx, ty)
        saved(ui)
        seg, n, rows = table(ui)
        check(seg != 0, "the table claim exists (sc_seg %#06x, %d rows)"
              % (seg, n))
        live = [r for r in rows if r[0] != 0xFF]
        check(len(live) == 1, "exactly one live shortcut (%d)" % len(live))
        r0 = rows[0] if rows else bytes(SC_REC)
        check(r0[0] == 1, "row 0 names volume 1, B: (%d)" % r0[0])
        check(cstr(r0[5:51]) == "\\APPS\\CALC.O88",
              "the WHOLE path (%r)" % cstr(r0[5:51]))
        check(r0[3] == 1, "kind 1, a package (%d)" % r0[3])
        check(cstr(r0[51:64]) == "CALCULATOR",
              "the header-name caption (%r)" % cstr(r0[51:64]))
        col, rw = r0[1], r0[2]
        check((col, rw) == (0, ui._word("desk_rows") - 1),
              "the cell nearest the drop (%d,%d)" % (col, rw))
        cx, cy = cell_xy(col, rw, zstep, x0)
        ui.mo.to(cx + SC_PX + SC_W, cy)    # the arrow is drawn INTO the
        ui.settle()                        # framebuffer: off the badge first
        sel = ui._byte("desk_sel") == DESK_SC0
        bad = badge_on_glass(m, cx, cy, sel)
        check(bad == 0, "the badge is on the glass beside the picture "
              "(%d of 100 pixels wrong, %s)"
              % (bad, "selected" if sel else "not selected"))
        check(ui._byte("fcp_cbop") == FCP_NONE,
              "the Cut the drag armed is DISARMED (fcp_cbop %d)"
              % ui._byte("fcp_cbop"))
        if shots:
            ui.settle()
            shot(m, os.path.join(shots, "a_created.png"))

        # --- B: the file --------------------------------------------------
        print("B: SYSTEM.CFG's trailer")
        after = live_cfg(m, tmp)
        cnt, frows = trailer(after)
        check(cnt == 1, "the trailer's count is 1 (%d, file %d bytes)"
              % (cnt, len(after)))
        check(frows and frows[0] == r0, "the row is the claim's, verbatim")
        check(after[:8] == b"O88CFG\0\0",
              "the settings head is SYSTEM.CFG's own container")

        # --- C: open ------------------------------------------------------
        print("C: double-click the shortcut")
        cx, cy = cell_xy(col, rw, zstep, x0)
        cx += SC_W // 2
        cy += 8
        before_t = set(ui.titles())
        ui.mo.dblclick(cx, cy)
        ui._wait(lambda: any(t.upper().startswith("CALC")
                             for t in ui.titles()),
                 "a Calculator window", 60,
                 snapshot=lambda: ui.titles())
        check(True, "the Calculator opened (%r)"
              % sorted(set(ui.titles()) - before_t))
        if shots:
            ui.settle()
            shot(m, os.path.join(shots, "c_opened.png"))
        for w in ui.windows():                 # close it again, so the
            if w.title.upper().startswith("CALC"):  # drag below has bare
                ui.close(w)                         # desktop under it

        # --- D: move ------------------------------------------------------
        print("D: drag the shortcut one cell up")
        nx, ny = cell_xy(col, rw - 1, zstep, x0)
        nx, ny = bare_point(ui, (nx + SC_W // 2, ny + SC_H // 2))
        fresh(ui)
        ui.mo.drag(cx, cy, nx, ny)
        saved(ui)
        _seg, _n, rows = table(ui)
        check((rows[0][1], rows[0][2]) == (col, rw - 1),
              "it moved to (%d,%d) (%d,%d)" % (col, rw - 1,
                                               rows[0][1], rows[0][2]))
        rw -= 1

        # --- E: reboot ----------------------------------------------------
        print("E: reboot, and it comes back")
        m.reset()
        m.run()
        ui.ready()
        seg, n, rows = table(ui)
        live = [r for r in rows if r[0] != 0xFF]
        check(len(live) == 1, "one shortcut after the reboot (%d)" % len(live))
        if live:
            check((live[0][1], live[0][2]) == (col, rw)
                  and cstr(live[0][51:64]) == "CALCULATOR",
                  "same cell and caption (%d,%d %r)"
                  % (live[0][1], live[0][2], cstr(live[0][51:64])))
        if shots:
            ui.settle()
            shot(m, os.path.join(shots, "e_rebooted.png"))

        # --- F: remove ----------------------------------------------------
        print("F: select it and press Delete")
        cx, cy = cell_xy(col, rw, zstep, x0)
        ui.mo.click(cx + SC_W // 2, cy + 8)
        ui._wait(lambda: ui._byte("desk_sel") == DESK_SC0,
                 "the shortcut selected", 10,
                 snapshot=lambda: "desk_sel %#x" % ui._byte("desk_sel"))
        fresh(ui)
        m.key("Delete")
        saved(ui)
        seg, n, rows = table(ui)
        check(seg == 0 and n == 0, "the claim went with the last one (%#x, %d)"
              % (seg, n))
        cnt, _ = trailer(live_cfg(m, tmp))
        check(cnt == 0, "SYSTEM.CFG has no trailer again")

        # --- G: a FOLDER, opened with Enter --------------------------------
        print("G: drag B:\\MEDIA onto the desktop, select it, press Enter")
        root = ui.open_drive("B")
        idx, _ty = ui.entry("MEDIA", root)
        row = ui.scroll_to(idx, win=root)
        px, py = ui.row_xy(root, row)
        gx, gy = cell_xy(0, ui._word("desk_rows") - 1, zstep, x0)
        fresh(ui)
        ui.mo.drag(px, py, *bare_point(ui, (gx + SC_W // 2, gy + SC_H // 2)))
        saved(ui)
        _s, _n, rows = table(ui)
        live = [r for r in rows if r[0] != 0xFF]
        check(len(live) == 1 and cstr(live[0][5:51]) == "\\MEDIA"
              and live[0][3] == 2 and cstr(live[0][51:64]) == "MEDIA",
              "a folder shortcut \\MEDIA, kind 2, captioned MEDIA (%r)"
              % [(cstr(r[5:51]), r[3], cstr(r[51:64])) for r in live])
        zone = DESK_SC0 + rows.index(live[0]) if live else 0
        ui.mo.click(gx + SC_W // 2, gy + 8)
        ui._wait(lambda: ui._byte("desk_sel") == zone,
                 "the folder shortcut selected", 10,
                 snapshot=lambda: "desk_sel %#x" % ui._byte("desk_sel"))
        if shots:
            ui.settle()
            shot(m, os.path.join(shots, "g_selected.png"))
        media = ui.entry("MEDIA", root)
        m.key("Enter")
        ui._wait(lambda: any((ui.fs_of(w) or (0, 0))[1] == 4
                             for w in ui.windows() if w.visible),
                 "a Disk window on B:\\MEDIA", 30,
                 snapshot=lambda: [(w.title, ui.fs_of(w))
                                   for w in ui.windows()])
        check(True, "Enter opened a Disk window on \\MEDIA")

        # --- H: a DOCUMENT, opened through its association -----------------
        print("H: drag MEDIA\\GUIDE.TEX out, and double-click it")
        mw = [w for w in ui.windows()
              if w.visible and (ui.fs_of(w) or (0, 0))[1] == 4][0]
        ui.raise_window(mw)
        idx, _ty = ui.entry("GUIDE.TEX", mw)
        row = ui.scroll_to(idx, win=mw)
        px, py = ui.row_xy(mw, row)
        hx, hy = cell_xy(0, ui._word("desk_rows") - 2, zstep, x0)
        fresh(ui)
        ui.mo.drag(px, py, *bare_point(ui, (hx + SC_W // 2, hy + SC_H // 2)))
        saved(ui)
        _s, _n, rows = table(ui)
        doc = [r for r in rows if r[0] != 0xFF and r[3] == 0]
        check(len(doc) == 1 and cstr(doc[0][5:51]) == "\\MEDIA\\GUIDE.TEX"
              and cstr(doc[0][51:64]) == "GUIDE.TEX",
              "a document shortcut, the full 8.3 caption (%r)"
              % [(cstr(r[5:51]), cstr(r[51:64])) for r in doc])
        before_t = ui.titles()
        ui.mo.dblclick(hx + SC_W // 2, hy + 8)
        ui._wait(lambda: len(ui.titles()) > len(before_t),
                 "the document's program to open", 90,
                 snapshot=lambda: (ui.titles(), ui.toast()))
        check(True, "the document opened in %r"
              % [t for t in ui.titles() if t not in before_t])
        if shots:
            ui.settle()
            shot(m, os.path.join(shots, "h_document.png"))
        for w in list(ui.windows()):
            if w.visible and w.title not in before_t:
                ui.close(w)

        # --- I: a target that is not there -------------------------------
        print("I: the folder's target gone, double-click it")
        fidx = zone - DESK_SC0
        fpath = (ui._word("sc_seg") << 4) + fidx * SC_REC + 5
        m.write(fpath, b"\\NOPE\0")         # memory only: no save follows
        fresh(ui)
        ui.mo.dblclick(gx + SC_W // 2, gy + 8)
        said = ui.wait_toast(says="not found", limit=60)
        check(said == "Shortcut not found (B:)",
              "a missing target names its drive (%r)" % said)
        m.write(fpath, b"\\MEDIA\0")

        # --- J: right-click > Remove Shortcut -----------------------------
        print("J: right-click the document's shortcut, Remove Shortcut")

        def aim(_mo):
            # rmenu calls this straight after the PRESS, and the popup opens
            # only after the select has repainted the shortcut - and a
            # repaint slow enough loses that race and aims at the PREVIOUS
            # menu's rect (a 32x32 draw did, SPEC.md 26.8.3). So the popup's x1 was poisoned
            # below, and this waits for menu_popup to write it.
            ui._wait(lambda: ui._word("menu_x1") != 0xFFFF,
                     "the shortcut's popup to open", 30)
            mx = ui._word("menu_x1")
            my = ui._word("menu_y1")
            return mx + 12, my + 1 + 8

        fresh(ui)
        m.write(ui._S("menu_x1"), b"\xff\xff")
        ui.mo.rmenu(hx + SC_W // 2, hy + 8, 0, 0, aim=aim)
        saved(ui)
        _s, _n, rows = table(ui)
        live = [r for r in rows if r[0] != 0xFF]
        check(len(live) == 1 and live[0][3] == 2,
              "the right-click took the document's and left the folder's")

        # --- K: Locator's File > Remove Shortcut --------------------------
        print("K: select the folder's shortcut, File > Remove Shortcut")
        ui.mo.click(gx + SC_W // 2, gy + 8)
        ui._wait(lambda: ui._byte("desk_sel") >= DESK_SC0
                 and ui._byte("desk_sel") != 0xFF,
                 "the folder shortcut selected", 10)
        # menu_pick matches by SUBSTRING, so it cannot see a label that runs
        # on into the next string - the item has no NUL of its own and
        # borrows sc_nul's, which a string put between them once took
        label = bytes(m.read(ui._S("sc_s_rem"), 16))
        check(label == b"Remove Shortcut\0",
              "the menu item reads exactly 'Remove Shortcut' (%r)" % label)
        fresh(ui)
        ui.menu_pick("File", "Remove Shortcut")
        saved(ui)
        seg, n, _rows = table(ui)
        check(seg == 0 and n == 0, "the menu took the last one, and the claim")

    shutil.rmtree(tmp, ignore_errors=True)
    print("desksc: %s" % ("PASS" if not fails else
                          "FAIL (%d): %s" % (len(fails), "; ".join(fails))))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
