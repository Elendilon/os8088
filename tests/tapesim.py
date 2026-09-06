#!/usr/bin/env python3
"""docs/plans/CASSETTE-PLAN.md wave 5 - TAPE.O88, driven end to end.

    make tapesimtest && python3 tests/tapesim.py

**THE ROUND TRIP IS THE TEST**, and it is a round trip between two
implementations rather than one program agreeing with itself: the fixture's
`ckfile` is computed HERE with `tools/os88tape.py`'s CRC-16 - the host
reference codec, written from SPEC.md 88.4 rather than from the assembly - and
the machine has to arrive at the same word over the same bytes, with the same
`nrec` and the same `lastblk`. That matters more here than anywhere else in
the tree, because **no instrument in this project can execute a cassette read
at all** (SPEC.md 88.11): two independent readers agreeing about the format is
most of the verification it is going to get before it meets a deck.

WHAT MAKES IT RUNNABLE WITH NO CASSETTE. `apps/tape/tapexfr.inc` has two arms.
`-DTAPE_FAKE` puts a memory buffer behind `tp_xfer` with the ROM's own
semantics - a short read CONSUMES the whole record, a read past the end
answers AH = 04 - and everything above that seam is the shipping code: the
layout off OSAPI_WM_GEOM, the buttons, the greying, the state machine, the
coast, the format and all 29 of SPEC.md 88.9's checks. The real `int 15h`
bracket is wave 6 and is NOT exercised here; nothing in this file should be
read as a claim about it.

THE SEQUENCE, one operation each:

  1. launch, and the window comes up idle with the layout computed
  2. Compress OFF, so the fixture stays 2,400 bytes and the transfer is FOUR
     records rather than one - the multi-record path is the whole point of
     the progress bar, the per-record repaint and Stop
  3. Choose... -> the Standard File dialog -> TAPEDATA.TXT
  4. Go -> the cue-confirm -> a SAVE. `ckfile`, `nrec` and `lastblk` are
     checked against the host codec's
  5. Verify -> the read path with the commit replaced by a comparison, which
     is what proves the tape holds the file: every block, every preamble
     field, `ckfile` over the assembled payload, then `ckfile` against a fresh
     CRC over the file as it sits on disk
  6. Load -> the same read path, committing this time, through the "replace
     the file?" question
  7. Catalog -> the SCAN, which is 256-byte reads that name what goes past.
     Never with CX > 256: a larger read consumes and CRC-checks a whole
     record you may not want
  8. ...and one more Save with Compress ON, which is the only path that
     reaches OSAPI_COMPRESS and the 'CZ' wrapper (SPEC.md 88.7 step 4)

HOW TO MAKE IT FAIL ON PURPOSE (docs/WRITING-TESTS.md 1): change `TP_CRC_POLY`
in tapefmt.inc and step 4 goes red on `ckfile` while every other step still
passes; delete the `cmp [es:TPB_CKFILE], ax` in `tp_body_parse` and nothing
here notices, which is why `tests/tapehostile` is wave 5's other row and not
this one; make `tp_geom` round DOWN and `nrec` disagrees with the host; and
take the `add [tp_fpos], dx` out of the fake transport's read and step 5 reads
the header record over and over until the scan cap stops it.
"""

import os
import re
import subprocess
import sys
import time
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
sys.path.insert(0, HERE)

import os88marty as M                                        # noqa: E402
import os88tape                                              # noqa: E402
import os88ui                                                # noqa: E402
from os88geom import WIN_SIZE, W_SEG, FD_BX1, FD_BX2, FD_BY0, FD_BY1, \
    FD_BH, FD_LX1, FD_LX2, FD_ROW0, FD_ROWH                  # noqa: E402

MACHINE = sys.argv[1] if len(sys.argv) > 1 else "os8088_5150_cga_gla"
# The GLaBIOS twin by name: the IBM ROM is not in this tree, and a row
# whose machine depends on which files happen to be lying about is a row
# whose result cannot be compared with anybody else's. Nothing here wants
# the period ROM - the transport under test is a memory buffer.
IMG = "build/os8088-360.img"
APPS = "build/tapesim360.img"
BIN = "build/tapesim.bin"
SRC = os.path.join(HERE, "..", "apps", "tape", "tape.asm")
FIXTURE = "TAPEDATA.TXT"
TITLE_H = 18

