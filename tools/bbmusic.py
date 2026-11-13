#!/usr/bin/env python3
"""bbmusic - Bounce Bonanza's music and effects (SPEC.md 128.20).

The songs are plain-text MML (apps/bonanza/music/*.bmu, TITHE's grammar -
its SPEC's 125.10.1 on tithe-new - with a note volume) over one bank of
instruments, drums
and effects (apps/bonanza/music/bank.bmb). This tool packs them into the
package's parts and writes bzsnd.inc, and it holds a Python copy of the
guest's sequencer (Seq), which the WAV renders and the rows run - so a
render is the guest's notes exactly, and only the synthesis is approximate.

    python3 tools/bbmusic.py -o build/bonanza-art      # BZSND.BIN, BZM<S>.BIN, bzsnd.inc
    python3 tools/bbmusic.py --selfcheck               # the packed notes == the source's
    python3 tools/bbmusic.py wav -o DIR [--arm spk|fm] [--song N] [--sfx] [--secs S]
    python3 tools/bbmusic.py sizes                     # bytes a part, a phrase

THE CLOCK is the physics SUB-TICK, 54.6 Hz (BZ_SUB = 21,845 PIT counts,
three to a system tick, SPEC.md 128.20.1). A PITCH is a word: the note
(MIDI numbering, A4 = 69) in the high byte, 1/256 semitone in the low.

The WAV renders want numpy and, for the AdLib, pyopl (DOSBox's OPL2);
packing and the selfcheck use the standard library only, and `make` runs
nothing but the packing.
"""
import argparse
import hashlib
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSDIR = os.path.join(ROOT, "apps", "bonanza", "music")
BANK = os.path.join(MUSDIR, "bank.bmb")
# THE MANIFEST: song S is SONGS[S]. 0 is the title, 1 - 5 the courses'
# (SPEC.md 128.20.6: course K plays song K, BENCH song 1).
SONGS = ["title.bmu", "fairway.bmu", "trial.bmu", "windmill.bmu",
         "moonlit.bmu", "summit.bmu"]

PIT_HZ = 1193182
SUB = 21845
TICK_HZ = PIT_HZ / SUB                  # 54.62 sub-ticks a second
RATE = 44100

CH_LEAD, CH_BASS, CH_CHORD, CH_DRUM = range(4)
KINDS = {"lead": CH_LEAD, "bass": CH_BASS, "chord": CH_CHORD, "drum": CH_DRUM}
KNAME = {v: k for k, v in KINDS.items()}
# a channel's FM voices: lead 0, bass 1, chord 2 - 4, drums 5; effects 6, 7
CH_VOICES = {CH_LEAD: [0], CH_BASS: [1], CH_CHORD: [2, 3, 4], CH_DRUM: [5]}
NVOICE = 6
# THE ADLIB'S CHANNELS (128.20.4): voices 0 - 4 on channels 0 - 4, the drum
# voice on 5 - or on 6 for an instrument marked `alt` (the snare's family), so
# a hit never re-patches - and the effect on 7. Channel 8 is the tone tier's.
FX_CH = 7

EV_REST, EV_INST, EV_SHAPE, EV_VOL, EV_SLUR, EV_END = 0x00, 0x80, 0xA0, 0xC0, 0xD0, 0xFF
NOTE_PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

# THE EVENTS (SPEC.md 128.20.5), in the event map's column order
EVENTS = ["LAND", "BOUNCE", "WALL", "BUMPER", "KNOCK", "STUN", "SHATTER",
          "HOP", "FALL", "TUBE", "GOAL"]
MATS = ["rubber", "steel", "glass"]
SONG_FLAG_SPKBASS = 1

OPL_SLOT = [0, 1, 2, 8, 9, 10, 16, 17, 18]
OPL_OPREG = [0x20, 0x40, 0x60, 0x80, 0xE0]
FMCAP = 8                                # BZS_FMCAP: registers a frame (128.20.4)


class ScoreError(Exception):
    pass


# ---------------------------------------------------------------------------
# THE PITCH TABLES (SPEC.md 128.20.3): a word a note, 0 - 127
# ---------------------------------------------------------------------------

# ONE OCTAVE EACH, shifted per octave on the guest (bzs_hzn, bzs_opn): the
# speaker's Hz for C7..B7 and the OPL2's F-numbers for C4..B4 (block 4).
HTOP = [int(440.0 * 2.0 ** ((96 + k - 69) / 12.0) + 0.5) for k in range(12)]
FTOP = [int(440.0 * 2.0 ** ((60 + k - 69) / 12.0) * 65536 / 49716.0 + 0.5)
        for k in range(12)]


def hz_n(n):
    """note n's Hz - bzs_hzn's arithmetic"""
    o, k = divmod(n, 12)
    if o < 8:
        h = ((HTOP[k] >> (7 - o)) + 1) >> 1     # rounded
    else:
        h = HTOP[k] << (o - 8)
    return max(19, min(20000, h))


def opl_n(n):
    """note n's block << 10 | F-number - bzs_opn's arithmetic"""
    o, k = divmod(n, 12)
    f, b = FTOP[k], o - 1
    if b < 0:
        f >>= -b
        b = 0
    elif b > 7:
        f = min(1023, f << (b - 7))
        b = 7
    return (b << 10) | f


def hz_table():
    return [hz_n(n) for n in range(128)]


def opl_table():
    return [opl_n(n) for n in range(128)]


HZT = hz_table()
OPLT = opl_table()


def clamp_pitch(p):
    return max(12 * 256, min(127 * 256 - 1, p))


def pitch_hz(p):
    """the speaker's Hz for a pitch word - bzs_hz's arithmetic, to the bit:
       interpolated in the top octave's table, then shifted to the octave"""
    n, fr = p >> 8, p & 255
    o, k = divmod(n, 12)
    h = HTOP[k]
    if fr:
        h1 = HTOP[k + 1] if k < 11 else HTOP[0] * 2
        h += ((h1 - h) * fr) >> 8
    if o < 8:
        h = ((h >> (7 - o)) + 1) >> 1           # rounded
    else:
        h <<= o - 8
    return max(19, min(20000, h))


def pitch_opl(p):
    """(A0h, B0h without the key) for a pitch word - bzs_fnum's arithmetic:
       interpolated in C4..B4's F-numbers, the block the octave less one"""
    n, fr = p >> 8, p & 255
    o, k = divmod(n, 12)
    f = FTOP[k]
    if fr:
        f1 = FTOP[k + 1] if k < 11 else FTOP[0] * 2
        f += ((f1 - f) * fr) >> 8
    b = o - 1
    if b < 0:
        f >>= 1
        b = 0
    elif b > 7:
        f = min(1023, f << (b - 7))
        b = 7
    return f & 0xFF, (b << 2) | (f >> 8)


# ---------------------------------------------------------------------------
# THE BANK
# ---------------------------------------------------------------------------

class Inst:
    def __init__(self, name):
        self.name = name
        self.fm = [0x21, 0x28, 0xF0, 0x07, 0x00, 0x21, 0x00, 0xF0, 0x07, 0x01, 0x00]
        self.macro = None               # (loop, [semitones])
        self.vdelay, self.vdepth = 0, 0
        self.spk = 0                     # a drum's speaker blip, sub-ticks
        self.alt = 0                     # the AdLib's second drum channel (6)


class Sfx:
    def __init__(self, name):
        self.name = name
        self.inst = None
        self.prio = 1
        self.sens = 255
        self.segs = []                   # (ticks, note|0x80 legato|0, slide, vol, decay, jitter)


