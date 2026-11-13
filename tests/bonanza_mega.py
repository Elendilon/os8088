#!/usr/bin/env python3
"""BONANZA on kern_mega: correct on selectors, RUN (SPEC.md 128.10.6.4, 128.11.14, 128.11.17.2).

    make mega bonanzadisk && python3 tests/bonanza_mega.py [--keep]
    python3 tests/bonanza_mega.py --red segadd|hxcs|shiftmap     (a red arm, below)
    python3 tests/bonanza_mega.py --check                        (the host half: the red arms assemble)

Under kern_mega a claim is an LDT SELECTOR, so every segment wave 1 added -
the course part, with the grid inside it, and the ball part - is a part's own,
from op_seg, loaded into DS or ES and used WHOLE, every offset under the
part's 65,024 bytes; nothing writes through CS and no immediate is patched
(the map stride is read from the part's header).  So the SHIPPED package
needs no PKG_MEGA arm (128.10.6.4), and this row is where that is proved by
running it, not by reading it.

It boots build/mega.img on 86Box's `286-mega-multimon` (vm/286-victory's AMI
286 with a Paradise VGA and a HERCULES, a monitor each; docs/86BOX.md) with a
SYSTEM.CFG asking for the EXTENDED desktop (tests/megarmbext.py's record),
and BONANZA's own 1.44MB floppy, build/bonanza.img, in B:.  BONANZA is opened
from B:'s Disk window on the VGA and its window DRAGGED onto the Hercules -
the display the bracket is taken on is the window's (SPEC.md 53.7.1), and
BONANZA plays on a CGA or a Hercules only - and then:

  1  B, the benchmark, to its end on the Hercules ([bz_herc] 1 inside, the
     results left: [bz_res] 1, 1,200 frames in [bz_rframes]);
  2  Enter, a play of FIRST, left by Esc after 100 frames;
  3  a play with a HOP (Space) and GRIP (Left Shift held) and the arrows,
     left by Esc, then its REPLAY by R run to its end: the replay's end
     state (nstep, gx, gy, gz and the velocities, read in the package's bss)
     is the play's - every launch on the Hercules BUILDS BZ_HTAB in the
     package's bss and TRANSLATES both fetched parts in place through their
     own selectors (SPEC.md 128.11.3, 128.11.14);

     Keys are held for STEPS, never frames: 86Box paces the Hercules'
     retrace nothing like a real card's (about nine frames a step on this
     machine), and a key is recorded only by a step that runs while it is
     down - a Hop held 4 frames fell between two steps in the first final
     pass and the play logged 19 steps in 120 frames;
  4  THE FAKE SHIFTS (128.11.7.2): with NumLock on, a play in which the GREY
     Right arrow (E0 4D: a 101-key keyboard sends E0 2A first with NumLock
     on) is held for 30 steps, left by Esc: every key byte the play
     RECORDED has bit 5 (Grip) clear.  (86Box's keyboard sends no fake
     shift, and its automation drops an explicit E0 2A - 0x12A, tried in
     wave 2's final pass - so on 86Box this case is a SKIP.)  Before that it reads kbd_track's map
     with the grey arrow held: if bit 2Ah is not set there, this machine's
     keyboard sends no fake shift, the case could not go red, and it reports
     SKIP with that reason (asserting nothing about it);

and asserts, after each, as bonanza_exit does on MartyPC: every part row
with OP_FETCHED clear and OP_R_ZKB back to its packed length, and the
instance's claims - the conventional heap's (mem_tab) and the pool's above
1MB (mx_tab, through tools/heapmap.py's `pool`) owned by its region's
selector - exactly those before the launch; and over the whole run 86Box's
fault log (this tree's patch prints every CPU exception and shutdown,
docs/86BOX.md *faults*) EMPTY past the desktop: no exception charged to
anything but the kernel's own code and the BIOS, and no reset but the
kernel's own way out of protected mode on a 286 (mega_svc_lo's deliberate
shutdown, which the first final pass counted as a failure).  No time is
asserted: 86Box is not cycle-exact.

--red NAME builds a package (in a temporary directory, never build/) that
is right on every real-mode kernel and wrong on kern_mega, and PASSES only if
the row FAILS at its own check:
  segadd    the grid reached by ADDING GRIDOFF >> 4 to the course's segment (on
            a selector, another descriptor): an exception in the fault log
  hxcs      the Hercules translation writes through CS (bz_hxrows' store a
            `mov [cs:di], al`): an exception in the fault log, charged to the
            package, at the first Hercules launch
  shiftmap  Grip read through OSAPI_KEY_DOWN (2Ah), §9.7's map: with the
            fake shift in the map, bit 5 set while the grey arrow is held
            (a SKIP of case 4 leaves this arm unjudged, and it says so)
Needs a built 86Box (python3 tools/os88box.py build).
"""
import argparse
import os
import shutil
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "tests")]
import os88box                                                # noqa: E402
import os88fat                                                # noqa: E402
import os88geom as G                                          # noqa: E402
import os88sym                                                # noqa: E402
import heapmap                                                # noqa: E402
import bonanza_ring as R                                      # noqa: E402

