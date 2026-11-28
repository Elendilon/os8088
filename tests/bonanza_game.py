#!/usr/bin/env python3
"""BONANZA: the GAME - the bests and BONANZA.DAT (SPEC.md 137.14.3, 137.14.14 bonanzagame).

    make bonanzadisk && python3 tests/bonanza_game.py [--adapter cga|herc|both] [--leg NAME ...]
    python3 tests/bonanza_game.py --red NAME        (a red arm, below)
    python3 tests/bonanza_game.py --check           (the host half: the model's plays, the hostile
                                                     files built and decided, every red arm assembled)

The game is driven by the AUTOPILOT: `bz_apilot` (a harness byte, never set
by the package) makes a PLAY take its key bytes from `bz_auto`, recorded as a
play's (bzphys.inc bz_step) - so a course is played by exactly the keys
bbcourse.Physics.auto() chooses, and its time is the MODEL's, the same on
both cards.

ONE BOOT A CARD (docs/plans/BOUNCE-BONANZA-SOAK.md phase 3), on the TEST courses (SPEC.md 137.54) found by
NAME: TQUIK, the goal 165 autopilot steps (3.0 s) from its start, is the course every best is made on, and
TCUP (its cup 291 steps away) the second course a file names.  The disk is the row's (the package, with
SYSTEM\\APPDATA as bonanzadisk builds it) and carries EVERY hostile and physics-identity file the legs need,
each under a name of its own in SYSTEM\\APPDATA (BZH<nn>.DAT, BZP<n>.DAT, BZNONE.DAT): a case is a RELOAD,
not a boot - BONANZA.DAT's name in the package ([bz_s_dat]) POKED to the case's file, od_write's state byte
([bz_datst]) cleared (a session's first save is a full write, SPEC.md 19.9.1), and the entry proc's own
reader, bz_dload, CALLED in the window's task (dat_reload: the guest stopped at T's handler, bz_tkey - a key
callback, where W and L do their file work - and returned there).  The one difference from a boot is that
the reader runs a second time in a live instance, which is what bz_dsave does at every save anyway.  The
legs, on MartyPC's CGA (os8088_5150_cga_gla) and Hercules (os8088_5150_herc_gla):

  posts   V loads ROLL's and HOP's SHIPPED demos ([bz_vk] poked to each one's row), R replays a TQUIK log
          MADE FROM THE MODEL (the autopilot's play, bbcourse.encode_log) to its goal, D benchmarks it,
          and D runs a TCUP log to the CUP - and after each BONANZA.DAT is still ABSENT from the floppy
          (read off it on the host, os88flush): only a PLAY posts a best (137.14.3.3)
  pause   a free play of TQUIK with its own ball, P pressed at step 40: no step for a guest second, the
          log unchanged; P again: the play ends at the model's goal step (the pause added none) with the
          model's log, and BONANZA.DAT holds TQUIK's best alone
  hostile a reload a file: the hostile BONANZA.DAT set (a 32-byte file whose bytes are a valid head with a
          best - the length; a bad magic; an entry under a foreign key; a duplicate key; a best of 0; a
          count past BZD_NENT; entries out of order, ...; slots judged alone, keyed by PAD: another pathway
          version, a pad word past the pathway's, exit bits past the pad's course's) - bz_dat after the
          reader is the image 137.14.3.3 and 137.14.17 item 6 say (the file refused whole, or the bad entry
          alone), and the next best (TQUIK by the autopilot) REWRITES THE FILE WHOLE as this build's BZS5
          bytes
  physdat wave 6 (SPEC.md 137.16.9, 137.16.14): BONANZA.DAT +5 is BZ_PHYSV.  A reload a file, each
          carrying THIS build's course identities and a best on every course: +5 = 00h (5b's unset
          value), +5 = A0h (5b's physics) and (wave 6b, SPEC.md 137.17.7, 137.17.10) +5 = 25h (wave 6's:
          the owner's round-1 disk) load with the identities kept and EVERY best cleared (bz_dat the first
          run's image), and the next best (TQUIK by the autopilot) rewrites the file whole with
          +5 = BZ_PHYSV and TQUIK's best alone; the same file with +5 = BZ_PHYSV keeps every best (the
          control: the clear is the physics test's, not the identities').  Every expected byte is DERIVED
          - BZ_PHYSV out of the build's bzcourse.inc, the course count out of BZ_COURSES - so a retune
          turns nothing red
  noapp   NO SYSTEM\\APPDATA (last: it is not put back for a later leg): a reload of BZNONE.DAT (an empty
          image, so neither course holds a best), then the folder's name in the package (od_s_appdat)
          POKED to one the disk has not and od_write's bank dropped ([od_gen] 0), so every save walks and
          finds no folder - as a disk built without one: a best toasts `Best times not saved` once
          (bz_toast reached once over two bests, TQUIK's and TCUP's; bz_datw 1), no folder made, and the
          last file named on the disk unchanged

--red NAME builds a broken package (or image) in a temporary directory (never
build/) and PASSES only if the row FAILS - at its own check:
  datlen      BONANZA.DAT's length check removed: the 32-byte file's best is shown (hostile short)
  replaybest  a replay posts a best: the posts leg's R of the TQUIK log
  noappdata   the leg's image built without SYSTEM\\APPDATA: the pause leg's read-back
  physdat     wave 6: bz_dnorm's +5 test left out (a file under other physics
              keeps its bests): the physdat leg's cleared-bests check, a best kept
  explorepad  EXPLORE's pad held to the open set: hostile explore
  pastbest    the bests past the pathway's pads unchecked: hostile wide
  dupkey      BZS5: a second entry with a key kept: hostile dupkey
  exitmask    BZS5: the exits found not masked to the pad's course's: hostile exitbits
  pathver     BZS5: a slot of another pathway version kept: hostile pathver
"""
import argparse
import os
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

DAT = "SYSTEM/APPDATA/BONANZA.DAT"
NENT = 23                       # BZD_NENT = BZ_CRS_MAX (SPEC.md 137.22.5.1: BZS5's best entries)
LEGS = ("posts", "pause", "hostile", "physdat", "noapp")     # (one boot, in this order: noapp last)
PHYSV_5B = 0xA0                 # wave 5b's BZ_PHYSV (SPEC.md 137.16.9: PHYSV_SHIPPED's last before wave 6)
PHYSV_6 = 0x25                  # wave 6's, on the owner's round-1 disk (SPEC.md 137.17.7: its bests cleared once)


# ---- the model's side -----------------------------------------------------------
_AUTO = {}


def ncrs():
    """BZ_NCRS, the courses of the build (bzcourse.inc's)"""
    return _equ("BZ_NCRS")


def first():
    """THE course every best is made on: TQUIK's K, by its NAME (never a literal K: BZ_COURSES's order
    moves).  (The name is the leg's history: it was FIRST's, a prototype course, until phase 3)"""
    return R.CRS_K["tquik"]


def second():
    """the OTHER course a file names (and noapp's second best): TCUP's K, by its name"""
    return R.CRS_K["tcup"]


