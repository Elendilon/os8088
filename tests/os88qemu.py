#!/usr/bin/env python3
"""The teardown every QEMU launcher in `tests/` owes, written ONCE.

WHY THIS FILE EXISTS.  A row that FAILS used to leave its emulator running.
`make test` daemonises QEMU and returns, so the process outlives the script
that started it, and the only thing that ever killed one was the NEXT run's
kill-stale — which reaches an instance in the same checkout with the same
pidfile, and nothing else.

Measured, and it is what put this here: two `qemu-system-i386` processes
**five hours old**, left by two `trkscrl` classification runs in two different
worktrees, still holding `build/os8088.img`.  The bill landed on `ps2mouse`,
which launches with a pidfile of its own and so had never had a chance to kill
them:

    qemu-system-i386: Failed to get "write" lock
    Is another process using the image [build/os8088.img]?

`ps2mouse` passed the moment they were killed.  **The cost of the leak is paid
by an unrelated row, hours later, wearing a message about the wrong subject** —
which is the expensive kind of failure, and a leaked emulator is
the account of it.  CLAUDE.md documents the same leak from the other end: a
previous session's instance still answering on `build/qmp.sock` and serving the
OLD kernel, which reads exactly like a change that did nothing.

`atexit` AND NOT A `finally` IN `main()`, which is what the two files that got
this right already use.  A `finally` covers what is inside its own `try`, and
these scripts raise `SystemExit` from helpers, run work at module level
(`tests/sbar.py` opens its machine inside an `if` at the top level), and die on
exceptions raised while a launcher is still being set up.  `atexit` covers all
of that, and it is one line at the launch site rather than a restructuring of
twelve `main()`s.  It does NOT cover `SIGKILL` or `os._exit`, and nothing can.
"""
import atexit
import os
import signal
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIDFILE = os.path.join(ROOT, "build", "qemu.pid")
SOCK = os.environ.get("QMP_SOCK", os.path.join(ROOT, "build", "qmp.sock"))


def kill(pidfile=PIDFILE, sock=SOCK, wait=1.0):
    """Stop the instance named by `pidfile`, and clear its files.

    **BY PIDFILE, NEVER BY `pkill -f`.**  `-f` matches the killing shell's own
    command line, so a command that names the emulator kills itself: exit 144,
    no error text, nothing dead, and every command after it silently skipped.
    That is why no file in this tree writes `qemu-system-i386` whole on a
    command line, and why this one does not either.

    Silent about everything: a pidfile naming a process that has already gone
    is the ordinary case on the success path, where the script has usually
    asked the guest to quit first.
    """
    if os.path.exists(pidfile):
        try:
            pid = int(open(pidfile).read().strip())
            os.kill(pid, signal.SIGTERM)
            gone(pid, wait)
        except Exception:                                       # noqa: BLE001
            pass
    for f in (sock, pidfile):
        if f and os.path.exists(f):
            try:
                os.unlink(f)
            except OSError:
                pass


def gone(pid, wait=1.0, most=10.0):
    """Wait for process `pid` to have EXITED - a HOST wait, on a host thing.

    It was `time.sleep(wait)` after the SIGTERM, which is a guess: the
    process that has not gone yet still holds the image's write lock, and
    the next launch then dies on `Failed to get "write" lock`. So this asks
    the process table instead, returning the moment it is gone and giving up
    at `max(wait, most)` seconds - still silently, as before.
    """
    end = time.monotonic() + max(wait, most)
    while time.monotonic() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return True
        # A ZOMBIE HAS EXITED: its files (the image's write lock) are closed,
        # and a daemonised QEMU's parent is PID 1, which here reaps ~1 s
        # later - measured 12 ms to exit, 1.0 s to vanish, every launch
        if _zombie(pid):
            return True
        time.sleep(0.01)
    return False


def _zombie(pid):
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[0] == "Z"
    except (OSError, IndexError):
        return False


