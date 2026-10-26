#!/usr/bin/env python3
"""kern_mega under Bochs, behind MartyPC's `Marty` API - so a row written for
the 8088 runs on the protected-mode kernel unchanged (docs/BOCHS.md, "Rows
ported from MartyPC").

    OS88_MEGA=1 python3 tests/<row>.py

`os88marty.launch()` answers a `BochsMarty` instead of a MartyPC connection
when $OS88_MEGA is set, and everything above it - os88ui, os88mouse, every
`os88marty.until`/`ui_done`/`settle` - runs on top of it as it stands,
because the shim is a SERVER rather than a wrapper: `Marty` is built on one
method, `cmd(**kw)`, the debug server's request/reply, and this class
answers those requests itself out of a Bochs (tools/os88bochs.py's Box) and
its debugger. So `type_text`, `ctrl`, `readseg`, `bp_exec`, `go`,
`wait_stop` and `advance` are MartyPC's own code over this transport.

WHAT IT MAPS, AND WHAT IT CANNOT
  * the disks: any system floppy (os8088*.img, small*.img) becomes
    build/mega.img and any shipped apps floppy (apps*.img) build/megaapps.img
    - kern_mega has one system disk and one apps disk, at 1.44MB. Any other
    image (a category disk, a scratch disk a row built) goes in B: as it is.
  * the machine: always Bochs's 386, a VGA, a PS/2 mouse, 16MB. A machine
    name with `_sb` in it gets the SB16. An adapter, a ROM or a clock card in
    the name is ignored - a row whose subject is one of those is not a row to
    port.
  * the clock: Bochs runs `clock: sync=realtime`, so a guest second IS a host
    second here. `status()["cycles"]` is the guest's RUNNING time at 4.77MHz,
    so every guest budget in os88marty means the same number of seconds of
    machine time it means on MartyPC. Nothing measured in cycles is a
    measurement here.
  * memory: `read`/`write` are LINEAR (paging is off). `readseg(seg, off)`
    takes a REAL segment or an LDT SELECTOR - under kern_mega every package
    region and heap claim is a selector, so a segment a row reads out of the
    guest is one, and its base is looked up in the descriptor. A row that
    does `seg << 4` itself has to call `m.lin(seg, off)` instead.
  * the glass: `fbuf()` is a screenshot of the Bochs window's guest area,
    which lags the framebuffer by one VGA update (`vga: update_freq`, raised
    to 20 here). `screen()` reads a text mode's cells out of B8000.
  * breakpoints: `exec`/`execseg` are Bochs `lb` (linear). `mem`, `int` and
    `io` are refused - Bochs has watchpoints but not MartyPC's semantics.
  * refused outright, by name: `flicker`, `pace`, `planes`, `inb`/`outb`,
    `snapshot`/`restore`. `reset` is a POWER CYCLE (_c_reset). A row
    built on one of those is not portable and says so in its first second.
"""
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import os88bochs as ob         # noqa: E402
import os88marty as om         # noqa: E402

GUEST_HZ = om.GUEST_HZ
_WIDEN = bytes(v | v >> 6 for v in range(256))

# W3C KeyboardEvent.code (MartyKey's names) -> X keysym
_KEYS = {
    "Enter": "Return", "Escape": "Escape", "Backspace": "BackSpace",
    "Tab": "Tab", "Space": "space", "ArrowUp": "Up", "ArrowDown": "Down",
    "ArrowLeft": "Left", "ArrowRight": "Right", "Home": "Home", "End": "End",
    "PageUp": "Prior", "PageDown": "Next", "Insert": "Insert",
    "Delete": "Delete", "ShiftLeft": "Shift_L", "ShiftRight": "Shift_R",
    "ControlLeft": "Control_L", "ControlRight": "Control_R",
    "AltLeft": "Alt_L", "AltRight": "Alt_R", "CapsLock": "Caps_Lock",
    "NumLock": "Num_Lock", "ScrollLock": "Scroll_Lock",
    "Minus": "minus", "Equal": "equal", "BracketLeft": "bracketleft",
    "BracketRight": "bracketright", "Backslash": "backslash",
    "Semicolon": "semicolon", "Quote": "apostrophe", "Backquote": "grave",
    "Comma": "comma", "Period": "period", "Slash": "slash",
    "NumpadEnter": "KP_Enter", "NumpadAdd": "KP_Add",
    "NumpadSubtract": "KP_Subtract", "NumpadMultiply": "KP_Multiply",
    "NumpadDivide": "KP_Divide", "NumpadDecimal": "KP_Decimal",
    "PrintScreen": "Print", "Pause": "Pause",
}