class Bank:
    def __init__(self):
        self.insts = {}                  # name -> Inst, in order
        self.drums = {}                  # letter -> (inst, note)
        self.sfx = {}                    # name -> Sfx, in order
        self.emap = {}                   # (mat, event) -> sfx name


def strip_comment(line):
    i = line.find(";")
    return line if i < 0 else line[:i]


def logical_lines(path):
    """Join an indented continuation onto the line above it."""
    out = []
    for n, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = strip_comment(raw)
        if not line.strip():
            continue
        if raw[0] in " \t" and out:
            out[-1] = (out[-1][0], out[-1][1] + " " + line.strip())
        else:
            out.append((n, line.strip()))
    return out


def parse_abs_note(s, where):
    """`c4`, `f+3`, `b-2` -> a note number (C4 = 60)"""
    m = re.match(r"^([a-gA-G])([+#-]?)(-?\d)$", s)
    if not m:
        raise ScoreError("%s: %r is not a note like c4 or f+3" % (where, s))
    return (12 * (int(m.group(3)) + 1) + NOTE_PC[m.group(1).lower()]
            + {"": 0, "+": 1, "#": 1, "-": -1}[m.group(2)])


def hexbytes(toks, n, where):
    try:
        v = [int(t, 16) for t in toks]
    except ValueError:
        raise ScoreError("%s: want hex bytes" % where)
    if len(v) != n or any(not 0 <= x <= 255 for x in v):
        raise ScoreError("%s: want %d hex bytes" % (where, n))
    return v


def parse_bank(path=BANK):
    b = Bank()
    base = os.path.basename(path)
    cur = None
    for n, line in logical_lines(path):
        where = "%s:%d" % (base, n)
        t = line.split()
        k = t[0]
        if k == "inst":
            if t[1] in b.insts:
                raise ScoreError("%s: instrument %s twice" % (where, t[1]))
            cur = b.insts[t[1]] = Inst(t[1])
            rest = t[2:]
            while rest:
                w = rest.pop(0)
                if w == "fm":
                    toks = [x for x in rest[:13] if x != "/"]
                    cur.fm = hexbytes(toks[:11], 11, where)
                    used = 0
                    cnt = 0
                    for x in rest:
                        used += 1
                        if x != "/":
                            cnt += 1
                        if cnt == 11:
                            break
                    rest = rest[used:]
                elif w == "macro":
                    loop, vals = None, []
                    while rest and re.match(r"^(-?\d+|\|)$", rest[0]):
                        x = rest.pop(0)
                        if x == "|":
                            loop = len(vals)
                        else:
                            vals.append(int(x))
                    if not 1 <= len(vals) <= 32 or any(not -64 <= v <= 63 for v in vals):
                        raise ScoreError("%s: a macro is 1..32 semitones, -64..63" % where)
                    cur.macro = (len(vals) if loop is None else loop, vals)
                elif w == "vib":
                    cur.vdelay, cur.vdepth = int(rest.pop(0)), int(rest.pop(0))
                    if not 0 <= cur.vdelay <= 255 or not 0 <= cur.vdepth <= 15:
                        raise ScoreError("%s: vib DELAY(0..255) DEPTH(0..15)" % where)
                elif w == "spk":
                    cur.spk = int(rest.pop(0))
                    if not 0 <= cur.spk <= 127:
                        raise ScoreError("%s: spk 0..127" % where)
                elif w == "alt":
                    cur.alt = 1
                else:
                    raise ScoreError("%s: what is %s?" % (where, w))
        elif k == "drum":
            if len(t) != 4 or t[2] not in b.insts or len(t[1]) != 1:
                raise ScoreError("%s: drum LETTER INSTRUMENT NOTE" % where)
            b.drums[t[1]] = (t[2], parse_abs_note(t[3], where))
        elif k == "sfx":
            s = Sfx(t[1])
            if t[1] in b.sfx:
                raise ScoreError("%s: effect %s twice" % (where, t[1]))
            head, _, segs = line.partition(":")
            ht = head.split()[2:]
            while ht:
                w = ht.pop(0)
                if w == "inst":
                    s.inst = ht.pop(0)
                    if s.inst not in b.insts:
                        raise ScoreError("%s: no instrument %s" % (where, s.inst))
                elif w == "prio":
                    s.prio = int(ht.pop(0))
                elif w == "sens":
                    s.sens = int(ht.pop(0))
                else:
                    raise ScoreError("%s: sfx NAME inst I prio P sens S : segments" % where)
            if s.inst is None:
                raise ScoreError("%s: an effect wants its inst" % where)
            for seg in segs.split(";"):
                if not seg.strip():
                    continue
                d = {"t": 1, "n": None, "s": 0, "v": 15, "d": 0, "j": 0, "leg": 0}
                for kv in seg.split():
                    if kv == "legato":
                        d["leg"] = 1
                        continue
                    kk, _, vv = kv.partition("=")
                    if kk == "n":
                        d["n"] = 0 if vv == "r" else parse_abs_note(vv, where)
                    elif kk in d:
                        d[kk] = int(vv)
                    else:
                        raise ScoreError("%s: a segment is t= n= s= v= d= j= [legato]" % where)
                if d["n"] is None:
                    raise ScoreError("%s: a segment wants its n=" % where)
                if not (1 <= d["t"] <= 255 and -128 <= d["s"] <= 127 and 0 <= d["v"] <= 15
                        and 0 <= d["d"] <= 255 and d["j"] in (0, 1, 3, 7, 15, 31, 63, 127)):
                    raise ScoreError("%s: t 1..255, s -128..127, v 0..15, d 0..255, "
                                     "j a mask (0,1,3,..127)" % where)
                note = d["n"] | (0x80 if d["leg"] and d["n"] else 0)
                s.segs.append((d["t"], note, d["s"] & 0xFF, d["v"], d["d"], d["j"]))
            if not s.segs:
                raise ScoreError("%s: an effect wants a segment" % where)
            b.sfx[t[1]] = s
        elif k == "event":
            if t[1] not in EVENTS:
                raise ScoreError("%s: no event %s" % (where, t[1]))
            for kv in t[2:]:
                kk, _, vv = kv.partition("=")
                if vv not in b.sfx:
                    raise ScoreError("%s: no effect %s" % (where, vv))
                mats = MATS if kk == "all" else [kk]
                for m in mats:
                    if m not in MATS:
                        raise ScoreError("%s: a material is rubber, steel, glass or all" % where)
                    b.emap[(m, t[1])] = vv
        else:
            raise ScoreError("%s: what is %s?" % (where, k))
    if len(b.insts) > 32:
        raise ScoreError("more than 32 instruments")
    if len(b.sfx) > 254:
        raise ScoreError("more than 254 effects")
    return b


# ---------------------------------------------------------------------------
# THE SONGS
# ---------------------------------------------------------------------------

class Ev:
    def __init__(self, row, rows, notes, inst, q, vol, slur=False):
        self.row, self.rows, self.notes, self.inst = row, rows, notes, inst
        self.q, self.vol, self.slur = q, vol, slur


class Song:
    def __init__(self, path):
        self.path = path
        self.id = None
        self.name = None
        self.groove = [6]
        self.unit = 16
        self.rows = 16
        self.measure = 0
        self.voice = {}
        self.phrases = {}
        self.order = []
        self.loop = 0
        self.flags = 0
        self.desk = False


