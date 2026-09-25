#!/usr/bin/env python3
"""os88vid - the host half of Video Player (docs/plans/VIDEO-PLAN.md).

    python3 tools/os88vid.py stat     FILE.XDV...
    python3 tools/os88vid.py verify   FILE.XDV...
    python3 tools/os88vid.py benchdat OUT.DAT FILE.XDV...

WAVE 0 IS WHAT THIS FILE IS FOR TODAY. It reads XDC streams (MobyGamer's
XDC, MIT, (c) 2014 Jim Leonard) exactly, re-expresses each frame in the
plan's operand format (four skip-coded lists of segments, section 2.2) and
writes the data file tests/vidbench/ measures. `encode` and the `.V88`
container come in wave 1; the functions here are the ones they will use.

AN XDC FRAME IS A PROGRAM. The player far-calls the packet: a fixed 14-byte
header (push ds / push cs / pop ds / mov si,<data> / mov ax,B800 / mov es,ax /
mov ch,0 / cld), then per changed span `mov di,imm16` and one of: unrolled
movsw/movsb, `mov cl|cx / rep movsb`, `mov al / rep stosb`, unrolled stosb,
or `es: mov [imm],imm`, then `pop ds / retf`. xdc_ops() executes that grammar
and REFUSES anything outside it, naming the packet and the offset - so a
stream that parses here is a stream whose every write is known.

THE CHECKSUM IS SHARED WITH THE GUEST (tests/vidbench/vidbench.asm vb_sum):
over the 16,384-byte canvas, 16-bit words little-endian, s = rol(s + w, 1).
Change one and the other must change with it.
"""
import argparse
import os
import struct
import sys

CANVAS = 16384                  # CGA mode 6: two 8 KB banks, 80 bytes a row
ROWB = 80
HDRLEN = 14
MOVSW, STOSW = 38.4, 27.4       # XDC_CODE.PAS's own constants (CGA waits and
                                # DRAM refresh folded in), for its cost model

# EIGHT lists (VIDEO-PLAN 2.2, revised by wave 0): a change of 1..6 bytes has
# a list of its own, decoded by straight-line stores exactly as XDC unrolls
# them - wave 0 measured a short span through `rep movsw` + `rep movsb` at
# +40-60 cycles against XDC's unrolled stores, and the rep start-up was all
# of it. SLICE is 7 bytes and up; RUN is a run of 7 and up (a shorter run is
# cheaper stored than set up).
L_P1, L_P2, L_P3, L_P4, L_P5, L_P6, L_SLICE, L_RUN, L_SLICEL, L_RUNL = \
    range(10)
NLISTS = 10                     # ...and a span of 256+ bytes has a list of
                                # its own (SLICEL, RUNL, 16-bit length), so
                                # the short ones' loops test for nothing


class XdvError(Exception):
    pass


# --------------------------------------------------------------------------
# reading an XDV
# --------------------------------------------------------------------------
def read_xdv(path):
    """(header dict, [packet bytes]) - XDC_GLOB.PAS's layout: a 512-byte
    header, packets padded to 512, and a one-byte-per-packet sector index
    at the very end."""
    d = open(path, "rb").read()
    if len(d) < 512 or d[:4] != b"XDCV":
        raise XdvError("%s: not an XDC stream (no XDCV signature)" % path)
    npk, largest, ach, rate, vm, cols, rows, feat = struct.unpack_from(
        "<HHHHBBBB", d, 4)
    if npk == 0 or ach == 0 or len(d) < 512 + npk:
        raise XdvError("%s: header says %d packets of %d audio bytes"
                       % (path, npk, ach))
    idx = d[len(d) - npk:]
    off, pk = 512, []
    for i in range(npk):
        n = idx[i] * 512
        if n == 0 or off + n > len(d) - npk:
            raise XdvError("%s: packet %d runs past the index" % (path, i))
        pk.append(d[off:off + n])
        off += n
    hdr = dict(path=path, packets=npk, largest=largest, achunk=ach,
               rate=rate, mode=vm, cols=cols, rows=rows, features=feat,
               fps=rate / ach)
    return hdr, pk


