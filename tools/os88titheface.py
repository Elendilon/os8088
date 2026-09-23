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
# ...and the two STANCES (TITHE-PLAN 5.4), which are a ranged character's
# standing order and the only per-character state the board cannot infer.
ICON_SFRONT, ICON_SNIPE = 8, 9

# How far apart an icon must be from every other glyph in its face, in pixels
# that differ. Four is what the shipped faces clear with room; two is what the
# coin and the digit 0 were, and what the shield and the heart were.
ICON_APART = 4


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
    # CW CH RISE BW BH HUD PAN BASEW CARDH INSX - NUMS went, and this read
    # CARDH and INSX one field along from where they are
    out = []
    for key, name, aspect in (("vgaw", "vga", 1.0),
                              ("herc", "herc", 1.55), ("cga", "cga", 2.40)):
        r = rows[key]
        out.append(dict(key=name, aspect=aspect, cardw=r[6] - 16, cardh=r[8],
                        insx=r[9], ch=r[1], unitw=24))
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


# =============================================================================
# the emitter - the faces as the package reads them
#
# ONE COMPACT INDEX, NOT ASCII. The package only ever draws capitals, digits,
# a space, four marks and the seven stat icons, so the faces are packed as 48
# consecutive glyphs and `ti_chidx` maps a byte to one. Emitting 32..90 instead
# would be 91 glyphs of which 43 are never drawn - at 8 rows each that is 344
# bytes of a package that has 60KB for everything.
#
# THE TALL FACE'S ICONS ARE THE ONES ALREADY ON SCREEN, byte for byte out of
# ti_ic_* - a second drawing of the same coin would be a second coin.
# =============================================================================