TOKEN = re.compile(r"\s*(?:"
                   r"(?P<inst>@[A-Za-z_][\w]*)"
                   r"|(?P<oct>o\d)"
                   r"|(?P<up>>)|(?P<dn><)"
                   r"|(?P<len>l\d+\.*)"
                   r"|(?P<q>q\d+)"
                   r"|(?P<vol>v\d+)"
                   r"|(?P<bar>\|)"
                   r"|(?P<amp>&)"
                   r"|(?P<ext>\^(?:\d+\.*|:\d+))"
                   r"|(?P<chord>\[[^\]]*\](?:\d+\.*|:\d+)?)"
                   r"|(?P<note>[a-zA-Z][+#-]?(?:\d+\.*|:\d+)?)"
                   r")")


def length_rows(spec, default, unit, where):
    """`8`, `4.`, `:3` -> rows; '' -> the default."""
    if not spec:
        return default
    if spec.startswith(":"):
        return int(spec[1:])
    m = re.match(r"^(\d+)(\.*)$", spec)
    n, dots = int(m.group(1)), len(m.group(2))
    if n == 0 or unit % n:
        raise ScoreError("%s: a 1/%d is not a whole number of rows at unit %d"
                         % (where, n, unit))
    r = unit // n
    add, part = r, r
    for _ in range(dots):
        if part % 2:
            raise ScoreError("%s: 1/%d%s is not a whole number of rows"
                             % (where, n, "." * dots))
        part //= 2
        add += part
    return add


def parse_phrase(body, kind, song, bank, where):
    octave, q, vol = 4, (0 if kind == CH_DRUM else 1), 12
    dlen = length_rows("8", 1, song.unit, where) if song.unit >= 8 else 1
    inst = song.voice.get(kind)
    evs, row, pos = [], 0, 0
    pending_amp = False
    while pos < len(body):
        m = TOKEN.match(body, pos)
        if not m or m.end() == pos:
            if body[pos:].strip() == "":
                break
            raise ScoreError("%s: cannot read '%s'" % (where, body[pos:pos + 12].strip()))
        pos = m.end()
        g = m.lastgroup
        v = m.group(g)
        if g == "inst":
            if v[1:] not in bank.insts:
                raise ScoreError("%s: no instrument %s" % (where, v))
            inst = v[1:]
        elif g == "oct":
            octave = int(v[1:])
        elif g == "up":
            octave += 1
        elif g == "dn":
            octave -= 1
        elif g == "len":
            dlen = length_rows(v[1:], dlen, song.unit, where)
        elif g == "q":
            q = int(v[1:])
        elif g == "vol":
            vol = int(v[1:])
            if not 0 <= vol <= 15:
                raise ScoreError("%s: a volume is v0..v15" % where)
        elif g == "bar":
            if song.measure and row % song.measure:
                raise ScoreError("%s: a bar line at row %d, not a multiple of %d"
                                 % (where, row, song.measure))
        elif g == "amp":
            pending_amp = True
        elif g == "ext":
            if not evs:
                raise ScoreError("%s: ^ with nothing to extend" % where)
            add = length_rows(v[1:], dlen, song.unit, where)
            evs[-1].rows += add
            row += add
        elif g in ("note", "chord"):
            if g == "chord":
                if kind != CH_CHORD:
                    raise ScoreError("%s: [chords] are for the chord channel" % where)
                inner, spec = re.match(r"^\[([^\]]*)\](.*)$", v).groups()
                notes, o2 = [], octave
                for tok in re.findall(r"[<>]|[a-g][+#-]?", inner.lower()):
                    if tok == ">":
                        o2 += 1
                    elif tok == "<":
                        o2 -= 1
                    else:
                        notes.append(12 * (o2 + 1) + NOTE_PC[tok[0]]
                                     + {"": 0, "+": 1, "#": 1, "-": -1}[tok[1:]])
                if not 1 <= len(notes) <= 3 or notes != sorted(notes) \
                        or len(set(notes)) != len(notes):
                    raise ScoreError("%s: a chord is 1..3 notes, lowest first: %s"
                                     % (where, v))
                ev_inst = inst
            else:
                mm = re.match(r"^([a-zA-Z])([+#-]?)(.*)$", v)
                letter, acc, spec = mm.group(1), mm.group(2), mm.group(3)
                if letter in "rR" and not (kind == CH_DRUM and letter in bank.drums):
                    notes, ev_inst = [], inst
                elif kind == CH_DRUM:
                    if letter not in bank.drums:
                        raise ScoreError("%s: no drum %s in the bank" % (where, letter))
                    ev_inst, dn = bank.drums[letter]
                    notes = [dn]
                else:
                    if letter.lower() not in NOTE_PC:
                        raise ScoreError("%s: %s is not a note" % (where, v))
                    notes = [12 * (octave + 1) + NOTE_PC[letter.lower()]
                             + {"": 0, "+": 1, "#": 1, "-": -1}[acc]]
                    ev_inst = inst
            rows = length_rows(spec, dlen, song.unit, where)
            if notes and ev_inst is None:
                raise ScoreError("%s: a note before any instrument (voice or @)" % where)
            for n in notes:
                if not 24 <= n <= 115:
                    raise ScoreError("%s: note %d is outside C1..G8" % (where, n))
            if pending_amp and evs and evs[-1].notes and notes == evs[-1].notes:
                evs[-1].rows += rows            # c4&c8: a TIE, one longer note
            else:
                evs.append(Ev(row, rows, notes, ev_inst, q, vol,
                              slur=pending_amp and bool(notes) and bool(evs)
                              and bool(evs[-1].notes)))
            pending_amp = False
            row += rows
    if row != song.rows:
        raise ScoreError("%s: %d rows, and the song's patterns are %d"
                         % (where, row, song.rows))
    return evs


def parse_song(path, bank):
    s = Song(path)
    base = os.path.basename(path)
    for n, line in logical_lines(path):
        where = "%s:%d" % (base, n)
        t = line.split()
        k = t[0]
        if k == "song":
            s.id = t[1]
            m = re.search(r'"([^"]*)"', line)
            if not m:
                raise ScoreError('%s: song wants a "name"' % where)
            s.name = m.group(1)
        elif k == "groove":
            s.groove = [int(x) for x in t[1:]]
        elif k == "unit":
            s.unit = int(t[1])
        elif k == "rows":
            s.rows = int(t[1])
        elif k == "measure":
            s.measure = int(t[1])
        elif k == "spkbass":
            s.flags |= SONG_FLAG_SPKBASS
        elif k == "desktop":
            s.desk = True               # the title: every row a multiple of 3
        elif k == "voice":
            if t[1] not in KINDS or t[2] not in bank.insts:
                raise ScoreError("%s: voice <lead|bass|chord|drum> <instrument>" % where)
            s.voice[KINDS[t[1]]] = t[2]
        elif k in KINDS:
            if len(t) < 3 or t[2] != "=":
                raise ScoreError("%s: %s NAME = ..." % (where, k))
            if t[1] in s.phrases:
                raise ScoreError("%s: phrase %s twice" % (where, t[1]))
            body = line.split("=", 1)[1]
            s.phrases[t[1]] = (KINDS[k], parse_phrase(body, KINDS[k], s, bank,
                                                      "%s %s" % (where, t[1])))
        elif k == "order":
            if len(t) != 5:
                raise ScoreError("%s: order LEAD BASS CHORD DRUM (- for silence)" % where)
            for kind, nm in zip((CH_LEAD, CH_BASS, CH_CHORD, CH_DRUM), t[1:]):
                if nm == "-":
                    continue
                if nm not in s.phrases:
                    raise ScoreError("%s: no phrase %s" % (where, nm))
                if s.phrases[nm][0] != kind:
                    raise ScoreError("%s: %s is a %s phrase, not a %s one"
                                     % (where, nm, KNAME[s.phrases[nm][0]], KNAME[kind]))
            s.order.append(tuple(t[1:]))
        elif k == "loop":
            s.loop = int(t[1])
        else:
            raise ScoreError("%s: what is %s?" % (where, k))
    if not s.id or not s.order:
        raise ScoreError("%s: a song wants `song` and at least one `order`" % base)
    if not 1 <= len(s.groove) <= 4 or any(not 1 <= g <= 15 for g in s.groove):
        raise ScoreError("%s: a groove is 1..4 sub-tick counts of 1..15" % base)
    if s.desk and any(g % 3 for g in s.groove):
        raise ScoreError("%s: a desktop song's rows are multiples of 3 sub-ticks "
                         "(the desktop steps three a system tick)" % base)
    if s.rows % len(s.groove) or not 1 <= s.rows <= 255:
        raise ScoreError("%s: rows must be 1..255 and a multiple of the groove" % base)
    if not 0 <= s.loop < len(s.order) or len(s.order) > 255:
        raise ScoreError("%s: loop %d is outside the order" % (base, s.loop))
    return s


