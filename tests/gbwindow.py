#!/usr/bin/env python3
"""REALBOY.O88 in a window, on the glass, against dmg-acid2's reference.

    python3 tests/gbwindow.py [--only vga|herc]

docs/plans/REALBOY-PLAN.md wave 3's gate. Boots os8088 on MartyPC with a B:
disk holding REALBOY.O88 and dmg-acid2 (tools/getgbtest.py's, as ACID2.GB),
opens the ROM from the Disk window - the association launches the package
with it - and checks, on each of the two writers:

  * the game RUNS: the frame counter in the package's view (S_FRAMES, read
    through rb_viewseg off the package's listing) advances;
  * the PICTURE is the reference's, pixel for pixel, in the window's
    content: on VGA the desktop's four greys through OSAPI_GFX_BLITP, on a
    Hercules the reference through the same 2x2 ordered dither the package
    uses (shade 0 lit, 1 a quarter dark, 2 a checkerboard, 3 dark), through
    OSAPI_GFX_BLIT1.

THE NEGATIVE CONTROL is the comparator's: the reference mirrored left to
right must NOT match what is on the glass.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests", "rbcore"))
import os88marty as M  # noqa: E402
import os88ui  # noqa: E402
import rbacid  # noqa: E402

MACHINES = {
    "vga": "os8088_xt_vga_720b",
    "herc": "os8088_5150_herc_sb_720_gla",
}
S_FRAMES = 0x4000 + 0x3E
S_VIEW = 0x4000 + 0x12


def label_off(lst, name):
    for line in open(lst, errors="replace"):
        m = re.match(r"\s*\d+\s+([0-9A-F]{8})\s+\S+\s+(?:<\d+>\s+)?%s\s" % name, line)
        if m:
            return int(m.group(1), 16)
    sys.exit("gbwindow: %s not in %s" % (name, lst))


def find_seg(m, name, viewoff):
    """The running package: a header match whose rb_viewseg names a view
    whose own S_VIEW agrees - a copy of the file in a disk buffer matches the
    header too, with any word at all where rb_viewseg would be."""
    buf = m.read(0x10000, 0x90000)
    for o in range(0, len(buf) - 32, 16):
        if buf[o:o + 2] == b"O8" and buf[o + 16:o + 16 + len(name)] == name:
            v = int.from_bytes(m.read(((0x10000 + o) & ~15) + viewoff, 2), "little")
            if v and int.from_bytes(m.read(v * 16 + S_VIEW, 2), "little") == v:
                return (0x10000 + o) >> 4      # its view names itself back
    return None


def shades_vga(px):
    """RGB -> shade by brightness: white 0 ... black 3."""
    levels = sorted(set(px), key=lambda c: -sum(c))
    assert len(levels) <= 4, levels
    return [levels.index(c) for c in px], levels


def dither(want):
    out = []
    for y in range(144):
        for x in range(160):
            s = want[y * 160 + x]
            even_c, even_r = x % 2 == 0, y % 2 == 0
            dark = (s == 3 or (s == 2 and (even_c == even_r)) or (s == 1 and even_c and even_r))
            out.append(0 if dark else 1)
    return out


def run(kind, want, disk, viewoff):
    img = os.path.join(ROOT, "build", "os8088-720.img")
    with os88ui.boot(img, apps=disk, machine=MACHINES[kind]) as ui:
        m = ui.m
        w = ui.path("B:/ACID2.GB")
        seg, view = None, 0
        for _ in range(60):
            M.guest_sleep(m, 2)
            seg = seg or find_seg(m, b"REALBOY", viewoff)
            if seg:
                view = int.from_bytes(m.read(seg * 16 + viewoff, 2), "little")
            if view:
                f = int.from_bytes(m.read(view * 16 + S_FRAMES, 2), "little")
                if f >= 30:
                    break
        if not view:
            return "the package never started a game"
        f0 = int.from_bytes(m.read(view * 16 + S_FRAMES, 2), "little")
        M.guest_sleep(m, 4)
        f1 = int.from_bytes(m.read(view * 16 + S_FRAMES, 2), "little")
        if f1 <= f0:
            return "frames did not advance (%d, %d)" % (f0, f1)
        ui.mo.to(600, 120)                  # the pointer off the picture
        M.guest_sleep(m, 1)
        w = ui.window("RealBoy")            # where it is NOW: SNAP may move it
        W, H, data = m.fbuf(0)
        cx, cy = w.x + 1, w.y + os88ui.geom.TITLE_H   # (measured: the frame's
                                            #   top row is the title's first)
        px = [tuple(data[((cy + y) * W + cx + x) * 3:((cy + y) * W + cx + x) * 3 + 3])
              for y in range(144) for x in range(160)]
        if kind == "herc":                  # THE CARD'S OWN BYTES: MartyPC's
            vw, vh, rows = m.vram("herc")   #   rendered Hercules frame is
            got = [rows[cy + y][cx + x]     #   cropped and offset, and the
                   for y in range(144) for x in range(160)]  # VRAM route is exact
        if kind == "vga":
            got, levels = shades_vga(px)
            exp, mir = want, [want[y * 160 + 159 - x] for y in range(144) for x in range(160)]
        else:
            exp = dither(want)
            mir = dither([want[y * 160 + 159 - x] for y in range(144) for x in range(160)])
        if os.environ.get("GBWIN_SAVE"):
            sv = os.environ["GBWIN_SAVE"]
            M.write_png_rgb(sv + "-%s-glass.png" % kind, W, H, data)
            with open(sv + "-%s-got.pgm" % kind, "wb") as f:
                f.write(b"P5 160 144 255\n" + bytes(255 - 85 * g if kind == "vga" else 255 * g for g in got))
        bad = sum(1 for a, b in zip(got, exp) if a != b)
        badm = sum(1 for a, b in zip(got, mir) if a != b)
        print("gbwindow %s: frames %d -> %d, %d of 23,040 pixels differ; mirrored, %d"
              % (kind, f0, f1, bad, badm))
        if badm == 0:
            return "the comparator cannot go red: the mirror matches too"
        return None if bad == 0 else "%d pixels differ" % bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", choices=sorted(MACHINES))
    a = ap.parse_args()
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools/getgbtest.py")],
                          stdout=subprocess.DEVNULL)
    g = lambda n: subprocess.check_output([sys.executable, os.path.join(ROOT, "tools/getgbtest.py"),
                                           "--path", n], text=True).strip()
    w, h, ref = rbacid.png_grey(g("dmg-acid2-dmg.png"))
    greys = sorted(set(ref), key=lambda c: -sum(c))
    want = [greys.index(c) for c in ref]
    viewoff = label_off(os.path.join(ROOT, "build", "realboy.lst"), "rb_viewseg")
    tmp = tempfile.mkdtemp(prefix="gbwin-")
    rom = os.path.join(tmp, "ACID2.GB")
    with open(g("dmg-acid2.gb"), "rb") as i, open(rom, "wb") as o:
        o.write(i.read())
    disk = os.path.join(tmp, "apps.img")
    subprocess.check_call([sys.executable, os.path.join(ROOT, "tools/os88disk.py"), "-o", disk,
                           "--size", "720", os.path.join(ROOT, "build", "realboy.o88"), rom],
                          stdout=subprocess.DEVNULL)
    fails = []
    for kind in sorted(MACHINES):
        if a.only and kind != a.only:
            continue
        err = run(kind, want, disk, viewoff)
        if err:
            fails.append("%s: %s" % (kind, err))
    for f in fails:
        print("FAIL gbwindow " + f)
    print("gbwindow: %s" % ("PASS" if not fails else "FAIL"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
