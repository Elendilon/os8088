#!/usr/bin/env python3
"""ArtfulType's band emit (SPEC.md 46.4.2) - the A/B that says it drew the
SAME PICTURE and did far less work to draw it.

    make && python3 tests/atblit.py              # CGA
    python3 tests/atblit.py --card herc
    python3 tests/atblit.py --card vga --census

WHAT IS UNDER TEST. `at_draw_line` used to widen `at_compose`'s 1bpp strip to
packed 4bpp (`at_expand`) purely so `OSAPI_GFX_BLIT4` could pack it straight
back down, on every adapter and every line. 46.4.2 composes the strip in
SCREEN polarity instead and hands it to `OSAPI_GFX_BLIT1`, which is a
`rep movsw` a row. `NOATBLIT1=1` is the arm before that, and it assembles BYTE
FOR BYTE IDENTICAL to the package that shipped - so the two trees differ in
this and in nothing else, which is what makes the comparison below mean
anything.

THE ASSERTION IS THE PICTURE, and it has to be, because every failure mode of
a polarity flip is a plausible-looking wrong image rather than a crash. Miss
one of the FIVE writers into `at_strip1` and that one element renders
inverted - and the fifth is `at_bigtext` in another file, which is exactly the
one an audit of `atrend.inc` misses. Complement above the italic `rcr` chain
and every italic grows a bar down its left edge. Forget `AT_X4TAB` and the
surviving 4bpp fallback draws the negative, which no kern_big row would ever
execute. None of those raise anything anywhere.

So the gate is `0 differing pixels` between the arms over a document that
exercises all six styles and a heading, and it FAILS LOUD on exactly the
mistakes the change invites. Break it on purpose to see it work: flip one of
`AT_PAPERAX`/`AT_MERGE`/`AT_RULE` in artful.asm and this goes red.

THE CENSUS is the second half, and it is what says the win is real rather than
that the picture merely survived: `gfx_blit4` must fall to ZERO on the lines
the band arm takes, and `gfx_blit1` must rise to one per line.

The band arm is reached by a DIFFERENT gate per adapter, which is why this
runs on three: 1bpp takes it outright (`at_codebg` has already cleared
`at_cellbg`, so no grey column survives), and a colour adapter takes it only
for a line with no code span. The `code` line below is therefore the one line
that must still go through the expander on VGA and must not on CGA or
Hercules - so on VGA the census floor for `gfx_blit4` is not zero.
"""
import sys, os, argparse
sys.path.insert(0, "/home/user/os8088/tools")
sys.path.insert(0, "/home/user/os8088/tests")
import os88fixture                                       # noqa: E402
ROOT = "/home/user/os8088"


def u16(b, i=0):
    return b[i] | (b[i + 1] << 8)
import os88marty, os88ui, os88build, os88sym, os88geom   # noqa: E402
import os, subprocess, tempfile                          # noqa: E402

# Every style ArtfulType can draw, so a missed writer has somewhere to show.
DOC = ["# Heading one",
       "Plain body text for the ordinary path.",
       "This is **bold** and *italic* and ~~struck~~.",
       "A `code` span is the three-colour line.",
       "A [link](http://os8088.com) underlines it."]

CARDS = {"cga":  "os8088_5150_cga_gla",
         "herc": "os8088_5150_herc_gla",
         "vga":  "os8088_xt_vga"}

COUNTED = ("gfx_blit4", "gfx_blit1")


def pkg_syms(defines=()):
    """ArtfulType's bss offsets, by re-assembling it - editmove.py's trick.

    They are `equ os88_image_end + N` behind macros, so they are neither
    greppable nor stable against an edit, and a wrong one reads a plausible
    word out of the middle of another variable. The DEFINES travel with it:
    NOATBLIT1 changes the image size, so the same name is at a different
    offset in the two arms and resolving both from one assembly would read
    the knob arm's caret out of the middle of its strip.
    """
    with tempfile.TemporaryDirectory() as d:
        cp, mp = os.path.join(d, "p.asm"), os.path.join(d, "p.map")
        open(cp, "w").write(open(ROOT + "/apps/artful/artful.asm").read()
                            + "\n[map symbols %s]\n" % mp)
        subprocess.run(["nasm", "-f", "bin", "-w+error"] + list(defines)
                       + ["-I", ROOT + "/apps/", "-I", ROOT + "/apps/artful/",
                          "-o", os.path.join(d, "p.bin"), cp], check=True)
        out = {}
        for line in open(mp):
            f = line.split()
            if len(f) == 3 and all(c in "0123456789ABCDEF" for c in f[0]):
                out[f[2]] = int(f[0], 16)
        return out


