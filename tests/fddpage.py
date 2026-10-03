#!/usr/bin/env python3
"""Does the Control Panel's Floppy page override the drive detection? (SPEC.md 31.14)

    make && python3 tests/fddpage.py

Two boots of one disk. The first drives the page the way a hand does - a
LEFT press on a drop-down box, the popup it opens (menu_popup, SPEC.md 12.4),
a drag onto the item and a release - four times, and reads each answer out of
`drv_cfg`'s 'FD' bytes; then it closes the panel, which is what writes
SYSTEM.CFG (SPEC.md 31.8). The second boots the disk that was written and
reads what `ovl_fdd_apply` did to `dsk_vtab` and the read bound:

  * A: forced to 5.25 - a zone, DVF_525, and NO DVF_GUESS, so the medium
    cannot take it back at the first mount;
  * B: forced to None - its row stays (a letter is not given away), its zone
    goes;
  * the third unit forced to 3.5 on a machine that claims two - a row it did
    not have, at D: because C: is the hard disk's, zone on, not 5.25;
  * the read bound forced to Track AGAINST a canary that found cylinder runs
    on boot 1, so the leg cannot pass by agreeing with the machine.

Then boot 2 picks the read bound's THIRD item, Cylinder, closes the panel
again, and the disk it writes is booted twice more - the two cases Cylinder
exists to tell apart (SPEC.md 31.14):

  * on QEMU, whose CPU is a 286-and-up, so 18.93.2's gate never runs the
    canary and Auto would leave the bound at a track. Cylinder must turn the
    run ON: `boot_cylrun` non-zero and `[dsk_cylrun]` = 1. That is the machine
    the setting is for, and MartyPC cannot be one;
  * on the same 5150, from a copy whose boot sector carries a WRONG `KSIG`, so
    the canary AFFIRMATIVELY FAILS and the loader reloads at the track bound.
    Cylinder must NOT turn the run back on over that: `[dsk_cylrun]` = 0, the
    record untouched. The same patch on the record-less disk reading
    `boot_cylrun` 0 is the witness that the canary did fail - after the boot,
    a broken patch and a broken ovl_fdd_apply look alike on the Cylinder disk.

Take the `call ovl_fdd_apply` out of drv_boot_x and every boot-2 leg fails;
put `[menu_btn]` back to 2 and the first pick fails, because the popup then
closes the instant it opens under a held LEFT button. Take the `and` with
`b2_cylok` out of ovl_fdd_apply and the failed-canary leg fails; make
Cylinder read as Auto again and the QEMU leg does.
"""
import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
import os88flush                                            # noqa: E402
import os88marty                                            # noqa: E402
import os88mouse                                            # noqa: E402
import os88sym                                              # noqa: E402
import dispcp                                               # noqa: E402
import os88fat                                              # noqa: E402
import os88qemu                                             # noqa: E402

S = os88sym.linear
KERNEL_SEG = 0x0060
TITLE_H = 18
CP_RX = 96
MENU_ITEM_H = 16
DV_SIZE, DV_KIND, DV_UNIT, DV_FLAGS = 16, 0, 1, 2
DVK_BIOS, DVK_FREE = 0, 0xFF
DVF_525, DVF_GUESS = 2, 4


def u16(b):
    return b[0] | (b[1] << 8)


def shot(m, path):
    w, h, rows = m.vram(None)
    os88marty.write_png(path, w, h, rows)


def break_canary(src, dst):
    """A copy of `src` whose boot sector expects a KSIG the kernel does not
    carry, so 18.93.1's canary compares UNEQUAL after the first load and the
    loader loads again at the track bound - a failed canary, on a 5150 whose
    FDC crosses heads perfectly well. KSIG is the word at KSIG_OFF +
    BOOT2_PAD of KERNEL.SYS (the Makefile's KSIGDEF2) and boot.asm loads it
    with one `mov di, imm16`, so the patch is that immediate and nothing else."""
    shutil.copyfile(src, dst)
    eq = os88sym.equates()
    k = bytes(os88fat.Fat12(dst).read("KERNEL.SYS"))
    o = eq["KSIG_OFF"] + eq["BOOT2_SECS"] * 512
    ksig = k[o] | (k[o + 1] << 8)
    with open(dst, "r+b") as f:
        bs = bytearray(f.read(512))
        at = [i for i in range(510 - 2)
              if bs[i] == 0xBF and bs[i + 1] | (bs[i + 2] << 8) == ksig]
        if len(at) != 1:
            sys.exit("fddpage: %d `mov di, %04X` in the boot sector, not one"
                     % (len(at), ksig))
        bad = ksig ^ 0x5A5A
        bs[at[0] + 1], bs[at[0] + 2] = bad & 0xFF, bad >> 8
        f.seek(0)
        f.write(bs)


