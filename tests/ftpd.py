#!/usr/bin/env python3
"""FTPD: the FTP server, driven by a real FTP client (SPEC.md 77).

    make && make ftpdtest && python3 tests/ftpd.py

**THIS ONE IS QEMU'S, FOR THE SAME REASON tests/ethernet.py IS.** CLAUDE.md's
rule is MartyPC first with a short list of exceptions, and the network card is
on it: MartyPC has no NIC of any kind, so the emulator this tree develops on
cannot host ETHER.DRV at all. QEMU's `ne2k_isa` on `-netdev user` is the only
harness there is.

What QEMU costs is what it always costs: the machine is not an 8088 and no
timing here means anything. Every assertion below is about BEHAVIOUR and none
is about speed, so there is no number in this file for PERFORMANCE.md to want
off the 5150.

**THE CLIENT IS `ftplib` AND THAT IS THE POINT.** A hand-rolled client in this
file would test the server against this file's idea of RFC 959; the standard
library's has talked to real servers for thirty years, so what it accepts is
evidence about interoperability rather than about the harness. It is what
finds a missing `227` bracket, a reply code the wrong side of a class boundary
and a `LIST` no parser can read.

`make test ETHFWD=1` is what makes it reachable at all: slirp gives a guest no
inbound route, so the control port and the whole passive range are forwarded
(Makefile). ftplib since Python 3.11 IGNORES the address in a `227` reply and
dials the one it is already connected to, so its data connection comes back to
127.0.0.1 and the forward catches it.

**AND THAT DEFAULT HID A REAL BUG FOR A WHOLE RELEASE.** This paragraph used
to end "a security default doing us a favour", and the favour it was doing was
concealing that the server advertised its own unroutable 10.0.2.15 in every
`227`. WinSCP trusts that address, dials it, and times out - so the server was
unusable behind NAT while this gate reported six green assertions. A harness
whose client is MORE FORGIVING than a real one is not a harness for that
behaviour (tests/lptlink/partner.py's `NC_BYE` is the same lesson). Assertion
7 now runs a client that trusts the 227, and assertion 8 runs ACTIVE mode,
which nothing covered at all.

ELEVEN ASSERTIONS, and they climb the same way stage E's did.

1. THE SERVER ANSWERS. A `220` greeting, and USER/PASS reach `230`. That is
   the port-21 listener, NETV_ACCEPT, and the control connection.

2. IT LISTS. `LIST` returns rows for the files that are on the disk, in the
   `ls -l` shape `SYST` promises - so the data connection opened, PASV's
   address was one the client could reach, and OSAPI_FILE_FIND's walk ran on
   the UI task while the worker held the socket.

3. RETR IS BYTE-EXACT, for TEXT AND FOR BINARY. FTPBIN.DAT is every byte value
   eight times over, which is what catches a path that is clean for ASCII and
   eats 0x00 or 0x1A.

4. STOR ROUND-TRIPS, AND THE SERVER IS NOT ASKED WHETHER IT WORKED. The file
   goes up, and it is read back with RETR - and then the IMAGE is read on the
   HOST by an independent FAT12 reader (tools/os88disk.py --verify plus a
   direct extract). Asking os8088 whether os8088 saved it correctly is the
   failure docs/FIELD-NOTES.md 4 is about: the writer and the reader are the
   same FAT12 code, so the two agreeing on the same wrong thing is exactly
   what cannot be seen from inside.

5. IT NAVIGATES. `CWD DEEP`, a `LIST` there, `PWD` says `/DEEP`, `CDUP` comes
   back. That is OSAPI_FILE_GOTO walking and fd_pathpush's string agreeing
   with it.

6. READ ONLY REFUSES. With the box ticked, STOR is answered `550` and the file
   does NOT appear - so the gate is the server's and not the client's.

7. A CLIENT THAT TRUSTS THE 227 CAN STILL TRANSFER. `trust_server_pasv_ipv4_
   address = True` is WinSCP's behaviour, and it is the one this gate was
   blind to. It needs the PASV override set, which is what SPEC.md 77.12's
   Setup page and FTPD.CFG exist for - so this drives the setting through the
   window and then proves a trusting client works.

8. ACTIVE MODE WORKS. `PORT`, where the SERVER dials the client. It needs no
   address from the server at all, which is why it is the answer for a machine
   behind NAT with nothing configured - and it had no coverage whatsoever.

9. A USER AND A PASSWORD GATE IT (SPEC.md 77.15). Configured through the
   Setup page, the old credentials are refused, the NAME is folded and the
   PASSWORD is not - which is two assertions in one, because getting the
   comparison the same way round for both is the easy mistake.

10. THE ROOT IS SELECTABLE (SPEC.md 77.16.1). Rooted at DEEP, `/` holds
    DEEP's one file and CDUP at the root stays put - the session never sees
    above what it was given.

11. WHOLE-MACHINE MODE SERVES THE VOLUMES (SPEC.md 77.16). The root lists one
    directory row per mounted drive, `CWD B` lands in B:'s root, `CDUP` comes
    back up above every volume, a BARE name there is refused, and an absolute
    `/B/FTPHELLO.TXT` still reaches the file - which is the payoff of putting
    the branch in `fd_enter` rather than in each command.

A STOR bigger than the staging buffer is deliberately included in 4: the whole
design is a stage-and-commit loop (SPEC.md 77.1) and a file that fits in one
chunk never exercises OSAPI_FILE_APPEND's cluster precondition at all.
"""
import argparse
import ftplib
import io
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))
import dispcp                                          # noqa: E402
import ethernet as eth                                 # noqa: E402
import os88sym                                         # noqa: E402