# ---------------------------------------------------------------------------
# PACKING
# ---------------------------------------------------------------------------

def row_ticks(groove, rows):
    """tick offset of every row boundary 0..rows, from a pattern's start"""
    t, out = 0, [0]
    for r in range(rows):
        t += groove[r % len(groove)]
        out.append(t)
    return out


def pack_phrase(kind, evs, song, iidx, shapes):
    rt = row_ticks(song.groove, song.rows)
    out = bytearray()
    cur_inst, cur_shape, cur_vol = song.voice.get(kind), 0, 12
    for i, e in enumerate(evs):
        nxt = evs[i + 1] if i + 1 < len(evs) else None
        ticks = rt[e.row + e.rows] - rt[e.row]
        if not e.notes:
            out += bytes([EV_REST, e.rows])
            continue
        if e.inst != cur_inst:
            out.append(EV_INST | iidx[e.inst])
            cur_inst = e.inst
        if kind == CH_CHORD:
            sh = tuple(n - e.notes[0] for n in e.notes[1:]) + (0,) * (3 - len(e.notes))
            if sh not in shapes:
                shapes.append(sh)
            if len(shapes) > 32:
                raise ScoreError("%s: more than 32 chord shapes" % song.id)
            si = shapes.index(sh)
            if si != cur_shape:
                out.append(EV_SHAPE | si)
                cur_shape = si
        if e.vol != cur_vol:
            out.append(EV_VOL | e.vol)
            cur_vol = e.vol
        if e.slur:
            out.append(EV_SLUR)
        if nxt is not None and nxt.slur:
            gate = ticks + 1                    # held into the note it slurs to
        else:
            gate = max(1, ticks - e.q)
        if gate > 255:
            raise ScoreError("%s: a note of %d sub-ticks; a gate is a byte" % (song.id, gate))
        if e.rows > 255:
            raise ScoreError("%s: an event of %d rows" % (song.id, e.rows))
        out += bytes([e.notes[0], e.rows, gate])
    out.append(EV_END)
    return bytes(out)


def build_song(s, bank):
    """-> the song part's bytes (SPEC.md 128.20.3)"""
    names = list(bank.insts)
    iidx = {n: i for i, n in enumerate(names)}
    shapes = [(0, 0)]                   # shape 0: a single note
    pidx, blobs = {}, []
    for nm, (kind, evs) in s.phrases.items():
        used = any(row[kind] == nm for row in s.order)
        if not used:
            continue
        pidx[nm] = len(blobs)
        blobs.append(pack_phrase(kind, evs, s, iidx, shapes))
    if len(blobs) > 254:
        raise ScoreError("%s: more than 254 phrases" % s.id)
    shapes = [sh[:2] for sh in shapes]
    head = 18 + 4
    order = bytearray()
    for row in s.order:
        order += bytes([0xFF if nm == "-" else pidx[nm] for nm in row])
    ooff = head
    poff = ooff + len(order)
    soff = poff + 2 * len(blobs)
    boff = soff + 2 * len(shapes)
    out = bytearray(b"BM")
    out += bytes([1, len(s.groove)])
    g = s.groove + [0] * (4 - len(s.groove))
    out += bytes(g)
    out += bytes([s.rows, len(s.order), s.loop, s.flags])
    out += struct.pack("<HHH", ooff, poff, soff)
    out += bytes([iidx[s.voice[k]] if k in s.voice else 0 for k in range(4)])
    assert len(out) == head
    out += order
    o = boff
    for b in blobs:
        out += struct.pack("<H", o)
        o += len(b)
    for sh in shapes:
        out += bytes([sh[0] & 0xFF, sh[1] & 0xFF])
    for b in blobs:
        out += b
    return bytes(out)


SND_HEAD = 16


def build_snd(bank):
    """-> the sound part's bytes (SPEC.md 128.20.3)"""
    names = list(bank.insts)
    iidx = {n: i for i, n in enumerate(names)}
    sfxn = list(bank.sfx)
    hzoff = SND_HEAD
    opoff = hzoff + 24
    ioff = opoff + 24
    moff = ioff + 16 * len(names)
    macros = bytearray()
    mpos = {}
    for n in names:
        mac = bank.insts[n].macro
        if mac:
            mpos[n] = len(macros)       # a BYTE: from the macro pool's start
            loop, vals = mac
            macros += bytes([len(vals), loop]) + bytes(v & 0xFF for v in vals)
    if len(macros) > 255:
        raise ScoreError("the macros are %d bytes; an instrument names one by a byte" % len(macros))
    pids = []                           # a PATCH ID: instruments that share
    for n in names:                     # their 11 bytes share it, so changing
        fm = bytes(bank.insts[n].fm)    # between them re-patches nothing
        if fm not in pids:
            pids.append(fm)
    xoff = moff + len(macros)
    emoff = xoff + 2 * len(sfxn)
    fxoff = emoff + len(MATS) * len(EVENTS)
    out = bytearray(b"BS")
    out += bytes([1, len(names)])
    out += struct.pack("<HHHHHH", hzoff, opoff, ioff, xoff, emoff, moff)
    assert len(out) == SND_HEAD
    out += b"".join(struct.pack("<H", h) for h in HTOP)
    out += b"".join(struct.pack("<H", v) for v in FTOP)
    for n in names:
        i = bank.insts[n]
        out += bytes(i.fm)
        out += bytes([mpos.get(n, 0xFF), pids.index(bytes(i.fm)), i.vdelay, i.vdepth,
                      i.spk | (i.alt << 7)])
    out += macros
    fxbytes = bytearray()
    for n in sfxn:
        out += struct.pack("<H", fxoff + len(fxbytes))
        s = bank.sfx[n]
        fxbytes += bytes([iidx[s.inst], s.prio, s.sens])
        for seg in s.segs:
            fxbytes += bytes(seg)
        fxbytes.append(0)
    for m in MATS:
        for e in EVENTS:
            nm = bank.emap.get((m, e))
            out.append(0xFF if nm is None else sfxn.index(nm))
    assert len(out) == fxoff
    out += fxbytes
    return bytes(out)


