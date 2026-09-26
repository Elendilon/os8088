#!/usr/bin/env python3
"""os88vid - the host half of Video Player (SPEC.md 98; docs/plans/VIDEO-PLAN.md).

    python3 tools/os88vid.py import   IN.XDV OUT.V88 [--target cga|herc|lin80]
    python3 tools/os88vid.py encode   FRAME... OUT.V88 --fps F [--wav W.WAV]
                                      [--layout cga|herc|lin80]
    python3 tools/os88vid.py info     FILE.V88...
    python3 tools/os88vid.py decode   FILE.V88 --frame N --png OUT.PNG
    python3 tools/os88vid.py verify   FILE.V88... [--against IN.XDV]
    python3 tools/os88vid.py verify   FILE.XDV...     (the lists vs XDC's code)
    python3 tools/os88vid.py stat     FILE.XDV...
    python3 tools/os88vid.py benchdat OUT.DAT FILE.XDV...   (tests/vidbench)
    python3 tools/os88vid.py --selfcheck

THE .V88 FILE IS SPEC.md 98.1, and this file is its reference: Writer writes
it, Reader reads it the way 98.1.6 says a player must, and verify_v88 holds
a file to every writer's rule as well. `import` re-expresses an XDC stream
(MobyGamer's XDC, MIT, (c) 2014 Jim Leonard) EXACTLY - `verify --against`
proves it frame by frame, audio included - and `--target` re-lays it out
for another surface by simulating it. `encode` is the minimal encoder:
lossless, every changed byte; the budgets are wave 8's.

AN XDC FRAME IS A PROGRAM. The player far-calls the packet: a fixed 14-byte
header (push ds / push cs / pop ds / mov si,<data> / mov ax,B800 / mov es,ax /
mov ch,0 / cld), then per changed span `mov di,imm16` and one of: unrolled
movsw/movsb, `mov cl|cx / rep movsb`, `mov al / rep stosb`, unrolled stosb,
or `es: mov [imm],imm`, then `pop ds / retf`. xdc_ops() executes that grammar
and REFUSES anything outside it, naming the packet and the offset - so a
stream that parses here is a stream whose every write is known. Its audio is
the packet's last `achunk` bytes.

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


def verify_xdv(path):
    """Decode every frame of an XDC stream both ways - XDC's program and our
    lists - onto one running screen each, and compare after every frame."""
    x = bytearray(CANVAS)
    y = bytearray(CANVAS)
    n = 0
    for hdr, i, p, ops, code in frames(path):
        apply_ops(x, ops)
        lists, e, s = to_lists(ops)
        used = decode_lists(y, lists)
        if used != len(lists) or x != y:
            print("%s: frame %d DIFFERS" % (path, i))
            return 1
        n += 1
    print("%s: %d frames, the lists reproduce XDC's screen exactly"
          % (os.path.basename(path), n))
    return 0


def xdc_emit(ops, pad=True):
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
                code += xdc_count(n) + b"\xf3\xaa"
        else:
            if n <= 6:
                code += b"\xa5" * (n // 2) + b"\xa4" * (n % 2)
            else:
                code += xdc_count(n) + b"\xf3\xa4"
            data += bs
    code += b"\x1f\xcb"
    struct.pack_into("<H", code, 4, len(code))
    p = bytes(code + data)
    return p + bytes(-len(p) % 512) if pad else p


def xdc_count(n):
    """XDC's count load: `mov cl` (CH is 0 from the header), `mov cx` past
    255."""
    return bytes([0xB1, n]) if n < 256 else b"\xb9" + struct.pack("<H", n)


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


# --------------------------------------------------------------------------
# the .V88 file (SPEC.md 98.1)
# --------------------------------------------------------------------------
class V88Error(Exception):
    pass


V88_SIG = b"V88\x1a"
SECTOR = 512
SP_MAX = 64                     # sectors a super-packet may take (32 KB)
AUD_NONE, AUD_PCM8, AUD_ADPCM4 = 0, 1, 2
AUD_BY_NAME = {"pcm8": AUD_PCM8, "adpcm4": AUD_ADPCM4}
ADPCM4_REF = 0x80               # the stream's reference byte (SPEC.md 98.1.1)
PF_MONO1, PF_CGACOMP, PF_VGA8 = 1, 2, 3
PF_NAMES = {PF_MONO1: "MONO1", PF_CGACOMP: "CGACOMP", PF_VGA8: "VGA8"}
LAY_CGA, LAY_HERC, LAY_LIN80, LAY_LIN320, LAY_MODEX = 1, 2, 3, 4, 5
LAYOUTS = {                     # SPEC.md 98.1.2: banks, stride, rows, name
    LAY_CGA: (2, 80, 200, "cga"),
    LAY_HERC: (4, 90, 348, "herc"),
    LAY_LIN80: (1, 80, 480, "lin80"),
    LAY_LIN320: (1, 320, 200, "lin320"),
    LAY_MODEX: (1, 80, 240, "modex"),   # a PLANE's image: 80 bytes a row
}
LAYOUT_BY_NAME = {v[3]: k for k, v in LAYOUTS.items()}
ASPECT = {LAY_CGA: (5, 12), LAY_HERC: (29, 45), LAY_LIN80: (1, 1),
          LAY_LIN320: (5, 6), LAY_MODEX: (1, 1)}
# a byte is a PIXEL on a VGA8 layout and eight of them on the others - and
# on MODEX a byte of each of four planes, so a plane row's byte is 4 pixels
PIX_PER_BYTE = {LAY_CGA: 8, LAY_HERC: 8, LAY_LIN80: 8, LAY_LIN320: 1,
                LAY_MODEX: 4}
VGA8_LAYOUTS = (LAY_LIN320, LAY_MODEX)
PLANE = 65536                   # a planar surface: plane p at p x 64 KB
CYC_SUB = 40                    # a MODEX sub-record's Map Mask OUT
PAL_BYTES = 768                 # VGA8's palette: 256 x (r, g, b), 0..63
BAYER4 = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)


def vga8_lum16(pal):
    """The player's luma of each palette entry, 0..16 (SPEC.md 98.4):
    (77 r + 150 g + 29 b) >> 8 on the DAC's six bits, then x 17 + 32 >> 6"""
    out = []
    for i in range(256):
        r, g, b = pal[3 * i:3 * i + 3]
        l6 = (77 * r + 150 * g + 29 * b) >> 8
        out.append((l6 * 17 + 32) >> 6)
    return out


def vga8_mono(cv, w, h, pal):
    """A VGA8 canvas (w pixels a row, a multiple of 8) as the MONO1 canvas
    the Preview shows: a pixel is lit when its luma beats the 4 x 4 Bayer
    cell over it - exactly the player's vp_v8mono"""
    lum = vga8_lum16(pal)
    wb = w // 8
    out = bytearray(wb * h)
    for y in range(h):
        row = cv[y * w:(y + 1) * w]
        by = BAYER4[(y & 3) * 4:(y & 3) * 4 + 4]
        for xb in range(wb):
            v = 0
            for i in range(8):
                x = xb * 8 + i
                if lum[row[x]] > by[x & 3]:
                    v |= 0x80 >> i
            out[y * wb + xb] = v
    return bytes(out)
KEY_SECS = 2.0                  # a keyframe every 2 seconds (98.1.3)
POSTER_FLAT = 0.98              # ...the poster is the first that is not
                                # this much one byte value
REC_HDR = 6                     # len, y0, y1

# The wave 0 cost model, MartyPC's CGA 5150 writing the screen, cycles
# (docs/reports/VIDEO-W0-2026-09-25.md, section (a)). A slice and a run are
# linear fits through the 16- and 40-byte rows, which both land on them.
CYC_FRAME, CYC_SEG, CYC_ABS = 1214, 215, 14
CYC_P = (49.6, 65.2, 89.1, 104.8, 125.5, 146.1)
CYC_SLICE = (84, 18.0)          # base, per byte
CYC_RUN = (101, 13.0)
HZ = 4772727.0


