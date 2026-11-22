#!/usr/bin/env python3
"""ADD TO THE GAME: a playable BONANZA.O88 with the author's courses, made with no assembler
(SPEC.md 130.58.17, the course builder's wave 8).

    python3 tools/bbgame.py OUT.o88 [--disk OUT.img --size 360|720|1200|1440] [--pad0 NAME | --path PATH.bbc]
                            [COURSE.bbc ...]
    python3 tools/bbgame.py prebuild [DIR]       (in the tree, with nasm: the prebuilt pieces)

The game's course list is ASSEMBLED in (bzcourse.inc, SPEC.md 130.10.6), and a course
changes more than a table: its count moves every label after the tables. So the pieces
nasm makes are made where nasm is - `prebuild`, run by `make bbgamebin` and shipped in the
course builder's zip as bbgame-bin/ - once for the shipped list (v0, the shipped package's
own pieces) and once for each count of added courses, 0 to SPARE_MAX (v0r, v<m>: the shipped
list and m SPARE courses, `make BUILD=... BZHEADROOM=1 BZ_COURSES=...`, the twoseg build's way;
SPEC.md 130.58.17.1: HEADROOM raises two capacities, signs and the pads' exits table, so an
author's pathway may have more pads and signs than the shipped map). Each variant
carries its bzcourse.inc and a MAP: where, in which piece, each per-course table's bytes are
(found by assembling a PROBE whose every table byte differs, a mask a table, and holding
that the bytes that moved are those tables and nothing else).

Composing: bbcourse.py compiles the shipped courses and the author's (the parts, the
demos, the pathway, the title - all Python), and its bzcourse.inc is held to the variant's
LINE BY LINE: outside the per-course tables (PATCH) and the per-course `BZ_CRS_<NAME>` and
unreferenced lines it must be the same text, or the game is REFUSED, naming the line - a
course with more lanes, props, signs or state than the game was assembled for, a course past
one part. Where it is the same, the tables' bytes are written at the map's places, and the
result is byte for byte what nasm would have made from that inc - so with no added course
and the shipped map the package IS build/bonanza.o88. The pad count (BZ_PATH_NPAD) is the save
file's guard, not a capacity, so a headroom variant carries its bytes at EVERY count 1 -
BZ_PAD_MAX (a probe assembly a count) and the composition writes the map's. os88pkg.py then
packs it as the Makefile does, and os88disk.py makes the floppy the bonanzadisk rule makes.

THE SHIPPED GAME HAS NO COURSE CYCLE (SPEC.md 130.26.8: N is BZDEV's): a course is played
from its pathway pad. --pad0 NAME puts course NAME on pad 0 - where a new game rests, so
Play Game, Enter plays it - in place of pad 0's course (the knob builds' precedent,
BZSHAPES): NAME takes that course's K and the displaced course moves to the end, so
BZ_CRS_DEFAULT stays what it was. Placing a course anywhere else on the map is the pathway
editor's wave.
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
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bbcourse as B  # noqa: E402

TREE = os.path.dirname(HERE)
BUNDLED = os.path.isdir(os.path.join(HERE, "bbgame-bin"))
BIN = os.path.join(HERE, "bbgame-bin") if BUNDLED else os.path.join(TREE, "build", "bbgame-bin")
SPARE_MAX = 4
# the tables a course owns a row (or a slot) of: db/dw lists, written into the prebuilt pieces at the map's
# places.  Every other line of bzcourse.inc must come out the same.
PATCH = ("BZ_CRS_NAMES", "BZ_CRS_TITLES", "BZ_CRS_BALLS", "BZ_CRS_LIMS", "BZ_CRS_IDS", "BZ_CRS_KEYS",
         "BZ_CRS_NCKS", "BZ_CRS_SONGS", "BZ_CRS_MEDALS", "BZ_CRS_PALS", "BZ_CRS_BOTS", "BZ_CRS_LOCKS",
         "BZ_CRS_WPARA", "BZ_CRS_SHN", "BZ_CRS_SHI", "BZ_DEMO_CRS", "BZ_CRS_NEXITS", "BZ_CRS_ARENA",
         "BZ_PAD_EXITS")
PIECES = ("bonanza.bin", "bzshell.bin", "bzvga.bin", "bzfbun.bin")   # + the fetch families' bzf-<name>.bin
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
    "BZ_NCRS2": "the course is past one part (a two-part course)",
    "BZ_NSHC": "the course is past one part (a SHEETED course)",
    "BZ_CRS_PARTS": "the course is past one part (its part row is OP_BIG)",
    "BZ_CRS_NAMEW": "the course's NAME is longer than every shipped course's",
    "BZ_NDEMO": "a TEST course (`test`) has no shipped demo, and the game's demo count is fixed",
    "BZ_CRS_DEFAULT": "pad 0's course moved",
}
SPARE = """course SPAR{n} "Spare {n}"
# SPEC.md 130.58.17: a SPARE course, the slot an added course takes in a prebuilt BONANZA (tools/bbgame.py).
# Never played and never shipped: bbgame writes the added course's rows over this one's.
music fairway
width 64
ball rubber
floor rect 3 4 11 8 flat 4
goal rect 10 4 11 8 flat 4
start 4 5
way 4 5
way 10 5
target 30
limit 30
clock 8 7
"""


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
        if m and m.group(1) in PATCH:
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


def compare(old, new, inert=(), npads=()):
    """hold the composed list's bzcourse.inc (NEW) to the variant's (OLD): -> ({table: new bytes} for every
    table that differs, the pad count when BZ_PATH_NPAD differs and is one of NPADS - a headroom variant's,
    SPEC.md 130.58.17.1 - else None); Refused naming the first other line that does"""
    lo, to, co = read_inc(old)
    ln, tn, cn = read_inc(new)
    if len(lo) != len(ln):
        raise Refused("bzcourse.inc has %d lines where the prebuilt game's has %d" % (len(ln), len(lo)))
    npad = None
    for a, b in zip(lo, ln):
        if a == b:
            continue
        if a[0] == "equ" and b[0] == "equ" and a[1] == b[1] and a[1] in inert:
            continue
        if a[0] == "equ" and b[0] == "equ" and a[1] == b[1] == "BZ_PATH_NPAD":
            n = int(NPAD_RE.search(b[2]).group(2))
            if n in npads:
                npad = n
                continue
            raise Refused("the pathway has %d pads: the game holds 1 - %d (BZ_PAD_MAX, a save slot's word-a-pad "
                          "tables)%s" % (n, B.PATH_PAD_MAX, "" if npads else " and this prebuilt game the "
                                         "shipped map's count alone"))
        key = a[1] or b[1] or ""
        if a[0] == "line" and b[0] == "line" and "OS88_PART" in a[2]:
            key = "BZ_CRS_PARTS"
        why = WHY.get(key, "")
        raise Refused("the game cannot take this course list without an assembler: the prebuilt game was "
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
            raise Refused("the table %s is %d bytes where the prebuilt game's is %d" % (t, len(en), len(eo)))
        if eo != en:
            out[t] = en
    return out, npad


# ---- the course compile ---------------------------------------------------------------------------------
def compile_into(art, paths, path, title, headroom=False):
    """bbcourse.py -o ART's files (write_out's: the stamp, the parts, bzcourse.inc, bzdemo.lst), compiled
    THROUGH the compile cache: the build's compile_all compiles fresh and only writes it, which for the
    shipped list is minutes (PLAY alone 181 s); the cache's key names every input (SPEC.md 130.58.8), and v0
    composed this way is held to the build's own package byte for byte (tests/unit/t_bbgame.py)"""
    tests = [n for n, _t, tst in B._course_info(paths) if tst]
    if tests:
        raise Refused("%s: a TEST course (`test`) never ships - take the statement out" % ", ".join(tests))
    held, B.HEADROOM = B.HEADROOM, headroom          # (bbcourse.py's --headroom, make's BZHEADROOM=1)
    try:
        courses, files, texts = B._compile_all(paths, path=path, title=title)
    except B.CourseError as e:
        raise Refused("the course compiler refused the list: %s" % e)
    finally:
        B.HEADROOM = held
    pc, tc = B.compile_all.path, B.compile_all.title
    os.makedirs(art, exist_ok=True)
    with open(os.path.join(art, ".bz-crs"), "w") as f:
        f.write(B.stamp(paths + [path, title, B.KIT_FILE]) + "\n")
    for name in sorted(files):
        with open(os.path.join(art, name), "wb") as f:
            f.write(files[name])
    for name in sorted(texts):
        with open(os.path.join(art, name), "w", newline="\n") as f:
            f.write(texts[name])

    def inc(room):
        """the list's bzcourse.inc with HEADROOM ROOM, written into ART -> its text"""
        held, B.HEADROOM = B.HEADROOM, room
        try:
            txt = B.emit_inc(courses, pc, tc)
        finally:
            B.HEADROOM = held
        with open(os.path.join(art, "bzcourse.inc"), "w", newline="\n") as f:
            f.write(txt)
        return txt
    return inc


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