def keysym(name):
    if name in _KEYS:
        return _KEYS[name]
    if name.startswith("Key") and len(name) == 4:
        return name[3].lower()
    if name.startswith("Digit") and len(name) == 6:
        return name[5]
    if name.startswith("Numpad") and name[6:].isdigit():
        return "KP_" + name[6:]
    if re.match(r"F\d{1,2}$", name):
        return name
    raise om.MartyError("os88bochsmarty: no X keysym for MartyKey %r" % name)


# --- the disks --------------------------------------------------------------

def mega_images(image, apps):
    """(A:, B:) for a row's (system, apps) pair: see the module note. Only
    the SHIPPED images in build/ itself are swapped - a scratch disk a row
    made (`tmp/apps.img`, built out of a shipped one with its own files on
    it) goes in as it is, because what is on it is the row's subject."""
    bld = os.environ.get("OS88_MEGA_BUILD") or os.path.join(ROOT, "build")

    def shipped(p):
        return p and os.path.realpath(os.path.dirname(os.path.abspath(p))) \
            == os.path.realpath(os.path.join(ROOT, "build"))
    a = os.environ.get("OS88_MEGA_A") or image
    if not os.environ.get("OS88_MEGA_A") and (
            not image or (shipped(image) and re.match(
                r"(os8088|small)[-\w]*\.img$", os.path.basename(image)))):
        a = os.path.join(bld, "mega.img")
    b = apps
    if apps and shipped(apps) and re.match(r"apps(360|720|120)?\.img$",
                                           os.path.basename(apps)):
        b = os.path.join(bld, "megaapps.img")
    return a, b


# --- the machine ------------------------------------------------------------

