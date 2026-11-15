#!/usr/bin/env python3
"""BONANZA's experiment on MartyPC's CGA (SPEC.md 128.21): FINE's one-line
vertical scroll by two 6845 frames a refresh, and SPLIT's frames.

    make bonanzadisk && python3 tests/bonanza_fine.py [--red nohook]

A play is launched in FINE SPLIT with the ball left alone (no autopilot, no
key), so the camera rests.  ASSERTED:

  1. FINE starts: [bz_hon] 1 and [bz_ffail] 0 within 2 s of the bracket.
  2. The clock: [bz_subs], the virtual sub-tick, advances 54.6 times a guest
     second (within 1%) - FASTTICK's rate, rebuilt from the hook (128.21.3).
  3. The glass, both phases: the camera's top line poked to 2 R0 + 1 (R0 + 1
     with phase 1) and back (LATTICE at rest keeps it), the committed phase [bz_hph] follows,
     and the window - found by matching the ring's decode at [bz_S] against
     MartyPC's whole raster (the 912 x 262 debug aperture, line 0 the sync's
     start) - sits at line 38 + P.  P = 0 is mode 4's own place.
  4. The refresh: 262 lines (79,648 clocks) a frame, by the card's frame
     counter over 120 frames of each phase, within 0.1%.
  5. SPLIT: MILL's shipped demo through D in GLIDE and in FINE SPLIT, stopped
     at every bz_presented: under FINE SPLIT no frame writes both a row
     (bz_row, not a full write) and a column (bz_col) - and GLIDE must write
     some (the control), FINE SPLIT both rows and columns.  Under FINE
     SPLIT also: the card's refresh 262 lines over the whole demo (within
     0.2%), no lost period and no failed start, W1 never later than 12 lines
     (its window closes 13 lines after it is due), and the phase changing.
     Each leg's frames over 1.5 refreshes REPORTED (the presents' cycle gaps).

--red now1 patches bz_hook's W1 to a bare RET once FINE runs (frame A's
registers never written, nothing re-timed): checks 3 and 4 must fail.
"""
import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import bonanza_ring as R       # noqa: E402

CLK = 4772727.0
FRAME = 262 * 304


def w1_offset(sym):
    """bz_hook.w1's offset from bz_hook, out of the build's listing"""
    import re
    lst = open(R.at("build/bonanza.lst")).read().split("\n")
    hook = sym["bz_hook"]
    i = next(k for k, ln in enumerate(lst) if re.search(r"^\s*\d+\s+bz_hook:", ln) or ln.rstrip().endswith("bz_hook:"))
    j = next(k for k in range(i, len(lst)) if lst[k].rstrip().endswith(".w1:"))
    for ln in lst[j + 1:j + 6]:
        mm = re.match(r"^\s*\d+\s+([0-9A-F]{8})\s+[0-9A-F]", ln)
        if mm:
            return int(mm.group(1), 16) - hook
    raise AssertionError("bz_hook.w1 not in the listing")


def field(g):
    w, h, d = g.m.fbuf(aperture=3)
    assert (w, h) == (912, 262), ("the debug aperture is not the whole CGA raster", w, h)
    return w, h, d


def window_y(g):
    """-> the field line the window's first line sits on: the ring's decode at
    bz_S matched black/not-black against the raster, 640 hdots from x 192"""
    exp = g.decode(g.w("bz_S"))
    w, h, d = field(g)
    best = None
    for y0 in range(20, 60):
        bad = 0
        for y in range(0, 200, 3):
            row = (y0 + y) * w
            for x in range(0, 320, 4):
                o = (row + 192 + 2 * x) * 3
                bad += (d[o:o + 3] == b"\0\0\0") != (exp[y][x] == 0)
        if best is None or bad < best[0]:
            best = (bad, y0)
    return best[1] if best[0] < 40 else None


def period(g, frames=120):
    m = g.m
    c0, f0 = R.cycles(m), m.cards()[0]["frames"]
    m.advance(frames=frames)
    return (R.cycles(m) - c0) / (m.cards()[0]["frames"] - f0)