NPAD_RE = re.compile(r"^(BZ_PATH_NPAD\s+equ\s+)(\d+)", re.M)


def npad_map(build, art, inc_text, pieces, taken):
    """SPEC.md 130.58.17.1: BZ_PATH_NPAD is not a capacity but the save file's guard (BZD_NPAD), so a headroom
    variant keeps the map's count and the composition writes the bytes it assembles into: the pieces assembled
    again at EVERY count 1 .. BZ_PAD_MAX -> {"base": n, "runs": [[piece, off, len], ...], "bytes": {count: [hex a
    run, ...]}}, the runs every byte that differs from the variant's own at any count - so a count's bytes
    written there ARE that count's assembly.  Exits unless every count assembles to the same sizes, no run
    touches a table's bytes (TAKEN: {piece: set of offsets}) and only the package's pieces move"""
    import concurrent.futures as cf
    base = int(NPAD_RE.search(inc_text).group(2))
    ref = {}
    for p in _srcs():
        with open(os.path.join(build, p), "rb") as f:
            ref[p] = f.read()
    counts = [n for n in range(1, B.PATH_PAD_MAX + 1) if n != base]

    def one(n, t):
        return _assemble(art, NPAD_RE.sub(lambda m: m.group(1) + str(n), inc_text, 1), t)
    with tempfile.TemporaryDirectory() as t:
        with cf.ThreadPoolExecutor(max(1, min(8, os.cpu_count() or 1))) as ex:
            got = dict(zip(counts, ex.map(lambda n: one(n, t), counts)))
    got[base] = ref
    diff = {}
    for n in sorted(got):
        for p, b in sorted(got[n].items()):
            if len(b) != len(ref[p]):
                sys.exit("bbgame: BZ_PATH_NPAD %d moves %s's size (%d -> %d): a count feeds a layout"
                         % (n, p, len(ref[p]), len(b)))
            d = set(i for i in range(len(b)) if b[i] != ref[p][i])
            if d and p not in pieces:
                sys.exit("bbgame: BZ_PATH_NPAD moves %s, which is not a piece the package carries" % p)
            if d & taken.get(p, set()):
                sys.exit("bbgame: BZ_PATH_NPAD %d moves a table's bytes in %s" % (n, p))
            diff.setdefault(p, set()).update(d)
    runs = []
    for p in sorted(diff):
        for i in sorted(diff[p]):
            if runs and runs[-1][0] == p and runs[-1][1] + runs[-1][2] == i:
                runs[-1][2] += 1
            else:
                runs.append([p, i, 1])
    return {"base": base, "runs": runs,
            "bytes": {str(n): [got[n][p][o:o + ln].hex() for p, o, ln in runs] for n in sorted(got)}}