def own(pidfile=PIDFILE, sock=SOCK):
    """Kill at exit whatever this script has just LAUNCHED.

    **Call it at the launch site and nowhere else.**  A script that DRIVES an
    instance somebody else started must not kill it — `tests/xmcheck.py` takes
    a socket on its command line and does exactly that, and killing another
    session's machine is the failure this file exists to prevent rather than
    to move.

    Idempotent: registering twice kills once, because the second call finds no
    pidfile.  Safe to call before the guest is up.

    AND IT CATCHES SIGTERM, because atexit alone is not enough: Python's
    default disposition for SIGTERM is the kernel's - the process is gone at
    once and no atexit runs - so a row that tools/os88test.py stops on a
    timeout would leave its guest running exactly as a SIGKILL did.  The
    handler raises SystemExit, which is the one path that runs the teardown
    registered above.  Installed only when no handler is already there, so a
    script with its own SIGTERM policy keeps it.
    """
    atexit.register(kill, pidfile, sock)
    try:
        if signal.getsignal(signal.SIGTERM) in (signal.SIG_DFL, None):
            signal.signal(signal.SIGTERM,
                          lambda signo, frame: sys.exit(128 + signo))
    except (ValueError, OSError):
        pass                            # not the main thread: atexit alone


# -----------------------------------------------------------------------------
# THE GUEST'S CLOCK, for every QEMU row. `make test` runs QEMU WITHOUT
# `-icount`, so there is no cycle counter to budget a wait in, and a
# `time.sleep` is a different amount of the machine at every load on the box.
# What there is, is the BIOS tick count at 0040:006C: IRQ0 advances it at
# 18.2 Hz, and only by running GUEST CODE (the ROM's int 08h, which the kernel
# chains, SPEC.md 8.5) - so a tick that has moved is proof the guest ran, and
# a budget counted in ticks is one a loaded box cannot shorten. It needs no
# symbol, so it is the same address under the kernel, DOS and a bare
# boot.
#
# `m` is any object with `read(linear, n)` - tests/ethernet.py's `Qemu`,
# tests/telansi.py's, tests/trkscrl.py's `Qmp`: each opens QMP per command.
# -----------------------------------------------------------------------------
BIOS_TICKS = 0x46C
TICK_HZ = 18.2065
STALL = 30.0            # HOST seconds of a clock that does not move = stopped
JUMP = 256              # a step bigger than this was SET, not counted


class GuestStopped(RuntimeError):
    """The guest's tick count stopped moving: the machine is not running."""


def ticks(m):
    """The low word of the BIOS tick count."""
    b = m.read(BIOS_TICKS, 2)
    return b[0] | (b[1] << 8)


def to_ticks(secs):
    """At LEAST `secs` of guest time, whatever phase the count is in."""
    return int(secs * TICK_HZ + 0.999) + 1


class Clock(object):
    """Guest ticks elapsed since construction, and a host-side stall watch.

    The low word is summed a step at a time rather than subtracted from the
    start, because the count is not a clean clock: the BIOS SETS it from the
    RTC during POST and clears it at midnight. So a step bigger than JUMP
    counts as one tick, never as thousands - a poll that lands across POST
    must not spend a whole budget at once.
    """

    def __init__(self, m):
        self.m = m
        self.last = ticks(m)
        self.n = 0
        self.seen = time.monotonic()

    def step(self):
        t = ticks(self.m)
        d = (t - self.last) & 0xFFFF
        if d:
            self.n += 1 if d > JUMP else d
            self.last, self.seen = t, time.monotonic()
        return self.n

    def secs(self):
        """Guest seconds so far - a deadline for a loop that reads as it goes."""
        return self.step() / TICK_HZ

    def stalled(self):
        return time.monotonic() - self.seen > STALL


