#!/usr/bin/env python3
"""ADD TO THE GAME: a playable BONANZA.O88 with the author's courses, made with no assembler
(SPEC.md 137.58.17, 137.58.36).

    python3 tools/bbgame.py OUT.o88 [--disk OUT.img --size 360|720|1200|1440] [--pad0 NAME | --path PATH.bbc]
                            [COURSE.bbc ...]
    python3 tools/bbgame.py prebuild [DIR]       (in the tree, with nasm: the shipped pieces and their map)

ONE BUILD HOLDS UP TO BZ_CRS_MAX (23) COURSES (SPEC.md 137.58.36). Every per-course table of bzcourse.inc is
laid out at its full width - the list's rows, zero rows to BZ_CRS_MAX, the pathway's and the title's after -
the counts (the list's courses, its shipped demos, the map's pads) are three bytes of DATA (BZ_CRS_COUNTS),
and the part table has BZ_CRS_MAX course rows and BZ_CRS_MAX demo rows, those past the list's RESERVED
(BZRES.BIN, never fetched). So another list moves no label: it changes table BYTES and nothing else, and
the shipped build's own pieces are the pieces of every list.

`prebuild` (make bbgamebin) copies those pieces - bonanza.bin, bzshell.bin, bzvga.bin, bzfbun.bin and the
fetch families' bzf-<name>.bin - with the shipped bzcourse.inc and a MAP: where each per-course table's bytes
are, in which piece. The map is found by a PROBE: the pieces assembled again from an inc whose every table
byte is XOR its table's own mask, whose every course part row's flags are another allowed form, and whose
every INFO equ (one the list may change: the counts' own `equ`s, BZ_CRS_DEFAULT, the switches BZ_NCRS2 and
BZ_NSHC, the inc's unreferenced ones) is one more - and it holds that the bytes that moved are those tables
and those flag bytes and nothing else. One assembly; seconds, where the variants it replaced were minutes.

Composing: bbcourse.py compiles the shipped courses and the author's (the parts, the demos, the pathway, the
title - all Python), and its bzcourse.inc is held to the shipped one LINE BY LINE: outside the per-course
tables (PATCH), the course rows' flags, the INFO equs and the per-course `BZ_CRS_<NAME>` lines it must be the
same text, or the game is REFUSED, naming the line - a course with more lanes, props or state than the game
was assembled for, a bigger pathway picture. Where it is the same, the tables' bytes and the rows' flags are
written at the map's places, and the result is byte for byte what nasm would have made from that inc - so
with no added course and the shipped map the package IS build/bonanza.o88. os88pkg.py then packs it as the
Makefile does, and os88disk.py makes the floppy the bonanzadisk rule makes.

THE SHIPPED GAME HAS NO COURSE CYCLE (SPEC.md 137.26.8: N is BZDEV's): a course is played from its pathway
pad. --pad0 NAME puts course NAME on pad 0 - where a new game rests, so Play Game, Enter plays it - in place
of pad 0's course (the knob builds' precedent, BZSHAPES): NAME takes that course's K and the displaced course
moves to the end. --path PATH.bbc is the author's own pathway (the course builder's Map tab, SPEC.md
137.58.20), whose pads may play the added courses.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402

TREE = os.path.dirname(HERE)
BUNDLED = os.path.isdir(os.path.join(HERE, "bbgame-bin"))
BIN = os.path.join(HERE, "bbgame-bin") if BUNDLED else os.path.join(TREE, "build", "bbgame-bin")
# the tables a course owns a row (or a slot) of: db/dw lists, written into the prebuilt pieces at the map's
# places - and BZ_CRS_COUNTS, the three counts.  Every other line of bzcourse.inc must come out the same.
PATCH = ("BZ_CRS_COUNTS", "BZ_CRS_NAMES", "BZ_CRS_TITLES", "BZ_CRS_BALLS", "BZ_CRS_LIMS", "BZ_CRS_IDS",
         "BZ_CRS_KEYS", "BZ_CRS_NCKS", "BZ_CRS_SONGS", "BZ_CRS_MEDALS", "BZ_CRS_PALS", "BZ_CRS_BOTS",
         "BZ_CRS_STOPS", "BZ_CRS_SPANS", "BZ_CRS_LOCKS", "BZ_CRS_WPARA", "BZ_CRS_SHN", "BZ_CRS_SHI", "BZ_DEMO_CRS",
         "BZ_CRS_NEXITS", "BZ_CRS_ARENA", "BZ_PAD_EXITS")
ROWS = "BZ_CRS_PARTS"           # the course part rows: their FLAGS are written (OP_BIG), never their count
# the equs another list may change (the probe proves each moves no byte) - besides the inc's unreferenced ones
INFO = ("BZ_NCRS", "BZ_NDEMO", "BZ_PATH_NPAD", "BZ_CRS_DEFAULT", "BZ_NCRS2", "BZ_NSHC")
PIECES = ("bonanza.bin", "bzshell.bin", "bzvga.bin", "bzfbun.bin")   # + the fetch families' bzf-<name>.bin
OPF = {"OP_LAZY": 8, "OP_COMP": 16, "OP_ARENA": 64, "OP_BIG": 128}    # apps/os88parts.inc's row flags
# what a refusal means, for the lines a course most often moves
WHY = {
    "BZ_PROPMAX": "the course has more LANES (moving or drawn props) than the game holds",
    "BZ_PROPALL": "the course has more PROPS than the game holds",
    "BZ_NSIGN": "the course has more signs (labels) than the game holds",
    "BZ_FSTB": "the course's props keep more state than the game holds",
    "BZ_FORMS": "the course's part uses a stored form no shipped course uses",
    "BZ_KWMAX": "a grid row of the course has more cells than the game holds",
    "BZ_MROWS": "the course has more block rows than the game holds",
    "BZ_CRS_MAXCLAIM": "the course on a pad needs a bigger claim than the largest the game holds",
    "BZ_CRS_ARMAX": "the course on a pad needs a bigger arena reserve than the game holds",
    "BZ_SHMAX": "the course has more SHEETS than the game holds",
    "BZ_SHTAB": "the course is SHEETED, and the game's sheet table is the shipped courses'",
    "BZ_CRS_PARTS": "the course's part row needs a form no shipped course's has",
    "BZ_CRS_NAMEW": "the course's NAME is longer than the face holds",
    "BZ_PATH_CLAIM": "the pathway's picture is bigger than the shipped one's",
    "BZ_PATH_VER": "the pathway's `version` is not the shipped one's (a save slot's guard)",
}


class Refused(Exception):
    pass


# ---- bzcourse.inc, read ---------------------------------------------------------------------------------
def _strip(ln):
    """a line without its comment (a ';' outside quotes) and its trailing space"""
    q = None
    for i, ch in enumerate(ln):
        if q:
            if ch == q:
                q = None
        elif ch in "'\"`":
            q = ch
        elif ch == ";":
            return ln[:i].rstrip()
    return ln.rstrip()


def _items(rest):
    out, cur, q = [], "", None
    for ch in rest:
        if q:
            cur += ch
            if ch == q:
                q = None
        elif ch in "'\"":
            q = ch
            cur += ch
        elif ch == ",":
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _num(t):
    t = t.strip()
    neg = t.startswith("-")
    t = t.lstrip("-+")
    if t.lower().endswith("h"):
        v = int(t[:-1], 16)
    elif t.lower().startswith("0x"):
        v = int(t[2:], 16)
    else:
        v = int(t)
    return -v if neg else v


def encode(body, mask=0):
    """the bytes nasm emits for a table macro's body (db/dw lines of numbers and quoted strings), each byte
    XOR MASK; a body of anything else raises ValueError"""
    out = bytearray()
    for ln in body:
        op, _, rest = ln.strip().partition(" ")
        if op not in ("db", "dw"):
            raise ValueError("not a db/dw line: %r" % ln)
        for it in _items(rest):
            if it[:1] in "'\"":
                if op != "db" or len(it) < 2 or it[-1] != it[0]:
                    raise ValueError("a string in %r" % ln)
                bs = it[1:-1].encode("ascii")
            elif op == "db":
                bs = bytes((_num(it) & 255,))
            else:
                bs = struct.pack("<H", _num(it) & 0xFFFF)
            out += bs
    return bytes(b ^ mask for b in out)


def _probe_body(body, mask):
    """a body whose every byte is the original's XOR MASK, written as db/dw numbers"""
    out = []
    for ln in body:
        op, _, rest = ln.strip().partition(" ")
        vals = []
        for it in _items(rest):
            if it[:1] in "'\"":
                vals += ["%d" % (b ^ mask) for b in it[1:-1].encode("ascii")]
            elif op == "db":
                vals.append("%d" % ((_num(it) & 255) ^ mask))
            else:
                vals.append("%d" % ((_num(it) & 0xFFFF) ^ (mask * 0x101)))
        out.append("    %s %s" % (op, ", ".join(vals)))
    return out