def physv():
    """this build's BZ_PHYSV, read out of the GENERATED bzcourse.inc (never a
    literal: a retune moves it, SPEC.md 137.16.11)"""
    import re
    inc = open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzcourse.inc")).read()
    return int(re.search(r"^BZ_PHYSV\s+equ\s+0?([0-9A-Fa-f]+)h", inc, re.M).group(1), 16)


def auto_steps(k, mat=None):
    """the model's autopilot PLAY on course K with material MAT (its own ball
    by default): -> (steps at its goal, falls), (None, falls) when it does not
    finish within bbcourse.DEMO_STEPS"""
    key = (k, mat)
    if key not in _AUTO:
        c = R.course_k(k)
        p = BB.Physics(c, play=True, mat=c.ball if mat is None else mat)
        keys = []
        while p.nstep < BB.DEMO_STEPS and not p.goal:
            kb = p.auto()
            p.step(kb)
            keys.append(kb)
        _AUTO[key] = ((p.nstep if p.goal else None), p.nfall, keys)
    return _AUTO[key][:2]


def auto_keys(k, mat=None):
    auto_steps(k, mat)
    return _AUTO[(k, mat)][2]


def _inc():
    return open(os.path.join(ROOT, R.at("build/bonanza-art"), "bzcourse.inc")).read()


def _words(macro):
    """a `dw` macro of the generated bzcourse.inc, as ints"""
    import re
    m = re.search(r"^%%macro %s 0\n\s+dw ([^\n]+)" % macro, _inc(), re.M)
    return [int(x.strip().rstrip("h"), 16) for x in m.group(1).split(",")]


def _equ(name):
    import re
    return int(re.search(r"^%s\s+equ\s+(\d+)" % name, _inc(), re.M).group(1))


def keys():
    """K -> course K's SAVE KEY (SPEC.md 137.22.5.1): bzcourse.inc's BZ_CRS_KEYS"""
    return dict(enumerate(_words("BZ_CRS_KEYS")))


def path_ver():
    """the pathway's version, a slot's +20 (BZ_PATH_VER, SPEC.md 137.22.5.1)"""
    return _equ("BZ_PATH_VER")


def pad_exits():
    """pad -> the exits of the course it plays, a bit each (BZ_PAD_EXITS): a slot's exits found are masked
    to them on load"""
    return _words("BZ_PAD_EXITS")


PAD_MAX = 23                    # BZ_PAD_MAX (SPEC.md 137.22.5.1): a slot's word-a-pad tables
SLOTB = 22 + 4 * PAD_MAX        # BZS5 (SPEC.md 137.22.5.1): 23 best entries, three 114-byte slots
SLOT_OFF = 8 + 6 * NENT         # BZD_SLOT: the first slot, +146 (no reserved bytes since BZS5)
DAT_FILE0 = SLOT_OFF + 3 * SLOTB  # BZD_FILE0: BZS5 before THE LIVES GIVEN (SPEC.md 137.55), still read
LIFE_OFF = DAT_FILE0            # BZD_LIFE: a dword a slot, a bit a pad whose `once` life the game took
DAT_FILE = LIFE_OFF + 4 * 3
BB_LIVES = 5                    # bonanza.asm BZ_LIVES, a new game's lives
BB_LVMAX = 9                    # bzcourse.inc BZ_LVMAX, a slot's most lives (a LIFE pickup's, 137.55)
assert DAT_FILE == 500, "BZS5 is 500 bytes: under one sector, never a whole one (od_write's in-place arm)"


def crs_max():
    """bzcourse.inc's BZ_CRS_MAX (the tool's, bonanza.asm BZD_NENT)"""
    return _equ("BZ_CRS_MAX")


def slot(lives, mode=0, pad=0, open_=1, done=0, ropn=0, rtak=0, ver=None, exits=None, best=None, z3=0, tail=b""):
    """one 114-byte BZS5 slot (SPEC.md 137.22.5.1): +0 lives, +1 the mode, +2 the pad, +3 zero, +4 the open
    pads, +8 the done ones, +12 the routes opened, +16 taken (dwords), +20 the pathway's VERSION, +22 the
    exits found (a word a PAD, 23), +68 the best a pad (23 words).  TAIL is poked over the last bytes"""
    ex = [0] * PAD_MAX
    for k, v in (exits or {}).items():
        ex[k] = v
    be = [0] * PAD_MAX
    for k, v in (best or {}).items():
        be[k] = v
    b = struct.pack("<BBBBIIIIH", lives, mode, pad, z3, open_, done, ropn, rtak,
                    path_ver() if ver is None else ver)
    b += struct.pack("<%dH%dH" % (PAD_MAX, PAD_MAX), *ex, *be)
    b = bytearray(b)
    if tail:
        b[SLOTB - len(tail):] = tail
    assert len(b) == SLOTB
    return bytes(b)


def entries(best):
    """BEST -> the 23 entries in FILE ORDER: a dict {K: (steps, falls)} fills entries 0, 1, ... in its order;
    a list is the entries themselves, each (K, steps, falls) or None for an empty one"""
    if isinstance(best, dict):
        best = [(k, t, f) for k, (t, f) in best.items()]
    out = list(best) + [None] * (NENT - len(best))
    assert len(out) == NENT
    return out


def dat_image(best=None, count=None, pv=None, slots=None, old=0, magic=b"BZS5", given=None):
    """the bytes bz_dat holds and a save writes (SPEC.md 137.14.3.3, 137.22.5.1): `BZS5`, 488 bytes, 23 best
    entries in NO ORDER (BEST, entries()'s forms: each +0 the course's SAVE KEY, +2 the steps, +4 the falls),
    +5 PV (this build's BZ_PHYSV by default) and three 114-byte SLOTS (bytes, or empty).  OLD = 64 / 304 /
    494: an older layout's LENGTH (`BZT1` / `BZS3` / `BZS4`, no longer read: the bytes only have to be of
    that length); 488 BZS5 before THE LIVES GIVEN (SPEC.md 137.55: still read, the table zero).  GIVEN: the
    three slots' lives-given dwords"""
    kt = keys()
    if old:
        magic = {64: b"BZT1", 304: b"BZS3", 494: b"BZS4", DAT_FILE0: b"BZS5"}[old]
    b = bytearray(magic + bytes([ncrs() if count is None else count, physv() if pv is None else pv, 0, 0]))
    for e in entries(best or {}):
        if e is None:
            b += bytes(6)
        else:
            k, t, f = e
            b += struct.pack("<HHH", kt[k], t, f)
    b += slots if slots is not None else bytes(3 * SLOTB)
    b += struct.pack("<3I", *(given or (0, 0, 0)))
    assert len(b) == DAT_FILE
    if old:
        b = (b + bytes(max(0, old - len(b))))[:old]
    return bytes(b)


def posted(best, k, t, f=0):
    """BEST (entries()'s forms) after a play's best T on course K as bz_post files it (137.22.5.1): into the
    entry holding K's key when T beats it, else into the FIRST EMPTY entry -> the list form"""
    es = entries(best)
    for i, e in enumerate(es):
        if e is not None and e[0] == k:
            if not e[1] or t < e[1]:
                es[i] = (k, t, f)
            return es
    es[es.index(None)] = (k, t, f)
    return es