S = os88sym.linear

SOCK = "build/qmp.sock"
SYSIMG = "build/ether360.img"
APPIMG = "build/ftpapps.img"
CTRL = 2121
HOST = "127.0.0.1"

HELLO = b"hello from os8088\r\n"
BINDAT = bytes(range(256)) * 8


def say(*a):
    print(*a)
    sys.stdout.flush()


# --- QMP's names for the keys dispcp's scroller presses ----------------------
# dispcp.scroll_to calls `m.key("ArrowDown")`, which is MartyPC's spelling -
# every other caller of it is a MartyPC gate (tests/brtest.py and friends) and
# os88marty.Marty has the method. This is the same contract over QMP, which is
# the whole of what a QEMU-hosted gate is missing to reuse that scroller.
QKEYS = {"ArrowDown": "down", "ArrowUp": "up", "Home": "home", "End": "end",
         "PageDown": "pgdn", "PageUp": "pgup", "Tab": "tab", "Enter": "ret"}


class Qemu(eth.Qemu):
    def key(self, name):
        if name not in QKEYS:
            raise KeyError("no QMP sendkey name for %r" % name)
        self.hmp("sendkey " + QKEYS[name])
        time.sleep(0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true",
                    help="leave QEMU running for a look afterwards")
    a = ap.parse_args()
    fails = []

    # THE IMAGES ARE REBUILT, NOT CHECKED. QEMU mounts both WRITABLE and the
    # guest writes to them - this gate's own STOR lands on ftpapps.img - so a
    # second run would find the uploaded file already there and assertion 4
    # would pass without a byte crossing the wire. Staleness is not the hazard
    # here, a dirty image is, and `make` cannot see the difference because the
    # guest's write leaves the image NEWER than everything it was built from.
    for f in (SYSIMG, APPIMG):
        if os.path.exists(f):
            os.remove(f)
    r = subprocess.run(["make", "ftpdtest"], capture_output=True, text=True)
    if r.returncode:
        sys.exit("ftpd: make ftpdtest failed:\n" + r.stdout + r.stderr)

    # A SURVIVOR KEEPS THE SOCKET, so the new machine cannot bind and every
    # read below would come from the OLD one - which reads as a change that
    # did nothing. Kill it by PID out of the pidfile, never with `pkill -f
    # qemu`, whose pattern matches the calling shell.
    if os.path.exists("build/qemu.pid"):
        try:
            os.kill(int(open("build/qemu.pid").read().strip()), 15)
            time.sleep(1.0)
        except (OSError, ValueError):
            pass
    for f in ("build/qmp.sock", "build/qemu.pid"):
        if os.path.exists(f):
            os.remove(f)

    r = subprocess.run(["make", "test", "ETHER=1", "ETHFWD=1",
                        "TESTIMG=" + SYSIMG, "TESTAPPS=" + APPIMG],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("ftpd: make test failed:\n" + r.stdout + r.stderr)

    # ethernet.py's Qemu and Mouse are reused rather than copied: one QMP
    # client at a time, `pmemsave` for memory, and one tools/mouse.py process
    # per action because msmouse is 1200 baud and the pacing inside that tool
    # is what makes a click land (its own header says so).
    m = Qemu(SOCK)
    mo = eth.Mouse()

    try:
        run_gate(m, mo, fails)
    finally:
        if not a.keep:
            try:
                m.quit()
            except Exception:
                pass

    say("")
    if fails:
        for f in fails:
            say("FAIL " + f)
        sys.exit(1)
    say("ftpd: all assertions passed")


def wait_dhcp(m):
    """The card up and an address bound, read out of the driver's own image.

    The gate reads state rather than clicking, exactly as tests/ethernet.py
    does: SYSTEM.CFG already asked for ETHER.DRV, so this is a wait and not a
    Control Panel drive.
    """
    syms = eth.ether_syms()
    for _ in range(200):
        time.sleep(0.4)
        row = m.read(S("drv_tab") + eth.ETH_ROW * eth.DRVR_SZ + eth.DRVR_SEG, 2)
        seg = eth.u16(row)
        if not seg:
            continue
        ip = m.readseg(seg, syms["eth_ip"], 4)
        if any(ip):
            return eth.dotted(ip)
    return None


def launch(m, mo):
    """Open B:, launch FTPD.O88, press Start.

    **THE DOUBLE-CLICK IS RETRIED AND THE WAIT IS ON THE WINDOW.** The first
    version did one open_named and then slept two seconds, and it failed about
    half the time with no instance in inst_tab at all - the launch had simply
    not happened. That is the harness being flaky and not the package: a
    double-click is two presses inside a 9-tick window through a 1200-baud
    mouse (CLAUDE.md), and scroll_to has just been pressing keys at the same
    window. So this waits for the STATE IT WANTS rather than for a duration,
    which is what dispcp's own scroller does, and asks again if it does not
    arrive.
    """
    def settle(mm, card=None):
        time.sleep(2.0)

    dispcp.open_drive(m, mo, S, settle, "B")
    # **open_drive ANSWERS THE DRIVE ICON's (x, y), NOT THE WINDOW's**, and
    # taking it for the window is what the first version of this did: row_xy
    # then computes a row inside the desktop off to the right of the Disk
    # window, every double-click lands on bare desktop, and the symptom is a
    # package that "will not launch" with nothing selected and no error
    # anywhere. The window's own rect is the only thing that answers this.
    wins = dispcp.win_list(m, S)
    if not wins:
        raise RuntimeError("opening drive B: left no window")
    wx, wy = dispcp.win_rect(m, S, wins[-1])[:2]
    for _ in range(4):
        dispcp.open_named(m, mo, S, settle, wx, wy, "FTPD.O88")
        fx, fy = wait_win(m, 12.0)
        if fx is not None:
            break
        say("   (the launch did not take - asking again)")
    else:
        raise RuntimeError("FTPD.O88 never opened a window in 4 attempts - "
                           "the package failed to load, rather than the click "
                           "failing to land")
    # The Start button is derived from the WINDOW RECORD rather than from the
    # template, because wm_fit clamps a template that does not fit the live
    # screen (SPEC.md 39.7) and a CGA desktop is 200 rows.
    bx, by = start_btn(fx, fy)
    mo.click(bx, by)
    time.sleep(1.5)
    return fx, fy


def wait_win(m, secs):
    """Poll for the FTP window rather than sleeping a guess."""
    end = time.time() + secs
    while time.time() < end:
        try:
            return ftp_win(m)
        except RuntimeError:
            time.sleep(0.5)
    return None, None


# --- the FTP window, and its two controls ------------------------------------
# FD_W is the identifier rather than "the newest slot": win_list answers in
# SLOT order and a slot is reused, so the highest index is not reliably the
# window just opened. A width is a fact about which window this is.
FD_W, FD_H = 400, 176
FD_PAD, FD_BTNW, FD_BTNH = 4, 72, 14
TITLE_H = 18


def ftp_win(m):
    slots = dispcp.win_list(m, S)
    if not slots:
        raise RuntimeError("no windows at all after launching FTPD.O88")
    for i in reversed(slots):
        x, y, w, h = dispcp.win_rect(m, S, i)
        if w == FD_W:
            return x, y
    x, y, w, h = dispcp.win_rect(m, S, slots[-1])
    raise RuntimeError("no %dpx-wide window after launching FTPD.O88 - the "
                       "newest is %dx%d at (%d,%d), which is the Disk window "
                       "still, so the package never opened one"
                       % (FD_W, w, h, x, y))


def start_btn(fx, fy):
    return (fx + 1 + FD_PAD + FD_BTNW // 2,
            fy + TITLE_H + FD_PAD + FD_BTNH // 2)


def ro_box(fx, fy):
    return (fx + 1 + FD_PAD + FD_BTNW + 8 + 6,
            fy + TITLE_H + FD_PAD + 2 + 6)


# --- the Setup page's controls, derived the way fd_setup_rects derives them --
# FD_SETX/FD_SETY/FD_SROW/FD_FLDX/FD_FLDW and the check box's offset, mirrored
# from ftpd.asm. A label and its field SHARE a row (the content box on CGA is
# ~117 rows once wm_fit has clamped the window), so the row pitch is one
# FD_SROW and not two.
FD_SETX, FD_SETY, FD_SROW = 8, 16, 16
FD_FLDX, FD_FLDW, FD_FN = 112, 160, 4
F_PASV, F_ROOT, F_USER, F_PASS = 0, 1, 2, 3


def field_pt(fx, fy, idx):
    return (fx + 1 + FD_FLDX + 20,
            fy + TITLE_H + FD_SETY + idx * FD_SROW + 6)


def mach_box(fx, fy):
    return (fx + 1 + FD_SETX + 6,
            fy + TITLE_H + FD_SETY + FD_FN * FD_SROW + 4 + 6)


def connect():
    f = ftplib.FTP()
    f.encoding = "latin-1"
    f.connect(HOST, CTRL, timeout=30)
    return f


def retr(f, name):
    buf = io.BytesIO()
    f.retrbinary("RETR " + name, buf.write)
    return buf.getvalue()


def run_gate(m, mo, fails):
    ip = wait_dhcp(m)
    if not ip:
        fails.append("the card never bound an address - ETHER.DRV did not "
                     "attach, or DHCP never completed")
        return
    say("card up, address %s" % ip)

    launch(m, mo)
    say("FTPD launched and started")

    # --- 1: it answers ------------------------------------------------------
    f = None
    for _ in range(30):
        try:
            f = connect()
            break
        except (OSError, ftplib.all_errors):
            time.sleep(1.0)
    if f is None:
        fails.append("nothing answered on port 21 - the server did not start, "
                     "or Start was never clicked")
        return
    greet = f.getwelcome()
    say("greeting: %s" % greet)
    if not greet.startswith("220"):
        fails.append("the greeting is %r, not a 220" % greet)
    r = f.login("os8088", "os8088")
    say("login: %s" % r)
    if not r.startswith("230"):
        fails.append("login answered %r, not a 230" % r)

    # --- 2: it lists --------------------------------------------------------
    rows = []
    f.retrlines("LIST", rows.append)
    say("LIST returned %d rows" % len(rows))
    for row in rows:
        say("   " + row)
    names = set()
    for row in rows:
        parts = row.split()
        if parts:
            names.add(parts[-1])
    for want in ("FTPHELLO.TXT", "FTPBIN.DAT", "FTPD.O88", "DEEP"):
        if want not in names:
            fails.append("LIST does not mention %s (saw %s)"
                         % (want, sorted(names)))
    for row in rows:
        if row.endswith("DEEP") and not row.startswith("d"):
            fails.append("DEEP is a folder and its LIST row does not say so: "
                         "%r - no client will let the user into it" % row)

    # --- 3: RETR is byte-exact, text and binary -----------------------------
    got = retr(f, "FTPHELLO.TXT")
    if got != HELLO:
        fails.append("RETR FTPHELLO.TXT gave %r, wanted %r" % (got, HELLO))
    else:
        say("RETR FTPHELLO.TXT: %d bytes, exact" % len(got))

    got = retr(f, "FTPBIN.DAT")
    if got != BINDAT:
        n = sum(1 for i in range(min(len(got), len(BINDAT)))
                if got[i] != BINDAT[i])
        fails.append("RETR FTPBIN.DAT is wrong: %d bytes against %d, %d "
                     "differing in the overlap" % (len(got), len(BINDAT), n))
    else:
        say("RETR FTPBIN.DAT: %d bytes, every byte value, exact" % len(got))

    # --- 4: STOR round-trips, and the HOST reads the image ------------------
    # BIGGER THAN THE STAGE ON PURPOSE: the whole design is a stage-and-commit
    # loop (SPEC.md 77.1), and a file that fits one chunk never exercises
    # OSAPI_FILE_APPEND's cluster precondition at all.
    up = bytes((i * 7 + 13) & 0xFF for i in range(20000))
    r = f.storbinary("STOR UP.DAT", io.BytesIO(up))
    say("STOR UP.DAT: %s" % r)
    if not r.startswith("226"):
        fails.append("STOR answered %r, not a 226" % r)
    back = retr(f, "UP.DAT")
    if back != up:
        fails.append("STOR/RETR round trip is wrong: %d bytes back against "
                     "%d sent" % (len(back), len(up)))
    else:
        say("STOR/RETR round trip: %d bytes, exact" % len(up))

    size = f.size("UP.DAT")
    if size != len(up):
        fails.append("SIZE says %r, the file is %d" % (size, len(up)))

    # --- 5: it navigates ----------------------------------------------------
    f.cwd("DEEP")
    pwd = f.pwd()
    say("after CWD DEEP, PWD = %s" % pwd)
    if pwd != "/DEEP":
        fails.append("PWD says %r after CWD DEEP, wanted '/DEEP'" % pwd)
    deep = retr(f, "FTPHELLO.TXT")
    if deep != HELLO:
        fails.append("the copy in DEEP came back %r" % deep)
    f.cwd("..")
    pwd = f.pwd()
    if pwd != "/":
        fails.append("PWD says %r after CDUP, wanted '/'" % pwd)
    try:
        f.cwd("NOSUCH")
        fails.append("CWD NOSUCH was accepted")
    except ftplib.error_perm:
        pass
    pwd = f.pwd()
    if pwd != "/":
        fails.append("a FAILED CWD moved the session to %r - every later bare "
                     "name now resolves in the wrong folder, silently" % pwd)

    # --- 5b: MKD and RMD, and RMD's refusal to empty a folder ---------------
    # **THE REFUSAL IS THE ASSERTION HERE, not the removal.** RFC 959's RMD is
    # specified to fail on a non-empty directory, and the recursive form of
    # OSAPI_FILE_RMDIR (SPEC.md 18.90.2) is one register away - so a server
    # that reached for it would pass a "does RMD work" test while silently
    # destroying a tree the client believed it was protecting.
    r = f.mkd("NEWDIR")
    say("MKD NEWDIR -> parsed path %r" % r)
    # ftplib's mkd() runs parse257, which pulls the path out of the QUOTED
    # field RFC 959 gives a 257. It answers '' rather than raising when the
    # field is missing - so an empty answer here is the reply being malformed
    # in a way the client tolerates, which is how it shipped once already.
    if r != "NEWDIR":
        fails.append("MKD's 257 parsed as %r, not 'NEWDIR' - the reply is not "
                     "carrying the quoted path RFC 959 asks for" % r)
    rows = []
    f.retrlines("LIST", rows.append)
    if not any(r.split()[-1] == "NEWDIR" and r.startswith("d") for r in rows):
        fails.append("MKD NEWDIR did not produce a folder row in LIST")
    try:
        f.rmd("DEEP")
        fails.append("RMD emptied DEEP, which has a file in it - the server "
                     "reached for the RECURSIVE form and RFC 959 says it must "
                     "not")
    except ftplib.error_perm as e:
        say("RMD on a non-empty folder refused: %s" % e)
        if not str(e).startswith("550"):
            fails.append("RMD on a non-empty folder answered %r, not a 550" % e)
    deep = retr(f, "DEEP/FTPHELLO.TXT")
    if deep != HELLO:
        fails.append("the refused RMD damaged DEEP's contents")
    f.rmd("NEWDIR")
    rows = []
    f.retrlines("LIST", rows.append)
    if any(r.split()[-1] == "NEWDIR" for r in rows):
        fails.append("RMD NEWDIR left the folder in the listing")
    else:
        say("RMD NEWDIR: gone")

    f.quit()

    # --- 6: Read Only refuses ----------------------------------------------
    fx, fy = ftp_win(m)
    mo.click(*ro_box(fx, fy))
    time.sleep(1.0)
    f = connect()
    f.login("os8088", "os8088")
    refused = False
    try:
        f.storbinary("STOR NO.DAT", io.BytesIO(b"x" * 64))
    except ftplib.error_perm as e:
        refused = str(e).startswith("550")
        say("Read Only refused STOR: %s" % e)
    if not refused:
        fails.append("STOR was accepted with Read Only ticked")
    rows = []
    f.retrlines("LIST", rows.append)
    if any("NO.DAT" in r for r in rows):
        fails.append("Read Only refused the STOR and the file appeared anyway")
    try:
        f.mkd("NOPE")
        fails.append("MKD was accepted with Read Only ticked")
    except ftplib.error_perm:
        pass
    try:
        f.rmd("DEEP")
        fails.append("RMD was accepted with Read Only ticked")
    except ftplib.error_perm:
        say("Read Only refused MKD and RMD too")
    f.quit()

    # --- 8: ACTIVE mode, which needs no address from the server -------------
    # It had NO coverage, and it is the answer for a machine behind NAT with
    # nothing configured - so it is the first thing to check after a report
    # that passive times out.
    # A BEAT BETWEEN SESSIONS, and it is not padding. Four handles
    # (netpkg.inc) and the session just ended still holds one while TCP
    # finishes its close, so a data connection opened immediately can find
    # nothing free. The server answers 425 for that now rather than 501, so a
    # real client retries - but this gate asserts the FIRST attempt, which
    # means it has to give the previous one time to drain.
    time.sleep(4.0)
    f = connect()
    f.login("os8088", "os8088")
    f.set_pasv(False)
    rows = []
    try:
        f.retrlines("LIST", rows.append)
        say("ACTIVE LIST: %d rows" % len(rows))
        if not rows:
            fails.append("active-mode LIST returned nothing")
    except Exception as e:
        fails.append("active mode (PORT) failed: %s: %s" % (type(e).__name__, e))
    try:
        got = retr(f, "FTPHELLO.TXT")
        if got != HELLO:
            fails.append("active-mode RETR gave %r" % got)
        else:
            say("ACTIVE RETR: exact")
    except Exception as e:
        fails.append("active-mode RETR failed: %s: %s" % (type(e).__name__, e))
    f.quit()

    # --- 7: a client that TRUSTS the 227, which is WinSCP's behaviour -------
    # Untick Read Only first (the box is still set from assertion 6), then set
    # the PASV override through the Setup page and prove a trusting client can
    # transfer. Without the override the server advertises its own 10.0.2.15
    # and this times out - which is exactly what the field reported.
    fx, fy = ftp_win(m)
    mo.click(*ro_box(fx, fy))
    time.sleep(1.0)
    set_pasv_override(m, mo, "127.0.0.1")

    f = ftplib.FTP()
    f.encoding = "latin-1"
    f.trust_server_pasv_ipv4_address = True     # WinSCP, not ftplib's default
    f.connect(HOST, CTRL, timeout=30)
    f.login("os8088", "os8088")
    raw = f.sendcmd("PASV")
    say("227 as a trusting client sees it: %s" % raw)
    if "127,0,0,1" not in raw:
        fails.append("the PASV override did not reach the 227: %r" % raw)
    rows = []
    try:
        f.retrlines("LIST", rows.append)
        say("TRUSTING LIST: %d rows" % len(rows))
        if not rows:
            fails.append("a client trusting the 227 got an empty listing")
    except Exception as e:
        fails.append("a client trusting the 227 could not transfer: %s: %s "
                     "- the PASV override is not working, which is the whole "
                     "reason it exists" % (type(e).__name__, e))
    f.quit()

    # === 9. AUTHENTICATION (SPEC.md 77.15) ==================================
    say("")
    say("--- 9. a configured user and password ---")
    setup(m, mo, fields=((F_USER, "bob"), (F_PASS, "s3cret")))

    f = ftplib.FTP()
    f.encoding = "latin-1"
    f.connect(HOST, CTRL, timeout=30)
    try:
        f.login("os8088", "os8088")
        fails.append("the server accepted os8088/os8088 with bob/s3cret "
                     "configured - the User setting is not a gate at all")
    except ftplib.error_perm as e:
        say("wrong credentials refused: %s" % str(e).strip())
    f.close()

    # THE NAME IS FOLDED AND THE PASSWORD IS NOT, so `BOB` must work and a
    # differently-cased password must not. One connection each: a 530 leaves
    # [fd_auth] clear but the control connection open, and a client that
    # retries on the same one is testing something this server does not
    # promise.
    f = ftplib.FTP()
    f.encoding = "latin-1"
    f.connect(HOST, CTRL, timeout=30)
    try:
        f.login("bob", "S3CRET")
        fails.append("the server accepted S3CRET for s3cret - the PASSWORD is "
                     "being folded, which throws bits away (SPEC.md 77.15)")
    except ftplib.error_perm:
        say("a differently-cased PASSWORD refused, as it must be")
    f.close()

    f = ftplib.FTP()
    f.encoding = "latin-1"
    f.trust_server_pasv_ipv4_address = True
    f.connect(HOST, CTRL, timeout=30)
    try:
        f.login("BOB", "s3cret")
        rows = []
        f.retrlines("LIST", rows.append)
        say("BOB/s3cret logged in and listed %d rows - the NAME is folded"
            % len(rows))
        if not rows:
            fails.append("an authenticated client got an empty listing")
    except ftplib.error_perm as e:
        fails.append("BOB/s3cret was refused: %s - the user name is being "
                     "compared case-SENSITIVELY (SPEC.md 77.15)" % e)
    f.quit()

    # === 10. A SELECTABLE ROOT (SPEC.md 77.16.1) ============================
    # `Root` is a PATH in FTPD.CFG and a (drive, cluster) in the session,
    # walked once. DEEP holds exactly one file and no folder, so a session
    # rooted there is unmistakable from one rooted at B:'s own root.
    say("")
    say("--- 10. a selectable root ---")
    setup(m, mo, fields=((F_ROOT, "DEEP"),))

    f = ftplib.FTP()
    f.encoding = "latin-1"
    f.trust_server_pasv_ipv4_address = True
    f.connect(HOST, CTRL, timeout=30)
    f.login("BOB", "s3cret")
    rows = []
    f.retrlines("LIST", rows.append)
    names = sorted(r.split()[-1] for r in rows if r.split())
    say("rooted at DEEP, / holds %r" % names)
    if names != ["FTPHELLO.TXT"]:
        fails.append("a session rooted at DEEP lists %r - it must be DEEP\'s "
                     "own contents and nothing above them" % names)
    if f.pwd() != "/":
        fails.append("PWD in the served root is %r, not '/'" % f.pwd())

    # ...AND THE SESSION NEVER SEES ABOVE IT. CDUP at the root succeeds and
    # stays put, which is what every FTP server does - a 550 to a client's
    # "go to the top" loop makes it fail.
    f.cwd("..")
    if f.pwd() != "/":
        fails.append("CDUP at the served root moved to %r" % f.pwd())
    rows = []
    f.retrlines("LIST", rows.append)
    names = sorted(r.split()[-1] for r in rows if r.split())
    if names != ["FTPHELLO.TXT"]:
        fails.append("CDUP at the served root escaped it: %r" % names)
    else:
        say("CDUP at the served root stays put, as it must")
    f.quit()

    # === 11. WHOLE-MACHINE MODE (SPEC.md 77.16) =============================
    # The root becomes the LEVEL ABOVE every volume: one row per mounted
    # drive, and a CWD into one lands in that volume's root. It is the only
    # place in this server where the thing being listed is not a directory.
    say("")
    say("--- 11. whole-machine mode ---")
    setup(m, mo, machine=True)

    f = ftplib.FTP()
    f.encoding = "latin-1"
    f.trust_server_pasv_ipv4_address = True
    f.connect(HOST, CTRL, timeout=30)
    f.login("BOB", "s3cret")
    rows = []
    f.retrlines("LIST", rows.append)
    say("machine root: %r" % rows)
    names = [r.split()[-1] for r in rows if r.split()]
    if "A" not in names or "B" not in names:
        fails.append("the machine root listed %r - it must carry one row per "
                     "MOUNTED volume, and this machine has A: and B:" % names)
    for r in rows:
        if not r.startswith("d"):
            fails.append("a volume row is not a directory: %r" % r)
    if f.pwd() != "/":
        fails.append("PWD at the machine root is %r, not '/'" % f.pwd())

    # ...and stepping into one is a real volume, with the apps disk's own
    # folders in it. B: is TESTAPPS, whose root this gate has been serving.
    f.cwd("B")
    if f.pwd() != "/B":
        fails.append("PWD inside a volume is %r, not '/B'" % f.pwd())
    vrows = []
    f.retrlines("LIST", vrows.append)
    vnames = [r.split()[-1] for r in vrows if r.split()]
    say("B: holds %r" % vnames)
    if "DEEP" not in vnames:
        fails.append("B: does not list DEEP - stepping into a volume did not "
                     "land in its root (%r)" % vnames)

    # A BARE NAME AT THE MACHINE ROOT IS REFUSED, which is the guard in
    # fd_split's `.bare`: there is no directory to resolve it in, and
    # resolving it in whichever volume was current last serves a folder the
    # client was never shown.
    f.cwd("..")
    if f.pwd() != "/":
        fails.append("CDUP from a volume root is %r, not the machine level"
                     % f.pwd())
    try:
        retr(f, "FTPHELLO.TXT")
        fails.append("a bare name at the MACHINE root was served - it "
                     "resolved in whatever volume happened to be current "
                     "(SPEC.md 77.16.2)")
    except ftplib.error_perm:
        say("a bare name at the machine root refused, as it must be")

    # ...but an ABSOLUTE one through a volume works, which is the whole
    # payoff of putting the branch in fd_enter rather than in each command.
    got = retr(f, "/B/FTPHELLO.TXT")
    if got != HELLO:
        fails.append("RETR /B/FTPHELLO.TXT gave %r - an absolute path "
                     "through a volume must reach the file" % got[:40])
    else:
        say("RETR /B/FTPHELLO.TXT is byte-exact through the machine root")
    f.quit()

    # --- and the HOST reads the image, with no os8088 code in the way -------
    verify_host(fails, up)
    verify_cfg(fails)


def setup(m, mo, fields=(), machine=None):
    """Drive the Setup page: menu, click each field, type, tick, menu again.

    THROUGH THE UI AND NOT BY POKING THE BSS, because what is under test is
    the whole path - the menu item, the line editor, the parse, the save to
    FTPD.CFG and the reader taking it back out. A poke would prove the last
    step and none of the others.

    `fields` is (index, text) pairs; the text is TYPED, so a field is only
    ever appended to - every caller here sets a field that was empty.
    """
    fx, fy = ftp_win(m)
    menu_setup(m, mo, fx, fy)
    time.sleep(1.0)
    for idx, text in fields:
        mo.click(*field_pt(fx, fy, idx))
        time.sleep(0.6)
        type_text(text)
        time.sleep(0.4)
    if machine is not None:
        mo.click(*mach_box(fx, fy))
        time.sleep(0.8)
    menu_setup(m, mo, fx, fy)       # leaving is what commits and saves
    time.sleep(2.0)
    say("Setup: %s%s"
        % (", ".join("field %d = %r" % f for f in fields) or "nothing typed",
           "" if machine is None else ", whole-machine toggled"))


def set_pasv_override(m, mo, addr):
    setup(m, mo, fields=((F_PASV, addr),))


# The app's menu bar cell and its third item, MEASURED on a running machine
# rather than derived: `Server` spans x 97..143 under the chip menu and the
# `Ftpd` name cell, and MENU_ITEM_H puts `Setup...` at y 56.
MENU_X, MENU_Y, SETUP_Y = 120, 8, 56


def menu_setup(m, mo, fx, fy):
    """Server > Setup..., through the real menu bar.

    **A MENU IS PRESS, DRAG, RELEASE - never a click** (CLAUDE.md): menu_track
    draws the pull-down and then polls a level, so a press-and-release in place
    opens it and closes it in the same breath. tools/mouse.py has no `menu`
    verb - that is os88mouse.py, the MartyPC one - so it is down / to / up.
    """
    mo.run("down", str(MENU_X), str(MENU_Y))
    time.sleep(0.5)
    mo.run("to", str(MENU_X), str(SETUP_Y))
    time.sleep(0.4)
    mo.run("up")
    time.sleep(0.8)


# QMP's `sendkey` takes KEY names, not characters, so a shifted character is
# `shift-<key>` and the punctuation has names of its own. Only what this gate
# actually types is here - an unmapped character exits rather than sending a
# plausible wrong key, because a field that quietly received something else is
# a failure that reads as the setting not working.
QCHR = {".": "dot", "/": "slash", ":": "shift-semicolon", "-": "minus",
        "_": "shift-minus"}


def type_text(text):
    cmds = []
    for ch in text:
        if ch.isdigit():
            cmds += ["sendkey " + ch]
        elif "a" <= ch <= "z":
            cmds += ["sendkey " + ch]
        elif "A" <= ch <= "Z":
            cmds += ["sendkey shift-" + ch.lower()]
        elif ch in QCHR:
            cmds += ["sendkey " + QCHR[ch]]
        else:
            sys.exit("ftpd: no sendkey mapping for %r" % ch)
        cmds += ["sleep 0.08"]
    subprocess.run(["python3", "tools/qmp.py", SOCK] + cmds,
                   check=True, capture_output=True)


def verify_host(fails, up):
    """**ASKING os8088 WHETHER os8088 SAVED IT IS NOT A TEST.**

    The writer and the reader are the same FAT12 code, so the failure that
    matters most - both halves agreeing on the same wrong thing - is the one
    that cannot be seen from inside (docs/FIELD-NOTES.md 4). This walks the
    image with tools/os88disk.py's own independent reader instead.

    The guest wrote to the MOUNTED image, so QEMU has already flushed it by
    the time it quit.
    """
    r = subprocess.run(["python3", "tools/os88disk.py", "--verify", APPIMG],
                       capture_output=True, text=True)
    if r.returncode:
        fails.append("the image does not fsck after the upload:\n"
                     + r.stdout + r.stderr)
        return
    say("host fsck of %s: clean" % APPIMG)
    data = extract(APPIMG, "UP      DAT")
    if data is None:
        fails.append("UP.DAT is not in the image's root when read on the HOST")
    elif data[:len(up)] != up:
        fails.append("UP.DAT on the image differs from what was sent - the "
                     "server and its own reader agree on the wrong bytes")
    else:
        say("UP.DAT read off the image by an independent reader: %d bytes, "
            "exact" % len(up))


def verify_cfg(fails):
    """FTPD.CFG is ON THE DISK, parsed by a reader that shares no code with it.

    **THE IN-SESSION EFFECT IS NOT THE PERSISTENCE.** Assertion 7 proves the
    override reaches the 227, which it does whether or not anything was ever
    written - and on the first run of this gate nothing was: the test disk had
    no SYSTEM/APPDATA, so fd_data_enter refused and the save said nothing,
    exactly as SPEC.md 19.9 asks it to. The setting worked all session and was
    gone on the next launch, and every assertion still passed.
    """
    data = extract(APPIMG, "FTPD    CFG", ("SYSTEM     ", "APPDATA    "))
    if data is None:
        fails.append("FTPD.CFG is not on the image - the setting was never "
                     "persisted, and SPEC.md 77.12 is half a feature")
        return
    if data[:8] != b"O88FTPD\0":
        fails.append("FTPD.CFG's magic is %r" % data[:8])
        return
    ver = data[8] | (data[9] << 8)
    keys = {}
    i = 10
    while i + 1 < len(data) and data[i] != 0:
        k, n = data[i], data[i + 1]
        keys[chr(k)] = list(data[i + 2:i + 2 + n])
        i += 2 + n
    say("FTPD.CFG: %d bytes, version %d, keys %s"
        % (len(data), ver, sorted(keys)))
    if keys.get("A") != [127, 0, 0, 1]:
        fails.append("FTPD.CFG's 'A' record is %r, wanted [127,0,0,1]"
                     % keys.get("A"))
    # ...and everything assertions 9 and 10 set. A record carries NO
    # terminator - its length byte is the bound - so an empty setting is an
    # ABSENT key rather than a one-byte one, which is why `R` is not here:
    # nothing typed a root.
    want = {"U": b"bob", "P": b"s3cret", "M": bytes([1]), "R": b"DEEP"}
    for k, v in want.items():
        got = bytes(keys.get(k, []))
        if got != v:
            fails.append("FTPD.CFG's %r record is %r, wanted %r - the setting "
                         "worked all session and is gone on the next launch"
                         % (k, got, v))
    say("FTPD.CFG persisted the root, the user, the password and "
        "whole-machine mode")


def extract(img, name11, path=()):
    """A file's bytes, by hand off the BPB - optionally down a folder PATH.

    Deliberately NOT os88disk.py's own extractor: this is the second opinion,
    so it reads the volume the way any FAT12 driver would and shares no code
    with the thing under test.

    **THE PATH ARGUMENT IS NOT A CONVENIENCE.** Without it this walked the
    ROOT only, and FTPD.CFG lives in SYSTEM/APPDATA (SPEC.md 19.9) - so the
    persistence check reported the file missing when it was there, which is a
    false failure that reads exactly like the real one it was written to
    catch.
    """
    b = open(img, "rb").read()
    bps = b[11] | (b[12] << 8)
    spc = b[13]
    rsvd = b[14] | (b[15] << 8)
    nfat = b[16]
    nroot = b[17] | (b[18] << 8)
    spf = b[22] | (b[23] << 8)
    root = (rsvd + nfat * spf) * bps
    data = root + nroot * 32
    fat = b[rsvd * bps: (rsvd + spf) * bps]

    def chain(clus, limit=None):
        out = b""
        while 2 <= clus < 0xFF0 and (limit is None or len(out) < limit):
            off = data + (clus - 2) * spc * bps
            out += b[off: off + spc * bps]
            j = clus + (clus >> 1)              # FAT12: 12 bits an entry
            v = fat[j] | (fat[j + 1] << 8)
            clus = (v >> 4) if (clus & 1) else (v & 0xFFF)
        return out

    # Walk down to the directory that holds the file. The root is a flat
    # region; a SUBdirectory is an ordinary cluster chain of the same records.
    ents = b[root: root + nroot * 32]
    for comp in path:
        found = None
        for i in range(0, len(ents), 32):
            e = ents[i:i + 32]
            if not e or e[0] == 0x00:
                break
            if e[0] == 0xE5 or (e[11] & 0x0F) == 0x0F:
                continue
            if e[:11].decode("latin-1") == comp and (e[11] & 0x10):
                found = e[26] | (e[27] << 8)
                break
        if found is None:
            return None
        ents = chain(found)
    for i in range(0, len(ents), 32):
        e = ents[i:i + 32]
        if len(e) < 32 or e[0] == 0x00:
            break
        if e[0] == 0xE5 or (e[11] & 0x0F) == 0x0F:
            continue
        if e[:11].decode("latin-1") != name11:
            continue
        size = int.from_bytes(e[28:32], "little")
        return chain(e[26] | (e[27] << 8), size)[:size]
    return None


if __name__ == "__main__":
    main()