def drive(img, apps, machine, tree, census, shot=None):
    """Boot one tree, type DOC into a fullscreen ArtfulType, return the glass.

    Returns (w, h, splash rgb24, document rgb24, {symbol: entries}).

    TWO SCENES, because they exercise DIFFERENT writers into at_strip1. The
    fullscreen document is at_compose + at_glyph + at_ruleat; the windowed
    splash card is at_bigtext (the fifth writer, in this other file) and
    at_drawimg (the artwork, which is the one source of pixels nothing
    composes). Breaking at_bigtext on purpose with only the document scene
    captured left this row GREEN - which is why both are here.

    at_drawimg is skipped when at_vh < 300, so the artwork is covered by the
    herc and vga arms and not by cga.
    """
    tree.apply()                       # os88sym resolves against THIS kernel
    # THE DEFINE COMES OFF THE TREE'S MAKE ARGS, NOT ITS `defines`.
    # os88build's `defines` describes the KERNEL, and NOATBLIT1 reaches no
    # kernel byte (it is in the Makefile's KERN_KNOB exemption beside
    # NOHEDGE), so it is not in that list - the knob tree reports
    # `defines: KERN_BIG` exactly like the shipped one. Resolving the knob
    # arm's symbols without it read at_caret at the shipped arm's offset,
    # which is 58 bytes along and inside another variable: the wait then sat
    # out its whole guest budget waiting for a number that could not arrive.
    syms = pkg_syms(["-D" + a.split("=")[0] for a in tree.args
                     if a.startswith("NOAT")])
    counts = {}
    with os88ui.boot(img, apps=apps, machine=machine) as ui:
        m = ui.m
        w = ui.path("B:/APPS/ARTFUL.O88")          # the splash card
        seg = u16(m.read(os88geom.winptr(m, w.i, ui.sym) +
                    os88geom.W_SEG, 2))
        ui.settle()
        sw, sh, splash = m.fbuf()                  # SCENE 1: the splash card
        if shot:
            os88marty.write_png_rgb(shot.replace(".png", "-splash.png"),
                                    sw, sh, splash)
        m.key("KeyN")                              # New -> fullscreen (46.5)
        # FREEZE THE BLINK BEFORE THE FIRST SETTLE. at_worker toggles an XOR
        # caret every 9 ticks, so a fullscreen ArtfulType NEVER stops
        # changing and `settle` spends its whole guest budget and raises. It
        # would also land in the capture as a difference between two arms
        # that merely sampled different phases. [at_drag] is at_worker's own
        # .gate (artful.asm:636) and nothing else reads it, so setting it is
        # exactly "no blink" and touches no drawing state.
        m.write(seg * 16 + syms["at_drag"], b"\x01")
        m.write(seg * 16 + syms["at_cphase"], b"\x00")
        ui.settle()
        caret = syms["at_caret"]

        def absorbed(n):
            """Wait until the APP says it has taken n characters.

            THIS IS THE WHOLE REASON THE ROW IS HONEST. type_text fires keys
            as fast as the debug server accepts them, and one ArtfulType
            keystroke is 50-190 ms of 4.77 MHz work, so the kernel's key queue
            overflows and `kbd_ovflow` drops what will not fit. The first run
            of this gate typed the document into BOTH arms and got two
            DIFFERENT garbled documents - the slow arm dropped more - and
            reported 4,214 differing pixels, which reads exactly like a
            rendering bug and is not one. Pacing on the app's own caret makes
            the two arms receive the same text by construction; it is also
            the only way this row could ever have compared anything.
            """
            os88marty.until(
                m, lambda _: u16(m.readseg(seg, caret, 2)) == n,
                "ArtfulType to absorb %d characters" % n, poll=0.05, limit=90.0)

        n = 0

        def typedoc():
            nonlocal n
            for i, line in enumerate(DOC):
                if i:
                    m.key("Enter")
                    n += 1
                    absorbed(n)
                for ch in line:
                    m.type_text(ch)
                    n += 1
                    absorbed(n)
            return n

        if census:
            for sym in COUNTED:
                counts[sym] = os88marty.bp_count(m, sym, typedoc)
                m.bp_exec()
                m.run()
        else:
            typedoc()
        ui.settle()
        w, h, rgb = m.fbuf()                       # SCENE 2: the document

        # --- SCENE 3: a document TALLER THAN THE VIEW, scrolled -------------
        # at_scroll_to is the only path 46.4.4 changes and neither scene above
        # reaches it: five short lines never overflow even CGA's 16-line
        # region. Enter is the cheap way to get there - one keystroke a line
        # against ~64 characters of filler - and PageUp then forces the
        # UPWARD arm, which is the one whose dy at_sumn negates.
        for _ in range(22):
            m.key("Enter")
            n += 1
            absorbed(n)
            m.type_text("x")
            n += 1
            absorbed(n)
        ui.settle()
        m.key("PageUp")
        ui.settle()
        m.key("PageDown")
        ui.settle()
        w3, h3, scrolled = m.fbuf()
        if shot:
            os88marty.write_png_rgb(shot.replace(".png", "-scroll.png"),
                                    w3, h3, scrolled)
        if shot:
            os88marty.write_png_rgb(shot, w, h, rgb)
    return w, h, splash, rgb, scrolled, counts


