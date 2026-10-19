#!/usr/bin/env python3
"""RealBoy's speed IN ITS WINDOW, on an 86Box machine: the game's frames
against real time, and the frames drawn.

    python3 tests/rbcore/rbwin.py GAME.GB [--vm 286] [--secs 20] [--hold KEYS]
                                  [--profile N] [--keep NAME]
    python3 tests/rbcore/rbwin.py GAME.GB --attach NAME ...   (a --keep machine)

docs/reports/REALBOY-CORE-COST-2026-10-19.md section 3 times the core bare;
this times the package, with os8088 under it and the picture drawn. It writes
a 1.44MB B: disk holding build/realboy.o88 and the game, boots vm/<VM>,
opens B: and double-clicks the game, lets it run 10 emulated seconds, then
reads:

  * the game's speed, from the core's own frame counter (S_FRAMES, in the
    view) across --secs of emulated time, against the 59.7275 frames a
    second a Game Boy runs at; and
  * the frames drawn a second, from the F1 overlay's line, which the package
    composes in its own memory whether or not the overlay is up.

--press taps keys first (os88box names, comma separated: return to start
a game; w5000 runs 5 emulated seconds between two). --hold presses keys (86Box scan codes, comma separated, 0x14D for
Right) for the whole timed span. --profile N then samples CS:IP N times, one
emulated millisecond apart, and charges each to a core handler, a package
routine or a kernel symbol (by linear address, docs/plans/DISK-CPU-PLAN.md
section 1). --keep leaves the machine running under NAME.

86Box times instructions by its model and is not cycle-accurate
(docs/86BOX.md). The game is the caller's and is never written anywhere but
the scratch disk.
"""
import argparse
import bisect
import collections
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "tests", "rbcore"))
import os88box  # noqa: E402
import gbwindow  # noqa: E402
import rbprof  # noqa: E402

GB_HZ = 4194304 / 70224
LST = os.path.join(ROOT, "build", "realboy.lst")
CORELST = os.path.join(ROOT, "build", "realboy", "rbcore.asm.lst")
DRIVE_B = (592, 105)            # the B: icon on the VGA desktop
MENU_MACHINE = (190, 9)         # RealBoy's Machine menu on the bar
ITEM_FULLSCREEN = (200, 60)     # ...its third item
FIRST_ICON = (160, 127)         # the first file in a fresh B: window (list view)


def find(b):
    vo = gbwindow.label_off(LST, "rb_viewseg")
    mem = b"".join(b.memr(0x10000 + k, 0x8000) for k in range(0, 0x90000, 0x8000))
    for o in range(0, len(mem) - 32, 16):
        if mem[o:o+2] == b"O8" and mem[o+16:o+23] == b"REALBOY":
            v = int.from_bytes(mem[o+vo:o+vo+2], "little")
            if v and int.from_bytes(b.memr(v*16 + 0x4012, 2), "little") == v:
                core = int.from_bytes(mem[o+vo+2:o+vo+4], "little")
                return (0x10000 + o) >> 4, v, core
    raise SystemExit("rbwin: no running REALBOY with a view found")


def frames(b, view):
    return int.from_bytes(b.memr(view*16 + 0x403E, 2), "little")


def overlay(b, seg):
    m = re.search(rb"(\d+)% (\d+)fps(?: JIT)?\0", b.memr(seg*16, 0x8000) + b.memr(seg*16 + 0x8000, 0x8000))
    return (int(m.group(1)), int(m.group(2))) if m else None