B = os.path.join(ROOT, "build")
VM = "286-mega-multimon"
NAME = "BONANZA"
PROMPTS = (("bypass MEMORY test", "esc"), ("to RESUME", "f1"), ("EXIT FOR BOOT", "return"))
DRIVE_B = (592, 105)            # the B: zone on the VGA desktop (tests/megarmbext.py)
FIRST = (160, 127)              # the first file of a fresh B: window: BONANZA.O88
OP_ROW, OP_T_ROWS, OP_R_FLAG, OP_R_ZKB, OP_FETCHED = 8, 10, 1, 6, 32
KERNEL_CS = (0x0060, 0x0028)    # the kernel's own code (os88box.faults' segmap)
FAILS = []
SKIPS = []


def want(cond, what):
    print("   %s  %s" % ("ok  " if cond else "FAIL", what), flush=True)
    if not cond:
        FAILS.append(what)


def u16(b, i=0):
    return b[i] | b[i + 1] << 8


def syscfg(path, vel):
    """SYSTEM.CFG asking for Extend - tests/megarmbext.py's (and extdmod.py's)
    record: 'VM', the adapter FFh, [vid_dmode] 1 Extend, [vid_dlay] 0 (display
    1 to the RIGHT), and on a VID_EXT kernel the packed display's class"""
    with open(path, "wb") as f:
        f.write(b"O88CFG\0\0" + (3).to_bytes(2, "little") + b"VM"
                + bytes([2 + vel, 3 + vel, 0xFF, 1, 0]) + bytes(vel) + b"\0\0")


def insts(b):
    raw = b.memr(b.sym("inst_tab"), G.INST_MAX * G.I_RECSZ)
    out = {}
    for i in range(G.INST_MAX):
        r = raw[i * G.I_RECSZ:(i + 1) * G.I_RECSZ]
        if r[G.I_STATE] != 1 or not r[G.I_KIND] & G.KIND_PKG:
            continue
        nm = r[G.I_NAME:G.I_NAME + 16].split(b"\0")[0].decode("latin-1")
        out[nm] = u16(r, G.I_SPTR)
    return out


def top_win(b):
    """wm_top's answer, off wm_zord: (x, y, w)"""
    n = b.byte("wm_zn")
    if not n:
        return None
    zord = b.memr(b.sym("wm_zord"), n)
    raw = b.memr(b.sym("wm_wins"), G.MAX_WIN * G.WIN_SIZE)
    for k in range(n - 1, -1, -1):
        o = zord[k] * G.WIN_SIZE
        if u16(raw, o) & (G.WF_VIS | G.WF_DESK) == G.WF_VIS:
            return u16(raw, o + G.W_X), u16(raw, o + G.W_Y), u16(raw, o + G.W_W)
    return None


