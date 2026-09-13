#!/usr/bin/env python3
"""Is the CHEAP what-if right?  (docs/plans/REGION-SELF-COMPACT-PLAN.md 5.1)

    python3 tools/heapwhatif.py

The question is whether a package can be told "how much would you have if you
moved too?" WITHOUT the kernel carrying an exact combined plan - which is
~150-250 resident bytes against ~50 for three plans and a subtraction:

    what-if  =  A  +  (D_free - D_pinned)

A being the ascending plan (plain mem_avail's own answer), D_pinned the
descending plan as things stand, and D_free the same with the caller's region
treated as frameless.  All three are arithmetic over 32 records; nothing moves.

It is checked against the TRUE both-passes figure - the descending pass RUN for
real, barriers and all, then the floor planned against the result - over the
layout tests/heapmap read off a running machine and six built to break it.
The reference is tools/heapmap.py's own model, so this asserts the formula and
not the model.

WHY IT IS A SCRIPT AND NOT A ROW: nothing here runs the kernel.  It is the
arithmetic behind a design decision, kept runnable so the decision can be
re-taken against a layout somebody adds rather than re-argued.  The row that
would assert it on the machine is that plan's 7.2, and it does not exist yet.

UNDER-REPORTING IS THE SAFE DIRECTION and the whole reason the approximation
is affordable: a what-if that reads low makes a package skip a post that would
have helped, which is exactly where it stands with no flag at all.  One that
read HIGH would talk it into a compaction that disturbs every other holder's
claims for less than advertised.
"""
import copy, os, sys
sys.path.insert(0, "/home/user/os8088/tools")
import heapmap

PARA = 64                                   # paragraphs per KB


class C(object):
    def __init__(self, seg, kb, hi, movable, purge=False):
        self.seg, self.para, self.hi = seg, kb * PARA, hi
        self.rloc = 160 if movable else 0
        self.purgeable, self.own, self.dma = purge, 3, 0
    @property
    def end(self): return self.seg + self.para
    @property
    def pinned(self): return self.rloc == 0


class M(object):
    def __init__(self, base, top, claims):
        self.base, self.top = base, top
        self.claims = sorted(claims, key=lambda c: c.seg)
    runs = heapmap.Map.runs
    compacted = heapmap.Map.compacted


def true_combined(m):
    """Both passes for real: RUN the descending pass - mirroring
    heapmap.compacted(up=True)'s own walk, barriers and all - then plan the
    floor against the result."""
    s = copy.deepcopy(m)
    at = s.top
    for c in reversed(s.claims):
        if c.purgeable:
            continue
        if c.pinned or not c.hi:
            at = c.seg                      # a barrier: the fill point resumes
        else:
            at -= c.para
            c.seg = at                      # ...and it MOVES there
    s.claims.sort(key=lambda c: c.seg)
    return max((p for _, p in s.compacted(up=False)), default=0) / PARA


def cheap(m, me):
    """A + (D_free - D_pinned), three PLANS and no move."""
    A = max((p for _, p in m.compacted(up=False)), default=0) / PARA
    dp = max((p for _, p in m.compacted(up=True)), default=0) / PARA
    f = copy.deepcopy(m)
    for c in f.claims:
        if c.seg == me:
            c.rloc = 160                    # "pretend I am frameless"
    df = max((p for _, p in f.compacted(up=True)), default=0) / PARA
    return A + (df - dp), A


def after_the_pass(m, me):
    """What PLAIN mem_avail reads once the posted compaction has actually run -
    the ascending plan over a heap that is already packed BOTH ways.  No
    what-if, no combined plan, no new kernel arithmetic at all."""
    s = copy.deepcopy(m)
    for c in s.claims:
        if c.seg == me:
            c.rloc = 160                    # the service point: I am frameless
    at = s.top                              # ...the descending pass, RUN
    for c in reversed(s.claims):
        if c.purgeable:
            continue
        if c.pinned or not c.hi:
            at = c.seg
        else:
            at -= c.para
            c.seg = at
    s.claims.sort(key=lambda c: c.seg)
    at = s.base                             # ...and the ascending pass, RUN
    for c in list(s.claims):
        if c.purgeable:
            continue
        if c.pinned or c.hi:
            at = c.end
        else:
            c.seg = at
            at = c.end
    s.claims.sort(key=lambda c: c.seg)
    # ...then PLAIN mem_avail: the ascending PLAN over the packed heap.
    return max((p for _, p in s.compacted(up=False)), default=0) / PARA


def case(name, base, top, claims, me):
    m = M(base, top, claims)
    free = copy.deepcopy(m)                 # what-if: my region movable
    for c in free.claims:
        if c.seg == me:
            c.rloc = 160
    want = true_combined(free)
    got, plain = cheap(m, me)
    woke = after_the_pass(m, me)
    err = got - want
    verdict = "ok " if abs(err) < 0.01 else ("OVER" if err > 0 else "UNDER")
    print("  %-35s plain %6.1f | what-if %6.1f %s%+5.1f | on the wake %6.1f %s"
          % (name, plain, got, verdict, err, woke,
             "ok " if abs(woke - want) < 0.01 else "WRONG"))


B, T = 0x1B20, 0xA000                       # the measured machine's arena
# the measured layout, CALC closed: 8K hole above a 20K movable region
base_lo = [C(0x1B20, 3, False, True), C(0x1D20, 3, False, True),
           C(0x2FC0, 3, False, True)]
case("measured (8K hole above me)", B, T,
     base_lo + [C(0x9900, 20, True, False)], 0x9900)
case("no hole above me", B, T,
     base_lo + [C(0x9900, 20, True, False), C(0x9E00, 8, True, False)], 0x9900)
case("hole above, another mover below me", B, T,
     base_lo + [C(0x9400, 20, True, True), C(0x9900, 20, True, False)], 0x9900)
case("PINNED driver between me and roof", B, T,
     base_lo + [C(0x9900, 20, True, False), C(0x9E00, 4, True, False),
                C(0x9F00, 4, True, False)], 0x9900)
case("me at the very ceiling", B, T,
     base_lo + [C(0x9B00, 20, True, False)], 0x9B00)
case("two holes, one above one below me", B, T,
     base_lo + [C(0x9000, 12, True, True), C(0x9900, 20, True, False)], 0x9900)
# --- the reported layout: free at the top, me, another package under me ----
case("[free][me][another pkg], adjacent", B, T,
     base_lo + [C(0x9400, 20, True, True), C(0x9900, 20, True, False)], 0x9900)
case("[free][me][another], another PINNED", B, T,
     base_lo + [C(0x9400, 20, True, False), C(0x9900, 20, True, False)], 0x9900)
case("[free][me][gap][another movable]", B, T,
     base_lo + [C(0x9000, 20, True, True), C(0x9900, 20, True, False)], 0x9900)
case("[free][me][gap][gap][2 movable]", B, T,
     base_lo + [C(0x8800, 8, True, True), C(0x9000, 12, True, True),
                C(0x9900, 20, True, False)], 0x9900)
case("big floor barrier (pinned cache)", B, T,
     [C(0x1B20, 3, False, True), C(0x4000, 40, False, False),
      C(0x2FC0, 3, False, True)] + [C(0x9900, 20, True, False)], 0x9900)