def model_load(raw):
    """SPEC.md 137.22.5.1's reader, in Python - an independent second reading of the rules bz_dload,
    bz_dchk, bz_dnorm and bz_dslots apply: RAW -> the image the entry proc makes"""
    kt = keys()
    ks = set(kt.values())
    np_, vx = npad(), pad_exits()
    ok = len(raw) in (DAT_FILE, DAT_FILE0) and raw[:4] == b"BZS5" and 1 <= raw[4] <= NENT \
        and raw[6:8] == b"\0\0"
    b = bytearray(raw) + bytes(DAT_FILE - len(raw)) if ok else bytearray(DAT_FILE)
    if ok:
        for i in range(NENT):
            key, t, f = struct.unpack_from("<HHH", b, 8 + 6 * i)
            if f > 9999 or (key == 0 and (t or f)):
                ok = False
        if not ok:
            b = bytearray(DAT_FILE)
    for s_ in range(3):
        o = SLOT_OFF + s_ * SLOTB
        lv, md, pd, z3, op, dn, ro, rt, ver = struct.unpack_from("<BBBBIIIIH", b, o)
        wd = struct.unpack_from("<%dH" % (2 * PAD_MAX), b, o + 22)
        bad = lv > BB_LVMAX or md & 0xFE or z3 or rt & ~ro or any(wd[np_:PAD_MAX]) or any(wd[PAD_MAX + np_:]) \
            or ver != path_ver() or (lv and (not op & 1 or pd >= np_ or (not md & 1 and not op >> pd & 1)))
        if bad:
            b[o:o + SLOTB] = bytes(SLOTB)
            b[LIFE_OFF + 4 * s_:LIFE_OFF + 4 * s_ + 4] = bytes(4)
        for p_ in range(np_):
            w = struct.unpack_from("<H", b, o + 22 + 2 * p_)[0]
            struct.pack_into("<H", b, o + 22 + 2 * p_, w & vx[p_])
    if b[5] != physv():
        ok = False
    b[0:8] = b"BZS5" + bytes([ncrs(), physv(), 0, 0])
    seen = set()
    for i in range(NENT):
        o = 8 + 6 * i
        key, t, f = struct.unpack_from("<HHH", b, o)
        if not ok or key not in ks or not 1 <= t <= 65534 or key in seen:
            b[o:o + 6] = bytes(6)
        else:
            seen.add(key)
    return bytes(b)


def hostile_set():
    """[(name, the file's bytes, the bz_dat image the entry proc must make,
    the bests the next TQUIK play files)] - SPEC.md 137.14.3.3's hostile set,
    137.14.17 item 6's whole-file refusals and 137.22.5.1's keys and pads.
    TQUIK's play (the autopilot, its own ball) is the next best in every case,
    so each file is REWRITTEN WHOLE.  (F is TQUIK, the course played; T is TCUP, the file's other course)"""
    F, T = first(), second()
    t1, _ = auto_steps(F)
    fresh = dat_image()
    out = []
    good = bytearray(dat_image({F: (t1 + 99, 2), T: (499, 0)}))
    # the LENGTH: 32 bytes that are a valid head with TQUIK's best (the datlen red shows it)
    short = bytes(dat_image({F: (99, 0)})[:32])
    out.append(("short", short, fresh, {F: (t1, 0)}))
    bad = bytearray(good)
    bad[3] = ord("4")                                     # `BZS4` at BZS5's length
    out.append(("magic", bytes(bad), fresh, {F: (t1, 0)}))
    bad = bytearray(good)
    struct.pack_into("<H", bad, 8, keys()[F] ^ 0x0101)    # TQUIK's entry under a FOREIGN key: dropped alone
    out.append(("foreign", bytes(bad), dat_image([None, (T, 499, 0)]), posted([None, (T, 499, 0)], F, t1)))
    bad = bytearray(good)
    struct.pack_into("<HH", bad, 8 + 2, 0, 3)             # TQUIK's best 0 (its falls 3)
    out.append(("zero", bytes(bad), dat_image([None, (T, 499, 0)]), posted([None, (T, 499, 0)], F, t1)))
    bad = bytearray(good)
    bad[4] = NENT + 1                                                       # a count past BZD_NENT
    out.append(("count", bytes(bad), fresh, {F: (t1, 0)}))
    bad = bytearray(good)
    bad[4] = 0                                                              # no courses
    out.append(("count0", bytes(bad), fresh, {F: (t1, 0)}))
    bad = bytearray(good)
    bad[6] = 1                                                              # +6 - +7 not zero
    out.append(("hdr67", bytes(bad), fresh, {F: (t1, 0)}))
    bad = bytearray(good)
    struct.pack_into("<HHH", bad, 8 + 6 * (NENT - 1), 0, 77, 3)             # the LAST entry EMPTY (key 0) with
    out.append(("entlast", bytes(bad), fresh, {F: (t1, 0)}))                # a best: refused whole
    # the entries are in NO ORDER (137.22.5.1): TCUP's at entry 20, TQUIK's at 5 - both kept where they are,
    # and TQUIK's next best files into its own entry
    scat = [None] * 5 + [(F, t1 + 99, 2)] + [None] * 14 + [(T, 499, 0)]
    out.append(("order", dat_image(scat), dat_image(scat), posted(scat, F, t1)))
    # a DUPLICATE key: the first entry holding it is kept, the second dropped (though its best is better)
    dup = [(T, 499, 0), (F, t1 + 99, 2), (F, 50, 0)]
    out.append(("dupkey", dat_image(dup), dat_image(dup[:2]), posted(dup[:2], F, t1)))
    # no older layout is read (137.22.5.1): `BZT1`, `BZS3` and `BZS4` are unrecognised - the first run's image
    out.append(("old1", dat_image({F: (t1 + 99, 2), T: (499, 0)}, old=64), fresh, {F: (t1, 0)}))
    out.append(("old3", dat_image({F: (t1 + 99, 2), T: (499, 0)}, old=304), fresh, {F: (t1, 0)}))
    out.append(("old4", dat_image({F: (t1 + 99, 2), T: (499, 0)}, old=494), fresh, {F: (t1, 0)}))
    # SPEC.md 137.55: BZS5 before THE LIVES GIVEN (488 bytes) IS read, its table zero; a slot at BZ_LVMAX's 9
    # lives kept with its dword, one at 10 emptied with its dword
    out.append(("bzs5old", dat_image({F: (t1 + 99, 2), T: (499, 0)}, slots=slot(3) + bytes(2 * SLOTB),
                                     given=(5, 6, 7), old=DAT_FILE0),
                dat_image({F: (t1 + 99, 2), T: (499, 0)}, slots=slot(3) + bytes(2 * SLOTB)),
                posted({F: (t1 + 99, 2), T: (499, 0)}, F, t1)))
    out.append(("lvmax", dat_image({T: (499, 0)}, slots=slot(BB_LVMAX) + slot(BB_LVMAX + 1) + bytes(SLOTB),
                                   given=(1 << 6, 0xFF, 0)),
                dat_image({T: (499, 0)}, slots=slot(BB_LVMAX) + bytes(2 * SLOTB), given=(1 << 6, 0, 0)),
                posted({T: (499, 0)}, F, t1)))
    # ...and a SLOT judged alone: one of another pathway VERSION emptied, one of this pathway's kept
    np_ = npad()
    keep = slot(3, 1, 1, 0b11, 0b1, 0b101, 0b001, exits={1: 1, 2: 3}, best={1: 300})
    other = slot(4, ver=path_ver() + 1)
    taken = slot(2, ropn=1, rtak=3)                       # a route TAKEN that was never opened
    out.append(("slot", dat_image({T: (499, 0)}, slots=keep + other + taken),
                dat_image({T: (499, 0)}, slots=keep + bytes(2 * SLOTB)), posted({T: (499, 0)}, F, t1)))
    # another pathway VERSION empties a slot whatever its lives: a finished game's exits found and bests too
    fin = slot(0, exits={0: 1}, best={0: 9})
    out.append(("pathver", dat_image({T: (499, 0)}, slots=slot(0, ver=path_ver() + 1, exits={0: 1}, best={0: 9}) +
                                     fin + bytes(SLOTB)),
                dat_image({T: (499, 0)}, slots=bytes(SLOTB) + fin + bytes(SLOTB)), posted({T: (499, 0)}, F, t1)))
    # the pad: not open / past 31; pad 0 shut; +3, the last best word and a pad's exits past the pads
    out.append(("pad", dat_image({T: (499, 0)}, slots=slot(3, pad=1) + slot(3, pad=32, open_=0xFFFFFFFF) +
                                  slot(3, open_=2)),
                dat_image({T: (499, 0)}), posted({T: (499, 0)}, F, t1)))
    out.append(("zero3", dat_image({T: (499, 0)}, slots=slot(3, z3=1) + slot(3, best={PAD_MAX - 1: 1}) +
                                    slot(3, exits={np_: 1})),
                dat_image({T: (499, 0)}), posted({T: (499, 0)}, F, t1)))
    # BZS5 (137.22.5.1): the exits found and the best of a pad past the pathway's pads - pad NPAD and
    # PAD_MAX - 1 (the last word) - each EMPTIES its slot alone; the words of the pads that exist are kept
    w3 = slot(3, exits={1: 1, np_ - 1: 1}, best={1: 300, np_ - 1: 450})
    out.append(("wide", dat_image({T: (499, 0)}, slots=slot(3, exits={PAD_MAX - 1: 0x8000}) +
                                   slot(3, best={np_: 7}) + w3),
                dat_image({T: (499, 0)}, slots=bytes(2 * SLOTB) + w3), posted({T: (499, 0)}, F, t1)))
    # each pad's exits found MASKED to the exits of the course on it (137.22.5.1: the course on a pad can
    # change under its progress) - every bit set on every pad, in a kept slot and an empty one
    vx = pad_exits()
    allx = {p_: 0xFFFF for p_ in range(np_)}
    out.append(("exitbits", dat_image({T: (499, 0)}, slots=slot(3, exits=allx) + slot(0, exits=allx) +
                                       bytes(SLOTB)),
                dat_image({T: (499, 0)}, slots=slot(3, exits=dict(enumerate(vx))) +
                          slot(0, exits=dict(enumerate(vx))) + bytes(SLOTB)), posted({T: (499, 0)}, F, t1)))
    # EXPLORE rests on any pad of the pathway's, none of them in the open set (137.19.8): KEPT (the verify of
    # 8R.5: the reader emptied it, and with it the slot's exits found and bests); a pad past the pathway's
    # emptied whatever its open bit says, in either mode
    xkeep = slot(3, mode=1, pad=np_ - 1, exits={1: 1}, best={1: 300})
    out.append(("explore", dat_image({T: (499, 0)}, slots=xkeep + slot(3, pad=np_, open_=0xFFFFFFFF) +
                                      slot(3, mode=1, pad=np_)),
                dat_image({T: (499, 0)}, slots=xkeep + bytes(2 * SLOTB)), posted({T: (499, 0)}, F, t1)))
    return out