# the package's own constants, mirrored - and every one of them is READ BACK
# out of the guest below, so a value that drifts here fails loudly rather than
# quietly agreeing with itself
TS_IDLE, TS_CUE, TS_RUN, TS_DONE, TS_ERR = 0, 1, 2, 3, 4
TM_SAVE, TM_LOAD, TM_CAT = 0, 1, 2
TP_HW_OK = 0
TP_F_CZ = 0x01
B_CHOOSE, B_GO, B_VERIFY, B_STOP, T_SAVE, T_LOAD, T_CAT, T_ZIP = range(1, 9)
# apps/os88ui.inc's alert: OS88UI_ABW / ABG / ABH / ABTNY
A_BW, A_BG, A_BH, A_BTNY = 72, 12, 13, 46

fails = []


def say(s):
    print(s, flush=True)


def check(name, cond, note=""):
    say("  %s %-38s %s" % ("ok  " if cond else "FAIL", name, note))
    if not cond:
        fails.append(name)


def fixture_bytes():
    """The same 2,400 bytes the Makefile writes onto the scratch image.

    ONE generator, quoted in two places, and the Makefile's copy is the one
    that lands on the disk - so a mismatch here is a mismatch the guest sees
    as a different file and every checksum below goes red at once.
    """
    return b"".join(b"os8088 tape fixture line %03d\r\n" % i for i in range(80))


# =============================================================================
# the package's variables, by name
# =============================================================================
def symbols(names):
    """label -> offset in the package image, out of a NASM listing.

    It re-assembles the source and REFUSES unless the result is byte-identical
    to the `build/tapesim.bin` under test - `tools/os88sym.py`'s discipline one
    layer out. A listing that describes a different binary is worse than no
    listing: every offset below would be plausible and wrong.
    """
    want = set(names)
    with tempfile.TemporaryDirectory() as d:
        lst = os.path.join(d, "tape.lst")
        out = os.path.join(d, "tape.bin")
        r = subprocess.run(["nasm", "-f", "bin", "-w+error", "-I", "apps/",
                            "-I", "apps/tape/", "-DTAPE_FAKE",
                            "-l", lst, "-o", out, "apps/tape/tape.asm"],
                           capture_output=True)
        if r.returncode:
            sys.exit("tapesim: the source no longer assembles:\n"
                     + r.stderr.decode("latin-1"))
        if open(out, "rb").read() != open(BIN, "rb").read():
            sys.exit("tapesim: %s is not what apps/tape/tape.asm assembles to "
                     "- run `make tapesimtest` first" % BIN)
        text = open(lst, "r", errors="replace").read()
    syms = {}
    for line in text.splitlines():
        m = re.match(r"^\s*\d+\s+([0-9A-F]{8})\s", line)
        if not m:
            continue
        for hit in re.finditer(r"(?:^|\s)([A-Za-z_][\w]*):", line):
            n = hit.group(1)
            if n in want and n not in syms:
                syms[n] = int(m.group(1), 16)
    missing = want - set(syms)
    if missing:
        sys.exit("tapesim: no address for %s" % ", ".join(sorted(missing)))
    return syms


class Pkg(object):
    """One live TAPE instance, read by variable name."""

    def __init__(self, m, seg, syms):
        self.m, self.seg, self.syms = m, seg, syms

    def raw(self, name, n):
        return bytes(self.m.readseg(self.seg, self.syms[name], n))

    def w(self, name):
        b = self.raw(name, 2)
        return b[0] | (b[1] << 8)

    def b(self, name):
        return self.raw(name, 1)[0]

    def s(self, name, n=40):
        return self.raw(name, n).split(b"\0")[0].decode("latin-1")

    def rect(self, i):
        b = self.raw("tp_rects", 8 * 8)
        return [b[i * 8 + k * 2] | (b[i * 8 + k * 2 + 1] << 8)
                for k in range(4)]

    def centre(self, i):
        x1, y1, x2, y2 = self.rect(i - 1)
        return (x1 + x2) // 2, (y1 + y2) // 2


