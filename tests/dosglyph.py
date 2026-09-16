#!/usr/bin/env python3
"""A SHIPPED document glyph reaches every path the kernel fills a slot's
glyph by, and the glass (SPEC.md 54.3.2).

    make && python3 tests/dosglyph.py [machine]

tests/unit/t_docglyph.py is the host half: the validator, the baker and the
disk builder. This is the kernel's, and the kernel writes a slot's glyph in
four places - the BAKED table it boots with, the cache SEED at a volume
switch (asc_seed), a cache HIT at a mount (asc_note) and a cache MISS's
harvest (assoc_note_app) - each of which used to REDUCE the 16x16 icon and
now prefers the block the package ships. DOS is the package, its icon a CRT
the reduction empties, so what is asserted is that DOS's slot holds the
SHIPPED bytes, and never the reduction, after each of the four:

  1. BAKED: after a cold boot, before any full mount, the slot holds them
     (tools/os88mini.py baked the shipped block into the kernel).
  2. THE GLASS: a Disk window on a floppy with a .COM at its root draws the
     composed document icon - the page with the shipped glyph inset - and it
     is found in the window's own pixels (assoc_compose is unchanged; this
     says the whole chain reaches the screen).
  3. SEED: the slot is POISONED with the reduction, Drive A is opened (a
     volume switch, so ASSOC.DAT is loaded and asc_seed runs), and the slot
     holds the shipped bytes again.
  4. HIT: poisoned again, A:\\APPS is opened (DOS.O88's row is in the cache,
     so the harvest takes asc_note), and the slot holds them again.
  5. MISS: poisoned again, the cache's DOS row is broken in memory (its size
     word, which is half the lookup key), APPS/ is left and re-entered, so
     the harvest READS the sector and takes assoc_img_glyph off it - and the
     slot holds them again.

The fifth writer, a runtime OSAPI_ASSOC_SET claim (assoc_self_glyph), is not
driven here: DOS makes none, and it goes through the same assoc_img_glyph as
step 5 with the package's own segment for the sector.

Each poison is checked to have TAKEN before the path under test runs, so a
pass says the path wrote the slot and not that nothing touched it. The
poison is the reduction rather than zeros because zero is the UNRESOLVED
sentinel and a writer that skips blanks would leave zeros alone by design.

The 1bpp pixel half runs on CGA and Hercules; on VGA it says so and asserts
the bytes alone (tests/assocglyph.py's reason).
"""
import os
import sys

sys.path.insert(0, "tools")
sys.path.insert(0, "tests")
import os88build                                              # noqa: E402
import os88marty                                              # noqa: E402
import os88mouse                                              # noqa: E402
import os88sym                                                # noqa: E402
import os88mini                                               # noqa: E402
import dispcp                                                 # noqa: E402

MACHINE = sys.argv[1] if len(sys.argv) > 1 else "os8088_5150_cga_gla"
SYS_IMG = "build/os8088-360.img"
DOC_IMG = "build/doscom360.img"          # DOSHELLO.COM at the root
S = os88sym.linear
NAPP = 12                                # ASSOC_NAPP
PARK = (320, 190)
PIX1BPP = ("cga", "mda")
fails = []

# The page frame assoc_compose lays down (SPEC.md 54.3), data plane, and the
# inset: glyph row i lands in data row 5 + i, shifted left by 4.
PAGE = [0x3FE0, 0x2030, 0x2028, 0x203C] + [0x2004] * 11 + [0x3FFC]


def say(s):
    print("  " + s)


def shipped_and_reduced():
    """DOS's shipped glyph and what the reduction would have made of it."""
    with open(os88build.at("build/dos.o88"), "rb") as f:
        d = f.read()
    if not d[3] & 0x20:
        sys.exit("dosglyph: build/dos.o88 does not set flags bit 5 - this "
                 "test is about a package that SHIPS a glyph")
    rows = [int.from_bytes(d[64 + 2 * y:66 + 2 * y], "little")
            for y in range(16)]
    return bytes(d[112:120]), bytes(os88mini.reduce8(rows))


def slots(m):
    """{stem: (index, 8-byte glyph)} for every live app slot."""
    stem = m.read(S("assoc_stem"), NAPP * 8)
    glyph = m.read(S("assoc_glyph"), NAPP * 8)
    out = {}
    for i in range(NAPP):
        s = bytes(stem[i * 8:(i + 1) * 8])
        if s[0]:
            out[s.decode("latin1").rstrip()] = (i, bytes(glyph[i * 8:(i + 1) * 8]))
    return out


def dos_glyph(m):
    sl = slots(m)
    if "DOS" not in sl:
        sys.exit("dosglyph: no DOS slot in assoc_stem - SPEC.md 96 makes it a "
                 "built-in row, so this kernel is not the one described")
    return sl["DOS"]


def poison(m, idx, what):
    m.write(S("assoc_glyph") + idx * 8, what)
    got = dos_glyph(m)[1]
    if got != what:
        sys.exit("dosglyph: the poison did not take (%s against %s) - the "
                 "write went somewhere else" % (got.hex(), what.hex()))


