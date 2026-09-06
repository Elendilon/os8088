#!/usr/bin/env python3
"""WORD'S COMBOS ARE DROP-DOWNS (SPEC.md 68.2.3), and the gesture works BOTH WAYS.

    make worddisk && python3 tests/wdcombo.py

The ribbon's Font and Pts and the ruler's Style used to be three rows of
`wd_mtab` - pseudo-menus on Word's own menu code, opened by a modal poll.  They
are `os88ui_drop` records now (SPEC.md 13.14), which means the gesture is three
EVENTS rather than one loop: `os88ui_drpress` on the way down, `os88ui_drdrag`
while the button is held, `os88ui_drup` at the release.  That is the whole of
what this row is for, because each edge fails differently and silently:

  * press-drag-release  - needs W_ONDRAG to reach the record, or DR_HOT stays
    0FFh and the release picks NOTHING while leaving the list on screen
  * click-then-click    - needs the press ROUTED to the record before the strip
    hit tests.  The Style list lies on top of the ruler's second row, which
    owns the indent-marker drag, so without that routing the second click goes
    to the RULER and the list never comes down.  This one was real: it is why
    `wd_mroute` tests `wd_drany` in front of everything

and both of them end in PIXELS.  The list banks what it covers (SPEC.md
13.14.1) and the close writes it back, so a cycle that opens and picks must
leave the content bit-for-bit as it found it - and `--repaint` pokes
`OS88UI_DR_SEG` = 0 while the list is down, which is exactly what a refused
claim leaves behind, so `wd_drrep`'s piecewise repaint is measured against the
same reference in the same boot.

THE REFERENCE IS TAKEN INSIDE ONE BOOT and never across two: two boots of this
machine differ by a handful of bits at the desktop clock alone, so a
cross-boot comparison cannot answer a question about a save-under.
"""
import os, sys, time, subprocess, tempfile, argparse

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, "tools")
sys.path.insert(0, "tests")

import os88marty as M
from os88mouse import Mouse
import dispcp

WD_MENU_H, WD_RIBBON_H = 14, 16
WD_RL_SBX, WD_RL_SBW = 64, 96
DR_SEL, DR_OPEN, DR_HOT, DR_SEG, DR_TOP = 12, 16, 17, 18, 22
FAIL = []
u16 = lambda b, i=0: b[i] | (b[i + 1] << 8)


def check(name, ok, detail=""):
    print("   %-48s %s%s" % (name, "ok" if ok else "FAIL",
                             "" if ok else "  " + detail))
    if not ok:
        FAIL.append(name)


def pkg_syms(src="apps/word/word.asm", incs=("apps/", "apps/word/")):
    with tempfile.TemporaryDirectory() as d:
        cp, mp = os.path.join(d, "p.asm"), os.path.join(d, "p.map")
        open(cp, "w").write(open(src).read() + "\n[map symbols %s]\n" % mp)
        subprocess.run(["nasm", "-f", "bin", "-w+error"]
                       + sum([["-I", i] for i in incs], [])
                       + ["-o", os.path.join(d, "p.bin"), cp], check=True)
        out = {}
        for line in open(mp):
            f = line.split()
            if len(f) == 3 and all(c in "0123456789ABCDEF" for c in f[0]):
                out[f[2]] = int(f[0], 16)
        return out, open(os.path.join(d, "p.bin"), "rb").read()


def shot(m):
    if m.cards()[0]["type"] in ("cga", "mda"):
        w, h, rows = m.vram()
        return w, h, bytes(b for r in rows for b in r)
    w, h, px = m.fbuf()
    return w, h, bytes(1 if px[i] or px[i + 1] or px[i + 2] else 0
                       for i in range(0, len(px), 3))


def diff(a, b, box):
    w, _, ap = a
    _, _, bp = b
    x0, y0, x1, y1 = box
    return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
            if ap[y * w + x] != bp[y * w + x]]


ap = argparse.ArgumentParser()
ap.add_argument("--machine", default="os8088_5150_cga_gla")
a = ap.parse_args()

syms, image = pkg_syms()
DISK = "build/wdcombo.img"
M.scratch_disk(DISK, "build/word.o88", "build/WORD.OVL", "build/WELCOME.DOC")

