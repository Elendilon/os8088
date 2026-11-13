"""trace.py "<menu item>" NFRAMES OUT.json [keys] - exact guest cycles of the renderer's
pieces during the P bench, by breakpoints at their entries (split build).
Run from the worktree root."""
import sys, os, re, struct, subprocess, tempfile, json
sys.path.insert(0, 'tools')
import os88ui
from os88pkg import PKG_FMT
F = 4772727
item, nfr, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
pre = sys.argv[4:]
def amap(path, binp):
    d = tempfile.mkdtemp(); mp, bn = os.path.join(d, "m"), os.path.join(d, "b")
    subprocess.check_call(["nasm", "-f", "bin", "-w+error", "-I", "apps/", "-I", "apps/wirearena/",
                           "-I", "build/", "--before", "[map all %s]" % mp, "-o", bn, path])
    assert open(bn, "rb").read() == open(binp, "rb").read(), "stale " + binp
    o = {}
    for line in open(mp):
        f = line.split()
        if len(f) == 3 and re.match(r'^[0-9A-F]+$', f[0]) and re.match(r'^[0-9A-F]+$', f[1]):
            o[f[2]] = int(f[0], 16)
    return o
g = amap("apps/wirearena/wirearena.asm", "build/wirearena.bin")
r = amap("apps/wirearena/wrpart.asm", "build/wrpart.bin")
NAMES = ["G.render", "wa_render", "wa_render.walked", "wa_render.roomless", "wa_leaf", "wa_face",
         "wa_span", "wa_figures", "wa_cross", "wa_present"]
with os88ui.boot("build/os8088-360.img", apps="build/warena360.img") as ui:
    m = ui.m
    ui.path("B:/WARENA.O88"); m.advance(cycles=F // 2); m.go()
    ui.menu_pick("Game", item); m.advance(cycles=F)
    for k in pre:
        m.key(k); m.advance(cycles=F // 4)
    buf = m.read(0x10000, 0x90000)
    b = [0x10000 + o for o in range(0, len(buf) - 32, 16)
         if buf[o:o + 2] == b'O8' and buf[o + 2] == PKG_FMT and buf[o + 16:o + 22] == b'WARENA'][-1]
    m.key("KeyP"); m.advance(cycles=F // 2)
    m.pause()
    rs = struct.unpack('<H', m.read(b + g["wa_rds"], 2))[0] * 16
    pts = [b + g["wa_render"]] + [rs + r[n] for n in NAMES[1:]]
    m.bp_exec(*pts)
    rd = lambda n: struct.unpack('<h', m.read(rs + r[n], 2))[0]
    ev = []; frames = 0
    while frames <= nfr:
        m.go()
        if m.wait_stop(30) is None:
            raise SystemExit("no stop")
        st = m.status()
        lin = (int(st["cs"]) << 4) + int(st["ip"])
        k = pts.index(lin)
        e = {"k": NAMES[k], "c": int(st["cycles"]), "left": rd("wa_left")}
        if NAMES[k] == "wa_span":
            e["c1"] = rd("wa_c1"); e["c2"] = rd("wa_c2")
        if NAMES[k] == "wa_face":
            e["ax"] = int(m.regs()["ax"])
        if NAMES[k] == "G.render":
            frames += 1
        ev.append(e)
    m.bp_exec()
json.dump(ev, open(out, "w"))
print("events", len(ev), "frames", frames)