def probe_map(build, art, inc_text, pieces):
    """assemble bonanza.asm and the linked parts again with every PATCH table's bytes XOR its own mask, and
    -> {table: [[piece, offset], ...]}; exits unless the bytes that moved are exactly those tables"""
    lines = inc_text.splitlines()
    probe, cur, masks = [], None, {}
    for raw in lines:
        ln = _strip(raw)
        m = re.match(r"^%macro\s+(\w+)", ln)
        if m and m.group(1) in PATCH:
            cur, body = m.group(1), []
            masks[cur] = 0x80 + len(masks)
            probe.append(raw)
            continue
        if cur is not None:
            if ln.strip() == "%endmacro":
                probe += _probe_body(body, masks[cur])
                probe.append(raw)
                cur = None
            elif ln.strip():
                body.append(ln)
            continue
        probe.append(raw)
    _, tables, _ = read_inc(inc_text)
    with tempfile.TemporaryDirectory() as t:
        got = _assemble(art, "\n".join(probe) + "\n", t)
        out = {}
        for piece in sorted(got):
            a = open(os.path.join(build, piece), "rb").read()
            b = got[piece]
            if len(a) != len(b):
                sys.exit("bbgame: the probe moved %s's size (%d -> %d): a table feeds an assembly-time "
                         "expression" % (piece, len(a), len(b)))
            diff = set(i for i in range(len(a)) if a[i] != b[i])
            seen = set()
            for tname, body in tables.items():
                e = encode(body)
                p = encode(body, masks[tname])
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
                         "a table feeds code" % (len(diff - seen), piece, min(diff - seen or seen)))
            if diff and piece not in pieces:
                sys.exit("bbgame: %s holds a table but is not a piece the package carries" % piece)
    for tname in tables:
        if tname not in out:
            out[tname] = []                     # a table no piece expands (SONGS, TITLES): it moves nothing
    return out


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


