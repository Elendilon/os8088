#!/usr/bin/env python3
"""THE DOS BOX'S CONSOLE, AND THE PROMPT IN IT (SPEC.md 96.33).

The band below the top bar carried three lines of status text until this wave
and now carries an 80x25 screen. What that is worth is a list of things a
person can DO, so the row drives them in the order a person would - and every
one of them is a separate thing that can be missing:

  1  a box launched with NO document opens on a PROMPT, not on an error, and
     the prompt names the drive it was launched from (96.33.2). It read `A:\\>`
     on a machine standing on C: until OSAPI_FILE_HERE was asked.
  2  typing ECHOES, and costs ONE ROW of redraw and not twenty-five - the
     dirty-row bitmap is the whole reason the console is not a glyph call per
     cell (70.8.1), and a renderer that lost it would look identical.
  3  a BUILT-IN runs and its output lands in the band: VER is dosh.inc's and
     was reachable only from `AH=4Bh` before there was a prompt.
  4  DIR - the one verb the table was missing (96.33.4) - lists the folder
     with `<DIR>` for a folder and a size for a file.
  5  CD moves, and THE PROMPT FOLLOWS IT. `$P$G` is recomposed rather than
     held, so this is the assertion that says so.
  6  a PROGRAM is run by typing its name (96.33.3), the path box ends up
     holding what was typed, and the exit line comes back into the console.
  7  ...and a name that is neither says `Bad command or file name`, which is
     DOS's sentence and not "It could not be read." about a file the user
     never had.
  8  FULL SCREEN puts the same buffer on real text VRAM and ESC comes back
     (96.33.5). The assertion is VRAM's OWN BYTES at the segment the bracket
     was handed, CELL FOR CELL over all 2,000 - because that is the whole
     claim the design makes: con_scr's cell IS the cell in VRAM, so the
     renderer is a move and not a translation (70.8.7), and a screenshot
     cannot tell those apart.

...and 5b, between them, is that a bare `B:` is a DRIVE CHANGE and not a verb
(96.33.6) - which the box answered `Bad command or file name` until it was
reported, because a drive letter falls through a table that has no row for it.
`Z:` must be refused AND must not move.

**IT READS THE BUFFER AND NOT THE GLASS**, with one exception. con_scr is
2,000 cells of (character, attribute) and every assertion above is about
CHARACTERS, so reading pixels would be reading a font. The exception is
assertion 2's cost, which is counted in the guest's own marks - and the one
PICTURE check, that the band is actually BLACK, because a console whose
buffer is perfect and whose glyph table is empty draws a black rectangle and
reads green from every other row here. That is not hypothetical: it is what
the first build did, con_open having not called con_font.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88marty                                               # noqa: E402
import os88ui                                                  # noqa: E402

SYS = "build/os8088-360.img"
APPS = "build/apps360.img"
BOX = "A:/APPS/DOS.O88"


def fail(msg):
    print("doscon: FAIL: %s" % msg)
    sys.exit(1)


class Box(object):
    """The live instance, and the two reads every assertion is made of."""

    def __init__(self, m):
        self.m = m
        self.dm = dosmap.package()
        self.seg = dosmap.instance(m)
        self.base = self.seg << 4

    def w(self, name):
        return int.from_bytes(self.m.read(self.base + self.dm[name], 2),
                              "little")

    def b(self, name):
        return self.m.read(self.base + self.dm[name], 1)[0]

    def text(self, name, n):
        raw = self.m.read(self.base + self.dm[name], n)
        return raw.split(b"\0")[0].decode("latin-1")

    def rows(self):
        """The console buffer as 25 rstripped lines of text."""
        scr = self.m.read(self.base + self.dm["con_scr"], 80 * 25 * 2)
        out = []
        for r in range(25):
            row = scr[r * 160:(r + 1) * 160]
            out.append("".join(chr(row[i]) if 32 <= row[i] < 127 else " "
                               for i in range(0, 160, 2)).rstrip())
        return out

    def live(self):
        """...and the ones with anything on them, in order."""
        return [r for r in self.rows() if r.strip()]

    def type(self, s):
        self.m.type_text(s)
        os88marty.settle(self.m)


def band_ink(m, bx):
    """(lit, dark) pixels INSIDE the console band, found by its own shape.

    **NOT AT AN ADDRESS.** The rendered frame is not in guest coordinates -
    MartyPC's Hercules aperture starts sixteen columns in - so a rectangle read
    at [dos_conx] lands partly on the window's WHITE MARGIN either side of the
    band, and 40 pixels of that margin look exactly like 40 pixels of text.
    Measured: with con_font deliberately removed, an address-read band still
    reported 3,951 lit pixels and the check stayed green.

    So the band is found instead: the widest run of DARK pixels on any row of
    it is a blank text row and gives the x extent, and a row counts as the
    band's when that extent is mostly dark. Everything outside is ignored.
    """
    w, h, px = m.fbuf()
    y0 = bx.w("dos_cony")
    rws = bx.w("dos_conrows") * 8
    lo = max(0, y0 - 6)
    hi = min(h, y0 + rws + 6)

    def runs(y):
        row = px[y * w * 3:(y + 1) * w * 3]
        out, st = [], None
        for x in range(w):
            if row[x * 3] <= 128:
                if st is None:
                    st = x
            elif st is not None:
                out.append((st, x - 1))
                st = None
        if st is not None:
            out.append((st, w - 1))
        return out

    # **THE MODAL EXTENT AND NOT THE WIDEST.** The window's own bottom border is
    # one full-width dark row, so "widest" picks 0..719 - and then the band's
    # white MARGINS are inside the rectangle and read as text. Measured: with
    # con_font removed the widest-run version reported 12,855 lit pixels and
    # stayed green. The band is twenty-five rows and the border is one, so the
    # extent that occurs most often is the band's.
    tally = {}
    for y in range(lo, hi):
        r = runs(y)
        if not r:
            continue
        a, b = max(r, key=lambda ab: ab[1] - ab[0])
        if b - a >= 200:
            tally[(a, b)] = tally.get((a, b), 0) + 1
    if not tally:
        fail("no dark band found under the top bar in rows %d..%d, and an "
             "80-column console is 640 pixels of one (SPEC.md 96.33)"
             % (lo, hi))
    x1, x2 = max(tally, key=lambda k: (tally[k], k[1] - k[0]))
    span = x2 - x1 + 1
    lit = dark = 0
    for y in range(lo, hi):
        row = px[y * w * 3:(y + 1) * w * 3]
        d = sum(1 for x in range(x1, x2 + 1) if row[x * 3] <= 128)
        if d * 10 < span * 6:
            continue                        # not one of the band's rows
        lit += span - d
        dark += d
    return lit, dark


def main():
    for p in (SYS, APPS):
        if not os.path.exists(p):
            fail("%s is missing - a plain `make` builds it" % p)

    with os88ui.boot(SYS, apps=APPS, machine="os8088_5150_herc_gla") as ui:
        m = ui.m
        if not ui.path(BOX):
            fail("could not launch %s" % BOX)
        bx = Box(m)

        # --- 1: a prompt, and it names the drive we came from ----------------
        rows = bx.live()
        print("doscon: the box opens on:")
        for r in rows[:6]:
            print("   | %s" % r)
        if not rows or not rows[-1].endswith(">"):
            fail("a box launched with no document should open on a PROMPT and "
                 "the last live row is %r" % (rows[-1] if rows else None))
        want = "%s:\\>" % chr(ord("A") + bx.b("dos_vol"))
        if rows[-1] != want:
            fail("the prompt is %r and the box is standing on volume %d, so "
                 "$P$G is %r (SPEC.md 96.33.2)"
                 % (rows[-1], bx.b("dos_vol"), want))

        # --- 2: typing echoes, one row of redraw at a time ------------------
        before = bx.w("con_cx")
        bx.type("VER")
        if bx.w("dos_cmdn") != 3:
            fail("three keys reached the console and it holds %d of them"
                 % bx.w("dos_cmdn"))
        if bx.w("con_cx") != before + 3:
            fail("three glyphs were echoed and the cursor moved %d columns"
                 % (bx.w("con_cx") - before))
        if not bx.live()[-1].endswith(">VER"):
            fail("the typed text is not on the prompt's row: %r"
                 % bx.live()[-1])

        # --- 3: a built-in runs, into the band ------------------------------
        bx.type("\n")
        rows = bx.live()
        if not any("os8088 DOS Version" in r for r in rows[-3:]):
            fail("VER ran and its line is not in the band - the last rows are "
                 "%r" % rows[-3:])

        # --- ...and the BAND IS BLACK, which the buffer cannot say ----------
        # A console with a perfect buffer and an empty glyph table draws a
        # black rectangle and passes every other check in this file. It is
        # what the first build did (con_open did not call con_font), so this
        # counts LIT pixels in the band and wants some.
        # 500, and the gap it sits in is two orders of magnitude: this screen
        # carries ~100 characters at this point and measures ~6,300 lit
        # pixels, and with con_font deliberately removed it measures 47 - the
        # cursor's underline, which con_compose draws from no glyph at all.
        lit, dark = band_ink(m, bx)
        if lit < 500:
            fail("the console band has %d lit pixels in %d dark ones and there "
                 "is text in its buffer - a zeroed [con_glyf] draws a BLACK "
                 "RECTANGLE and every character check above still passes "
                 "(with con_font removed this reads 47, the cursor alone)"
                 % (lit, dark))
        print("doscon: the band is %d lit of %d pixels - black with text on it"
              % (lit, lit + dark))

        # --- 4: DIR, the verb the table was missing -------------------------
        bx.type("DIR\n")
        rows = bx.live()
        body = [r for r in rows if "<DIR>" in r]
        if not body:
            fail("DIR listed no folder and this volume's root has four: %r"
                 % rows[-8:])
        if not any(r.strip().endswith("file(s)") for r in rows):
            fail("DIR printed no footer: %r" % rows[-4:])
        print("doscon: DIR lists %d folder(s) and a footer" % len(body))

        # --- 5: CD moves, and the prompt follows ----------------------------
        bx.type("CD APPS\n")
        rows = bx.live()
        if rows[-1] != "%s:\\APPS>" % chr(ord("A") + bx.b("dos_vol")):
            fail("CD APPS left the prompt at %r - $P$G is recomposed at every "
                 "prompt so that it cannot go stale (SPEC.md 96.33.2)"
                 % rows[-1])
        print("doscon: ...and the prompt follows CD: %r" % rows[-1])

        # --- 5b: a bare X: changes DRIVE, which is not a verb ---------------
        # DOS answers it before the table, and the box did not answer it at
        # all: `B:` came back `Bad command or file name` (SPEC.md 96.33.6).
        here = bx.b("dos_vol")
        other = "B" if here == 0 else "A"
        bx.type("%s:\n" % other)
        if bx.b("dos_vol") != (1 if here == 0 else 0):
            fail("%s: left the box on volume %d - a bare drive letter is a "
                 "DRIVE CHANGE and not a verb (SPEC.md 96.33.6)"
                 % (other, bx.b("dos_vol")))
        if not bx.live()[-1].startswith("%s:" % other):
            fail("the prompt did not follow the drive change: %r"
                 % bx.live()[-1])
        bx.type("Z:\n")
        rows = bx.live()
        if not any("Invalid drive" in r for r in rows[-3:]):
            fail("a drive that is not there should answer DOS's own "
                 "`Invalid drive specification`, and the band says %r"
                 % rows[-3:])
        if bx.b("dos_vol") != (1 if here == 0 else 0):
            fail("a REFUSED drive change moved the box anyway, to volume %d"
                 % bx.b("dos_vol"))
        print("doscon: ...and %s: changes drive while Z: is refused without "
              "moving" % other)
        bx.type("%s:\n" % chr(ord("A") + here))

        # --- 7: a name that is neither a verb nor a file --------------------
        bx.type("NOSUCH\n")
        rows = bx.live()
        if not any("Bad command" in r for r in rows[-3:]):
            fail("a name that is neither a built-in nor a program should "
                 "answer DOS's own `Bad command or file name`, and the band "
                 "says %r (SPEC.md 96.33.3)" % rows[-3:])
        print("doscon: ...and an unknown name is a bad command, not a read "
              "error")

        # --- 6: a PROGRAM, by typing its name -------------------------------
        # DOS.O88 is in this folder and is not a DOS program, so the launch
        # refuses - which is the half this row can assert without a second
        # disk: the path box holds what was typed, the state moved, and the
        # console got a line back. tests/dosargs.py drives a real .COM.
        bx.type("DOS.O88\n")
        if bx.text("dos_path", 32).upper() != "DOS.O88":
            fail("typing a program's name should put it in the path box and "
                 "it holds %r (SPEC.md 96.33.3)" % bx.text("dos_path", 32))
        rows = bx.live()
        if not any("DOS.O88" in r for r in rows[-4:]):
            fail("the console said nothing about the program that was run: %r"
                 % rows[-4:])
        print("doscon: ...and typing a program's name fills the path box and "
              "reports back")

        # --- 8: FULL SCREEN, and Esc back out of it (SPEC.md 96.33.5) -------
        # The assertion is TEXT VRAM's own bytes, read out of the guest at the
        # segment the bracket was handed - B000 on this Hercules, B800 on the
        # rest - because that is the whole claim the design makes: con_scr's
        # cell IS the cell in VRAM, so the renderer is a move and not a
        # translation (70.8.7). A screenshot could not tell that from a
        # translation that happened to work.
        want = [r for r in bx.live()][-6:]
        ui.menu_pick("Program", "Full Screen")
        time.sleep(2.0)
        if not bx.b("dos_fsxup"):
            fail("Program > Full Screen did not take the screen: [dos_fsxup] "
                 "is 0 (SPEC.md 96.33.5)")
        seg = bx.w("con_tseg")
        if seg not in (0xB000, 0xB800):
            fail("the bracket's framebuffer segment is %04X, and FSXM_TEXT80 "
                 "is B000 on Hercules and B800 on the rest" % seg)
        # **CELL FOR CELL, all 2,000 of them** - which is a far stronger claim
        # than "every line is present somewhere", and the one 70.8.7 actually
        # makes. The ATTRIBUTE byte is deliberately not compared: on a mono
        # adapter con_tx_mattr maps it (70.8.9) and on a colour one it does
        # not, so the CHARACTER is the half that is a pure move on every
        # adapter.
        buf = m.read(bx.base + bx.dm["con_scr"], 80 * 25 * 2)
        vram = m.read(seg << 4, 80 * 25 * 2)
        hint = " Esc to leave"
        pairs = []
        for r in range(25):
            pairs.append(("".join(chr(buf[r * 160 + c * 2]) for c in range(80)),
                          "".join(chr(vram[r * 160 + c * 2]) for c in range(80))))
        for r, (b, v) in enumerate(pairs):
            if r == 24:
                b, v = b[:80 - len(hint)], v[:80 - len(hint)]   # the hint has
                                                               # the row's TAIL
                                                               # and may (70.8.7)
            if b != v:
                col = next(i for i in range(len(b)) if b[i] != v[i])
                fail("the full screen is not the buffer: row %d column %d is "
                     "%r in con_scr and %r in text VRAM at %04X. The cell IS "
                     "the cell (SPEC.md 70.8.7), so this is a MOVE and cannot "
                     "differ" % (r, col, b[col], v[col], seg))
        got = [v for _, v in pairs if v.strip()]
        if hint not in pairs[24][1]:
            fail("the bottom row does not name the key that leaves: %r"
                 % pairs[24][1])
        print("doscon: full screen is the buffer cell for cell over %d live "
              "rows, and row 24 says how to get out" % len(got))

        m.key("Escape")
        time.sleep(2.0)
        if bx.b("dos_fsxup"):
            fail("Esc did not leave the full screen: [dos_fsxup] is still set. "
                 "It is OURS only while the console has the screen - a running "
                 "program's Esc is the program's (SPEC.md 96.33.5)")
        rows = bx.live()
        if rows[-1] != want[-1]:
            fail("the window came back showing %r where it went in on %r"
                 % (rows[-1], want[-1]))
        print("doscon: ...and Esc comes back to the window on the same line")

    print("doscon: ok")


if __name__ == "__main__":
    main()