def qemu_boot(img, apps):
    """`make test` on a scratch copy of `img`, until the desktop is idle.
    QEMU because its CPU is a 286 and up: the one machine here on which
    18.93.2's gate leaves the canary unrun."""
    os88qemu.kill()
    os88qemu.own()
    r = subprocess.run(["make", "test", "TESTIMG=" + img, "TESTAPPS=" + apps],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("fddpage: make test failed:\n" + r.stdout + r.stderr)
    from ethernet import Qemu
    q = Qemu()
    entry = S("cold_entry")
    os88qemu.acted(q, lambda: q.read(entry, 1)[0] == 0xE9 and
                   os88qemu.ui_idle(q, S), secs=90, what="the desktop",
                   poll=0.4)
    return q


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--shot", default="build/fddpage.png")
    a = ap.parse_args(argv)

    eq = os88sym.equates()
    FDD = S("drv_cfg") + eq["CFG_FDD"]
    FDR = S("drv_cfg") + eq["CFG_FDR"]
    R0Y, ROWH, BX1 = eq["CPF_R0Y"], eq["CPF_ROWH"], eq["CPF_BX1"]
    settle = os88marty.settle
    fail = []
    written = os.path.abspath(os.path.join("build", "fddpage-written.img"))
    cylimg = os.path.abspath(os.path.join("build", "fddpage-cyl.img"))

    def byte(m, addr):
        return m.read(addr, 1)[0]

    def rows(m):
        t = m.read(S("dsk_vtab"), 8 * DV_SIZE)
        return [(t[i * DV_SIZE + DV_KIND], t[i * DV_SIZE + DV_UNIT],
                 t[i * DV_SIZE + DV_FLAGS]) for i in range(8)]

    def row_of(m, unit):
        for i, (k, u, f) in enumerate(rows(m)):
            if k == DVK_BIOS and u == unit:
                return i, f
        return None, None

    with os88marty.launch(a.image, apps=a.apps, machine=a.machine) as m:
        cyl0 = byte(m, S("boot_cylrun"))
        print("boot 1: FD = %02X %02X, boot_cylrun %d, rows %s"
              % (byte(m, FDD), byte(m, FDR), cyl0, rows(m)))
        if byte(m, FDD) or byte(m, FDR):
            sys.exit("fddpage: the disk already carries an 'FD' record")
        if row_of(m, 2)[0] is not None:
            sys.exit("fddpage: this machine already has a third drive, so "
                     "forcing one proves nothing")
        if not cyl0:
            sys.exit("fddpage: the canary found track runs, so forcing Track "
                     "proves nothing")
        # the read bound is forced to the OPPOSITE of what the canary found
        rd, want_cyl = 1, 0

        # the page's RECORD. cp_items is in CTRL.DRV's image now (kernel
        # size pass 8), so it is the kernel's own equate rather than a walk of
        # the table - ctrl.inc asserts CP_IFDD is the Floppy row at build time
        rec = [os88sym.equates()["CP_IFDD"]]
        f = os88flush.Flush(marty=m)
        mo = os88mouse.Mouse(marty=m)
        dispcp.open_panel(m, mo, S, settle, page=rec[0])
        settle(m)

        def pick(m, mo, row, item):
            wx, wy = dispcp._cp_win(m, S)
            x0 = wx + 1 + CP_RX + BX1 + 20
            y0 = wy + TITLE_H + 1 + R0Y + row * ROWH + 7

            def aim(_mo):
                os88marty.until(m, lambda mm: mm.read(S("menu_dropd"), 1)[0],
                                "the drop-down's list to be up", poll=0.05,
                                guest=10.0)
                x = u16(m.read(S("menu_x1"), 2))
                y = u16(m.read(S("menu_y1"), 2))
                return x + 12, y + 1 + item * MENU_ITEM_H + 8
            mo.menu(x0, y0, 0, 0, aim=aim)

        steps = ((1, 1, lambda: byte(m, FDD) == 0x04, "B: None"),
                 (2, 3, lambda: byte(m, FDD) == 0x34, "unit 2 3.5"),
                 (0, 2, lambda: byte(m, FDD) == 0x36, "A: 5.25"),
                 (4, rd, lambda: byte(m, FDR) == rd, "reads %d" % rd))
        for row, item, ok, what in steps:
            try:
                pick(m, mo, row, item)
                os88marty.until(m, lambda _: ok(), what, poll=0.05,
                                guest=10.0)
                print("boot 1: %-10s ok, FD = %02X %02X"
                      % (what, byte(m, FDD), byte(m, FDR)))
            except os88marty.MartyError as e:
                fail.append("%s: the pick did not reach drv_cfg (%s)"
                            % (what, e))
        settle(m)
        shot(m, a.shot)
        print("boot 1: the page is in %s" % a.shot)
        if not byte(m, S("cp_wdirty")):
            fail.append("no pick marked the settings dirty")
        dispcp.close_panel(m, mo, S, settle)
        if byte(m, S("cp_dsave")):
            fail.append("SYSTEM.CFG was not written: cp_dsave = %d"
                        % byte(m, S("cp_dsave")))
        try:
            cfg = f.volume(0).read("SYSTEM.CFG")
        except os88flush.FlushError:
            cfg = b""
        if b"FD\x01\x02" not in cfg:
            fail.append("SYSTEM.CFG carries no 'FD' ver 1 len 2 record")
        f.save(0, written)

    with os88marty.launch(written, apps=a.apps, machine=a.machine) as m:
        print("boot 2: FD = %02X %02X, boot_cylrun %d, dsk_cylrun %d, rows %s"
              % (byte(m, FDD), byte(m, FDR), byte(m, S("boot_cylrun")),
                 byte(m, S("dsk_cylrun")), rows(m)))
        i, fl = row_of(m, 0)
        if i != 0 or fl & 7 != 1 | DVF_525:
            fail.append("A: is not a 5.25 zone with no guess: row %s flags %s"
                        % (i, fl))
        i, fl = row_of(m, 1)
        if i != 1 or fl & 1:
            fail.append("B: did not keep its row and lose its zone: row %s "
                        "flags %s" % (i, fl))
        i, fl = row_of(m, 2)
        if i != 3 or fl is None or fl & 7 != 1:
            fail.append("the third unit is not a 3.5 zone at D:: row %s "
                        "flags %s" % (i, fl))
        if (byte(m, S("boot_cylrun")) != 0) != bool(want_cyl) or \
                byte(m, S("dsk_cylrun")) != want_cyl:
            fail.append("the read bound was not forced to %d" % want_cyl)
        shot(m, os.path.splitext(a.shot)[0] + "-boot2.png")

        # --- the read bound's third item: Cylinder -------------------------
        f = os88flush.Flush(marty=m)
        mo = os88mouse.Mouse(marty=m)
        dispcp.open_panel(m, mo, S, settle, page=rec[0])
        settle(m)
        try:
            pick(m, mo, 4, 2)
            os88marty.until(m, lambda _: byte(m, FDR) == 2, "reads 2",
                            poll=0.05, guest=10.0)
            print("boot 2: reads 2    ok, FD = %02X %02X"
                  % (byte(m, FDD), byte(m, FDR)))
        except os88marty.MartyError as e:
            fail.append("Cylinder: the pick did not reach drv_cfg (%s)" % e)
        settle(m)
        dispcp.close_panel(m, mo, S, settle)
        try:
            cfg = f.volume(0).read("SYSTEM.CFG")
        except os88flush.FlushError:
            cfg = b""
        if b"FD\x01\x02\x36\x02" not in cfg:
            fail.append("SYSTEM.CFG's 'FD' record is not 36 02 after Cylinder")
        f.save(0, cylimg)

    # --- Cylinder where the canary never ran: a 286 and up ------------------
    qimg = os.path.join("build", "fddpage-qemu.img")
    shutil.copyfile(cylimg, qimg)
    q = qemu_boot(qimg, a.apps)
    try:
        qb = q.read(S("drv_cfg") + eq["CFG_FDR"], 1)[0]
        qr = q.read(S("boot_cylrun"), 2)
        qd = q.read(S("dsk_cylrun"), 1)[0]
    finally:
        q.quit()
        os88qemu.kill()
    print("qemu:   FDR %d, boot_cylrun %d, dsk_cylrun %d"
          % (qb, u16(qr), qd))
    if qb != 2 or not u16(qr) or qd != 1:
        fail.append("Cylinder did not turn the run on where the canary never "
                    "ran (QEMU): FDR %d boot_cylrun %d dsk_cylrun %d"
                    % (qb, u16(qr), qd))

    # --- the witness: the same patch on the Auto disk FAILS the canary -----
    # Below, a broken KSIG and a broken ovl_fdd_apply read identically after
    # the boot - Cylinder writes over the loader's 0 - so the loader's half is
    # proved on a disk with no record, where nothing writes over it.
    autobad = os.path.join("build", "fddpage-autobad.img")
    break_canary(a.image, autobad)
    with os88marty.launch(autobad, apps=a.apps, machine=a.machine) as m:
        wr = u16(m.read(S("boot_cylrun"), 2))
        print("boot 3: FD = %02X %02X, boot_cylrun %d (KSIG broken, Auto)"
              % (byte(m, FDD), byte(m, FDR), wr))
    if wr:
        fail.append("the broken KSIG did not fail the canary: boot_cylrun is "
                    "%d on the Auto disk, so the next leg proves nothing" % wr)

    # --- Cylinder over a canary that FAILED this boot -----------------------
    badimg = os.path.join("build", "fddpage-cylbad.img")
    break_canary(cylimg, badimg)
    with os88marty.launch(badimg, apps=a.apps, machine=a.machine) as m:
        br, bd = u16(m.read(S("boot_cylrun"), 2)), byte(m, S("dsk_cylrun"))
        print("boot 4: FD = %02X %02X, boot_cylrun %d, dsk_cylrun %d (KSIG "
              "broken, Cylinder)" % (byte(m, FDD), byte(m, FDR), br, bd))
        if br or bd:
            fail.append("Cylinder turned the run on over a FAILED canary: "
                        "boot_cylrun %d, dsk_cylrun %d" % (br, bd))
        if byte(m, FDR) != 2:
            fail.append("the record changed under a failed canary: FDR %d"
                        % byte(m, FDR))

    for x in fail:
        print("FAIL: %s" % x)
    print("fddpage: %s" % ("FAILED" if fail else
                           "ok - five picks, two files, four reboots"))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
