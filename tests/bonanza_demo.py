#!/usr/bin/env python3
"""BONANZA: recorded demos on the disk - W, L, R, D, V and the double-click (SPEC.md 128.14.7, 128.14.14 bonanzademo).

    make bonanzadisk && python3 tests/bonanza_demo.py [--adapter cga|herc|both] [--leg NAME ...]
    python3 tests/bonanza_demo.py --red NAME        (a red arm, below)
    python3 tests/bonanza_demo.py --check           (the host half: the hostile set built and each file's
                                                     refusal decided by bbcourse.check_log; the reds assembled)

On MartyPC's CGA and Hercules, BONANZA on a disk the row builds (the shipped
build/bonanza.o88, SYSTEM\\APPDATA, and a folder HOSTILE of files the HOST
wrote), the autopilot driving the play (bz_apilot, tests/bonanza_game.py):

  save     a free play of MILL by the autopilot, then W through the Save dialog
           (os88ui's chooser verbs) into ANOTHER folder (SYSTEM) as MILLA.BZR:
           the file read back off the floppy on the host equals bz_rlog's bytes,
           which equal the model's log of that play (bbcourse.encode_log); then
           Enter plays MILL again - the dialog moved the instance, so the play's
           fetches must go HOME first (128.14.7.6: `nohome`'s check)
  load     the log overwritten (a FIRST log poked in), L of SYSTEM\\MILLA.BZR:
           bz_rlog the file's bytes again, the face's log line its name
           (bz_lsv 2, bz_lfn); R to the model's end state (bbcourse.replay_log);
           D: the RESULTS page (bz_page, bz_res) and its measured frames those
           its replay presented (bz_rframes = bz_frames at its end)
  ship     V through the five shipped demos (bz_vk 0 - 4): each BZD<K>.BIN in
           bz_rlog byte for byte, D'd to its recorded end equal to the model's
           replay of it (nstep, the position, the velocities, the falls)
  hostile  THE HOSTILE SET (128.14.7.2), each through L's Open dialog: an
           extension not BZR, 15 bytes, 4,097 bytes, a bad magic, K = BZ_NCRS,
           material 3, +6 bit 3, an identity of another build, +7 another
           physics, N = 0, a length one byte off 16 + 2N, a TILT log one off
           16 + 3N, steps one off the sum, a count of 0, a key byte with bit 7,
           a tilt nibble of 9 - each REFUSED with its toast (`Not a Bonanza
           demo` for the first three, `Demo from other physics` for +7, `Damaged
           demo file` for the rest), bz_rlog unchanged byte for byte, no part
           row fetched, the instance's claims as before (tools/heapmap.py), and
           for the first three bz_lfile NEVER ENTERED - so no claim and no
           OSAPI_FILE_READ (breakpoints on bz_lfile and its read)
  dclick   with the window closed, a DOUBLE-CLICK on SYSTEM\\MILLA.BZR in the
           Disk window opens BONANZA with it loaded (bz_rlog, bz_lsv 2, bz_lfn),
           and R after it fetches MILL from home and replays to the model's end;
           then the double-click legs of the set, each a new instance: 4,097
           bytes refused by FERR_BIG before any data (`Not a Bonanza demo`, the
           read's capacity 4,096), 15 bytes (`Not a Bonanza demo`), a bad
           identity (`Damaged demo file`) - no log held, no part fetched, the
           instance's claims those of a plain open

--red NAME builds a broken package in a temporary directory (never build/) and
PASSES only if the row FAILS - at its own check:
  nosum      the step-sum check removed: the off-by-one file is accepted (hostile)
  readfirst  the size refused after the read: the 4,097-byte file reaches bz_lfile's read
  stageleak  the staging claim not freed on a refusal (hostile's claims)
  inplace    the checks run on what is already in bz_rlog: a refused file damages the log
  nohome     bz_home does not go home: the play after W cannot read its parts (save)
  argsize    the double-click reads at a capacity of 64KB: the 4,097-byte file is read
"""
import argparse
import os
import re
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import os88flush               # noqa: E402
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_exit as X       # noqa: E402
import bonanza_game as GM      # noqa: E402

