#!/usr/bin/env python3
"""Run kern_mega under Bochs and start packages until one faults
(docs/plans/KERN-MEGA-PLAN.md 10.1 items 13 and 16).

    python3 tools/os88bochs.py sweep [--batch N] [--out DIR] PKG.o88 ...
    python3 tools/os88bochs.py boot [--out DIR]     boot and leave it running

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
log: {log}
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


class Box(object):
    """One Bochs, its disks in OUT, its E9 output in OUT/e9.out."""

    def __init__(self, out, pkgs):
        self.out = out
        self.e9 = os.path.join(out, "e9.out")
        a, b = os.path.join(out, "a.img"), os.path.join(out, "b.img")
        c = os.path.join(out, "c.img")
        shutil.copy(os.path.join(ROOT, "build", "mega.img"), a)
        shutil.copy(os.path.join(ROOT, "build", "apps120.img"), b)
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
            f.write(BOCHSRC.format(a=a, b=b, c=c, cy=GEOM[0], hd=GEOM[1],
                                   sp=GEOM[2],
                                   log=os.path.join(out, "bochs.log")))
        for n in os.listdir(out):
            if n.endswith(".lock"):
                os.remove(os.path.join(out, n))
        xvfb()
        self.f = open(self.e9, "wb")
        self.p = subprocess.Popen(["bochs", "-q", "-f", rc], cwd=out,
                                  stdin=subprocess.PIPE, stdout=self.f,
                                  stderr=subprocess.STDOUT, env=ENV)
        self.p.stdin.write(b"c\n")
        self.p.stdin.flush()

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
        self.p.terminate()
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()
        self.f.close()


def sweep(pkgs, batch, out, quiet_secs=60):
    os.makedirs(out, exist_ok=True)
    left = list(pkgs)
    report = []
    boot = 0
    while left:
        boot += 1
        todo, left = left[:batch], left[batch:]
        d = os.path.join(out, "boot%02d" % boot)
        os.makedirs(d, exist_ok=True)
        box = Box(d, todo)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("sweep", "boot"))
    ap.add_argument("pkgs", nargs="*")
    ap.add_argument("--batch", type=int, default=6)
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "bochs"))
    a = ap.parse_args()
    a.out = os.path.abspath(a.out)
    a.pkgs = [os.path.abspath(p) for p in a.pkgs]
    if a.cmd == "sweep":
        sweep(a.pkgs, a.batch, a.out)
    else:
        os.makedirs(a.out, exist_ok=True)
        box = Box(a.out, a.pkgs)
        box.wait_for("kern_mega:", 240)
        print("running: DISPLAY=%s, E9 in %s" % (DISPLAY, box.e9))


if __name__ == "__main__":
    main()