def acted(m, cond, secs=6.0, what=None, poll=0.05):
    """Wait for `cond()` - budgeted in `secs` of the GUEST's time.

    Answers True the moment it holds and False once the guest has run `secs`
    without it (one last look is taken at the edge). A guest whose clock does
    not move for STALL host seconds is not slow, it has STOPPED, and that
    raises GuestStopped naming `what` rather than reporting it as the
    condition failing.
    """
    c = Clock(m)
    lim = to_ticks(secs)
    while True:
        if cond():
            return True
        if c.step() >= lim:
            return bool(cond())
        if c.stalled():
            raise GuestStopped("the guest's clock stopped (%s at 0040:006C "
                               "for %ds) while waiting for %s"
                               % (hex(c.last), STALL, what or "a condition"))
        time.sleep(poll)


def key(m, qcode, secs=10.0):
    """ONE KEY, as a keyboard sends it: the press, and the release only once
    the ROM has STORED the press - the BIOS buffer's tail (0040:001C) moved.

    HMP's `sendkey` queues the release a fixed 100 ms of HOST time after the
    press. A guest the host starves for longer than that - a loaded box -
    finds BOTH bytes waiting at its first IRQ1, and QEMU's 8042 loads the
    next queued byte the moment port 60h is read. So when SPEC.md 9.7's
    key-state map is armed, `kbm_isr`'s peek takes the press and the ROM
    reads the release: the keystroke is gone - two IRQ1s and nothing in the
    BIOS buffer (vidxiphdhold, the Video Player arming the map for
    Alt+Enter; 1 run in 4 at four lanes). A real keyboard cannot do that: it
    holds its next byte until the controller has been read and its clock
    released, about a millisecond. This is that pacing, on the guest's
    clock. QEMU's own IRQ count is NOT the signal - it counts the line being
    RAISED, which is the byte being queued, not the guest taking it.

    For a key the ROM stores nothing for (a shift key) the tail never moves,
    so that wait is bounded by `secs` of guest time and the release goes
    anyway; answers whether the tail moved."""
    import xmcheck
    ev = {"type": "key", "data": {"down": True,
                                  "key": {"type": "qcode", "data": qcode}}}
    t0 = m.read(0x41C, 2)
    xmcheck.qmp_exec(m.sock, "input-send-event", {"events": [ev]})
    took = acted(m, lambda: m.read(0x41C, 2) != t0, secs=secs,
                 what="the ROM to store %s's press" % qcode, poll=0.005)
    ev["data"]["down"] = False
    xmcheck.qmp_exec(m.sock, "input-send-event", {"events": [ev]})
    return took


def pace(m, secs, poll=0.02):
    """Spend `secs` of GUEST time - the wait for a pause with nothing to wait
    on (a gesture's spacing, a program left to run, a NEGATIVE case's "and
    nothing happened"). QEMU's clock follows the host's, so on an idle box
    this is what `time.sleep(secs)` was, rounded UP to whole ticks; on a
    loaded one it is still that much of the machine. A clock that stops ends
    the pause, as a sleep would have."""
    c = Clock(m)
    lim = to_ticks(secs)
    while c.step() < lim and not c.stalled():
        time.sleep(poll)


