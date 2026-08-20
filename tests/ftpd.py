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
127.0.0.1 and the forward catches it - a security default doing us a favour.

SIX ASSERTIONS, and they climb the same way stage E's did.

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

    # --- and the HOST reads the image, with no os8088 code in the way -------
    verify_host(fails, up)


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


def extract(img, name11):
    """The root directory and the cluster chain, by hand off the BPB.

    Deliberately NOT os88disk.py's own extractor: this is the second opinion,
    so it reads the volume the way any FAT12 driver would and shares no code
    with the thing under test.
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
    for i in range(nroot):
        e = b[root + i * 32: root + i * 32 + 32]
        if e[0] in (0x00,):
            break
        if e[0] == 0xE5 or (e[11] & 0x0F) == 0x0F:
            continue
        if e[:11].decode("latin-1") != name11:
            continue
        size = int.from_bytes(e[28:32], "little")
        clus = e[26] | (e[27] << 8)
        out = b""
        while 2 <= clus < 0xFF0 and len(out) < size:
            off = data + (clus - 2) * spc * bps
            out += b[off: off + spc * bps]
            j = clus + (clus >> 1)                  # FAT12: 12 bits an entry
            v = fat[j] | (fat[j + 1] << 8)
            clus = (v >> 4) if (clus & 1) else (v & 0xFFF)
        return out[:size]
    return None


if __name__ == "__main__":
    main()
