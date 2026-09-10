#!/usr/bin/env python3
"""A GROW is not refused over a cache, and "Too big" is not said about memory.

    make small && python3 tests/regrowshed.py [machine]

SPEC.md 50.6.2.1 and 27.6.1, on the 128KB floor machine, through the one path
that put both defects on the glass at once: **Note Pad opening the manual.**

The field report was *"kern_small says Too big opening README.TXT"*, and the
arithmetic said it should work - Note Pad's small region is 13,475 bytes, the
manual is 14,722, and the machine has 52.5KB of heap. Two things were wrong
and each hid the other:

  `mem_regrow` had no SHED.  `mem_claim` has had shed-and-retry since
                             SPEC.md 50.6.2 and this routine never did, so a
                             grow was refused over three purgeable caches
                             holding 31,744 bytes - memory the kernel keeps
                             on the explicit understanding that it can give
                             it away.
  `np_load` said the wrong    The claim stayed at NP_KB0, the read compared
  thing about it.             14,722 against 1,024, and the file API answered
                              the only thing it can: FERR_BIG. So a MEMORY
                              refusal reached the user as a sentence about
                              the FILE, and the field went looking for a size
                              limit that was not the cause.

Four verdicts, and the third is the positive control WRITING-TESTS 1 asks
for - a Note Pad that never said "Too big" at all would pass the other three:

  loaded    README.TXT opens with the claim at NP_MAXKB and np_len at 14,427,
            the CRLF file FOLDED. This is the shed: measured on the machine,
            the claim starts at 1KB under a 6,144-byte raise cache with
            2,560 bytes of run free, and three sheds - cheapest first - are
            what open the 16KB it needs
  intact    ...and a REFUSED load leaves the note alone (SPEC.md 27.6), which
            is checked on the way through the next leg rather than costing
            one of its own
  toobig    PAINT.O88 is 21,285 bytes and is genuinely too big for this
            application, so it must still say so - with the claim AT the
            ceiling, which is the fact that makes the sentence true
  nomem     ...and a SECOND Note Pad cannot fund a second 16KB document on a
            128KB machine, so its load is refused for real - and the toast
            must be "No memory" and never "Too big"

The toast is read out of `toast_buf` and not off the glass: it expires on a
tick count (SPEC.md 59), so a settle long enough to be sure a load finished
is long enough to lose it.

**How to make it go red** (WRITING-TESTS 1): take the `call mem_shed_one` out
of `mem_regrow.shed` and `loaded` fails with np_len 0; take np_load's
`cmp word [np_capkb], NP_MAXKB` out and `nomem` fails reading "Too big".
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
# kern_small, and set BEFORE the imports: os88sym checks the map against the
# binary the moment it is asked.
os.environ.setdefault("OS88_DEFINES", "KERN_SMALL")
import os88build                                            # noqa: E402
os88build.use_build("build/smallk")
import os88marty as M                                       # noqa: E402
import os88geom                                             # noqa: E402
import os88sym                                              # noqa: E402
import os88ui                                               # noqa: E402
import dispcp                                               # noqa: E402
import dispapps                                             # noqa: E402

ARM = ("KERN_SMALL",)
MACHINE = sys.argv[1] if len(sys.argv) > 1 else "os8088_5150_cga_128k"

# THE MANUAL'S FOLDED LENGTH, derived and not carried: the file ships with
# CRLF and np_load folds each pair to one 13, so what the note holds is the
# repository copy's own byte count. Deriving it means an edit to readme.txt
# never makes this row red.
README = os.path.join(os.path.dirname(__file__), "..", "readme.txt")
WANT_LEN = len(open(README, "rb").read().replace(b"\r\n", b"\n"))

fails = []


def check(name, cond, note=""):
    print("  [%s] %-8s %s" % ("PASS" if cond else "FAIL", name, note))
    if not cond:
        fails.append(name)


def u16(b, i=0):
    return b[i] | (b[i + 1] << 8)


# A PRIVATE TREE (WRITING-TESTS 5.2): `make small` writes build/*.drv beside
# build/smallk/, so out of tree is what lets this row run beside anything
# else. `small` is the only target it needs - the small SYSTEM disk carries
# README.TXT in its root AND the APP_SMALL Note Pad in APPS/ (§24.3), so
# there is no B: floppy in this scenario at all.
_T = os88build.tree(targets=("small",))

# ...AND BOTH READERS FOLLOW IT, which takes `apply()` AND an override.
#
# `apply()` is what makes `os88build.at` resolve `build/...` into this tree -
# and dispapps.sym needs that, because its staleness guard compares the
# APP_SMALL package against `build/smallapp/notepad.o88`. Without it the
# offsets come from the shared directory while the GUEST runs the tree's copy,
# which agree only while `build/` happens to be current: the guard then fails
# saying "build/ is BEHIND THE TREE" about a tree that is fine.
#
# But `apply()` alone points the KERNEL reader wrong, which is
# tests/small128.py's note: `defines_for` asks how the tree's DEFAULT kernel
# target is compiled and answers KERN_BIG even for a tree built for `small`.
# So name the tree's own smallk/ afterwards and put KERN_SMALL back.
_T.apply()
os.environ["OS88_BUILD"] = os.path.join(_T.dir, "smallk")
os.environ["OS88_DEFINES"] = "KERN_SMALL"
os88sym.default_defines(*ARM)

# THE SMALL BUILD'S OWN LAYOUT (dispapps.sym's note): the disk carries the
# APP_SMALL Note Pad, whose np_* offsets are not the shipped build's.
NP = dict((k, dispapps.sym("notepad", k, small=True))
          for k in ("np_len", "np_cap", "np_capkb", "np_dseg"))

with os88ui.boot(_T.img("small360.img"), machine=MACHINE, limit=180) as ui:
    m = ui.m
    S = lambda n: m.sym(n, ARM)                             # noqa: E731
    eq = os88sym.equates(ARM)
    ram = u16(m.read(0x413, 2)) * 1024
    HEAP, top = eq["HEAP_SEG"], u16(m.read(S("mem_top"), 2))
    print("== %s : %d bytes RAM, heap %.1f KB, the manual folds to %d =="
          % (MACHINE, ram, (top - HEAP) * 16 / 1024.0, WANT_LEN))

    def heap(label):
        """The map, and the largest FREE RUN - which is the quantity the whole
        row is about: `mem_regrow` wants one run the whole new size."""
        sz = os88geom.MC_SIZE
        tab = m.read(S("mem_tab"), eq["MEM_MAX"] * sz)
        rows = []
        for i in range(eq["MEM_MAX"]):
            r = tab[i * sz:(i + 1) * sz]
            seg = u16(r, os88geom.MC_SEG)
            if seg:
                rows.append((seg, u16(r, os88geom.MC_PARA),
                             u16(r, os88geom.MC_OWN)))
        rows.sort()
        cur, free, run = HEAP, 0, 0
        purge = 0
        for seg, para, own in rows:
            if seg > cur:
                free += (seg - cur) * 16
                run = max(run, (seg - cur) * 16)
            if eq["MEM_PG_MIN"] <= (own >> 8) <= eq["MEM_PG_MAX"]:
                purge += para * 16
            cur = max(cur, seg + para)
        if top > cur:
            free += (top - cur) * 16
            run = max(run, (top - cur) * 16)
        print("    %-26s free %6d  largest run %6d  in caches %6d"
              % (label, free, run, purge))
        return run, purge

    def npseg(win):
        rec = m.read(S("wm_wins") + win.i * os88geom.WIN_SIZE,
                     os88geom.WIN_SIZE)
        return u16(rec, os88geom.W_SEG)

    def npstate(win):
        p = npseg(win)
        return dict((k, u16(m.readseg(p, NP[k], 2)))
                    for k in ("np_len", "np_cap", "np_capkb", "np_dseg"))

    def dlg():
        """The dialog is the newest visible window titled Open or Save As.
        BY TITLE STRING: on kern_small fdlg.inc's data lives inside the
        FDLG.DRV image, so `fdlg_s_topen` is not a KERNEL_SEG offset and the
        usual W_TITLE compare answers None for a dialog that is up."""
        return next((x for x in reversed(
            [w for w in os88geom.windows(m, S) if w.visible])
            if x.title in ("Open", "Save As")), None)

    def open_file(win, path, tag):
        """File > Open in `win`, then walk to `path` and pick it.

        `path` is folder-relative to the VOLUME ROOT ("README.TXT",
        "APPS/PAINT.O88"), and the walk starts by going UP until there is no
        `..` row - which it has to, because SPEC.md 38.10 opens the dialog on
        whatever folder this instance last chose. After leg 1 that is the
        root and before it the launch folder, so a row that assumed either
        would pick the wrong file on one of the two.

        KEYBOARD, not a click: fdlg_onkey's .move and .enter ARE the dialog's
        own navigation (arrows select, Enter acts), so no listing geometry is
        needed and nothing can land on the wrong row. The rows come off the
        GLOBAL mount snapshot, which is what the dialog itself lists
        (dispcp.snapshot) and NOT the acting Disk window's cache.
        """
        ui.raise_window(win)
        ui.menu_pick("File", "Open")
        M.settle(m, limit=120)
        if dlg() is None:
            sys.exit("%s: File > Open put no dialog up" % tag)

        def rows():
            return [r[0] for r in dispcp.snapshot(m, S)]

        def down(n=1):
            for _ in range(n):
                m.key("ArrowDown")
                time.sleep(0.2)

        def pick(name):
            """Select `name` and press Enter - a dive for a folder, the
            command for a file. Asserts the SELECTION before committing, so a
            miss is reported here rather than as the feature under test."""
            rs = rows()
            if name not in rs:
                sys.exit("%s: %s is not listed here - %r" % (tag, name, rs))
            idx = rs.index(name)
            down(idx + 1)               # the selection starts at "none", so
                                        # the first key lands on row 0
            got = u16(m.read(S("fdlg_sel"), 2))
            if got != idx:
                sys.exit("%s: the dialog selected row %d, wanted %d (%s)"
                         % (tag, got, idx, name))
            m.key("Enter")
            M.settle(m, limit=180)

        while rows()[:1] == [".."]:     # up to the volume root
            down()
            m.key("Enter")
            M.settle(m, limit=120)
        for part in path.split("/"):
            pick(part)
        return m.read(S("toast_buf"), 26).split(b"\0")[0].decode(
            "latin-1", "replace")

    # --- the caches have to EXIST, so open a Disk window before anything ----
    # A bare desktop holds no claims at all (tests/small128.py asserts it), so
    # a Note Pad launched from nowhere would find the heap empty and grow with
    # no shed to make. Navigating A: is what claims MEM_P_VIEW and the
    # directory read-ahead, and it is also how a person gets to Note Pad.
    first = ui.path("A:/APPS/NOTEPAD.O88")
    run, purge = heap("one Note Pad, caches warm")
    st = npstate(first)
    print("    claim starts at %d bytes (np_capkb=%d)"
          % (st["np_cap"], st["np_capkb"]))

    # 1. THE SHED. The claim needs 16,384 and the largest run is smaller
    #    than that with tens of KB sitting in caches - which is the whole
    #    defect, so the row says so rather than leaving it implied.
    print("  -- README.TXT, %d bytes into a %d-byte claim --"
          % (WANT_LEN, st["np_cap"]))
    t = open_file(first, "README.TXT", "loaded")
    st = npstate(first)
    check("loaded", st["np_len"] == WANT_LEN and st["np_capkb"] == 16,
          "(np_len=%d want %d, np_capkb=%d, toast %r; the run was %d with "
          "%d in caches)"
          % (st["np_len"], WANT_LEN, st["np_capkb"], t, run, purge))
    if run >= 16 * 1024:
        print("    NOTE: a 16KB run was already free, so this leg did NOT "
              "exercise the shed - the heap has moved and the row wants "
              "re-deriving (SPEC.md 50.6.2.1)")

    # 2. THE POSITIVE CONTROL. PAINT.O88 is 21,285 bytes and there is no
    #    claim this application may grow to that holds it, so "Too big" is
    #    the true sentence - and np_capkb AT the ceiling is what makes it
    #    true. Without this leg a Note Pad that had simply stopped saying
    #    "Too big" would pass every other one.
    heap("...the manual loaded")
    t = open_file(first, "APPS/PAINT.O88", "toobig")
    st = npstate(first)
    check("toobig", t == "Too big" and st["np_capkb"] == 16,
          "(toast %r, np_capkb=%d - a 21,285-byte file against a "
          "16,384-byte ceiling)" % (t, st["np_capkb"]))
    # ...and SPEC.md 27.6's other promise, for free: a refused load leaves
    # the note exactly as it was.
    check("intact", st["np_len"] == WANT_LEN,
          "(np_len=%d after the refusal, want %d unchanged)"
          % (st["np_len"], WANT_LEN))

    # 3. A REAL refusal, and what it is allowed to say. Two Note Pads cannot
    #    fund two 16KB documents on a 128KB machine: the first instance is
    #    holding ~15KB for the manual it loaded, so the second's grow is
    #    refused with every cache already shed.
    second = ui.path("A:/APPS/NOTEPAD.O88")
    run, purge = heap("a SECOND Note Pad")
    t = open_file(second, "README.TXT", "nomem")
    st = npstate(second)
    if st["np_capkb"] >= 16:
        check("nomem", t != "Too big",
              "(the claim reached the ceiling after all, so this machine "
              "COULD fund it - toast %r; the leg asserted only that the "
              "sentence is not about the file)" % t)
        print("    NOTE: the second instance was funded, so the refusal "
              "this leg is about did not happen - largest run %d" % run)
    else:
        check("nomem", t == "No memory",
              "(toast %r with np_capkb=%d short of %d - a refused CLAIM must "
              "not be reported as a file that is too big, SPEC.md 27.6.1)"
              % (t, st["np_capkb"], 16))

print()
if fails:
    sys.exit("regrowshed: FAILED: %s" % ", ".join(fails))
print("regrowshed: a grow sheds, and the toast tells memory from size")