def row_flags(body):
    """the course part rows' FLAGS, a byte a row, out of BZ_CRS_PARTS' body (its %rep form expanded)"""
    out, rep = [], None
    for ln in body:
        t = ln.strip()
        m = re.match(r"^%rep\s+(\w+)$", t)
        if m:
            rep = B.CRS_MAX if m.group(1) == "BZ_CRS_MAX" else int(m.group(1))
            continue
        if t == "%endrep":
            continue
        m = re.match(r"^OS88_PART\s+OP_ASSET\s*,\s*(.+)$", t)
        if not m:
            raise ValueError("not a course part row: %r" % ln)
        f = 0
        for n in m.group(1).split("|"):
            if n.strip() not in OPF:
                raise ValueError("a row flag %r" % n)
            f |= OPF[n.strip()]
        out += [f] * (rep or 1)
    return out


def read_inc(text):
    """-> (lines, tables, crs): the inc's lines without comments or blanks, each a (kind, key, text) - a table
    macro's body collected under tables[name] and stood for by one ("table", name) line; each `BZ_CRS_<X> equ`
    line whose X is a course's NAME in crs[sym] = text and left out"""
    lines, tables, crs = [], {}, {}
    cur = None
    for raw in text.splitlines():
        ln = _strip(raw)
        if not ln.strip():
            continue
        m = re.match(r"^%macro\s+(\w+)", ln)
        if m and (m.group(1) in PATCH or m.group(1) == ROWS):
            cur = m.group(1)
            tables[cur] = []
            lines.append(("table", cur, ln))
            continue
        if cur is not None:
            if ln.strip() == "%endmacro":
                cur = None
            else:
                tables[cur].append(ln)
            continue
        m = re.match(r"^(BZ_CRS_[A-Z0-9]+)\s+equ\s+(\d+)\s*$", ln)
        if m and raw.split(";", 1)[1:] and ".bbc," in raw.split(";", 1)[1]:   # `BZ_CRS_<NAME> equ K ; <file>.bbc, ...`
            crs[m.group(1)] = int(m.group(2))
            continue
        m = re.match(r"^(\w+)\s+equ\b", ln)
        lines.append(("equ" if m else "line", m.group(1) if m else None, re.sub(r"\s+", " ", ln.strip())))
    return lines, tables, crs