def variants():
    """-> [(name, spare courses, HEADROOM)]: v0 the shipped build's own pieces, v0r the shipped list with
    HEADROOM (SPEC.md 130.58.17.1: a pathway of the author's with no added course), v1 .. vSPARE_MAX with it"""
    return [("v0", 0, False), ("v0r", 0, True)] + [("v%d" % m, m, True) for m in range(1, SPARE_MAX + 1)]


def _prebuild_key(top):
    """what the prebuilt pieces are made from, by CONTENT (make's dates rebuild them for any edit to the
    compiler, which mostly leaves every shipped course's bytes as they were): the shipped package itself, the
    game's sources, this tool and the Makefile.  A compiler change that moves only a HEADROOM or spare build's
    bytes and none of the shipped package's is the one this cannot see - `make -B bbgamebin BBGAME_FORCE=1` forces it"""
    h = hashlib.sha1()
    files = [os.path.join(top, "bonanza.o88"), os.path.abspath(__file__), os.path.join(TREE, "Makefile")]
    for base, _, names in sorted(os.walk(os.path.join(TREE, "apps", "bonanza"))):
        files += [os.path.join(base, n) for n in sorted(names) if n.endswith((".asm", ".inc", ".bbc"))]
    for f in files:
        h.update(os.path.relpath(f, TREE).encode() + b"\0")
        with open(f, "rb") as fh:
            h.update(hashlib.sha1(fh.read()).digest())
    return h.hexdigest()


