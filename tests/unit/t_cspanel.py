#!/usr/bin/env python3
"""THE COCKPIT LAYOUTS FIT, ON EVERY ADAPTER (SPEC.md 88.9.5, 88.9.8).

A panel is one drawing on three adapters, and the two units it is drawn in
do not scale together: a window's width is CELLS and a cell is 8 DEVICE
pixels, while its x is the 320-wide layout's, which Hercules doubles. So a
layout that is tidy on CGA can overlap on Hercules and the other way round,
and neither shows up in a test that looks at one of them.

This is host-side and reads the records out of apps/skies/cspanel.inc, so it
runs in the fast tier and covers all five aeroplanes on all three adapters
at once:

  1. no two windows overlap;
  2. no round instrument - a decoration's plate, or the attitude indicator's
     bezel - overlaps a window or another instrument;
  3. every window is wide enough for what is lettered into it, and no more
     than CS_SLACK cells wider (the field's "too big for their contents");
  4. every window and instrument is inside the panel.

The three adapters differ in BOTH terms, so all three are checked: a cell is
4 layout units on Hercules and 8 on CGA and Mode X, and a dial's x radius is
its rows over the pixel aspect, which is widest on CGA.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "apps", "skies", "cspanel.inc")
ASM = os.path.join(ROOT, "apps", "skies", "skies.asm")

# vw, wh (moderate), pasp - the three adapters cs_vptab names
ADAPTERS = [
    ("MODEX", 320, 108, 256),
    ("CGA",   320,  84, 213),
    ("HERC",  640, 112, 330),   # cs_vw is 640 here, not the 720
                                # of the screen: the fsx box is
                                # 640x200 at (40, 74)
]
RASTER = os.path.join(ROOT, "apps", "skies", "csraster.inc")


def equ(path, name):
    """A constant READ OUT of the assembly rather than copied into here: a
    mirrored number is a number that goes stale, and these two decide where
    every box in this file is allowed to be."""
    m = re.search(r"^%s\s+equ\s+(\d+)" % name, open(path).read(), re.M)
    if not m:
        raise SystemExit("t_cspanel: %s is not defined in %s" % (name, path))
    return int(m.group(1))


CS_PANROWS = equ(RASTER, "CS_PANROWS")
CS_SLACK = 4                        # cells a window may exceed its text by
# cs_d_msg ERASES ITS STRIP ON THE FACE, full width, from two rows above the
# message's own row to nine below (SPEC.md 88.9.9) - so nothing may be drawn
# there but the message, and a decoration that strays into it is rubbed out
# the first time the aeroplane has something to say
CS_RAILSTEP = equ(ASM, "CS_RAILSTEP")
MSG_ROW = 67
MSG_BAND = (MSG_ROW - 2, MSG_ROW + 9)

# item -> the cells it letters, by the draw procs in csgame.inc
ITEM_CELLS = {0: 4 + 3,             # SPD: the digits are four cells along
              1: 4 + 5,             # ALT
              2: 4 + 3,             # HDG
              3: 0,                 # the attitude indicator draws itself
              4: 4 + 3,             # THR
              5: 13,                # ON THE GROUND
              6: 0,                 # the throttle bar: CSK_BARW says its width
              7: 0,                 # the message: centred, its own strip
              8: 3 + 3}             # UP 015 - the variometer letters its label
bad = []


def check(cond, what):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", what))
    if not cond:
        bad.append(what)


def words(line):
    line = line.split(";")[0]
    m = re.match(r"\s*dw\s+(.*)", line)
    if not m:
        return None
    out = []
    for t in m.group(1).split(","):
        t = t.strip()
        if not t:
            continue
        if re.fullmatch(r"[-0-9xXa-fA-F |()<>+*]+", t):
            out.append(eval(t, {"__builtins__": {}}, {}))    # noqa: S307
        else:
            out.append(t)
    return out


def cockpits():
    """Every cs_ck_* record and its .win / .items / .deco tables."""
    text = open(SRC, errors="replace").read().splitlines()
    out, cur, sub = {}, None, None
    for ln in text:
        m = re.match(r"(cs_ck_[a-z0-9_]+):", ln)
        if m:
            cur = m.group(1)
            out[cur] = {"hdr": [], "win": [], "items": [], "deco": []}
            sub = "hdr"
            continue
        if cur is None:
            continue
        m = re.match(r"\.(win|items|deco):", ln)
        if m:
            sub = m.group(1)
            continue
        if re.match(r"[a-z_][a-z0-9_]*:", ln):
            cur = None
            continue
        w = words(ln)
        if w:
            out[cur][sub].extend(w)
    return out


def main():
    ck = cockpits()
    check(len(ck) == 5, "five cockpits in the file (%d: %s)"
          % (len(ck), ", ".join(sorted(ck))))
    for name in sorted(ck):
        c = ck[name]
        hdr = c["hdr"]
        nwin, adcx, adcy, adry, barw = (hdr[1], hdr[3], hdr[4],
                                        hdr[5], hdr[6])
        ndeco = hdr[8]
        win = [c["win"][i:i + 4] for i in range(0, len(c["win"]), 4)]
        items = [c["items"][i:i + 2] for i in range(0, len(c["items"]), 2)]
        deco = [c["deco"][i:i + 5] for i in range(0, len(c["deco"]), 5)]
        check(len(win) == nwin,
              "%s: CSK_NWIN is %d and the table has %d" % (name, nwin, len(win)))
        check(len(deco) == ndeco,
              "%s: CSK_NDECO is %d and the table has %d"
              % (name, ndeco, len(deco)))
        check(len(items) == 9,
              "%s: nine items (%d)" % (name, len(items)))

        for aname, vw, wh, pasp in ADAPTERS:
            hsx = vw * 8 // 320
            cell = 8 * 8 // hsx                 # a cell in layout units
            rows = max(CS_PANROWS, wh and CS_PANROWS)

            def colx(c):
                return c * cell if c >= 0 else 320 + c * cell

            boxes = []                          # (x0, x1, y0, y1, what)
            for i, (cx, y, cells, h) in enumerate(win):
                if cells == 0:                  # the whole panel
                    x0, w = 0, 320
                elif cells < 0:                 # that many cells, CENTRED
                    w = -cells * cell
                    x0 = 160 - w // 2
                else:
                    x0, w = colx(cx), cells * cell
                boxes.append((x0, x0 + w - 1, y, y + h - 1, "window %d" % i))
            rx = lambda r: (r * 256 // pasp)
            boxes.append((adcx - rx(adry) - 3, adcx + rx(adry) + 3,
                          adcy - adry - 1, adcy + adry + 1, "the ADI bezel"))
            for i, (kind, dx, dy, dr, arg) in enumerate(deco):
                w = rx(dr)
                # A RAIL is a ROW of switches (SPEC.md 88.9.3.1): its ARG's
                # low byte says how many and they are CS_RAILSTEP apart, so
                # the gate has to expand it or it checks one switch of nine
                n = (arg & 0xFF) if kind == "CSDK_RAIL" else 1
                for k in range(n):
                    x = dx + k * CS_RAILSTEP
                    boxes.append((x - w, x + w, dy - dr, dy + dr,
                                  "deco %d.%d" % (i, k) if n > 1
                                  else "deco %d" % i))
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    a, b = boxes[i], boxes[j]
                    if (a[0] <= b[1] and b[0] <= a[1]
                            and a[2] <= b[3] and b[2] <= a[3]):
                        check(False, "%s/%s: %s overlaps %s (%s vs %s)"
                              % (name, aname, a[4], b[4], a[:4], b[:4]))
            for x0, x1, y0, y1, what in boxes:
                check(0 <= x0 and x1 <= 319 and 0 <= y0 and y1 < CS_PANROWS,
                      "%s/%s: %s is inside the panel (%d..%d, %d..%d)"
                      % (name, aname, what, x0, x1, y0, y1))
                check(y1 < MSG_BAND[0] or y0 > MSG_BAND[1],
                      "%s/%s: %s is clear of the message strip's erase "
                      "(rows %d..%d against %d..%d)"
                      % (name, aname, what, y0, y1, MSG_BAND[0], MSG_BAND[1]))

        # 3 - the windows fit their text, and not much more
        for it, (cx, y) in enumerate(items):
            need = ITEM_CELLS[it]
            if not need or (cx == 0 and y == 0):
                continue
            here = [w for w in win if w[1] <= y and y + 8 <= w[1] + w[3]
                    and w[2] > 0 and w[0] <= cx and cx + need <= w[0] + w[2]]
            check(bool(here),
                  "%s: item %d (%d cells at column %d, row %d) is inside a "
                  "window" % (name, it, need, cx, y))
            if here:
                w = min(here, key=lambda w: w[2])
                check(w[2] - need <= CS_SLACK,
                      "%s: item %d's window is %d cells for %d of text "
                      "(slack %d, max %d)"
                      % (name, it, w[2], need, w[2] - need, CS_SLACK))

    if bad:
        print("t_cspanel: %d problem(s)" % len(bad))
        return 1
    print("  ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
