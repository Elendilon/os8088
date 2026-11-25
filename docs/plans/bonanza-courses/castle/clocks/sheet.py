#!/usr/bin/env python3
"""CASTLE CLIMB's clock study, compiled and drawn (host only; ../../clockkit.py is the kit and says what each
option does, frames.py holds the concepts).    python3 docs/plans/bonanza-courses/castle/clocks/sheet.py --help"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import clockkit                                        # noqa: E402

clockkit.PALS[2] = ((0, 0, 0), (85, 255, 255), (255, 85, 85), (255, 255, 255))   # the CGA's palette 2 (mode 5's)


def _warned():
    """the kit calls clock_vis() OUTSIDE a compile, where a visual finding is a refusal (SPEC.md 130.58.4); this
    course carries findings as warnings (the gate's clock hides a ball behind its pillar), so collect them
    instead, and write every warning of the compile beside the sizes: clocks/<concept>.warn.txt"""
    import bbcourse as B
    vis, run = B.clock_vis, clockkit.run

    def clock_vis(c, *a, **k):
        if B._VWARN is not None:                    # (inside a compile: a warning already)
            return vis(c, *a, **k)
        B._VWARN = []
        try:
            return vis(c, *a, **k)
        finally:
            B._VWARN = None
    B.clock_vis = clock_vis
    comp = B.compile_course

    def compile_course(path, *a, **k):
        c = comp(path, *a, **k)
        name = os.path.basename(path).split("-")[-1][:-4]
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".warn.txt"), "w") as f:
            f.write("".join("%s: %s\n" % (w.get("kind"), w["msg"].split("/")[-1]) for w in getattr(c, "warnings", [])))
        return c
    B.compile_course = compile_course



if __name__ == "__main__":
    if sys.argv[1:2] == ["--help"]:
        print(clockkit.__doc__)
    else:
        _warned()
        clockkit.main(course="castle", palette=2,
                      positions=("start (the outer wall)", "the first gate", "the terraces", "the keep"))