def _kernel_reset(cs, ip):
    """Is CS:IP the kernel's OWN way out of protected mode on a 286 - the
    deliberate shutdown in mega_svc_lo (kernel/mega.inc: `lmsw` cannot clear
    PE, so the 40:67 vector is set and the CPU triple-faulted)?  That reset is
    the kernel's code doing what it is for, as the BIOS's own at F000 is, and
    SPEC.md 128.10.11.3 excludes both; any other reset is a failure."""
    if cs not in KERNEL_CS:
        return False
    syms = os88box.load_map(os.path.join(B, "megak", "kernel.map"))
    return os88box.resolve(syms, cs, ip, {c: ".text" for c in KERNEL_CS}).startswith("mega_svc_lo.")


def faults(b, since=0):
    """-> (exceptions charged to anything but the kernel and the BIOS, resets
    other than the kernel's own (_kernel_reset), the kernel's own exceptions
    and resets) after stderr line SINCE"""
    mine, resets, kern = [], [], 0
    for k, line in enumerate(open(os.path.join(b.run, "stderr.log"), errors="replace")):
        if k < since:
            continue
        m = os88box.FAULT.search(line)
        if m:
            cs = int(m.group(2), 16)
            if cs >= 0xF000:
                continue
            if cs in KERNEL_CS:
                kern += 1
                continue
            mine.append(line.strip())
        elif os88box.RESET.search(line) and int(os88box.RESET.search(line).group(1), 16) < 0xF000:
            r = os88box.RESET.search(line)
            if _kernel_reset(int(r.group(1), 16), int(r.group(2), 16)):
                kern += 1
                continue
            resets.append(line.strip())
    return mine, resets, kern


class Gone(Exception):
    """BONANZA's instance is not in inst_tab: the kernel closed it (kern_mega's
    fault path, mega_fkill, closes the package a fault is charged to) - an
    OUTCOME the row reports, never a traceback"""


def sel_of(b):
    """the region's selector, or Gone"""
    sel = insts(b).get(NAME)
    if sel is None:
        raise Gone("%s is no longer running: the kernel closed it" % NAME)
    return sel


class Pkg(object):
    """BONANZA's bss on kern_mega: its region's selector, read through the
    descriptor every time (b.lin) - the region is above 1MB and may move"""

    def __init__(self, b, sym):
        self.b, self.sym = b, sym

    def base(self):
        return self.b.lin(sel_of(self.b))

    def a(self, n):
        return self.base() + self.sym[n]

    def byte(self, n):
        return self.b.memr(self.a(n), 1)[0]

    def word(self, n):
        return u16(self.b.memr(self.a(n), 2))

    def rows(self):
        base = self.base()
        n = self.b.memr(base + self.sym["op_table"] + 8, 1)[0]
        raw = self.b.memr(base + self.sym["op_table"] + OP_T_ROWS, n * OP_ROW)
        return [(raw[i * OP_ROW + OP_R_FLAG], u16(raw, i * OP_ROW + OP_R_ZKB)) for i in range(n)]


class Q(object):
    """heapmap's reader over an 86Box: read, sym, tail (kern_mega's tables' tail)"""

    def __init__(self, b, equ):
        self.b, self.equ = b, equ

    def read(self, lin, n):
        return self.b.memr(lin, n)

    def sym(self, name):
        return self.b.sym(name)

    def tail(self, name):
        return os88sym.tail(name, self.read, self.sym, self.equ)


def claims(b, pkg, hs, equ):
    """The instance's claims: [(where, paragraphs, pinned)], sorted - mem_tab's
    owned by its region selector, and the pool's (the region itself and its
    OS88_HIGHMEM claims, whose MX_OWN heapmap.pool maps to that selector)"""
    sel = sel_of(b)
    q = Q(b, equ)
    mp = heapmap.Map(q, hs)
    out = [("low", c.para, c.pinned) for c in mp.claims if c.own == sel]
    out += [("pool", c.para, c.pinned) for c in heapmap.pool(q) if c.own == sel]
    return sorted(out)


def nstep(b, pkg):
    """[bz_nstep]: the play's steps so far"""
    return u16(b.memr(pkg.a("bz_nstep"), 2))


