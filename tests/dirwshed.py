#!/usr/bin/env python3
"""THE DIRECTORY READ-AHEAD WINDOW IS 32K A DOS PROGRAM CAN HAVE (SPEC.md 66.10.4).

§50.6.6 gave a claimant a FLOOR - "compact the disk cache, do not destroy it" -
and the DOS box is its one consumer: the Setup page shows the two figures side
by side and a check box picks between them (§96.24, §96.25).  They read the
SAME NUMBER for a release, because §66.10 rests on a sentence §18.95.7 withdrew.
`mem_cp_plan` reaches `mem_cp_drop` only from its `.pinned` arm, and the day
`MEM_P_DIRW` became movable it stopped being pinned - so a cache that can move
is moved, never dissolved, `OSAPI_MEM_AVAIL_LVL` answered identically at every
rank, and the box handed its programs 32K less than the machine had.

Four assertions, and each is a separate thing that can be missing:

  1  the cache is THERE.  A machine with no read-ahead window would pass every
     check below with both figures equal and mean nothing, so the claim is read
     out of `mem_tab` first - owner 0xFE02 - and its size is what the rest are
     measured against.
  2  the two figures DIFFER, by the cache, on the page the user reads.
  3  ...and so does what a program is actually HANDED.  [dos_akb] is banked by
     dos_run from the same slot the page asked, so a page that displayed the
     right pair while the launch used the wrong one fails here alone.
  4  and the cache really WENT - [dsk_rah_seg], the kernel's own word, read
     under each arm while the program is running.  Without this the row would
     pass on a box that asked for the bigger number and was quietly given the
     smaller.  **IT IS READ INSIDE THE BRACKET AND NOT AFTER IT**, which is
     not a nicety: the window is claimed at a MOUNT (SPEC.md 18.95.5) and the
     box re-mounts every volume on the way out of an fsx bracket, so a read
     taken once the program has exited finds the cache back and says the shed
     never happened.

**IT READS STATE AND NOT THE GLASS.**  Every number is a word in the kernel's
own table or the package's own bss; the digits on the page are a font.

THE ORDER IS LOAD-BEARING and is the row's own trap, three times over.  The
page must be read BEFORE any launch, because a DOS_CA_OFF launch SHEDS the
cache and a page read after it correctly reports two equal numbers about a
machine that no longer has one.  The launches then go KEEP first and DUMP
second, because assertion 4 is about what the DUMP left behind.  And they must
happen with the console up, because the console is the MAIN page's band
(§96.33): with Environment showing there is nothing to type at, and every
[dos_akb] reads 0 - a failure that names the arena and is really the test's own
navigation.

**THE CACHE IS `[dos_cache]` AND NOT AN ARM** (§96.36.5, §96.36.6).  It was a
CHECK BOX whose ON byte was 1 for "keep"; then the third arm turned the control
into an OS88UI_RD_SEL where 0 was `Keep the disk cache` and 1 was `Take it
too`; and it is a DROP-DOWN now, because two positions cannot say 18 KB.  This
row has had the polarity wrong once already - it failed naming a spread of -32
against a 32 KB cache, the right quantity with the wrong sign, which is the
sharpest shape a polarity bug has - so the values it pokes are named after the
list they index and not after what they mean.

Inside the OS that list is two rows, `Auto` and `Off (SLOW!)`, which are the
two the kernel can actually do: the `dirw` claim is taken at a mount and is
either standing or shed (§96.36.6).  The rungs between them are arm 1's.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dosmap                                                  # noqa: E402
import os88geom                                                # noqa: E402
import os88marty                                               # noqa: E402
import os88sym                                                 # noqa: E402
import os88ui                                                  # noqa: E402

SYS = "build/os8088-360.img"
# B: carries a `.COM` for assertion 3 - a launch is what banks [dos_akb], and
# every package on an apps disk is a `.O88`.  doscon.py's disk, for its reason.
APPS = "build/doscom360.img"
BOX = "A:/APPS/DOS.O88"
PROG = "DOSHELLO"

MEM_MAX = 32
P_DIRW = 0xFE02                  # MEM_PG_HIGH<<8 | 2 (SPEC.md 50.6)
# [dos_cache]'s rows on ARM 0's list, which are OS88UI_DR_SEL's index and not
# a tick (SPEC.md 96.36.6).  The other arm, DOS_MEM_WHOLE, is not this row's
# subject - it takes os8088 itself and never reaches [dos_akb].
CA_AUTO, CA_OFF = 0, 1
SLACK = 2                        # KB: both figures round DOWN to whole KB and
                                 # the two roundings need not land together


def fail(msg):
    print("dirwshed: FAIL: %s" % msg)
    sys.exit(1)


def dirw(m):
    """(the record's linear address, paragraphs) for the read-ahead window."""
    tab = os88sym.linear("mem_tab")
    for i in range(MEM_MAX):
        a = tab + i * os88geom.MC_SIZE
        seg = int.from_bytes(m.read(a, 2), "little")
        own = int.from_bytes(m.read(a + 4, 2), "little")
        if seg and own == P_DIRW:
            return a, int.from_bytes(m.read(a + 2, 2), "little")
    return None, 0


def main():
    for p in (SYS, APPS):
        if not os.path.exists(p):
            fail("%s is missing - `make` and `make doscom` build them" % p)

    with os88ui.boot(SYS, apps=APPS) as ui:
        m = ui.m
        win = ui.path(BOX)
        if not win:
            fail("could not launch %s" % BOX)
        os88marty.settle(m)
        dm = dosmap.package()

        # **RESOLVED PER READ AND NOT BANKED** (SPEC.md 66.6.1.2). The DOS
        # box's region is a re-homed carve and MOVES under the compactor now,
        # which on this row is guaranteed rather than possible: the whole
        # subject here is the arena claim SHEDDING the directory cache, and a
        # shed is a compaction. A base taken before the run named the bytes
        # the package used to occupy, so `inbr` read a stale byte for ever and
        # the row waited out 600 guest seconds for a program that had started.
        def pb():
            return dosmap.instance(m) << 4

        def word(name):
            return int.from_bytes(m.read(pb() + dm[name], 2), "little")

        def digits(name):
            raw = m.read(pb() + dm[name], 8).split(b"\0")[0].decode("latin-1")
            try:
                return int(raw.rstrip("KB").strip())
            except ValueError:
                fail("%s reads %r and should be digits and a KB - the page has "
                     "never been painted, or dos_mem_num did not run "
                     "(SPEC.md 96.25)" % (name, raw))

        def inbr(_=None):
            return m.read(pb() + dm["dos_inbr"], 1)[0]

        # --- 1: the cache is actually there ---------------------------------
        rec, para = dirw(m)
        if rec is None:
            fail("no MEM_P_DIRW claim in mem_tab, so there is nothing to shed "
                 "and this machine cannot answer the question. The window is "
                 "claimed at a MOUNT (SPEC.md 18.95.5) and a heap too small "
                 "for DSK_RAH_MIN slots gets none")
        cache_kb = para // 64
        print("dirwshed: MEM_P_DIRW is %d paragraphs = %d KB, MC_RLOC %04X "
              "(non-zero = MOVABLE, which is the case that broke)"
              % (para, cache_kb,
                 int.from_bytes(m.read(rec + 8, 2), "little")))

        # --- 2: the two figures the user is choosing between ----------------
        # **THERE IS ONE FIGURE ON THE PAGE NOW** (SPEC.md 96.36.3), live,
        # so the two the user is choosing between are read by SETTING the dial
        # and looking twice.  The dial is poked and the page re-entered, which
        # is what repaints it: driving the drop-down itself is
        # tests/dosmem.py's and tests/doslnk.py's subject, and re-driving it
        # here would make this row fail for somebody else's defect.
        ui.menu_pick("Program", "Setup")
        os88marty.settle(m)

        def furn(name):
            r = [int.from_bytes(m.read(pb() + dm[name] + i * 2, 2), "little")
                 for i in range(4)]
            return (r[0] + r[2]) // 2, (r[1] + r[3]) // 2

        seen = {}
        for ca in (CA_AUTO, CA_OFF):
            m.write(pb() + dm["dos_cache"], bytes([ca, 0]))
            ui.mo.click(*furn("dos_trect"))         # Return...
            os88marty.settle(m)
            ui.mo.click(*furn("dos_erect"))         # ...and back, which paints
            os88marty.settle(m)
            seen[ca] = digits("dos_marn")
        keep, take = seen[CA_AUTO], seen[CA_OFF]
        print("dirwshed: the page offers %dK with the cache on Auto and %dK "
              "with it Off" % (keep, take))
        if take - keep < cache_kb - SLACK:
            fail("the page offers %dK and %dK, a spread of %d where the cache "
                 "is %d KB. OSAPI_MEM_AVAIL_LVL is answering the same number "
                 "at both ranks, which is what mem_cp_plan does when it can "
                 "MOVE a cache instead of dissolving it (SPEC.md 66.10.4)"
                 % (keep, take, take - keep, cache_kb))
        m.write(pb() + dm["dos_cache"], bytes([CA_AUTO, 0]))

        # --- back to the console, by the button's OWN rect -------------------
        # dos_brect is composed at paint time and lives in the package's bss,
        # so this is a position resolved out of the guest rather than one
        # remembered from a screenshot (docs/WRITING-TESTS.md).
        ui.mo.click(*furn("dos_trect"))
        os88marty.settle(m)
        r = [int.from_bytes(m.read(pb() + dm["dos_trect"] + i * 2, 2), "little")
             for i in range(4)]
        if m.read(pb() + dm["dos_page"], 1)[0] != 0:
            fail("clicking Return at %r left the box on page %d, so there is "
                 "no console to type at" % (r, m.read(pb() + dm["dos_page"], 1)[0]))

        # --- 3: what a program is actually handed ---------------------------
        m.type_text("B:\n")
        os88marty.settle(m)
        got, rah = {}, {}
        for arm in (CA_AUTO, CA_OFF):
            m.write(pb() + dm["dos_cache"], bytes([arm, 0]))
            m.type_text("%s\n" % PROG)
            # **INTO THE BRACKET AND BACK OUT OF IT.** DOSHELLO waits on AH=08h
            # so its screen can be read, so a run left undismissed keeps
            # [dos_inbr] = 1 - no desktop, and the next thing typed goes to the
            # program.  The DUMP arm is also the SLOW one: it sheds the cache
            # it is claiming over, so the load that follows has no read-ahead
            # at all.
            os88marty.until(m, inbr, "%s to be running" % PROG,
                            limit=300.0, guest=600.0)
            got[arm] = word("dos_akb")
            rah[arm] = int.from_bytes(
                m.read(os88sym.linear("dsk_rah_seg"), 2), "little")
            print("dirwshed: arm %d, %s the cache -> the arena is %d KB, "
                  "[dsk_rah_seg]=%04X"
                  % (arm, "keep" if arm == CA_AUTO else "take", got[arm],
                     rah[arm]))
            m.type_text(" ")
            os88marty.until(m, lambda _=None: not inbr(), "%s to exit" % PROG,
                            limit=120.0)
            os88marty.settle(m)
        if not got[CA_AUTO] or not got[CA_OFF]:
            fail("a launch banked an arena of %d/%d KB - dos_run never got as "
                 "far as the claim, so nothing here is about memory"
                 % (got[CA_AUTO], got[CA_OFF]))
        if got[CA_OFF] - got[CA_AUTO] < cache_kb - SLACK:
            fail("a launch gets %d KB with the cache kept and %d KB with it "
                 "taken, a spread of %d where the cache is %d KB. dos_run asks "
                 "the same slot the page did (SPEC.md 96.24)"
                 % (got[CA_AUTO], got[CA_OFF],
                    got[CA_OFF] - got[CA_AUTO], cache_kb))
        if (abs(got[CA_AUTO] - keep) > SLACK
                or abs(got[CA_OFF] - take) > SLACK):
            fail("the page promised %dK/%dK and the launch took %dK/%dK - the "
                 "figure SHOWN is not the figure the program GETS (SPEC.md "
                 "96.25.1)"
                 % (keep, take, got[CA_AUTO], got[CA_OFF]))

        # --- 4: ...and the cache really went, and only under the arm that
        #        asked for it -------------------------------------------------
        if rah[CA_OFF] != 0:
            fail("the box asked for %d KB at MEM_LVL_TOP and [dsk_rah_seg] was "
                 "still %04X while the program ran, so the claim was satisfied "
                 "without the cache - the arena figure and the arena disagree"
                 % (got[CA_OFF], rah[CA_OFF]))
        if rah[CA_AUTO] == 0:
            fail("[dsk_rah_seg] was already 0 while the DOS_CA_AUTO program "
                 "ran, so the cache went for an arm that asked to keep it. "
                 "That is SPEC.md 50.6.6's floor - `compact the disk cache, do "
                 "not destroy it` - and the two figures above then describe a "
                 "machine with one cache between them")

    print("dirwshed: ok - the window is %d KB, the page offers it, a launch "
          "collects it, and only the arm that asked for it lost the cache"
          % cache_kb)


if __name__ == "__main__":
    main()
