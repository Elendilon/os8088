#!/usr/bin/env python3
"""Every DOT DELIRIUM layout, read out of the source and flooded (SPEC.md 93.2).

A maze is a PICTURE, and the three in `apps/dotdel/ddmzdat.inc` are written out
as characters precisely so that a person can review one in a diff. This is the
half a person cannot do by eye: that all three are 28 x 31, that every dot in
them is REACHABLE from Smiles' start tile, that each has exactly four power
pellets, and that rows 9 to 19 - the ghost house, its door, the two columns
above it, the tunnel row and the two long verticals that carry the board's
traffic past the house - are IDENTICAL in all three.

That last one is the binding invariant (SPEC.md 93.2): every constant that
knows where a ghost is born, where its eyes go home to, where the fruit
appears and where Smiles starts reads those rows, so a layout that moved them
would be a layout the game's own machinery does not fit.

BREAK IT ON PURPOSE (docs/WRITING-TESTS.md 1): put a `#` over one dot's only
way out of a pocket in dd_lay1 and this goes red naming the count; change one
character of row 14 in dd_lay2 and it goes red naming the row. Neither is
visible in a screenshot and neither would stop the game booting - a walled-off
dot is a level that can never be cleared, which is a game that hangs at 99%.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "apps", "dotdel", "ddmzdat.inc")

COLS, ROWS = 28, 31
SHARED = range(9, 20)                       # SPEC.md 93.2's shared block
START = (13, 23)                            # Smiles, in (col, row)
PILLS = 4


def layouts():
    """{name: [31 rows of 28 chars]} straight out of the assembly source."""
    out, cur = {}, None
    for line in open(SRC):
        m = re.match(r"^(dd_lay\d+):", line)
        if m:
            cur = m.group(1)
            out[cur] = []
            continue
        m = re.match(r"^\s+db\s+'(.*)'\s*$", line.rstrip("\n"))
        if m and cur:
            out[cur].append(m.group(1).replace("''", "'"))
    return out


def flood(g):
    """Every tile reachable from Smiles' start, the tunnel wrapping in x."""
    open_ = [[c != '#' for c in row] for row in g]
    seen = [[False] * COLS for _ in range(ROWS)]
    c0, r0 = START
    st = [(r0, c0)]
    seen[r0][c0] = True
    while st:
        r, c = st.pop()
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nr, nc = r + dr, (c + dc) % COLS
            if 0 <= nr < ROWS and open_[nr][nc] and not seen[nr][nc]:
                seen[nr][nc] = True
                st.append((nr, nc))
    return seen


def main():
    lays = layouts()
    fail = []
    if len(lays) != 3:
        fail.append("expected three layouts in %s, found %d: %s"
                    % (os.path.relpath(SRC, ROOT), len(lays), sorted(lays)))
    base = None
    for name in sorted(lays):
        g = lays[name]
        if len(g) != ROWS:
            fail.append("%s: %d rows, want %d" % (name, len(g), ROWS))
            continue
        for i, row in enumerate(g):
            if len(row) != COLS:
                fail.append("%s row %d: %d columns, want %d"
                            % (name, i, len(row), COLS))
            bad = set(row) - set("#.o =")
            if bad:
                fail.append("%s row %d: %s is not a maze character"
                            % (name, i, sorted(bad)))
        if any("%s row" % name in f for f in fail):
            continue

        # the shared block, byte for byte
        if base is None:
            base = (name, g)
        else:
            for r in SHARED:
                if g[r] != base[1][r]:
                    fail.append("%s row %d differs from %s's - rows 9..19 are "
                                "the ghost house, the door, the tunnel and the "
                                "two verticals past it, and every spawn, home "
                                "and fruit constant reads them (SPEC.md 93.2)\n"
                                "      %s: %s\n      %s: %s"
                                % (name, r, base[0], base[0], base[1][r],
                                   name, g[r]))

        c0, r0 = START
        if g[r0][c0] != ' ' or g[r0][c0 + 1] != ' ':
            fail.append("%s: Smiles' start tiles (%d..%d, %d) must be empty "
                        "floor, got %r%r"
                        % (name, c0, c0 + 1, r0, g[r0][c0], g[r0][c0 + 1]))

        seen = flood(g)
        dots = pills = unreach = 0
        for r in range(ROWS):
            for c in range(COLS):
                ch = g[r][c]
                if ch not in ".o":
                    continue
                if ch == ".":
                    dots += 1
                else:
                    pills += 1
                if not seen[r][c]:
                    unreach += 1
                    if unreach <= 3:
                        fail.append("%s: the %s at (%d,%d) cannot be reached "
                                    "from Smiles' start - a board with one of "
                                    "those in it never clears"
                                    % (name, "pellet" if ch == "o" else "dot",
                                       c, r))
        if pills != PILLS:
            fail.append("%s: %d power pellets, want %d (dd_pill_list keeps "
                        "DD_NPILL of them and the blink reads that list)"
                        % (name, pills, PILLS))
        if not 180 <= dots <= 300:
            fail.append("%s: %d dots, want 180..300 - a board that empties in "
                        "seconds or never is not a level" % (name, dots))
        if not fail:
            print("  %-8s ok   %3d dots, %d pellets, all reachable"
                  % (name, dots, pills))

    if fail:
        print("t_ddmaze: %d FAILED" % len(fail))
        for f in fail:
            print("    FAIL: %s" % f)
        return 1
    print("t_ddmaze: %d layouts passed" % len(lays))
    return 0


if __name__ == "__main__":
    sys.exit(main())