LEGS = ("save", "load", "ship", "hostile", "dclick")
SAVENAME = "MILLA.BZR"


def toasts():
    """the package's own toast strings, read from bonanza.asm's TOASTSTRs"""
    t = open(os.path.join(ROOT, "apps", "bonanza", "bonanza.asm")).read()
    return {n: s for n, s in re.findall(r"^TOASTSTR (bz_t_\w+), ['\"](.*)['\"]\s*$", t, re.M)}


def mill_log():
    k = R.CRS_K["mill"]
    return R.make_log(GM.auto_keys(k), k, R.course_k(k).ball)


def tilt_log():
    """a valid TILT log of MOON (128.14.8.3): 40 steps, its caps changing"""
    k = R.CRS_K["moon"]
    keys = [BB.K_R] * 20 + [BB.K_D] * 20
    tilts = [0x80 + (i // 5) for i in range(20)] + [0x08 + 0x10 * (i // 5) for i in range(20)]
    return BB.encode_log(keys, course=k, mat=R.course_k(k).ball, ident=R.course_k(k).ident, tilts=tilts)


def hostile_set():
    """[(file name, bytes, the toast's label, the check bbcourse.check_log fails
    or None for a refusal before it, first-three)] - SPEC.md 128.14.14's set"""
    good = bytearray(mill_log())
    tl = bytearray(tilt_log())
    k = R.CRS_K["mill"]
    out = [("H01.BZX", bytes(good), "bz_t_notbzr", None, True),
           ("H02.BZR", bytes(good[:15]), "bz_t_notbzr", 1, True),
           ("H03.BZR", bytes(good) + bytes(4097 - len(good)), "bz_t_notbzr", 1, True)]

    def mut(name, f, toast="bz_t_dmg", base=good):
        b = bytearray(base)
        f(b)
        out.append((name, bytes(b), toast, None, False))
    mut("H04.BZR", lambda b: b.__setitem__(slice(0, 4), b"BZR2"))
    mut("H05.BZR", lambda b: b.__setitem__(4, GM.ncrs()))
    mut("H06.BZR", lambda b: b.__setitem__(5, 3))
    mut("H07.BZR", lambda b: b.__setitem__(6, b[6] | 8))
    mut("H08.BZR", lambda b: struct.pack_into("<H", b, 14, R.course_k(k).ident ^ 0x0101))
    mut("H09.BZR", lambda b: b.__setitem__(7, (BB.PHYSV ^ 0x5A) & 0xFF), "bz_t_phys")

    def n0(b):
        struct.pack_into("<H", b, 12, 0)
        del b[16:]
    mut("H10.BZR", n0)
    mut("H11.BZR", lambda b: b.append(0))
    mut("H12.BZR", lambda b: b.append(0), base=tl)
    mut("H13.BZR", lambda b: struct.pack_into("<I", b, 8, struct.unpack_from("<I", b, 8)[0] + 1))
    def c0(b):                                                      # the first run's count 0, the
        struct.pack_into("<I", b, 8, struct.unpack_from("<I", b, 8)[0] - b[17])   # steps still its sum
        b[17] = 0
    mut("H14.BZR", c0)
    mut("H15.BZR", lambda b: b.__setitem__(16, b[16] | 0x80))       # the first run's key byte
    mut("H16.BZR", lambda b: b.__setitem__(17, 0x89), base=tl)      # the first run's tilt byte, y cap 9
    ids = [R.course_k(i).ident for i in range(GM.ncrs())]
    res = []
    for name, raw, toast, _c, first in out:
        chk = BB.check_log(raw, GM.ncrs(), ids)
        res.append((name, raw, toast, chk, first))
    return res


def check_set():
    """-> failure lines: every hostile file refused by the model's checks (but
    the extension, refused by its name), in the toast the guest must give"""
    bad = []
    for name, raw, toast, chk, first in hostile_set():
        why = "its extension" if name.endswith(".BZX") else chk
        print("bonanza_demo hostile %s %4d bytes: %s -> %s" % (name, len(raw), why, toasts()[toast]))
        if not name.endswith(".BZX") and chk is None:
            bad.append("hostile %s: bbcourse.check_log ACCEPTS it" % name)
        if chk and toast == "bz_t_phys" and chk[0] != 5:
            bad.append("hostile %s: refused at check %d, not 5 (physics)" % (name, chk[0]))
    ids = [R.course_k(i).ident for i in range(GM.ncrs())]
    for nm, lg in (("MILL's autopilot", mill_log()), ("MOON's TILT", tilt_log())):
        if BB.check_log(lg, GM.ncrs(), ids) is not None:
            bad.append("the base %s log is itself refused: %s" % (nm, BB.check_log(lg, GM.ncrs(), ids)))
    return bad


def fresh(g):
    """(part rows, claims) of the instance now, bonanza_exit's readers"""
    g.m.pause()
    r = (X.rows(g), X.claims(g))
    g.m.run()
    return r


def rows_fetched(base, now):
    title = X.title_rows()
    return [i for i, ((f0, _), (f1, _)) in enumerate(zip(base, now)) if i not in title and f1 & X.OP_FETCHED]


def end_state(g):
    return (g.d("bz_nstep"), g.d("bz_gx"), g.d("bz_gy"), g.sd("bz_gz"), g.s("bz_gvx"), g.s("bz_gvy"),
            g.s("bz_gvz"), g.w("bz_nfall"))


def model_end(log):
    k = log[4]
    p, _first = BB.replay_log(R.course_k(k), bytes(log))
    return (p.nstep, p.gx, p.gy, p.gz, p.gvx, p.gvy, p.gvz, p.nfall)


def pick(ui, path):
    """answer the chooser with PATH ('FOLDER/NAME'): the name where the chooser
    opened, else in the folder, else from the parent"""
    w = ui.chooser()
    folder, name = path.split("/")
    for spec in (name, path, "../" + path):
        try:
            for p in spec.split("/")[:-1]:
                ui.open(p, expect="nav", win=w)
            ui.entry(name, w)
            ui.open(name, expect=None, win=w)
            ui.chooser_gone()
            return
        except os88ui.UIError:
            continue
    raise os88ui.UIError("the chooser never showed %s" % path)


def leg_save(g, ui):
    fails = []
    m = g.m
    k = R.CRS_K["mill"]
    GM.free_play(g, k, R.course_k(k).ball, "MILL by the autopilot")
    want = mill_log()
    got = bytes(m.read(g.a("bz_rlog"), len(want)))
    if got != want:
        fails.append("save: MILL's play left a log that is not the model's (%d bytes)" % len(want))
    GM.guard(g)
    g.key("KeyW")
    ui.chooser_save(SAVENAME, folders=("SYSTEM",))
    ui.wait_toast(says=toasts()["bz_t_saved"])
    GM.motor_off(g)
    try:
        f = os88flush.Flush(marty=m).volume(1).read("SYSTEM/" + SAVENAME)
    except os88flush.FlushError as e:
        f = None
        fails.append("save: SYSTEM\\%s is not on the floppy: %s" % (SAVENAME, e))
    if f is not None and f != got:
        fails.append("save: the file read back off the floppy (%d bytes) is not bz_rlog's %d" % (len(f), len(got)))
    try:
        GM.free_play(g, k, R.course_k(k).ball, "MILL after W (the fetch from home)")
        ok = bool(g.b("bz_goal"))
    except (AssertionError, M.MartyError) as e:  # (a refused launch: no bracket ever comes up -
        ok = False                               # until's own error, the `nohome` red's case)
        fails.append("save: the play after W did not run (%s): its parts were not read from home, toast %r" % (
            e, ui.toast()[0]))
    print("%s save: MILL's log the model's, W into SYSTEM, the file = bz_rlog, the play after W at home: %s" % (
        g.tag, "yes" if not fails and ok else "NO"), flush=True)
    return fails


def leg_load(g, ui):
    fails = []
    m = g.m
    want = mill_log()
    m.pause()
    g.write_log(R.make_log([0] * 30, R.CRS_K["first"], 0))
    m.run()
    GM.guard(g)
    g.key("KeyL")
    pick(ui, "SYSTEM/" + SAVENAME)
    M.until(m, lambda _: bytes(m.read(g.a("bz_rlog"), len(want))) == want, "L to load %s" % SAVENAME, guest=20)
    lfn = bytes(m.read(g.a("bz_lfn"), 13)).split(b"\0")[0].decode("latin-1")
    if g.b("bz_lsv") != 2 or lfn != SAVENAME:
        fails.append("load: the log line is kind %d naming %r, not 2 and %r" % (g.b("bz_lsv"), lfn, SAVENAME))
    g.key("KeyR")
    GM.bracket(g, "R of the loaded log")
    if end_state(g) != model_end(want):
        fails.append("load: R ended at %s, the model's replay at %s" % (end_state(g), model_end(want)))
    GM.guard(g)
    g.key("KeyD")
    GM.bracket(g, "D of the loaded log")
    fr, rfr = g.w("bz_frames"), g.w("bz_rframes")
    if g.b("bz_page") == 0 or not g.b("bz_res") or rfr != fr or end_state(g) != model_end(want):
        fails.append("load: D left page %d, bz_res %d, its results' frames %d against the replay's %d, end %s "
                     "(the model's %s)" % (g.b("bz_page"), g.b("bz_res"), rfr, fr, end_state(g), model_end(want)))
    print("%s load: L of %s, R and D to the model's end, D's RESULTS (%d frames): %s" % (
        g.tag, SAVENAME, rfr, "yes" if not fails else "NO"), flush=True)
    return fails


def leg_ship(g):
    fails = []
    m = g.m
    art = R.at("build/bonanza-art")
    m.pause()
    g.putb("bz_vk", 0)
    m.run()
    rep = []
    for kd in range(1, GM.ncrs()):
        demo = open(os.path.join(ROOT, art, "BZD%d.BIN" % kd), "rb").read()
        GM.guard(g)
        g.key("KeyV")
        M.until(m, lambda _: bytes(m.read(g.a("bz_rlog"), len(demo))) == demo,
                "V to load BZD%d.BIN" % kd, guest=20)
        GM.guard(g)
        g.key("KeyD")
        GM.bracket(g, "D of BZD%d.BIN" % kd, guest=200)
        got, want = end_state(g), model_end(demo)
        rep.append("BZD%d %d steps" % (kd, got[0]))
        if got != want:
            fails.append("ship: D of BZD%d.BIN ended at %s, the model's replay at %s" % (kd, got, want))
    print("%s ship: %s, each D'd to the model's end: %s" % (g.tag, ", ".join(rep), "yes" if not fails else "NO"),
          flush=True)
    return fails


def leg_hostile(g, ui):
    fails = []
    m = g.m
    T = toasts()
    m.pause()
    g.write_log(mill_log())
    m.run()
    for name, raw, toast, _chk, first in hostile_set():
        base_rows, base_claims = fresh(g)
        m.pause()
        log0 = bytes(g.read_log())
        m.write(ui._S("toast_buf"), b"\0")
        m.run()
        with M.bp_trace(m, g.a("bz_lfile"), g.a("bz_lfile.read"), log=True) as tr:
            GM.guard(g)
            g.key("KeyL")
            pick(ui, "HOSTILE/" + name)
            try:
                txt = ui.wait_toast(says=T[toast])
            except Exception:
                txt = None
            M.guest_sleep(m, 0.3)
            nl = tr.count()
        rows_now, claims_now = fresh(g)
        m.pause()
        log1 = bytes(g.read_log())
        m.run()
        why = []
        if txt is None:
            why.append("no `%s` toast (it says %r)" % (T[toast], ui.toast()[0]))
        if log1 != log0:
            why.append("bz_rlog CHANGED")
        f = rows_fetched(base_rows, rows_now)
        if f:
            why.append("part row(s) %s fetched" % f)
        if claims_now != base_claims:
            why.append("the claims %s, before %s" % (claims_now, base_claims))
        if first and nl:
            why.append("bz_lfile (its claim and OSAPI_FILE_READ) reached %d time(s)" % nl)
        if why:
            fails.append("hostile %s (%d bytes): %s" % (name, len(raw), "; ".join(why)))
    print("%s hostile: %d files through L, each refused with its toast, the log, rows and claims as before: %s" % (
        g.tag, len(hostile_set()), "yes" if not fails else "NO"), flush=True)
    return fails


def leg_dclick(ui, tag, sym, g):
    """the double-click: a good .BZR, then three of the set, each a new instance"""
    fails = []
    T = toasts()
    m = ui.m
    base_claims = None
    want = mill_log()
    cases = [("SYSTEM", SAVENAME, None)] + [("HOSTILE", n, t) for n, t in (
        ("H03.BZR", "bz_t_notbzr"), ("H02.BZR", "bz_t_notbzr"), ("H08.BZR", "bz_t_dmg"))]
    where = "B:/"
    for folder, name, toast in cases:
        ui.close(g.win)
        dw = R.disk_b(ui)
        if where != folder:
            if where != "B:/":
                ui.open("..", expect="nav", win=dw)
            ui.open(folder, expect="nav", win=dw)
            where = folder
        m.pause()
        m.write(ui._S("toast_buf"), b"\0")
        m.run()
        ui.open(name)
        g = R.Bz(ui, tag, sym, live=True)
        ui.settle()
        if toast:
            try:
                txt = ui.wait_toast(says=T[toast])
            except Exception:
                txt = None
        rows, claims = fresh(g)
        why = []
        if toast is None:
            if bytes(m.read(g.a("bz_rlog"), len(want))) != want or g.b("bz_lsv") != 2:
                why.append("the log is not %s's (bz_lsv %d)" % (name, g.b("bz_lsv")))
            base_claims = claims
            g.key("KeyR")
            GM.bracket(g, "R after the double-click")
            if end_state(g) != model_end(want):
                why.append("R after it ended at %s, the model's %s" % (end_state(g), model_end(want)))
        else:
            if txt is None:
                why.append("no `%s` toast (it says %r)" % (T[toast], ui.toast()[0]))
            if bytes(m.read(g.a("bz_rlog"), 4)) == b"BZR1":
                why.append("a log is held")
            if claims != base_claims:
                why.append("the claims %s, a plain open's %s" % (claims, base_claims))
        if [i for i, (fl, _) in enumerate(rows) if i not in X.title_rows() and fl & X.OP_FETCHED]:
            why.append("a part row is held")
        if why:
            fails.append("dclick %s: %s" % (name, "; ".join(why)))
    print("%s dclick: %s opened BONANZA with it, R from home; three of the set refused: %s" % (
        tag, SAVENAME, "yes" if not fails else "NO"), flush=True)
    return fails


def build_img(td, o88=None):
    files = []
    hd = os.path.join(td, "hostile")
    os.makedirs(hd, exist_ok=True)
    for name, raw, _t, _c, _f in hostile_set():
        p = os.path.join(hd, name)
        open(p, "wb").write(raw)
        files.append("HOSTILE:" + p)
    return R.disk(td, files, name="demo", o88=o88)


def run(tag, legs=LEGS, src=None, o88=None):
    sym = R.symbols(src)
    fails = []
    with tempfile.TemporaryDirectory() as td:
        img = build_img(td, o88)
        with GM.boot(tag, img) as ui:
            g = GM.open_game(ui, tag, sym)
            if "save" in legs:
                fails += leg_save(g, ui)
            if "load" in legs and not fails:
                fails += leg_load(g, ui)
            if "ship" in legs and not fails:
                fails += leg_ship(g)
            if "hostile" in legs and not fails:
                fails += leg_hostile(g, ui)
            if "dclick" in legs and not fails:
                fails += leg_dclick(ui, tag, sym, g)
    return fails


REDS = {
    # 7: the steps check removed
    "nosum": [("bonanza.asm", "    cmp ax, [es:BZR_STEPS]      ; 7: the steps, the runs' sum\n    jne .out\n"
               "    cmp bp, [es:BZR_STEPS + 2]\n    jne .out\n",
               "    nop                         ; RED nosum: no step-sum check\n")],
    # the size refused after the read: no size test before bz_lfile (its claim of 4,097 reads)
    "readfirst": [("bonanza.asm", "    cmp cx, BZR_SIZE\n    ja .not\n    xor al, al                  ; the size is the dialog's: exact\n",
                   "    xor al, al                  ; RED readfirst: the size after the read\n")],
    # the staging claim not freed on a refusal
    "stageleak": [("bonanza.asm", ".ref:\n    call .free\n    pop es\n.toast:\n",
                   ".ref:\n    pop es                      ; RED stageleak: the claim kept\n.toast:\n")],
    # the bytes into bz_rlog BEFORE the checks (the checks run on the log's copy)
    "inplace": [("bonanza.asm", ".chk:\n    call bz_lchk                ; 2 - 8\n",
                 ".chk:\n    mov cx, [bz_lfsz]           ; RED inplace: into the log first\n    cld\n"
                 "    push ds\n    push ds\n    push es\n    pop ds\n    pop es\n    xor si, si\n"
                 "    mov di, bz_rlog\n    rep movsb\n    pop ds\n    mov es, [bz_lseg]\n"
                 "    call bz_lchk\n")],
    # bz_home does not go home
    "nohome": [("bonanza.asm", "bz_home:\n    push bx\n",
                "bz_home:\n    mov byte [bz_hmov], 0       ; RED nohome: never moves\n    clc\n    ret\n"
                "    push bx\n")],
    # the double-click reads at a capacity of 64KB
    "argsize": [("bonanza.asm", "    mov al, 1\n    mov cx, BZR_SIZE\n    call bz_lfile\n",
                 "    mov al, 1\n    mov cx, 0fff0h              ; RED argsize: 64KB\n    call bz_lfile\n")],
}
RED_LEGS = {"nosum": ("hostile",), "readfirst": ("hostile",), "stageleak": ("hostile",), "inplace": ("hostile",),
            "nohome": ("save",), "argsize": ("save", "dclick")}
RED_WANT = {"nosum": "hostile H13", "readfirst": "hostile H03", "stageleak": "the claims",
            "inplace": "bz_rlog CHANGED", "nohome": "save: the play after W", "argsize": "dclick H03"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--leg", action="append", choices=LEGS)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only")
    a = ap.parse_args()
    if a.check:
        bad = check_set()
        for line in R.check_reds(REDS, "bonanza_demo"):
            print(line)
        for b in bad:
            print("FAIL %s" % b)
        assert not bad, "%d hostile file(s) not decided" % len(bad)
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    legs = tuple(a.leg) if a.leg else LEGS
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, _img = R.build_tree(td, REDS[a.red])
            o88 = os.path.join(td, "BONANZA.O88")
            for tag in tags:
                try:
                    bad = run(tag, RED_LEGS[a.red], src=src, o88=o88)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(RED_WANT[a.red] in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (a.red, tag, RED_WANT[a.red], bad)
                print("bonanza_demo --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_demo --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad = []
    for tag in tags:
        bad = run(tag, legs)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d demo failure(s)" % len(allbad)
    print("bonanza_demo (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
