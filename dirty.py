#!/usr/bin/env python3
"""WHAT ACTUALLY CHANGED, against what the machine CARRIES.

At the cs_blit call site the shadow holds the NEW frame and the card still
holds the OLD one, so the two together are the exact answer to "which bytes
had to move". cs_blit's own rule is the union of the two span sets per row,
word-aligned - so the same walk, scored against the truth, prices every mark
in the frame at once.
"""
import os, sys, importlib.util
ROOT = "/home/user/os8088"
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
os.chdir(ROOT)
import os88marty, dispapps                                     # noqa: E402
import skies as skiestest                                      # noqa: E402
spec = importlib.util.spec_from_file_location("sp", "tests/skiesprof.py")
sp = importlib.util.module_from_spec(spec); spec.loader.exec_module(sp)
S = os.path.dirname(os.path.abspath(__file__))
MP = dispapps._map("skies")
P = sp.PROFILES["slightbank"]
ANGLES = [float(a) for a in (sys.argv[1:] or [0, 5, 12])]
find = sp.sites()
mtx = find("cs_render", r"call cs_matrix$")[0][0]
blt = find("cs_r_end", r"call cs_blit$")[0][0]
NF = 9
with os88marty.launch("build/os8088-360.img", apps="build/apps360.img",
                      machine="os8088_5150_herc_gla") as m:
    slot, seg, base = skiestest.open_game(m)
    lin = seg << 4
    off = lambda n: MP[n] - MP["os88_image_end"]
    goff = lambda a: base + a - MP["os88_image_end"]
    rw = lambda n: int.from_bytes(m.readseg(seg, base + off(n), 2), "little")
    poke = lambda n, d: m.write(lin + base + off(n), d)
    m.type_text("f"); m.advance(frames=30); m.run(); m.pause()
    print("\n  %5s | %8s %8s %7s | %8s %8s | %s"
          % ("roll", "carried", "differ", "waste", "rows cd", "rows df",
             "missed"))
    for deg in ANGLES:
        for n, v in zip(("cs_px", "cs_py", "cs_pz"), P["pos"]):
            poke(n, ((int(v * 256)) & 0xFFFFFFFF).to_bytes(4, "little"))
        poke("cs_hdg", ((P["hdg"] * 65536 // 360) & 0xFFFF).to_bytes(2, "little"))
        poke("cs_pitch", b"\x00\x00"); poke("cs_state", b"\x01")
        poke("cs_spd", (P.get("spd", 40) * 128).to_bytes(2, "little"))
        poke("cs_thr", P["thr"].to_bytes(2, "little"))
        hold = (int(deg * 65536 / 360) & 0xFFFF).to_bytes(2, "little")
        poke("cs_roll", hold)
        frames, tot = [0], [0, 0, 0, 0, 0, 0]
        maps = []

        def on_hit(mm, rec):
            a = rec["addr"] - lin
            if a == mtx:
                poke("cs_roll", hold)
                frames[0] += 1
                return True
            if a != blt or frames[0] < 4:
                return True
            wh, wb0 = rw("cs_wh"), mm.readseg(seg, base + off("cs_wb0"), 1)[0]
            wbn = mm.readseg(seg, base + off("cs_wbn"), 1)[0]
            cur = mm.readseg(seg, goff(rw("cs_spcur")), wh * 2)
            prv = mm.readseg(seg, goff(rw("cs_spprv")), wh * 2)
            dev = mm.readseg(seg, base + off("cs_devoff"), wh * 2)
            shs, fsi = rw("cs_shseg"), rw("cs_fsi")
            tb = rw("cs_tbase")
            sh = mm.readseg(shs, tb, 80 * wh)
            vr = mm.readseg(fsi, 0, 0x8000)
            car = dif = rc = rd = miss = 0
            rowmap = []
            for y in range(wh):
                lo, hi = cur[y * 2], cur[y * 2 + 1]
                pl, ph = prv[y * 2], prv[y * 2 + 1]
                l = min(lo, pl); h = max(hi, ph) if (hi != 255 or ph != 255) else 0
                if lo == 255 and pl == 255:
                    l, h = 1, 0
                else:
                    h = max(hi if lo != 255 else 0, ph if pl != 255 else 0)
                    l = min(lo if lo != 255 else 255, pl if pl != 255 else 255)
                    if l > h:
                        l, h = 1, 0
                    else:
                        l &= 0xFE; h |= 1
                d0 = int.from_bytes(dev[y * 2:y * 2 + 2], "little")
                line = [0] * wbn
                dr = False
                for b in range(wbn):
                    col = wb0 + b
                    s = sh[80 * y + col]
                    v = vr[(d0 + col) & 0x7FFF]
                    carried = l <= col <= h
                    differs = s != v
                    if carried:
                        car += 1
                    if differs:
                        dif += 1
                        dr = True
                        if not carried:
                            miss += 1
                    line[b] = (2 if differs else 1) if carried else (3 if differs else 0)
                rowmap.append(line)
                if l <= h:
                    rc += 1
                if dr:
                    rd += 1
            for i, v in enumerate((car, dif, rc, rd, miss, 1)):
                tot[i] += v
            if len(maps) < 1:
                maps.append((wbn, wh, rowmap))
            return True

        m.run()
        with os88marty.bp_trace(m, lin + mtx, lin + blt, poll=0.0008,
                                cap=40000, on_hit=on_hit):
            os88marty.until(m, lambda _: frames[0] > NF, "%d frames" % NF,
                            poll=0.4, limit=900.0, guest=1500.0)
        m.pause()
        n = max(1, tot[5])
        print("  %4.0f° | %8.0f %8.0f %6.1fx | %8.1f %8.1f | %.1f"
              % (deg, tot[0] / n, tot[1] / n,
                 tot[0] / max(1.0, tot[1]), tot[2] / n, tot[3] / n,
                 tot[4] / n))
        wbn, wh, rowmap = maps[0]
        px = bytearray()
        for y in range(wh):
            for _ in range(2):
                for b in range(wbn):
                    v = rowmap[b and b or b] if False else rowmap[y][b]
                    c = ((0, 0, 0), (170, 40, 40), (255, 255, 90),
                         (0, 120, 255))[v]
                    px += bytes(c) * 8
        os88marty.write_png_rgb("%s/dirty_r%d.png" % (S, int(deg)),
                                wbn * 8, wh * 2, bytes(px))