ONLY = None                             # --only FILE: that song alone (a composer's)


def load_all():
    bank = parse_bank()
    if ONLY:
        return bank, [parse_song(ONLY, bank)]
    songs = [parse_song(os.path.join(MUSDIR, f), bank) for f in SONGS]
    if not songs[0].desk:
        raise ScoreError("song 0, the title, must say `desktop` (SPEC.md 128.20.1)")
    return bank, songs


# ---------------------------------------------------------------------------
# THE SEQUENCER - bzsound.inc's, step for step (SPEC.md 128.20)
# ---------------------------------------------------------------------------

def u8(p, o):
    return p[o]


def s8(p, o):
    v = p[o]
    return v - 256 if v & 0x80 else v


def u16(p, o):
    return p[o] | (p[o + 1] << 8)


class Voice:
    def __init__(self):
        self.on = 0           # keyed
        self.keyed = 0        # keyed THIS tick (not aged)
        self.retrig = 0       # to strike on the chip
        self.note = 0         # the base note
        self.gate = 0         # sub-ticks left
        self.inst = 0
        self.vol = 12
        self.mpos = 0         # the macro's position
        self.age = 0          # sub-ticks since keyed - or, while off, since
                              # the key went up (saturates at 255)
        self.keys = 0         # notes keyed, a byte: the speaker's re-send
        self.pitch = 0        # the output pitch word, this tick


class Fx:
    def __init__(self):
        self.ptr = 0          # the next segment, 0 = idle
        self.left = 0
        self.pitch = 0
        self.slide = 0
        self.vol = 0          # 4.4
        self.decay = 0
        self.jit = 0
        self.trans = 0
        self.boost = 0
        self.prio = 0
        self.inst = 0
        self.retrig = 0
        self.out = 0          # the output pitch, 0 silent
        self.seq = 0          # when it started (the older is replaced)
        self.segn = 0         # segments begun, a byte: the speaker's re-send
        self.rest = False
        self.svol = 0         # the segment's own volume: the AdLib's level