def split_leg(g, fails):
    """D, frame by frame at bz_presented: -> (frames, with rows, with a column,
    with both, full writes, SPLIT's cuts, missed refreshes)"""
    m = g.m
    m.pause()
    g.put("bz_nsplit", 0)
    m.run()
    g.key("KeyD")
    M.until(m, lambda _: g.b("bz_fs") == 1, "D's bracket", guest=60)
    m.pause()
    m.breakpoints([{"type": "exec", "addr": g.a("bz_presented")}])
    n = both = rows = cols = full = flips = 0
    last = (g.w("bz_nrow"), g.w("bz_ncol"), g.w("bz_nfull"))
    c_last = None
    miss = 0
    ph = g.b("bz_hph")
    c0, f0 = R.cycles(m), m.cards()[0]["frames"]
    while g.b("bz_fs") == 1:
        mark = m.go()
        if not m.wait_stop(20.0, since=mark):
            m.pause()
            if g.b("bz_fs") == 1:
                r = m.regs()
                fails.append("D stopped presenting after %d frames (CS:IP %04X:%04X)" % (n, r.get("cs", 0), r.get("ip", 0)))
            break
        c = R.cycles(m)
        if c_last is not None and c - c_last > 1.5 * FRAME:
            miss += 1
        c_last = c
        p2 = g.b("bz_hph")
        flips += p2 != ph
        ph = p2
        cur = (g.w("bz_nrow"), g.w("bz_ncol"), g.w("bz_nfull"))
        dr, dc, df = [(x - y) & 0xFFFF for x, y in zip(cur, last)]
        last = cur
        n += 1
        if df:
            full += 1
            continue
        rows += dr > 0
        cols += dc > 0
        both += dr > 0 and dc > 0
    per = (R.cycles(m) - c0) / max(1, m.cards()[0]["frames"] - f0)
    extra = dict(flips=flips, refresh=per, hbad=g.w("bz_nhbad"), ffail=g.b("bz_ffail"), hlate=g.w("bz_hlate"))
    m.breakpoints([])
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 0 and g.w("bz_cseg") == 0, "D to end", guest=60)
    return (n, rows, cols, both, full, g.w("bz_nsplit"), miss, extra)