def diff(a, b, w, h):
    """Differing pixels, and their bounding box.

    The WHOLE screen is compared and that is safe here where it is not in
    tests/blitplane.py: ArtfulType is FULLSCREEN, so the menu bar with its
    running clock is ArtfulType's own and carries no time, and os88ui.boot
    parks the pointer and turns the saver off. If this ever starts reporting a
    handful of pixels in one corner, that assumption is what broke.
    """
    n, box = 0, None
    for row in range(h):
        base = row * w * 3
        if a[base:base + w * 3] == b[base:base + w * 3]:
            continue
        for col in range(w):
            i = base + col * 3
            if a[i:i+3] != b[i:i+3]:
                n += 1
                box = ((min(box[0], col), min(box[1], row),
                        max(box[2], col), max(box[3], row))
                       if box else (col, row, col, row))
    return n, box


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", default="cga", choices=sorted(CARDS))
    ap.add_argument("--knob", default="NOATBLIT1",
                    help="which ArtfulType A/B to run: the shipped package "
                         "against this knob's arm. NOATBLIT1 is 46.4.2's "
                         "band emit, NOATFAST is 46.4.3's scale-1 composer. "
                         "Every one of them must draw the IDENTICAL picture, "
                         "so this row generalises rather than being copied "
                         "per wave.")
    ap.add_argument("--census", action="store_true",
                    help="COUNT the two blits INSTEAD of comparing pixels. "
                         "The two are not additive: bp_count stops the guest "
                         "at every hit and the caret pacing needs the guest "
                         "RUNNING to make progress, so together they type a "
                         "different document into each arm and the compare "
                         "is meaningless - it reported 3,506 differing "
                         "pixels the one time they were run together. Pixels "
                         "are the gate; this is the reading you take by hand.")
    a = ap.parse_args()
    machine = CARDS[a.card]

    shipped = os88build.plain()
    knob = os88build.tree(a.knob + "=1")
    print("   shipped arm: %s" % os.path.relpath(shipped.dir, ROOT))
    print("   %s arm: %s" % (a.knob, os.path.relpath(knob.dir, ROOT)))

    os.makedirs("/tmp/atblit", exist_ok=True)
    w, h, bsp, band, bsc, cb = drive(shipped.img("os8088-360.img"),
                                shipped.img("apps360.img"), machine, shipped,
                                a.census, "/tmp/atblit/%s-shipped-%s.png" % (a.knob, a.card))
    w2, h2, esp, expa, esc, ce = drive(knob.img("os8088-360.img"),
                                  knob.img("apps360.img"), machine, knob,
                                  a.census,
                                  "/tmp/atblit/%s-knob-%s.png" % (a.knob, a.card))

    if (w, h) != (w2, h2):
        print("FAIL: the two arms rasterised %dx%d against %dx%d"
              % (w, h, w2, h2))
        return 1

    if a.census:
        print("\n   %s, per document (%d lines):" % (a.card, len(DOC)))
        for sy in COUNTED:
            print("      %-10s band=%-6s expand=%s" % (sy, cb.get(sy),
                                                      ce.get(sy)))
        print("   (pixels NOT compared - see --census's help)")
        return 0

    bad = 0
    for scene, x, y in (("splash", bsp, esp), ("document", band, expa),
                        ("scrolled", bsc, esc)):
        n, box = diff(x, y, w, h)
        print("   %s/%s %-9s %d differing pixels of %d%s"
              % (a.knob, a.card, scene, n, w * h,
                 "" if not box else "  box %r" % (box,)))
        bad += n
    n = bad
    if n:
        print("   per-row (row: differing px):")
        for row in range(h):
            base = row * w * 3
            if band[base:base + w*3] == expa[base:base + w*3]:
                continue
            c = sum(1 for col in range(w)
                    if band[base+col*3:base+col*3+3]
                    != expa[base+col*3:base+col*3+3])
            print("      y=%-4d %d" % (row, c))
        print("   captures in /tmp/atblit/")
        print("FAIL: the shipped arm and %s drew different pictures" % a.knob)
        return 1
    print("ok: %s draws the identical picture on %s" % (a.knob, a.card))
    return 0


if __name__ == "__main__":
    sys.exit(main())