def xdc_ops(p, where=""):
    """The spans one XDC packet writes, in program order:
    [(address, bytes written, is_run)]. Also returns the code length.
    Every opcode outside XDC_CODE.PAS's vocabulary is refused."""
    if len(p) < HDRLEN + 2 or p[0:4] != b"\x1e\x0e\x1f\xbe" \
            or p[6:14] != b"\xb8\x00\xb8\x8e\xc0\xb5\x00\xfc":
        raise XdvError("%s: not XDC's frame header" % where)
    si = struct.unpack_from("<H", p, 4)[0]
    code = si
    pc, cx, al = HDRLEN, 0, 0
    ops, cur = [], None

    def need(k):
        if pc + k > code:
            raise XdvError("%s: instruction at +%d runs past the code"
                           % (where, pc))

    def data(n):
        nonlocal si
        if si + n > len(p):
            raise XdvError("%s: data at +%d runs past the packet"
                           % (where, si))
        b = p[si:si + n]
        si += n
        return b

    while True:
        need(1)
        b = p[pc]
        if b == 0x1F:
            need(2)
            if p[pc + 1] != 0xCB:
                raise XdvError("%s: pop ds at +%d not followed by retf"
                               % (where, pc))
            break
        if b == 0xBF:
            need(3)
            cur = [struct.unpack_from("<H", p, pc + 1)[0], bytearray(), False]
            ops.append(cur)
            pc += 3
            continue
        if cur is None and b not in (0xB1, 0xB9, 0xB0):
            raise XdvError("%s: a write at +%d before any mov di"
                           % (where, pc))
        if b == 0xB1:
            need(2); cx = p[pc + 1]; pc += 2
        elif b == 0xB9:
            need(3); cx = struct.unpack_from("<H", p, pc + 1)[0]; pc += 3
        elif b == 0xB0:
            need(2); al = p[pc + 1]; pc += 2
        elif b == 0xF3:
            need(2)
            o = p[pc + 1]
            pc += 2
            if o == 0xA4:
                cur[1] += data(cx)
            elif o == 0xA5:
                cur[1] += data(2 * cx)
            elif o == 0xAA:
                cur[1] += bytes([al]) * cx; cur[2] = True
            elif o == 0xAB:
                cur[1] += bytes([al]) * (2 * cx); cur[2] = True
            else:
                raise XdvError("%s: rep %02x at +%d" % (where, o, pc - 2))
            cx = 0
        elif b in (0xA4, 0xA5):
            cur[1] += data(1 if b == 0xA4 else 2); pc += 1
        elif b in (0xAA, 0xAB):
            cur[1] += bytes([al]) * (1 if b == 0xAA else 2)
            cur[2] = True
            pc += 1
        elif b == 0x26:                 # es: mov byte|word [imm], imm
            need(2)
            o = p[pc + 1]
            if o == 0xC6 and p[pc + 2] == 0x06:
                need(6)
                a = struct.unpack_from("<H", p, pc + 3)[0]
                ops.append([a, bytearray(p[pc + 5:pc + 6]), False])
                pc += 6
            elif o == 0xC7 and p[pc + 2] == 0x06:
                need(7)
                a = struct.unpack_from("<H", p, pc + 3)[0]
                ops.append([a, bytearray(p[pc + 5:pc + 7]), False])
                pc += 7
            else:
                raise XdvError("%s: es: %02x at +%d" % (where, o, pc))
            cur = None
        else:
            raise XdvError("%s: opcode %02x at +%d is not XDC's" %
                           (where, b, pc))
    out = []
    for a, bs, run in ops:
        if not bs:
            continue
        if a + len(bs) > CANVAS:
            raise XdvError("%s: a write at %04x+%d leaves the canvas"
                           % (where, a, len(bs)))
        out.append((a, bytes(bs), run and len(set(bs)) == 1))
    return out, code