def npad():
    """the pads a slot's +2 may name (bonanza.asm BZD_NPAD): bzcourse.inc's BZ_PATH_NPAD (137.22.3)"""
    return _equ("BZ_PATH_NPAD")


# ---- the guest's side -----------------------------------------------------------
def boot(tag, img):
    return os88ui.boot(R.at("build/os8088-360.img"), apps=img, machine=R.MACHINE[tag])


def open_game(ui, tag, sym):
    ui.open_drive("B")
    ui.open("BONANZA.O88")
    g = R.Bz(ui, tag, sym, live=True)       # launches claim and drop: the region may move
    ui.settle()
    g.m.pause()
    g.putb("bz_apilot", 1)                  # every play from here is the autopilot's
    g.m.run()
    return g


def guard(g):
    """the held-key guard: the next press of a guarded key needs the last one up"""
    M.until(g.m, lambda _: g.b("bz_dkk") == 0, "the held-key guard to see the last key come up", guest=5)


def motor_off(g):
    """a save is written and finished once the floppy motors have stopped (SPEC.md 18.9.1)"""
    M.guest_sleep(g.m, 0.5)
    M.until(g.m, lambda mm: mm.read(0x43F, 1)[0] & 0x0F == 0, "the floppy motors to stop", guest=15.0)


def bracket(g, what, guest=120):
    """a launch's whole life: the bracket up, down, its parts dropped, the
    title back; -> (floppy reads to the bracket, guest seconds to it)"""
    m = g.m
    c0 = R.cycles(m)
    M.until(m, lambda _: g.b("bz_fs") == 1, "%s: the bracket to come up" % what, guest=60)
    up = (R.cycles(m) - c0) / 4772727.0
    reads = m.disk()["reads"]
    M.until(m, lambda _: g.b("bz_fs") == 0, "%s: the bracket to end" % what, guest=guest)
    M.until(m, lambda _: g.w("bz_cseg") == 0 and g.w("bz_bseg") == 0, "%s: its parts dropped" % what, guest=30)
    if "bzs_desk" in g.sym:
        M.until(m, lambda _: g.b("bzs_desk") == 1 or g.b("bzs_mode") == 3, "%s: the title back" % what, guest=30)
    motor_off(g)
    return reads, up


def read_dat(g, path=DAT):
    """BONANZA.DAT (or PATH) as the FLOPPY holds it (os88flush, the host's reader), None when absent"""
    try:
        return os88flush.Flush(marty=g.m).volume(1).read(path)
    except os88flush.FlushError:
        return None


# ---- THE RELOAD (phase 3): a case is the reader called again, not a boot -------------------------------
HOSTILE_FILE = "BZH%02d.DAT"            # the hostile set's files, in SYSTEM\APPDATA beside BONANZA.DAT
PHYS_FILE = "BZP%d.DAT"                 # the physics-identity set's
EMPTY_FILE = "BZNONE.DAT"               # an empty image: noapp's bests start from none
NOAPP_DIR = "APPDATZ"                   # noapp's folder name: one the disk has not (od_s_appdat's 7 letters)
REGS = ("ax", "bx", "cx", "dx", "si", "di", "bp", "sp", "ss", "ds", "es", "flags")
OD_SYMS = ("od_s_appdat", "od_gen")     # os88data.inc's (no bz_ prefix: bonanza_ring.symbols() has none)
_OD = {}


