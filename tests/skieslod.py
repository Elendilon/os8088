#!/usr/bin/env python3
"""THE BOX LOD'S GATE, PAST SIX KILOMETRES (SPEC.md 88.5.4.2): a solid too
small to tell apart is one filled rectangle, at EVERY range and not only the
near half of the world.

    python3 tests/skieslod.py [--machine os8088_5150_herc_gla]

cs_drawobj decides between cs_boxlod and the whole model by comparing the
model's projected size against 11 cz, and it built that product in CX - a
WORD, which 11 cz stops fitting at 5,958 m. Past there it wrapped, the
comparison fell the wrong way and every solid in the band drew all of its
vertices and all of its faces to cover four pixels. Nothing shipped stood in
the band, so nothing was slow and nothing looked wrong; what it cost was the
next building anybody added, at exactly the distance a JFK take-off starts
from (6,845 m to the Empire State).

The four anonymous towers of NYC-JFK are moved nowhere - the CAMERA is put
7 km back down the runway heading and their ranges raised so the cull keeps
them - and then, over one frame:

  1. every one of them takes cs_boxlod and none takes cs_stackverts, which
     is the gate falling the right way;
  2. the box reaches the glass - cs_rect once per tower - so a gate that
     merely CALLED cs_boxlod and had it refuse would not pass this;
  3. and the frame is shorter for it: the marginal cost of the four is
     under 7 ms a tower, against the ~11.9 the full path costs them there.

Check 3 is deliberately a BOUND and not a ratchet: it has to separate two
regimes (4.2 ms a tower boxed, 11.9 unboxed on a 4.77 MHz 8088) and not
pin whatever this month's rectangle costs.

--clobber-lod is the red run (docs/WRITING-TESTS.md 1): it NOPs the two
instructions that refuse the multiply, which restores the wrapping product
exactly, and all three checks must go red.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88ui                                               # noqa: E402
import dispapps                                             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CPS = 4772727.0
CSO_X, CSO_RANGE, CSO_SKIP, CSO_SIZE = 4, 10, 18, 20
CSA_OBJS, CSA_NOBJ = 18, 20
DIST = 7000                     # ...down the runway heading, in the band
bad = []


def check(cond, what):
    print("  [%s] %s" % ("PASS" if cond else "FAIL", what))
    if not cond:
        bad.append(what)


def main(argv):
    import math
    ap = argparse.ArgumentParser()
    ap.add_argument("--machine", default="os8088_5150_herc_gla")
    ap.add_argument("--image", default="build/os8088-360.img")
    ap.add_argument("--apps", default="build/apps360.img")
    ap.add_argument("--clobber-lod", action="store_true",
                    help="the wrapping multiply back: the row must go red")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    mp = dispapps._map("skies")

    def off(n):
        return dispapps.bss_off("skies", n)

    with os88ui.boot(a.image, apps=a.apps, machine=a.machine) as ui:
        m = ui.m
        ui.path("B:/GAMES/SKIES.O88")
        slot, seg = dispapps.pkg_seg(m, 0)
        lin = seg << 4
        base = int.from_bytes(m.readseg(seg, 8, 2), "little")

        def poke(n, d):
            m.write(lin + base + off(n), d)

        m.advance(frames=40)
        m.run()

        # --- NYC-JFK, by name out of the guest's own table -----------------
        nport = int.from_bytes(m.readseg(seg, mp["cs_drport"] + 10, 2), "little")
        port = None
        for i in range(nport):
            p = int.from_bytes(m.readseg(seg, mp["cs_ports"] + 2 * i, 2), "little")
            q = int.from_bytes(m.readseg(seg, p, 2), "little")
            nm = ""
            while True:
                c = m.readseg(seg, q + len(nm), 1)[0]
                if not c:
                    break
                nm += chr(c)
            if "JFK" in nm:
                port = p
        if port is None:
            sys.exit("skieslod: no JFK in cs_ports")
        m.pause()
        poke("cs_airport", port.to_bytes(2, "little"))
        poke("cs_inited", b"\x00")
        m.run()
        m.type_text("f")
        m.advance(frames=140)
        m.run()

        if a.clobber_lod:
            # `cmp cx, 5958` is 81 F9 46 17 and the `jae` after it 73 dd:
            # six bytes of NOP puts the wrapping multiply back exactly.
            lo, hi = mp["cs_drawobj"], mp["cs_sizepx"]
            code = m.read(lin + lo, hi - lo)
            pat = b"\x81\xF9" + (5958).to_bytes(2, "little") + b"\x73"
            i = code.find(pat)
            if i < 0:
                sys.exit("skieslod: cs_drawobj does not refuse the multiply "
                         "the way this patch expects - re-read it before "
                         "trusting the red run")
            m.pause()
            m.write(lin + lo + i, b"\x90" * 6)
            m.run()
            print("  (the wrapping 11 cz put back: must fail)")

        objs = int.from_bytes(m.read(lin + port + CSA_OBJS, 2), "little")
        nobj = int.from_bytes(m.read(lin + port + CSA_NOBJ, 2), "little")
        want = (mp["cs_m_jfk_mid"], mp["cs_m_jfk_dtn"])
        towers = [i for i in range(nobj)
                  if int.from_bytes(m.read(lin + objs + i * CSO_SIZE, 2),
                                    "little") in want]
        check(len(towers) == 4, "NYC-JFK's four anonymous towers found in its "
                                "object table (%d)" % len(towers))

        h = math.radians(310)                   # the runway's own heading

        def place(on):
            """The camera DIST back down the heading, the towers ON it.

            Where they stand in the shipped world is not the question here -
            two of the four are off to the side from this camera and the
            frustum drops them, which would make the counts below a fact
            about JFK's layout rather than about the gate. They are put in a
            row across the sight line instead, all at DIST.
            """
            m.pause()
            for k, i in enumerate(towers):
                lat = (k - (len(towers) - 1) / 2.0) * 200.0
                x = int(round(lat * math.cos(h)))
                z = int(round(-lat * math.sin(h)))
                m.write(lin + objs + i * CSO_SIZE + CSO_X,
                        ((x & 0xFFFF).to_bytes(2, "little")
                         + (z & 0xFFFF).to_bytes(2, "little")))
            for nm, v in (("cs_px", int(round(-DIST * math.sin(h)))),
                          ("cs_py", 200),
                          ("cs_pz", int(round(-DIST * math.cos(h))))):
                poke(nm, ((v * 256) & 0xFFFFFFFF).to_bytes(4, "little"))
            poke("cs_hdg", (int(310 * 65536 / 360) & 0xFFFF).to_bytes(2, "little"))
            poke("cs_pitch", b"\x00\x00")
            poke("cs_roll", b"\x00\x00")
            poke("cs_state", b"\x01")
            poke("cs_pause", b"\x01")
            for i in range(nobj):
                r = 15900 if (i in towers and on) else 0
                m.write(lin + objs + i * CSO_SIZE + CSO_RANGE,
                        r.to_bytes(2, "little"))
                m.write(lin + objs + i * CSO_SIZE + CSO_SKIP, b"\x00\x00")
            m.run()

        stages = ("cs_render", "cs_boxlod", "cs_stackverts", "cs_rect")
        byoff = {mp[s]: s for s in stages}

        def one_frame():
            """Every stage entered between one cs_render and the next."""
            m.bp_exec(*[lin + mp[s] for s in stages])
            m.run()
            if m.wait_stop(60) is None:
                sys.exit("skieslod: nothing stopped")
            while byoff.get(m.regs()["ip"]) != "cs_render":
                m.run()
                if m.wait_stop(60) is None:
                    sys.exit("skieslod: cs_render never ran")
            hits = {}
            for _ in range(400):
                m.run()
                if m.wait_stop(60) is None:
                    break
                nm = byoff.get(m.regs()["ip"])
                if nm == "cs_render":
                    break
                hits[nm] = hits.get(nm, 0) + 1
            m.bp_exec()
            m.run()
            return hits

        def frame_ms(n=9):
            m.bp_exec(lin + mp["cs_render"])
            m.run()
            m.wait_stop(60)
            c0 = m.status()["cycles"]
            out = []
            for _ in range(n):
                m.run()
                if m.wait_stop(60) is None:
                    sys.exit("skieslod: no frame")
                c1 = m.status()["cycles"]
                out.append((c1 - c0) / CPS * 1000.0)
                c0 = c1
            m.bp_exec()
            m.run()
            return sorted(out)[len(out) // 2]

        # --- 1 and 2: which path the four take, over one frame -------------
        place(True)
        m.advance(frames=6)
        m.run()
        hits = one_frame()
        nbox = hits.get("cs_boxlod", 0)
        nstk = hits.get("cs_stackverts", 0)
        nrect = hits.get("cs_rect", 0)
        check(nbox == len(towers) and nstk == 0,
              "at %d m every tower takes the box: cs_boxlod %d, "
              "cs_stackverts %d (want %d and 0)"
              % (DIST, nbox, nstk, len(towers)))
        check(nrect >= len(towers),
              "and the box REACHES THE GLASS: cs_rect %d (want %d or more, "
              "so a cs_boxlod that refused would not pass)"
              % (nrect, len(towers)))

        # --- 3: and the frame is shorter for it ----------------------------
        on = frame_ms()
        place(False)
        m.advance(frames=6)
        m.run()
        m.bp_exec()
        m.run()
        gone = frame_ms()
        per = (on - gone) / len(towers)
        check(per < 7.0,
              "the four cost %.2f ms a tower (%.1f ms against %.1f), under "
              "the 7 ms that separates the box from the full path"
              % (per, on, gone))

    print("skieslod: %s" % ("FAIL - " + "; ".join(bad) if bad else "ok"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
