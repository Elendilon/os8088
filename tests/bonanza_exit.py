#!/usr/bin/env python3
"""BONANZA: nothing is left behind - every way out drops both claims (SPEC.md 128.10.6.2, 128.10.11.3).

    make bonanzadisk && python3 tests/bonanza_exit.py [--adapter cga|herc|both]
    python3 tests/bonanza_exit.py --red leak        (the red arm, below)

A launch fetches TWO lazy, compressed parts on the desktop - the course's row
for the card and the ball's (SPEC.md 128.10.6.1) - and holds them in DS and
ES for the bracket's whole life, so both stay PINNED (128.10.6.3) and every
way out must drop both (128.10.6.2's table).  This row takes each of the
five ways out, on both cards:

    Esc, F, Alt+Enter    a play of FIRST (Enter), left by that key
    the benchmark's end  B, BENCH, its 1,200th frame
    the goal             a play of FIRST whose ball is POKED onto the goal
                         column at bz_t0 (as bonanza_phys's goal scenario):
                         the play ends the frame after the grounded step

and asserts, against what was read on the desktop BEFORE that launch:

  1  every part row of BONANZA.O88's table (os88parts.inc's op_table, all
     2 + 2 BZ_NCRS of them): OP_FETCHED clear - so op_seg answers 0 for it,
     op_seg's own test (os88partsbody.inc) - and OP_R_ZKB equal to its
     value before the launch: on an OP_COMP | OP_LAZY row that word is the
     PACKED LENGTH until a fetch banks the segment in it, and op_drop writes
     the length back (SPEC.md 20.12.7.4.1), so a row dropped wrong cannot be
     fetched again;
  2  the instance's heap claims, read by tools/heapmap.py (mem_tab: the
     region, owned by its instance slot, and the data claims, owned by the
     package's segment - kernel/memory.inc MC_OWN), exactly those before the
     launch: the same count, sizes and pinning.  The region may MOVE (it is
     OS88_REGION_MOVABLE), so a claim is compared by what it is, not where;
  3  as a POSITIVE CONTROL, inside every bracket: the two rows the launch
     fetched have OP_FETCHED set and a segment in OP_R_ZKB, and the claims
     are two more than on the desktop - the check above can see a part that
     is there.

It reports, for each launch, the floppy controller's reads from the key to
the bracket (MartyPC's own counter, m.disk(): no guest instrument) - SPEC.md
128.10.9's "the launch's int 13h calls, within one of wave 0b's".  A refused
fetch is not driven (it needs a heap too short at one moment and not the
next, SPEC.md 128.10.11.3); the review reads that path.

--red leak builds a package (in a temporary directory, never build/) whose
GOAL path does not drop the course's row, and PASSES only if the row FAILS -
at the goal, and only there.
"""
import argparse
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import heapmap                 # noqa: E402
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_phys as P       # noqa: E402

OP_ROW, OP_T_ROWS, OP_R_FLAG, OP_R_ZKB = 8, 10, 1, 6        # apps/os88parts.inc
OP_LAZY, OP_FETCHED = 8, 32
WAYS = ("esc", "f", "altenter", "bench", "goal")


class Q(object):
    """heapmap.Map wants .read(linear, n); Marty has exactly that"""

    def __init__(self, m):
        self.m = m

    def read(self, linear, n):
        return self.m.read(linear, n)


def rows(g):
    """[(flags, zkb)] for every part row, read out of the image's own table"""
    n = g.m.read(g.a("op_table") + 8, 1)[0]
    raw = g.m.read(g.a("op_table") + OP_T_ROWS, n * OP_ROW)
    return [(raw[i * OP_ROW + OP_R_FLAG], struct.unpack_from("<H", raw, i * OP_ROW + OP_R_ZKB)[0])
            for i in range(n)]


def claims(g):
    """The instance's claims through tools/heapmap.py: [(role, paragraphs, pinned,
    owner)], sorted - the region (the claim holding the window's W_SEG; MC_OWN
    its instance slot) and the data claims (MC_OWN = the package's segment)."""
    m = g.m
    mp = heapmap.Map(Q(m), {n: m.sym(n) for n in ("mem_base", "mem_top", "spl_live", "mem_tab")})
    seg = g.wseg()
    reg = [c for c in mp.claims if c.seg <= seg < c.end]
    assert len(reg) == 1, "no claim of the heap holds BONANZA's segment %04X" % seg
    out = [("region", reg[0].para, reg[0].pinned, owner_kind(reg[0].own))]
    out += [("data", c.para, c.pinned, "seg") for c in mp.claims if c.own == seg]
    return sorted(out)


def owner_kind(own):
    return "slot" if own < 12 else "%04X" % own


def leave(g, way):
    """One way out of a running play (Esc, F, Alt+Enter)."""
    m = g.m
    if way == "esc":
        g.key("Escape")
    elif way == "f":
        g.key("KeyF")
    else:
        m.key("AltLeft", up=False)
        M.pace(m, .04)
        m.key("Enter", up=False)
        M.pace(m, .04)
        m.key("Enter", down=False)
        m.key("AltLeft", down=False)