def symbols(src=None):
    """bonanza_ring.symbols() (a fresh dict) and OD_SYMS, os88data.inc's labels the noapp leg pokes - found
    the same way, a `dw` table assembled on the package's end, once a process a tree"""
    import subprocess
    sym = R.symbols(src)
    d = os.path.abspath(src or os.path.join(ROOT, "apps", "bonanza"))
    if d not in _OD:
        art = os.path.abspath(R.at("build/bonanza-art"))
        apps = os.path.join(os.path.dirname(d), "") if os.path.exists(
            os.path.join(os.path.dirname(d), "os88api.inc")) else os.path.join(ROOT, "apps") + "/"
        with tempfile.TemporaryDirectory() as td:
            pa, pb = os.path.join(td, "probe.asm"), os.path.join(td, "probe.bin")
            open(pa, "w").write(open(os.path.join(d, "bonanza.asm")).read() + "\n" +
                                "\n".join("dw " + n for n in OD_SYMS) + "\n")
            subprocess.run(R.NASM + ["-f", "bin", "-I", apps, "-I", d + "/", "-I", art + "/", "-o", pb, pa],
                           cwd=ROOT, check=True, capture_output=True)
            raw = open(pb, "rb").read()
        _OD[d] = dict(zip(OD_SYMS, struct.unpack("<%dH" % len(OD_SYMS), raw[-2 * len(OD_SYMS):])))
    sym.update(_OD[d])
    return sym


def dat_files(td):
    """every file the reload legs read, written into TD under its 8.3 name -> os88disk.py operands
    (SYSTEM\\APPDATA)"""
    out = []
    files = [(HOSTILE_FILE % i, raw) for i, (_n, raw, _w, _x) in enumerate(hostile_set())]
    files += [(PHYS_FILE % i, raw) for i, (_n, raw, _w, _x) in enumerate(physdat_set()[0])]
    files.append((EMPTY_FILE, dat_image()))
    d = os.path.join(td, "appdata")
    os.makedirs(d, exist_ok=True)
    for nm, raw in files:
        pth = os.path.join(d, nm)
        open(pth, "wb").write(raw)
        out.append("SYSTEM/APPDATA:" + pth)
    return out


def dat_reload(g, name):
    """RELOAD: [bz_s_dat] poked to NAME (a file in SYSTEM\\APPDATA), [bz_datst] cleared (the next save a full
    write, as a session's first), and bz_dload - the entry proc's reader - CALLED in the window's task: the
    guest stopped at T's handler (bz_tkey, a key callback: CS = DS = the package, interrupts on, the UI
    task, where L and W do their file work), a near return to it pushed, run back to it, every register
    and CS:IP put back, and T's own work (a toggle of [bz_ctl]) undone.  -> None; raises if the call never
    came back"""
    m = g.m
    guard(g)
    m.pause()
    assert len(name) <= 11, "reload %s: longer than 'BONANZA.DAT' (bz_s_dat's 12 bytes)" % name
    ctl = g.b("bz_ctl")
    m.write(g.a("bz_s_dat"), name.encode("ascii") + b"\0")
    g.putb("bz_datst", 0)
    tk = g.a("bz_tkey")
    m.bp_exec(tk)
    m.run()
    m.key("KeyT", up=False)
    st = m.wait_stop(30)
    assert st == "breakpoint", "reload %s: T never reached bz_tkey (state %r)" % (name, st)
    saved = m.regs()
    assert ((saved["cs"] << 4) + saved["ip"]) & 0xFFFFF == tk, "reload %s: stopped off bz_tkey" % name
    sp = (saved["sp"] - 2) & 0xFFFF
    slot = (saved["ss"] << 4) + sp
    old = bytes(m.read(slot, 2))
    m.write(slot, struct.pack("<H", saved["ip"]))      # bz_dload's near RET comes back to bz_tkey's entry
    m.cmd(cmd="park", cs=saved["cs"], ip=saved["ip"] - g.sym["bz_tkey"] + g.sym["bz_dload"])
    for r in REGS:
        m.setreg(r, saved[r])
    m.setreg("sp", sp)
    m.run()
    st = m.wait_stop(60)
    back = m.regs()
    ok = (st == "breakpoint" and back["cs"] == saved["cs"] and back["ip"] == saved["ip"]
          and back["sp"] == saved["sp"])
    m.write(slot, old)
    m.cmd(cmd="park", cs=saved["cs"], ip=saved["ip"])
    for r in REGS:
        m.setreg(r, saved[r])
    m.bp_exec()
    m.run()
    m.key("KeyT", down=False)
    assert ok, "reload %s: bz_dload never returned to bz_tkey (state %r, at %04X:%04X sp %04X)" % (
        name, st, back["cs"], back["ip"], back["sp"])
    guard(g)
    m.pause()
    g.putb("bz_ctl", ctl)                       # (T's toggle undone: KEYS as it was)
    m.run()


def select(g, k):
    """course K for F's free play: [bz_crsel] POKED (no course key since 2026-11-19, SPEC.md 137.11.5.4)"""
    g.m.pause()
    g.putb("bz_crsel", k)
    g.m.run()


def free_play(g, k, what):
    """a free play of course K with its own ball (F: Enter is the game since wave 8b), the autopilot's -> bracket()"""
    select(g, k)
    g.m.disk(reset=True)
    g.key("KeyF")
    return bracket(g, what)


def logs_equal(g, keys, k, mat):
    want = R.make_log(keys, k, mat)
    got = g.read_log(len(want))
    return bytes(got) == want, want, bytes(got)


# ---- the legs -----------------------------------------------------------------
def demo_log(k):
    """course K's log MADE FROM THE MODEL: the autopilot's play to its goal (or cup), its own ball, stamped
    with the course's identity (bonanza_ring.make_log) - never a shipped demo"""
    return R.make_log(auto_keys(k), k, R.course_k(k).ball)


def leg_posts(g):
    """V of ROLL's and HOP's shipped demos, R and D of a TQUIK log, D of a TCUP log to its cup: no post"""
    fails = []
    m = g.m
    art = R.at("build/bonanza-art")

    def absent(what):
        d = read_dat(g)
        if d is not None:
            fails.append("posts: after %s BONANZA.DAT is ON the floppy (%d bytes): only a play with the course's "
                         "own ball posts a best (SPEC.md 137.14.3.3)" % (what, len(d)))
        if g.b("bz_newb"):
            fails.append("posts: after %s [bz_newb] is 1" % what)
    if read_dat(g) is not None:
        fails.append("posts: the leg's disk holds a BONANZA.DAT before any play")
    dks = R.demo_ks(art)                        # (V's cycle: the demo rows' order)
    for name in ("roll", "hop"):                # the SHIPPED courses' shipped demos
        kd = R.CRS_K[name]
        demo = open(os.path.join(ROOT, art, R.demo_name(kd)), "rb").read()
        m.pause()
        g.putb("bz_vk", dks.index(kd))          # (the row V loads next)
        m.run()
        guard(g)
        g.key("KeyV")
        M.until(m, lambda _: bytes(g.read_log(len(demo))) == demo,
                "V to put %s's shipped demo (%s) in the log" % (name.upper(), R.demo_name(kd)), guest=20)
        absent("V of %s's demo" % name.upper())
    q, c = first(), second()
    m.pause()
    g.write_log(demo_log(q))
    m.run()
    guard(g)
    g.key("KeyR")
    bracket(g, "R of TQUIK's log")
    if not g.b("bz_goal"):
        fails.append("posts: R of TQUIK's log (the model's play) did not reach its goal")
    absent("R of TQUIK's log to its goal")
    guard(g)
    g.key("KeyD")
    bracket(g, "D of TQUIK's log")
    absent("D of TQUIK's log to its goal")
    m.pause()
    g.write_log(demo_log(c))
    m.run()
    guard(g)
    g.key("KeyD")
    bracket(g, "D of TCUP's log", guest=60)
    if not (g.b("bz_goal") and g.b("bz_hid")):
        fails.append("posts: D of TCUP's log did not hole out (bz_goal %d bz_hid %d)" % (
            g.b("bz_goal"), g.b("bz_hid")))
    absent("D of TCUP's log to its cup")
    print("%s posts: V, R, D and D to a cup left BONANZA.DAT absent: %s" % (g.tag, "yes" if not fails else "NO"),
          flush=True)
    return fails