def _equ_val(text):
    m = re.match(r"^\w+ equ (\S+)$", text)
    try:
        return _num(m.group(1)) if m else None
    except ValueError:
        return None


def compare(old, new, info=INFO, allowed=None):
    """hold the composed list's bzcourse.inc (NEW) to the shipped one (OLD): -> ({table: new bytes} for every
    table that differs, [the course part rows' flags] - None when they are OLD's); Refused naming the first
    other line that does.  INFO: the equs that may differ (the probe proved they move no byte) - but never
    between zero and not, which the probe did not try.  ALLOWED: the row flags the probe tried"""
    lo, to, co = read_inc(old)
    ln, tn, cn = read_inc(new)
    for a in ln:
        if a[0] == "equ" and a[1] == "BZ_PATH_NPAD" and (_equ_val(a[2]) or 0) > B.PATH_PAD_MAX:
            raise Refused("the pathway has %d pads: the game holds 1 - %d (BZ_PAD_MAX, a save slot's word-a-pad "
                          "tables)" % (_equ_val(a[2]), B.PATH_PAD_MAX))
    if len(lo) != len(ln):
        raise Refused("bzcourse.inc has %d lines where the shipped game's has %d" % (len(ln), len(lo)))
    for a, b in zip(lo, ln):
        if a == b:
            continue
        if a[0] == "equ" and b[0] == "equ" and a[1] == b[1] and a[1] in info:
            va, vb = _equ_val(a[2]), _equ_val(b[2])
            if va is not None and vb is not None and (va == 0) == (vb == 0):
                continue
        key = a[1] or b[1] or ""
        why = WHY.get(key, "")
        raise Refused("the game cannot take this course list without an assembler: the shipped game was "
                      "assembled with `%s`, this list needs `%s`%s" % (a[2], b[2], " - " + why if why else ""))
    for sym in cn:
        if sym in set(x[1] for x in ln if x[1]) or sym in tn:
            raise Refused("a course NAME makes %s, which is already one of the game's symbols: rename the course"
                          % sym)
    out = {}
    for t in PATCH:
        if (t in to) != (t in tn):
            raise Refused("the table %s is in one list's inc and not the other's" % t)
        if t not in to:
            continue
        eo, en = encode(to[t]), encode(tn[t])
        if len(eo) != len(en):
            raise Refused("the table %s is %d bytes where the shipped game's is %d" % (t, len(en), len(eo)))
        if eo != en:
            out[t] = en
    fo, fn = row_flags(to[ROWS]), row_flags(tn[ROWS])
    if len(fo) != len(fn):
        raise Refused("%d course part rows where the shipped game has %d" % (len(fn), len(fo)))
    ok = set(fo) | set(allowed or ())
    bad = [k for k, f in enumerate(fn) if f not in ok]
    if bad:
        raise Refused("course %d's part row is %02Xh, a form no shipped course's row has (%s) - %s"
                      % (bad[0], fn[bad[0]], ", ".join("%02Xh" % f for f in sorted(ok)), WHY[ROWS]))
    return out, (fn if fn != fo else None)


