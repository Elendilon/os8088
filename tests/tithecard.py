#!/usr/bin/env python3
"""TITHE's card panel and HUD: does everything stay inside its own box?

SPEC.md 97.4.1's gate, and 97.4.8's. The panel is one `OSAPI_GFX_BLIT1` a card
now - a band composed by the package, in the package's OWN face - and every
defect it has had is a thing crossing a boundary or failing to come back:

  1. A ROW THAT DOES NOT FIT IS NOT DRAWN. The flow's bottom test was off by
     one row, so a VGA card started a fourth line of text and the card's foot
     cut it in half.

  2. THE FIGURE OWNS A COLUMN. Before the flow had a right margin the stat row
     ran under the mini unit and off the card's right-hand edge.

  NEITHER OF THOSE IS VISIBLE AS A BROKEN FRAME LINE, which is the lesson of
  this file: the band is composed by OR and the frame is drawn FIRST, so a
  glyph landing on it changes no pixel at all. Both were put back in on
  purpose and PASSED a frame-line check. What catches them is the row above
  the foot being blank and the three-column gutter to the figure being clear.

  3. THE PANEL COMES BACK. The hovered card expands into the panel's 8-pixel
     margins, and the composer dropped the `gfx_fill` of the whole panel row
     that used to put them back - so moving off a card left a stripe of it
     down each side. The margins are part of the composition now.

  4. THE HOVERED CARD'S FIGURE KEEPS ITS POLARITY. The wheel redraws the unit
     ALONE every frame at a pen of its own, and that pen said the opposite of
     what the composition says - so the card went down right and was inverted
     one frame later, which on the glass is a figure that goes black part of
     the way round its cycle.

  5. THE FACE FITS. One face ships (the 6x6, SPEC.md 97.4.1.1) and every card
     carries at least a row of it; the `T` key that compared it with a tall
     8x8 went at the demo cleanup, because on CGA the 8x8 fitted no row.

  6. THE TOGGLE AND THE STATUS LINE (97.4.8). Every card restates its stats
     when FRONT/REAR flips - a toggle that redrew one card would leave six
     stating the other row's - and the HUD says what the pointer is over and
     comes back WHOLE, which the centred `font_run` it replaced could not do:
     a run draws only its own length, so a forty-character ability line after
     a fifty-three-character one left thirteen characters behind.

Every check runs on all three adapters, because the card's height is a
geometry-table field and the flow's answer differs on each.
"""
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import os88ui                                             # noqa: E402
import os88marty                                          # noqa: E402
import os88geom                                           # noqa: E402
import os88mouse                                          # noqa: E402
import os88titheface                                      # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SYMS = ("ti_cardx", "ti_cardw", "ti_cardh", "ti_cardpitch", "ti_cardn",
        "ti_by", "ti_crows", "ti_face", "ti_fh", "ti_panx",
        "ti_pan", "ti_unith", "ti_cpad", "ti_row", "ti_hx", "ti_hw",
        "ti_hnx", "ti_nrows", "ti_hovc", "ti_bx", "ti_cw", "ti_ch",
        "TI_CELLROWS", "ti_aseg", "ti_cslot", "TI_POSES",
        "ti_bs", "ti_bh",
        "ti_oy", "ti_hud", "ti_tg0x", "ti_tg1x", "TI_FACES", "TI_UNITW")
MACHINES = ("os8088_xt_vga", "os8088_5150_herc_gla", "os8088_5150_cga_gla")
# The ability line of the card the hover checks land on - hand row 5, the
# HERALD. Kept here rather than scraped out of the source, so a change to the
# text is a change somebody makes on purpose.
#
# IT IS THE ONE WITH A COMMA IN IT, deliberately. Row 2's line has only a
# colon, and a colon is the ONE mark that worked while every other one was
# unreachable - it sorts above '9', so it reached the mark table the long way
# round where `+ , - . /` fell to the index's refusal. A row chosen without
# looking at its punctuation passed the break that this check exists for.
HOVER_ROW = 5
ABILITY = "CALL: ONE MORE PLAY THIS ROUND, PAID IN GOLD"