def leg_pause(g):
    """P in mid-play: no step while paused, the log unchanged; the time the model's"""
    fails = []
    m = g.m
    k = first()
    mat = R.course_k(k).ball
    t1, _ = auto_steps(k)
    select(g, k)
    g.key("KeyF")
    M.until(m, lambda _: g.b("bz_fs") == 1 and g.d("bz_nstep") >= 40, "TQUIK's play 40 steps in", guest=30)
    g.key("KeyP")
    M.guest_sleep(m, 0.3)
    m.pause()
    n1, log1 = g.d("bz_nstep"), bytes(g.read_log())
    m.run()
    M.guest_sleep(m, 1.0)
    m.pause()
    n2, log2 = g.d("bz_nstep"), bytes(g.read_log())
    m.run()
    if n1 != n2 or n1 >= t1:
        fails.append("pause: P pressed at step >= 40: the steps %d then %d a guest second later (the goal at %d): "
                     "a pause runs no step (SPEC.md 137.14.4.7)" % (n1, n2, t1))
    if log1 != log2:
        fails.append("pause: the log changed while paused")
    g.key("KeyP")
    bracket(g, "TQUIK's paused play")
    n = g.d("bz_nstep")
    eq, want, got = logs_equal(g, auto_keys(k), k, mat)
    if not g.b("bz_goal") or n != t1:
        fails.append("pause: the play ended at step %d (goal %d), the model's goal step is %d: the pause added "
                     "steps" % (n, g.b("bz_goal"), t1))
    if not eq:
        fails.append("pause: the play's log is not the model's (%d bytes against %d): the pause recorded "
                     "something" % (len(got), len(want)))
    d = read_dat(g)
    exp = dat_image({k: (t1, 0)})
    if d != exp:
        fails.append("pause: BONANZA.DAT after TQUIK's best is %s, not the expected %s" % (
            d.hex() if d else None, exp.hex()))
    print("%s pause: paused at step %d for a guest second, the play to its goal at %d (the model's %d), the log "
          "the model's, BONANZA.DAT TQUIK's best: %s" % (g.tag, n1, n, t1, "yes" if not fails else "NO"), flush=True)
    return fails


def leg_hostile(g, cases=None):
    """a RELOAD a hostile file (dat_reload): bz_dat as the checks say, then the file rewritten whole"""
    fails = []
    for i, (name, raw, want, nxt) in enumerate(hostile_set()):
        if cases and name not in cases:
            continue
        fn = HOSTILE_FILE % i
        dat_reload(g, fn)
        got = bytes(g.m.read(g.a("bz_dat"), DAT_FILE))
        if got != want:
            fails.append("hostile %s: [bz_dat] after the reader %s, SPEC.md 137.14.3.3's %s" % (
                name, got.hex(), want.hex()))
        free_play(g, first(), "hostile %s: TQUIK" % name)
        d = read_dat(g, "SYSTEM/APPDATA/" + fn)
        exp = dat_image(nxt, slots=want[SLOT_OFF:LIFE_OFF],        # (the slots as the reader kept them,
                        given=struct.unpack_from("<3I", want, LIFE_OFF))  # and their lives given, 137.55)
        if d != exp:
            fails.append("hostile %s: the next best did not rewrite the file whole: %s, want %s" % (
                name, d.hex() if d else "ABSENT", exp.hex()))
        print("%s hostile %s (%s, %d bytes): bz_dat as the checks say and the file rewritten whole: %s" % (
            g.tag, name, fn, len(raw), "yes" if not [f for f in fails if (" %s:" % name) in f] else "NO"),
            flush=True)
    return fails


def leg_noapp(g):
    """no SYSTEM\\APPDATA (od_s_appdat poked to a folder the disk has not): one toast over two bests"""
    fails = []
    m, ui = g.m, g.ui
    dat_reload(g, EMPTY_FILE)                   # (neither course holds a best: both plays below post one)
    m.pause()
    old = bytes(m.read(g.a("od_s_appdat"), 8))
    assert old == b"APPDATA\0", "od_s_appdat is %r, not APPDATA" % old
    m.write(g.a("od_s_appdat"), NOAPP_DIR.encode("ascii") + b"\0")
    g.putb("od_gen", 0)                         # (the bank dropped: every visit WALKS, and finds no folder)
    m.run()
    with M.bp_trace(m, "toast_show", log=True) as tr:     # (the kernel's: fixed, where the
                                                            # package's region may move in a launch)
        free_play(g, first(), "noapp TQUIK")
        n1 = tr.count()
        txt = ui.toast()[0]
        free_play(g, second(), "noapp TCUP")
        n2 = tr.count() - n1
    if n1 != 1 or "Best times not saved" not in txt or g.b("bz_datw") != 1:
        fails.append("noapp: the first best's failed save toasted %d time(s), the toast %r, bz_datw %d: want "
                     "`Best times not saved` once" % (n1, txt, g.b("bz_datw")))
    if n2:
        fails.append("noapp: the second best's failed save toasted again (%d): once a session" % n2)
    vol = os88flush.Flush(marty=m).volume(1)
    if NOAPP_DIR in [e.name for e in vol.listdir("SYSTEM")]:
        fails.append("noapp: a folder SYSTEM\\%s appeared: od_write made the folder it could not find" % NOAPP_DIR)
    if read_dat(g, "SYSTEM/APPDATA/" + EMPTY_FILE) != dat_image():
        fails.append("noapp: SYSTEM\\APPDATA\\%s changed: a save with no folder wrote through the bank" % EMPTY_FILE)
    m.pause()
    m.write(g.a("od_s_appdat"), old)            # (put back, the bank dropped again)
    g.putb("od_gen", 0)
    m.run()
    print("%s noapp: `Best times not saved` once over two bests: %s" % (g.tag, "yes" if not fails else "NO"),
          flush=True)
    return fails