class BochsMarty(om.Marty):
    """`Marty` with the debug server replaced by Bochs: see the module note.
    `m.box` is the os88bochs.Box underneath, for anything only Bochs has."""

    bochs = True

    def __init__(self, box, run_dir, label=None):
        # NOT Marty.__init__: there is no socket. Everything Marty's methods
        # touch is set here.
        self.box = box
        self.run_dir = run_dir
        self.addr = "bochs%s" % box.display
        self.port = None
        self.pid = box.p.pid
        self._proc = box.p
        self._rec = None
        self._lock = threading.RLock()
        self._log = []
        self._go = None
        self._pumping = 0
        self._planes_verb = False
        self._pipeline = False
        self.label = label
        # the machine's state, kept HERE: Bochs answers nothing between stops
        self._state = "running"
        self._stops = 0
        self._cyc = 0.0             # guest seconds run before _since
        self._since = time.time()   # running since (None while stopped)
        self._bps = {}              # bochs bp number -> linear
        self._bpmark = os.path.getsize(box.e9)   # e9 offset of the last resume
        self._at = (0, 0, 0)        # cs, ip, flat ip of the last stop
        self._btn = set()
        self._keys = set()          # keysyms a row holds down (_c_key)
        self._ldt = None
        self._tmp = tempfile.mkdtemp(prefix="bxm", dir=run_dir)
        self._closed = False

    # ---- the clock --------------------------------------------------------
    def _cycles(self):
        run = self._cyc + ((time.time() - self._since)
                           if self._since is not None else 0.0)
        return int(run * GUEST_HZ)

    # ---- the debugger channel -------------------------------------------
    def _e9(self, start):
        return ob._tail(self.box.e9, start)

    def _bp_hit(self):
        """A stop Bochs made by ITSELF since the last resume: a breakpoint.
        Read off the transcript, so asking costs no stop."""
        if self._state != "running" or not self._bps:
            return False
        t = self._e9(self._bpmark)
        if not ob._PROMPT.search(t):
            return False
        self._stopped_now("breakpoint", t)
        return True

    def _stopped_now(self, why, text=""):
        if self._since is not None:
            self._cyc += time.time() - self._since
            self._since = None
        self._state = why
        self._stops += 1
        m = None
        for m in re.finditer(r"\[0x([0-9a-f]+)\] ([0-9a-f]{4}):([0-9a-f]+)",
                             text):
            pass
        if m:
            self._at = (int(m.group(2), 16), int(m.group(3), 16) & 0xFFFF,
                        int(m.group(1), 16))
        if self.box.captured:
            self.box.inp.regrab = True

    def _halt(self):
        """Stop the guest at the debugger's prompt (no-op if stopped). The
        transcript is read from the last RESUME, not from the signal: a
        breakpoint that fires between the check and the SIGINT is a prompt
        already printed, and the signal is then lost at it - so the stop is
        whichever prompt comes first, and a `Breakpoint` line says which."""
        if self._state != "running" or self._bp_hit():
            return
        gap = self.box.inp.last + ob.INPUT_GAP - time.time()
        if gap > 0:
            time.sleep(gap)
        end, kick = time.time() + 20, time.time() + 1.0
        os.kill(self.box.p.pid, signal.SIGINT)
        nap = 0.002
        while True:
            t = self._e9(self._bpmark)
            if ob._PROMPT.search(t) and t.rstrip(" ").endswith(">"):
                break
            if time.time() > kick:
                os.kill(self.box.p.pid, signal.SIGINT)
                kick = time.time() + 1.0
            if time.time() > end:
                raise om.MartyError("os88bochsmarty: no debugger prompt in 20s"
                                    " - Bochs on %s is gone or wedged"
                                    % self.box.display)
            time.sleep(nap)
            nap = min(nap * 2, 0.02)
        self._stopped_now("breakpoint" if re.search(r"Breakpoint \d+,", t)
                          else "paused", t)

    def _do(self, cmds, timeout=30.0):
        """Run debugger commands on a STOPPED guest; their transcript."""
        if not cmds:
            return ""
        e9 = self.box.e9
        n = os.path.getsize(e9)
        with open(os.path.join(self.box.out, "dbg.fifo"), "w") as fh:
            fh.write("\n".join(cmds) + "\n")
        end, nap = time.time() + timeout, 0.002
        while True:
            t = self._e9(n)
            if (len(ob._PROMPT.findall(t)) >= len(cmds)
                    and t.rstrip(" ").endswith(">")):
                return t
            if time.time() > end:
                raise om.MartyError("os88bochsmarty: %r had no answer in %.0fs"
                                    % (cmds[0], timeout))
            time.sleep(nap)
            nap = min(nap * 2, 0.02)

    def _resume(self):
        if self._state == "running":
            return
        e9 = self.box.e9
        n = os.path.getsize(e9)
        with open(os.path.join(self.box.out, "dbg.fifo"), "w") as fh:
            fh.write("c\n")
        end, base, mark = time.time() + 10, max(0, n - 4), None
        while time.time() < end:        # until Bochs has READ it (its echo):
            i = self._e9(base).find("c\n")     # a SIGINT before that is
            if i >= 0:                          # lost at the prompt
                mark = base + i + 2
                break
            time.sleep(0.002)
        # THE MARK IS THE ECHO, NOT THE FILE'S SIZE when the echo was seen:
        # a breakpoint a few instructions on prints its stop and its next
        # prompt before this loop looks again, and a mark taken past them
        # hides that stop - _halt then SIGINTs a debugger already at its
        # prompt and waits 20s for one that never comes
        self._bpmark = mark if mark is not None else os.path.getsize(e9)
        self._state = "running"
        self._since = time.time()

    def _stopped(self, cmds, timeout=30.0):
        """CMDS with the guest stopped for them, left as it was found."""
        with self._lock:
            if self._state == "running" and not self._bp_hit():
                self._halt()
                if self._state == "paused":
                    try:
                        return self._do(cmds, timeout)
                    finally:
                        self._resume()
                        # a stop made only for a read is not a stop a
                        # caller waits on: take it back out of the count
                        self._stops -= 1
            return self._do(cmds, timeout)

    # ---- memory -----------------------------------------------------------
    def _read(self, addr, n):
        if n <= 64:
            got = ob.xp_bytes(self._stopped(["xp /%dbx 0x%x" % (n, addr)]))
            b = got.get(addr, b"")
        else:
            f = os.path.join(self._tmp, "r.bin")
            if os.path.exists(f):
                os.remove(f)
            self._stopped(['writemem "%s" 0x%x %d' % (f, addr, n)])
            with open(f, "rb") as fh:
                b = fh.read()
        if len(b) < n:
            raise om.MartyError("os88bochsmarty: read 0x%x came back %d of %d"
                                " bytes" % (addr, len(b), n))
        return b[:n]

    def _write(self, addr, data):
        cmds, i = [], 0
        while i < len(data):
            k = 4 if len(data) - i >= 4 else 1
            v = int.from_bytes(data[i:i + k], "little")
            cmds.append("setpmem 0x%x %d 0x%x" % (addr + i, k, v))
            i += k
        for j in range(0, len(cmds), 64):
            self._stopped(cmds[j:j + 64])
        return len(data)

    def ldt_base(self):
        if self._ldt is None:
            t = self._stopped(["sreg"])
            m = re.search(r"ldtr:0x[0-9a-f]+, dh=(0x[0-9a-f]+), "
                          r"dl=(0x[0-9a-f]+)", t)
            if not m:
                raise om.MartyError("os88bochsmarty: no LDTR in `sreg`")
            dh, dl = int(m.group(1), 16), int(m.group(2), 16)
            self._ldt = ((dl >> 16) | ((dh & 0xFF) << 16) | (dh & 0xFF000000),
                         (dl & 0xFFFF) | (dh & 0xF0000))
        return self._ldt

    def selector(self, sel):
        """(base, limit) of LDT selector SEL, or None when SEL is not a
        present LDT data/code descriptor - a real segment."""
        if not sel & 4:
            return None
        base, limit = self.ldt_base()
        if (sel & ~7) + 7 > limit:
            return None
        d = self._read(base + (sel & ~7), 8)
        if not d[5] & 0x80 or not d[5] & 0x10:     # present, code/data
            return None
        return (d[2] | d[3] << 8 | d[4] << 16 | d[7] << 24,
                d[0] | d[1] << 8 | (d[6] & 0x0F) << 16)

    def lin(self, seg, off=0):
        """The linear address of SEG:OFF, SEG a real segment or a selector."""
        s = self.selector(seg)
        return (s[0] if s else seg << 4) + off

    def readseg(self, seg, off, length):
        return self.read(self.lin(seg, off), length)

    def sym(self, name, defines=()):
        """Marty.sym, plus WHERE kern_mega RUNS `.cold` and `.mega`: once
        mega_coldup has copied them above 1MB (`[mega_codehi]` = 1) the rung
        os88sym names is heap, so a `.cold` or `.mega` label is
        `[mega_coldlin]` + its distance from COLD_RAM - the two are one
        block, `.mega` at COLD_PARA paragraphs (kernel/mega.inc
        mega_coldup, mega_hilin). Without this a breakpoint on any `.cold`
        routine (dsk_xfer, the file layer) is set on bytes nothing runs."""
        import os88sym
        addr = om.Marty.sym(self, name, defines)
        try:
            sect = os88sym.sections(defines).get(name)
        except Exception:
            return addr
        if sect not in (".cold", ".mega"):
            return addr
        if not self.read(os88sym.linear("mega_codehi", defines), 1)[0]:
            return addr
        eq = os88sym.equates(defines)
        hi = int.from_bytes(self.read(os88sym.linear("mega_coldlin",
                                                     defines), 4), "little")
        return hi + addr - eq["COLD_RAM"] * 16

    # ---- the glass --------------------------------------------------------
    def _window(self):
        w = getattr(self, "_win", None)
        if w is None:
            r = subprocess.run(["xdotool", "search", "--name", "Bochs"],
                               env=self.box.env, capture_output=True,
                               text=True).stdout.split()
            if not r:
                raise om.MartyError("os88bochsmarty: no Bochs window")
            self._win = w = r[0]
        return w

    def _fbuf(self):
        """(w, h, rgb24) of the guest's display, out of the Bochs window."""
        time.sleep(ob.GLASS)
        raw = subprocess.run(["xwd", "-silent", "-id", self._window()],
                             env=self.box.env, capture_output=True,
                             check=True).stdout
        hsz = int.from_bytes(raw[0:4], "big")
        W, H = (int.from_bytes(raw[16:20], "big"),
                int.from_bytes(raw[20:24], "big"))
        bpl = int.from_bytes(raw[48:52], "big")
        ncol = int.from_bytes(raw[76:80], "big")
        px = raw[hsz + ncol * 12:]
        # THE GUEST AREA: `xwd -id` takes the window with its 4-pixel X
        # border, and Bochs's x GUI draws a 32-pixel headerbar above the
        # guest's display and an 18-pixel status bar under it (measured on
        # this build: a 640x480 desktop is a 648x538 dump, white from row 36
        # to row 515). The display is exactly as wide as the window.
        bd, top, bot = 4, 32, 18
        w, h = W - 2 * bd, H - 2 * bd - top - bot
        out = bytearray(w * h * 3)
        for y in range(h):
            o0 = (bd + top + y) * bpl + bd * 4
            row = px[o0:o0 + w * 4]
            o = y * w * 3
            out[o:o + w * 3:3] = row[2::4]
            out[o + 1:o + w * 3:3] = row[1::4]
            out[o + 2:o + w * 3:3] = row[0::4]
        # THE DAC'S SIX BITS, widened the way a VGA's are read: Bochs shifts
        # them left two (white is FC), MartyPC and every palette in tests/
        # fill the low bits (FF, AA, 55) - so v | v >> 6
        return w, h, bytes(out).translate(_WIDEN)

    # ---- the server -------------------------------------------------------
    def cmd(self, **kw):
        c = kw.pop("cmd")
        f = getattr(self, "_c_" + c, None)
        if f is None:
            raise om.MartyError(
                "`%s` is a MartyPC instrument the kern_mega Bochs shim does not"
                " have (tools/os88bochsmarty.py) - this row is not portable "
                "as it stands" % c)
        with self._lock:
            r = f(**kw)
        r = dict(r or {})
        r["ok"] = True
        return r

    def _status(self):
        self._bp_hit()
        cs, ip, flat = self._at
        return {"state": self._state, "cycles": self._cycles(),
                "stops": self._stops, "cs": cs, "ip": ip, "flat_ip": flat}

    def _c_ping(self, **_):
        return {"pipeline": False}

    def _c_status(self, **_):
        return self._status()

    def _c_read(self, addr, len, **_):          # noqa: A002
        return {"data": self._read(addr, len).hex()}

    def _c_write(self, addr, data, **_):
        return {"written": self._write(addr, bytes.fromhex(data))}

    def _c_run(self, **_):
        self._bp_hit()
        frm = self._stops
        self._resume()
        st = self._status()
        st["resumed_from"] = frm
        return st

    def _c_pause(self, **_):
        self._halt()
        return self._status()

    def _c_step(self, n=1, over=False, **_):
        self._halt()
        t = self._do(["%s %d" % ("n" if over else "s", n)])
        self._stopped_now("paused", t)
        return self._status()

    def _c_advance(self, frames=None, cycles=None, card=None, **_):
        secs = (cycles / GUEST_HZ if cycles is not None else
                (frames or 1) / 60.0)
        self._bp_hit()
        self._resume()
        end = time.time() + secs
        while time.time() < end:
            if self._bp_hit():
                return self._status()
            time.sleep(min(0.01, max(0.0, end - time.time())))
        self._halt()
        return self._status()

    def _c_bp(self, list, **_):                 # noqa: A002
        was = self._state
        cmds = ["d %d" % n for n in self._bps]
        want = []
        for b in list:
            t = b.get("type")
            if t == "exec":
                want.append(int(b["addr"]))
            elif t == "execseg":
                want.append(self.lin(int(b["seg"]), int(b["off"])))
            else:
                raise om.MartyError("os88bochsmarty: a %r breakpoint is not "
                                    "available on Bochs" % t)
        with self._lock:
            if self._state == "running":
                self._halt()
                if self._state == "paused":
                    self._stops -= 1
                else:
                    was = self._state       # a breakpoint got there first
            self._do(cmds) if cmds else None
            self._bps = {}
            if want:
                t = self._do(["lb 0x%x" % a for a in want] + ["blist"])
                for m in re.finditer(r"^\s*(\d+) lbreakpoint\s+keep y\s+"
                                     r"0x([0-9a-f]+)", t, re.M):
                    self._bps[int(m.group(1))] = int(m.group(2), 16)
            if was == "running":
                self._resume()
        return {"count": len(want)}

    def _c_regs(self, **_):
        t = self._stopped(["r", "sreg"])
        r = {}
        for name, val in re.findall(r"^r([a-z0-9]{1,2})\s*: ([0-9a-f_]+)$",
                                    t, re.M):
            v = int(val.replace("_", ""), 16)
            if name in ("ax", "bx", "cx", "dx", "sp", "bp", "si", "di",
                        "ip"):
                r[name] = v & 0xFFFF
        m = re.search(r"eflags 0x([0-9a-f]+)", t)
        if m:
            r["flags"] = int(m.group(1), 16) & 0xFFFF
        for s, v in re.findall(r"^(es|cs|ss|ds|fs|gs):0x([0-9a-f]+)", t,
                               re.M):
            r[s] = int(v, 16)
        return r

    def _c_setreg(self, reg, value, **_):
        reg = {"flags": "eflags", "ip": "eip"}.get(reg, reg)
        self._stopped(["set %s = 0x%x" % (reg, value)])
        return {}

    def _c_park(self, cs, ip, **_):
        """MartyPC's `park`: the CPU to CS:IP on a stopped machine (a row
        calling a kernel routine on the paused guest, tests/desklayer.py's
        top_i). Bochs's `set` takes a selector into CS as it stands"""
        self._halt()
        cmds = ["set eip = 0x%x" % ip]
        if cs != self._at[0]:
            cmds.insert(0, "set cs = 0x%x" % cs)
        t = self._do(cmds)
        self._at = (cs, ip, self._at[2])
        return {}

    def _c_key(self, key, down=True, up=True, **_):
        k = keysym(key)
        if not self.box.captured:   # a key before any mouse event: until
            self.box.capture()      # the window has the focus it is lost
        if down and up:
            self._xd("key", "--delay", 40, k)
        elif down:
            self._xd("keydown", k)
            self._keys.add(k)
        elif up:
            self._xd("keyup", k)
            self._keys.discard(k)
        self._log.append({"cycles": self._cycles(), "kind": "key",
                          "args": {"key": key, "down": down, "up": up}})
        return {"cycles": self._cycles()}

    def _xd(self, *a):
        """xdotool on the machine's display, keeping a HELD Ctrl held: the
        re-capture after a debugger stop (os88bochs.GRAB) is Ctrl + middle
        click and lets Ctrl go, so a row holding ControlLeft across a read
        (msel's Ctrl+click, any Ctrl+key) lost it at its next event"""
        if self.box.inp.regrab:
            held = [k for k in ("Control_L", "Control_R") if k in self._keys]
            if held:
                a = sum((("keydown", k) for k in held), ()) + a
        self.box.xd(*a)

    def _c_mouse(self, dx=0, dy=0, l=False, r=False, wz=0, **_):
        if wz:
            raise om.MartyError("os88bochsmarty: no wheel on Bochs's PS/2 "
                                "mouse")
        if not self.box.captured:
            self.box.capture()
        if dx or dy:
            # TWO X PIXELS A GUEST PIXEL, measured (os88bochs.Box.goto) -
            # a serial packet's dx is in mickeys at the same ratio
            self._xd("mousemove_relative", "--", 2 * dx, 2 * dy)
        for want, btn in ((l, 1), (r, 3)):
            if want and btn not in self._btn:
                self._xd("mousedown", btn)
                self._btn.add(btn)
            elif not want and btn in self._btn:
                self._xd("mouseup", btn)
                self._btn.discard(btn)
        return {"cycles": self._cycles()}

    def _video(self):
        """What mode the card is in, from the BIOS data area's mode byte and
        the window's own size - enough for Marty's callers."""
        try:
            mode = self._read(0x449, 1)[0]
        except om.MartyError:
            mode = 0x12
        text = mode in (0, 1, 2, 3, 7)
        return {"type": "vga", "primary": True, "mode": "Mode%02X" % mode,
                "graphics": not text, "field_w": 800, "field_h": 524,
                "frames": 1}

    def _c_video(self, card=None, **_):
        return self._video()

    def _c_cards(self, **_):
        return {"cards": [self._video()]}

    def _c_screen(self, card=None, **_):
        v = self._video()
        if v["graphics"]:
            return {"rows": []}
        return {"rows": self._vga_text(v)}

    def _c_fbuf(self, aperture=0, card=None, **_):
        w, h, data = self._fbuf()
        return {"w": w, "h": h, "data": data.hex()}

    def _c_disk(self, reset=False, **_):
        """MartyPC's FDC counters, out of Bochs's own floppy log (`debug:
        floppy=report`, which Box(flog=True) turns on): a READ or WRITE
        command the controller completed is one `<<READ DONE>>` or
        `<<WRITE DONE>>` line. Read incrementally, so asking is cheap."""
        log = os.path.join(self.box.out, "bochs.log")
        pos, cnt = getattr(self, "_flog", (0, [0, 0]))
        try:
            with open(log, "rb") as f:
                f.seek(pos)
                t = f.read()
        except OSError:
            t = b""
        cut = t.rfind(b"\n") + 1
        cnt[0] += t[:cut].count(b"<<READ DONE>>")
        cnt[1] += t[:cut].count(b"<<WRITE DONE>>")
        self._flog = (pos + cut, cnt)
        r = {"reads": cnt[0], "writes": cnt[1]}
        if reset:
            cnt[0] = cnt[1] = 0
        return r

    def _c_reset(self, **_):
        """MartyPC's machine reset, as a POWER CYCLE: Bochs's debugger has
        no reset, so this one is stopped and a new one booted on the SAME
        display from the disks as the guest left them (Bochs writes a
        floppy straight through). The breakpoints are re-armed in the new
        one; the guest is left RUNNING, which `reset(); run()` expects.
        SYSTEM.CFG is not re-injected - what the guest wrote is the point
        of a reboot row."""
        kw = dict(self._boxkw, cfg=None)
        keep = tempfile.mkdtemp(prefix="reset", dir=self.run_dir)
        for n in ("a.img", "b.img"):
            shutil.copy(os.path.join(self.box.out, n), os.path.join(keep, n))
        bps = list(self._bps.values())
        try:
            for b in sorted(self._btn):
                self.box.xd("mouseup", b)
        except Exception:                                   # noqa: BLE001
            pass
        self.box.stop()
        kw.update(aimg=os.path.join(keep, "a.img"),
                  bimg=os.path.join(keep, "b.img"))
        self.box = ob.Box(self.run_dir, [], **kw)
        self.pid = self.box.p.pid
        self._proc = self.box.p
        self._btn, self._keys, self._bps = set(), set(), {}
        self._ldt, self._win, self._flog = None, None, (0, [0, 0])
        self._state, self._since = "running", time.time()
        _first_c(self.box)
        self._bpmark = os.path.getsize(self.box.e9)
        if bps:
            self._c_bp([{"type": "exec", "addr": a} for a in bps])
        shutil.rmtree(keep, ignore_errors=True)
        return self._status()

    def boot_toast(self, limit=10.0):
        """Retire kern_mega's boot toast (`Entered protected mode`,
        mega_mtoast): it is staged at the switch, armed by ui_task's first
        passes for EIGHT seconds, and a row that waits for "a toast" after
        its first act reads it as the answer - while a row comparing the
        menu bar before and after something sees it go. os88marty's
        kernel_up and os88ui's UI.up call this when the machine has it.

        It is waited for (the switch can come after the desktop gate), and
        once it is up it is EXPIRED by its own path - [toast_die] wound
        back, toast_pass's modular compare taking it down, as
        tests/toastbar.py does - rather than waited out."""
        import os88sym
        on, buf = os88sym.linear("toast_on"), os88sym.linear("toast_buf")
        die, ticks = os88sym.linear("toast_die"), os88sym.linear("ticks")
        end = time.time() + limit
        seen = False
        while time.time() < end:
            up = self.read(on, 1)[0]
            ours = self.read(buf, 8).startswith(b"Entered")
            if seen and not up:
                return
            if up and not ours:
                return                  # something else is being said
            if up and ours and not seen:
                t = int.from_bytes(self.read(ticks, 2), "little")
                self.write(die, ((t - 2) & 0xFFFF).to_bytes(2, "little"))
                seen = True
            time.sleep(0.1)

    def _c_quit(self, **_):
        self.close()
        return {}

    # Marty.screen falls back to _vga_text via `video`, which reads B8000
    def video(self, card=None):
        return self._video()

    def disks(self):
        return [{"drive": 0, "path": self.box.out + "/a.img"},
                {"drive": 1, "path": self.box.out + "/b.img"}]

    def flush(self, drive=0, path=None, fmt="raw"):
        """Bochs writes a floppy straight through to its image file, so the
        image IS the disk: copy it out."""
        src = os.path.join(self.box.out, "a.img" if drive == 0 else "b.img")
        if path:
            shutil.copy(src, path)
        return {"path": path or src}

    def wait_for(self, text, secs):
        return self.box.wait_for(text, secs)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            for b in sorted(self._btn):
                self.box.xd("mouseup", b)
        except Exception:
            pass
        try:
            self.box.stop()
        finally:
            if not os.environ.get("OS88_MEGA_KEEP"):
                shutil.rmtree(self.run_dir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


_ENV_DISP_USED = False


def _first_c(box):
    """UNTIL BOCHS HAS TAKEN ITS FIRST `c`: it starts at the debugger's
    prompt, and a SIGINT that lands before that `c` is read is lost"""
    end = time.time() + 60
    while not re.search(r"<bochs:1> c", ob._tail(box.e9, 0)):
        if time.time() > end or box.p.poll() is not None:
            raise om.MartyError("os88bochsmarty: Bochs never started (%s)"
                                % os.path.join(box.out, "bochs.log"))
        time.sleep(0.05)


def launch(image, apps=None, machine="", boot=True, label=None, extra=(),
           sb=None, cfg=None, megs=None, **_):
    """os88marty.launch's shape, on Bochs and kern_mega (see the module
    note). `boot` True waits for the desktop (os88bochs.Box.up's state gate,
    then a settle of the glass); a number runs blind for that many seconds;
    False hands the machine back PAUSED, as MartyPC's does."""
    a, b = mega_images(image, apps)
    bld = os.environ.get("OS88_MEGA_BUILD") or os.path.join(ROOT, "build")
    base = os.path.join(ROOT, "build", "bochs", "inst")
    os.makedirs(base, exist_ok=True)
    tag = re.sub(r"\W+", "", label or os.path.splitext(
        os.path.basename(sys.argv[0] or "row"))[0])[:24]
    run_dir = tempfile.mkdtemp(prefix="%s-" % tag, dir=base)
    # THE RUNNER'S DISPLAY for this row's first machine (tools/os88test.py
    # holds one per Bochs row, $OS88_BOCHS_DISPLAY); any further machine in
    # the same process takes one of its own
    global _ENV_DISP_USED
    disp = os.environ.get("OS88_BOCHS_DISPLAY")
    if not disp or _ENV_DISP_USED or ob.running(disp):
        disp = ob.take_display()
    else:
        _ENV_DISP_USED = True
    if sb is None:
        sb = "_sb" in (machine or "")
    if not b:
        b = os.path.join(bld, "megaapps.img")
    btype = {368640: "360k", 737280: "720k", 1228800: "1_2",
             1474560: "1_44"}[os.path.getsize(b)]
    box_btype = "1_2" if btype in ("360k", "1_2") else "1_44"
    box = ob.Box(run_dir, [], sb=sb, cfg=cfg, bimg=b, aimg=a,
                 btype=box_btype,
                 build=bld, display=disp, megs=megs, noc=True, vgahz=20, flog=True)
    m = BochsMarty(box, run_dir, label=label)
    m._boxkw = dict(sb=sb, cfg=cfg, btype=box_btype, build=bld,
                    display=disp, megs=megs, noc=True, vgahz=20, flog=True)
    try:
        _first_c(box)
        m._bpmark = os.path.getsize(box.e9)
        if boot is False or boot == 0:
            m._c_pause()
            return m
        if boot is True:
            box.up()
            box.capture()
            m.boot_toast()
            return m
        time.sleep(float(boot))
        return m
    except BaseException:
        m.close()
        raise