# ...and the whole set, because a BOARD hover names a card by the cell it is
# over and the test cannot choose which cell the pointer lands on.
ABILITIES = [
    "BRACES: THE FIRST CHARGE INTO THIS LANE IS HALVED",
    "VOLLEY: STRIKES THE REAR RANK FROM BEHIND THE LINE",
    "HOLD: THE LANE DOES NOT BREAK WHILE THE WARDEN STANDS",
    "TITHE: TAKES A SOUL FROM EVERY DEATH IN THIS LANE",
    "BREACH: A GATE, AND WHATEVER IS STANDING BEHIND IT",
    "CALL: ONE MORE PLAY THIS ROUND, PAID IN GOLD",
    "NOTHING PASSES WHILE IT STANDS. NOTHING.",
]
POWER = [1, 2, 3, 2, 4, 2, 5]           # TI_C_PWR, card by card
NAMES = ["PIKEMAN", "ARCHER", "WARDEN", "ACOLYTE", "RAM", "HERALD", "BULWARK"]
HAND = 7

fails = []


def check(ok, what, got=""):
    print("  %-4s %s%s" % ("ok" if ok else "FAIL", what,
                           "" if ok else "   got: %s" % got))
    if not ok:
        fails.append(what)


def offsets():
    """Assembled from the SOURCE, so the offsets cannot drift from the binary."""
    src = open(os.path.join(ROOT, "apps/tithe/tithe.asm"), encoding="utf-8").read()
    tmp = os.path.join(ROOT, "build", "tithecard-off.asm")
    out = os.path.join(ROOT, "build", "tithecard-off.bin")
    open(tmp, "w", encoding="utf-8").write(
        src + "\n\nsection .text\n" + "".join("dw %s\n" % s for s in SYMS))
    subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                    "-I", "apps/tithe/", "-o", out, tmp], cwd=ROOT, check=True)
    base = os.path.getsize(os.path.join(ROOT, "build", "tithe.bin"))
    blob = open(out, "rb").read()
    return {s: blob[base + i * 2] | (blob[base + i * 2 + 1] << 8)
            for i, s in enumerate(SYMS)}


def mono(m):
    """The screen as rows of booleans - lit or not.

    ON 1bpp IT IS THE GUEST'S OWN FRAMEBUFFER and not the rendered frame.
    `fbuf` asks the CARD what it rasterised, and MartyPC's Hercules raster
    carries two rows of overscan above the picture - so every rect read two
    pixels low there and the card's own frame line looked broken. `vram` is
    the byte-exact route on both 1bpp adapters (and is what the assertion is
    really about: did the kernel put these bits at this address). VGA has no
    flat framebuffer to read at all - mode 12h is four planes behind the
    Graphics Controller - so it stays on `fbuf`, where the origin is exact.
    """
    if m.cmd(cmd="video")["type"] in ("cga", "herc", "mda"):
        w, h, rows = m.vram()
        return w, h, [[bool(b) for b in r] for r in rows]
    w, h, d = m.fbuf()
    return w, h, [[d[(y * w + x) * 3] > 127 for x in range(w)] for y in range(h)]