def physdat_set():
    """[(name, the file's bytes, the bz_dat image the reader must make, the
    best the next TQUIK play files)] - SPEC.md 137.16.9's three cases: each file
    carries THIS build's course identities and a best on every course, and
    differs only at +5"""
    F = first()
    t1, _ = auto_steps(F)
    best = {k: (t1 + 50 + k, 1) for k in sorted(dict.values(R.CRS_K))}  # every best SLOWER than TQUIK's play
    pv = physv()
    out = []
    for name, v in (("unset", 0x00), ("5b", PHYSV_5B), ("w6", PHYSV_6)):
        out.append((name, dat_image(best, pv=v), dat_image(), {F: (t1, 0)}))
    out.append(("same", dat_image(best, pv=pv), dat_image(best),
                {k: ((t1, 0) if k == F else v) for k, v in best.items()}))
    assert pv not in (0x00, PHYSV_5B, PHYSV_6), "BZ_PHYSV %02Xh is an earlier physics' value (bbcourse refuses " \
        "it)" % pv
    return out, best


def leg_physdat(g):
    """a RELOAD a BONANZA.DAT under other physics (+5 00h, A0h, 25h) and one under this build's: the bests
    cleared, then rewritten whole; or kept"""
    fails = []
    cases, best = physdat_set()
    for i, (name, raw, want, nxt) in enumerate(cases):
        fn = PHYS_FILE % i
        dat_reload(g, fn)
        got = bytes(g.m.read(g.a("bz_dat"), DAT_FILE))
        if got != want:
            kt = {v: k for k, v in keys().items()}
            kept = [kt.get(struct.unpack_from("<H", got, 8 + 6 * i_)[0]) for i_ in range(NENT)
                    if struct.unpack_from("<H", got, 8 + 6 * i_ + 2)[0]]
            fails.append("physdat %s: [bz_dat] after the reader %s, want %s (+5 %02Xh, this build's "
                         "BZ_PHYSV %02Xh: %s; a best kept on course(s) %s)" % (
                             name, got.hex(), want.hex(), raw[5], physv(),
                             "every best CLEARED" if raw[5] != physv() else "every best KEPT",
                             kept or "none"))
        free_play(g, first(), "physdat %s: TQUIK" % name)
        d = read_dat(g, "SYSTEM/APPDATA/" + fn)
        exp = dat_image(nxt)
        if d != exp:
            fails.append("physdat %s: the next best did not rewrite the file whole with +5 = BZ_PHYSV: %s, "
                         "want %s" % (name, d.hex() if d else "ABSENT", exp.hex()))
        print("%s physdat %s (%s, +5 %02Xh, BZ_PHYSV %02Xh): bz_dat %s and the file rewritten whole: %s" % (
            g.tag, name, fn, raw[5], physv(), "cleared" if want == dat_image() else "kept",
            "yes" if not [f for f in fails if ("physdat %s:" % name) in f] else "NO"), flush=True)
    return fails


def run(tag, legs=LEGS, src=None, appdata=True, o88=None):
    """ONE BOOT of card TAG, the disk the row's own (O88's package, every reload's file in SYSTEM\\APPDATA,
    or no folder at all), every leg in LEGS in that boot -> failures"""
    sym = symbols(src)
    fails = []
    with tempfile.TemporaryDirectory() as td:
        img = R.disk(td, dat_files(td) if appdata else [], appdata=appdata, name="game", o88=o88)
        with boot(tag, img) as ui:
            g = open_game(ui, tag, sym)
            for leg, fn in (("posts", leg_posts), ("pause", leg_pause), ("hostile", leg_hostile),
                            ("physdat", leg_physdat), ("noapp", leg_noapp)):
                if leg in legs and not fails:
                    fails += fn(g)
    return fails


REDS = {
    # the length check removed: a short file's bytes are checked as a whole one
    "datlen": [("bonanza.asm", "    cmp ax, BZD_FILE            ; BZS5 (137.22.5.1): exactly BZD_FILE bytes; any\n"
                "    je .len                     ; other length (an older layout too) is unrecognised\n",
                "    jmp short .len              ; RED datlen: no length check\n")],
    # a replay posts a best
    "replaybest": [("bonanza.asm", "    cmp byte [bz_mode], 0       ; a replay posts nothing\n    jne .out\n",
                    "    nop                         ; RED replaybest: a replay posts\n")],
    "noappdata": [],
    # wave 8R (137.22.5, the verify of 8R.5): EXPLORE's pad held to the open set - the explore slot emptied
    "explorepad": [("bonanza.asm", "    test byte [si + 1], 1       ; ...and, TIMED, an open one (EXPLORE plays\n"
                    "    jnz .n                      ; any pad, 137.19.8: none of them in the set)\n",
                    "    nop                         ; RED explorepad: EXPLORE's pad must be open\n")],
    # BZS5 (137.22.5.1): the bests of pads past the pathway's not held to zero - the slot keeps a best for
    # a pad that does not exist
    "pastbest": [("bonanza.asm", "    lea di, [si + BZD_SBEST]\n    add di, ax\n"
                  "    call bz_dzero\n    jnz .bad\n",
                  "    nop                         ; RED pastbest: the bests past the pads unchecked\n")],
    # BZS5: a second entry with a key kept - the dupkey file's second TQUIK entry survives
    "dupkey": [("bonanza.asm", "    cmp si, di                  ; ...is this one: kept\n    je .keep\n",
                "    jmp short .keep             ; RED dupkey: every entry with a key of ours kept\n")],
    # BZS5: the exits found not masked to the pad's course's - the exitbits file's bits survive
    "exitmask": [("bonanza.asm", "    mov ax, [di]\n    and [si + BZD_SEXIT], ax\n",
                  "    mov ax, [di]                ; RED exitmask: no mask\n")],
    # BZS5: a slot of another pathway VERSION kept
    "pathver": [("bonanza.asm", "    cmp word [si + BZD_SVER], BZ_PATH_VER ; this build's pathway VERSION (an\n"
                 "    jne .bad                    ; all-zero slot's emptying changes nothing)\n",
                 "    nop                         ; RED pathver: the version not checked\n")],
    # wave 6 (SPEC.md 137.16.14): +5 not checked - a file under other physics keeps its bests
    "physdat": [("bonanza.asm", "    cmp byte [bz_dat + 5], BZ_PHYSV ; physics or not (a game is no time)\n    je .phys\n"
                 "    xor cl, cl\n.phys:\n",
                 "    nop                         ; RED physdat: +5 not checked\n.phys:\n")],
}
RED_LEGS = {"datlen": ("hostile",), "replaybest": ("posts",),
            "noappdata": ("pause",), "physdat": ("physdat",), "explorepad": ("hostile",),
            "pastbest": ("hostile",), "dupkey": ("hostile",), "exitmask": ("hostile",),
            "pathver": ("hostile",)}
RED_WANT = {"datlen": "hostile short", "replaybest": "posts: after R",
            "noappdata": "pause: BONANZA.DAT", "physdat": "every best CLEARED",
            "explorepad": "hostile explore", "pastbest": "hostile wide", "dupkey": "hostile dupkey",
            "exitmask": "hostile exitbits", "pathver": "hostile pathver"}