def main():
    for p in (IMG, APPS, BIN):
        if not os.path.exists(p):
            sys.exit("tapesim: %s is missing - `make tapesimtest` first" % p)

    data = fixture_bytes()
    want_ck = os88tape.crc16(data)
    want_nrec, want_lastblk, cap = os88tape.geometry(len(data), 4)
    say("fixture: %d bytes, ckfile %04X, %d body records, lastblk %d"
        % (len(data), want_ck, want_nrec, want_lastblk))

    syms = symbols(["tp_win", "tp_down", "tp_msg", "tp_step", "tp_nrecs",
                    "tp_cellip", "tp_state", "tp_run", "tp_mode", "tp_phase",
                    "tp_stop", "tp_wantz", "tp_name", "tp_size", "tp_usize",
                    "tp_ckfile", "tp_nrec", "tp_lastblk", "tp_flags",
                    "tp_rects", "tp_hw", "tp_total", "tp_cw", "tp_ch",
                    "tp_compact", "tp_bt_y2", "tp_oy", "tp_s_vok",
                    "os88ui_awin"])

    with os88ui.boot(IMG, apps=APPS, machine=MACHINE) as ui:
        m, mo = ui.m, ui.mo
        w = ui.path("B:/TAPESIM.O88")
        w = ui.wait_window("Tape")
        seg = int.from_bytes(m.read(m.sym("wm_wins") + w.i * WIN_SIZE + W_SEG,
                                    2), "little")
        p = Pkg(m, seg, syms)
        # **THE WINDOW RECORD EXISTS BEFORE THE FIRST W_PAINT HAS RUN**, and
        # the layout is computed IN the paint (SPEC.md 88.8: every rect comes
        # from OSAPI_WM_GEOM at paint time, never from a table). So a read
        # taken the instant `wait_window` returns finds a layout of zeroes and
        # reports the geometry broken.
        M.until(m, lambda _: p.w("tp_cw") != 0, "the first paint",
                poll=0.2, guest=30.0)

        # --- 1. the window is up, detected, idle, and LAID OUT --------------
        say("--- the window ---")
        check("hardware gate", p.b("tp_hw") == TP_HW_OK,
              "[tp_hw]=%d" % p.b("tp_hw"))
        check("idle", p.b("tp_state") == TS_IDLE)
        check("mode is Save", p.b("tp_mode") == TM_SAVE)
        cw, ch = p.w("tp_cw"), p.w("tp_ch")
        check("geometry came from WM_GEOM", cw == w.w - 2 and ch == w.h - 19,
              "content %dx%d of a %dx%d frame" % (cw, ch, w.w, w.h))
        check("CGA folds the footer away", p.b("tp_compact") == 1,
              "[tp_compact]=%d at %d rows" % (p.b("tp_compact"), ch))
        bot = p.w("tp_bt_y2") - p.w("tp_oy")
        check("the buttons are inside the content", bot < ch,
              "button row ends at row %d of %d" % (bot, ch))
        r = p.rect(B_GO - 1)
        check("Go's rect is on the glass",
              w.x < r[0] < r[2] < w.x + w.w and w.y < r[1] < r[3] < w.y + w.h,
              "%r" % (r,))

        def finish(what, guest=240.0):
            """Run the operation to its end, answering every question on the
            way with the DEFAULT.

            The cue-confirm and the "replace the file?" question are the same
            shape, so they are answered by one loop rather than by a script
            that has to know how many alerts this leg puts up - which is a
            property of the DISK (is there already a file of that name?) and
            not of the test. TS_ERR ends the wait too: a refusal is an ANSWER,
            and waiting out four guest minutes for one hides the sentence that
            says what went wrong.
            """
            seen = {"was": None, "ran": False}

            def cond(_):
                st = (p.b("tp_state"), p.b("tp_run"), p.w("tp_step"),
                      p.w("os88ui_awin") != 0)
                if st[0] in (TS_CUE, TS_RUN):
                    seen["ran"] = True
                if st != seen["was"]:
                    seen["was"] = st
                    say("       state=%d run=%d step=%d%s"
                        % (st[0], st[1], st[2], "  [alert]" if st[3] else ""))
                if st[3]:
                    # Click, then WAIT FOR IT TO GO, inside the poll. A latch
                    # ("I have clicked this one") is the obvious spelling and
                    # it is wrong here: a whole four-record load runs in about
                    # half a second of HOST time, so the poll can miss the gap
                    # between the cue-confirm closing and the replace question
                    # opening entirely - and the latch then never resets and
                    # the second question is never answered. Re-clicking
                    # blindly is worse: the alert's buttons sit over our own
                    # window's controls.
                    mo.click(*alert_button(0))
                    for _ in range(40):
                        if p.w("os88ui_awin") == 0:
                            break
                        time.sleep(0.1)
                    return False
                if p.b("tp_state") == TS_IDLE:
                    return True         # nothing ever started: say so HERE,
                                        # rather than spending four guest
                                        # minutes finding out
                return p.b("tp_state") in (TS_DONE, TS_ERR)
            M.until(m, cond, what, poll=0.4, guest=guest)
            M.settle(m, quiet=0.6, stable=2)
            if not seen["ran"]:
                # NOTHING EVER STARTED, and the state is whatever the last
                # operation left - so the wait returned at once and every
                # assertion after it would be about the PREVIOUS leg. A green
                # row that tests nothing is worse than no row.
                check(what, False, "the operation never started: %r" % pmsg(p))
            elif p.b("tp_state") != TS_DONE:
                check(what, False, "state %d, %r"
                      % (p.b("tp_state"), pmsg(p)))

        def press(i):
            mo.click(*p.centre(i))
            M.settle(m, quiet=0.6, stable=2)

        def alert_button(which, n=2):
            """The alert's button `which` of `n` - apps/os88ui.inc's formula,
            not a measured layout."""
            ptr = p.w("os88ui_awin")
            if not ptr:
                raise RuntimeError("no alert is up")
            b = bytes(m.readseg(M.KERNEL_SEG, ptr, 12))
            ax, ay, aw = (b[2] | b[3] << 8), (b[4] | b[5] << 8), \
                         (b[6] | b[7] << 8)
            row = n * (A_BW + A_BG) - A_BG
            left = ax + (aw - row) // 2
            x1 = left + which * (A_BW + A_BG)
            y1 = ay + TITLE_H + A_BTNY
            return x1 + A_BW // 2, y1 + A_BH // 2

        # --- 2. Compress OFF ------------------------------------------------
        say("--- the controls ---")
        check("Compress is on by default", p.b("tp_wantz") == 1)
        press(T_ZIP)
        check("...and the check toggles it", p.b("tp_wantz") == 0)
        press(T_CAT)
        check("a mode radio moves the mode", p.b("tp_mode") == TM_CAT)
        press(T_SAVE)
        check("...and back", p.b("tp_mode") == TM_SAVE)

        # --- 3. Choose... ---------------------------------------------------
        say("--- Choose... (SPEC.md 38) ---")
        got = choose(ui, p, m, mo, press)
        check("the dialog named the file", got == FIXTURE, "[tp_name]=%r" % got)
        check("...and its RAW size", p.w("tp_size") == len(data),
              "[tp_size]=%d" % p.w("tp_size"))

        # --- 4. a SAVE ------------------------------------------------------
        say("--- Save ---")
        press(B_GO)
        check("the cue-confirm came up", p.b("tp_state") == TS_CUE,
              "[tp_state]=%d, %r" % (p.b("tp_state"), pmsg(p)))
        finish("the save to finish")
        check("nrec agrees with the host codec",
              p.b("tp_nrec") == want_nrec,
              "guest %d, os88tape %d" % (p.b("tp_nrec"), want_nrec))
        check("lastblk agrees with the host codec",
              p.b("tp_lastblk") == want_lastblk,
              "guest %d, os88tape %d" % (p.b("tp_lastblk"), want_lastblk))
        check("ckfile agrees with the host codec",
              p.w("tp_ckfile") == want_ck,
              "guest %04X, os88tape %04X" % (p.w("tp_ckfile"), want_ck))
        check("every record went", p.w("tp_step") == want_nrec + 1,
              "[tp_step]=%d" % p.w("tp_step"))
        check("the bar had one cell per record",
              p.w("tp_nrecs") == want_nrec + 1)
        check("...and it says Verify rather than 'written'",
              "Verify" in pmsg(p), pmsg(p))

        # --- 5. Verify ------------------------------------------------------
        say("--- Verify ---")
        press(B_VERIFY)
        finish("the verify to finish")
        check("the tape holds the file",
              p.w("tp_msg") == syms["tp_s_vok"],
              "[tp_msg] -> %r" % pmsg(p))
        check("...having read every record back",
              p.w("tp_total") == len(data),
              "[tp_total]=%d" % p.w("tp_total"))

        # --- 6. a LOAD, through the replace question ------------------------
        say("--- Load ---")
        press(T_LOAD)
        check("the mode moved", p.b("tp_mode") == TM_LOAD)
        press(B_GO)
        finish("the load to finish")
        check("the whole payload came back",
              p.w("tp_total") == len(data), "[tp_total]=%d" % p.w("tp_total"))
        check("the name came off the TAPE", p.s("tp_name", 13) == FIXTURE,
              "[tp_name]=%r" % p.s("tp_name", 13))
        check("ckfile still agrees", p.w("tp_ckfile") == want_ck)
        check("the file was written", "written" in pmsg(p), pmsg(p))

        # --- 7. Catalog: the scan, which NAMES what goes past ---------------
        say("--- Catalog (SPEC.md 88.8.2) ---")
        press(T_CAT)
        check("the mode moved", p.b("tp_mode") == TM_CAT)
        press(B_GO)
        finish("the catalog to finish")
        check("every record on the tape went past",
              p.w("tp_step") == want_nrec + 1, "[tp_step]=%d" % p.w("tp_step"))
        check("...and it said so", "Catalog" in pmsg(p), pmsg(p))

        # --- 8. ...and the compressed leg ----------------------------------
        say("--- Save, compressed (SPEC.md 88.7) ---")
        press(T_SAVE)
        check("the mode is Save again", p.b("tp_mode") == TM_SAVE)
        # A READ forgets the chosen file - a Load takes its name off the tape
        # and a Catalog has no file at all - so Go is correctly greyed until
        # one is chosen again. Choosing here is not ceremony: it is the state
        # the package is honestly in.
        check("the catalog cleared the chosen file", p.s("tp_name", 13) == "",
              "[tp_name]=%r" % p.s("tp_name", 13))
        check("...and choosing again names it",
              choose(ui, p, m, mo, press) == FIXTURE)
        press(T_ZIP)
        check("Compress is back on", p.b("tp_wantz") == 1)
        press(B_GO)
        finish("the compressed save")
        check("the payload is a 'CZ' container",
              (p.b("tp_flags") & TP_F_CZ) != 0,
              "[tp_flags]=%02X" % p.b("tp_flags"))
        check("...and it got smaller", 0 < p.w("tp_size") < len(data),
              "%d bytes from %d" % (p.w("tp_size"), len(data)))
        check("usize still names the original",
              p.w("tp_usize") == len(data), "[tp_usize]=%d" % p.w("tp_usize"))

    say("")
    for f in fails:
        say("  FAIL: " + f)
    say("tapesim: %s" % ("FAILED" if fails else "ok"))
    return 1 if fails else 0