# ---- the course compile ---------------------------------------------------------------------------------
def compile_into(art, paths, path, title):
    """bbcourse.py -o ART's files (write_out's: the stamp, the parts, bzcourse.inc, bzdemo.lst, bzparts.lst),
    compiled THROUGH the compile cache: the build's compile_all compiles fresh and only writes it, which for the
    shipped list is minutes; the cache's key names every input (SPEC.md 137.58.8), and the shipped list
    composed this way is held to the build's own package byte for byte (tests/unit/t_bbgame.py) -> the inc's
    text"""
    tests = [n for n, _t, tst in B._course_info(paths) if tst]
    if tests:
        raise Refused("%s: a TEST course (`test`) never ships - take the statement out" % ", ".join(tests))
    if len(paths) > B.CRS_MAX:
        raise Refused("%d courses: the game holds %d (BZ_CRS_MAX, the save's one sector)" % (len(paths), B.CRS_MAX))
    try:
        courses, files, texts = B._compile_all(paths, path=path, title=title)
    except B.CourseError as e:
        raise Refused("the course compiler refused the list: %s" % e)
    os.makedirs(art, exist_ok=True)
    with open(os.path.join(art, ".bz-crs"), "w") as f:
        f.write(B.stamp(paths + [path, title, B.KIT_FILE]) + "\n")
    for name in sorted(files):
        with open(os.path.join(art, name), "wb") as f:
            f.write(files[name])
    for name in sorted(texts):
        with open(os.path.join(art, name), "w", newline="\n") as f:
            f.write(texts[name])
    return texts["bzcourse.inc"]


