#!/usr/bin/env python3
"""THE BOUNCE BONANZA COURSE BUILDER, PACKED FOR PEOPLE WITH NO os8088 TREE
(SPEC.md 130.55.11), the battle builder's shape (tools/os88vbtbundle.py).

    make bbeditbundle       # -> build/os8088-course-builder.zip
    python3 tools/bbeditbundle.py OUT.zip

One folder, `os8088-course-builder/`: the window (bbedit.py), the model and
its command line (bbedproj.py), the job it runs (bbedjob.py) and every
tools/ module they import, at the TOP; under `data/`, the working files the
compiler reads, at their places in the tree - apps/bonanza/courses/ (every
course and the art they name), demos/, music/, fonts/tallx.f8 - and
data/Makefile, the course lists (BZ_COURSES, BZ_TESTCRS) and nothing else.
bbcourse, bonanza_assets, bbmusic and bbicons take `data/` beside them as
their ROOT when it is there, so the same files run in the tree and in the
bundle. The module list is COMPUTED (os88vbundle.closure over every import
from the ROOTS); a third-party import nobody expects stops the build. The
zip is deterministic: sorted entries, every timestamp 1980-01-01.
"""
import argparse
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TREE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import os88vbundle as VB    # noqa: E402

ROOTS = ("bbedit.py", "bbedjob.py", "bbedproj.py")
THIRD_PARTY = {"PIL"}
# imported only inside functions the builder never calls: the music's WAV
# render (numpy, pyopl) and the compiler's guest checks (unicorn)
LAZY = {"numpy", "pyopl", "unicorn"}
DATA_DIRS = ("apps/bonanza/courses", "apps/bonanza/demos", "apps/bonanza/music")
DATA_FILES = ("fonts/tallx.f8",)
FOLDER = "os8088-course-builder"

README = """os8088 BOUNCE BONANZA COURSE BUILDER
====================================

Makes and edits Bounce Bonanza courses (.bbc files): a top-down PLAN with a
height map, the game's own ISO picture (Tab switches between them), every
tile and prop in the palette, and the course compiler's checks - errors
that stop a course building and warnings about what the player cannot see.

    python3 bbedit.py [COURSE.bbc]

    (Windows: py bbedit.py)

The courses that ship with the game are in data/apps/bonanza/courses/;
open one to start, or File > New course. Your own courses can live
anywhere.

IN THE WINDOW
  Build tab   the palette on the left (search it), the course in the middle,
              the selected part's settings on the right.
              Click a part, then click the course (or drag a rectangle for
              floors, walls, holes and surfaces). Esc goes back to Select.
              Click to select, drag or use the arrow keys to move, Delete to
              remove, Ctrl+D to duplicate, Ctrl+Z / Ctrl+Y to undo and redo.
              Mouse wheel zooms; right- or middle-drag pans.
              Plan: Height map, Route and Hard to see switch overlays.
              Iso: CGA or Hercules; X-ray dims everything but the selection,
              shows a part's hidden pixels in red and what hides them in
              orange. Hover names what drew each pixel.
              The list under the course is every problem; click one to go
              to it.
  Course tab  the title, size, ball, music, colours, times; "Ready to play?"
              runs the full check (by itself, 2 s after you stop editing).
  Source tab  the file itself; double-click a line to select it.

  Saving changes only the lines you edited: comments and order are kept.
  A family a part needs (`uses magnet`, ...) is added for you.

THE COMMAND LINE (what agents use; the same edits as the window)
    python3 bbedproj.py check COURSE.bbc [--strict] [--json]
    python3 bbedproj.py show  COURSE.bbc
    python3 bbedproj.py add   COURSE.bbc "prop bumper 14 19"
    python3 bbedproj.py set   COURSE.bbc LINE "floor rect 6 9 11 14 flat 16"
    python3 bbedproj.py move  COURSE.bbc LINE DX DY
    python3 bbedproj.py remove COURSE.bbc LINE
    python3 bbcourse.py --png OUTDIR COURSE.bbc     the game's pictures

NEEDS
  Python 3.11 or newer with Tk (python.org's installer has it; on Linux the
  python3-tk package), and Pillow:
      python3 -m pip install pillow
  The checks keep a cache in data/build/bbcache/ (safe to delete).
"""


def course_lists():
    """data/Makefile: the tree Makefile's BZ_COURSES and BZ_TESTCRS lines, as bbcourse.default_paths reads
    them (its continuation lines joined), and nothing else"""
    import bbcourse as B
    mk = B._makefile()
    out = ["# The course lists of os8088's Makefile (BZ_COURSES, BZ_TESTCRS), for the course builder's",
           "# bundle: tools/bbcourse.py reads the courses and their order from here (SPEC.md 130.55.11).", ""]
    for var in ("BZ_COURSES", "BZ_TESTCRS"):
        files = B._mk_list(mk, var)
        if files:
            out.append("%s := %s" % (var, " ".join(files)))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    a = ap.parse_args()
    mods, other = VB.closure(ROOTS)
    stray = other - THIRD_PARTY - LAZY
    if stray:
        sys.exit("bbeditbundle: the builder imports %s, which is neither in tools/ nor expected "
                 "(THIRD_PARTY, LAZY) - add it there and to the README, or drop the import" % ", ".join(sorted(stray)))
    files = [(m, open(os.path.join(HERE, m), "rb").read(), 0o755) for m in mods]
    for d in DATA_DIRS:
        for base, dirs, names in os.walk(os.path.join(TREE, d)):
            dirs.sort()
            for n in sorted(names):
                p = os.path.join(base, n)
                rel = os.path.relpath(p, TREE).replace(os.sep, "/")
                files.append(("data/" + rel, open(p, "rb").read(), 0o644))
    for f in DATA_FILES:
        files.append(("data/" + f, open(os.path.join(TREE, f), "rb").read(), 0o644))
    files.append(("data/Makefile", course_lists().encode("ascii"), 0o644))
    files.append(("README.TXT", README.replace("\n", "\r\n").encode(), 0o644))
    tmp = a.out + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data, mode in sorted(files):
            zi = zipfile.ZipInfo("%s/%s" % (FOLDER, name), VB.STAMP)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = (0o100000 | mode) << 16
            z.writestr(zi, data)
    os.replace(tmp, a.out)
    print("bbeditbundle: %s - %d files (%d modules, %d data files), %d bytes" % (
        a.out, len(files), len(mods), len(files) - len(mods) - 1, os.path.getsize(a.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