class Seq:
    """One song and the effects, one sub-tick a step. `arm` is 'spk' or 'fm'
       (the effects' slots: one on the speaker, two on the AdLib)."""

    def __init__(self, snd, song, arm="fm"):
        self.p, self.s, self.arm = snd, song, arm
        self.v = [Voice() for _ in range(NVOICE)]
        self.fx = [Fx()]            # ONE effect slot on either arm
        self.spk = arm == "spk"     # the speaker keys no chord voice: it never plays one
        self.lfsr = 0xACE1
        self.fxseq = 0
        self.spk_hz = 0          # the speaker's last tone (0 off)
        self.spk_tok = 0         # ...and what sounded it (bzs_stok)
        self.spk_pit = 0         # ...and its pitch word (bzs_spit)
        self.keylog = None              # the selfcheck's: (tick, voice, note, gate)
        self.t = 0
        self.restart()

    # --- the song ---------------------------------------------------------
    def restart(self):
        s = self.s
        self.glen = u8(s, 3)
        self.groove = list(s[4:8])
        self.rows = u8(s, 8)
        self.olen, self.loop, self.flags = u8(s, 9), u8(s, 10), u8(s, 11)
        self.ooff, self.poff, self.soff = u16(s, 12), u16(s, 14), u16(s, 16)
        self.ord = 0
        self.row = 0                  # rows begun in this pattern
        self.gi = 0
        self.rtick = 0
        self.cptr = [0] * 4           # 0 = the channel is silent this pattern
        self.cwait = [0] * 4
        self.cinst = [u8(s, 18 + c) for c in range(4)]
        self.cvol = [12] * 4
        self.cshape = [0] * 4
        self.cslur = [0] * 4
        self.started = False
        for vo in self.v:
            vo.__init__()

    def load_pattern(self):
        o = self.ooff + 4 * self.ord
        for c in range(4):
            ph = u8(self.s, o + c)
            self.cptr[c] = 0 if ph == 0xFF else u16(self.s, self.poff + 2 * ph)
            self.cwait[c] = 0
            # every pattern starts from the voice's own instrument, v12 and a
            # single note: the state pack_phrase packs every phrase from
            self.cinst[c] = u8(self.s, 18 + c)
            self.cvol[c] = 12
            self.cshape[c] = 0
            self.cslur[c] = 0

    def read(self, c):
        s = self.s
        while True:
            p = self.cptr[c]
            if p == 0:
                self.cwait[c] = 255
                return
            b = s[p]
            if b == EV_END:
                self.cwait[c] = 255
                return
            if b == EV_REST:
                self.cwait[c] = s[p + 1]
                self.cptr[c] = p + 2
                return
            if b < 0x80:
                self.cwait[c] = s[p + 1]
                self.key(c, b, s[p + 2])
                self.cptr[c] = p + 3
                return
            self.cptr[c] = p + 1
            hi = b & 0xE0
            if hi == EV_INST:
                self.cinst[c] = b & 0x1F
            elif hi == EV_SHAPE:
                self.cshape[c] = b & 0x1F
            elif (b & 0xF0) == EV_VOL:
                self.cvol[c] = b & 0x0F
            elif b == EV_SLUR:
                self.cslur[c] = 1

    def key(self, c, note, gate):
        if c == CH_CHORD and self.spk:      # (bzs_key: the fold never plays it)
            self.cslur[c] = 0
            return
        notes = [note]
        if c == CH_CHORD:
            sh = self.soff + 2 * self.cshape[c]
            for k in range(2):
                iv = self.s[sh + k]
                notes.append(note + iv if iv else 0)
        slur = self.cslur[c]
        self.cslur[c] = 0
        for vi, n in zip(CH_VOICES[c], notes):
            vo = self.v[vi]
            if n == 0:
                vo.on = 0
                vo.keyed = 0
                continue
            if self.keylog is not None:
                self.keylog.append((self.t, vi, n, gate, self.cinst[c], self.cvol[c]))
            vo.keys = (vo.keys + 1) & 0xFF
            vo.inst = self.cinst[c]
            vo.vol = self.cvol[c]
            vo.note = n
            vo.gate = gate
            vo.keyed = 1
            if slur and vo.on:
                continue            # legato: re-pitched, not re-keyed
            vo.on = 1
            vo.retrig = 1
            vo.mpos = 0
            vo.age = 0

    def inst_rec(self, i):
        return u16(self.p, 8) + 16 * i

    def music_tick(self):
        if not self.started:
            self.started = True
            self.load_pattern()
        if self.rtick == 0:                 # a ROW begins
            if self.row == self.rows:
                self.row = 0
                self.ord += 1
                if self.ord == self.olen:
                    self.ord = self.loop
                self.load_pattern()
            for c in range(4):
                if self.cwait[c] == 0:
                    self.read(c)
                if self.cwait[c] != 255:
                    self.cwait[c] -= 1
            self.rtick = self.groove[self.gi]
            self.gi += 1
            if self.gi == self.glen:
                self.gi = 0
            self.row += 1
        self.rtick -= 1
        for vo in self.v:                   # every sounding note AGES
            if not vo.on:
                if vo.age < 255:            # (a silent voice counts its
                    vo.age += 1             # silence: the speaker's bass)
                continue
            if vo.keyed:
                vo.keyed = 0
            else:
                vo.gate -= 1
                if vo.gate == 0:
                    vo.on = 0
                    vo.age = 0
                    continue
            r = self.inst_rec(vo.inst)
            p = vo.note << 8
            mac = self.p[r + 11]
            if mac != 0xFF:
                mac += u16(self.p, 14)
                ln, lp = self.p[mac], self.p[mac + 1]
                p += s8(self.p, mac + 2 + vo.mpos) << 8
                vo.mpos += 1
                if vo.mpos == ln:
                    vo.mpos = lp if lp < ln else ln - 1
            if vo.age < 255:
                vo.age += 1
            vo.pitch = clamp_pitch(p)

    # --- the effects ------------------------------------------------------
    def rand(self):
        lsb = self.lfsr & 1
        self.lfsr >>= 1
        if lsb:
            self.lfsr ^= 0xB400
        return self.lfsr & 0xFF

    def trigger(self, mat, ev, strength=0):
        """an event (SPEC.md 128.20.5) -> its effect into a slot"""
        n = self.p[u16(self.p, 12) + mat * len(EVENTS) + ev]
        if n == 0xFF:
            return
        rec = u16(self.p, u16(self.p, 10) + 2 * n)
        prio, sens = self.p[rec + 1], self.p[rec + 2]
        # the slot: an idle one, else the lowest priority, the older on a tie
        best = None
        for f in self.fx:
            if f.ptr == 0:
                best = f
                break
        if best is None:
            best = min(self.fx, key=lambda f: (f.prio, f.seq))
            if best.prio > prio:
                return
        tr = 0 if sens >= 16 else min(7, strength >> sens)
        self.fxseq = (self.fxseq + 1) & 0xFFFF
        best.ptr, best.left = rec + 3, 0
        best.prio, best.inst, best.trans, best.boost = prio, self.p[rec], tr, tr >> 1
        best.seq = self.fxseq
        best.out = 0

    def fx_tick(self):
        for f in self.fx:
            if f.ptr == 0:
                continue
            if f.left == 0:
                p = self.p
                t = p[f.ptr]
                if t == 0:
                    f.ptr = 0
                    f.out = 0
                    continue
                note = p[f.ptr + 1]
                f.left = t
                if note & 0x7F:
                    f.pitch = ((note & 0x7F) + f.trans) << 8
                    if not note & 0x80:
                        f.retrig = 1
                f.slide = s8(p, f.ptr + 2) * 16
                f.svol = min(15, p[f.ptr + 3] + f.boost)
                f.vol = f.svol << 4
                f.decay = p[f.ptr + 4]
                f.jit = p[f.ptr + 5]
                f.rest = (note & 0x7F) == 0
                f.segn = (f.segn + 1) & 0xFF
                f.ptr += 6
            if f.rest or f.vol < 16:
                f.out = 0
            else:
                p = f.pitch
                if f.jit:
                    p += ((self.rand() & f.jit) - (f.jit >> 1)) * 16
                f.out = clamp_pitch(p)
            f.pitch = clamp_pitch(f.pitch + f.slide)
            f.vol = max(0, f.vol - f.decay)
            f.left -= 1

    # --- one sub-tick, and what the arms make of it -------------------------
    def step(self):
        self.music_tick()
        self.fx_tick()

    def spk_choice(self, music=True):
        """(pitch, sub-ticks it lasts, token) the speaker sounds, or pitch 0.
           The TOKEN names the source and its note: a new note at the same
           pitch is sent again, or the first one's duration would end it."""
        f = self.fx[0]
        if f.ptr:
            return (f.out, f.left + 1, 0x100 | f.segn) if f.out else (0, 0, 0)
        if not music:
            return (0, 0, 0)
        d = self.v[5]
        if d.on:
            spk = self.p[self.inst_rec(d.inst) + 15] & 0x7F
            if spk and d.age <= spk:
                return d.pitch, spk - d.age + 1, 0x200 | d.keys
        lead = self.v[0]
        if lead.on:
            return lead.pitch, lead.gate, 0x300 | lead.keys
        # the BASS, where the song says so and the lead has been silent for
        # more than an articulation gap (its age counts the silence)
        b = self.v[1]
        if self.flags & SONG_FLAG_SPKBASS and b.on and lead.age >= 2:
            return b.pitch, b.gate, 0x400 | b.keys
        return (0, 0, 0)

    def spk_out(self, music=True):
        """the tone bzs_spk would send this sub-tick: None (nothing sent),
           or (Hz, duration in system ticks), Hz 0 = off"""
        p, left, tok = self.spk_choice(music)
        if p == self.spk_pit and (p == 0 or tok == self.spk_tok):
            return None
        self.spk_pit, self.spk_tok = p, tok
        self.spk_hz = hz = pitch_hz(p) if p else 0
        return (hz, (left + 2) // 3 + 1 if hz else 0)

    def fm_chan(self, vi):
        """the AdLib channel logical voice VI plays on (FX_CH for the effect)"""
        if vi >= NVOICE:
            return FX_CH
        if vi == 5 and self.p[self.inst_rec(self.v[5].inst) + 15] & 0x80:
            return 6
        return vi

    def fm_want(self, vi):
        """(on, A0, B0 with the key, TL register, patch id, inst) logical
           voice VI wants (NVOICE: the effect, at its SEGMENT's level - the
           chip's envelope decays it)"""
        if vi >= NVOICE:
            f = self.fx[0]
            on, pitch, inst, vol = f.ptr != 0 and f.out != 0, f.out, f.inst, f.svol
        else:
            vo = self.v[vi]
            on, pitch, inst, vol = vo.on, vo.pitch, vo.inst, vo.vol
        r = self.inst_rec(inst)
        car40 = self.p[r + 6]
        tl = min(63, (car40 & 0x3F) + (15 - vol) * 2) | (car40 & 0xC0)
        pid = self.p[r + 12]
        if not on:
            return (0, None, None, tl, pid, inst)
        a0, b0 = pitch_opl(pitch)
        return (1, a0, b0 | 0x20, tl, pid, inst)


class Chip:
    """The guest's FM arm: a shadow a CHANNEL, the logical voices served in
       the guest's order (128.20.4).  write(reg, val) is the OPL."""
    ORDER = [6, 0, 5, 1, 2, 3, 4]

    def __init__(self, seq, write):
        self.q, self.w = seq, write
        self.have = [{"a0": None, "b0": 0, "tl": None, "pid": None} for _ in range(9)]

    def patch(self, c, inst):
        r = self.q.inst_rec(inst)
        pb = list(self.q.p[r:r + 11])
        if self.q.p[r + 14]:            # a vibrato: the chip's own, on the carrier
            pb[5] |= 0x40
        s = OPL_SLOT[c]
        regs = [(OPL_OPREG[k] + s, pb[k]) for k in range(5)]
        regs += [(OPL_OPREG[k] + s + 3, pb[5 + k]) for k in range(5)]
        regs.append((0xC0 + c, pb[10]))
        return regs

    def voice_regs(self, v):
        on, a0, b0, tl, pid, inst = self.q.fm_want(v)
        c = self.q.fm_chan(v)
        h = self.have[c]
        regs = []
        src = self.q.fx[0] if v >= NVOICE else self.q.v[v]
        if on and pid != h["pid"]:
            regs += self.patch(c, inst)
            h["pid"] = pid
            h["tl"] = None
        if not on:
            if h["b0"] & 0x20:
                regs.append((0xB0 + c, h["b0"] & 0xDF))
                h["b0"] &= 0xDF
            return regs
        if src.retrig and h["b0"] & 0x20:
            regs.append((0xB0 + c, h["b0"] & 0xDF))
            h["b0"] &= 0xDF
        if a0 != h["a0"]:
            regs.append((0xA0 + c, a0))
            h["a0"] = a0
        if tl != h["tl"]:
            regs.append((0x40 + OPL_SLOT[c] + 3, tl))
            h["tl"] = tl
        if b0 != h["b0"]:
            regs.append((0xB0 + c, b0))
            h["b0"] = b0
        src.retrig = 0
        return regs

    def flush_all(self):
        for v in self.ORDER:
            for r, val in self.voice_regs(v):
                self.w(r, val)


def load_parts():
    bank, songs = load_all()
    return build_snd(bank), [build_song(s, bank) for s in songs], bank, songs


# ---------------------------------------------------------------------------
# THE RENDERS
# ---------------------------------------------------------------------------

def render_spk(tones, nticks):
    """tones: per sub-tick None or (Hz, duration ticks). PIT ch2 mode 3."""
    import numpy as np
    spt = RATE / TICK_HZ
    n = int(nticks * spt) + 1
    out = np.zeros(n, dtype=np.float32)
    f, left, phase = 0.0, 0.0, 0.0
    for t in range(nticks):
        a = tones[t]
        if a is not None:
            f = 0.0 if a[0] == 0 else PIT_HZ / (PIT_HZ // a[0])
            left = a[1] * 3.0           # system ticks -> sub-ticks
        if left > 0:
            left -= 1
            if left <= 0:
                f = 0.0
        a0, a1 = int(t * spt), int((t + 1) * spt)
        if f:
            ph = phase + np.arange(a1 - a0) * f / RATE
            out[a0:a1] = np.where((ph % 1.0) < 0.5, 0.22, -0.22)
            phase = (phase + (a1 - a0) * f / RATE) % 1.0
    k = 0.35                            # the cone: a gentle one-pole low-pass
    y = np.empty_like(out)
    acc = 0.0
    for i in range(len(out)):
        acc += k * (out[i] - acc)
        y[i] = acc
    return y


class OplOut:
    def __init__(self):
        try:
            import pyopl
        except ImportError:
            raise ScoreError("the FM render wants pyopl (DOSBox's OPL2): pip install pyopl")
        self.o = pyopl.opl(RATE, 2, 1)
        self.w(0x01, 0x20)
        self.w(0xBD, 0x00)
        defp = [0x21, 0x28, 0xF0, 0x07, 0x00, 0x21, 0x00, 0xF0, 0x07, 0x01, 0x00]
        for v in range(9):
            s = OPL_SLOT[v]
            for k in range(5):
                self.w(OPL_OPREG[k] + s, defp[k])
                self.w(OPL_OPREG[k] + s + 3, defp[5 + k])
            self.w(0xC0 + v, defp[10])
        self.chunks = []
        self.done = 0

    def w(self, r, v):
        self.o.writeReg(r, v)

    def run_to(self, t):
        import numpy as np
        want = int(t * RATE / TICK_HZ) - self.done
        self.done += want
        while want > 0:
            k = min(want, 512)
            buf = bytearray(k * 2)
            self.o.getSamples(buf)
            self.chunks.append(np.frombuffer(bytes(buf), dtype="<i2").astype(np.float32)
                               / 32768.0)
            want -= k

    def samples(self):
        import numpy as np
        return np.concatenate(self.chunks) if self.chunks else np.zeros(1, np.float32)


def write_wav(path, y):
    import numpy as np
    y = np.clip(y, -1, 1)
    pcm = (y * 32000).astype("<i2").tobytes()
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16))
        f.write(b"data" + struct.pack("<I", len(pcm)) + pcm)


