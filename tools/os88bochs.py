#!/usr/bin/env python3
"""Run kern_mega under Bochs and start packages until one faults
(docs/plans/KERN-MEGA-PLAN.md 10.1 items 13 and 16).

    python3 tools/os88bochs.py sweep [--batch N] [--out DIR] PKG.o88 ...
    python3 tools/os88bochs.py boot [--out DIR]     boot and leave it running
    python3 tools/os88bochs.py stop                 end every Bochs on the display
    python3 tools/os88bochs.py dbg [--out DIR] CMD...  break in, run debugger
                                                    commands, print, carry on

    --sb        give the machine a Sound Blaster 16 (port 220h, IRQ 5, DMA 1),
                its output written to OUT/sb.wav
    --b IMG     a 1.2MB floppy for B: in place of build/apps120.img
    --cfg BITS  write a SYSTEM.CFG onto A: wanting the drivers in BITS - one
                bit per driver by kernel/driver.inc's drv_cfgbit, sound being
                bit 0 (the Makefile's system.cfg rules are the same bytes)

WHY BOCHS. QEMU's TCG checks no segment on a data access and lets code write
through CS, so on QEMU kern_mega runs code that faults on a real 286 - every
one of the Victory 286's first five faults ran clean there. Bochs checks every
access the way the CPU does, and reproduced those faults to the CS:IP and SP
of the photographs. Its CPU is a 386, so the reflection takes the CR0 path and
the 286 RESET path stays the field machine's to prove.

SWEEP builds a hard disk whose one folder, RUN/, holds tests/megarun's
MEGARUN (as 0RUN.O88, so it is the first file in the listing) and a batch of
packages; boots build/mega.img in A: with that disk as C:; opens C:, RUN and
0RUN.O88 with the mouse; and follows MEGARUN's lines on port E9, which name
each package before it is started. A `kern_mega FAULT` line ends the boot and
is charged to the package last named; so is a minute with no new line (a
package that took the screen, or a hang). The next boot carries on with the
packages after it. Every started package gets a screenshot in --out.

NEEDS: bochs (2.7: `BIOS-bochs-legacy` - the default BIOS's 32-bit init
crashes here), Xvfb, xdotool, xwd and ImageMagick's convert; `apt-get install
bochs bochsbios vgabios bochs-x xvfb xdotool x11-apps imagemagick`. The
Debian build has the debugger compiled in and stops at reset, so `c` goes in
on stdin.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPLAY = ":99"
ENV = dict(os.environ, DISPLAY=DISPLAY)
GEOM = (615, 4, 17)             # a 20MB disk: C/H/S as the BIOS sees it

BOCHSRC = """megs: 16
romimage: file=/usr/share/bochs/BIOS-bochs-legacy
vgaromimage: file=/usr/share/vgabios/vgabios.bin
vga: extension=vbe
pci: enabled=0
floppya: 1_44={a}, status=inserted
floppyb: 1_2={b}, status=inserted
ata0: enabled=1, ioaddr1=0x1f0, ioaddr2=0x3f0, irq=14
ata0-master: type=disk, path={c}, mode=flat, cylinders={cy}, heads={hd}, spt={sp}
boot: floppy
port_e9_hack: enabled=1
mouse: enabled=1, type=ps2, toggle=ctrl+mbutton
clock: sync=realtime, time0=local
{sb}log: {log}
panic: action=report
error: action=report
info: action=ignore
display_library: x
"""


def xd(*a):
    subprocess.run(["xdotool"] + [str(x) for x in a], env=ENV, check=True)


def rel(dx, dy):
    xd("mousemove_relative", "--", dx, dy)
    time.sleep(0.04)


def goto(x, y):
    """Pin at the guest's top-left corner, then walk: the guest moves one
    pixel per two X pixels (measured), in small steps."""
    for _ in range(40):
        rel(-60, -60)
    time.sleep(0.3)
    x2, y2 = 2 * x, 2 * y
    while x2 or y2:
        sx, sy = max(-30, min(30, x2)), max(-30, min(30, y2))
        rel(sx, sy)
        x2 -= sx
        y2 -= sy
    time.sleep(0.5)


def dbl(x, y):
    goto(x, y)
    xd("click", "--repeat", 2, "--delay", 120, 1)


def shot(path):
    subprocess.run("xwd -root -silent | convert xwd:- -crop 650x500+5+40 "
                   "+repage '%s'" % path, shell=True, env=ENV, check=True)


def xvfb():
    if subprocess.run(["pgrep", "-x", "Xvfb"],
                      capture_output=True).returncode != 0:
        subprocess.Popen(["Xvfb", DISPLAY, "-screen", "0", "1024x768x24"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)


def running():
    """PIDs of every Bochs on the box. ONE AT A TIME: the mouse, the keys and
    the screenshots all go to the X display, and with two machines on it they
    land on whichever window is on top - which reads exactly like a guest that
    froze. `bochs` execs `bochs-bin`, so that is the name to look for."""
    r = subprocess.run(["pgrep", "-x", "bochs-bin"], capture_output=True,
                       text=True)
    return [int(p) for p in r.stdout.split()]


def dbg(out, cmds):
    """Break into the running Bochs, run CMDS, print what they said, and
    continue it."""
    e9 = os.path.join(out, "e9.out")
    n = os.path.getsize(e9)
    for p in running():
        os.kill(p, 2)               # SIGINT: Bochs stops at its prompt
    time.sleep(1.5)
    with open(os.path.join(out, "dbg.fifo"), "w") as fh:
        fh.write("\n".join(cmds) + "\nc\n")
    time.sleep(2 + 0.3 * len(cmds))
    with open(e9, "rb") as f:
        f.seek(n)
        sys.stdout.write(f.read().decode("latin-1"))


def stop():
    subprocess.run(["pkill", "-f", "^sleep 86400"])
    for p in running():
        os.kill(p, 15)
    end = time.time() + 10
    while running() and time.time() < end:
        time.sleep(0.5)
    for p in running():
        os.kill(p, 9)


class Box(object):
    """One Bochs, its disks in OUT, its E9 output in OUT/e9.out."""

    def __init__(self, out, pkgs, sb=False, cfg=None, bimg=None):
        if running():
            sys.exit("os88bochs: a Bochs is already running (pids %s) - every "
                     "click would land on whichever window is on top. "
                     "`os88bochs.py stop` ends it" %
                     " ".join(map(str, running())))
        self.out = out
        self.e9 = os.path.join(out, "e9.out")
        a, b = os.path.join(out, "a.img"), os.path.join(out, "b.img")
        c = os.path.join(out, "c.img")
        shutil.copy(os.path.join(ROOT, "build", "mega.img"), a)
        shutil.copy(bimg or os.path.join(ROOT, "build", "apps120.img"), b)
        if cfg is not None:
            f = os.path.join(out, "SYSTEM.CFG")
            with open(f, "wb") as fh:
                fh.write(b"O88CFG\0\0" + (3).to_bytes(2, "little") + b"DW" +
                         bytes([1, 2]) + cfg.to_bytes(2, "little") + b"\0\0")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                         "os88fat.py"),
                            "del", a, "SYSTEM.CFG"], stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                         "os88fat.py"),
                            "add", a, f], check=True,
                           stdout=subprocess.DEVNULL)
        stage = os.path.join(out, "stage")
        shutil.rmtree(stage, ignore_errors=True)
        os.makedirs(stage)
        args = ["RUN:" + self._stage(stage, os.path.join(ROOT, "build",
                                                         "megarun.o88"),
                                     "0run.o88")]
        for p in pkgs:
            args.append("RUN:" + self._stage(stage, p,
                                             os.path.basename(p).lower()))
        subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                     "os88disk.py"),
                        "-o", c, "--hdd",
                        "--mbr", os.path.join(ROOT, "build", "mbr.bin"),
                        "--boot", os.path.join(ROOT, "build", "megak",
                                               "boothd.bin"),
                        "--kernel", os.path.join(ROOT, "build", "megak",
                                                 "kernel.sys"),
                        "--geometry", "%d/%d/%d" % GEOM] + args,
                       check=True, stdout=subprocess.DEVNULL)
        rc = os.path.join(out, "bochsrc")
        with open(rc, "w") as f:
            f.write(BOCHSRC.format(
                a=a, b=b, c=c, cy=GEOM[0], hd=GEOM[1], sp=GEOM[2],
                log=os.path.join(out, "bochs.log"),
                sb=("sound: waveoutdrv=file, waveout=%s\n"
                    "sb16: enabled=1, midimode=0, wavemode=1, "
                    "dmatimer=600000\n" % os.path.join(out, "sb.wav"))
                if sb else ""))
        for n in os.listdir(out):
            if n.endswith(".lock"):
                os.remove(os.path.join(out, n))
        xvfb()
        self.f = open(self.e9, "wb")
        # The debugger reads a FIFO, held open by a `sleep` of its own so the
        # machine outlives this process (`boot`) and `dbg` can still reach it
        fifo = os.path.join(out, "dbg.fifo")
        if os.path.exists(fifo):
            os.remove(fifo)
        os.mkfifo(fifo)
        self.p = subprocess.Popen(["bochs", "-q", "-f", rc], cwd=out,
                                  stdin=os.open(fifo, os.O_RDWR),
                                  stdout=self.f, stderr=subprocess.STDOUT,
                                  env=ENV)
        self.hold = subprocess.Popen("exec sleep 86400 > '%s'" % fifo,
                                     shell=True)
        with open(fifo, "w") as fh:
            fh.write("c\n")

    @staticmethod
    def _stage(stage, src, name):
        dst = os.path.join(stage, name)
        shutil.copy(src, dst)
        return dst

    def lines(self):
        with open(self.e9, "rb") as f:
            t = f.read().decode("latin-1")
        return [l for l in t.splitlines() if l.strip()]

    def wait_for(self, text, secs):
        end = time.time() + secs
        while time.time() < end:
            if any(text in l for l in self.lines()):
                return True
            time.sleep(1)
        return False

    def capture(self):
        w = subprocess.run(["xdotool", "search", "--name", "Bochs"], env=ENV,
                           capture_output=True, text=True).stdout.split()[0]
        xd("windowfocus", "--sync", w)
        xd("mousemove", 330, 300)
        xd("keydown", "ctrl")
        xd("click", 2)
        xd("keyup", "ctrl")
        time.sleep(1)

    def stop(self):
        self.hold.kill()
        self.p.terminate()
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()
        self.f.close()


def sweep(pkgs, batch, out, quiet_secs=60, sb=False, cfg=None):
    os.makedirs(out, exist_ok=True)
    left = list(pkgs)
    report = []
    boot = 0
    while left:
        boot += 1
        todo, left = left[:batch], left[batch:]
        d = os.path.join(out, "boot%02d" % boot)
        os.makedirs(d, exist_ok=True)
        box = Box(d, todo, sb, cfg)
        try:
            if not box.wait_for("kern_mega:", 240):
                report.append(("(boot)", "no kern_mega line in 240s"))
                left = todo + left
                break
            time.sleep(15)          # the desktop's first frame
            box.capture()
            dbl(591, 160)           # C:
            time.sleep(10)
            dbl(150, 123)           # RUN, the root's one folder
            time.sleep(8)
            dbl(160, 139)           # 0RUN.O88, under '..'
            seen, last, quiet = 0, None, time.time()
            started = []
            while True:
                ls = box.lines()
                new = ls[seen:]
                seen = len(ls)
                fault = None
                for l in new:
                    if l.startswith("MEGARUN: ") and l not in (
                            "MEGARUN: ok", "MEGARUN: done") \
                            and not l.startswith("MEGARUN: no "):
                        last = l[9:]
                        started.append(last)
                    elif l == "MEGARUN: ok" and last:
                        time.sleep(4)
                        shot(os.path.join(d, last.replace(".", "_") +
                                          ".png"))
                        report.append((last, "ok"))
                    elif l.startswith("MEGARUN: no "):
                        report.append((last, "refused " + l[12:]))
                    elif l.startswith("kern_mega FAULT"):
                        fault = l + " | " + " ".join(
                            ls[ls.index(l) + 1:ls.index(l) + 2])
                    elif l == "MEGARUN: done":
                        fault = "done"
                if new:
                    quiet = time.time()
                if fault == "done":
                    break
                if fault:
                    shot(os.path.join(d, "FAULT.png"))
                    report.append((last or "(before MEGARUN)",
                                   "FAULT " + fault))
                    break
                if time.time() - quiet > quiet_secs:
                    shot(os.path.join(d, "QUIET.png"))
                    report.append((last or "(MEGARUN did not start)",
                                   "no E9 line in %ds" % quiet_secs))
                    break
                time.sleep(1)
            # what MEGARUN never reached goes round again
            done = {os.path.basename(p).upper() for p in todo
                    if os.path.basename(p).upper() in started}
            left = [p for p in todo
                    if os.path.basename(p).upper() not in done] + left
            if not started:
                break               # nothing moved: do not loop for ever
        finally:
            box.stop()
    for name, what in report:
        print("%-14s %s" % (name, what))
    if left:
        print("not reached: " + " ".join(os.path.basename(p) for p in left))


def main():
    if sys.argv[1:2] == ["dbg"]:
        rest, out = sys.argv[2:], os.path.join(ROOT, "build", "bochs")
        if rest[:1] == ["--out"]:
            out, rest = rest[1], rest[2:]
        dbg(os.path.abspath(out), rest)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("sweep", "boot", "stop"))
    ap.add_argument("pkgs", nargs="*")
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "bochs"))
    ap.add_argument("--sb", action="store_true")
    ap.add_argument("--cfg", type=lambda v: int(v, 0))
    ap.add_argument("--b", dest="bimg", help="a 1.2MB image for B: in place "
                    "of build/apps120.img")
    a = ap.parse_args()
    a.out = os.path.abspath(a.out)
    a.pkgs = [os.path.abspath(p) for p in a.pkgs]
    if a.cmd == "stop":
        stop()
    elif a.cmd == "sweep":
        sweep(a.pkgs, a.batch, a.out, sb=a.sb, cfg=a.cfg)
    else:
        os.makedirs(a.out, exist_ok=True)
        box = Box(a.out, a.pkgs, a.sb, a.cfg,
                  os.path.abspath(a.bimg) if a.bimg else None)
        box.wait_for("kern_mega:", 240)
        print("running: DISPLAY=%s, E9 in %s" % (DISPLAY, box.e9))


if __name__ == "__main__":
    main()