def expect(m, step, shipped):
    got = dos_glyph(m)[1]
    ok = got == shipped
    say("%s: DOS's slot = %s%s" % (step, got.hex(),
                                   "" if ok else " (WANT %s)" % shipped.hex()))
    if not ok:
        fails.append("%s: the slot holds %s, not the shipped %s"
                     % (step, got.hex(), shipped.hex()))


def find_icon(m, mo, rect, glyph):
    """Search the window's pixels for the composed document icon."""
    mo.to(*PARK)
    os88marty.settle(m)
    w, h, rows = m.vram()
    x0, y0, rw, rh = rect
    data = list(PAGE)
    for i, b in enumerate(glyph):
        data[5 + i] |= b << 4
    want = [[(data[yy] >> (15 - xx)) & 1 for xx in range(16)]
            for yy in range(16)]
    hits = {0: [], 1: []}
    for y in range(y0, min(y0 + rh, h) - 16):
        for x in range(x0, min(x0 + rw, w) - 16):
            for pol in (0, 1):
                good = True
                for yy in range(16):
                    r = rows[y + yy]
                    for xx in range(16):
                        px = 1 if r[x + xx] else 0
                        if (px ^ pol) != want[yy][xx]:
                            good = False
                            break
                    if not good:
                        break
                if good:
                    hits[pol].append((x, y))
    return hits


def break_cache_row(m):
    """Spoil the cache's DOS row in memory so the next lookup MISSES."""
    seg = int.from_bytes(m.read(S("asc_seg"), 2), "little")
    n = int.from_bytes(m.read(S("asc_n"), 2), "little")
    rowsz = int.from_bytes(m.read(S("asc_rowsz"), 2), "little")
    say("cache at %04X, %d rows of %d bytes" % (seg, n, rowsz))
    if rowsz != 88:
        fails.append("the loaded cache's row stride is %d, not 88 - the "
                     "system disk's ASSOC.DAT is not version 2" % rowsz)
    if not seg or not n:
        sys.exit("dosglyph: no cache is loaded, so a miss cannot be staged")
    for i in range(n):
        row = seg * 16 + 16 + i * rowsz
        if bytes(m.read(row, 8)) == b"DOS     ":
            m.write(row + 8, b"\xFF\xFF")
            say("row %d is DOS: its size word is now 0xFFFF" % i)
            return
    sys.exit("dosglyph: the cache has no DOS row - the system disk's "
             "ASSOC.DAT was built without APPS/DOS.O88")


shipped, reduced = shipped_and_reduced()
say("shipped %s, the reduction would be %s" % (shipped.hex(), reduced.hex()))
if shipped == reduced:
    sys.exit("dosglyph: the shipped glyph IS the reduction, so nothing here "
             "can tell the two apart")

with os88marty.launch(SYS_IMG, apps=DOC_IMG, machine=MACHINE) as m:
    mo = os88mouse.Mouse(marty=m)
    card = m.cmd(cmd="video")["type"]

    # --- 1. baked -----------------------------------------------------------
    idx, _ = dos_glyph(m)
    expect(m, "1 baked", shipped)

    # --- 2. the glass -------------------------------------------------------
    dispcp.open_drive(m, mo, S, os88marty.settle, "B")
    names = [n for n, _ in dispcp.listing(m, S)]
    say("B:\\ = %r" % names)
    if "DOSHELLO.COM" not in names:
        sys.exit("dosglyph: %s has no DOSHELLO.COM at its root" % DOC_IMG)
    rect = dispcp.win_rect(m, S, dispcp.win_list(m, S)[-1])
    if card in PIX1BPP:
        hits = find_icon(m, mo, rect, shipped)
        n = len(hits[0]) + len(hits[1])
        say("2 glass: the composed icon found %d time(s) in the window %r"
            % (n, tuple(rect)))
        if n < 1:
            fails.append("the page-with-shipped-glyph icon is not in the "
                         "Disk window's pixels")
        bad = find_icon(m, mo, rect, reduced)
        if bad[0] or bad[1]:
            fails.append("the page-with-REDUCTION icon IS in the window")
    else:
        say("2 glass: card is %r, no 1bpp framebuffer - bytes only" % card)

    # --- 3. the seed, on a volume switch ------------------------------------
    poison(m, idx, reduced)
    dispcp.open_drive(m, mo, S, os88marty.settle, "A")
    expect(m, "3 seed (asc_seed, Drive A opened)", shipped)
    wx, wy = dispcp.win_rect(m, S, dispcp.win_list(m, S)[-1])[:2]

    # --- 4. a hit, at a mount -----------------------------------------------
    poison(m, idx, reduced)
    dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "APPS")
    names = [n for n, _ in dispcp.listing(m, S)]
    if "DOS.O88" not in names:
        sys.exit("dosglyph: A:\\APPS has no DOS.O88: %r" % names)
    expect(m, "4 hit (asc_note, APPS/ entered)", shipped)

    # --- 5. a miss, and the harvest reads the sector ------------------------
    poison(m, idx, reduced)
    break_cache_row(m)
    dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "..")
    dispcp.open_named(m, mo, S, os88marty.settle, wx, wy, "APPS")
    expect(m, "5 miss (assoc_img_glyph off the sector)", shipped)

if fails:
    print("dosglyph: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("dosglyph: ok - the shipped glyph survives the baked table, the seed, "
      "a hit and a miss, and is on the glass")