def launch(g, way):
    """Start the launch that WAY leaves by; -> the floppy reads it took, once
    the bracket is up (both parts fetched)."""
    m = g.m
    m.disk(reset=True)
    if way == "bench":
        g.key("KeyB")
    else:
        g.key("Enter")
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.w("bz_frames") > 3, "the bracket is up (%s)" % way, guest=60)
    m.pause()
    return m.disk()["reads"]


def goal(g):
    """Play FIRST to its goal: the ball poked onto the goal column at bz_t0."""
    m = g.m
    (wx, wy), gvx, gvy, _ = P.SCEN["goal"]
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0)
    while wk.next() != "t0":
        pass
    p = BB.Physics(R.course("first"), play=True).poke(wx, wy, gvx, gvy)
    R.poke_ball(g, p.gx, p.gy, p.gz, p.gvx, p.gvy, p.gvz)
    m.bp_exec()
    m.run()


def one(g, way, base_rows, base_claims):
    """One launch left by WAY: -> (failures, the report line)"""
    m = g.m
    fails = []
    reads = launch(g, way)
    pc, pb = g.b("bz_pc"), g.b("bz_pb")
    r_in, c_in = rows(g), claims(g)
    for i in (pc, pb):
        f, z = r_in[i]
        if not f & OP_FETCHED or not z:
            fails.append("%s: inside the bracket row %d is not fetched (flags %02X zkb %04X): the control cannot "
                         "see a part that is there" % (way, i, f, z))
    if len(c_in) != len(base_claims) + 2:
        fails.append("%s: inside the bracket the instance holds %d claims, not the desktop's %d + 2: %s" % (
            way, len(c_in), len(base_claims), c_in))
    if way == "bench":
        m.run()
        M.until(m, lambda _: g.b("bz_fs") == 0, "the benchmark's 1,200 frames", guest=120)
    elif way == "goal":
        goal(g)
        M.until(m, lambda _: g.b("bz_fs") == 0, "the play to end at the goal", guest=60)
        if not g.b("bz_fin"):
            fails.append("goal: the play ended but [bz_fin] is clear - it did not end at the goal")
    else:
        m.run()
        leave(g, way)
        M.until(m, lambda _: g.b("bz_fs") == 0, "the play to end on %s" % way, guest=60)
    # bz_launch's .drop writes bz_cseg and bz_bseg 0 LAST, after both op_drop calls
    M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "the launch to drop its parts (%s)" % way,
            guest=30)
    m.pause()
    r_out, c_out = rows(g), claims(g)
    for i, (before, after) in enumerate(zip(base_rows, r_out)):
        if after[0] & OP_FETCHED:
            fails.append("%s: part row %d is still FETCHED after the launch (op_seg answers %04X)" % (
                way, i, after[1]))
        if after[1] != before[1]:
            fails.append("%s: part row %d's zkb is %04X after the launch, %04X before (op_drop did not write "
                         "the packed length back)" % (way, i, after[1], before[1]))
    if c_out != base_claims:
        fails.append("%s: the instance's claims after the launch %s, before it %s" % (way, c_out, base_claims))
    m.run()
    line = "%s: rows %d,%d fetched inside; %d floppy reads to the bracket; after it every row as before and the " \
           "claims as before: %s" % (way, pc, pb, reads, "yes" if not fails else "NO")
    return fails, line


def run(tag, ways=WAYS, apps=None, src=None):
    sym = R.symbols(src)
    fails = []
    with os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, tag, sym, live=True)     # the region is movable and launches claim and drop
        ui.settle()
        m = g.m
        m.pause()
        base_rows, base_claims = rows(g), claims(g)
        m.run()
        nlazy = sum(1 for f, _ in base_rows if f & OP_LAZY)
        print("%s: %d part rows (%d lazy), none fetched on the desktop: %s; the instance's claims %s" % (
            tag, len(base_rows), nlazy, all(not f & OP_FETCHED for f, _ in base_rows), base_claims), flush=True)
        if any(f & OP_FETCHED for f, _ in base_rows):
            fails.append("a part row is fetched on the desktop before any launch")
        for way in ways:
            f, line = one(g, way, base_rows, base_claims)
            print("%s %s" % (tag, line), flush=True)
            fails += f
            if f:
                break
    return fails


REDS = {
    # the goal path does not drop the course's row: bz_fin is set only by a play that reached the goal
    "leak": [("bonanza.asm", "    mov al, [bz_pc]\n    call op_drop\n",
              "    cmp byte [bz_fin], 0         ; RED leak: the goal keeps the course\n    jne .redleak\n"
              "    mov al, [bz_pc]\n    call op_drop\n.redleak:\n")],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--red", choices=sorted(REDS))
    a = ap.parse_args()
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            for tag in tags:
                try:
                    bad = run(tag, apps=img, src=src)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert all(b.startswith("goal:") for b in bad), \
                    "RED ARM %s on %s went red somewhere other than the goal: %s" % (a.red, tag, bad)
                print("bonanza_exit --red %s (%s): went red at the goal, as it must" % (a.red, tag), flush=True)
        print("bonanza_exit --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad = []
    for tag in tags:
        bad = run(tag)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d exit failure(s)" % len(allbad)
    print("bonanza_exit (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
