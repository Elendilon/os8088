#!/usr/bin/env python3
"""KITE HILL's clock study, compiled and drawn (host only; ../../clockkit.py is the kit and says what each
option does, frames.py holds the concepts).    python3 docs/plans/bonanza-courses/kite/clocks/sheet.py --help"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
import clockkit                                        # noqa: E402

if __name__ == "__main__":
    if sys.argv[1:2] == ["--help"]:
        print(clockkit.__doc__)
    else:
        clockkit.main(course="kite", palette=0, positions=("start (meadow)", "fan plaza", "launch plaza", "summit"))