def song_ticks(sp):
    """sub-ticks in one pass of the order (intro and body)"""
    glen = sp[3]
    g = list(sp[4:8])[:glen]
    rows, olen = sp[8], sp[9]
    return sum(g[r % glen] for r in range(rows)) * olen


def run(snd, sp, arm, nticks, events=(), music=True):
    """-> per sub-tick: the speaker tone (None/(hz,dur)) for 'spk', or the
       OPL writes for 'fm'. events: {tick: [(mat, ev, strength)]}"""
    q = Seq(snd, sp, arm)
    ev = dict(events)
    out = []
    if arm == "fm":
        log = []
        chip = Chip(q, lambda r, v: log.append((r, v)))
    for t in range(nticks):
        for e in ev.get(t, []):
            q.trigger(*e)
        q.step()
        if not music:
            for vo in q.v:
                vo.on = 0
        if arm == "spk":
            out.append(q.spk_out(music))
        else:
            log.clear()
            chip.flush_all()
            out.append(list(log))
    return out


def render(snd, sp, arm, nticks, events=(), music=True):
    acts = run(snd, sp, arm, nticks, events, music)
    if arm == "spk":
        return render_spk(acts, nticks)
    o = OplOut()
    for t, regs in enumerate(acts):
        for r, v in regs:
            o.w(r, v)
        o.run_to(t + 1)
    return o.samples()


def fx_demo_events(bank):
    """every impact of every ball, then the shared ones, a beat apart"""
    evs, t = {}, 10
    for mi, m in enumerate(MATS):
        for ei, e in enumerate(EVENTS[:7]):
            if (m, e) in bank.emap:
                for strength in (64, 400):
                    evs.setdefault(t, []).append((mi, ei, strength))
                    t += 30
        t += 30
    for ei, e in enumerate(EVENTS[7:], 7):
        if ("rubber", e) in bank.emap:
            evs.setdefault(t, []).append((0, ei, 0))
            t += 60
    return evs, t + 60


def wav_cmd(args):
    import numpy as np
    snd, parts, bank, songs = load_parts()
    os.makedirs(args.o, exist_ok=True)
    arms = [args.arm] if args.arm else ["spk", "fm"]
    if args.sfx:
        evs, n = fx_demo_events(bank)
        for arm in arms:
            y = render(snd, parts[-1], arm, n, evs, music=False)
            path = os.path.join(args.o, "sfx-%s.wav" % arm)
            write_wav(path, y)
            print("%s: every effect, %.1f s" % (path, len(y) / RATE))
        return
    for si, (s, sp) in enumerate(zip(songs, parts)):
        if args.song is not None and si != args.song:
            continue
        one = song_ticks(sp)
        n = int(args.secs * TICK_HZ) if args.secs else one + int(4 * TICK_HZ)
        for arm in arms:
            y = render(snd, sp, arm, n)
            k = min(len(y), int(3 * RATE))
            y[-k:] *= np.linspace(1, 0, k)
            path = os.path.join(args.o, "%d-%s-%s.wav" % (si, s.id, arm))
            write_wav(path, y)
            print("%s: %s, %.1f s (one pass %.1f s)" % (path, s.name, len(y) / RATE,
                                                       one / TICK_HZ))


# ---------------------------------------------------------------------------
# EMIT, SIZES, SELFCHECK
# ---------------------------------------------------------------------------