def poke(hmp, linear, data):
    """WRITE guest memory - which QEMU's monitor cannot do.

    HMP reads (`xp`, `pmemsave`) and has no write at all, so this borrows the
    one door QEMU has: its GDB stub. `gdbserver` starts one on a free local
    port at runtime (no relaunch, no `-s` in the Makefile), the remote
    protocol's `M` packet writes the bytes, and `D` detaches - which also
    RESUMES the guest the connection paused, so the write lands between two
    instructions with the machine stopped and every byte of `data` written at
    once. `gdbserver none` takes the stub down again. `hmp` is a callable
    taking one HMP command line (tests/thewire.py's `Qemu.hmp`). In real mode
    there is no paging, so the stub's address is the LINEAR one os88sym hands
    out. Raises on any answer but OK - a write that did not happen must not
    read as a test of what it would have done.
    """
    import socket
    s0 = socket.socket()
    s0.bind(("127.0.0.1", 0))
    port = s0.getsockname()[1]
    s0.close()
    hmp("gdbserver tcp:127.0.0.1:%d" % port)
    s = None
    for _ in range(50):
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=5)
            break
        except OSError:
            time.sleep(0.1)
    if s is None:
        raise RuntimeError("poke: no GDB stub on port %d" % port)
    buf = b""

    def packet(body):
        nonlocal buf
        b = body.encode("ascii")
        s.sendall(b"$" + b + b"#%02x" % (sum(b) & 0xFF))
        while True:                       # skip acks; read one $...#xx reply
            while b"#" not in buf or len(buf) < buf.index(b"#") + 3:
                got = s.recv(4096)
                if not got:
                    raise RuntimeError("poke: the GDB stub hung up")
                buf += got
            buf = buf.lstrip(b"+")
            if buf.startswith(b"$"):
                end = buf.index(b"#")
                reply, buf = buf[1:end], buf[end + 3:]
                s.sendall(b"+")
                return reply.decode("ascii", "replace")
            buf = buf[1:]                 # noise before a packet
    try:
        packet("?")                       # the stop reply: the guest is held
        r = packet("M%x,%x:%s" % (linear, len(data), bytes(data).hex()))
        if r != "OK":
            raise RuntimeError("poke: M at %#x answered %r" % (linear, r))
        packet("D")                       # detach: the guest runs on
    finally:
        s.close()
        hmp("gdbserver none")


def ui_idle(m, sym):
    """tools/os88marty.py's `ui_idle` on QEMU: ui_task ASLEEP (task 0's
    T_STATE is 2) with no event queued, no wake pending, the gfx lock free
    and the BIOS key ring empty - the UI has finished with everything it was
    given. `sym(name)` is the flat address of a kernel symbol
    (os88sym.linear). QEMU has no drive counter to watch as MartyPC does, and
    needs none: a load here runs inside ui_task's handler, which reads busy
    for as long as it lasts."""
    a = getattr(m, "_ui_idle_syms", None)
    if a is None:
        a = m._ui_idle_syms = (sym("sch_tasks"), sym("evq_count"),
                               sym("sch_uiwake"), sym("gfx_lock_flag"))
    if m.read(a[0], 1)[0] != 2:
        return False
    if m.read(a[1], 1)[0] or m.read(a[2], 1)[0] or m.read(a[3], 1)[0]:
        return False
    kb = m.read(0x41A, 4)
    return kb[0:2] == kb[2:4]


def ui_done(m, sym, cap=2.0, what=None):
    """Until `ui_idle` holds across two consecutive guest ticks, CAPPED at
    `cap` guest seconds - the fixed pause a caller used to spend, so no wait
    is ever longer than it was. Answers True if the UI went idle, False if
    the cap ran out first. A kernel this process cannot resolve takes the
    old pause."""
    try:
        ui_idle(m, sym)
    except (GuestStopped, OSError):
        raise
    except Exception:
        pace(m, cap)
        return False
    c = Clock(m)
    lim = to_ticks(cap)
    run, last = 0, None
    while True:
        n = c.step()
        if ui_idle(m, sym):
            if n != last:
                run += 1
                last = n
            if run >= 2:
                return True
        else:
            run, last = 0, None
        if n >= lim:
            return False
        if c.stalled():
            return False
        time.sleep(0.02)


def quiesce(m, read, secs=1.0, stable=2, limit=60.0, what=None, poll=0.1):
    """Wait until `read()` answers the same thing `stable` times running,
    `secs` of GUEST time apart - "until these bytes stop changing" (a block
    table, a listing, a counter). Answers the settled value; a value still
    moving after `limit` guest seconds answers the last one read, and the
    caller's own assertion then says what was wrong with it."""
    c = Clock(m)
    lim = to_ticks(limit)
    gap = max(1, int(secs * TICK_HZ + 0.5))
    last, same, mark = read(), 1, c.step()
    while same < stable:
        n = c.step()
        if n >= lim:
            break
        if c.stalled():
            raise GuestStopped("the guest's clock stopped while waiting for "
                               "%s to settle" % (what or "a value"))
        if n - mark >= gap:
            v = read()
            same = same + 1 if v == last else 1
            last, mark = v, n
        else:
            time.sleep(poll)
    return last