def herc(sym, fails):
    """6. The Hercules: no FINE (bz_nofine; C skips modes 2 and 4), and SPLIT
    on MILL's demo writes no frame of a row and a column."""
    import bonanza_perf as P
    with os88ui.boot(R.at("build/os8088-360.img"), apps=R.at("build/bonanza360.img"),
                     machine=R.MACHINE["herc"]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, "herc", sym, live=True)
        ui.settle()
        m = g.m
        m.pause()
        g.putb("bz_cmode", 1)                   # TRICKLE: C's next on a Hercules is SPLIT, not FINE
        m.run()
        M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)
        g.key("KeyC")
        M.until(m, lambda _: g.b("bz_cmode") != 1, "C to move the camera mode", guest=5)
        cm = g.b("bz_cmode")
        print("bonanza_fine (herc): C from TRICKLE -> mode %d (SPLIT is 3)" % cm)
        if cm != 3:
            fails.append("Hercules: C from TRICKLE gave mode %d, not SPLIT" % cm)
        P.set_snd(g, False)
        P.load_demo(g, R.CRS_K["mill"])
        m.pause()
        g.putb("bz_cmode", 3)
        m.run()
        M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)
        r = split_leg(g, fails)
        print("bonanza_fine (herc): MILL's demo in SPLIT: %d frames, %d with rows, %d with a column, %d with both; "
              "SPLIT cut %d; %d frames over 1.5 refreshes; nofine %d, FINE on %d" % (
                  r[0], r[1], r[2], r[3], r[5], r[6], g.b("bz_nofine"), g.b("bz_hon")), flush=True)
        if r[3]:
            fails.append("Hercules SPLIT: %d frames wrote a row and a column" % r[3])
        if not r[1] or not r[2]:
            fails.append("Hercules SPLIT moved no row or no column: untested")
        if g.b("bz_nofine") != 1:
            fails.append("Hercules: bz_nofine is not set")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--red", choices=["now1"])
    ap.add_argument("--only", choices=["cga", "herc"])
    a = ap.parse_args()
    sym = R.symbols()
    fails = []
    if a.only == "herc":
        herc(sym, fails)
        print("bonanza_fine: %s" % ("FAIL\n  " + "\n  ".join(fails) if fails else "PASS"))
        return 1 if fails else 0
    with os88ui.boot(R.at("build/os8088-360.img"), apps=R.at("build/bonanza360.img"),
                     machine=R.MACHINE["cga"]) as ui:
        ui.open_drive("B")
        ui.open("BONANZA.O88")
        g = R.Bz(ui, "cga", sym, live=True)
        ui.settle()
        m = g.m
        m.pause()
        g.putb("bz_cmode", 4)                   # FINE SPLIT
        g.putb("bz_apilot", 0)
        m.run()
        g.key("Enter")
        M.until(m, lambda _: g.b("bz_fs") == 1, "the bracket", guest=60)
        M.until(m, lambda _: g.b("bz_hon") == 1 or g.b("bz_ffail"), "FINE to start", guest=2)
        print("bonanza_fine: FINE on: hon %d, ffail %d" % (g.b("bz_hon"), g.b("bz_ffail")))
        if g.b("bz_hon") != 1 or g.b("bz_ffail"):
            fails.append("FINE did not start")
        m.advance(frames=60)
        # 2. the virtual sub-tick
        m.pause()
        c0, s0 = R.cycles(m), g.w("bz_subs")
        m.advance(frames=300)
        rate = ((g.w("bz_subs") - s0) & 0xFFFF) / ((R.cycles(m) - c0) / CLK)
        print("bonanza_fine: the virtual sub-tick %.3f Hz (FASTTICK's 54.620)" % rate)
        if abs(rate - 54.620) > 0.55:
            fails.append("the virtual sub-tick runs at %.3f Hz" % rate)
        if a.red == "now1":
            m.pause()
            m.write(g.a("bz_hook") + w1_offset(sym), b"\xc3")
            m.run()
        # 3, 4. both phases, the camera's line poked where the camera reads it (bz_t0)
        seen = {}
        for want in (1, 0, 1, 0):
            m.pause()
            m.breakpoints([{"type": "exec", "addr": g.a("bz_t0")}])
            mark = m.go()
            assert m.wait_stop(30.0, since=mark), "bz_t0 never came"
            m.breakpoints([])
            r0 = g.w("bz_R0") - (1 if want == 0 and seen else 0)
            g.put("bz_C", 2 * r0 + want)        # P = 1: R0 + 1 shown one line down
            m.run()
            m.advance(frames=8)
            ph, y0 = g.b("bz_hph"), window_y(g)
            per = period(g)
            print("bonanza_fine: phase asked %d, committed %d: window at line %s (38 + P = %d), "
                  "refresh %.1f clk (%.2f lines)" % (want, ph, y0, 38 + ph, per, per / 304))
            seen[want] = (ph, y0)
            if ph != want:
                fails.append("phase %d asked, %d committed" % (want, ph))
            if y0 is None:
                fails.append("phase %d: the window is on the glass at no line 20 - 59" % ph)
            elif y0 != 38 + ph:
                fails.append("phase %d: the window at line %d" % (ph, y0))
            if abs(per - FRAME) > FRAME * 0.001:
                fails.append("phase %d: the refresh is %.1f clk" % (ph, per))
        m.run()
        g.key("Escape")
        M.until(m, lambda _: g.b("bz_fs") == 0, "the play to end", guest=30)
        M.until(m, lambda _: g.w("bz_cseg") == 0, "its parts dropped", guest=30)
        # 5. SPLIT: MILL's demo through D, GLIDE (the control) and FINE SPLIT
        import bonanza_perf as P
        res = {}
        P.set_snd(g, False)                     # (the perf row's A/B: sound off, like for like)
        for mode in (0, 4):
            P.load_demo(g, R.CRS_K["mill"])
            m.pause()
            g.putb("bz_cmode", mode)
            m.run()
            M.until(m, lambda _: g.b("bz_dkk") == 0, "the held-key guard", guest=5)
            res[mode] = split_leg(g, fails)
            print("bonanza_fine: MILL's demo in %s: %d frames, %d with rows, %d with a column, %d with both, "
                  "%d full writes; SPLIT cut %d vertical steps; %d frames over 1.5 refreshes; %s" % (
                      ("GLIDE", "", "", "", "FINE SPLIT")[mode], *res[mode][:7],
                      ", ".join("%s %s" % (k, ("%.1f" % v) if isinstance(v, float) else v)
                                for k, v in res[mode][7].items())), flush=True)
        if res[4][3]:
            fails.append("FINE SPLIT: %d frames wrote a row and a column" % res[4][3])
        x = res[4][7]
        if abs(x["refresh"] - FRAME) > FRAME * 0.002:
            fails.append("FINE SPLIT's demo: a refresh of %.1f clk, not 262 lines" % x["refresh"])
        if x["hbad"] or x["ffail"]:
            fails.append("FINE SPLIT's demo: %d lost periods, %d failed starts" % (x["hbad"], x["ffail"]))
        if x["hlate"] > 12 * 76:
            fails.append("FINE SPLIT's demo: W1 ran %d counts late, past its window (line 260)" % x["hlate"])
        if not x["flips"]:
            fails.append("FINE SPLIT's demo never changed phase: the one-line step untested")
        if not res[0][3]:
            fails.append("GLIDE wrote no frame of both on MILL: the control does not show SPLIT can fail")
        if not res[4][1] or not res[4][2]:
            fails.append("FINE SPLIT moved no row or no column: untested")
    if not a.red and a.only != "cga":
        herc(sym, fails)
    if a.red:
        if fails:
            print("bonanza_fine --red %s: went red as it must (%s)" % (a.red, "; ".join(fails)))
            return 0
        print("bonanza_fine --red %s: FAIL - the row passed against a broken package" % a.red)
        return 1
    if fails:
        print("bonanza_fine: FAIL\n  " + "\n  ".join(fails))
        return 1
    print("bonanza_fine: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