def profile(b, seg, core, n):
    import os88sym
    psyms = rbprof.labels(LST)
    pk = [o for o, _ in psyms]
    csyms = rbprof.labels(CORELST) if os.path.exists(CORELST) else []
    ck = [o for o, _ in csyms]
    size = os.path.getsize(os.path.join(ROOT, "build", "realboy.bin")) + 20000
    lin = []
    for nm in os88sym.syms():
        try:
            a = os88sym.linear(nm)
        except Exception:
            continue
        if a is not None and "." not in nm:
            lin.append((a, nm))
    lin.sort()
    lk = [a for a, _ in lin]
    hits = collections.Counter()
    for _ in range(n):
        b.cmd("step 1")
        r = b.cmd("regs")
        ip = r["cs_base"] + (r["eip"] & 0xFFFF)
        if seg*16 <= ip < seg*16 + size:
            k = bisect.bisect_right(pk, ip - seg*16) - 1
            hits["pkg " + (psyms[k][1] if k >= 0 else "?")] += 1
        elif core*16 <= ip < core*16 + 0x10000:
            k = bisect.bisect_right(ck, ip - core*16) - 1
            hits["core " + (csyms[k][1] if ck and k >= 0 else "%02X" % ((ip - core*16) >> 8))] += 1
        elif ip >= 0xF0000:
            hits["BIOS"] += 1
        else:
            k = bisect.bisect_right(lk, ip) - 1
            hits["kern " + (lin[k][1] if k >= 0 else "?")] += 1
    groups = collections.Counter()
    for k, v in hits.items():
        groups[k.split()[0]] += v
    print("profile: " + "  ".join("%s %.1f%%" % (g, 100.0*v/n) for g, v in groups.most_common()))
    for k, v in hits.most_common(30):
        print("%6.1f%% %s" % (100.0*v/n, k))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--vm", default="286")
    ap.add_argument("--secs", type=float, default=20)
    ap.add_argument("--hold", default="")
    ap.add_argument("--profile", type=int, default=0)
    ap.add_argument("--keep", default="")
    ap.add_argument("--shot", default="")
    ap.add_argument("--attach", default="", help="measure a machine --keep left running")
    ap.add_argument("--press", default="", help="keys to tap first, e.g. return")
    ap.add_argument("--fs", action="store_true", help="Machine > Full Screen first")
    o = ap.parse_args()

    if o.attach:
        o.keep = o.attach
        b = os88box.Box(o.attach)
    else:
        b = boot(o)
    try:
        measure(b, o)
    finally:
        if not o.keep:
            b.cmd("quit")


def boot(o):
    name = o.keep or "rbwin%d" % os.getpid()
    tmp = tempfile.mkdtemp(prefix="rbwin")
    gb = os.path.join(tmp, "GAME.GB")
    with open(o.rom, "rb") as f, open(gb, "wb") as g:
        g.write(f.read())
    disk = os.path.join(tmp, "rb144.img")
    os88box.subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88disk.py"), "-o", disk,
                            "--size", "1440", os.path.join(ROOT, "build", "realboy.o88"), gb],
                           check=True, stdout=os88box.subprocess.DEVNULL)
    b = os88box.launch(o.vm, name=name, hold=True, fresh=True,
                       a=os.path.join(ROOT, "build", "os8088.img"), b=disk)
    if True:
        for _ in range(120):
            b.cmd("step 500")
            try:
                t = "".join(bytes.fromhex(x).decode("cp437") for x in b.cmd("text").get("chars", []))
            except SystemExit:
                t = ""
            if "EXIT FOR BOOT" in t:
                b.tap("return")
        b.cmd("step 20000")
        b.to(*DRIVE_B)
        b.click(2)
        b.cmd("step 6000")
        b.to(*FIRST_ICON)
        b.click(2)
        b.cmd("step 10000")
    return b


def measure(b, o):
    if True:
        for k in o.press.split(","):
            if re.match(r"w\d+$", k):          # w5000: run 5 emulated s
                b.cmd("step %s" % k[1:])
            elif k:                             # held 300 ms: a game polls
                code = os88box.KEYS[k]          #   once a frame, and a slow
                b.cmd("key down 0x%X" % code)   #   frame is longer than a tap
                b.cmd("step 300")
                b.cmd("key up 0x%X" % code)
                b.cmd("step 2000")
        if o.fs:
            b.to(*MENU_MACHINE)
            b.mouse(0, 0, 1)
            b.pause(200)
            b.to(*ITEM_FULLSCREEN, buttons=1)
            b.pause(200)
            b.mouse(0, 0, 0)
            b.cmd("step 3000")
        seg, view, core = find(b)
        keys = [int(k, 0) for k in o.hold.split(",") if k]
        for k in keys:
            b.cmd("key down 0x%02X" % k)
        b.cmd("step 2000")
        f0, t0 = frames(b, view), b.cmd("info").get("ms")
        b.cmd("step %d" % int(o.secs * 1000))
        f1, t1 = frames(b, view), b.cmd("info").get("ms")
        ov = overlay(b, seg)
        secs = (t1 - t0) / 1000.0
        n = (f1 - f0) & 0xFFFF
        print("rbwin %s on %s: %d frames in %.1f emulated s = %.2f fps, %.1f%% of real time; "
              "overlay: %s" % (os.path.basename(o.rom), o.vm, n, secs, n / secs,
                               100.0 * n / secs / GB_HZ,
                               "%d%% %d fps drawn" % ov if ov else "none"))
        if o.shot:
            b.shot(o.shot)
        if o.profile:
            profile(b, seg, core, o.profile)
        for k in keys:
            b.cmd("key up 0x%02X" % k)


if __name__ == "__main__":
    main()