# ---- the prebuilt pieces (the tree, with nasm) -------------------------------------------------------------
def _run(cmd, cwd=TREE, env=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if r.returncode:
        sys.exit("bbgame: %s failed:\n%s%s" % (" ".join(cmd[:3]), r.stdout[-3000:], r.stderr[-3000:]))
    return r.stdout


def _pieces():
    return list(PIECES) + ["bzf-%s.bin" % f["name"] for f in B.FAM_FETCH]


def shipped_paths():
    """the shipped courses, BZ_COURSES's first line (the Makefile's, or the bundle's data/Makefile)"""
    lst = B._mk_list(B._makefile(), "BZ_COURSES")
    if not lst:
        raise Refused("no BZ_COURSES line in %s" % os.path.join(B.ROOT, "Makefile"))
    return [os.path.join(B.ROOT, p) for p in lst]


def _srcs():
    """every piece bonanza.asm links, and its source"""
    srcs = {"bonanza.bin": "apps/bonanza/bonanza.asm", "bzshell.bin": "apps/bonanza/bzshell.asm",
            "bzvga.bin": "apps/bonanza/bzvga.asm"}
    for f in B.FAM_FETCH + B.FAM_RES:
        srcs["bzf-%s.bin" % f["name"]] = "apps/bonanza/fam/%s.asm" % f["name"]
    return srcs


def _assemble(art, inc_text, tmp):
    """every piece of _srcs() assembled with ART's includes and INC_TEXT as its bzcourse.inc, in a directory of
    its own under TMP -> {piece: bytes}: bonanza.bin first, and bzlink.inc (the constants and bss the linked
    parts assemble against, SPEC.md 106.20) made again from it, as the Makefile makes it"""
    pa = os.path.join(tempfile.mkdtemp(dir=tmp), "art")
    shutil.copytree(art, pa, ignore=shutil.ignore_patterns("*.png"))
    with open(os.path.join(pa, "bzcourse.inc"), "w") as f:
        f.write(inc_text)
    inc = ["-I", "apps/", "-I", "apps/bonanza/", "-I", pa + "/"]
    out = {}
    srcs = _srcs()
    for piece in ["bonanza.bin"] + sorted(set(srcs) - {"bonanza.bin"}):
        o = os.path.join(pa, piece)
        _run(["nasm", "-f", "bin", "-w+error"] + inc + ["-o", o, srcs[piece]])
        with open(o, "rb") as f:
            out[piece] = f.read()
        if piece == "bonanza.bin":
            _run([sys.executable, os.path.join(HERE, "pxlink.py"), o, "--src", "apps/bonanza/bonanza.asm"] + inc
                 + ["--prefix", "BZL", "--consts", "BZ", "-o", os.path.join(pa, "bzlink.inc")])
    return out


def _rowbase(img):
    """the first course part row's offset in bonanza.bin: the part table's (os88pkg's reader) + its 10-byte
    head (apps/os88parts.inc OP_T_ROWS; BZ_P_CRS is 0)"""
    import os88pkg
    at, _g = os88pkg.part_table(img)
    if at is None:
        sys.exit("bbgame: no part table in bonanza.bin")
    return at + 10


def probe_map(build, art, inc_text, pieces, info):
    """assemble bonanza.asm and the linked parts again with every PATCH table's bytes XOR its own mask, every
    course part row's flags another form the shipped rows use (OP_BIG toggled) and every INFO equ one more,
    and -> ({table: [[piece, offset], ...]}, [the row flags the probe tried]); exits unless the bytes that moved
    are exactly those tables and those flag bytes"""
    lines = inc_text.splitlines()
    probe, cur, masks, body = [], None, {}, []
    _, tables, _ = read_inc(inc_text)
    flags = row_flags(tables[ROWS])
    forms = sorted(set(flags))
    alt = [f ^ OPF["OP_BIG"] if (f ^ OPF["OP_BIG"]) in forms else f for f in flags]
    for raw in lines:
        ln = _strip(raw)
        m = re.match(r"^%macro\s+(\w+)", ln)
        if m and (m.group(1) in PATCH or m.group(1) == ROWS):
            cur, body = m.group(1), []
            if cur in PATCH:
                masks[cur] = 0x80 + len(masks)
            probe.append(raw)
            continue
        if cur is not None:
            if ln.strip() == "%endmacro":
                if cur == ROWS:
                    probe += ["    OS88_PART OP_ASSET, %d" % f for f in alt]
                else:
                    probe += _probe_body(body, masks[cur])
                probe.append(raw)
                cur = None
            elif ln.strip():
                body.append(ln)
            continue
        m = re.match(r"^(\w+)(\s+equ\s+)(\S+)(.*)$", raw)
        if m and m.group(1) in info and _equ_val("%s equ %s" % (m.group(1), m.group(3))) is not None:
            v = _equ_val("%s equ %s" % (m.group(1), m.group(3)))
            probe.append("%s%s%d%s" % (m.group(1), m.group(2), v + 1 if v else 0, m.group(4)))
            continue
        probe.append(raw)
    with tempfile.TemporaryDirectory() as t:
        got = _assemble(art, "\n".join(probe) + "\n", t)
        out = {}
        for piece in sorted(got):
            a = open(os.path.join(build, piece), "rb").read()
            b = got[piece]
            if len(a) != len(b):
                sys.exit("bbgame: the probe moved %s's size (%d -> %d): a table, a row or an INFO equ feeds an "
                         "assembly-time expression" % (piece, len(a), len(b)))
            diff = set(i for i in range(len(a)) if a[i] != b[i])
            seen = set()
            if piece == "bonanza.bin":
                r0 = _rowbase(a)
                seen |= set(r0 + 8 * k + 1 for k, (f, g) in enumerate(zip(flags, alt)) if f != g)
            for tname, tb in tables.items():
                if tname == ROWS:
                    continue
                e = encode(tb)
                p = encode(tb, masks[tname])
                i = a.find(e)
                while i >= 0:
                    if b[i:i + len(e)] == p:
                        if seen & set(range(i, i + len(e))):
                            sys.exit("bbgame: %s overlaps another table in %s" % (tname, piece))
                        seen |= set(range(i, i + len(e)))
                        out.setdefault(tname, []).append([piece, i])
                    i = a.find(e, i + 1)
            if diff != seen:
                sys.exit("bbgame: %d bytes of %s moved with the tables that are not a table's (first at %d): "
                         "a table, a row or an INFO equ feeds code" % (len(diff ^ seen), piece,
                                                                       min(diff ^ seen)))
            if diff and piece not in pieces:
                sys.exit("bbgame: %s holds a table but is not a piece the package carries" % piece)
    for tname in tables:
        if tname not in out and tname != ROWS:
            out[tname] = []                     # a table no piece expands (TITLES, SONGS): it moves nothing
    if not out.get("BZ_CRS_COUNTS"):
        sys.exit("bbgame: the probe found no BZ_CRS_COUNTS in the pieces: the counts are not data")
    return out, forms


def _inert(inc_text):
    """the inc's equ symbols nothing assembled names (no source under apps/bonanza/, no apps/*.inc, no other
    inc line): a change to one moves no byte"""
    words = set()
    for base, _, names in os.walk(os.path.join(TREE, "apps")):
        if base != os.path.join(TREE, "apps") and not base.startswith(os.path.join(TREE, "apps", "bonanza")):
            continue
        for n in names:
            if n.endswith((".asm", ".inc")):
                words |= set(re.findall(r"\w+", open(os.path.join(base, n), encoding="latin-1").read()))
    syms = re.findall(r"^(\w+)\s+equ\b", inc_text, re.M)
    rest = re.findall(r"\w+", "\n".join(_strip(ln) for ln in inc_text.splitlines()))
    return sorted(s for s in set(syms) if s not in words and rest.count(s) == 1)


def prebuild(out, top="build"):
    """the shipped build's pieces (the tree's TOP, build/) -> OUT: the pieces, bzcourse.inc, map.json, README.md"""
    build = os.path.join(TREE, top)
    art = os.path.join(build, "bonanza-art")
    pieces = _pieces()
    for p in pieces + ["bonanza.o88"]:
        if not os.path.isfile(os.path.join(build, p)):
            sys.exit("bbgame: no %s in %s (make bonanza)" % (p, build))
    inc = open(os.path.join(art, "bzcourse.inc")).read()
    info = sorted(set(INFO) | set(_inert(inc)))
    tabmap, forms = probe_map(build, art, inc, pieces, info)
    if os.path.isdir(out):
        shutil.rmtree(out)                      # (an older prebuild's variants v0 .. v4 with it)
    os.makedirs(out)
    for p in pieces:
        shutil.copyfile(os.path.join(build, p), os.path.join(out, p))
    shutil.copyfile(os.path.join(art, "bzcourse.inc"), os.path.join(out, "bzcourse.inc"))
    shutil.copyfile(os.path.join(TREE, "apps", "bonanza", "README.md"), os.path.join(out, "README.md"))
    mp = {"courses": B._mk_list(B._makefile(), "BZ_COURSES"), "map": tabmap, "info": info, "forms": forms,
          "o88": hashlib.sha1(open(os.path.join(build, "bonanza.o88"), "rb").read()).hexdigest()}
    with open(os.path.join(out, "map.json"), "w") as f:
        json.dump(mp, f, indent=1, sort_keys=True)
        f.write("\n")
    print("bbgame: %s - %s, %d tables placed, %d INFO equs, row forms %s" % (
        out, ", ".join("%s %d" % (p, os.path.getsize(os.path.join(out, p))) for p in pieces[:3]),
        sum(map(len, tabmap.values())), len(info), " ".join("%02Xh" % f for f in forms)))
    return 0


# ---- composing (anywhere: the tree or the zip) -------------------------------------------------------------
def _course_name(path):
    with open(path, encoding="ascii", errors="replace") as f:
        for ln in f:
            m = re.match(r"^\s*course\s+(\S+)", ln)
            if m:
                return m.group(1)
    raise Refused("%s has no `course` line" % path)


def _pathway(work, pad0, displaced):
    """THE PATHWAY's source: the shipped one, or with --pad0 a copy whose pad 0 names PAD0"""
    src = os.path.join(B.COURSE_DIR, "path.bbc")
    if not pad0:
        return src
    txt = open(src, encoding="ascii").read()
    new, n = re.subn(r"^(pad\s+0\s+)%s(\s)" % re.escape(displaced), lambda m: m.group(1) + pad0.ljust(
        len(displaced)) + m.group(2), txt, count=1, flags=re.M)
    if n != 1:
        raise Refused("the pathway's pad 0 line does not name %s" % displaced)
    p = os.path.join(work, "path.bbc")
    with open(p, "w", encoding="ascii") as f:
        f.write(new)
    return p


def compose(out, authors, pad0=None, disk=None, size=1440, work=None, log=print, pathway=None, _skip=()):
    """-> 0 after writing OUT (and DISK); Refused with the reason. PATHWAY: a pathway of the author's (the course
    builder's Map tab, SPEC.md 137.58.20) in place of the shipped one - its pads may play the added courses, and
    with no courses given they are the ones its `# builder-course:` lines name.  _SKIP: tables NOT written
    (tests/unit/t_bbgame.py's red arm)"""
    if pathway:
        if pad0:
            raise Refused("--path and --pad0 together: put the course on pad 0 in the pathway itself")
        pathway = os.path.abspath(pathway)
        if not authors:
            import bbedmap
            authors = bbedmap.extra_courses(open(pathway, encoding="ascii").read(), pathway)
    authors = [os.path.abspath(a) for a in authors]
    ship = shipped_paths()
    sn = [_course_name(p) for p in ship]        # SPEC.md 137.58.17: an author's course NAMED as a shipped one
    replaces = {}                               # REPLACES it, in its own slot and on its own pad
    for a_ in list(authors):
        n_ = _course_name(a_)
        if n_ in sn and n_ not in replaces:
            replaces[n_] = a_
            authors.remove(a_)
    if len(ship) + len(authors) > B.CRS_MAX:
        raise Refused("at most %d added courses (BZ_CRS_MAX %d less the %d shipped); %d given"
                      % (B.CRS_MAX - len(ship), B.CRS_MAX, len(ship), len(authors)))
    if not os.path.isfile(os.path.join(BIN, "map.json")):
        raise Refused("no prebuilt game in %s (in the tree: make bbgamebin)" % BIN)
    mp = json.load(open(os.path.join(BIN, "map.json")))
    names = [_course_name(p) for p in ship]
    if [os.path.basename(p) for p in ship] != [os.path.basename(p) for p in mp["courses"]]:
        raise Refused("the shipped course list (%s) is not the one the prebuilt game was made with (%s)"
                      % (" ".join(map(os.path.basename, ship)), " ".join(map(os.path.basename, mp["courses"]))))
    anames = [_course_name(p) for p in authors]
    for a in anames:
        if a in names or anames.count(a) > 1:
            raise Refused("two courses are named %s: a course's NAME is its key, give yours another" % a)
    courses = [replaces.get(n_, p_) for n_, p_ in zip(names, ship)] + authors
    for n_ in replaces:
        pm = re.search(r"^pad\s+(\d+)\s+%s\b" % re.escape(n_), open(os.path.join(B.COURSE_DIR, "path.bbc")).read(),
                       re.M)
        log("bbgame: your %s replaces the shipped %s%s" % (os.path.basename(replaces[n_]), n_,
                                                           (" on its own pad (pad %s)" % pm.group(1)) if pm else ""))
    if pad0 in replaces:                        # (it is already on the pathway, on its own pad)
        pad0 = None
    displaced = None
    if pad0:
        if pad0 not in anames:
            raise Refused("--pad0 %s: not one of the added courses (%s)" % (pad0, ", ".join(anames) or "none"))
        pad = re.search(r"^pad\s+0\s+(\S+)", open(os.path.join(B.COURSE_DIR, "path.bbc")).read(), re.M)
        displaced = pad.group(1)
        k0 = names.index(displaced)
        ka = len(ship) + anames.index(pad0)
        courses[k0], courses[ka] = courses[ka], courses[k0]
        courses.append(courses.pop(ka))         # (the displaced course LAST: the others keep their K)
    own = work is None
    work = work or tempfile.mkdtemp(prefix="bbgame-")
    os.makedirs(work, exist_ok=True)
    try:
        art = os.path.join(work, "art")
        path = pathway or _pathway(work, pad0, displaced)
        log("bbgame: compiling %d courses (%s)" % (len(courses), " ".join(_course_name(c) for c in courses)))
        inc = compile_into(art, courses, path, os.path.join(B.COURSE_DIR, "title.bbc"))
        patches, rows = compare(open(os.path.join(BIN, "bzcourse.inc")).read(), inc, mp["info"], mp["forms"])
        bins = os.path.join(work, "bin")
        os.makedirs(bins, exist_ok=True)
        for p in _pieces():
            shutil.copyfile(os.path.join(BIN, p), os.path.join(bins, p))
        writes = [(piece, off, data) for t, data in sorted(patches.items()) if t not in _skip
                  for piece, off in mp["map"][t]]
        if rows is not None:                    # the course part rows' flags (OP_BIG: a world part or sheets)
            fp = os.path.join(bins, "bonanza.bin")
            r0 = _rowbase(open(fp, "rb").read())
            writes += [("bonanza.bin", r0 + 8 * k + 1, bytes((f,))) for k, f in enumerate(rows)]
        for piece, off, data in writes:
            fp = os.path.join(bins, piece)
            b = bytearray(open(fp, "rb").read())
            b[off:off + len(data)] = data
            open(fp, "wb").write(bytes(b))
        log("bbgame: %d tables written (%s)%s" % (len(patches), " ".join(sorted(patches)) or "none",
                                                  ", the course rows' flags" if rows is not None else ""))
        rowfiles = [os.path.join(art, ln.strip()) for ln in open(os.path.join(art, "bzparts.lst")) if ln.strip()]
        tail = [os.path.join(art, n) for n in ("BZPATH.BIN", "BZTITLE.BIN", "BZTDEMO.BIN", "BZKIT.BIN")]
        fams = [os.path.join(bins, os.path.basename(p)) for p in B.fam_partfiles(bins)]
        cmd = [sys.executable, os.path.join(HERE, "os88pkg.py"), os.path.join(bins, "bonanza.bin"), "-o", out,
               "--compress-if=lz4"]
        for p in rowfiles + [os.path.join(bins, "bzshell.bin")] + tail + fams + [os.path.join(bins, "bzvga.bin")]:
            cmd += ["--part", p]
        cmd += ["--part-compress", "lzb"]
        for p in sorted(set(rowfiles)) + tail:
            cmd += ["--part-data", p]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise Refused("os88pkg refused the package:\n" + (r.stderr or r.stdout).strip()[-2000:])
        log("bbgame: %s - %d bytes, %d courses%s" % (out, os.path.getsize(out), len(courses),
                                                      ", %s on pad 0" % pad0 if pad0 else ""))
        if disk:
            rd = os.path.join(work, "README.md")
            src = os.path.join(BIN, "README.md")
            subprocess.run([sys.executable, os.path.join(HERE, "os88lz.py"), "--wrap", rd, "--fmt", "lz4", src],
                           check=True, capture_output=True)
            pk = os.path.join(work, "BONANZA.O88")
            shutil.copyfile(out, pk)
            for c in ([sys.executable, os.path.join(HERE, "os88disk.py"), "-o", disk, "--size", str(size), pk, rd,
                       "--folder", "SYSTEM/APPDATA"],
                      [sys.executable, os.path.join(HERE, "os88disk.py"), "--verify", disk]):
                r = subprocess.run(c, capture_output=True, text=True)
                if r.returncode:
                    raise Refused("os88disk refused the floppy:\n" + (r.stderr or r.stdout).strip()[-2000:])
            log("bbgame: %s - a %d KB floppy" % (disk, size))
        return 0
    finally:
        if own:
            shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["prebuild"]:
        ap = argparse.ArgumentParser(prog="bbgame.py prebuild")
        ap.add_argument("out", nargs="?", default=BIN)
        ap.add_argument("--build", default="build", help="the tree's build directory (make's BUILD)")
        a = ap.parse_args(argv[1:])
        return prebuild(a.out, a.build)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", help="the package to write, BONANZA.O88")
    ap.add_argument("courses", nargs="*", help="the courses to add after the shipped ones (BZ_CRS_MAX in all)")
    ap.add_argument("--disk", metavar="IMG", help="also a floppy: the package, its README and SYSTEM/APPDATA")
    ap.add_argument("--size", type=int, default=1440, choices=(360, 720, 1200, 1440))
    ap.add_argument("--pad0", metavar="NAME", help="put added course NAME on the pathway's pad 0")
    ap.add_argument("--no-trap", action="store_true", help="skip NO TRAP, the softlock search (SPEC.md 137.58.24): "
                    "the course builder asks the author whether to run it")
    ap.add_argument("--path", metavar="PATH.bbc", help="the author's pathway in place of the shipped one (its pads "
                    "may play the added courses; with no courses given, its `# builder-course:` lines name them)")
    ap.add_argument("--work", metavar="DIR", help="keep the compile's files here")
    a = ap.parse_args(argv)
    if a.no_trap:
        B.TRAP_CHECK = False
    try:
        return compose(a.out, a.courses, a.pad0, a.disk, a.size, a.work, pathway=a.path)
    except Refused as e:
        print("bbgame: REFUSED: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