def prebuild(out, top="build", only=None, jobs=None, force=False):
    """the variants() - v0 the shipped list (the tree's TOP, build/), the rest the shipped list and m spare
    courses, each a private tree TOP/bbgame/<name>, made with BZHEADROOM=1 - -> OUT/<name>/: the pieces,
    bzcourse.inc, map.json.  The variants are independent trees, so they are made side by side (JOBS, one
    a core), each a `prebuild --only` process of its own; and none is made when _prebuild_key() says the
    pieces in OUT were made from these very inputs"""
    if only is None:
        topd = os.path.join(TREE, top)
        key = _prebuild_key(topd)
        kfile = os.path.join(out, "key.txt")
        have = all(os.path.exists(os.path.join(out, v, "map.json")) for v, _m, _r in variants())
        force = force or os.environ.get("BBGAME_FORCE", "") not in ("", "0")
        if not force and have and os.path.exists(kfile) and open(kfile).read().strip() == key:
            print("bbgame: the prebuilt pieces in %s were made from these inputs - nothing to do" % out)
            return 0
        if os.path.exists(kfile):
            os.remove(kfile)
        os.makedirs(out, exist_ok=True)
        jobs = max(1, min(len(variants()), jobs or 1))     # (one: npad_map already fills every core - 585 s
        #  serial against 592 s side by side, 2026-11-22)
        procs, fail = {}, []
        todo = [v for v, _m, _r in variants()]
        while todo or procs:
            while todo and len(procs) < jobs:
                v = todo.pop(0)
                procs[v] = subprocess.Popen([sys.executable, os.path.abspath(__file__), "prebuild", out,
                                             "--build", top, "--only", v], cwd=TREE, stdout=subprocess.PIPE,
                                            stderr=subprocess.STDOUT, text=True)
            for v, pr in list(procs.items()):
                if pr.poll() is not None:
                    text = pr.stdout.read()
                    sys.stdout.write(text)
                    if pr.returncode:
                        fail.append(v)
                    del procs[v]
            time.sleep(0.5)
        if fail:
            sys.exit("bbgame: prebuild failed for %s" % ", ".join(fail))
        shutil.copyfile(os.path.join(TREE, "apps", "bonanza", "README.md"), os.path.join(out, "README.md"))
        with open(kfile, "w") as f:
            f.write(key + "\n")
        return 0
    make = os.environ.get("MAKE", "make")
    top = os.path.join(TREE, top)
    ship = B._mk_list(B._makefile(), "BZ_COURSES")
    os.makedirs(out, exist_ok=True)
    for vname, m, room in variants():
        if vname != only:
            continue
        if not room:
            build = top
        else:
            build = os.path.join(top, "bbgame", vname)
            os.makedirs(build, exist_ok=True)
            spares = []
            for n in range(1, m + 1):
                p = os.path.join(build, "spar%d.bbc" % n)
                txt = SPARE.format(n=n)
                if not os.path.exists(p) or open(p).read() != txt:
                    with open(p, "w") as f:
                        f.write(txt)
                spares.append(os.path.relpath(p, TREE))
            art = os.path.join(build, "bonanza-art")      # (seeded through the cache; make takes it as made)
            compile_into(art, [os.path.join(TREE, p) for p in ship + spares],
                         os.path.join(B.COURSE_DIR, "path.bbc"), os.path.join(B.COURSE_DIR, "title.bbc"), True)
            _run([make, "--no-print-directory", "BUILD=%s" % os.path.relpath(build, TREE), "BZHEADROOM=1",
                  "BZ_COURSES=%s" % " ".join(ship + spares), "-o", os.path.relpath(art, TREE) + "/.bz-crs",
                  os.path.relpath(build, TREE) + "/bonanza.o88"])
        art = os.path.join(build, "bonanza-art")
        v = os.path.join(out, vname)
        os.makedirs(v, exist_ok=True)
        inc = open(os.path.join(art, "bzcourse.inc")).read()
        pieces = _pieces()
        for p in pieces:
            shutil.copyfile(os.path.join(build, p), os.path.join(v, p))
        shutil.copyfile(os.path.join(art, "bzcourse.inc"), os.path.join(v, "bzcourse.inc"))
        mp = {"courses": ship, "spares": m, "map": probe_map(build, art, inc, pieces), "inert": _inert(inc),
              "o88": hashlib.sha1(open(os.path.join(build, "bonanza.o88"), "rb").read()).hexdigest(),
              "headroom": room}
        if room:
            _, tables, _ = read_inc(inc)
            taken = {}
            for t, places in mp["map"].items():
                for piece, off in places:
                    taken.setdefault(piece, set()).update(range(off, off + len(encode(tables[t]))))
            mp["npad"] = npad_map(build, art, inc, pieces, taken)
        with open(os.path.join(v, "map.json"), "w") as f:
            json.dump(mp, f, indent=1, sort_keys=True)
            f.write("\n")
        print("bbgame: %s - %s, %d tables placed%s" % (
            vname, ", ".join("%s %d" % (p, os.path.getsize(os.path.join(v, p))) for p in pieces[:3]),
            sum(map(len, mp["map"].values())), ", BZ_PATH_NPAD's %d bytes at every count" % sum(
                r[2] for r in mp["npad"]["runs"]) if room else ""))
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


