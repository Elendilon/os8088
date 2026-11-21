#!/usr/bin/env python3
"""DOWNHILL DECISION: STRUCTURAL visual-interest options (STRUCT.md).  A scratch copy of the lead's sketch, never
the sketch itself: it imports ../sketch.py as it stands, adds ONE option's statements, and writes a course.

    python3 variants.py OPTION OUT.bbc        # OPTION: base A B C D E F (base must equal down.bbc byte for byte)

Every statement is in SKETCH coordinates (the engine's less 4) and is added AFTER the sketch has laid the course,
so an option is a pure addition to the text.  Options A - C are `float` alone: the picture's and nothing else's
(SPEC.md 130.27.2 - no grid byte, no physics, no route).  D and E touch the grid on cells no route goes near and
are priced as such in STRUCT.md."""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sketch", os.path.join(HERE, "..", "sketch.py"))
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
w = S._w


def flt(x0, y0, x1, y1, thick=None):
    return "float rect %d %d %d %d%s" % (w(x0), w(y0), w(x1), w(y1), " thick %g" % thick if thick else "")


def opt_A():
    """the BOUNCE LANDING L floats: its columns stop 3 units under its top, so it no longer stands on one magenta
    wall with the steel leg's lower platforms below it (the owner's two checkers in one field)"""
    return ["# STRUCT A: the bounce landing floats - its checker separated from the steel leg's below it",
            flt(34, 10, 39, 15)]


# the upper run's FRONT edge (the +y row, sketch y 13) east of the chute's corner, and the ramp's open +x side
PIERS = (11, 12, 19, 20, 25)             # grounded: the piers (the chute's corner, x <= 8, stays a grounded tower)


def opt_B():
    """an ARCADE under the upper run: the front edge of the hump run, descent and funnel floats, with grounded
    PIERS left standing; the ramp's open side floats as a slab coming down the hill"""
    L = ["# STRUCT B: the upper run on piers - its front edge floats, piers at x %s stay grounded"
         % ", ".join(str(p) for p in PIERS)]
    run = [x for x in range(9, 27) if x not in PIERS]
    i = 0
    while i < len(run):                                    # the floated stretches between piers, as rects
        j = i
        while j + 1 < len(run) and run[j + 1] == run[j] + 1:
            j += 1
        L.append(flt(run[i], 13, run[j] + 1, 14))
        i = j + 1
    L.append(flt(5, 4, 6, 9))                              # the ramp's open side (x 5, y 4 - 8): a slab
    return L


def opt_C():
    """the glass leg's web maze as FLOATING islands: every 3 x 3 island and the banks float; the one-cell membrane
    links stay as they are (a `thick` on a crack would re-lane it, 130.27.2.1), so each reads as a bridge"""
    isl = [(39, 22), (39, 18), (35, 18), (35, 22), (31, 22), (39, 26), (31, 18)]
    L = ["# STRUCT C: the web maze's islands float (the links do not)"]
    L += [flt(x, y, x + 3, y + 3) for x, y in isl]
    L.append(flt(43, 22, 47, 25))                          # the bridge's landing P
    return L


def opt_D():
    """CHAMFERED corners: the outer corners of the bounce landing L and the hub's free front corner cut on the
    diagonal (a `hole half`, SPEC.md 130.24.4) - corners no route and no autopilot way goes near"""
    cuts = [(34, 10, "up"), (38, 10, "right"), (34, 14, "left"), (38, 14, "down"),     # L's four corners
            (42, 16, "left")]                                                           # the hub's front-left
    return ["# STRUCT D: chamfered corners (half holes) on the bounce landing and the hub"] + \
           ["hole  half %s tile %d %d" % (s, w(x), w(y)) for x, y, s in cuts]


# free-standing WALL pillars in the black BEHIND the bounce landing and the hub (lower s than anything near them,
# so nothing on the route is ever drawn behind one): three tiles and more (Chebyshev) from every floor and rail, so
# no ball reaches one (a wall is never a reachable cell, 130.10.4.1); heights stepping down the hill; screen
# columns kept clear of the hub clock's (other agents' art)
PILLARS = [(32, 1, 40 - 12), (36, 3, 40 - 16), (39, 5, 40 - 20)]


def opt_E():
    """a SKYLINE: three free-standing pillars in the black behind the landing and the hub, stepping down"""
    return ["# STRUCT E: free-standing pillars behind the bounce landing and the hub (unreachable)"] + \
           ["wall  tile %d %d  flat %g" % (w(x), w(y), z) for x, y, z in PILLARS]


def opt_F():
    """A + B + C together: the combination priced as one (bytes are not additive)"""
    return opt_A() + opt_B() + opt_C()


OPTS = {"base": lambda: [], "A": opt_A, "B": opt_B, "C": opt_C, "D": opt_D, "E": opt_E, "F": opt_F}

if __name__ == "__main__":
    o, out = sys.argv[1], sys.argv[2]
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    S.iso(tmp)                                             # (as the sketch's own --bbc does first)
    os.remove(tmp)
    add = OPTS[o]()
    if add:
        S.EXTRA += [""] + add
    if "--force" not in sys.argv:
        sys.argv.append("--force")
    S.bbc(out)
