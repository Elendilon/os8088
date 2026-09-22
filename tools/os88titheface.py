#!/usr/bin/env python3
"""os8088 - tools/os88titheface.py

TITHE's SMALL FACES, and what they buy (docs/plans/TITHE-PLAN.md 8, SPEC.md 97.4.1).

THE QUESTION IS NOT TYPOGRAPHY, IT IS HOW MANY NUMBERS FIT. A character has six
stats - two COSTS that only matter while it is a card, and four that have to be
on the board: HP, two variable stats whose icon says which they are, and POWER.
At the system 8x8 a CGA cell's stat column is 3 columns by 2 rows, which holds
TWO of the four, and a CGA card row is 17 characters, which holds a name or the
numbers and not both.

    face   CGA card    CGA cell   what the cell holds
    8x8    17 x 1      3 x 2      two values
    5x7    27 x 1      4 x 2      two values - the fourth has nowhere to go
    4x6    34 x 1      6 x 3      HP / POWER / stat1+stat2  <- all four

So 4x6 is the size that answers it, and 5x7 is not - which is why only the
dense face and a SQUARE alternative to it are drawn here.

AND THE ASPECT IS THE REAL RISK. A CGA pixel is 2.4:1 tall, so tithe4's 3x5 ink
is READ as 3 wide by 12 tall. tools/os88font.py's own header says a face
balanced on VGA can be spindly there and that is the adapter it will be read
on, so tithe6 puts the same three rows in five pixels of width instead of
three. Both are rendered at every surface, aspect-corrected, and the choice is
made by eye.

    python3 tools/os88titheface.py sheet
    python3 tools/os88titheface.py --selfcheck
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88marty                                             # noqa: E402
from os88tithebase import Sheet, WHITE, GREY, RED            # noqa: E402

ICON_HP, ICON_GOLD, ICON_SOUL, ICON_MELEE, ICON_SHIELD, ICON_BOW, ICON_STAR = range(1, 8)


class Face:
    """A fixed-cell face read from fonts/*.fN - ASCII art, like the .f8s."""

    def __init__(self, path):
        self.name = os.path.basename(path).split(".")[0]
        self.w = int(path.rsplit(".f", 1)[1])   # .f4 is a 4-wide cell, .f6 a 6
        self.g = {}
        rows, code = [], None
        for n, raw in enumerate(open(path, encoding="utf-8"), 1):
            line = raw.rstrip("\n").strip()
            # A PIXEL ROW IS TESTED FOR FIRST, and that ordering is the whole of
            # why this is not a one-line `startswith('#')`: '#' is the ink AND
            # the comment marker, so a comment rule applied first eats every row
            # that begins with a lit pixel. tools/os88font.py's parser carries
            # the same comment because the same thing happened to it - and here
            # it happened again, on this file's first run, with the selfcheck
            # reporting glyphs three rows tall.
            if len(line) == self.w and not (set(line) - set(".#")):
                if code is not None:
                    rows.append(line)
                continue
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^char\s+(\d+)", line)
            if m:
                if code is not None:
                    self.g[code] = rows
                code, rows = int(m.group(1)), []
                if code in self.g:
                    raise SystemExit("%s:%d: char %d appears twice"
                                     % (path, n, code))
        if code is not None:
            self.g[code] = rows
        self.h = len(next(iter(self.g.values())))

    def put(self, band, x, y, text, ink=1):
        """Draw `text` (a str, or ints for icons) and return the x after it."""
        for ch in text:
            code = ch if isinstance(ch, int) else ord(ch.upper())
            g = self.g.get(code)
            if g is None:
                # THE CONTROL HAS NO ICONS. Drawing nothing would make it look
                # narrower than it is, so a missing glyph is a solid block: the
                # same advance, and obviously a stand-in.
                for gy in range(self.h - 1):
                    for gx in range(self.w - 1):
                        band.set(x + gx, y + gy, ink)
                x += self.w
                continue
            for gy, row in enumerate(g):
                for gx, c in enumerate(row):
                    if c == "#":
                        band.set(x + gx, y + gy, ink)
            x += self.w
        return x

    def width(self, text):
        return self.w * len(text)


class Mono:
    """A plain bitmap the mock-ups draw into. 1 = lit."""

    def __init__(self, w, h, fill=0):
        self.w, self.h = w, h
        self.px = [[fill] * w for _ in range(h)]

    def set(self, x, y, v=1):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = v

    def box(self, x0, y0, x1, y1, v=1):
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.px[y][x] = v

    def frame(self, x0, y0, x1, y1, v=1):
        for x in range(x0, x1 + 1):
            self.set(x, y0, v); self.set(x, y1, v)
        for y in range(y0, y1 + 1):
            self.set(x0, y, v); self.set(x1, y, v)


def geo():
    src = open("apps/tithe/tithe.asm", encoding="utf-8").read()
    rows = {m.group(1): [int(x) for x in m.group(2).split(",")]
            for m in re.finditer(r"^ti_geo_(\w+):\s*dw\s+(.+)$", src, re.M)}
    # CW CH RISE BW BH HUD PAN BASEW NUMS CARDH INSX
    out = []
    for key, name, aspect in (("vgaf", "vga-full", 1.0), ("vgaw", "vga", 1.0),
                              ("herc", "herc", 1.55), ("cga", "cga", 2.40)):
        r = rows[key]
        out.append(dict(key=name, aspect=aspect, cardw=r[6] - 16, cardh=r[9],
                        insx=r[10], ch=r[1], unitw=24))
    return out


# --- the mock-ups ------------------------------------------------------------
# A card and a cell drawn with a face, at the exact size the built layout hands
# them. The CONTENT is what TITHE-PLAN 5.2 says a character has, not a sample of
# lorem: name, the two costs that only matter as a card, and the four that go on
# the board.

CARD = dict(name="PIKEMAN", gold=2, soul=0, hp=5, power=3,
            s1=(ICON_MELEE, 3), s2=(ICON_SHIELD, 2), block="F")


def card_mock(f, s, hovered=False):
    b = Mono(s["cardw"], s["cardh"])
    b.frame(0, 0, s["cardw"] - 1, s["cardh"] - 1)
    pad = 2
    x0, y0 = pad, pad
    right = s["cardw"] - s["unitw"] - pad - 2      # the sprite's corner
    b.box(right + 2, pad, s["cardw"] - pad - 1, s["cardh"] - pad - 1, 1)
    rows = (s["cardh"] - 2 * pad) // f.h
    if rows >= 2:
        f.put(b, x0, y0, CARD["name"])
        y = y0 + f.h
        f.put(b, x0, y, [ICON_GOLD] + list(str(CARD["gold"])) +
              [" ", ICON_SOUL] + list(str(CARD["soul"])) + [" ", CARD["block"]])
        if rows >= 3:
            y += f.h
            f.put(b, x0, y, [ICON_HP] + list(str(CARD["hp"])) +
                  [" ", CARD["s1"][0]] + list(str(CARD["s1"][1])) +
                  [" ", CARD["s2"][0]] + list(str(CARD["s2"][1])) +
                  [" ", ICON_SOUL] + list(str(CARD["power"])))
    else:
        # ONE ROW IS TWO CARDS, not a cramped one. SPEC.md 97.4.2 already has a
        # short card showing the NUMBERS at rest and the NAME when the pointer
        # is on it, so the honest mock-up is both - drawing name AND numbers on
        # one row is a layout this game does not use, and it is what made the
        # square face look as though it did not fit.
        if hovered:
            f.put(b, x0, y0, list(CARD["name"]) + [" ", ICON_GOLD] +
                  list(str(CARD["gold"])))
        else:
            f.put(b, x0, y0, [ICON_GOLD] + list(str(CARD["gold"])) +
                  [" ", ICON_HP] + list(str(CARD["hp"])) +
                  [" ", CARD["s1"][0]] + list(str(CARD["s1"][1])) +
                  [" ", CARD["s2"][0]] + list(str(CARD["s2"][1])) +
                  [" ", ICON_SOUL] + list(str(CARD["power"])))
    return b


def cell_mock(f, s):
    """The stat COLUMN beside a figure: INSX wide, CH tall."""
    b = Mono(s["insx"], s["ch"])
    y = 0
    if f.h * 3 <= s["ch"] and f.w * 4 <= s["insx"]:
        f.put(b, 0, y, [ICON_HP] + list("12")); y += f.h
        f.put(b, 0, y, [ICON_SOUL] + list(str(CARD["power"]))); y += f.h
        f.put(b, 0, y, [CARD["s1"][0]] + list(str(CARD["s1"][1])) +
              [CARD["s2"][0]] + list(str(CARD["s2"][1])))
    else:
        f.put(b, 0, y, [ICON_HP] + list("12")); y += f.h
        if y + f.h <= s["ch"]:
            f.put(b, 0, y, [ICON_SOUL] + list(str(CARD["power"])))
    return b


def blit(sheet, m, x, y, zx, zy, ink=WHITE):
    for by in range(m.h):
        for bx in range(m.w):
            if m.px[by][bx]:
                for dy in range(zy):
                    for dx in range(zx):
                        sheet.set(x + bx * zx + dx, y + by * zy + dy, ink)


def sheet_out(faces, out):
    g = geo()
    zx = 4
    rowh = 0
    for s in g:
        rowh = max(rowh, s["cardh"], s["ch"])
    per = len(faces) + 0
    W = 40 + max(s["cardw"] for s in g) * zx + 60 + 26 * 4 * zx
    H = 140
    for s_ in g:
        zy_ = max(1, round(zx * s_['aspect']))
        H += 24
        one_ = (s_['cardh'] - 4) // faces[0].h < 2
        for f_ in faces:
            hh = max(s_['cardh'], s_['ch'])
            if one_:
                hh = s_['cardh'] * 2 + 8
            H += hh * zy_ + 20
        H += 16
    sh = Sheet(W, H)
    sh.text(24, 22, "TITHE - SMALL FACES, AT THE SIZES THE LAYOUT HANDS THEM", WHITE, 2)
    sh.text(24, 48, "EACH ROW IS ONE SURFACE AND ONE FACE, SHOWN AT ITS OWN "
                    "PIXEL ASPECT.", GREY, 1)
    sh.text(24, 62, "LEFT: A CARD.   RIGHT: THE STAT COLUMN BESIDE A FIGURE, "
                    "WHICH NEEDS FOUR VALUES.", GREY, 1)
    y = 92
    for s in g:
        zy = max(1, round(zx * s["aspect"]))
        sh.rect(24, y, sh.w - 24, y, GREY)
        sh.text(24, y + 8, "%s   card %dx%d   cell %dx%d   pixel 1 x %.2f"
                % (s["key"].upper(), s["cardw"], s["cardh"], s["insx"],
                   s["ch"], s["aspect"]), WHITE, 1)
        y += 24
        one = (s["cardh"] - 4) // faces[0].h < 2
        for f in faces:
            e = cell_mock(f, s)
            sh.text(24, y + 2, f.name.upper(), RED, 1)
            c = card_mock(f, s)
            blit(sh, c, 90, y, zx, zy)
            blit(sh, e, 90 + s["cardw"] * zx + 40, y, zx, zy)
            h = max(c.h, e.h)
            if one:
                sh.text(90, y + c.h * zy + 3, "AT REST", GREY, 1)
                c2 = card_mock(f, s, hovered=True)
                blit(sh, c2, 90, y + c.h * zy + 16, zx, zy)
                sh.text(90, y + c.h * zy + 16 + c2.h * zy + 3, "HOVERED", GREY, 1)
                h = c.h + c2.h + 8
            y += h * zy + 20
        y += 16
    sh.save(out)
    print("%s: %dx%d" % (out, sh.w, sh.h))


def selfcheck():
    bad = []
    need = set(range(1, 8)) | {32} | set(range(48, 58)) | set(range(65, 91))
    for path in ("fonts/tithe4.f4", "fonts/tithe6.f6"):
        f = Face(path)
        miss = sorted(need - set(f.g))
        if miss:
            bad.append("%s is missing %d glyph(s): %s" % (path, len(miss), miss[:8]))
        for code, rows in f.g.items():
            if len(rows) != f.h or any(len(r) != f.w for r in rows):
                bad.append("%s glyph %d is not %dx%d" % (path, code, f.w, f.h))
            # THE LAST COLUMN AND ROW ARE THE ADVANCE: ink there and a run of
            # glyphs touches, which at three pixels of width is a word nobody
            # can read.
            if any(r[-1] == "#" for r in rows) or "#" in rows[-1]:
                bad.append("%s glyph %d inks its advance column or row"
                           % (path, code))
        # ...and every glyph must differ from every other, which is the failure
        # that reads as a typo rather than as a bug.
        seen = {}
        for code, rows in f.g.items():
            k = "\n".join(rows)
            if k in seen and code != 32 and seen[k] != 32:
                bad.append("%s glyphs %d and %d are the SAME picture"
                           % (path, seen[k], code))
            seen[k] = code
    for line in bad:
        print("  FAIL %s" % line)
    print("os88titheface: %d face(s), %s"
          % (2, "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("cmd", nargs="?", default="sheet", choices=["sheet"])
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    faces = [Face("fonts/tithe4.f4"), Face("fonts/tithe6.f6"),
             Face("fonts/tallx.f8")]
    sheet_out(faces, "build/tithe-faces.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