def steps(b, pkg, n, what):
    """run until the play has taken N more STEPS.  Counted in steps, not frames:
    86Box paces the Hercules' retrace nothing like a real card's (it is not
    cycle-exact; on this machine about nine frames a step), and a key a frame
    samples is recorded only by a step that runs while it is down"""
    s0 = nstep(b, pkg)
    b.until(lambda: nstep(b, pkg) >= s0 + n, "%s (%d steps)" % (what, n), 60000, 20)


def hold(b, pkg, key, n):
    """KEY held down for N of the play's STEPS (a tap could fall between two
    steps' samples), then up"""
    b.cmd("key down 0x%X" % os88box.keycode(key))
    steps(b, pkg, n, "%s held" % key)
    b.cmd("key up 0x%X" % os88box.keycode(key))


def phys(b, pkg):
    """(nstep, gx, gy, gz, gvx, gvy, gvz, air) out of the package's bss"""
    lo = pkg.a("bz_phs")
    raw = b.memr(lo, pkg.sym["bz_phe"] - pkg.sym["bz_phs"])

    def f(n, fmt):
        return struct.unpack_from(fmt, raw, pkg.sym[n] - pkg.sym["bz_phs"])[0]
    return (f("bz_nstep", "<I"), f("bz_gx", "<I"), f("bz_gy", "<I"), f("bz_gz", "<i"), f("bz_gvx", "<h"),
            f("bz_gvy", "<h"), f("bz_gvz", "<h"), f("bz_air", "B"))


def log_keys(b, pkg):
    """the key bytes of the play bz_rlog holds (its runs; SPEC.md 128.11.12.1)"""
    raw = b.memr(pkg.a("bz_rlog"), 4096)
    if raw[:4] != b"BZR1":
        return []
    n = u16(raw, 12)
    out = []
    for i in range(min(n, 2040)):
        out += [raw[16 + 2 * i]] * raw[17 + 2 * i]
    return out


def check_after(what, pkg, base_rows, base_claims, got_claims):
    rows = pkg.rows()
    bad = [i for i, (f, _) in enumerate(rows) if f & OP_FETCHED]
    want(not bad, "%s: no part row FETCHED after it (%s)" % (what, bad or "none"))
    moved = [i for i, (a, c) in enumerate(zip(base_rows, rows)) if a[1] != c[1]]
    want(not moved, "%s: every row's zkb back to its packed length (%s)" % (what, moved or "all"))
    want(got_claims == base_claims, "%s: the instance's claims as before the launch: %s" % (what, got_claims))