def xdc_cycles(ops):
    """XDC's own cycle model for the program that wrote `ops`
    (XDC_CODE.PAS): header + footer, a mov di each, then the store."""
    c = 18 * 4 + 12 + 34
    for a, bs, run in ops:
        n = len(bs)
        if run:
            c += 12 + 8 + 8 + 4 + n * STOSW / 2
        elif n <= 6:
            c += 12 + (n // 2) * (4 + MOVSW) + (n % 2) * (4 + MOVSW / 2)
        else:
            c += 12 + 8 + 4 + n * MOVSW / 2
    return c


def apply_ops(buf, ops):
    for a, bs, run in ops:
        buf[a:a + len(bs)] = bs


# --------------------------------------------------------------------------
# the operand format (VIDEO-PLAN 2.2)
# --------------------------------------------------------------------------
def screen_row(a):
    """The CGA screen row holding canvas address `a`."""
    return ((a & 0x1FFF) // ROWB) * 2 + (a >> 13)


def band(ops):
    """(first, last) screen row the frame writes; (255, 0) for none."""
    rows = [screen_row(a + i) for a, bs, r in ops for i in (0, len(bs) - 1)]
    rows += [screen_row(a + i) for a, bs, r in ops
             for i in range(0, len(bs), ROWB)]
    return (min(rows), max(rows)) if rows else (255, 0)


def rowend(a):
    """The address one past the end of the CGA row holding `a`."""
    return (a - (a & 0x1FFF) % ROWB) + ROWB


def split_rows(ops):
    """Every span cut at its row's end - the rule that lets one file drive a
    surface of another layout."""
    out = []
    for a, bs, run in ops:
        i = 0
        while i < len(bs):
            k = min(len(bs) - i, rowend(a + i) - (a + i))
            piece = bs[i:i + k]
            out.append((a + i, piece, run))
            i += k
    return out


def classify(a, bs, run):
    n = len(bs)
    if n >= RUN_MIN and (run or len(set(bs)) == 1):
        return L_RUN if n < 256 else L_RUNL
    if n <= 6:
        return L_P1 + n - 1
    return L_SLICE if n < 256 else L_SLICEL


RUN_MIN = 6                     # a stretch of one byte value this long
                                # inside a slice becomes a RUN of its own


def hidden_runs(ops, rmin=RUN_MIN):
    """Every slice cut around the runs of one byte value inside it - XDC's
    FindHiddenRuns, re-applied because the streams do not carry it through:
    a run is 3 bytes on disk however long it is, and `rep stosw` into RAM is
    ~7 cycles a byte where a copy is ~13 (wave 0). Pieces keep their order
    and their addresses; nothing written changes."""
    out = []
    for a, bs, run in ops:
        if run or len(bs) < rmin:
            out.append((a, bs, run))
            continue
        i = 0
        start = 0
        n = len(bs)
        while i < n:
            j = i
            while j < n and bs[j] == bs[i]:
                j += 1
            if j - i >= rmin:
                if i > start:
                    out.append((a + start, bs[start:i], False))
                out.append((a + i, bs[i:j], True))
                start = j
            i = j
        if start < n:
            out.append((a + start, bs[start:], False))
    return out


ABS_BELOW = 4                   # a cluster of fewer entries than this goes
                                # into an ABSOLUTE segment (wave 0: a skip
                                # segment's set-up is ~228 cycles, an
                                # absolute entry ~11 more than a skip entry,
                                # and below 4 the absolute form is ALSO the
                                # smaller - so it wins both ways there)


def to_lists(ops, abs_below=ABS_BELOW):
    """The eight lists, in the plan's byte layout:
        list    = segment* 00
        segment = count(1..127) address(16) entry*count      skip-coded
                | 80h+count(1..127)          aentry*count     absolute
        entry   = skip, then the change      aentry = address(16), change
        Pn      = n bytes (n = 1..6)
        SLICE   = len8 bytes (7..255)        RUN    = len8 value (6..255)
        SLICEL  = len16 bytes (256+)         RUNL   = len16 value (256+)
        (a fill of a whole screen is one RUNL, as XDC makes it one
        rep stosb)
    NOTHING IS SPLIT AT A ROW: the addresses are the target adapter's own
    memory image (a file is laid out for its surface on the host - wave 0
    measured translating at playback at ~480 cycles a row change), so a
    span that is contiguous in memory is one entry however many rows it
    crosses. A row split is what made the worst frames 290 runs where XDC
    has one `rep stosb`.
    `skip` is from the end of the previous write in the segment (from the
    segment's address for its first entry). Entries one skip byte can reach
    form a CLUSTER; a cluster of `abs_below` or more is a skip segment, and
    the rest are pooled into absolute segments. Only P1..P6 take the
    absolute form; a SLICE or RUN cluster is always a skip segment.
    Returns (bytes, entries, segments)."""
    lists = [[] for _ in range(NLISTS)]
    for a, bs, run in hidden_runs(ops):
        lists[classify(a, bs, run)].append((a, bs))
    out = bytearray()
    ents = segs = 0

    def change(k, bs):
        if k <= L_P6:
            return bs
        if k == L_SLICE:
            return bytes([len(bs)]) + bs
        if k == L_RUN:                  # len then value: ONE lodsw
            return bytes([len(bs), bs[0]])
        if k == L_SLICEL:
            return struct.pack("<H", len(bs)) + bs
        return struct.pack("<H", len(bs)) + bs[:1]     # RUNL

    for k in range(NLISTS):
        L = sorted(lists[k])
        clusters, cur, end = [], [], None
        for a, bs in L:
            if cur and (a - end > 255 or len(cur) == 127):
                clusters.append(cur)
                cur = []
            cur.append((a, bs))
            end = a + len(bs)
        if cur:
            clusters.append(cur)
        pool = []
        for c in clusters:
            if k <= L_P6 and len(c) < abs_below:
                pool += c
                continue
            out += bytes([len(c)]) + struct.pack("<H", c[0][0])
            e = c[0][0]
            for a, bs in c:
                out += bytes([a - e]) + change(k, bs)
                e = a + len(bs)
            ents += len(c)
            segs += 1
        for i in range(0, len(pool), 127):
            part = pool[i:i + 127]
            out.append(0x80 | len(part))
            for a, bs in part:
                out += struct.pack("<H", a) + change(k, bs)
            ents += len(part)
            segs += 1
        out.append(0)
    return bytes(out), ents, segs


def decode_lists(buf, lists):
    """The reference decoder: what tests/vidbench's vd_native must do."""
    si = 0

    def put(k, di):
        nonlocal si
        if k <= L_P6:
            n = k - L_P1 + 1
            buf[di:di + n] = lists[si:si + n]
            si += n
        else:
            if k in (L_SLICE, L_RUN):
                n = lists[si]
                si += 1
            else:
                n = struct.unpack_from("<H", lists, si)[0]
                si += 2
            if k in (L_SLICE, L_SLICEL):
                buf[di:di + n] = lists[si:si + n]
                si += n
            else:
                buf[di:di + n] = bytes([lists[si]]) * n
                si += 1
        return di + n

    for k in range(NLISTS):
        while True:
            n = lists[si]
            si += 1
            if n == 0:
                break
            if n & 0x80:
                for _ in range(n & 0x7F):
                    di = struct.unpack_from("<H", lists, si)[0]
                    si += 2
                    put(k, di)
                continue
            di = struct.unpack_from("<H", lists, si)[0]
            si += 2
            for _ in range(n):
                di += lists[si]
                si += 1
                di = put(k, di)
    return si


def checksum(buf):
    """vb_sum's: s = rol16(s + word) over the canvas, little-endian words."""
    s = 0
    for i in range(0, len(buf), 2):
        s = (s + buf[i] + (buf[i + 1] << 8)) & 0xFFFF
        s = ((s << 1) | (s >> 15)) & 0xFFFF
    return s


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------
def frames(path):
    hdr, pk = read_xdv(path)
    for i, p in enumerate(pk):
        ops, code = xdc_ops(p, "%s packet %d" % (os.path.basename(path), i))
        yield hdr, i, p, ops, code


def cmd_stat(a):
    for path in a.files:
        n = ents = segs = lbytes = xbytes = 0
        for hdr, i, p, ops, code in frames(path):
            lists, e, s = to_lists(ops)
            n += 1
            ents += e
            segs += s
            lbytes += len(lists)
            xbytes += code - HDRLEN - 2 + sum(
                0 if r else len(b) for _, b, r in ops)
        fps = hdr["fps"]
        print("%s: mode %d, %d frames, %.3f fps, %d Hz x %d; per frame: "
              "XDC video %.0f B, lists %.0f B (%d entries, %.1f segments)"
              % (os.path.basename(path), hdr["mode"], n, fps, hdr["rate"],
                 hdr["achunk"], xbytes / n, lbytes / n, ents // n, segs / n))


def cmd_verify(a):
    """Decode every frame both ways onto one running screen each and
    compare after every frame."""
    bad = 0
    for path in a.files:
        x = bytearray(CANVAS)
        y = bytearray(CANVAS)
        n = 0
        for hdr, i, p, ops, code in frames(path):
            apply_ops(x, ops)
            lists, e, s = to_lists(ops)
            used = decode_lists(y, lists)
            if used != len(lists) or x != y:
                print("%s: frame %d DIFFERS" % (path, i))
                bad += 1
                break
            n += 1
        print("%s: %d frames, the lists reproduce XDC's screen exactly"
              % (os.path.basename(path), n) if not bad else "")
    return 1 if bad else 0


def xdc_emit(ops):
    """An XDC packet for `ops`, in XDC_CODE.PAS's own forms: a change of 6
    bytes or fewer is unrolled movsw/movsb (or stosb for a run), a longer
    one `mov cl,n / rep movsb` (`mov al,v / mov cl,n / rep stosb` for a
    run), AL cached across runs of one value as XDC caches it. For the
    bench's SYNTHETIC frames, so each construct is priced against exactly
    what XDC would have emitted for it."""
    code = bytearray(b"\x1e\x0e\x1f\xbe\0\0\xb8\x00\xb8\x8e\xc0\xb5\x00\xfc")
    data = bytearray()
    al = None
    for a, bs, run in ops:
        n = len(bs)
        code += b"\xbf" + struct.pack("<H", a)
        if run:
            if al != bs[0]:
                code += bytes([0xB0, bs[0]])
                al = bs[0]
            if n <= 6:
                code += b"\xaa" * n
            else:
                code += bytes([0xB1, n, 0xF3, 0xAA])
        else:
            if n <= 6:
                code += b"\xa5" * (n // 2) + b"\xa4" * (n % 2)
            else:
                code += bytes([0xB1, n, 0xF3, 0xA4])
            data += bs
    code += b"\x1f\xcb"
    struct.pack_into("<H", code, 4, len(code))
    p = bytes(code + data)
    return p + bytes(-len(p) % 512)


def synth_frames():
    """Frames that price ONE construct each: n changes of one kind, dense
    (one skip apart, so a segment holds 255) or sparse (300 bytes apart, so
    every change is a segment of its own), and an empty frame for the fixed
    cost of a frame. All inside bank 0 and never across a row, so the
    translating decoder sees exactly the row changes the layout forces."""
    def row_ok(a, n):
        return (a % ROWB) + n <= ROWB

    def dense(n, k, run=False, step=None):
        ops, a = [], 0
        step = step or (k + 1)
        while len(ops) < n:
            if not row_ok(a, k):
                a += ROWB - a % ROWB
                continue
            v = (len(ops) * 37 + 11) & 0xFF
            bs = bytes([v]) * k if run else bytes((v + j * 13) & 0xFF
                                                 for j in range(k))
            ops.append((a, bs, run))
            a += step
            if a + k > 8000:
                break
        return ops
    return [
        ("S empty", []),
        ("S P1 x400", dense(400, 1)),
        ("S P1 sparse", dense(26, 1, step=300)),
        ("S P2 x400", dense(400, 2)),
        ("S P3 x300", dense(300, 3)),
        ("S P4 x300", dense(300, 4)),
        ("S P6 x200", dense(200, 6)),
        ("S SL16 x150", dense(150, 16)),
        ("S SL40 x60", dense(60, 40)),
        ("S RUN16x150", dense(150, 16, run=True)),
        ("S RUN40 x60", dense(60, 40, run=True)),
        ("S P1 row", [(ROWB * i, bytes([i & 0xFF]), False)
                      for i in range(100)]),
    ]


BENCH_PICK = (("max cycles", lambda r: r["cyc"]),
              ("max entries", lambda r: r["ents"]),
              ("p95 cycles", None),
              ("median cycles", None))


def cmd_benchdat(a):
    """VIDBENCH.DAT: the frames tests/vidbench/ times, each twice - XDC's
    own packet (paragraph-aligned, so it can be far-called at seg:0) and
    our lists - plus the checksum of the canvas after that frame is applied
    to BLACK, which all three of the guest's check rows must reproduce.

        0    'VBD1'
        4    frame count (word)
        6    0
        8    per frame, 32 bytes:
               +0  label, 12 bytes, NUL-padded
               +12 XDC packet paragraph (from the file's start), +14 length
               +16 lists paragraph, +18 length
               +20 checksum on black
               +22 XDC spans, +24 list entries, +26 bytes written
               +28 XDC's cycle model / 16
               +30 first and +31 last screen row the frame writes (the
                   dirty band a shadow copies; 255, 0 when it writes none)
        then the blobs, each on a paragraph."""
    picked = []
    want = {}
    for f in a.frame or []:
        name, _, idx = f.rpartition(":")
        want.setdefault(name.upper(), set()).add(int(idx))
    extra = {}
    for f in a.extra or []:
        name, _, idx = f.rpartition(":")
        extra.setdefault(name.upper(), set()).add(int(idx))
    for path in a.files:
        rows = []
        base = os.path.splitext(os.path.basename(path))[0][:6].upper()
        if want:
            only = want.get(os.path.basename(path).upper(), set())
            for hdr, i, p, ops, code in frames(path):
                if i in only:
                    lists, e, s = to_lists(ops)
                    picked.append(dict(i=i, p=p, ops=ops, lists=lists,
                                       ents=e, cyc=xdc_cycles(ops),
                                       wb=sum(len(b) for _, b, r in ops),
                                       label=("%s %d" % (base, i))[:12]))
            continue
        for hdr, i, p, ops, code in frames(path):
            lists, e, s = to_lists(ops)
            rows.append(dict(i=i, p=p, ops=ops, lists=lists, ents=e,
                             cyc=xdc_cycles(ops),
                             wb=sum(len(b) for _, b, r in ops)))
        by = sorted(rows, key=lambda r: r["cyc"])
        chosen = []
        for tag, key in BENCH_PICK:
            if tag == "p95 cycles":
                r = by[int(len(by) * 0.95)]
            elif tag == "median cycles":
                r = by[len(by) // 2]
            else:
                r = max(rows, key=key)
            if r["i"] not in [c["i"] for c in chosen]:
                chosen.append(r)
        for i in sorted(extra.get(os.path.basename(path).upper(), ())):
            if i not in [c["i"] for c in chosen]:
                chosen.append(next(r for r in rows if r["i"] == i))
        for r in chosen:
            r["label"] = ("%s %d" % (base, r["i"]))[:12]
            picked.append(r)
    if a.synth:
        for label, ops in synth_frames():
            lists, e, sg = to_lists(ops)
            picked.append(dict(label=label[:12], p=xdc_emit(ops), ops=ops,
                               lists=lists, ents=e, cyc=xdc_cycles(ops),
                               wb=sum(len(b) for _, b, r in ops)))
    if len(picked) > a.max:
        picked = picked[:a.max]
    out = bytearray(b"VBD1" + struct.pack("<HH", len(picked), 0))
    out += bytes(32 * len(picked))

    def para():
        while len(out) % 16:
            out.append(0)
        return len(out) // 16

    for n, r in enumerate(picked):
        black = bytearray(CANVAS)
        apply_ops(black, r["ops"])
        chk = bytearray(CANVAS)
        decode_lists(chk, r["lists"])
        assert chk == black, "lists and XDC disagree on %s" % r["label"]
        xp = para()
        out += r["p"]
        lp = para()
        out += r["lists"]
        d = 8 + 32 * n
        out[d:d + 12] = r["label"].encode().ljust(12, b"\0")
        y0, y1 = band(r["ops"])
        struct.pack_into("<HHHHHHHHHBB", out, d + 12, xp, len(r["p"]), lp,
                         len(r["lists"]), checksum(black), len(r["ops"]),
                         r["ents"], r["wb"], int(r["cyc"] / 16), y0, y1)
        print("  %-12s  XDC %5d B  lists %5d B  spans %4d  entries %4d  "
              "written %5d B  XDC model %6.0f cyc  sum %04x"
              % (r["label"], len(r["p"]), len(r["lists"]), len(r["ops"]),
                 r["ents"], r["wb"], r["cyc"], checksum(black)))
    para()
    if len(out) > a.limit:
        sys.exit("os88vid: %s would be %d bytes, over --limit %d"
                 % (a.out, len(out), a.limit))
    open(a.out, "wb").write(out)
    print("os88vid: %s, %d frames, %d bytes" % (a.out, len(picked), len(out)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stat")
    s.add_argument("files", nargs="+")
    s = sub.add_parser("verify")
    s.add_argument("files", nargs="+")
    s = sub.add_parser("benchdat")
    s.add_argument("out")
    s.add_argument("files", nargs="+")
    s.add_argument("--max", type=int, default=32)
    s.add_argument("--frame", action="append", metavar="FILE:INDEX",
                   help="time exactly these frames instead of the picks")
    s.add_argument("--extra", action="append", metavar="FILE:INDEX",
                   help="time this frame as well as the picks")
    s.add_argument("--synth", action="store_true",
                   help="append the one-construct frames (synth_frames)")
    s.add_argument("--limit", type=int, default=150 * 1024)
    a = ap.parse_args()
    try:
        return {"stat": cmd_stat, "verify": cmd_verify,
                "benchdat": cmd_benchdat}[a.cmd](a) or 0
    except XdvError as e:
        sys.exit("os88vid: %s" % e)


if __name__ == "__main__":
    sys.exit(main())