class Geom:
    """A canvas on a layout: where each row starts in the surface's memory
    image, which addresses belong to the canvas, and which row each is."""

    def __init__(self, layout, wb, h):
        if layout not in LAYOUTS:
            raise V88Error("layout %d is not one of SPEC.md 98.1.2's" % layout)
        banks, stride, rows, self.name = LAYOUTS[layout]
        if not (1 <= wb <= stride and 1 <= h <= rows):
            raise V88Error("a %d x %d canvas does not fit %s (%d x %d)"
                           % (wb, h, self.name, stride, rows))
        self.layout, self.wb, self.h = layout, wb, h
        self.banks, self.stride = banks, stride
        self.planes = 4 if layout == LAY_MODEX else 1
        self.w = wb * PIX_PER_BYTE[layout]
        self.base = [(y % banks) * 8192 + (y // banks) * stride
                     for y in range(h)]
        self.valid = bytearray(65536)
        self.rowof = [-1] * 65536
        for y, b in enumerate(self.base):
            self.valid[b:b + wb] = b"\x01" * wb
            for x in range(wb):
                self.rowof[b + x] = y

    def surface(self):
        """A black surface image: 64 KB, or a plane of it each for MODEX"""
        return bytearray(PLANE * self.planes)

    def canvas(self, surf):
        """The canvas out of a surface image, top row first - for MODEX a
        pixel a byte, pixel x in plane x mod 4"""
        if self.planes == 1:
            return b"".join(bytes(surf[b:b + self.wb]) for b in self.base)
        w, out = self.w, bytearray(self.w * self.h)
        for y, b in enumerate(self.base):
            for p in range(4):
                out[y * w + p:(y + 1) * w:4] = surf[p * PLANE + b:
                                                    p * PLANE + b + self.wb]
        return bytes(out)

    def put(self, surf, cv):
        if self.planes == 1:
            for y, b in enumerate(self.base):
                surf[b:b + self.wb] = cv[y * self.wb:(y + 1) * self.wb]
            return
        w = self.w
        for y, b in enumerate(self.base):
            for p in range(4):
                surf[p * PLANE + b:p * PLANE + b + self.wb] = \
                    cv[y * w + p:(y + 1) * w:4]


def spans(changed, surf, g, valid=None, gaps=True):
    """Writes for the canvas addresses in `changed`, whose new values
    are in `surf`. Adjacent addresses make one span. A gap of one byte is
    closed (a P1 + P1 costs more than the P3 that covers both), and so is a
    gap of up to four between two spans of 7 or more (a slice entry's ~84
    cycles of set-up against ~18 a byte) - but only across canvas bytes,
    so nothing outside the canvas is ever written."""
    sp = []
    for a in sorted(changed):      # a banked layout's rows are not in
        if sp and a == sp[-1][1]:  # address order
            sp[-1][1] = a + 1
        else:
            sp.append([a, a + 1])
    out = []
    valid = g.valid if valid is None else valid
    for s, e in sp:
        if out and gaps:
            ps, pe = out[-1]
            gap = s - pe
            if gap <= 4 and all(valid[pe:s]) and \
                    (gap <= 1 or (pe - ps >= 7 and e - s >= 7)):
                out[-1][1] = e
                continue
        out.append([s, e])
    return [(s, bytes(surf[s:e]), False) for s, e in out]


def clip_ops(ops, g):
    """`ops` cut to canvas addresses: XDC's full-screen fill is one 16 KB
    rep stosb straight across the two 192-byte holes at the ends of CGA's
    banks, which no row owns. The picture is the same; the writer's rule
    (SPEC.md 98.1.3) is that nothing outside the canvas is written."""
    out = []
    for a, bs, run in ops:
        i, n = 0, len(bs)
        while i < n:
            while i < n and not g.valid[a + i]:
                i += 1
            j = i
            while j < n and g.valid[a + j]:
                j += 1
            if j > i:
                out.append((a + i, bs[i:j], run))
            i = j
    return out


def band_of(ops, g):
    """(y0, y1): the canvas rows `ops` write, y0 <= row < y1; (0, 0) none.
    A span stays inside one bank, and a bank's rows rise with its
    addresses, so a span's first and last byte bound its rows."""
    if not ops:
        return 0, 0
    y0 = min(g.rowof[a] for a, bs, r in ops)
    y1 = max(g.rowof[a + len(bs) - 1] for a, bs, r in ops) + 1
    return y0, y1


def record(ops, g, audio=b"", limit=SP_MAX * SECTOR - 4):
    """A frame record; `limit` is a super-packet's room, or a keyframe's
    (65,535: its length is a word, and it rides in no super-packet)"""
    if g.planes > 1:
        # MODEX (98.1.3.1): sub-records, each its Map Mask and ten lists,
        # a 0 after the last - ops is [(mask, ops), ...]
        body, every = bytearray(), []
        for mask, sub in ops:
            if sub:
                body.append(mask)
                body += to_lists(sub)[0]
                every += sub
        body.append(0)
        lists = bytes(body)
        y0, y1 = band_of(every, g)
    else:
        lists, e, s = to_lists(ops)
        y0, y1 = band_of(ops, g)
    n = REC_HDR + len(lists) + len(audio)
    if n > limit:
        raise V88Error("a record of %d bytes cannot fit %s" % (
            n, "a super-packet" if limit < 65535 else "its length word"))
    return struct.pack("<HHH", n, y0, y1) + lists + audio


def keyframe_ops(surf, g):
    if g.planes > 1:
        cv = g.canvas(surf)
        return modex_subs(cv, [v != 0 for v in cv], g)
    changed = [a for b in g.base for a in range(b, b + g.wb) if surf[a]]
    return spans(changed, surf, g)


def modex_subs(cv, changed, g):
    """A MODEX frame's writes (98.1.3.1): the canvas `cv` (a pixel a byte)
    at the pixels `changed` flags. An aligned group of four pixels of ONE
    colour with two or more of them changed is one byte under Map Mask 0Fh
    - four pixels a store; every other changed pixel is its plane's. A
    plane's spans may close a gap over bytes that are already right (the
    target's own bytes, so nothing changes), but never over a group the
    0Fh sub-record writes, and 0Fh's spans close no gap at all: a byte
    there is four pixels, and a gap's four need not be one colour"""
    w = g.w
    grp, per = [], [[] for _ in range(4)]
    gsurf = bytearray(PLANE)
    psurf = [bytearray(PLANE) for _ in range(4)]
    pvalid = [bytearray(g.valid) for _ in range(4)]
    for y, b in enumerate(g.base):
        row = cv[y * w:(y + 1) * w]
        for p in range(4):
            psurf[p][b:b + g.wb] = row[p::4]
        for xb in range(g.wb):
            x = xb * 4
            ch = changed[y * w + x:y * w + x + 4]
            n = sum(1 for c in ch if c)
            if not n:
                continue
            v = row[x]
            if n >= 2 and row[x + 1] == v and row[x + 2] == v and \
                    row[x + 3] == v:
                grp.append(b + xb)
                gsurf[b + xb] = v
                for p in range(4):
                    pvalid[p][b + xb] = 0
            else:
                for p in range(4):
                    if ch[p]:
                        per[p].append(b + xb)
    return [(0x0F, spans(grp, gsurf, g, gaps=False))] + \
        [(1 << p, spans(per[p], psurf[p], g, valid=pvalid[p]))
         for p in range(4)]


def flat(cv):
    return max(cv.count(bytes([v])) for v in set(cv)) >= POSTER_FLAT * len(cv) \
        if cv else True


PIT_HZ = 1193182
FSX_RATE_MIN = 2048             # apps/os88api.inc's


def pit_rate(rate, spf):
    """(divisor, periods a frame) for FSXF_RATE (SPEC.md 98.1.1): the fewest
    periods a frame whose period fits 16 bits, and that period rounded."""
    n = 1
    while PIT_HZ * spf / (rate * n) > 65535:
        n += 1
    div = round(PIT_HZ * spf / (rate * n))
    if div < FSX_RATE_MIN:
        raise V88Error("%.1f fps is faster than FSXF_RATE can pace"
                       % (rate / spf))
    return div, n


class Writer:
    """Collects a stream frame by frame and writes SPEC.md 98.1's file."""

    def __init__(self, g, rate, spf, audio_fmt, abytes, pixfmt, title="",
                 credits="", aspect=None, keysecs=KEY_SECS, palette=None):
        if (pixfmt == PF_VGA8) != (g.layout in VGA8_LAYOUTS):
            raise V88Error("VGA8 is LIN320's and MODEX's format, and they "
                           "take no other")
        if (pixfmt == PF_VGA8) != (palette is not None) or \
                (palette is not None and (len(palette) != PAL_BYTES or
                                          max(palette) > 63)):
            raise V88Error("a VGA8 file carries 768 palette bytes of 0..63, "
                           "and no other file carries any")
        self.palette = bytes(palette) if palette is not None else None
        self.g, self.rate, self.spf = g, rate, spf
        self.audio_fmt, self.abytes, self.pixfmt = audio_fmt, abytes, pixfmt
        self.title, self.credits = title, credits
        self.aspect = aspect or ASPECT[g.layout]
        self.keyint = max(1, round(keysecs * rate / spf))
        self.recs, self.keys = [], []       # keys: (k, record, canvas)

    def frame(self, ops, surf, audio=b""):
        """`ops` are the frame's writes, already applied to `surf`."""
        if len(audio) != self.abytes:
            raise V88Error("frame %d has %d audio bytes, not %d"
                           % (len(self.recs), len(audio), self.abytes))
        k = len(self.recs)
        self.recs.append(record(ops, self.g, audio))
        if k % self.keyint == 0:
            kop = keyframe_ops(surf, self.g)
            try:
                self.keys.append((k, record(kop, self.g, limit=65535),
                                  self.g.canvas(surf)))
            except V88Error:
                # a VGA8 canvas past its record's length word (a 320 x
                # 240 MODEX one can be) has no keyframe here: the file
                # still plays from the start, and seeks to the ones it has
                self.skipped = getattr(self, "skipped", 0) + 1

    def write(self, path, poster=None):
        g = self.g
        if not self.recs:
            raise V88Error("no frames")
        # the stream: greedy super-packets, then chained
        sps, where = [], []          # where[f] = (super-packet, index)
        cur, size = [], 4
        for r in self.recs:
            if cur and size + len(r) > SP_MAX * SECTOR:
                sps.append(cur)
                cur, size = [], 4
            where.append((len(sps), len(cur)))
            cur.append(r)
            size += len(r)
        sps.append(cur)
        secs = [-(-(4 + sum(len(r) for r in sp)) // SECTOR) for sp in sps]
        keys = self.keys
        if self.audio_fmt == AUD_ADPCM4:
            # THE REFERENCE BYTE (98.1.1.1): the sample the decoder holds at
            # frame k+1, where a seek starts the card - and its scale must
            # be 0 there, which only audio_chunks(keys=) arranges
            st = adpcm4_trace(b"".join(r[len(r) - self.abytes:]
                                       for r in self.recs))
            keys = []
            for k, r, c in self.keys:
                ref, sc = st[(k + 1) * self.abytes]
                if sc:
                    raise V88Error("the ADPCM4 stream's scale is %d at frame "
                                   "%d, where keyframe %d's seek starts; "
                                   "encode it with audio_chunks(keys=)"
                                   % (sc, k + 1, k))
                keys.append((k, r + bytes([ref]), c))
        nk = len(keys)
        ktab = -(-16 * nk // SECTOR) * SECTOR if nk else 0
        krec = sum(len(r) for k, r, c in keys)
        pal = SECTOR if self.palette else 0     # the palette: sector 1
        kbase = SECTOR + (2 * SECTOR if self.palette else 0) + ktab
        ktoff = SECTOR + (2 * SECTOR if self.palette else 0)
        s0 = kbase + -(-krec // SECTOR) * SECTOR
        spoff, o = [], s0
        for n in secs:
            spoff.append(o)
            o += n * SECTOR
        stream = bytearray()
        for i, sp in enumerate(sps):
            nxt = secs[i + 1] if i + 1 < len(sps) else 0
            b = struct.pack("<HH", len(sp), nxt) + b"".join(sp)
            stream += b + bytes(secs[i] * SECTOR - len(b))
        kt, kr, o = bytearray(), bytearray(), kbase
        for k, r, c in keys:
            if k + 1 < len(self.recs):
                spi, idx = where[k + 1]
                sp_at, sp_n = spoff[spi], secs[spi]
            else:
                sp_at, sp_n, idx = 0, 0, 0
            if idx > 255:
                raise V88Error("frame %d is record %d of its super-packet; "
                               "a keyframe can name 255" % (k + 1, idx))
            kt += struct.pack("<IIHIBB", k, o, len(r), sp_at, sp_n, idx)
            kr += r
            o += len(r)
        if poster is None:
            poster = next((i for i, (k, r, c) in enumerate(keys)
                           if not flat(c)), 0 if nk else 0xFFFF)
        elif not 0 <= poster < nk:
            raise V88Error("--poster %d: there are %d keyframes" % (poster, nk))
        hdr = bytearray(SECTOR)
        hdr[0:4] = V88_SIG
        struct.pack_into("<HHIHHBBH", hdr, 4, 1, 0, len(self.recs), self.rate,
                         self.spf, self.audio_fmt, 1, self.abytes)
        struct.pack_into("<HB", hdr, 20, *pit_rate(self.rate, self.spf))
        for off, size, text in ((32, 48, self.title), (80, 96, self.credits)):
            t = text.encode("ascii", "replace")[:size - 1]
            hdr[off:off + len(t)] = t
        struct.pack_into("<BBHHBBIHHIHHIHH", hdr, 192, self.pixfmt,
                         g.layout, g.wb, g.h, self.aspect[0], self.aspect[1],
                         ktoff if nk else 0, nk, poster, s0, secs[0],
                         max(secs), len(stream),
                         max(len(r) for r in self.recs),
                         max((len(r) for k, r, c in keys), default=0))
        struct.pack_into("<I", hdr, 224, pal)
        front = bytes(hdr)
        if self.palette:
            front += self.palette + bytes(2 * SECTOR - PAL_BYTES)
        out = front + kt + bytes(ktab - len(kt)) + kr + \
            bytes(s0 - kbase - len(kr)) + stream
        with open(path, "wb") as f:
            f.write(out)
        return dict(bytes=len(out), keys=nk, keybytes=ktab + len(kr),
                    stream=len(stream), sps=len(sps), poster=poster)


def walk_lists(buf, data, si, write=None, seg=None):
    """Apply the ten lists at data[si:] to `buf` (a surface image); call
    write(k, di, n) for each write first and seg(absolute) for each
    segment. Returns the index past the tenth list. A truncated list raises
    V88Error."""
    try:
        for k in range(NLISTS):
            while True:
                n = data[si]
                si += 1
                if n == 0:
                    break
                if n & 0x80:
                    todo, di, absolute = n & 0x7F, None, True
                else:
                    todo, absolute = n, False
                    di = data[si] | data[si + 1] << 8
                    si += 2
                if seg:
                    seg(absolute)
                for _ in range(todo):
                    if absolute:
                        di = data[si] | data[si + 1] << 8
                        si += 2
                    else:
                        di += data[si]
                        si += 1
                    if k <= L_P6:
                        m = k - L_P1 + 1
                        src = data[si:si + m]
                        si += m
                    else:
                        if k in (L_SLICE, L_RUN):
                            m = data[si]
                            si += 1
                        else:
                            m = data[si] | data[si + 1] << 8
                            si += 2
                        if k in (L_SLICE, L_SLICEL):
                            src = data[si:si + m]
                            si += m
                        else:
                            src = bytes([data[si]]) * m
                            si += 1
                    if len(src) != m or si > len(data):
                        raise IndexError
                    if write:
                        write(k, di, m)
                    if di + m > 65536:
                        raise V88Error("a write at %04x+%d wraps the segment"
                                       % (di, m))
                    buf[di:di + m] = src
                    di += m
    except IndexError:
        raise V88Error("the lists run off the end of their record")
    return si


class Reader:
    """A .V88, read the way SPEC.md 98.1.6 says a player must: every field
    it sizes by is checked, and a failure is a V88Error naming it."""

    def __init__(self, path):
        self.path = path
        self.d = d = open(path, "rb").read()
        if len(d) < SECTOR or d[:4] != V88_SIG:
            raise V88Error("%s: not a .V88 (no signature)" % path)
        (ver, flags, self.frames, self.rate, self.spf, self.audio,
         self.nrend, self.abytes) = struct.unpack_from("<HHIHHBBH", d, 4)
        if ver != 1 or flags:
            raise V88Error("version %d, flags %04x: a version 1 reader "
                           "refuses both" % (ver, flags))
        if self.frames < 1 or self.spf < 1 or self.rate < 1:
            raise V88Error("frames %d, rate %d, samples per frame %d"
                           % (self.frames, self.rate, self.spf))
        if not 1 <= self.nrend <= 4:
            raise V88Error("%d renditions" % self.nrend)
        want = {AUD_NONE: 0, AUD_PCM8: self.spf}
        if self.spf % 2 == 0:
            want[AUD_ADPCM4] = self.spf // 2
        if self.audio not in want:
            raise V88Error("audio format %d is not a version 1 one"
                           % self.audio)
        if self.abytes != want[self.audio]:
            raise V88Error("%d audio bytes a frame with format %d and %d "
                           "samples" % (self.abytes, self.audio, self.spf))
        self.pitdiv, self.pitper = struct.unpack_from("<HB", d, 20)
        if (self.pitdiv, self.pitper) != pit_rate(self.rate, self.spf):
            raise V88Error("PIT divisor %d x %d for %d Hz / %d; it should be "
                           "%d x %d" % ((self.pitdiv, self.pitper, self.rate,
                                         self.spf) +
                                        pit_rate(self.rate, self.spf)))
        self.title = d[32:80].split(b"\0")[0].decode("ascii", "replace")
        self.credits = d[80:176].split(b"\0")[0].decode("ascii", "replace")
        (self.pixfmt, layout, wb, h, an, ad, self.ktab, self.nkeys,
         self.poster, self.sp0, self.sp0n, self.spmax, self.slen, self.rmax,
         self.kmax) = struct.unpack_from("<BBHHBBIHHIHHIHH", d, 192)
        if self.pixfmt not in PF_NAMES:
            raise V88Error("pixel format %d" % self.pixfmt)
        if (self.pixfmt == PF_VGA8) != (layout in VGA8_LAYOUTS):
            raise V88Error("pixel format %d on layout %d: VGA8 is LIN320's "
                           "and MODEX's, and only theirs"
                           % (self.pixfmt, layout))
        self.g = Geom(layout, wb, h)
        pal = struct.unpack_from("<I", d, 224)[0]
        self.palette = None
        if self.pixfmt == PF_VGA8:
            if not pal or pal % SECTOR or pal + PAL_BYTES > len(d):
                raise V88Error("a VGA8 file's palette at %d does not fit"
                               % pal)
            self.palette = d[pal:pal + PAL_BYTES]
            if max(self.palette) > 63:
                raise V88Error("the palette holds values past the DAC's 63")
        elif pal:
            raise V88Error("a palette at %d in a %s file"
                           % (pal, PF_NAMES[self.pixfmt]))
        self.aspect = (an, ad)
        if not (1 <= self.sp0n <= SP_MAX and 1 <= self.spmax <= SP_MAX) \
                or self.sp0 % SECTOR:
            raise V88Error("first super-packet at %d, %d sectors, largest %d"
                           % (self.sp0, self.sp0n, self.spmax))
        if self.nkeys and (self.ktab % SECTOR or
                           self.ktab + 16 * self.nkeys > len(d)):
            raise V88Error("the keyframe table at %d does not fit" % self.ktab)
        if self.poster != 0xFFFF and self.poster >= self.nkeys:
            raise V88Error("poster %d of %d keyframes"
                           % (self.poster, self.nkeys))
        self.keys = [struct.unpack_from("<IIHIBB", d, self.ktab + 16 * i)
                     for i in range(self.nkeys)]

    @property
    def fps(self):
        return self.rate / self.spf

    def records(self, at=None, nsec=None, skip=0):
        """(frame record bytes, super-packet offset, index) for every frame
        from super-packet `at` onward, following the chain."""
        at = self.sp0 if at is None else at
        nsec = self.sp0n if nsec is None else nsec
        while nsec:
            if not 1 <= nsec <= SP_MAX:
                raise V88Error("a super-packet of %d sectors" % nsec)
            sp = self.d[at:at + nsec * SECTOR]
            if len(sp) != nsec * SECTOR:
                raise V88Error("the super-packet at %d runs off the file" % at)
            nf, nxt = struct.unpack_from("<HH", sp, 0)
            if nf < 1:
                raise V88Error("the super-packet at %d holds no frames" % at)
            o = 4
            for i in range(nf):
                if o + REC_HDR > len(sp):
                    raise V88Error("record %d of the super-packet at %d runs "
                                   "off it" % (i, at))
                n = struct.unpack_from("<H", sp, o)[0]
                if n < REC_HDR + 1 + self.abytes or o + n > len(sp):
                    raise V88Error("record %d of the super-packet at %d says "
                                   "%d bytes" % (i, at, n))
                if i >= skip:
                    yield sp[o:o + n], at, i
                o += n
            if any(sp[o:]):
                raise V88Error("the super-packet at %d does not end in padding"
                               % at)
            skip = 0
            at, nsec = at + nsec * SECTOR, nxt

    def apply(self, surf, rec, key=False, check=True):
        """Decode one record onto `surf`; with `check`, enforce the WRITER's
        rules too (SPEC.md 98.1.3): canvas-only, no byte written twice,
        rows inside y0..y1, audio exact."""
        g = self.g
        n, y0, y1 = struct.unpack_from("<HHH", rec, 0)
        seens = [bytearray(65536) for _ in range(g.planes)]
        wrote = [0]
        plane = [0]

        def write(k, di, m):
            seen = seens[plane[0]]
            if not all(g.valid[di:di + m]):
                raise V88Error("a write at %04x+%d leaves the canvas" % (di, m))
            for a in (di, di + m - 1):
                if not y0 <= g.rowof[a] < y1:
                    raise V88Error("a write on row %d is outside the band "
                                   "%d..%d" % (g.rowof[a], y0, y1))
            if any(seen[di:di + m]):
                raise V88Error("two writes overlap at %04x" % di)
            seen[di:di + m] = b"\x01" * m
            wrote[0] += m
        if g.planes == 1:
            end = walk_lists(surf, rec, REC_HDR, write if check else None)
        else:                       # 98.1.3.1: a Map Mask, then its lists
            si, mv = REC_HDR, memoryview(surf)
            while True:
                if si >= len(rec):
                    raise V88Error("the sub-records run off their record")
                mask = rec[si]
                si += 1
                if not mask:
                    break
                if mask > 15:
                    raise V88Error("a Map Mask of %02x" % mask)
                for p in range(4):
                    if mask >> p & 1:
                        plane[0] = p
                        end = walk_lists(mv[p * PLANE:(p + 1) * PLANE], rec,
                                         si, write if check else None)
                si = end
            end = si
        tail = len(rec) - end
        want = (1 if self.audio == AUD_ADPCM4 else 0) if key else self.abytes
        if tail != want:
            raise V88Error("%d bytes follow the lists, not %d" % (tail, want))
        if check and not wrote[0] and y0 != y1:
            raise V88Error("an empty record with a band %d..%d" % (y0, y1))
        return rec[end:]

    def key(self, i):
        k, off, n, spo, spn, idx = self.keys[i]
        rec = self.d[off:off + n]
        if len(rec) != n or n < REC_HDR + 10:
            raise V88Error("keyframe %d runs off the file" % i)
        return k, rec, spo, spn, idx


def cycles_of(rec, planar=False):
    """The wave 0 model's cycles for one record, writing CGA's screen: the
    frame's fixed cost, a set-up per skip segment, each entry by its list,
    and an absolute entry's extra address. A MODEX record's sub-records
    are decoded once each whatever their mask, and pay an OUT"""
    c = [CYC_FRAME]

    def write(k, di, m):
        c[0] += CYC_ABS if mode[0] else 0
        if k <= L_P6:
            c[0] += CYC_P[k]
        elif k in (L_SLICE, L_SLICEL):
            c[0] += CYC_SLICE[0] + CYC_SLICE[1] * m
        else:
            c[0] += CYC_RUN[0] + CYC_RUN[1] * m

    def seg(absolute):
        c[0] += 0 if absolute else CYC_SEG
        mode[0] = absolute
    mode = [False]
    if not planar:
        walk_lists(bytearray(65536), rec, REC_HDR, write, seg)
        return c[0]
    si = REC_HDR
    while rec[si]:
        c[0] += CYC_SUB
        si = walk_lists(bytearray(65536), rec, si + 1, write, seg)
    return c[0]


# --------------------------------------------------------------------------
# frames in, pictures out
# --------------------------------------------------------------------------
def _tokens(d, n):
    """The first `n` whitespace-separated header tokens of a PNM, skipping
    comments; and the offset just past the one whitespace after the last."""
    out, i = [], 2
    while len(out) < n:
        while d[i:i + 1].isspace():
            i += 1
        if d[i:i + 1] == b"#":
            while d[i:i + 1] not in (b"\n", b""):
                i += 1
            continue
        j = i
        while not d[j:j + 1].isspace():
            j += 1
        out.append(int(d[i:j]))
        i = j
    return out, i + 1


def read_frame(path):
    """(width px, height, 1bpp rows packed MSB first, 1 = WHITE) from a PBM
    (P4 or P1), a PGM (P5, >= 128 is white) or an uncompressed BMP of 1, 8
    or 24 bits (luminance >= 128 is white). The frames are expected to be
    dithered already; this only thresholds."""
    d = open(path, "rb").read()
    lum = None
    if d[:2] in (b"P4", b"P1"):
        (w, h), o = _tokens(d, 2)
        if d[:2] == b"P4":
            rb = (w + 7) // 8
            px = [255 * (1 - ((d[o + y * rb + x // 8] >> (7 - x % 8)) & 1))
                  for y in range(h) for x in range(w)]
        else:
            bits = [c for c in d[o:] if c in b"01"]
            px = [255 * (1 - (c - 48)) for c in bits[:w * h]]
        lum = px
    elif d[:2] == b"P5":
        (w, h, mx), o = _tokens(d, 3)
        lum = [v * 255 // mx for v in d[o:o + w * h]]
    elif d[:2] == b"BM":
        off, = struct.unpack_from("<I", d, 10)
        w, h, planes, bpp, comp = struct.unpack_from("<iiHHI", d, 18)
        if comp not in (0, 3) or bpp not in (1, 8, 24):
            raise V88Error("%s: a %d-bit BMP (compression %d)"
                           % (path, bpp, comp))
        hsz, = struct.unpack_from("<I", d, 14)
        pal = d[14 + hsz:off]
        top = h < 0
        h = abs(h)
        stride = (w * bpp + 31) // 32 * 4
        lum = []
        for y in range(h):
            r = d[off + (y if top else h - 1 - y) * stride:][:stride]
            for x in range(w):
                if bpp == 24:
                    b_, g_, r_ = r[3 * x:3 * x + 3]
                else:
                    i = (r[x // 8] >> (7 - x % 8)) & 1 if bpp == 1 else r[x]
                    b_, g_, r_ = pal[4 * i:4 * i + 3]
                lum.append((r_ * 299 + g_ * 587 + b_ * 114) // 1000)
    else:
        raise V88Error("%s: not a PBM, PGM or BMP" % path)
    if len(lum) != w * h:
        raise V88Error("%s: %d pixels for %d x %d" % (path, len(lum), w, h))
    rows = bytearray()
    for y in range(h):
        for x0 in range(0, w, 8):
            b = 0
            for x in range(x0, x0 + 8):
                b = b << 1 | (x < w and lum[y * w + x] >= 128)
            rows.append(b)
    return w, h, bytes(rows)


def read_wav(path):
    """(rate, unsigned 8-bit mono samples) from a PCM WAV of 8 or 16 bits,
    mono or stereo (the channels are averaged)."""
    d = open(path, "rb").read()
    if d[:4] != b"RIFF" or d[8:12] != b"WAVE":
        raise V88Error("%s: not a WAV" % path)
    i, fmt, data = 12, None, None
    while i + 8 <= len(d):
        cid, n = d[i:i + 4], struct.unpack_from("<I", d, i + 4)[0]
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", d, i + 8)
        elif cid == b"data":
            data = d[i + 8:i + 8 + n]
        i += 8 + n + (n & 1)
    if not fmt or data is None or fmt[0] != 1 or fmt[5] not in (8, 16) \
            or fmt[1] not in (1, 2):
        raise V88Error("%s: only PCM, 8 or 16 bits, mono or stereo" % path)
    ch, rate, bits = fmt[1], fmt[2], fmt[5]
    if bits == 8:
        s = list(data)
    else:
        s = [((v + 32768) >> 8) for v in
             struct.unpack("<%dh" % (len(data) // 2), data[:len(data) & ~1])]
    if ch == 2:
        s = [(s[j] + s[j + 1]) // 2 for j in range(0, len(s) - 1, 2)]
    return rate, bytes(s)


def write_png(path, wb, h, cv):
    """A 1-bit greyscale PNG of a canvas, 1 = white - MONO1's own polarity,
    so the rows go in as they are."""
    import zlib

    def chunk(t, b):
        c = t + b
        return struct.pack(">I", len(b)) + c + \
            struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    raw = b"".join(b"\0" + cv[y * wb:(y + 1) * wb] for y in range(h))
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" +
                chunk(b"IHDR", struct.pack(">IIBBBBB", wb * 8, h, 1, 0, 0, 0,
                                           0)) +
                chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


# --------------------------------------------------------------------------
# the V88 commands
# --------------------------------------------------------------------------
def import_xdv(src, out, target="cga", title=None, keysecs=KEY_SECS,
               poster=None, audio_fmt=AUD_PCM8):
    """SPEC.md 98.2's import. On CGA the XDV's own writes become the lists
    (clipped to the canvas, which changes no pixel). On another layout the
    stream is simulated and each frame re-encoded from the bytes it
    changed."""
    hdr, pk = read_xdv(src)
    layout = LAYOUT_BY_NAME[target]
    g = Geom(layout, ROWB, 200)
    cga = Geom(LAY_CGA, ROWB, 200) if layout != LAY_CGA else g
    pix = PF_CGACOMP if hdr["mode"] == 1 else PF_MONO1
    keyint = max(1, round(keysecs * hdr["rate"] / hdr["achunk"]))
    chunks = audio_chunks(b"".join(xdc_audio(p, hdr) for p in pk), len(pk),
                          hdr["achunk"], audio_fmt,
                          key_frames(len(pk), keyint))
    w = Writer(g, hdr["rate"], hdr["achunk"], audio_fmt, len(chunks[0]), pix,
               title=title or os.path.splitext(os.path.basename(src))[0],
               credits="imported from XDC (MobyGamer's XDC, MIT)",
               aspect=ASPECT[LAY_CGA], keysecs=keysecs)
    xs = bytearray(65536)
    ts = bytearray(65536) if layout != LAY_CGA else xs
    for i, p in enumerate(pk):
        ops, code = xdc_ops(p, "%s packet %d" % (os.path.basename(src), i))
        audio = chunks[i]
        if layout == LAY_CGA:
            ops = clip_ops(ops, g)
            apply_ops(xs, ops)
        else:
            changed = set()
            for a, bs, run in ops:
                for j, v in enumerate(bs):
                    ca = a + j
                    if not cga.valid[ca]:
                        continue
                    xs[ca] = v
                    y = cga.rowof[ca]
                    ta = g.base[y] + (ca - cga.base[y])
                    if ts[ta] != v:
                        ts[ta] = v
                        changed.add(ta)
            ops = spans(changed, ts, g)
        w.frame(ops, ts, audio)
    return w.write(out, poster)


def xdc_audio(p, hdr):
    """A packet's audio: XDC puts its `achunk` bytes at the very END of the
    packet, after the code, the data and the padding."""
    return bytes(p[len(p) - hdr["achunk"]:])


# --- ADPCM4 (SPEC.md 98.1.1): Creative's 4-bit ADPCM as a DSP 2.00 plays it
# with DSP 7Dh - the reference byte first, then two samples a byte, high
# nibble first. The tables are DOSBox's (decode_ADPCM_4_sample), and
# MartyPC's card (tools/martypc/patches/06) decodes with the same ones, so
# what is encoded here is what that card plays, sample for sample.
ADPCM4_SCALE = (
    0, 1, 2, 3, 4, 5, 6, 7, 0, -1, -2, -3, -4, -5, -6, -7,
    1, 3, 5, 7, 9, 11, 13, 15, -1, -3, -5, -7, -9, -11, -13, -15,
    2, 6, 10, 14, 18, 22, 26, 30, -2, -6, -10, -14, -18, -22, -26, -30,
    4, 12, 20, 28, 36, 44, 52, 60, -4, -12, -20, -28, -36, -44, -52, -60)
ADPCM4_ADJUST = (
    0, 0, 0, 0, 0, 16, 16, 16, 0, 0, 0, 0, 0, 16, 16, 16,
    -16, 0, 0, 0, 0, 16, 16, 16, -16, 0, 0, 0, 0, 16, 16, 16,
    -16, 0, 0, 0, 0, 16, 16, 16, -16, 0, 0, 0, 0, 16, 16, 16,
    -16, 0, 0, 0, 0, 0, 0, 0, -16, 0, 0, 0, 0, 0, 0, 0)


def _adpcm4_step(ref, scale, nib):
    i = min(63, max(0, nib + scale))
    return (min(255, max(0, ref + ADPCM4_SCALE[i])),
            min(48, max(0, scale + ADPCM4_ADJUST[i])))


def adpcm4_decode(data, ref=ADPCM4_REF, scale=0):
    """ADPCM4 bytes -> PCM8, the card's way"""
    out = bytearray()
    for b in data:
        for nib in (b >> 4, b & 15):
            ref, scale = _adpcm4_step(ref, scale, nib)
            out.append(ref)
    return bytes(out)


def adpcm4_encode(pcm, ref=ADPCM4_REF, scale=0, zeros=()):
    """PCM8 (an even count) -> ADPCM4, greedily: each nibble the one whose
    decoded sample is nearest, against the decoder's own state.

    `zeros` are sample indexes where the decoder must ARRIVE with its scale
    at 0 - a keyframe's frame k+1 (SPEC.md 98.1.1.1). The scale moves in
    steps of 16 and a zero-step nibble lowers it one, so the three samples
    before one are chosen only among nibbles that get it there: a card
    started at that byte with its reference is then in exactly the state the
    continuous stream is, and a seek plays the file's own sound."""
    if len(pcm) % 2:
        raise V88Error("ADPCM4 packs two samples a byte; %d is odd"
                       % len(pcm))
    zs = sorted(z for z in zeros if 0 < z <= len(pcm))
    left = {}                       # sample index -> steps to a zero
    for z in zs:
        for d in (1, 2, 3):
            if z - d >= 0:
                left[z - d] = min(left.get(z - d, d), d)
    out = bytearray()
    hi = None
    for j, x in enumerate(pcm):
        best = None
        cap = 16 * (left[j] - 1) if j in left else 48
        for nib in range(16):
            r2, s2 = _adpcm4_step(ref, scale, nib)
            if s2 > cap:
                continue
            e = abs(r2 - x)
            if best is None or e < best[0]:
                best = (e, nib, r2, s2)
        _, nib, ref, scale = best
        if hi is None:
            hi = nib
        else:
            out.append(hi << 4 | nib)
            hi = None
    return bytes(out)


_A4 = {}


def _adpcm4_tables():
    """The trellis's fixed tables, once: for each arriving scale q, the
    (scale, nibble, step) pairs that land there, as gather indexes into the
    1,024 states (sample r + 256 x scale/16) with 1,024 an INF sentinel"""
    if _A4:
        return _A4
    import numpy as np
    groups = [[] for _ in range(4)]
    for p in range(4):
        for nib in range(16):
            i = min(63, nib + 16 * p)
            q = min(3, max(0, p + ADPCM4_ADJUST[i] // 16))
            groups[q].append((p, nib, ADPCM4_SCALE[i]))
    G = max(len(g) for g in groups)
    r = np.arange(256)
    idx = np.full((4, G, 256), 1024, np.int64)
    nibt = np.zeros((4, G), np.uint8)
    for q, g in enumerate(groups):
        for j, (p, nib, d) in enumerate(g):
            src = r - d
            v = (src >= 0) & (src < 256)
            idx[q, j] = np.where(v, p * 256 + np.clip(src, 0, 255), 1024)
            nibt[q, j] = nib
    _A4.update(idx=idx, nibt=nibt,
               gidx=np.ascontiguousarray(idx.transpose(0, 2, 1)),
               sq=((r[None, :] - r[:, None]) ** 2).astype(np.int32))
    return _A4


def _adpcm4_viterbi(pcm, start, zeros, chunk=2048):
    """(nibbles, states) for PCM8 `pcm`: the least-squared-error path, from
    the state `start` (sample + 256 x scale/16), or from ANY state when it
    is None. states[k] is the decoder's state after sample k. A decision is
    committed where every live state's survivor agrees, so the memory is a
    window and not the stream."""
    import numpy as np
    T = _adpcm4_tables()
    idx, nibt, gidx, sq = T["idx"], T["nibt"], T["gidx"], T["sq"]
    x = np.frombuffer(bytes(pcm), np.uint8).astype(np.int64)
    n = len(x)
    cap = np.full(n, 3, np.int64)
    for z in zeros:
        for d in (1, 2, 3):
            if 0 <= z - d < n:
                cap[z - d] = min(cap[z - d], d - 1)
    INF = np.int32(1) << 28
    cost = np.full(1025, INF, np.int32)
    if start is None:
        cost[:1024] = 0
    else:
        cost[start] = 0
    nibs = np.zeros(n, np.uint8)
    states = np.zeros(n, np.int32)
    win = [0, []]                   # the window's first sample, backpointers

    def trace(t, S, all_agree):
        w0, bp = win
        path = None if all_agree else t
        for k in range(t - 1, w0 - 1, -1):
            j = bp[k - w0][S]
            q, rr = S // 256, S % 256
            if path is None and np.all(S == S[0]):
                path = k + 1
            if path is not None:
                if len(S) > 1:
                    S, j, q, rr = S[:1], j[:1], q[:1], rr[:1]
                nibs[k] = nibt[q[0], j[0]]
                states[k] = S[0]
            S = idx[q, j, rr]
        return path

    for t in range(n):
        cand = cost[gidx]                           # (4, 256, G)
        j = cand.argmin(axis=2)
        best = cand.min(axis=2)
        best += sq[x[t]]
        if cap[t] < 3:
            best[cap[t] + 1:, :] = INF
        dead = best >= INF
        best -= best.min()
        best[dead] = INF            # renormalised, and the dead stay dead
        cost[:1024] = best.reshape(1024)
        win[1].append(j.reshape(1024).astype(np.uint8))
        if len(win[1]) >= chunk:
            live = np.nonzero(cost[:1024] < INF)[0]
            path = trace(t + 1, live, True)
            if path is not None:    # decided before `path`: drop it
                win[1] = win[1][path - win[0]:]
                win[0] = path
    trace(n, np.array([int(cost[:1024].argmin())]), False)
    return nibs, states


def _adpcm4_seg(args):
    return _adpcm4_viterbi(*args)


def adpcm4_search(pcm, ref=ADPCM4_REF, scale=0, zeros=(), jobs=1,
                  seg=88200, lead=4096):
    """PCM8 -> ADPCM4 by EXACT SEARCH (Viterbi): the nibble sequence whose
    decode has the least total squared error, where adpcm4_encode picks
    each nibble for its own sample alone. The decoder has 1,024 states - a
    sample and a scale of 0, 16, 32 or 48 - so the trellis is a numpy step
    a sample. MEASURED on 12 s of Bad Apple's sound: 27.3 dB against the
    greedy encoder's 19.9. `zeros` as adpcm4_encode's.

    ON `jobs` CORES the stream is cut into segments, and each is searched
    from `lead` samples BEFORE its cut, starting from any state: survivors
    merge within tens of samples, so over the lead its path becomes the one
    the whole search would have taken. The two are stitched at the latest
    sample where their STATES agree - the prefix is the best way into that
    state and the rest the best way on from it, which is the whole search's
    path through it - and a segment whose lead never meets the one before
    it is searched again from where that one ended. A step that would
    CLAMP at 0 or 255 is a second route into an edge state and is not
    taken; every stream written decodes by the card's arithmetic."""
    if len(pcm) % 2:
        raise V88Error("ADPCM4 packs two samples a byte; %d is odd"
                       % len(pcm))
    n = len(pcm)
    s0 = (scale // 16) * 256 + ref
    if jobs <= 1 or n <= 2 * seg:
        nibs, _ = _adpcm4_viterbi(pcm, s0, zeros)
    else:
        import multiprocessing
        import numpy as np
        cuts = list(range(seg, n, seg))
        bounds = [0] + cuts + [n]
        work = []
        for i in range(len(bounds) - 1):
            a = bounds[i] - (lead if i else 0)
            b = bounds[i + 1]
            work.append((bytes(pcm[a:b]), None if i else s0,
                         [z - a for z in zeros if a < z <= b]))
        with multiprocessing.Pool(jobs) as pool:
            parts = pool.map(_adpcm4_seg, work)
        nibs = np.zeros(n, np.uint8)
        states = np.zeros(n, np.int32)
        nibs[:bounds[1]], states[:bounds[1]] = parts[0]
        for i in range(1, len(bounds) - 1):
            a, c, b = bounds[i] - lead, bounds[i], bounds[i + 1]
            pn, ps = parts[i]
            m = None                # the latest sample both agree after
            for k in range(c - 1, a - 1, -1):
                if states[k] == ps[k - a]:
                    m = k
                    break
            if m is None:           # never met: on from where it really is
                rn, rs = _adpcm4_viterbi(
                    pcm[c:b], int(states[c - 1]),
                    [z - c for z in zeros if c < z <= b])
                nibs[c:b], states[c:b] = rn, rs
            else:
                nibs[m + 1:b] = pn[m + 1 - a:]
                states[m + 1:b] = ps[m + 1 - a:]
    out = bytes((int(nibs[i]) << 4) | int(nibs[i + 1])
                for i in range(0, n, 2))
    st = adpcm4_trace(out, ref, scale)
    for z in zeros:
        if 0 < z <= n and z % 2 == 0 and st[z // 2][1]:
            raise V88Error("adpcm4_search: the scale is %d at sample %d"
                           % (st[z // 2][1], z))
    return out


def adpcm4_trace(data, ref=ADPCM4_REF, scale=0):
    """The decoder's (sample, scale) before each byte of `data`, and after
    the last: [i] is the state a card started at byte i must be in"""
    st = [(ref, scale)]
    for b in data:
        for nib in (b >> 4, b & 15):
            ref, scale = _adpcm4_step(ref, scale, nib)
        st.append((ref, scale))
    return st


def key_frames(nf, keyint):
    """The frames keyframes are written after (98.1.3): every keyint-th"""
    return list(range(0, nf, keyint))


def audio_chunks(pcm, nf, spf, afmt, keys=(), search=0):
    """A stream's PCM8 cut into the frames' audio parts in format afmt: PCM8
    a sample a byte, or ADPCM4 encoded ONCE across the whole stream - its
    state runs on from frame to frame, the reference byte being the
    player's (SPEC.md 98.1.1) - with the scale steered to 0 at frame k+1 of
    every keyframe k in `keys`, where a seek starts the card afresh"""
    pcm = bytes(pcm[:nf * spf]) + b"\x80" * max(0, nf * spf - len(pcm))
    if afmt == AUD_ADPCM4:
        if spf % 2:
            raise V88Error("ADPCM4 needs an even number of samples a frame, "
                           "and this stream has %d" % spf)
        zs = [(k + 1) * spf for k in keys]
        # `search`: 0 the greedy encoder, n > 0 the exact search on n cores
        data = adpcm4_search(pcm, zeros=zs, jobs=search) if search \
            else adpcm4_encode(pcm, zeros=zs)
        n = spf // 2
    else:
        data, n = pcm, spf
    return [data[f * n:(f + 1) * n] for f in range(nf)]


def encode_frames(paths, out, fps, wav=None, layout="cga", title="",
                  keysecs=KEY_SECS, poster=None, audio_fmt=AUD_PCM8):
    """SPEC.md 98.2's minimal encoder: every changed byte, losslessly."""
    lay = LAYOUT_BY_NAME[layout]
    w0, h0, _ = read_frame(paths[0])
    if w0 % 8:
        raise V88Error("%s: %d pixels wide; a MONO1 canvas is whole bytes"
                       % (paths[0], w0))
    g = Geom(lay, w0 // 8, h0)
    if wav:
        rate, samples = read_wav(wav)
        spf = max(1, round(rate / fps))
        afmt, abytes = audio_fmt, spf
        if afmt == AUD_ADPCM4:
            spf += spf % 2              # two samples a byte: the frame rate
            abytes = spf // 2           # moves by a hair to keep it even
        chunks = audio_chunks(samples, len(paths), spf, afmt, key_frames(
            len(paths), max(1, round(keysecs * rate / spf))))
    else:
        rate, spf, afmt, abytes = max(1, round(fps * 100)), 100, AUD_NONE, 0
        samples = b""
    if rate > 65535:
        raise V88Error("a %d Hz rate does not fit the header" % rate)
    wr = Writer(g, rate, spf, afmt, abytes, PF_MONO1, title=title,
                keysecs=keysecs)
    surf = bytearray(65536)
    for f, path in enumerate(paths):
        w, h, cv = read_frame(path)
        if (w, h) != (w0, h0):
            raise V88Error("%s is %d x %d; the first frame was %d x %d"
                           % (path, w, h, w0, h0))
        changed = []
        for y, b in enumerate(g.base):
            row = cv[y * g.wb:(y + 1) * g.wb]
            if row == surf[b:b + g.wb]:
                continue
            for x in range(g.wb):
                if surf[b + x] != row[x]:
                    changed.append(b + x)
            surf[b:b + g.wb] = row
        wr.frame(spans(changed, surf, g), surf, chunks[f] if abytes else b"")
    return wr.write(out, poster)


def encode_canvases(canvases, g, out, fps, pixfmt=PF_MONO1, palette=None,
                    title="", keysecs=KEY_SECS, poster=None):
    """encode_frames for canvases already in hand (bytes, g.wb a row) - the
    only way to make a VGA8 file without a video (SPEC.md 98.2): silent,
    every changed byte"""
    rate, spf = max(1, round(fps * 100)), 100
    wr = Writer(g, rate, spf, AUD_NONE, 0, pixfmt, title=title,
                keysecs=keysecs, palette=palette)
    surf = g.surface()
    prev = g.canvas(surf)
    for cv in canvases:
        if g.planes > 1:
            subs = modex_subs(cv, [a != b for a, b in zip(cv, prev)], g)
            g.put(surf, cv)
            prev = cv
            wr.frame(subs, surf)
            continue
        changed = []
        for y, b in enumerate(g.base):
            row = cv[y * g.wb:(y + 1) * g.wb]
            if row == surf[b:b + g.wb]:
                continue
            for x in range(g.wb):
                if surf[b + x] != row[x]:
                    changed.append(b + x)
            surf[b:b + g.wb] = row
        wr.frame(spans(changed, surf, g), surf)
    return wr.write(out, poster)


def v88_frames(r, check=True):
    """(frame, surface after it) for every frame of the stream, checking
    each record; and the stream's own totals against the header's."""
    surf = r.g.surface()
    f = 0
    for rec, at, i in r.records():
        r.apply(surf, rec, check=check)
        yield f, surf, rec, at, i
        f += 1
    if f != r.frames:
        raise V88Error("the stream holds %d frames; the header says %d"
                       % (f, r.frames))


def cmd_import(a):
    s = import_xdv(a.src, a.out, a.target, a.title, a.keysecs, a.poster,
                   AUD_BY_NAME[a.audio])
    print("os88vid: %s -> %s: %d bytes, %d super-packets, %d keyframes "
          "(%.1f%% of the file), poster %d"
          % (a.src, a.out, s["bytes"], s["sps"], s["keys"],
             100.0 * s["keybytes"] / s["bytes"], s["poster"]))


def cmd_encode(a):
    s = encode_frames(a.frames, a.out, a.fps, a.wav, a.layout, a.title,
                      a.keysecs, a.poster, AUD_BY_NAME[a.audio])
    print("os88vid: %d frames -> %s: %d bytes, %d keyframes (%.1f%%)"
          % (len(a.frames), a.out, s["bytes"], s["keys"],
             100.0 * s["keybytes"] / s["bytes"]))


def cmd_info(a):
    for path in a.files:
        r = Reader(path)
        g = r.g
        secs = r.frames / r.fps
        cyc = [cycles_of(rec, r.g.planes > 1) for rec, at, i in r.records()]
        period = HZ / r.fps
        print("%s: '%s'" % (path, r.title))
        if r.credits:
            print("   credits: %s" % r.credits)
        print("   %d frames at %.3f fps (%d Hz / %d), %.1f s; audio %s; "
              "PIT %d x %d" % (r.frames, r.fps, r.rate, r.spf, secs,
                               {0: "none", 1: "PCM8", 2: "ADPCM4"}[r.audio],
                              r.pitdiv,
                               r.pitper))
        print("   canvas %d x %d on %s, %s, aspect %d:%d"
              % (g.wb * PIX_PER_BYTE[g.layout], g.h, g.name,
                 PF_NAMES[r.pixfmt], *r.aspect))
        print("   stream %d bytes = %.1f KB/s; largest super-packet %d "
              "sectors, largest record %d"
              % (r.slen, r.slen / 1024.0 / secs, r.spmax, r.rmax))
        print("   %d keyframes, poster %s; front matter %d bytes"
              % (r.nkeys, r.poster if r.poster != 0xFFFF else "none", r.sp0))
        print("   CPU (wave 0 model, CGA screen): mean %.1f%%, worst %.1f%% "
              "(frame %d)" % (100 * sum(cyc) / len(cyc) / period,
                              100 * max(cyc) / period, cyc.index(max(cyc))))


def decode_at(r, n):
    """The canvas after frame `n`, through the keyframe at or before it."""
    if not 0 <= n < r.frames:
        raise V88Error("frame %d of %d" % (n, r.frames))
    surf = r.g.surface()
    at = nsec = None
    f, skip = 0, 0
    best = [i for i, e in enumerate(r.keys) if e[0] <= n]
    if best:
        k, rec, spo, spn, idx = r.key(best[-1])
        r.apply(surf, rec, key=True)
        if k == n:
            return r.g.canvas(surf)
        at, nsec, f, skip = spo, spn, k + 1, idx
    for rec, _, _ in r.records(at, nsec, skip):
        r.apply(surf, rec)
        if f == n:
            return r.g.canvas(surf)
        f += 1
    raise V88Error("the stream ended before frame %d" % n)


# THE POSTER (SPEC.md 98.4): the Preview shows a keyframe at the scale the
# window's layout chose (98.4.1) - the canvas itself, or halved 2x2 into 1,
# each output pixel lit when its four source pixels hold MORE lit ones than
# its threshold (2x2 ordered dither, by output row and column parity), so a
# grey stays grey and a one-pixel line survives; or that halved again.
THUMB_T = ((0, 2), (3, 1))


def thumb_half(cv, wb, h):
    """(bytes, wb, h) of the canvas `cv` halved - apps/video/video.asm's
    vp_half, bit for bit. An odd last row pairs with itself; an odd last
    byte's missing partner is black."""
    owb, oh = (wb + 1) // 2, (h + 1) // 2
    out = bytearray(owb * oh)
    for y in range(oh):
        up = cv[2 * y * wb:(2 * y + 1) * wb]
        lo = cv[(2 * y + 1) * wb:(2 * y + 2) * wb] if 2 * y + 1 < h else up
        t = THUMB_T[y & 1]
        for j in range(owb):
            v = 0
            for s in (0, 1):
                a = up[2 * j + s] if 2 * j + s < wb else 0
                b = lo[2 * j + s] if 2 * j + s < wb else 0
                for p in range(4):
                    sh = 6 - 2 * p
                    n = bin((a >> sh) & 3).count("1") + \
                        bin((b >> sh) & 3).count("1")
                    if n > t[p & 1]:
                        v |= 0x80 >> (4 * s + p)
            out[y * owb + j] = v
    return bytes(out), owb, oh


def poster(cv, wb, h, scale=2):
    """(bytes, bytes a row, width in pixels, rows) of the picture the
    Preview's box shows for canvas `cv` at `scale` 1, 2 or 4 (SPEC.md 98.4)"""
    if scale == 1:
        return bytes(cv), wb, wb * 8, h
    img, bw, bh = thumb_half(cv, wb, h)
    if scale == 4:
        img, bw, bh = thumb_half(img, bw, bh)
    return img, bw, wb * 8 // scale, bh


def cmd_decode(a):
    r = Reader(a.file)
    cv = decode_at(r, a.frame)
    write_png(a.png, r.g.wb, r.g.h, cv)
    print("os88vid: frame %d of %s -> %s" % (a.frame, a.file, a.png))


def verify_v88(path, against=None):
    """Everything SPEC.md 98.1.6 lets a reader check, and every writer's
    rule of 98.1.3, over the whole file. Returns the frame count."""
    r = Reader(path)
    g = r.g
    ref = None
    if against:
        hdr, pk = read_xdv(against)
        if len(pk) != r.frames:
            raise V88Error("%s has %d frames, %s %d" % (against, len(pk),
                                                       path, r.frames))
        ref = (hdr, pk, bytearray(65536), Geom(LAY_CGA, ROWB, 200))
        want_audio = audio_chunks(b"".join(xdc_audio(p, hdr) for p in pk),
                                  len(pk), hdr["achunk"], r.audio,
                                  [e[0] for e in r.keys]) \
            if r.audio == AUD_ADPCM4 else None
    ks = [e[0] for e in r.keys]
    if ks != sorted(set(ks)) or (ks and ks[-1] >= r.frames):
        raise V88Error("the keyframe table is not ascending frames of the "
                       "stream")
    kat = {k: i for i, k in enumerate(ks)}
    pos, rmax, kmax = {}, 0, 0
    for f, surf, rec, at, i in v88_frames(r):
        pos[f] = (at, i)
        rmax = max(rmax, len(rec))
        if ref:
            hdr, pk, xs, cga = ref
            ops, code = xdc_ops(pk[f], "%s packet %d" % (against, f))
            apply_ops(xs, ops)
            if cga.canvas(xs) != g.canvas(surf):
                raise V88Error("frame %d differs from XDC's screen" % f)
            if rec[len(rec) - r.abytes:] != (want_audio[f] if want_audio
                                             else xdc_audio(pk[f], hdr)):
                raise V88Error("frame %d's audio differs from XDC's" % f)
        if f in kat:
            k, krec, spo, spk, idx = r.key(kat[f])
            kmax = max(kmax, len(krec))
            kb = g.surface()
            r.apply(kb, krec, key=True)
            if g.canvas(kb) != g.canvas(surf):
                raise V88Error("keyframe %d is not the screen after frame %d"
                               % (kat[f], f))
    sp_secs = {}
    at, n = r.sp0, r.sp0n
    while n:
        sp_secs[at] = n
        at, n = at + n * SECTOR, struct.unpack_from("<H", r.d, at + 2)[0]
    if at - r.sp0 != r.slen or max(sp_secs.values()) != r.spmax:
        raise V88Error("the stream is %d bytes, largest %d sectors; the "
                       "header says %d and %d" % (at - r.sp0,
                                                 max(sp_secs.values()),
                                                 r.slen, r.spmax))
    for k, off, n, spo, spk, idx in r.keys:
        want = (pos[k + 1] + (sp_secs[pos[k + 1][0]],)) \
            if k + 1 < r.frames else (0, 0, 0)
        if (spo, idx, spk) != want:
            raise V88Error("keyframe after frame %d names super-packet %d "
                           "record %d (%d sectors); the stream says %s"
                           % (k, spo, idx, spk, want))
    if r.audio == AUD_ADPCM4 and r.keys:
        # 98.1.1.1: each keyframe's reference byte is the sample the decoder
        # holds at frame k+1, with its scale 0 - so a card started there with
        # it plays exactly what the continuous stream plays
        st = adpcm4_trace(b"".join(rec[len(rec) - r.abytes:]
                                   for rec, _, _ in r.records()))
        for i, (k, off, n, spo, spk, idx) in enumerate(r.keys):
            want = st[(k + 1) * r.abytes]
            if (r.d[off + n - 1], 0) != want:
                raise V88Error("keyframe %d's ADPCM4 reference is %d; the "
                               "stream holds %d at scale %d there"
                               % (i, r.d[off + n - 1], want[0], want[1]))
    if (rmax, kmax) != (r.rmax, r.kmax):
        raise V88Error("the largest record and keyframe are %d and %d bytes; "
                       "the header says %d and %d" % (rmax, kmax, r.rmax,
                                                     r.kmax))
    return r.frames


def cmd_verify(a):
    bad = 0
    for path in a.files:
        if path.upper().endswith(".XDV"):
            bad |= verify_xdv(path)
            continue
        try:
            n = verify_v88(path, a.against)
            print("%s: %d frames verified%s" % (
                path, n, (", every one XDC's screen and audio exactly"
                          if a.against else "")))
        except V88Error as e:
            print("%s: FAIL - %s" % (path, e))
            bad = 1
    return bad


# --------------------------------------------------------------------------
# --selfcheck: generated fixtures, no samples needed
# --------------------------------------------------------------------------
def _fixture_canvases(wb, h, n, rnd):
    """`n` canvases that between them reach every list: a black start, a
    white fill (RUNL), noise (SLICEL), isolated bytes (absolute P1..P6),
    runs and slices of every short length, and a box that moves."""
    cv = bytearray(wb * h)
    out = []
    for f in range(n):
        kind = f % 8
        if kind == 1:
            cv = bytearray(b"\xff" * (wb * h))
        elif kind == 2:
            cv = bytearray(rnd.getrandbits(8) for _ in range(wb * h))
        elif kind == 3:
            for _ in range(40):
                a = rnd.randrange(wb * h - 6)
                m = rnd.randint(1, 6)
                cv[a:a + m] = bytes(rnd.getrandbits(8) for _ in range(m))
        elif kind == 4:
            for _ in range(12):
                a = rnd.randrange(wb * h - 300)
                m = rnd.choice((6, 7, 40, 255, 256, 300))
                cv[a:a + m] = bytes([rnd.getrandbits(8)]) * m
        elif kind == 5:
            for _ in range(12):
                a = rnd.randrange(wb * h - 300)
                m = rnd.choice((7, 16, 255, 256, 290))
                cv[a:a + m] = bytes(rnd.getrandbits(8) for _ in range(m))
        elif kind == 6:
            x, y = f % (wb - 4), (3 * f) % (h - 8)
            for r in range(8):
                cv[(y + r) * wb + x:(y + r) * wb + x + 4] = b"\x3c" * 4
        elif kind == 7:
            cv = bytearray(wb * h)
        out.append(bytes(cv))
    return out


def _write_pbm(path, wb, h, cv):
    with open(path, "wb") as f:
        f.write(b"P4\n%d %d\n" % (wb * 8, h) + bytes(255 - b for b in cv))


def _write_wav(path, rate, samples):
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(samples)) + b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, 1, rate, rate, 1, 8) +
                b"data" + struct.pack("<I", len(samples)) + samples)


def _write_xdv(path, frames_ops, rate, achunk, mode, rnd):
    """A synthetic XDC stream in XDC_GLOB.PAS's layout, from xdc_emit's
    packets, each with its audio in its last `achunk` bytes."""
    pks = []
    for ops in frames_ops:
        raw = xdc_emit(ops, pad=False)
        aud = bytes(rnd.getrandbits(8) for _ in range(achunk))
        size = -(-(len(raw) + achunk) // 512) * 512
        pks.append(raw + bytes(size - len(raw) - achunk) + aud)
    hdr = bytearray(512)
    hdr[0:4] = b"XDCV"
    struct.pack_into("<HHHHBBBB", hdr, 4, len(pks),
                     max(len(p) for p in pks), achunk, rate, mode, 80, 200, 0)
    with open(path, "wb") as f:
        f.write(hdr + b"".join(pks) + bytes(len(p) // 512 for p in pks))


def selfcheck():
    import random
    import tempfile
    rnd = random.Random(8088)
    fails = []

    def expect_fail(what, path, mutate, why):
        """`mutate` the file; verify must refuse it, and for `why`."""
        d = mutate(bytearray(open(path, "rb").read()))
        bad = path + ".bad"
        open(bad, "wb").write(d)
        try:
            verify_v88(bad)
        except (V88Error, XdvError) as e:
            if why not in str(e):
                fails.append("a %s was refused for another reason: %s"
                             % (what, e))
            return
        fails.append("a %s was not refused" % what)

    def swap_keys(d, r):
        """Two keyframes' records swapped in the table: both well formed,
        each the wrong picture."""
        recs = [r.key(i)[1] for i in range(r.nkeys)]
        i = next(i for i in range(r.nkeys - 1) if recs[i] != recs[i + 1])
        a, b = r.ktab + 16 * i + 4, r.ktab + 16 * (i + 1) + 4
        d[a:a + 6], d[b:b + 6] = d[b:b + 6], d[a:a + 6]
        return d

    with tempfile.TemporaryDirectory() as tmp:
        for lay, wb, h, wav in (("cga", 80, 200, True), ("cga", 40, 100, False),
                                ("herc", 50, 200, True),
                                ("lin80", 40, 240, False)):
            cvs = _fixture_canvases(wb, h, 24, rnd)
            paths = []
            for i, cv in enumerate(cvs):
                pth = os.path.join(tmp, "%s%d_%03d.pbm" % (lay, wb, i))
                _write_pbm(pth, wb, h, cv)
                paths.append(pth)
            wv = None
            if wav:
                wv = os.path.join(tmp, "a.wav")
                _write_wav(wv, 8000, bytes(rnd.getrandbits(8)
                                           for _ in range(8000)))
            out = os.path.join(tmp, "%s%d.v88" % (lay, wb))
            encode_frames(paths, out, 30.0, wv, lay, "selfcheck", 0.2)
            try:
                verify_v88(out)
                r = Reader(out)
                for f in range(len(cvs)):
                    if decode_at(r, f) != cvs[f]:
                        fails.append("%s %dx%d frame %d decodes wrong"
                                     % (lay, wb, h, f))
                if wav and r.frames * r.abytes and r.audio != AUD_PCM8:
                    fails.append("%s: the audio was dropped" % lay)
                if r.nkeys < 3:
                    fails.append("%s: %d keyframes" % (lay, r.nkeys))
            except V88Error as e:
                fails.append("%s %dx%d: %s" % (lay, wb, h, e))
            # corruptions verify must refuse
            r = Reader(out)
            rec0 = r.sp0 + 4
            expect_fail("record length past its super-packet", out,
                        lambda d: d[:rec0] + b"\xff\x7f" + d[rec0 + 2:],
                        "says 32767 bytes")
            expect_fail("truncated file", out, lambda d: d[:len(d) - 700],
                        "runs off the file")
            expect_fail("stale keyframe", out, lambda d: swap_keys(d, r),
                        "is not the screen after frame")
            if wb < LAYOUTS[LAYOUT_BY_NAME[lay]][1]:
                # keyframe 0's record rewritten as one absolute P1 entry,
                # aimed one byte past the canvas's first row
                def outside(d):
                    kr = r.keys[0]
                    body = struct.pack("<HHH", kr[2], 0, 1) + \
                        bytes([0x81]) + struct.pack("<H", wb) + b"\x55" + \
                        bytes(kr[2] - 10)
                    return d[:kr[1]] + body + d[kr[1] + len(body):]
                expect_fail("write outside the canvas", out, outside,
                            "leaves the canvas")
        # the importer, on a synthetic XDC stream
        ops = [ops for label, ops in synth_frames()]
        ops += [[(0, b"\xaa" * 16384, True)], [(100, b"\x0f" * 3, False)]]
        xdv = os.path.join(tmp, "SYN.XDV")
        _write_xdv(xdv, ops, 8040, 134, 2, rnd)
        for tgt in ("cga", "herc", "lin80"):
            out = os.path.join(tmp, "syn_%s.v88" % tgt)
            import_xdv(xdv, out, tgt, keysecs=0.1)
            try:
                verify_v88(out, xdv)
            except (V88Error, XdvError) as e:
                fails.append("import --target %s: %s" % (tgt, e))
        png = os.path.join(tmp, "f.png")
        write_png(png, 80, 200, decode_at(Reader(os.path.join(
            tmp, "syn_cga.v88")), 3))
        if open(png, "rb").read(8) != b"\x89PNG\r\n\x1a\n":
            fails.append("the PNG writer")
        # ADPCM4: an import that re-encodes the sound, verified against the
        # XDC stream it came from, and a tone that survives the codec
        out = os.path.join(tmp, "syn_adpcm.v88")
        import_xdv(xdv, out, "cga", keysecs=0.1, audio_fmt=AUD_ADPCM4)
        try:
            if verify_v88(out, xdv) and Reader(out).abytes != 67:
                fails.append("ADPCM4 import: %d bytes a frame, not 67"
                             % Reader(out).abytes)
        except (V88Error, XdvError) as e:
            fails.append("ADPCM4 import: %s" % e)
        import math
        tone = bytes(128 + int(90 * math.sin(i * 2 * math.pi * 440 / 22050))
                     for i in range(4410))
        back = adpcm4_decode(adpcm4_encode(tone))
        err = max(abs(a - b) for a, b in zip(tone[200:], back[200:]))
        if len(back) != len(tone) or err > 24:
            fails.append("ADPCM4 does not carry a 440 Hz tone (worst "
                         "sample %d off)" % err)
        # ...and a SEEK into it plays the stream's own sound (98.1.1.1): the
        # keyframes' reference bytes, and a scale steered to 0 there
        rs = Reader(out)
        whole = adpcm4_decode(b"".join(rec[len(rec) - rs.abytes:]
                                       for rec, _, _ in rs.records()))
        for i in range(1, len(rs.keys)):
            k, rec, spo, spn, idx = rs.key(i)
            tail = b"".join(r[len(r) - rs.abytes:]
                            for r, _, _ in rs.records(spo, spn, idx))
            got = adpcm4_decode(tail, ref=rec[-1])
            if got != whole[len(whole) - len(got):]:
                fails.append("ADPCM4: a seek to keyframe %d does not play "
                             "the stream's sound" % i)
                break
    for f in fails:
        print("os88vid --selfcheck: FAIL - %s" % f)
    if not fails:
        print("os88vid --selfcheck: ok - encode, import (cga, herc, lin80), "
              "decode and verify agree, ADPCM4 carries a tone and seeks "
              "exactly, and four "
              "corruptions were refused")
    return 1 if fails else 0


def main():
    if sys.argv[1:] == ["--selfcheck"]:
        return selfcheck()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def keyargs(s):
        s.add_argument("--audio", choices=sorted(AUD_BY_NAME), default="pcm8",
                       help="the sound's format (SPEC.md 98.1.1): ADPCM4 is "
                       "half the bytes, decoded by the card")
        s.add_argument("--keysecs", type=float, default=KEY_SECS,
                       help="seconds between keyframes (SPEC.md 98.1.3)")
        s.add_argument("--poster", type=int,
                       help="the poster keyframe (default: the first that is "
                       "not all one value)")
        s.add_argument("--title", default=None)
    s = sub.add_parser("import", help="XDV -> V88, exactly")
    s.add_argument("src")
    s.add_argument("out")
    s.add_argument("--target", choices=sorted(LAYOUT_BY_NAME), default="cga")
    keyargs(s)
    s = sub.add_parser("encode", help="frames (+ a WAV) -> V88, losslessly")
    s.add_argument("frames", nargs="+")
    s.add_argument("out")
    s.add_argument("--fps", type=float, required=True)
    s.add_argument("--wav")
    s.add_argument("--layout", choices=sorted(LAYOUT_BY_NAME), default="cga")
    keyargs(s)
    s = sub.add_parser("info")
    s.add_argument("files", nargs="+")
    s = sub.add_parser("decode")
    s.add_argument("file")
    s.add_argument("--frame", type=int, required=True)
    s.add_argument("--png", required=True)
    s = sub.add_parser("stat", help="an XDV's frames in the plan's lists")
    s.add_argument("files", nargs="+")
    s = sub.add_parser("verify", help="a V88 (SPEC.md 98.1.6), or an XDV's "
                       "lists against its own programs")
    s.add_argument("files", nargs="+")
    s.add_argument("--against", help="the XDV a V88 was imported from")
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
    if a.cmd == "encode":
        a.title = a.title or os.path.splitext(os.path.basename(a.out))[0]
    try:
        return {"stat": cmd_stat, "verify": cmd_verify, "import": cmd_import,
                "encode": cmd_encode, "info": cmd_info, "decode": cmd_decode,
                "benchdat": cmd_benchdat}[a.cmd](a) or 0
    except (XdvError, V88Error) as e:
        sys.exit("os88vid: %s" % e)


if __name__ == "__main__":
    sys.exit(main())