def run(img_b, keep, tmp):
    eq = os88sym._parse_map(os.path.join(B, "megak", "kernel.map"))[2]
    off = os88sym._parse_map(os.path.join(B, "megak", "kernel.map"))[0]
    img = os.path.join(tmp, "mega.img")             # (named mega*: os88box then reads megak/'s map)
    shutil.copy(os.path.join(B, "mega.img"), img)
    cfg = os.path.join(tmp, "system.cfg")
    syscfg(cfg, eq.get("CFG_VEL", 0))
    fat = os88fat.Fat12(img)
    fat.delete("SYSTEM.CFG")
    fat.add(cfg, "SYSTEM.CFG")
    fat.save()
    sym = R.symbols(os.path.join(tmp, "bonanza") if os.path.isdir(os.path.join(tmp, "bonanza")) else None)
    b = os88box.launch(VM, name="bonanzamega%d" % os.getpid(), hold=True, fresh=True, a=img, b=img_b,
                       temp=not keep, turbo=True)
    since = 0
    try:
        b.kernel_up(prompts=PROMPTS)
        b.until(lambda: b.byte("mega_on"), "protected mode", 30000, 250)
        b.ui_done(cap_ms=10000)
        since = sum(1 for _ in open(os.path.join(b.run, "stderr.log"), errors="replace"))
        hs = {n: b.sym(n) for n in ("mem_base", "mem_top", "spl_live")}
        hs["mem_tab"] = eq["LOW_SEG"] * 16 + off["mem_tab"]     # (.lowbss: not a .text/.bss symbol)
        want(b.byte("vid_ndisp") == 2, "0. the desktop is EXTENDED: two displays ([vid_ndisp] %d)"
             % b.byte("vid_ndisp"))
        b.to(*DRIVE_B)
        b.click(2)
        b.ui_done(limit_ms=20000)
        b.to(*FIRST)
        b.click(2)
        b.until(lambda: NAME in insts(b), "BONANZA to start", 60000, 100)
        b.ui_done(limit_ms=60000)
        pkg = Pkg(b, sym)
        # the window onto the Hercules: display 1 sits RIGHT of the VGA ([vid_dlay] 0)
        d1 = b.memr(b.sym("vid_ctx") + G.VID_CTX_SZ, G.VID_CTX_SZ)
        vx1, cw1 = u16(d1, G.VID_CTX_VX), u16(d1, G.VID_CTX_CW)
        x, y, w = top_win(b)
        b.to(x + w // 2, y + 6)
        b.mouse(0, 0, 1)
        b.to(vx1 + cw1 // 2, y + 6, buttons=1)
        b.mouse(0, 0, 0)
        b.ui_done(limit_ms=20000)
        x, y, w = top_win(b)
        want(x + w // 2 >= vx1, "0. BONANZA's window dragged onto the Hercules: its centre at x %d, display 1 "
             "from %d" % (x + w // 2, vx1))
        base_rows, base_claims = pkg.rows(), claims(b, pkg, hs, eq)
        print("   desktop: %d part rows, none fetched: %s; the instance's claims %s" % (
            len(base_rows), all(not f & OP_FETCHED for f, _ in base_rows), base_claims), flush=True)
        # 1. the benchmark
        b.tap("b", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 1, "the benchmark's bracket", 60000, 100)
        want(pkg.byte("bz_herc") == 1, "1. the bracket is the Hercules' ([bz_herc] %d)" % pkg.byte("bz_herc"))
        inside = claims(b, pkg, hs, eq)
        want(len(inside) == len(base_claims) + 2, "1. inside: the two parts claimed (%d claims against %d)"
             % (len(inside), len(base_claims)))
        b.until(lambda: pkg.byte("bz_fs") == 0, "the benchmark's 1,200 frames", 240000, 500)
        b.until(lambda: pkg.word("bz_cseg") == 0 and pkg.word("bz_bseg") == 0, "the parts dropped", 10000, 50)
        b.ui_done(limit_ms=30000)
        want(pkg.byte("bz_res") == 1 and pkg.word("bz_rframes") == 1200,
             "1. the benchmark finished: [bz_res] %d, %d frames" % (pkg.byte("bz_res"), pkg.word("bz_rframes")))
        check_after("1. the benchmark", pkg, base_rows, base_claims, claims(b, pkg, hs, eq))
        # 2. a play, left by Esc
        b.tap("return", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 1 and pkg.word("bz_frames") > 100, "a play of 100 frames",
                60000, 100)
        want(pkg.byte("bz_crs") == R.CRS_K["first"] and pkg.byte("bz_mode") == 0, "2. Enter plays FIRST")
        b.tap("escape", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 0, "the play to end on Esc", 30000, 100)
        b.until(lambda: pkg.word("bz_cseg") == 0 and pkg.word("bz_bseg") == 0, "the parts dropped", 10000, 50)
        b.ui_done(limit_ms=30000)
        check_after("2. the play", pkg, base_rows, base_claims, claims(b, pkg, hs, eq))
        # 3. a play with a Hop and Grip, then its replay by R
        b.tap("return", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 1 and pkg.word("bz_frames") > 20, "a play of 20 frames", 60000, 100)
        steps(b, pkg, 10, "the play's first steps")
        hold(b, pkg, "space", 4)                        # a Hop from the ground
        b.cmd("key down 0x%X" % os88box.keycode("lshift"))
        b.cmd("key down 0x%X" % os88box.keycode("right"))
        steps(b, pkg, 60, "Grip and Right held")
        b.cmd("key up 0x%X" % os88box.keycode("right"))
        b.cmd("key up 0x%X" % os88box.keycode("lshift"))
        hold(b, pkg, "space", 4)
        steps(b, pkg, 40, "the play's last steps")
        b.tap("escape", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 0, "the play to end on Esc", 30000, 100)
        b.until(lambda: pkg.word("bz_cseg") == 0 and pkg.word("bz_bseg") == 0, "the parts dropped", 10000, 50)
        b.ui_done(limit_ms=30000)
        play_end = phys(b, pkg)
        log = b.memr(pkg.a("bz_rlog"), 16)
        keys = log_keys(b, pkg)
        want(log[:4] == b"BZR1" and log[6] & 1 and any(k & 0x10 for k in keys) and any(k & 0x20 for k in keys),
             "3. the play's log: BZR1, COMPLETE, %d steps, with a Hop (bit 4) and Grip (bit 5) recorded" % len(keys))
        check_after("3. the play with Hop and Grip", pkg, base_rows, base_claims, claims(b, pkg, hs, eq))
        b.tap("r", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 1, "R's replay", 60000, 100)
        want(pkg.byte("bz_mode") == 2 and pkg.byte("bz_herc") == 1, "3. R replays it on the Hercules")
        b.until(lambda: pkg.byte("bz_fs") == 0, "the replay to reach its end", 60000, 100)
        b.until(lambda: pkg.word("bz_cseg") == 0 and pkg.word("bz_bseg") == 0, "the parts dropped", 10000, 50)
        b.ui_done(limit_ms=30000)
        rep_end = phys(b, pkg)
        want(rep_end == play_end, "3. the replay ends where the play did: %s (the play %s)" % (rep_end, play_end))
        check_after("3. the replay", pkg, base_rows, base_claims, claims(b, pkg, hs, eq))
        # 4. the fake shifts: NumLock on, the grey Right arrow held
        b.tap("numlock", gap=200)
        b.tap("return", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 1 and pkg.word("bz_frames") > 10, "a play of 10 frames", 60000, 100)
        steps(b, pkg, 5, "the play's first steps")
        b.cmd("key down 0x%X" % os88box.keycode("right"))
        steps(b, pkg, 5, "the grey arrow down")
        dnmap = b.sym("kbd_dnmap")
        fake = bool(b.memr(dnmap + (0x2A >> 3), 1)[0] & (1 << (0x2A & 7)))
        steps(b, pkg, 25, "the grey arrow held")
        b.cmd("key up 0x%X" % os88box.keycode("right"))
        b.tap("escape", gap=300)
        b.until(lambda: pkg.byte("bz_fs") == 0, "the play to end on Esc", 30000, 100)
        b.until(lambda: pkg.word("bz_cseg") == 0 and pkg.word("bz_bseg") == 0, "the parts dropped", 10000, 50)
        b.ui_done(limit_ms=30000)
        b.tap("numlock", gap=200)
        keys = log_keys(b, pkg)
        if not fake:
            SKIPS.append("4. the fake shifts: SKIP - with the grey arrow held, kbd_track's map has no 2Ah (Left "
                         "Shift): this machine's keyboard sends no fake shift, so the case could not go red")
            print("   SKIP %s" % SKIPS[-1], flush=True)
        else:
            want(any(k & 2 for k in keys) and not any(k & 0x20 for k in keys),
                 "4. the fake shifts: 2Ah set in kbd_track's map with the grey arrow held (NumLock on), and bit 5 "
                 "(Grip) clear in every one of the play's %d recorded key bytes (Right, bit 1, among them)"
                 % len(keys))
        check_after("4. the grey-arrow play", pkg, base_rows, base_claims, claims(b, pkg, hs, eq))
    except Gone as e:
        # every later step is skipped: there is nothing left to read
        want(False, "%s (a fault charged to it - the fault log below names it)" % e)
    except SystemExit as e:
        want(False, "the machine stopped answering or a step missed: %s" % e)
    finally:
        mine, resets, kern = faults(b, since)
        b.quit(remove=not keep)
    want(not mine and not resets, "3. the fault log past the desktop: %d exceptions charged to a loaded image, "
         "%d resets (the kernel's own exceptions and 286 mode-switch resets: %d)%s" % (
             len(mine), len(resets), kern, "".join("\n        " + x for x in (mine + resets)[:6])))
    return mine


REDS = {
    # the grid by segment arithmetic: on a selector, another descriptor (SPEC.md 128.10.6.4)
    "segadd": [("bzphys.inc", "bz_step:\n    push cx\n    push es\n    mov es, [bz_cseg]\n",
                "bz_step:\n    push cx\n    push es\n"
                "    mov ax, [bz_goff]           ; RED segadd: the grid at (cseg + GRIDOFF >> 4):0\n"
                "    mov cl, 4\n    shr ax, cl\n    add ax, [bz_cseg]\n    mov es, ax\n"
                "    mov bx, [bz_goff]\n    and bx, 15\n    mov ax, [es:bx + BZG_NROWS]\n"
                "    mov es, [bz_cseg]\n")],
    # the Hercules translation's store through CS: on kern_mega a code selector takes no write
    "hxcs": [("bonanza.asm", "    es lodsb\n    xlat\n    stosb\n",
              "    es lodsb\n    xlat\n    mov [cs:di], al             ; RED hxcs: written through CS\n"
              "    inc di\n")],
    # Grip read through the key-state map, which takes a grey arrow's fake shift as Left Shift
    "shiftmap": [("bzgame.inc", "    mov ah, 2                   ; the BIOS's shift flags: bit 1 Left Shift\n"
                  "    int 16h\n    test al, 2\n    jz .out\n",
                  "    mov al, 2ah                 ; RED shiftmap: Left Shift through OSAPI_KEY_DOWN\n"
                  "    call OSAPI_KEY_DOWN\n    jnc .out\n")],
}
RED_WANT = {"segadd": None, "hxcs": None, "shiftmap": "4. the fake shifts"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only: every red arm assembles")
    a = ap.parse_args()
    if a.check:
        for line in R.check_reds(REDS, "bonanza_mega"):
            print(line)
        return 0
    for f in ("mega.img", "megak/kernel.map", "bonanza.img"):
        if not os.path.exists(os.path.join(B, f)):
            sys.exit("bonanza_mega: build/%s is not built - `make mega bonanzadisk`" % f)
    tmp = tempfile.mkdtemp(prefix="bonanzamega")
    try:
        if a.red:
            _, img_b = R.build_tree(tmp, REDS[a.red], size=1440)
            mine = run(img_b, a.keep, tmp)
            gp = [x for x in mine if " 13 at " in x or "OS88ABRT 13" in x]
            print("bonanza_mega --red %s: %d failure(s), %d exception(s) charged to the package, %d of them #GP"
                  % (a.red, len(FAILS), len(mine), len(gp)))
            if not FAILS:
                if SKIPS and RED_WANT[a.red]:
                    print("RED ARM %s could not be judged: %s" % (a.red, SKIPS[-1]))
                    return 2
                print("RED ARM %s: the row stayed GREEN against a package broken on kern_mega" % a.red)
                return 1
            if RED_WANT[a.red] is None and not mine:
                print("RED ARM %s went red, but with no exception in the fault log: %s" % (a.red, FAILS))
                return 1
            if RED_WANT[a.red] and not any(RED_WANT[a.red] in f for f in FAILS):
                print("RED ARM %s went red, but not at its own check (%r): %s" % (a.red, RED_WANT[a.red], FAILS))
                return 1
            print("bonanza_mega --red %s: PASS (the row fails against the broken package)" % a.red)
            return 0
        img_b = os.path.join(tmp, "bonanza.img")
        shutil.copy(os.path.join(B, "bonanza.img"), img_b)
        run(img_b, a.keep, tmp)
    finally:
        if a.keep or (FAILS and not a.red):
            print("bonanza_mega: kept %s" % tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    print("bonanza_mega: %s%s" % ("FAIL - %d" % len(FAILS) if FAILS else "ok",
                                  "; %d case(s) SKIPPED: %s" % (len(SKIPS), " | ".join(SKIPS)) if SKIPS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