# --- a CLOSED-LOOP mouse (docs/plans/completed/SOAK-SPEED.md, harness changes) ---------
#
# tools/mouse.py cannot know where the pointer is, so it PINS against the
# bottom-right clamp and walks back, a host `sleep 0.06` after every packet,
# then holds each button edge 0.2 guest s: ~1.7 s a click, which was 88 of
# rdxms's 111 host seconds. A row that can resolve kernel symbols can do what
# tools/os88mouse.py does on MartyPC instead - read `mouse_x`/`mouse_y`/
# `mouse_btn` (kernel/mouse.inc, published by the ISR), send the exact delta,
# and wait for the word to MOVE rather than for a clock. The packet still goes
# through QEMU's msmouse, the UART and mou_isr: nothing is poked.

PKT_SECS = 0.5          # guest seconds a packet may take to land (it is ~25 ms
                        # at 1200 baud; the slack is a guest busy repainting)
STEP = 60               # msmouse truncates bigger deltas (tools/mouse.py)


class MouseError(RuntimeError):
    """The pointer did not get where it was sent, or a button edge was lost."""


def mouse_where(m, sym):
    """(x, y, buttons) as the kernel last published them."""
    a = getattr(m, "_mouse_at", None)
    if a is None:
        a = sym("mouse_x")
        if sym("mouse_y") != a + 2 or sym("mouse_btn") != a + 4:
            raise MouseError("mouse_x/mouse_y/mouse_btn are not contiguous "
                             "any more - mouse_where reads them as one block")
        m._mouse_at = a
    b = m.read(a, 5)
    return b[0] | (b[1] << 8), b[2] | (b[3] << 8), b[4]


def _changed(m, sym, was, what):
    c = Clock(m)
    lim = to_ticks(PKT_SECS)
    while True:
        if mouse_where(m, sym) != was:
            return True
        if c.step() >= lim or c.stalled():
            return False
        time.sleep(0.003)


def mouse_to(m, sym, hmp, x, y, btn=0):
    """Drive to (x, y) and PROVE it, carrying button level `btn` (an HMP
    move carries the current buttons). `hmp(*cmds)` sends human-monitor
    commands (xmcheck.qmp bound to the socket). Raises MouseError when the
    pointer stops short - a target off the kernel's clamp, or packets lost
    for longer than a busy guest explains."""
    cx, cy, _ = mouse_where(m, sym)
    tries = (max(abs(x - cx), abs(y - cy)) + STEP - 1) // STEP * 2 + 6
    for _ in range(tries):
        cx, cy, b = mouse_where(m, sym)
        dx, dy = x - cx, y - cy
        if not dx and not dy:
            return
        hmp("mouse_move %d %d" % (max(-STEP, min(STEP, dx)),
                                  max(-STEP, min(STEP, dy))))
        _changed(m, sym, (cx, cy, b), "the pointer to move")
    cx, cy, _ = mouse_where(m, sym)
    if (cx, cy) != (x, y):
        raise MouseError("could not reach (%d,%d): stuck at (%d,%d)"
                         % (x, y, cx, cy))


def mouse_button(m, sym, hmp, mask):
    """Set the buttons to `mask` (HMP's: 1 left, 2 right) and wait until the
    kernel has decoded that level - mouse_btn's bit 0 left, bit 1 right."""
    want = (1 if mask & 1 else 0) | (2 if mask & 2 else 0)
    for _ in range(3):
        hmp("mouse_button %d" % mask)
        c = Clock(m)
        lim = to_ticks(PKT_SECS)
        while c.step() < lim and not c.stalled():
            if mouse_where(m, sym)[2] & 3 == want:
                return
            time.sleep(0.003)
        if mouse_where(m, sym)[2] & 3 == want:
            return
    raise MouseError("the button level %d was never decoded (mouse_btn = %02x)"
                     % (want, mouse_where(m, sym)[2]))