def run(mach, off):
    print("  --- %s" % mach)
    with os88ui.boot("build/os8088-360.img", apps="build/tithe360.img",
                     machine=mach) as ui:
        m = ui.m
        ui.path("B:/TITHE.O88")
        win = [w for w in os88geom.windows(m) if w.title == "Tithe"][0]
        seg = struct.unpack(
            "<H", bytes(m.read(os88geom.winptr(m, win) + os88geom.W_SEG, 2)))[0]
        ui.raise_window(win)
        os88marty.guest_sleep(m, 4.0)
        rw = lambda n: struct.unpack("<H", bytes(m.readseg(seg, off[n], 2)))[0]

        rows_seen = []
        for face in range(off["TI_FACES"]):
            name = "face %d" % rw("ti_face")
            rows_seen.append((rw("ti_fh"), rw("ti_crows")))
            w, h, px = mono(m)
            # THE PACKAGE'S COORDINATES ARE THE SCREEN'S. A kernel drawing
            # slot takes a screen x and y, so what the package banks is one
            # too - adding the window's content origin here put every rect a
            # whole HUD lower and read the desktop as a broken card. It is
            # the trap ti_basey carries its own note about, one file along.
            x, cw, ch = rw("ti_cardx"), rw("ti_cardw"), rw("ti_cardh")
            px0, pw = rw("ti_panx"), rw("ti_pan")
            pitch, n, by = rw("ti_cardpitch"), rw("ti_cardn"), rw("ti_by")

            broke, leaked = [], []
            for i in range(n):
                x0, x1 = x, x + cw - 1
                y0, y1 = by + i * pitch, by + i * pitch + ch - 1
                if y1 >= h or x1 + 1 >= w or x0 < 1:
                    continue
                # THE FRAME IS ASSERTED UNIFORM AND NOT LIT. A resting card is
                # the package's pen the other way round - black ink on white
                # paper (SPEC.md 5.4.2.2) - so its frame is the same colour as
                # the panel's ground and a "the frame is lit" test passes on
                # the hovered card and fails on the other six.
                ink = px[y0][x0]
                for xx in range(x0, x1 + 1):
                    if px[y0][xx] != ink:
                        broke.append((i, xx, "top"))
                    if px[y1][xx] != ink:
                        broke.append((i, xx, "foot"))
                for yy in range(y0, y1 + 1):
                    if px[yy][x0] != ink:
                        broke.append((i, yy, "left"))
                    if px[yy][x1] != ink:
                        broke.append((i, yy, "right"))
                # ...and the row inside each upright is PAPER: the flow's
                # margin starts at x=3 and the figure ends before the pad, so
                # a glyph in either column is one that ran past its line.
                for yy in range(y0 + 1, y1):
                    if px[yy][x0 + 1] == ink or px[yy][x1 - 1] == ink:
                        leaked.append((i, yy, "inside the upright"))
                # THE ROW ABOVE THE FOOT IS BLANK, which is how a PARTIAL row
                # is caught. The obvious assertion - that the foot's frame
                # line is unbroken - cannot see one: the band is composed by
                # OR, the frame is drawn first and is already set, so a glyph
                # landing on it changes no pixel at all. What a row too many
                # DOES leave is the top of a glyph in the rows just above the
                # foot, and the flow's grid puts nothing there: lines start at
                # 2+cpad and step by the face's height, so the last legal one
                # ends at cardh-3-cpad or higher.
                for xx in range(x0 + 1, x1):
                    if px[y1 - 1][xx] == ink:
                        leaked.append((i, xx, "a partial row above the foot"))
                # ...AND THE GUTTER TO THE FIGURE IS CLEAR, which is how the
                # other one is caught. Text running under the mini unit and
                # off the card is invisible to the upright check for the same
                # OR reason; what it cannot avoid is crossing the three
                # columns between the flow's right margin and the figure's
                # own, which nothing is ever drawn in.
                gut = x0 + cw - off["TI_UNITW"] - 11
                for yy in range(y0 + 1, y1):
                    for xx in range(gut, gut + 3):
                        if px[yy][xx] == ink:
                            leaked.append((i, yy, "in the figure's gutter"))
            check(not broke, "%s: every card's frame is unbroken" % name,
                  "%d break(s), first %s" % (len(broke), broke[:3]))
            check(not leaked, "%s: nothing is drawn outside the flow's grid" % name,
                  "%d pixel(s), first %s" % (len(leaked), leaked[:3]))

        # ONE FACE SHIPS NOW (SPEC.md 97.4.1.1), so what was "the shorter face
        # fits more rows" is the floor it stood on: a card carries text at
        # all. On CGA the tall face fitted none, which is why it went.
        check(all(r[1] >= 1 for r in rows_seen),
              "every card carries at least one row of text",
              "%s" % rows_seen)

        # AND MOVING OFF A CARD LEAVES NOTHING BEHIND. The hovered card
        # expands sideways into the panel's 8-pixel margins, so the row the
        # pointer LEAVES has to put those margins back - and the composer's
        # first build did not, because the `gfx_fill` of the whole panel row
        # that used to do it went away with the eleven other calls. The margins
        # are part of the composition now, which costs no arrival; this is the
        # assertion that says so, and it is a PIXEL COMPARISON against the
        # panel before anything was hovered rather than a rule about what
        # should be there.
        w, h, before = mono(m)
        x0, y0 = rw("ti_panx"), rw("ti_by")
        y1 = min(y0 + rw("ti_cardn") * rw("ti_cardpitch"), h)
        marg = rw("ti_cardx") - x0
        # THE MARGINS AND NOT THE WHOLE PANEL. The card's own body is where the
        # figure is, and the figure is on a clock: a card is redrawn only when
        # the hover changes, so its pose is whatever the clock had reached and
        # two captures a few seconds apart differ there by design. Reading the
        # whole panel row measured the ANIMATION and called it residue.
        def margins(p):
            return [(r[x0:x0 + marg], r[x0 + rw("ti_pan") - marg:x0 + rw("ti_pan")])
                    for r in p[y0:y1]]
        base = margins(before)
        mo = os88mouse.Mouse(marty=m)
        mid = y0 + HOVER_ROW * rw("ti_cardpitch") + rw("ti_cardh") // 2
        mo.to(x0 + 20, mid)                     # ...onto a card
        os88marty.guest_sleep(m, 1.5)

        # THE FIGURE ON THE HOVERED CARD MOVES, AND IT STAYS THE CARD'S OWN
        # POLARITY. Two defects met here and each hid the other. The wheel
        # redraws the unit ALONE every frame, at a pen of its own, and that pen
        # said black-ink-on-white where the composition says white-on-black -
        # so the card was composed right and inverted again one frame later,
        # which on the glass is a figure that goes black part of the way round
        # its cycle. And the composer REBUILT the pose it was about to draw,
        # where every pose is built once at art-build time; the rebuild clears
        # TI_UNITMAX bytes - the worst case over every geometry - so on any
        # card but the tallest it blanked the top of the NEXT pose's band.
        top = mid - rw("ti_cardh") // 2
        fy = top + 2 + rw("ti_cpad")
        fx = x0 + rw("ti_pan") - off["TI_UNITW"] - 8
        paper = mono(m)[2][fy + 1][x0 + 1]      # ...BETWEEN the two frames, which
                                                # the upright check above has
                                                # already asserted is ground;
                                                # column 2 is the inner frame
        shots, wrong = [], 0
        for _ in range(5):
            f = mono(m)[2]
            shots.append([r[fx:fx + off["TI_UNITW"]]
                          for r in f[fy:fy + rw("ti_unith")]])
            if f[fy][fx] != paper or f[fy][fx + off["TI_UNITW"] - 1] != paper:
                wrong += 1                      # the band's own corners are
            os88marty.guest_sleep(m, 0.35)      # always ground, whatever pose
        check(wrong == 0,
              "the hovered card's figure keeps the card's own polarity",
              "%d of 5 frames inverted" % wrong)
        check(any(a != b for a, b in zip(shots, shots[1:])),
              "...and it actually moves", "5 identical frames")

        os88marty.guest_sleep(m, 0.5)
        mo.to(x0 // 2, mid)                     # ...and off it again
        os88marty.guest_sleep(m, 2.5)
        after = margins(mono(m)[2])
        left = sum(1 for (la, ra), (lb, rb) in zip(base, after)
                   for p, q in list(zip(la, lb)) + list(zip(ra, rb)) if p != q)
        check(left == 0, "the panel comes back when the pointer leaves a card",
              "%d margin pixel(s) left behind" % left)

        # --- the FRONT/REAR toggle, and the HUD's status line --------------
        # ONE CONTROL FOR THE HAND AND NOT A SWITCH ON EVERY CARD (97.4.8).
        # What it changes is every card at once, so a toggle that redrew only
        # the hovered one would leave six cards stating the stats they would
        # have had in the other row - which is the sort of wrong that reads as
        # a balance question rather than as a bug.
        hud = lambda p: [r[rw("ti_hx"):rw("ti_hx") + rw("ti_hw")]
                         for r in p[rw("ti_oy"):rw("ti_oy") + rw("ti_hud")]]
        pan = lambda p: [r[x0:x0 + rw("ti_pan")] for r in p[y0:y1]]
        was_row = rw("ti_row")
        p0 = pan(mono(m)[2])
        # THE TOGGLE IS CLICKED, as a player does - the `W` key that drove it
        # is gone. The left arm is FRONT and anything right of it REAR
        # (ti_onclick), so the click goes into the arm that is NOT selected.
        def toggle():
            arm = rw("ti_tg1x") if rw("ti_row") == 0 else rw("ti_tg0x")
            mo.click(rw("ti_hx") + arm + 4, rw("ti_oy") + rw("ti_hud") // 2,
                     settle=0.2)
            mo.to(x0 // 2, mid)                 # ...and off the panel
            os88marty.guest_sleep(m, 2.0)
        toggle()
        check(rw("ti_row") != was_row, "the row toggle moves", "%d" % rw("ti_row"))
        p1 = pan(mono(m)[2])
        moved = sum(1 for a, b in zip(p0, p1) for q, r_ in zip(a, b) if q != r_)
        check(moved > 40, "...and every card in the hand restates its stats",
              "%d differing pixel(s)" % moved)
        # ...and the toggle's own box moved with it, which is the only thing
        # on the strip that says WHICH arm is selected on a 1bpp adapter
        tg = lambda p: [r[rw("ti_hx") + rw("ti_tg0x") - 2:
                          rw("ti_hx") + rw("ti_tg1x") + 40]
                        for r in p[rw("ti_oy"):rw("ti_oy") + rw("ti_hud")]]
        toggle()
        check(rw("ti_row") == was_row, "...and back", "%d" % rw("ti_row"))

        # THE HUD SAYS WHAT THE POINTER IS OVER, and puts it back afterwards.
        # The strip was one centred `font_run`, which draws only its own
        # length - so a forty-character ability line followed by a
        # fifty-three-character one left thirteen characters of the first
        # behind. It is a composed band now and this is what says so.
        h0 = hud(mono(m)[2])
        mo.to(x0 + 20, mid)
        os88marty.guest_sleep(m, 2.0)
        h1 = hud(mono(m)[2])
        said = sum(1 for a, b in zip(h0, h1) for q, r_ in zip(a, b) if q != r_)
        check(said > 100, "the HUD says what the pointer is over",
              "%d differing pixel(s)" % said)
        # ...AND IT SAYS THE RIGHT WORDS, compared against the FACE's own
        # bitmaps rather than against a screenshot. This is the only check
        # that can see a glyph the face HAS and `ti_chidx` cannot reach: every
        # mark below '0' - `+ , - . /` - answered "no such glyph" and drew a
        # hole for as long as the faces have existed, because the index tested
        # for a digit before it tested for a mark and fell straight to its
        # refusal. The one mark anything wrote was the COLON, which sorts
        # above '9' and reached the marks the long way round, so the defect
        # shipped invisible - and `--selfcheck`, which reads the FACES, could
        # never have found it: nothing in them was wrong.
        face = [x for x in os88titheface.shipped() if x[0] == "t6"][0]
        want = os88titheface.render(face[1], face[2], ABILITY)
        f = mono(m)[2]
        y = rw("ti_oy") + (rw("ti_hud") - rw("ti_fh")) // 2
        got = [f[y + r][rw("ti_hx") + rw("ti_hnx"):
                        rw("ti_hx") + rw("ti_hnx") + len(want[0])]
               for r in range(rw("ti_fh"))]
        wrong = sum(1 for a, b in zip(want, got)
                    for p_, q in zip(a, b) if bool(p_) != bool(q))
        check(wrong == 0, "...and the line reads as the FACE says it should",
              "%d pixel(s) differ from the host's own render" % wrong)

        # --- THREE BODIES, THREE FIGURES (SPEC.md 97.4.9) -----------------
        # The bands themselves, out of the ARENA: pose 0 of cells 0, 1 and 5,
        # which play the soldier, the hooded caster and the nun. A card whose
        # record collapsed into another - a manifest read at the wrong stride,
        # a body table indexed by the item - draws a board of identical
        # figures. (That each cell is the RIGHT figure, body and item, to the
        # byte, is tests/titheterr.py's.)
        np_ = off["TI_POSES"]
        span = rw("ti_cslot")
        banks = [bytes(m.readseg(rw("ti_aseg"), c * np_ * span, span))
                 for c in (0, 1, 5)]
        same = [(a, b) for a in range(len(banks)) for b in range(a + 1, len(banks))
                if banks[a] == banks[b]]
        check(not same, "the three faction idles are three PICTURES",
              "characters %s share a band" % same)
        check(all(0 < sum(bin(x).count("1") for x in bk) for bk in banks),
              "...and each of them is drawn at all", "an empty band")

        # --- THE BOARD'S OWN STAT COLUMN (SPEC.md 97.4.8.1) ----------------
        # A character states its HP, both variable stats and its POWER beside
        # the figure, in the package's face - the column is 24 pixels on every
        # adapter, which is THREE cells of the system 8x8 and FOUR at 6x6, and
        # the cell's height holds four rows where it held two. Three is the
        # ask (HP, both stats) and four is HP, both and POWER.
        check(rw("ti_nrows") >= 3, "a cell states at least HP and both stats",
              "%d rows" % rw("ti_nrows"))

        # ...AND WHERE POWER DOES NOT FIT, THE POINTER CARRIES IT. Power is
        # what a player wants while planning a KILL, and a kill is of something
        # on the BOARD - so unlike a cost it cannot fall back to the card. On
        # CGA the cell is a row short and the status line leads with it.
        mo.to(x0 // 2, y0 + 2 * rw("ti_cardpitch"))
        os88marty.guest_sleep(m, 2.0)
        cell = rw("ti_hovc")
        if cell != 0xFFFF:
            card = cell % HAND
            # `NAME  <soul>PP  ABILITY` - the board's line NAMES the
            # character, because a figure at 64 pixels cannot and will not,
            # and it carries the POWER on every adapter: a cost falls back to
            # the card and power has nowhere to fall back to (97.4.8.1).
            want_s = "%s  \x03%02d  %s" % (NAMES[card], POWER[card],
                                           ABILITIES[card])
            want = os88titheface.render(face[1], face[2], want_s)
            f = mono(m)[2]
            y = rw("ti_oy") + (rw("ti_hud") - rw("ti_fh")) // 2
            got = [f[y + r][rw("ti_hx") + rw("ti_hnx"):
                            rw("ti_hx") + rw("ti_hnx") + len(want[0])]
                   for r in range(rw("ti_fh"))]
            bad = sum(1 for a, b in zip(want, got)
                      for p_, q in zip(a, b) if bool(p_) != bool(q))
            check(bad == 0,
                  "a hovered board character is NAMED, and says what it pays"
                  " and what it does",
                  "cell %d, %d pixel(s) differ from the host's render"
                  % (cell, bad))
        else:
            check(False, "the pointer reached a board cell at all", "none")

        mo.to(x0 // 2, mid)
        os88marty.guest_sleep(m, 2.5)
        h2 = hud(mono(m)[2])
        back = sum(1 for a, b in zip(h0, h2) for q, r_ in zip(a, b) if q != r_)
        check(back == 0, "...and the strip comes back whole",
              "%d pixel(s) of the last line left behind" % back)


def main():
    off = offsets()
    for mach in MACHINES:
        run(mach, off)
    print("tithecard: %d check(s) FAILED" % len(fails) if fails else "tithecard: ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