def compose(out, authors, pad0=None, disk=None, size=1440, work=None, log=print, pathway=None, _npad=None):
    """-> 0 after writing OUT (and DISK); Refused with the reason. PATHWAY: a pathway of the author's (the course
    builder's Map tab, SPEC.md 130.58.20) in place of the shipped one - its pads may play the added courses, and
    with no courses given they are the ones its `# builder-course:` lines name"""
    if pathway:
        if pad0:
            raise Refused("--path and --pad0 together: put the course on pad 0 in the pathway itself")
        pathway = os.path.abspath(pathway)
        if not authors:
            import bbedmap
            authors = bbedmap.extra_courses(open(pathway, encoding="ascii").read(), pathway)
    authors = [os.path.abspath(a) for a in authors]
    ship = shipped_paths()
    m = len(authors)
    if m > SPARE_MAX:
        raise Refused("at most %d added courses (the prebuilt game's spare slots); %d given" % (SPARE_MAX, m))
    # SPEC.md 130.58.17.1: with no added course v0 (the shipped build's own pieces) first, and v0r (HEADROOM) if
    # the list needs more pads or signs than the shipped map; an added course's variant has HEADROOM
    cands = [os.path.join(BIN, n) for n in (("v0", "v0r") if m == 0 else ("v%d" % m,))]
    if not os.path.isfile(os.path.join(cands[0], "map.json")):
        raise Refused("no prebuilt game in %s (in the tree: make bbgamebin)" % cands[0])
    cands = [c for c in cands if os.path.isfile(os.path.join(c, "map.json"))]
    mp = json.load(open(os.path.join(cands[0], "map.json")))
    names = [_course_name(p) for p in ship]
    if [os.path.basename(p) for p in ship] != [os.path.basename(p) for p in mp["courses"]]:
        raise Refused("the shipped course list (%s) is not the one the prebuilt game was made with (%s)"
                      % (" ".join(map(os.path.basename, ship)), " ".join(map(os.path.basename, mp["courses"]))))
    anames = [_course_name(p) for p in authors]
    for a in anames:
        if a in names or anames.count(a) > 1:
            raise Refused("two courses are named %s: a course's NAME is its key, give yours another" % a)
    courses = ship + authors
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
        inc = compile_into(art, courses, path, os.path.join(B.COURSE_DIR, "title.bbc"), mp.get("headroom", False))
        for i, v in enumerate(cands):
            mp = json.load(open(os.path.join(v, "map.json")))
            room = mp.get("headroom", False)
            try:
                patches, npad = compare(open(os.path.join(v, "bzcourse.inc")).read(), inc(room), mp["inert"],
                                        [int(n) for n in mp["npad"]["bytes"]] if room else ())
                break
            except Refused as e:
                if i + 1 == len(cands):
                    raise
                log("bbgame: not the shipped build's own pieces (%s) - the headroom build's" % e)
        bins = os.path.join(work, "bin")
        os.makedirs(bins, exist_ok=True)
        for p in _pieces():
            shutil.copyfile(os.path.join(v, p), os.path.join(bins, p))
        writes = [(piece, off, data) for t, data in sorted(patches.items()) for piece, off in mp["map"][t]]
        if room:                                # SPEC.md 130.58.17.1: the pad count's bytes, the save's guard
            n = npad if npad is not None else mp["npad"]["base"]
            n = _npad if _npad is not None else n        # (t_bbgame's red arm: another count's bytes)
            writes += [(piece, off, bytes.fromhex(h)) for (piece, off, _ln), h in
                       zip(mp["npad"]["runs"], mp["npad"]["bytes"][str(n)])]
        for piece, off, data in writes:
            fp = os.path.join(bins, piece)
            b = bytearray(open(fp, "rb").read())
            b[off:off + len(data)] = data
            open(fp, "wb").write(bytes(b))
        log("bbgame: %s, %d tables written (%s)%s" % (os.path.basename(v), len(patches), " ".join(sorted(patches))
                                                      or "none", ", %d pads" % npad if npad is not None else ""))
        demos = [os.path.join(art, ln.strip()) for ln in open(os.path.join(art, "bzdemo.lst")) if ln.strip()]
        crs = [os.path.join(art, "BZ%d.BIN" % k) for k in range(len(courses))]
        tail = [os.path.join(art, n) for n in ("BZPATH.BIN", "BZTITLE.BIN", "BZTDEMO.BIN", "BZKIT.BIN")]
        fams = [os.path.join(bins, os.path.basename(p)) for p in B.fam_partfiles(bins)]
        cmd = [sys.executable, os.path.join(HERE, "os88pkg.py"), os.path.join(bins, "bonanza.bin"), "-o", out,
               "--compress-if=lz4"]
        for p in crs + demos + [os.path.join(bins, "bzshell.bin")] + tail + fams + [os.path.join(bins, "bzvga.bin")]:
            cmd += ["--part", p]
        cmd += ["--part-compress", "lzb"]
        for p in crs + tail + demos:
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
        ap.add_argument("--only", help="make one variant (the parallel prebuild's worker)")
        ap.add_argument("-j", "--jobs", type=int, help="variants made at once (default 1: each already fills the cores)")
        ap.add_argument("--force", action="store_true", help="make them even when the inputs have not moved")
        a = ap.parse_args(argv[1:])
        return prebuild(a.out, a.build, a.only, a.jobs, a.force)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", help="the package to write, BONANZA.O88")
    ap.add_argument("courses", nargs="*", help="the courses to add after the shipped ones (at most %d)" % SPARE_MAX)
    ap.add_argument("--disk", metavar="IMG", help="also a floppy: the package, its README and SYSTEM/APPDATA")
    ap.add_argument("--size", type=int, default=1440, choices=(360, 720, 1200, 1440))
    ap.add_argument("--pad0", metavar="NAME", help="put added course NAME on the pathway's pad 0")
    ap.add_argument("--no-trap", action="store_true", help="skip NO TRAP, the softlock search (SPEC.md 130.58.24): "
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