def mouse_click(m, sym, hmp, x, y, mask=1):
    """to (x, y), press, release - each edge confirmed. No pause after: the
    caller's wait (ui_done, acted) is on the state the click is FOR."""
    mouse_to(m, sym, hmp, x, y)
    if mouse_where(m, sym)[2] & 3:
        mouse_button(m, sym, hmp, 0)
    mouse_button(m, sym, hmp, mask)
    mouse_button(m, sym, hmp, 0)


class Private(object):
    """A PRIVATE QEMU - what `make test TESTIMG=a TESTAPPS=b [TESTHD=hd]
    [ETHER=1]` launched, with its own socket, pidfile and COPIES of the
    floppies in `work`, so a row runs no `make` in the shared tree and never
    kills another row's emulator through build/qemu.pid. `ether` adds the
    NE2000 at 300h/IRQ3 on slirp, WITHOUT `make test`'s host forwards (a
    fixed host port is a collision between two rows). `.sock` is the QMP
    socket; `.close()` (also at exit) ends it by the pid it wrote."""

    def __init__(self, work, a, b, hd=None, ether=False, extra=()):
        import atexit
        import shutil
        import subprocess
        self.sock = os.path.join(work, "qmp.sock")
        pidf = os.path.join(work, "qemu.pid")
        self.a = os.path.join(work, "a.img")
        self.b = os.path.join(work, "b.img")
        shutil.copy(a, self.a)
        shutil.copy(b, self.b)
        cmd = ["qemu-system-i386", "-machine", "pc,vmport=off",
               "-drive", "file=%s,format=raw,if=floppy" % self.a,
               "-boot", "c" if hd else "a",
               "-chardev", "msmouse,id=m0", "-serial", "chardev:m0",
               "-drive", "file=%s,format=raw,if=floppy,index=1" % self.b]
        if hd:
            cmd += ["-drive", "file=%s,format=raw,if=ide,index=0,media=disk"
                    % hd]
        if ether:
            cmd += ["-netdev", "user,id=n0",
                    "-device", "ne2k_isa,netdev=n0,iobase=0x300,irq=3"]
        cmd += ["-display", "none", "-qmp", "unix:%s,server,nowait"
                % self.sock, "-daemonize", "-pidfile", pidf] + list(extra)
        subprocess.run(cmd, check=True)
        self.pid = int(open(pidf).read().strip())
        atexit.register(self.close)
        for _ in range(150):
            if os.path.exists(self.sock):
                break
            time.sleep(0.2)             # the socket appearing is a HOST event

    def close(self):
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
                gone(self.pid)
            except OSError:
                pass
            self.pid = None


class Mouse(object):
    """tools/mouse.py's verbs as an OBJECT, closed-loop (mouse_to): `click`,
    `dblclick`, `run("to"|"down"|"up"|"click", ...)` - the shape
    tests/ethernet.py's Mouse and the dispcp verbs take. `after` is the
    guest pause that followed each gesture there, now a CEILING: ui_done
    ends it as soon as the UI is finished with the gesture."""

    def __init__(self, m, sym, hmp, after=0.4):
        self.m, self.sym, self.hmp, self.after = m, sym, hmp, after

    def _wait(self):
        if self.after:
            ui_done(self.m, self.sym, cap=self.after)

    def run(self, verb, *xy):
        xy = tuple(int(v) for v in xy)
        if verb == "click":
            mouse_click(self.m, self.sym, self.hmp, *xy)
            return
        if xy:
            mouse_to(self.m, self.sym, self.hmp, *xy)
        if verb in ("down", "up"):
            mouse_button(self.m, self.sym, self.hmp, 1 if verb == "down" else 0)
        elif verb != "to":
            raise ValueError("Mouse.run: %r" % verb)

    def to(self, x, y):
        mouse_to(self.m, self.sym, self.hmp, x, y)

    def click(self, x, y):
        mouse_click(self.m, self.sym, self.hmp, x, y)
        self._wait()

    def dblclick(self, x, y):
        """Both presses down ONE QMP connection, as xmcheck.dblclick: the
        detectors' 9-tick window is shorter than two confirmed clicks."""
        mouse_to(self.m, self.sym, self.hmp, x, y)
        self.hmp("mouse_button 1", "sleep 0.08", "mouse_button 0",
                 "sleep 0.12", "mouse_button 1", "sleep 0.08",
                 "mouse_button 0")
        self._wait()


