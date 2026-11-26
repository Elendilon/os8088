#!/usr/bin/env python3
"""Pin the Control Panel to its COMPACT face for a row that drives it.

SPEC.md 135.2: on a VGA or VESA desktop whose work area holds 616x408 the
panel opens WIDE (CPWIDE.DRV), and every row written before 135 clicks the
compact panel's coordinates - its 320x151 frame, its item list at CP_IX /
CP_I0Y, its pane at CP_RX. 135.13 gives such a row two honest choices: read
the wide geometry, or be pinned to the compact face. This is the second,
for the rows whose subject is a page's LOGIC (a driver's page, the Display
page's VESA row, the Keyboard page's text), which both faces run - the wide
face hosts the very same page code (135.3).

How: the first byte of the module's resident file name, `mod_f_cpw`
('CPWIDE.DRV'), is written to 0 before the first open - which is the
kernel's OWN mark for "CPWIDE.DRV was refused" (135.2): the open tests it
and takes the compact face without a lookup, exactly as a machine whose
system disk has no CPWIDE.DRV does after its first open. Nothing in the
image changes, no kernel byte is spent, and the row's disk reads are the
ones it had before 135.

A kernel with no wide face (kern_small) has no `mod_f_cpw`: nothing to do.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def compact(m, sym):
    """Pin the next Control Panel open to the compact face.

    m:   a QEMU handle with `.hmp(cmd)` (heapmap.Qmp, vidxms.Q, ethernet's
         Qemu, ...) or a MartyPC handle with `.write(linear, data)`.
    sym: name -> LINEAR address (os88sym.linear or a row's own wrapper).
    Answers True when the byte was written, False on a kernel with no wide
    face. Call it before the first open: an open already wide stays wide
    until the panel closes (135.2 step 1)."""
    try:
        lin = sym("mod_f_cpw")
    except Exception:
        return False
    if lin is None:
        return False
    if hasattr(m, "hmp"):
        import os88qemu
        os88qemu.poke(m.hmp, lin, b"\0")
    else:
        m.write(lin, b"\0")
    return True


# ctrl.inc's list geometry, mirrored (a gate that derived its coordinates
# from the thing under test would test it against itself - tests/rdup.py):
# the rows, and the SCROLL of SPEC.md 31.1.5 - nine rows fit the pane, and a
# longer list shows eight from [cp_ltop] with the two arrows in the ninth
# row's place
CP_I0Y, CP_IROWH = 6, 14
CP_LVIS, CP_LAY, CP_LAH, CP_LAX1 = 8, 118, 12, 52


def record(m, sym, ordinal):
    """List ORDINAL -> the RECORD [cp_sel] holds once it is selected: the
    statics walked against [cp_hide]'s bits, driver pages after them by
    arithmetic (ctrl.inc's cp_v2r, restated)."""
    nst = m.read(sym("cp_nst"), 1)[0]
    hide = m.read(sym("cp_hide"), 1)[0]
    if ordinal >= nst:
        return nst + bin(hide).count("1") + (ordinal - nst)
    seen = -1
    for r in range(8 + nst):
        if r < 8 and hide & (1 << r):
            continue
        seen += 1
        if seen == ordinal:
            return r
    return ordinal


def _waiter(m, wait):
    """`wait(cond, what, guest_secs)` -> bool: the caller's own (a QEMU
    handle's, tests/rdxms.py), or os88marty.until on the guest's clock."""
    if wait is not None:
        return wait
    import os88marty

    def w(cond, what, secs):
        try:
            os88marty.until(m, lambda _: cond(), what, poll=0.2, guest=secs)
            return True
        except os88marty.MartyError:
            return False
    return w


def scroll_to(m, mo, sym, x0, y0, ordinal, scrolls=False, who="cpface",
              wait=None):
    """Scroll the open COMPACT panel's list until ORDINAL is among the rows
    shown, selecting nothing; answer the row it is drawn on. The down arrow,
    one press at a time (SPEC.md 31.1.5), each confirmed off [cp_ltop].

    A list that does not scroll shows NINE rows and one that does shows
    eight, and no cell says which, so ordinal-[cp_ltop] = 8 is ambiguous: a
    press at the arrows' cell there would SELECT row 8 on a list that does
    not scroll. That row is answered as shown unless the caller knows the
    list scrolls (`scrolls`, e.g. it looked for the row and it was not
    there); past it a press is always owed."""
    wait = _waiter(m, wait)

    def top():
        return m.read(sym("cp_ltop"), 1)[0]
    for _ in range(8):
        t = top()
        row = ordinal - t
        if row < 0:
            sys.exit("%s: list ordinal %d is above the rows shown"
                     % (who, ordinal))
        if row < CP_LVIS or (row == CP_LVIS and not scrolls):
            return row
        mo.click(x0 + CP_LAX1 + 8, y0 + CP_LAY + CP_LAH // 2)
        if not wait(lambda: top() != t, "the list to scroll", 5.0):
            sys.exit("%s: the panel's list did not scroll" % who)
    sys.exit("%s: list ordinal %d was never in reach" % (who, ordinal))


def select(m, mo, sym, x0, y0, ordinal, who="cpface", wait=None):
    """Select list ORDINAL in the open COMPACT panel whose content origin is
    (x0, y0), scrolling the list to it first; answer its record.

    The driver pages follow the statics (ordinal [cp_nst] is the first), and
    a VGA desktop's list has scrolled since the Keyboard page joined the
    statics (nine shown, Display not hidden), so a driver page can be below
    the rows shown. Row 8 is a list row only while nothing scrolls: a press
    there answers by selecting, or the down arrow is what it needs. Every
    step is CONFIRMED off [cp_sel] / [cp_ltop] on the guest's clock.
    `mo` is any mouse with click(x, y); `m` a MartyPC or kern_mega handle,
    or any handle with read(linear, n) given its own `wait` (_waiter)."""
    rec = record(m, sym, ordinal)
    wait = _waiter(m, wait)

    def top():
        return m.read(sym("cp_ltop"), 1)[0]

    def sel():
        return m.read(sym("cp_sel"), 1)[0] == rec
    for _ in range(8):
        t = top()
        row = ordinal - t
        if 0 <= row <= CP_LVIS:
            mo.click(x0 + 40, y0 + CP_I0Y + row * CP_IROWH + 7)
            if wait(sel, "list ordinal %d to be selected" % ordinal,
                    10.0 if row < CP_LVIS else 3.0):
                return rec
            if row < CP_LVIS:
                sys.exit("%s: the panel's list ordinal %d was not selected"
                         % (who, ordinal))
        elif row < 0:
            sys.exit("%s: list ordinal %d is above the rows shown" % (who,
                                                                      ordinal))
        mo.click(x0 + CP_LAX1 + 8, y0 + CP_LAY + CP_LAH // 2)
        if not wait(lambda: top() != t, "the list to scroll", 5.0):
            sys.exit("%s: the panel's list did not scroll" % who)
    sys.exit("%s: list ordinal %d was never in reach" % (who, ordinal))
