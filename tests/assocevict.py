#!/usr/bin/env python3
"""MORE DECLARING PROGRAMS THAN SLOTS, AND EVERY LISTING STILL HAS ITS ICONS
(SPEC.md 54.2.3).

The kernel's association table is ASSOC_NAPP program slots and ASSOC_NEXT
extension rows, RESIDENT, and nothing used to free one: the program that
arrived after the table filled was dropped silently, and its documents drew
the bare page for the rest of the session. A standard install filled it to
the last slot. Since 54.2.3 a full table EVICTS the least-recently-used slot
- but only on DEMAND (a declaring program in the listing being mounted, a
running program's claim, or the rows of ASSOC.DAT this listing's documents
want), never one used in the current generation, the pending open, or a slot
a STICKY runtime claim names.

The fixture is a scratch floppy built here: EIGHTEEN fake programs - CALC's
header and icon, its flags given the association bit and its block one
extension, `.Q01` to `.Q18`; the harvest reads a header and nothing runs
them - six to a folder in F1, F2 and F3, each beside one document of each of
its programs' types, and a DOCS folder holding F1's six types alone. Eighteen
is more than the eleven slots the five built-ins leave.

  1  F1, F2, F3 in turn: every document and every program in each has a real
     row (not ICO_R_NONE). With eviction taken out this fails at F2: B:'s
     ASSOC.DAT merge filled the eleven free slots at the first mount, so
     FAKE12 - answered from the icon store, which makes no slot - has none
     and D12.Q12 is bare (measured).
  2  DOCS, after F2 and F3 have pushed F1's programs out: F1's six types are
     NOT programs in this listing, so only the DEMAND MERGE can bring them
     back - asc_demand marks the volume's ASSOC.DAT rows these documents
     want, the re-read flag makes the stamped volume read again, and the
     first pass evicts for them.
  3  A STICKY row is never evicted: Q01's row is made sticky (what
     OSAPI_ASSOC_SET leaves) before F2 and F3, and FAKE01 is still in the
     table after them.

Break it on purpose: make assoc_app_new's full arm refuse without calling
assoc_evict, or drop `call asc_demand`, and leg 1 fails at F2 on D12.Q12 -
both measured. (Without the demand marking the re-read happens and its merge
may only fill free slots, of which there are none.)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import os88build                                           # noqa: E402
import os88marty as M                                      # noqa: E402
import os88sym                                             # noqa: E402
import os88ui                                              # noqa: E402

SYS = "build/os8088-360.img"
NFAKE = 18
_SY = os88sym.syms()
_EQ = os88sym.equates()


def V(name):
    return _SY[name] if name in _SY else _EQ[name]


def fail(msg):
    print("assocevict: FAIL: %s" % msg)
    sys.exit(1)


def fixture(dirn):
    calc = open(os88build.at("build/calc.o88"), "rb").read()
    if calc[:2] != b"O8" or not calc[3] & 1:
        fail("build/calc.o88 is not a package with an icon")
    os.makedirs(dirn, exist_ok=True)
    args = []
    for i in range(1, NFAKE + 1):
        folder = "F%d" % ((i - 1) // 6 + 1)
        ext = b"Q%02d" % i
        d = bytearray(calc)
        d[3] = (d[3] | 2) & ~(32 | 128 | 4)     # declares; no glyph, card
        d[96:112] = bytes([1]) + ext + b" " * 12  # the association block
        pkg = os.path.join(dirn, "FAKE%02d.O88" % i)
        open(pkg, "wb").write(bytes(d))
        doc = os.path.join(dirn, "D%02d.Q%02d" % (i, i))
        open(doc, "wb").write(b"document %d\r\n" % i)
        args += ["%s:%s" % (folder, pkg), "%s:%s" % (folder, doc)]
        if i <= 6:
            other = os.path.join(dirn, "E%02d.Q%02d" % (i, i))
            open(other, "wb").write(b"elsewhere %d\r\n" % i)
            args.append("DOCS:" + other)
    img = os.path.join(dirn, "evict360.img")
    rc = os.system("python3 tools/os88disk.py --size 360 -o %s %s >/dev/null"
                   % (img, " ".join(args)))
    if rc:
        fail("tools/os88disk.py could not build the fixture")
    return img


def main():
    if not os.path.exists(SYS):
        fail("%s is missing - `make` builds it" % SYS)
    run_dir = M.stage_run_dir("assocevict")
    img = fixture(os.path.join(run_dir, "fixture"))

    with os88ui.boot(SYS, apps=img, quick=True) as ui:
        m = ui.m
        k = V("KERNEL_SEG")
        lin = getattr(m, "lin", lambda s, o=0: (s << 4) + o)
        napp, next_ = V("ASSOC_NAPP"), V("ASSOC_NEXT")

        def rd(a, n=1):
            return int.from_bytes(m.read((k << 4) + a, n), "little")

        def stems():
            raw = m.read((k << 4) + V("assoc_stem"), napp * 8)
            return [raw[i * 8:i * 8 + 8].rstrip(b" \0").decode("latin-1")
                    for i in range(napp)]

        def ext_rows():
            raw = m.read((k << 4) + V("assoc_ext"), next_ * 4)
            return [(raw[i * 4:i * 4 + 3], raw[i * 4 + 3], i)
                    for i in range(next_)]

        def listing(p):
            ui.path(p)
            M.settle(m)
            vp = rd(V("fm_vp"), 2)
            vs = rd(vp + V("FS_VSEG"), 2)
            n, live = rd(V("dsk_nmax"), 2), rd(vp + V("FS_N"), 2)
            st = V("DSK_DE_STRIDE")
            raw = m.read(lin(vs), n * st)
            ix = m.read(lin(vs, n * st), n)
            out = [(raw[i * st:i * st + 16].split(b"\0")[0].decode("latin-1"),
                    ix[i]) for i in range(min(live, n))]
            return [x for x in out if x[0] != ".."]

        def leg(p, want):
            got = listing(p)
            bare = [nm for nm, r in got if r == 0xFF]
            used = sum(1 for s in stems() if s)
            print("assocevict: %-7s %2d entries, %d slots in use, generic: %s"
                  % (p, len(got), used, " ".join(bare) or "-"))
            if len(got) != want:
                fail("%s lists %d entries, the fixture put %d there"
                     % (p, len(got), want))
            if bare:
                fail("%s: %s on the generic icon - the table did not make "
                     "room for this listing (SPEC.md 54.2.3)"
                     % (p, ", ".join(bare)))

        # --- 3's set-up: Q01 claimed at run time ------------------------
        leg("B:/F1", 12)
        rows = [r for r in ext_rows() if r[0] == b"Q01"]
        if not rows:
            fail("Q01 has no extension row after F1 was listed")
        ext, app, i = rows[0]
        m.write((k << 4) + V("assoc_ext") + i * 4 + 3,
                bytes([app | V("ASSOC_STICKY")]))

        # --- 1: every folder in turn ------------------------------------
        leg("B:/F2", 12)
        leg("B:/F3", 12)

        # --- 3: the sticky slot survived --------------------------------
        if "FAKE01" not in stems():
            fail("FAKE01 was evicted although a STICKY row names it: a "
                 "runtime claim lives in RAM only and would be lost")
        print("assocevict: FAKE01 kept by its sticky row")

        # --- 2: documents whose programs are elsewhere ------------------
        gone = [s for s in ("FAKE02", "FAKE03", "FAKE04") if s not in stems()]
        if not gone:
            fail("F2 and F3 evicted none of F1's programs - DOCS would be "
                 "answered by slots that never left, testing nothing")
        leg("B:/DOCS", 6)
        print("assocevict: DOCS re-learned %s from ASSOC.DAT"
              % ", ".join(gone))
    print("assocevict: ok")


if __name__ == "__main__":
    main()