def emit(outdir):
    snd, parts, bank, songs = load_parts()
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "BZSND.BIN"), "wb") as f:
        f.write(snd)
    for si, sp in enumerate(parts):
        with open(os.path.join(outdir, "BZM%d.BIN" % si), "wb") as f:
            f.write(sp)
    lines = [
        "; GENERATED by tools/bbmusic.py from apps/bonanza/music/ - do not edit.",
        "; SPEC.md 128.20.3: the sound part BZSND.BIN and one part a song, BZM<S>.BIN.",
        "BZS_NSONG       equ %d        ; songs: 0 the title, 1 - %d the courses'"
        % (len(parts), len(parts) - 1),
        "BZS_NEV         equ %d        ; events, the event map's columns" % len(EVENTS),
    ]
    for i, e in enumerate(EVENTS):
        lines.append("BZS_E_%-9s equ %d" % (e, i))
    lines += [
        "BZS_NINST       equ %d" % len(bank.insts),
        "BZS_NFX         equ %d" % len(bank.sfx),
        "BZS_SNDBYTES    equ %d     ; BZSND.BIN" % len(snd),
    ]
    for si, (s, sp) in enumerate(zip(songs, parts)):
        lines.append("; song %d, %s: %d bytes, %.1f s a pass"
                     % (si, s.name, len(sp), song_ticks(sp) / TICK_HZ))
    lines.append("")
    with open(os.path.join(outdir, "bzsnd.inc"), "w") as f:
        f.write("\n".join(lines))
    h = hashlib.sha1(open(os.path.abspath(__file__), "rb").read()).hexdigest()
    with open(os.path.join(outdir, ".bz-snd"), "w") as f:
        f.write(h + "\n")


def sizes():
    snd, parts, bank, songs = load_parts()
    print("BZSND.BIN %5d bytes: %d instruments, %d effects" % (len(snd), len(bank.insts),
                                                             len(bank.sfx)))
    tot = len(snd)
    for si, (s, sp) in enumerate(zip(songs, parts)):
        print("BZM%d.BIN  %5d bytes: %-28s %5.1f s a pass, %d patterns"
              % (si, len(sp), s.name, song_ticks(sp) / TICK_HZ, len(s.order)))
        tot += len(sp)
    print("total     %5d bytes (before the parts' compression)" % tot)


def source_notes(s, bank):
    """(tick, voice, note, gate) the SOURCE keys - read off the parse, not
       the part - for the first pass and the loop's first pattern again"""
    rt = row_ticks(s.groove, s.rows)
    ptick = rt[-1]
    iidx = {n: i for i, n in enumerate(bank.insts)}
    out = []
    seq = list(range(len(s.order))) + [s.loop]
    for k, oi in enumerate(seq):
        base = k * ptick
        row = s.order[oi]
        for c in range(4):
            nm = row[c]
            if nm == "-":
                continue
            evs = s.phrases[nm][1]
            for i, e in enumerate(evs):
                if not e.notes:
                    continue
                nxt = evs[i + 1] if i + 1 < len(evs) else None
                ticks = rt[e.row + e.rows] - rt[e.row]
                gate = ticks + 1 if (nxt is not None and nxt.slur) else max(1, ticks - e.q)
                notes = e.notes + [0] * (3 - len(e.notes)) if c == CH_CHORD else e.notes
                for vi, n in zip(CH_VOICES[c], notes):
                    if n:
                        out.append((base + rt[e.row], vi, n, gate, iidx[e.inst], e.vol))
    return sorted(out), ptick * len(seq)


def selfcheck():
    problems = 0
    snd, parts, bank, songs = load_parts()

    def bad(msg):
        nonlocal problems
        problems += 1
        print("FAIL: " + msg)

    # 1. the tables
    for n in range(24, 115):
        hz = 440.0 * 2 ** ((n - 69) / 12.0)
        a0, b0 = pitch_opl(n << 8)
        f = a0 | ((b0 & 3) << 8)
        blk = b0 >> 2
        fhz = f * 49716.0 / (1 << (20 - blk))
        if abs(fhz / hz - 1) > 0.003:
            bad("OPL note %d: %.2f Hz against %.2f" % (n, fhz, hz))
        if abs(pitch_hz(n << 8) / hz - 1) > 0.02:
            bad("Hz note %d" % n)
    for n in range(24, 115):                  # interpolation is monotone
        last = 0
        for fr in range(0, 256, 15):
            a0, b0 = pitch_opl((n << 8) | fr)
            fhz = (a0 | ((b0 & 3) << 8)) * 49716.0 / (1 << (20 - (b0 >> 2)))
            if fhz < last:
                bad("OPL interpolation not monotone at %d+%d" % (n, fr))
            last = fhz
    # 2. every song: the notes the part keys are the source's, tick for tick
    for si, (s, sp) in enumerate(zip(songs, parts)):
        want, n = source_notes(s, bank)
        q = Seq(snd, sp)
        q.keylog = []
        for t in range(n):
            q.t = t
            q.step()
        got = q.keylog
        gw = want
        gg = sorted(got)
        if gw != gg:
            for a, b in zip(gw, gg):
                if a != b:
                    bad("%s: the source keys %s and the part %s" % (s.id, a, b))
                    break
            else:
                bad("%s: %d notes in the source, %d from the part" % (s.id, len(gw), len(gg)))
        # 3. the speaker's tones and the chip's writes are well formed
        for arm in ("spk", "fm"):
            acts = run(snd, sp, arm, min(n, 1200))
            if arm == "spk":
                if not any(a and a[0] for a in acts):
                    bad("%s: the speaker never sounds" % s.id)
                for a in acts:
                    if a and a[0] and not 19 <= a[0] <= 20000:
                        bad("%s: a tone of %d Hz" % (s.id, a[0]))
                        break
            else:
                if any((r & 0xF0) == 0xB0 and (r & 0x0F) > 7 for regs in acts for r, v in regs):
                    bad("%s: a write to voice 8 (the tone tier's)" % s.id)
    # 4. every material has every impact, and the effects are well formed
    for m in MATS:
        for e in EVENTS[:5]:
            if (m, e) not in bank.emap:
                bad("%s has no %s effect" % (m, e))
    for mi, m in enumerate(MATS):
        for ei, e in enumerate(EVENTS[:5]):
            others = [bank.emap.get((o, e)) for o in MATS if o != m]
            if bank.emap.get((m, e)) in others:
                bad("%s's %s effect is another ball's (SPEC.md 128.20.5)" % (m, e))
    evs, nt = fx_demo_events(bank)
    for arm in ("spk", "fm"):
        acts = run(snd, parts[-1], arm, nt, evs, music=False)
        if arm == "spk" and not any(a and a[0] for a in acts):
            bad("the effects never sound on the speaker")
    # 5. the packing is deterministic
    if build_snd(bank) != snd or [build_song(s, bank) for s in songs] != parts:
        bad("packing twice gave different bytes")
    print("bbmusic selfcheck: %d songs, %d effects, %d problem(s)"
          % (len(songs), len(bank.sfx), problems))
    return problems == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", default="emit", choices=["emit", "wav", "sizes"])
    ap.add_argument("-o", default=os.path.join(ROOT, "build", "bonanza-art"))
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--arm", choices=["spk", "fm"])
    ap.add_argument("--song", type=int)
    ap.add_argument("--sfx", action="store_true")
    ap.add_argument("--secs", type=float, default=0)
    ap.add_argument("--only", help="check, size or render this one .bmu alone")
    args = ap.parse_args()
    global ONLY
    ONLY = args.only
    try:
        if args.selfcheck:
            sys.exit(0 if selfcheck() else 1)
        if args.cmd == "wav":
            wav_cmd(args)
        elif args.cmd == "sizes":
            sizes()
        else:
            emit(args.o)
    except ScoreError as e:
        print("bbmusic: " + str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