def mouse_dblclick(m, sym, hmp, x, y):
    """to (x, y), then two clicks, every edge confirmed off mouse_btn - four
    packets, well inside the kernel's 9-tick double-click window (SPEC.md
    22), where xmcheck.dblclick paced them with host sleeps after a
    tools/mouse.py walk (~1.7 s)."""
    mouse_to(m, sym, hmp, x, y)
    if mouse_where(m, sym)[2] & 3:
        mouse_button(m, sym, hmp, 0)
    for _ in range(2):
        mouse_button(m, sym, hmp, 1)
        mouse_button(m, sym, hmp, 0)


def launch_test(tmp, sysimg="build/os8088.img", apps="build/apps.img",
                extra=(), card=True, copy=True):
    """`make test`'s machine WITHOUT `make`, in a directory of its own.

    `make test` is a launcher, but its parse rewrites build/buildnum.inc and
    its prerequisites are the shared images - so in a checkout whose build/
    is behind its sources (every commit moves the build number) it REBUILDS
    the kernel and the disks under every other row before it boots. This is
    the same command line (Makefile `test:` with the default MOUSE and
    DEVCARD - the OPL2 at 388h, `card=False` is NOCARD=1) against COPIES of
    the two images in `tmp` (the guest writes SYSTEM.CFG; `copy=False` boots
    the files given, for a row that reads its own scratch back), and its own
    socket and pidfile, so two of these can run at once. Paths resolve
    through os88build.at. Answers (sock, pidfile); torn down at exit (own)."""
    import shutil
    import subprocess
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import os88build
    imgs = []
    for name, src in (("sys.img", sysimg), ("apps.img", apps)):
        src = os88build.at(src) if not os.path.isabs(src) else src
        if copy:
            dst = os.path.join(tmp, name)
            shutil.copyfile(src, dst)
            src = dst
        imgs.append(os.path.abspath(src))
    sock = os.path.join(tmp, "qmp.sock")
    pid = os.path.join(tmp, "qemu.pid")
    cmd = ["qemu-system-i386", "-machine", "pc,vmport=off",
           "-drive", "file=%s,format=raw,if=floppy" % imgs[0], "-boot", "a",
           "-chardev", "msmouse,id=m0", "-serial", "chardev:m0",
           "-drive", "file=%s,format=raw,if=floppy,index=1" % imgs[1],
           "-display", "none", "-qmp", "unix:%s,server,nowait" % sock,
           "-daemonize", "-pidfile", pid]
    if card:
        cmd += ["-audiodev", "none,id=devsnd", "-device",
                "adlib,audiodev=devsnd"]
    own(pid, sock)
    subprocess.run(cmd + list(extra), cwd=ROOT, check=True)
    # ...and BY THE PID IT WROTE as well (vidxms.Q's lesson): a caller that
    # deletes `tmp` on its way out takes the pidfile own() would read
    atexit.register(_killpid, int(open(pid).read().strip()))
    return sock, pid


def _killpid(pid):
    try:
        os.kill(pid, signal.SIGTERM)
        gone(pid)
    except OSError:
        pass