def pmsg(p):
    """Whatever [tp_msg] is pointing at, as text."""
    ptr = p.w("tp_msg")
    if not ptr:
        return ""
    return bytes(p.m.readseg(p.seg, ptr, 60)).split(b"\0")[0].decode("latin-1")


def choose(ui, p, m, mo, press):
    """Choose... -> the Standard File dialog -> the fixture.

    The row is found by ASKING THE PACKAGE what it got rather than by trusting
    a sort order: click a row, commit, read [tp_name], and try the next one if
    it is not the file wanted. A remembered row index is exactly the
    hand-rolled coordinate docs/WRITING-TESTS.md 1 is about - the listing gains
    an entry the day this disk does.
    """
    for row in range(6):
        press(B_CHOOSE)
        M.until(m, lambda _: dlg_rect(ui) is not None, "the file dialog",
                poll=0.2, guest=30.0)
        d = dlg_rect(ui)
        cx, cy = d[0] + 1, d[1] + TITLE_H
        mo.click(cx + (FD_LX1 + FD_LX2) // 2,
                 cy + FD_ROW0 + row * FD_ROWH + FD_ROWH // 2)
        M.settle(m, quiet=0.6, stable=2)
        mo.click(cx + (FD_BX1 + FD_BX2) // 2, cy + FD_BY0 + FD_BH // 2)
        M.settle(m, quiet=0.6, stable=2)
        got = p.s("tp_name", 13)
        if got == FIXTURE:
            return got
        if dlg_rect(ui) is not None:            # still up: nothing was picked
            mo.click(cx + (FD_BX1 + FD_BX2) // 2, cy + FD_BY1 + FD_BH // 2)
            M.settle(m, quiet=0.6, stable=2)
    return p.s("tp_name", 13)


def dlg_rect(ui):
    """The Standard File dialog's frame, or None.

    It is found by its TITLE POINTER and not by the string: W_TITLE is a near
    offset into KERNEL_SEG, so `fdlg_s_topen`'s own address identifies the
    window with nothing to keep in step (tests/fdlgdrop.py's `titled`).
    """
    m = ui.m
    want = m.sym("fdlg_s_topen") - (M.KERNEL_SEG << 4)
    raw = m.read(m.sym("wm_wins"), WIN_SIZE * 12)
    for i in range(12):
        b = i * WIN_SIZE
        if not (raw[b] | raw[b + 1] << 8) & 2:
            continue
        if (raw[b + 10] | raw[b + 11] << 8) != want:
            continue
        return tuple(raw[b + o] | raw[b + o + 1] << 8 for o in (2, 4, 6, 8))
    return None


if __name__ == "__main__":
    sys.exit(main())