with M.launch("build/os8088-360.img", apps=DISK, machine=a.machine) as m:
    M.settle(m)
    mo = Mouse(marty=m)
    S = lambda n: m.sym(n)
    print("== Word's combos are drop-downs (SPEC.md 68.2.3) on %s ==" % a.machine)

    dispcp.open_drive(m, mo, S, M.settle, "B")
    d = dispcp.win_list(m, S)[-1]
    dx, dy = dispcp.win_rect(m, S, d)[:2]
    dispcp.open_named(m, mo, S, M.settle, dx, dy, "WELCOME.DOC")
    time.sleep(2.5)
    M.settle(m)

    # the package's base out of the instance table, its identity checked
    # against CODE at a named symbol (wdmenusu.py's probe, same reasoning)
    I_RECSZ, I_STATE, I_SPTR, I_KIND = 32, 0, 6, 2
    raw = m.read(S("inst_tab"), I_RECSZ * 12)
    seg = None
    for i in range(12):
        b = i * I_RECSZ
        if raw[b + I_STATE] == 1 and (raw[b + I_KIND] & 0x80):
            c = u16(raw, b + I_SPTR)
            if m.read(c * 16 + syms["wd_mact"], 48) == \
                    image[syms["wd_mact"]:syms["wd_mact"] + 48]:
                seg = c
                break
    if seg is None:
        sys.exit("could not locate the running package image in inst_tab")
    base = seg * 16
    R = base + syms["wd_dstyle"]
    rw = lambda n: u16(m.read(base + syms[n], 2))
    dw = lambda o: u16(m.read(R + o, 2))
    db = lambda o: m.read(R + o, 1)[0]

    cl, ct, cw, ch = rw("wd_cl"), rw("wd_ct"), rw("wd_cw"), rw("wd_ch")
    box = (cl, ct, cl + cw - 1, ct + ch - 1)
    bx = cl + WD_RL_SBX + WD_RL_SBW // 2
    by = ct + WD_MENU_H + WD_RIBBON_H + 8      # the Style box's own row
    boxtop = ct + WD_MENU_H + WD_RIBBON_H + 2

    mo.to(4, 4)                                # the pointer is part of the
    time.sleep(0.9)                            # picture: park it identically
    before = shot(m)

    # --- 1. press, drag onto the item, release -------------------------------
    mo.to(bx, by)
    time.sleep(0.4)
    mo._edge(True)
    time.sleep(1.4)
    check("the press drops the list", db(DR_OPEN) == 1, "DR_OPEN=%d" % db(DR_OPEN))
    check("...and BANKS the pixels it covers", dw(DR_SEG) != 0, "DR_SEG=0")
    top = dw(DR_TOP)
    check("...directly under the box (13.14.2)", top == boxtop + 12,
          "DR_TOP=%d, box top %d" % (top, boxtop))
    mo.to(bx, top + 5, l=True)                 # THE BUTTON STAYS DOWN
    time.sleep(1.2)
    check("the DRAG edge reaches the record", db(DR_HOT) == 0,
          "DR_HOT=%d (0FFh = W_ONDRAG never arrived)" % db(DR_HOT))
    mo._edge(False)
    time.sleep(1.6)
    check("the release picks and closes", db(DR_OPEN) == 0 and db(DR_SEL) == 0,
          "OPEN=%d SEL=%d" % (db(DR_OPEN), db(DR_SEL)))
    mo.to(4, 4)
    time.sleep(0.9)
    d1 = diff(before, shot(m), box)
    check("the close restores the content EXACTLY", not d1,
          "%d differing px, first %s" % (len(d1), d1[:3]))

    # --- 2. the same gesture with the bank REFUSED ---------------------------
    mo.to(bx, by)
    time.sleep(0.4)
    mo._edge(True)
    time.sleep(1.4)
    m.write(R + DR_SEG, b"\x00\x00")           # what a refused claim leaves
    mo.to(bx, dw(DR_TOP) + 5, l=True)
    time.sleep(1.2)
    mo._edge(False)
    time.sleep(2.5)
    mo.to(4, 4)
    time.sleep(0.9)
    d2 = diff(before, shot(m), box)
    check("wd_drrep lands on the same pixels", not d2,
          "%d differing px, first %s" % (len(d2), d2[:3]))

    # --- 3. click-then-click: the press must be ROUTED to an open list -------
    mo.to(bx, by)
    time.sleep(0.4)
    mo._edge(True)
    time.sleep(0.5)
    mo._edge(False)
    time.sleep(1.4)
    check("press-and-release on the box leaves it OPEN", db(DR_OPEN) == 1,
          "DR_OPEN=%d" % db(DR_OPEN))
    t2 = dw(DR_TOP)
    mo.to(bx, t2 + 5)
    time.sleep(0.4)
    mo._edge(True)
    time.sleep(0.5)
    mo._edge(False)
    time.sleep(1.6)
    check("the second click picks and closes", db(DR_OPEN) == 0,
          "DR_OPEN=%d (the RULER took the press?)" % db(DR_OPEN))
    mo.to(4, 4)
    time.sleep(0.9)
    d3 = diff(before, shot(m), box)
    check("...and restores the content too", not d3,
          "%d differing px, first %s" % (len(d3), d3[:3]))

    # --- 4. a KEY takes an open list down, as it takes a menu down ----------
    mo.to(bx, by)
    time.sleep(0.4)
    mo._edge(True)
    time.sleep(0.5)
    mo._edge(False)
    time.sleep(1.4)
    check("the list is open for the key test", db(DR_OPEN) == 1,
          "DR_OPEN=%d" % db(DR_OPEN))
    m.key("Escape")
    time.sleep(1.6)
    check("Esc takes it down", db(DR_OPEN) == 0, "DR_OPEN=%d" % db(DR_OPEN))
    mo.to(4, 4)
    time.sleep(0.9)
    d4 = diff(before, shot(m), box)
    check("...and the key's close restores it too", not d4,
          "%d differing px, first %s" % (len(d4), d4[:3]))

print("\n%s" % ("all ok" if not FAIL else "FAILED: " + ", ".join(FAIL)))
sys.exit(1 if FAIL else 0)