ORDER = ([("icon", i) for i in range(1, 10)] + [("c", " ")] +
         [("c", c) for c in "0123456789"] +
         [("c", c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"] +
         [("c", c) for c in "-.+/,:"])

TALL_ICONS = {                      # 8x8, and the first five are ti_ic_*'s own
    1: [0x66, 0xFF, 0xFF, 0xFF, 0x7E, 0x3C, 0x18, 0x00],   # heart   HP
    2: [0x3C, 0x66, 0xDB, 0xDB, 0xDB, 0xDB, 0x66, 0x3C],   # coin    gold
    3: [0x3C, 0x7E, 0xDB, 0xFF, 0xE7, 0x7E, 0x3C, 0x18],   # soul
    4: [0x18, 0x18, 0x18, 0x18, 0x7E, 0x18, 0x18, 0x3C],   # sword   melee
    5: [0xFF, 0xC3, 0xC3, 0x66, 0x66, 0x3C, 0x18, 0x00],   # shield
    6: [0x60, 0x50, 0x48, 0x44, 0x48, 0x50, 0x60, 0x00],   # bow     ranged
    7: [0x18, 0x18, 0x7E, 0x3C, 0x66, 0x42, 0x00, 0x00],   # star    special
    8: [0x80, 0xC0, 0xE0, 0xF0, 0xE0, 0xC0, 0x80, 0x00],   # stance  FRONT
    9: [0x80, 0xC0, 0xE0, 0xF0, 0x00, 0x00, 0xFE, 0x00],   # stance  SNIPE
}


def pack_face(f, icons=None):
    """48 glyphs x cellh bytes, MSB first - what the composer ORs in."""
    out = []
    for kind, v in ORDER:
        code = v if kind == "icon" else ord(v)
        if icons and kind == "icon":
            rows = icons[code]
            out.append(list(rows))
            continue
        g = f.g.get(code)
        if g is None:
            out.append([0] * f.h)
            continue
        rows = []
        for r in g:
            b = 0
            for i, c in enumerate(r):
                if c == "#":
                    b |= 0x80 >> i
            rows.append(b)
        out.append(rows)
    return out


def shipped():
    """The faces the package carries - named once, for `emit` and the gate."""
    # TWO FACES, AND WHICH ONE IS THE SURFACE'S (SPEC.md 97.4.1.1). tithe6 is
    # face 0: the board's numbers, the HUD and the vertical card strip, the
    # only face a CGA card can carry a line of at all. The tall 8x8 is face 1
    # and it is the FULLSCREEN HAND's (97.4.12) - more legible, and a portrait
    # card along the bottom has the rows for it that a strip row never had.
    return [("t6", Face("fonts/tithe6.f6"), None),
            ("tall", Face("fonts/tallx.f8"), TALL_ICONS)]


def emit(path):
    faces = shipped()
    L = ["; GENERATED by tools/os88titheface.py - do not edit.",
         "; TITHE's faces (SPEC.md 97.4.1): 48 glyphs each, MSB first, one byte a",
         "; row. The composer ORs them into a band; nothing here reaches a kernel",
         "; drawing slot.", "",
         "TI_FACES    equ %d" % len(faces),
         "TI_GLYPHS   equ %d" % len(ORDER), ""]
    L.append("ti_face_tab:")
    L.append("    dw " + ", ".join("ti_f_%s" % n for n, _, _ in faces))
    L.append("ti_face_w:  db " + ", ".join(str(f.w) for _, f, _ in faces))
    L.append("ti_face_h:  db " + ", ".join(str(f.h) for _, f, _ in faces))
    L.append("ti_face_nm: dw " + ", ".join("ti_fn_%s" % n for n, _, _ in faces))
    for n, f, _ in faces:
        L.append("ti_fn_%s: db '%-4s', 0" % (n, n.upper()))
    L.append("")
    total = 0
    for n, f, ic in faces:
        L.append("ti_f_%s:" % n)
        for rows in pack_face(f, ic):
            L.append("    db " + ", ".join("0%02Xh" % b for b in rows))
            total += len(rows)
    open(path, "w").write("\n".join(L) + "\n")
    print("%s: %d faces x %d glyphs, %d bytes"
          % (path, len(faces), len(ORDER), total))


def render(face, icons, text):
    """The pixel rows a run of `text` makes - the composer's own arithmetic.

    It exists so a TEST can compare what the machine drew against what the
    face says it should have, which is the only thing that catches a glyph
    the face HAS and the package's index cannot reach: every mark below '0'
    answered "no such glyph" for as long as this face has existed, because
    `ti_chidx` tested for a digit first and fell to its refusal, and the one
    mark anything wrote was the COLON - which sorts above '9' and got there
    the long way round. Nothing in the faces was wrong, so nothing that reads
    the faces could have told.
    """
    packed = {}
    for code, rows in face.g.items():
        packed[code] = [sum(0x80 >> i for i, c in enumerate(r) if c == "#")
                        for r in rows]
    for code, rows in (icons or {}).items():
        packed[code] = list(rows)
    out = [[0] * (len(text) * face.w) for _ in range(face.h)]
    for n, ch in enumerate(text):
        code = ord(ch.upper()) if isinstance(ch, str) else ch
        g = packed.get(code)
        if g is None:
            continue
        for y in range(face.h):
            for x in range(8):
                if g[y] & (0x80 >> x):
                    px = n * face.w + x
                    if px < len(out[y]):
                        out[y][px] = 1
    return out


def selfcheck():
    bad = []
    need = set(range(1, 10)) | {32} | set(range(48, 58)) | set(range(65, 91))
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

    # ...AND AN ICON MUST NOT MERELY DIFFER, IT MUST BE TELLABLE APART.
    # Identical is the failure that reads as a typo; NEARLY identical is the
    # one that ships. At five pixels the coin was a ring with a pip and the
    # digit 0 was a ring with a stroke - two pixels apart - and the shield was
    # the heart with its top row filled in, also two. Both sat in a column of
    # numbers where the reader has no context to recover from, so the gate is
    # a DISTANCE and not an inequality.
    #
    # IT IS THE SHIPPED FACES THAT ARE GATED, which is why this is not in the
    # loop above: tithe4's 3x5 ink cannot clear it at all - fourteen of its
    # glyph pairs are inside three pixels and that is a property of the size -
    # and tithe4 is a CANDIDATE that `emit` does not carry. Gating it would
    # only mean deleting it, which decides the face question by arithmetic
    # rather than by looking.
    for name, f, icons in shipped():
        ink = {}
        for code, rows in f.g.items():
            ink[code] = [p == "#" for r in rows for p in r]
        for code, rows in (icons or {}).items():       # ...a packed icon wins
            ink[code] = [bool(b & (0x80 >> x)) for b in rows for x in range(f.w)]
        for code in range(1, 10):
            if code not in ink:
                bad.append("%s has no icon %d" % (name, code))
                continue
            for other, bits in ink.items():
                if other in (code, 32) or len(bits) != len(ink[code]):
                    continue
                d = sum(1 for a, b in zip(ink[code], bits) if a != b)
                if d < ICON_APART:
                    bad.append("%s icon %d and glyph %d are %d pixel(s) apart "
                               "- under %d nobody reads them as two things"
                               % (name, code, other, d, ICON_APART))
    # ...AND EVERY CHARACTER THE PACKAGE ACTUALLY WRITES MUST EXIST.
    # `ti_chidx` answers 0FFh for a byte no face carries and `ti_glyph` then
    # draws NOTHING - no box, no fallback, just a gap the width of a cell. A
    # colon in an ability line came out as a hole with no error anywhere, and
    # the only way that is ever noticed is by reading the screen. So the
    # STRINGS are the input here: every `db '...'` in the package, against the
    # 48 glyphs the faces carry.
    have = set(" 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.+/,:")
    src = open("apps/tithe/tithe.asm", encoding="utf-8").read()
    for n, line in enumerate(src.split("\n"), 1):
        # CUT THE COMMENT OFF FIRST, and cut it at a `;` that is OUTSIDE a
        # quoted literal - nasm comments are full of apostrophes and prose,
        # and a scanner that took them for strings reports the whole file.
        code, q = [], False
        for ch in line:
            if ch == "'":
                q = not q
            if ch == ";" and not q:
                break
            code.append(ch)
        code = "".join(code)
        if " db " not in " " + code.strip():
            continue
        for lit in re.findall(r"'([^']*)'", code):
            if len(lit) == 1:
                continue                # a character CONSTANT, not a string
            miss = sorted({c for c in lit.upper() if c not in have})
            if miss:
                bad.append("tithe.asm:%d writes %s, which no face carries"
                           % (n, ", ".join(repr(c) for c in miss)))
    for line in bad:
        print("  FAIL %s" % line)
    print("os88titheface: %d face(s), %s"
          % (len(shipped()), "%d problem(s)" % len(bad) if bad else "ok"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("cmd", nargs="?", default="sheet", choices=["sheet", "emit"])
    ap.add_argument("--selfcheck", action="store_true")
    a = ap.parse_args()
    if a.selfcheck:
        return selfcheck()
    if a.cmd == "emit":
        emit("apps/tithe/tifaces.inc")
        return 0
    faces = [Face("fonts/tithe4.f4"), Face("fonts/tithe6.f6"),
             Face("fonts/tallx.f8")]
    sheet_out(faces, "build/tithe-faces.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