def check():
    """the host half: the model's plays, the hostile set decided, the reds assembled"""
    bad = []
    for k, why in ((first(), "every best, the pause and the posts' R and D are TQUIK's"),
                   (second(), "the posts' cup and noapp's second best are TCUP's")):
        t1, f1 = auto_steps(k)
        print("bonanza_game %s: the autopilot's play %s steps, %d falls" % (R.crs_name(k), t1, f1))
        if t1 is None:
            bad.append("%s: the model's autopilot does not finish (%s)" % (R.crs_name(k), why))
    if auto_steps(first())[0] is not None and auto_steps(first())[0] <= 40:
        bad.append("TQUIK's play is over by step 40: the pause leg presses P there")
    sym = symbols()                             # THE RELOAD's labels (dat_reload, leg_noapp)
    miss = [n for n in ("bz_s_dat", "bz_datst", "bz_dload", "bz_tkey", "bz_ctl", "bz_dat", "od_s_appdat",
                        "od_gen") if n not in sym]
    if miss:
        bad.append("the reload's labels %s are not in the package's symbols" % miss)
    names = [HOSTILE_FILE % i for i in range(len(hostile_set()))] + \
        [PHYS_FILE % i for i in range(len(physdat_set()[0]))] + [EMPTY_FILE]
    if len(set(names)) != len(names) or max(len(n) for n in names) > 11 or len(NOAPP_DIR) != 7:
        bad.append("the reload's file names %s: one longer than BONANZA.DAT, or a duplicate" % names)
    print("bonanza_game the reload: %d files in SYSTEM\\APPDATA (%s ... %s), bz_dload called at bz_tkey; noapp's "
          "folder %s" % (len(names), names[0], names[-1], NOAPP_DIR))
    print("bonanza_game BZ_CRS_MAX %d, BZ_PAD_MAX %d: BZS5 %d bytes (the slots at +%d, %d each; under one "
          "sector)" % (crs_max(), _equ("BZ_PAD_MAX"), DAT_FILE, SLOT_OFF, SLOTB))
    if DAT_FILE >= 512 or DAT_FILE % 512 == 0:  # od_write's one-sector arm refuses a whole sector (os88data.inc)
        bad.append("BZS5 is %d bytes: not under one sector, so every save is a full replace" % DAT_FILE)
    if _equ("BZ_PAD_MAX") != PAD_MAX or npad() > PAD_MAX:
        bad.append("BZ_PAD_MAX %d is not the test's %d (or %d pads exceed it)" % (_equ("BZ_PAD_MAX"), PAD_MAX,
                                                                                 npad()))
    import binascii                             # the keys, re-derived with the standard library's CRC-CCITT
    for k, key in keys().items():               # (SPEC.md 137.22.5.1: CRC-16/CCITT of the NAME, then the
        c = R.course_k(k)                       # version byte)
        want = binascii.crc_hqx(c.name.encode("ascii") + bytes([c.version]), 0xFFFF)
        if key != want or not key:
            bad.append("course %s's save key %04Xh, CRC-16/CCITT of its name and version %d says %04Xh"
                       % (c.name, key, c.version, want))
    if len(set(keys().values())) != ncrs():
        bad.append("BZ_CRS_KEYS has %d keys for %d courses, or a duplicate" % (len(keys()), ncrs()))
    print("bonanza_game save keys: %s; the pathway version %d; the pads' exits %s" % (
        ", ".join("%s %04Xh" % (R.course_k(k).name, v) for k, v in keys().items()), path_ver(),
        " ".join("%X" % v for v in pad_exits())))
    if crs_max() != NENT or ncrs() > NENT:
        bad.append("BZ_CRS_MAX %d is not the test's NENT %d (or %d courses exceed it)" % (crs_max(), NENT, ncrs()))
    try:                                        # the tool REFUSES more than BZ_CRS_MAX courses (SPEC.md 137.22.5)
        BB.compile_all([os.path.join(ROOT, R.COURSES["tquik"])] * (BB.CRS_MAX + 1))
        bad.append("bbcourse built %d courses: BZ_CRS_MAX is %d" % (BB.CRS_MAX + 1, BB.CRS_MAX))
    except BB.CourseError as e:
        print("bonanza_game bbcourse refuses %d courses: %s" % (BB.CRS_MAX + 1, e))
    for name, raw, want, nxt in hostile_set():
        mod = model_load(raw)                   # the rules read a second time, in Python: the case's image
        if mod != want:                         # is the one SPEC.md 137.22.5.1 says
            bad.append("hostile %s: the case wants bz_dat %s, the Python reader makes %s" % (
                name, want.hex(), mod.hex()))
        print("bonanza_game hostile %-8s %3d bytes -> bz_dat %s (the Python reader %s); the next best files %s" % (
            name, len(raw), "the first run's" if want == dat_image() else "kept in part",
            "agrees" if mod == want else "DISAGREES", [e for e in entries(nxt) if e]))
    cases, _best = physdat_set()
    for name, raw, want, nxt in cases:
        if model_load(raw) != want:
            bad.append("physdat %s: the case's bz_dat is not the Python reader's" % name)
        print("bonanza_game physdat %-5s +5 %02Xh (BZ_PHYSV %02Xh) -> bz_dat %s; the next best files %s" % (
            name, raw[5], physv(), "the first run's (every best cleared)" if want == dat_image() else
            "the file's (every best kept)", sorted(nxt)))
    for line in R.check_reds({k: v for k, v in REDS.items() if v}, "bonanza_game"):
        print(line)
    for b in bad:
        print("FAIL %s" % b)
    assert not bad, "%d model failure(s)" % len(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=("cga", "herc", "both"), default="both")
    ap.add_argument("--leg", action="append", choices=LEGS)
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true", help="the host half only")
    a = ap.parse_args()
    R.dev()                             # the BZDEV=1 build (SPEC.md 137.26.6.1)
    if a.check:
        check()
        return
    tags = ("cga", "herc") if a.adapter == "both" else (a.adapter,)
    legs = tuple(a.leg) if a.leg else LEGS
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, o88 = None, None
            if a.red != "noappdata":            # (noappdata: the shipped package on a disk with no folder)
                src, _img = R.build_tree(td, REDS[a.red])
                o88 = os.path.join(td, "BONANZA.O88")
            for tag in tags:
                try:
                    bad = run(tag, RED_LEGS[a.red], src=src, appdata=a.red != "noappdata", o88=o88)
                except AssertionError as e:
                    bad = ["assertion: %s" % e]
                for b in bad:
                    print("  red %s %s: %s" % (a.red, tag, b))
                assert bad, "RED ARM %s on %s: the row stayed GREEN against a broken package" % (a.red, tag)
                assert any(RED_WANT[a.red] in b for b in bad), \
                    "RED ARM %s on %s went red, but not at its own check (%r): %s" % (a.red, tag, RED_WANT[a.red], bad)
                print("bonanza_game --red %s (%s): went red as it must" % (a.red, tag), flush=True)
        print("bonanza_game --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    allbad = []
    for tag in tags:
        bad = run(tag, legs)
        for b in bad:
            print("FAIL %s: %s" % (tag, b))
        allbad += bad
    assert not allbad, "%d game failure(s)" % len(allbad)
    print("bonanza_game (%s): PASS" % ", ".join(tags))


if __name__ == "__main__":
    main()
