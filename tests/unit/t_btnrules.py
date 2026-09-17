#!/usr/bin/env python3
"""THE BUTTON REGISTRY (SPEC.md 20.5.1.3, tests/btnsites.txt).

`os88ui_btn` is the standard button and carries the SPEC.md 13.7 gesture with
it.  `os88ui_btnraw` is the bare painter underneath - no gesture at all - so a
caller on it owns the press/release/track/repaint dance by hand, and
twenty-five of the tree's call sites owned it by NOT doing it: they fired on
the press, showed no pressed look, and could not be cancelled by sliding off.

IT IS A RATCHET, NOT A CLEAN GATE, and that is deliberate.  The registry starts
at the counts the tree actually has, because a rule that cannot be enforced
from the day it is written is not enforced at all.  Four failures:

  * a FILE NOT IN THE REGISTRY calling either - the case that matters, because
    it is what a new package hits;
  * a file EXCEEDING either count;
  * a count that is now too HIGH, so the numbers cannot rot quietly behind a
    conversion that lowered them;
  * a `raw` line with no reason after the `#`.

WHY STATIC AND NOT DRIVEN: a press-fired button and a release-fired one are the
same pixels in every still.  The difference exists only while a button is
physically held, and no screenshot-driven row holds one down - which is exactly
how this survived ten packages and a written survey
(docs/plans/completed/UIHELPERS-PLAN.md 15.4, SPEC.md 13.8.4).

t_textrules.py is the precedent and most of this is its shape.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import check, done                           # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
REGISTRY = os.path.join(ROOT, "tests", "btnsites.txt")

REC = re.compile(r"^\s*call os88ui_btn\b", re.M)
RAW = re.compile(r"^\s*call os88ui_btnraw\b", re.M)
SCAN = ("apps", "drivers", "kernel")
EXT = (".asm", ".inc", ".c", ".h")


def registry():
    """path -> (record, raw, reason); and the parse errors found on the way."""
    out, bad = {}, []
    for n, line in enumerate(open(REGISTRY, encoding="utf-8"), 1):
        body = line.split("#", 1)
        reason = body[1].strip() if len(body) > 1 else ""
        f = body[0].split()
        if not f:
            continue
        if len(f) != 3 or not f[0].isdigit() or not f[1].isdigit():
            bad.append("%s:%d: want `<record> <raw> <path>  # <reason>`, got %r"
                       % (os.path.basename(REGISTRY), n, line.rstrip()))
            continue
        rec, raw, path = int(f[0]), int(f[1]), f[2]
        if raw and not reason:
            bad.append("%s:%d: %s calls os88ui_btnraw %d time(s) and gives no "
                       "reason. A raw call is a button with NO gesture "
                       "(SPEC.md 13.6) - say why, or convert it"
                       % (os.path.basename(REGISTRY), n, path, raw))
        out[path] = (rec, raw, reason)
    return out, bad


def tree():
    """path -> (record, raw) for every source that calls either."""
    out = {}
    for base in SCAN:
        for dp, _, fns in os.walk(os.path.join(ROOT, base)):
            for fn in fns:
                if not fn.endswith(EXT):
                    continue
                p = os.path.join(dp, fn)
                try:
                    t = open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                rec, raw = len(REC.findall(t)), len(RAW.findall(t))
                if rec or raw:
                    rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
                    out[rel] = (rec, raw)
    return out


def main():
    reg, bad = registry()
    live = tree()

    for path, (rec, raw) in sorted(live.items()):
        if path not in reg:
            bad.append("%s is NOT in tests/btnsites.txt and calls the button "
                       "(%d record, %d raw). Every caller is registered with a "
                       "reason - and if this is a NEW raw caller it is a button "
                       "that fires on the press, which is the defect the "
                       "registry exists for (SPEC.md 20.5.1.3)" % (path, rec, raw))
            continue
        wrec, wraw, _ = reg[path]
        if raw > wraw:
            bad.append("%s calls os88ui_btnraw %d time(s), registered for %d. "
                       "THE RAW COUNT MAY ONLY GO DOWN: a new one is a button "
                       "with no gesture (SPEC.md 13.6)" % (path, raw, wraw))
        if raw < wraw:
            bad.append("%s calls os88ui_btnraw %d time(s), registered for %d - "
                       "lower the number, which is the diff saying the "
                       "conversion happened" % (path, raw, wraw))
        if rec != wrec:
            bad.append("%s calls os88ui_btn %d time(s), registered for %d - "
                       "keep the count honest" % (path, rec, wrec))

    # --- THE RECORD MUST BE AIMED, and by the file that draws from it -------
    # A record whose BT_RECTS or BT_N is never written is all zeroes, and
    # os88ui_btn draws NOTHING for an index past a live count of 0.  That is
    # not a subtle failure: it is a button that is simply absent, and it
    # shipped once - apps/artful/atui.inc set its flags and its rects and
    # never the record's three POINTERS, so the modal had no buttons at all.
    #
    # It cannot catch the other half of that bug (DOS aimed its record in the
    # CLICK path, so the paint path drew nothing) - only driving it can, which
    # is tests/btngesture.py's DOS case.  It catches the half that is visible
    # from the source.
    AIM = re.compile(r"OS88UI_BT_RECTS\]")
    CNT = re.compile(r"OS88UI_BT_N\]")
    for path, (rec, raw) in sorted(live.items()):
        if not rec or path.endswith("os88ui.inc"):
            continue
        t = open(os.path.join(ROOT, path), encoding="utf-8",
                 errors="replace").read()
        if not AIM.search(t):
            bad.append("%s calls os88ui_btn but never writes "
                       "OS88UI_BT_RECTS: its record's rect array is a null "
                       "pointer and the buttons do not appear at all "
                       "(SPEC.md 20.5.1.3)" % path)
        if not CNT.search(t):
            bad.append("%s calls os88ui_btn but never writes OS88UI_BT_N: a "
                       "live count of 0 means every index is past the end and "
                       "os88ui_btn draws nothing (SPEC.md 20.5.1.3)" % path)

    for path in sorted(reg):
        if path not in live:
            bad.append("%s is in tests/btnsites.txt and calls neither - drop "
                       "the line" % path)

    check("every button call site is registered, and the raw count only falls",
          not bad, 0, len(bad),
          "os88ui_btnraw is the painter with NO gesture; os88ui_btn is the "
          "control (SPEC.md 20.5.1.3). A press-fired button and a "
          "release-fired one photograph identically, so nothing else in the "
          "suite can see this.")
    for b in bad:
        print("  " + b)
    nrec = sum(v[0] for v in live.values())
    nraw = sum(v[1] for v in live.values())
    print("btnrules: %d record call(s), %d raw, in %d file(s)"
          % (nrec, nraw, len(live)))
    done("t_btnrules")


if __name__ == "__main__":
    main()
