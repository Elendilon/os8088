#!/usr/bin/env python3
"""TITHE's MUSIC - a plain-text score in, the packed MUSIC part out.

    python3 tools/os88tithemus.py emit             # apps/tithe/tisong.inc + build/timus.bin
    python3 tools/os88tithemus.py wav              # build/tithemus/<song>-{spk,fm}.wav, every song
    python3 tools/os88tithemus.py wav procession --arm fm --secs 30
    python3 tools/os88tithemus.py list             # what is in the part, and what it costs
    python3 tools/os88tithemus.py --selfcheck

TITHE-PLAN 13 is the design and SPEC.md 97.10 the contract; this is the tool
its 13.10 asks for, in os88tithechar.py's shape.

ONE SCORE, TWO RENDERERS (TITHE-PLAN 13.2). A piece is four channels - LEAD,
BASS, CHORD, DRUM - and the speaker plays the lead and nothing else, so the
lead has to carry the tune on its own. The FM arm plays all four on six of
the OPL2's voices: the lead on 0, the bass on 1, the chord channel's up to
three notes on 2-4, and the drums on 5. Voices 6 and 7 are left for effects
(TITHE-PLAN 13.8) and 8 is the kernel's tone tier (SPEC.md 34.8).

THE CLOCK IS THE SYSTEM TICK (TITHE-PLAN 13.3): a row is a whole number of
ticks at 18.2065 Hz. A GROOVE of up to four tick counts is cycled a row at a
time - [3] is a 16th at 91 BPM, [3, 2] is 109 BPM with a lilt - and a pattern
must be a multiple of the groove's length, so every pattern starts on the
groove's first step and a note's length in TICKS is known here, at pack time.
That is what lets the tool, and not the machine, work out every GATE.

THE NOTATION is MML (the IBM PC BASIC `PLAY` statement's), a phrase a line:

    song procession "The Procession"   ; an id, and the name the window shows
    groove 3                           ; ticks a row, cycled
    unit 16                            ; a row is a 16th note - `l8` is 2 rows
    rows 32                            ; rows in a pattern
    measure 16                         ; `|` must fall on a multiple of this
    voice lead horn                    ; each channel's instrument at a
    voice bass lute                    ; phrase's start, until an `@name`
    lead L1 = o4 l8 e4 g a | b2 r2 |   ; lead / bass / chord / drum PHRASES,
          ...                          ; a continuation line starts indented
    chord C1 = [e g b]2 [d f+ a]2      ; up to three notes, lowest first
    drum D1 = k8 h8 s8 h8              ; a letter the bank's `drum` lines map
    order L1 B1 C1 D1                  ; lead bass chord drum, `-` for silent
    loop 1                             ; the order row the song returns to

`o` octave, `<`/`>` down/up one, `l` default length, `q` the GAP in ticks
before the next note (default 1 - a speaker with no envelope needs one to
hear a repeated note at all), `r` rest, `.` dotted, `^8` extend the last note,
`&` slur into the next note (legato, no retrigger), `:3` a length in ROWS.

THE BANK (apps/tithe/music/bank.tmb) is shared by every song, TITHE-PLAN
13.3's "a faction sounds like itself because of what it plays". An
instrument is an OPL2 patch in the driver's own 11-byte order (SPEC.md 34.2)
and a speaker behaviour: a per-tick semitone MACRO (a pluck is an octave up
for one tick) and a square VIBRATO. `wav` renders the FM arm through pyopl -
DOSBox's OPL2 - driven with the SAME register writes SOUND.DRV makes, so the
approximation is the synthesis and not the notes; the guest is the truth.
"""

import argparse
import os
import re
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MUSDIR = os.path.join(ROOT, "apps", "tithe", "music")
BANK = os.path.join(MUSDIR, "bank.tmb")
# THE MANIFEST, and its order is the demo's `M` key's (SPEC.md 97.7)
SONGS = ["procession.tmu",                  # the title theme
         "reckoning.tmu",                   # the campaign map's
         "bultoll.tmu",                     # the deck builder's
         "bulsteadfast.tmu",                # THE BULWARK
         "emberkindle.tmu",                 # THE EMBER CHOIR
         "covinter.tmu"]                    # THE COVENANT - every one chosen
# ...and the RESOLUTION pieces (TITHE-PLAN 13.4.1), after the songs in the
# part: `E` picks one and `R` cuts it into whatever is playing
RESOLUTIONS = ["reswar.tmu", "restoll.tmu", "rescharge.tmu"]
# archive/ holds the ones retired from this list, with why at the top of each

TICK_HZ = 1193182.0 / 65536.0        # 18.2065
PIT_HZ = 1193182
NOTE0 = 24                          # C1 - the frequency table's first note
NNOTE = 84                          # ...through B7
VERSION = 1
MAXSONG = 16

# the packed part (SPEC.md 97.10.2). Offsets are from the part's own start.
DIR_MAGIC = b"TM"
INST_REC = 16                       # 11 FM bytes, vib delay, vib shift,
                                    # macro length, macro loop, macro index
EV_REST = 0x00
EV_INST = 0x80                      # | instrument, 0..31
EV_SHAPE = 0xA0                     # | chord shape, 0..31
EV_SLUR = 0xC0
EV_END = 0xFF
PH_NONE = 0xFF                      # an order row's silent channel

CH_LEAD, CH_BASS, CH_CHORD, CH_DRUM = range(4)
KINDS = {"lead": CH_LEAD, "bass": CH_BASS, "chord": CH_CHORD, "drum": CH_DRUM}
KNAME = {v: k for k, v in KINDS.items()}
# the OPL voices each channel sounds on (SPEC.md 97.10.3)
FM_VOICES = {CH_LEAD: [0], CH_BASS: [1], CH_CHORD: [2, 3, 4], CH_DRUM: [5]}
SPK_PRIO = 0x20                     # under the package default, so an effect
                                    # at 0x40 always preempts (TITHE-PLAN 13.8)


class ScoreError(Exception):
    pass


def hz_of(note):
    return 440.0 * 2 ** ((note - 69) / 12.0)


def freq_table():
    return [int(round(hz_of(NOTE0 + i))) for i in range(NNOTE)]


# ---------------------------------------------------------------------------
# the BANK
# ---------------------------------------------------------------------------

class Inst:
    def __init__(self, name):
        self.name = name
        self.fm = None
        self.macro = [0]
        self.mloop = 0
        self.vdelay = 0
        self.vshift = 0             # 0 = no vibrato


def strip_comment(line):
    return line.split(";", 1)[0].rstrip()


def parse_bank(path=BANK):
    insts, order, drums = {}, [], {}
    cur = None
    for n, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = strip_comment(raw)
        if not line.strip():
            continue
        t = line.split()
        where = "%s:%d" % (os.path.basename(path), n)
        if t[0] == "inst":
            cur = Inst(t[1])
            if cur.name in insts:
                raise ScoreError("%s: instrument %s twice" % (where, cur.name))
            insts[cur.name] = cur
            order.append(cur.name)
        elif t[0] == "fm":
            b = [int(x, 16) for x in t[1:] if x != "/"]
            if len(b) != 11 or cur is None:
                raise ScoreError("%s: fm wants 11 hex bytes after an inst" % where)
            cur.fm = b
        elif t[0] == "spk":
            i = 1
            while i < len(t):
                if t[i] == "macro":
                    i += 1
                    m, loop = [], None
                    while i < len(t) and re.match(r"^[-+]?\d+$|^\|$", t[i]):
                        if t[i] == "|":
                            loop = len(m)
                        else:
                            m.append(int(t[i]))
                        i += 1
                    if not m or any(v < -64 or v > 63 for v in m):
                        raise ScoreError("%s: a macro is 1+ offsets in -64..63" % where)
                    cur.macro = m
                    cur.mloop = len(m) - 1 if loop is None else loop
                elif t[i] == "vib":
                    cur.vdelay, cur.vshift = int(t[i + 1]), int(t[i + 2])
                    i += 3
                else:
                    raise ScoreError("%s: spk wants macro/vib, not %s" % (where, t[i]))
        elif t[0] == "drum":
            letter, iname, note = t[1], t[2], t[3]
            if len(letter) != 1 or not letter.isalpha() or letter.lower() == "r":
                raise ScoreError("%s: a drum is one letter, not r" % where)
            drums[letter] = (iname, parse_abs_note(note, where))
        else:
            raise ScoreError("%s: what is %s?" % (where, t[0]))
    for i in insts.values():
        if i.fm is None:
            raise ScoreError("instrument %s has no fm line" % i.name)
    for letter, (iname, _) in drums.items():
        if iname not in insts:
            raise ScoreError("drum %s names no instrument %s" % (letter, iname))
    if len(order) > 32:
        raise ScoreError("the bank has %d instruments; an event names 32" % len(order))
    return insts, order, drums


NOTE_PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def parse_abs_note(s, where):
    m = re.match(r"^([a-g])([+#-]?)(\d)$", s.lower())
    if not m:
        raise ScoreError("%s: %s is not a note like c2 or f+3" % (where, s))
    pc = NOTE_PC[m.group(1)] + {"": 0, "+": 1, "#": 1, "-": -1}[m.group(2)]
    return 12 * (int(m.group(3)) + 1) + pc


# ---------------------------------------------------------------------------
# a SONG
# ---------------------------------------------------------------------------

class Ev:
    """One event of a phrase: a note, a chord or a rest, at a row."""
    def __init__(self, row, rows, notes, inst, q, slur=False):
        self.row, self.rows, self.notes = row, rows, notes   # notes [] = rest
        self.inst, self.q, self.slur = inst, q, slur


class Song:
    def __init__(self, path):
        self.path = path
        self.id = None
        self.name = None
        self.groove = [3]
        self.unit = 16
        self.rows = 16
        self.measure = None
        self.states = 1
        self.voice = {}
        self.phrases = {}           # name -> (kind, [Ev])
        self.order = []             # [(lead names[states], bass, chord, drum)]
        self.loop = 0
        self.tail = 0               # the order row the TAIL starts at, 0: none


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


def parse_song(path, insts, drums):
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
        elif k == "states":
            s.states = int(t[1])
        elif k == "voice":
            if t[1] not in KINDS or t[2] not in insts:
                raise ScoreError("%s: voice <lead|bass|chord> <instrument>" % where)
            s.voice[KINDS[t[1]]] = t[2]
        elif k in KINDS:
            if len(t) < 3 or t[2] != "=":
                raise ScoreError("%s: %s NAME = ..." % (where, k))
            if t[1] in s.phrases:
                raise ScoreError("%s: phrase %s twice" % (where, t[1]))
            body = line.split("=", 1)[1]
            s.phrases[t[1]] = (KINDS[k], parse_phrase(body, KINDS[k], s, insts,
                                                      drums, "%s %s" % (where, t[1])))
        elif k == "order":
            if len(t) not in (5, 6):
                raise ScoreError("%s: order LEAD BASS CHORD DRUM [SPEAKER]" % where)
            leads = t[1].split("/")
            if len(leads) == 1:
                leads = leads * s.states
            if len(leads) != s.states:
                raise ScoreError("%s: %d states want %d leads" % (where, s.states, s.states))
            spk = t[5] if len(t) == 6 else None
            if s.order and (spk is None) != (s.order[-1][4] is None):
                raise ScoreError("%s: a SPEAKER lead on every order row or on none"
                                 % where)
            row = (leads, t[2], t[3], t[4], spk)
            for kind, nm in ([(CH_LEAD, x) for x in leads] +
                             ([(CH_LEAD, spk)] if spk else []) +
                             [(CH_BASS, t[2]), (CH_CHORD, t[3]), (CH_DRUM, t[4])]):
                if nm == "-":
                    continue
                if nm not in s.phrases:
                    raise ScoreError("%s: no phrase %s" % (where, nm))
                if s.phrases[nm][0] != kind:
                    raise ScoreError("%s: %s is a %s phrase, not a %s one"
                                     % (where, nm, KNAME[s.phrases[nm][0]], KNAME[kind]))
            s.order.append(row)
        elif k == "loop":
            s.loop = int(t[1])
        elif k == "tail":
            s.tail = int(t[1])
        else:
            raise ScoreError("%s: what is %s?" % (where, k))
    if not s.id or not s.order:
        raise ScoreError("%s: a song wants `song` and at least one `order`" % base)
    if not 1 <= len(s.groove) <= 4 or any(not 1 <= g <= 15 for g in s.groove):
        raise ScoreError("%s: a groove is 1..4 tick counts of 1..15" % base)
    if s.rows % len(s.groove) or not 1 <= s.rows <= 255:
        raise ScoreError("%s: rows must be 1..255 and a multiple of the groove" % base)
    if s.states not in (1, 3):
        raise ScoreError("%s: states is 1 or 3 (TITHE-PLAN 13.4)" % base)
    if not 0 <= s.loop < len(s.order):
        raise ScoreError("%s: loop %d is outside the order" % (base, s.loop))
    if s.tail and not s.loop < s.tail < len(s.order):
        raise ScoreError("%s: a tail starts after the loop and inside the order"
                         % base)
    return s


TOKEN = re.compile(r"\s*(?:"
                   r"(?P<inst>@[A-Za-z_][\w]*)"
                   r"|(?P<oct>o\d)"
                   r"|(?P<up>>)|(?P<dn><)"
                   r"|(?P<len>l\d+\.*)"
                   r"|(?P<q>q\d+)"
                   r"|(?P<bar>\|)"
                   r"|(?P<amp>&)"
                   r"|(?P<ext>\^(?:\d+\.*|:\d+))"
                   r"|(?P<chord>\[[^\]]*\](?:\d+\.*|:\d+)?)"
                   r"|(?P<note>[a-gA-GrRkKsShHtTcCpPxXzZjJmM][+#-]?(?:\d+\.*|:\d+)?)"
                   r")")


def length_rows(spec, default, unit, where):
    """`8`, `4.`, `:3` -> rows; '' -> the default."""
    if not spec:
        return default
    if spec.startswith(":"):
        return int(spec[1:])
    m = re.match(r"^(\d+)(\.*)$", spec)
    n, dots = int(m.group(1)), len(m.group(2))
    if unit % n:
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


def parse_phrase(body, kind, song, insts, drums, where):
    octave, dlen, q = 4, length_rows("8", 1, song.unit, where) if song.unit >= 8 else 1, 1
    if kind == CH_DRUM:
        q = 0
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
            if v[1:] not in insts:
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
                if not 1 <= len(notes) <= 3 or notes != sorted(notes):
                    raise ScoreError("%s: a chord is 1..3 notes, lowest first: %s"
                                     % (where, v))
                ev_inst = inst
            else:
                letter = v[0]
                mm = re.match(r"^([a-zA-Z])([+#-]?)(.*)$", v)
                acc, spec = mm.group(2), mm.group(3)
                if letter.lower() == "r":
                    notes, ev_inst = [], inst
                elif kind == CH_DRUM:
                    if letter not in drums:
                        raise ScoreError("%s: no drum %s in the bank" % (where, letter))
                    ev_inst, dn = drums[letter]
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
                if not NOTE0 <= n < NOTE0 + NNOTE:
                    raise ScoreError("%s: note %d is off the frequency table" % (where, n))
            if pending_amp and evs and evs[-1].notes and notes == evs[-1].notes:
                evs[-1].rows += rows            # c4&c8: a TIE, one longer note
            else:
                evs.append(Ev(row, rows, notes, ev_inst, q,
                              slur=pending_amp and bool(notes) and bool(evs)
                              and bool(evs[-1].notes)))
            pending_amp = False
            row += rows
    if row != song.rows:
        raise ScoreError("%s: %d rows, and the song's patterns are %d"
                         % (where, row, song.rows))
    return evs


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
    cur_inst, cur_shape = None, None
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
                raise ScoreError("more than 32 chord shapes")
            si = shapes.index(sh)
            if si != cur_shape:
                out.append(EV_SHAPE | si)
                cur_shape = si
        if e.slur:
            out.append(EV_SLUR)
        if nxt is not None and nxt.slur:
            gate = ticks + 1                    # held into the note it slurs to
        else:
            gate = max(1, ticks - e.q)
        if gate > 255:
            raise ScoreError("%s: a note of %d ticks; a gate is a byte" % (song.id, gate))
        if e.rows > 255:
            raise ScoreError("%s: an event of %d rows" % (song.id, e.rows))
        out += bytes([e.notes[0], e.rows, gate])
    out.append(EV_END)
    return bytes(out)


def build_part():
    insts, iorder, drums = parse_bank()
    iidx = {n: i for i, n in enumerate(iorder)}
    songs = [parse_song(os.path.join(MUSDIR, f), insts, drums)
             for f in SONGS + RESOLUTIONS]
    if len(songs) > MAXSONG:
        raise ScoreError("more than %d songs" % MAXSONG)
    shapes = [(0, 0)]                   # shape 0: one note
    # the fixed head, then the tables, then each song
    head = 4 + 8 + 2 * len(songs)
    part = bytearray(head)
    lab = {}
    lab["freq"] = len(part)
    for f in freq_table():
        part += struct.pack("<H", f)
    # the macro pool and the instrument records
    pool = bytearray()
    recs = bytearray()
    for n in iorder:
        i = insts[n]
        mi = len(pool)
        pool += bytes([v & 0xFF for v in i.macro])
        recs += bytes(i.fm) + bytes([i.vdelay, i.vshift, len(i.macro), i.mloop, mi])
    if len(pool) > 255:
        raise ScoreError("the macro pool is %d bytes; an index is a byte" % len(pool))
    lab["inst"] = len(part)
    part += recs
    lab["macro"] = len(part)
    part += pool
    songoffs = []
    packed_songs = []
    for s in songs:
        # phrases, deduplicated by their bytes
        blobs, pidx = [], {}
        for name, (kind, evs) in s.phrases.items():
            b = pack_phrase(kind, evs, s, iidx, shapes)
            if b not in blobs:
                blobs.append(b)
            pidx[name] = blobs.index(b)
        if len(blobs) >= PH_NONE:
            raise ScoreError("%s: %d phrases" % (s.id, len(blobs)))
        packed_songs.append((s, blobs, pidx))
    lab["shape"] = len(part)
    for sh in shapes:
        part += bytes(sh[:2])
    for s, blobs, pidx in packed_songs:
        songoffs.append(len(part))
        hdr_at = len(part)
        part += bytes(16)
        order_at = len(part)
        for leads, b, c, d, spk in s.order:
            def ix(nm):
                return PH_NONE if nm == "-" else pidx[nm]
            part += bytes([ix(b), ix(c), ix(d)] + [ix(x) for x in leads]
                          + ([ix(spk)] if spk else []))
        ptab_at = len(part)
        part += bytes(2 * len(blobs))
        for i, b in enumerate(blobs):
            struct.pack_into("<H", part, ptab_at + 2 * i, len(part))
            part += b
        g = s.groove + [0] * (4 - len(s.groove))
        struct.pack_into("<5B5BHH", part, hdr_at, len(s.groove), *g, s.rows,
                         s.states, len(s.order), s.loop, s.tail, order_at, ptab_at)
        part[hdr_at + 14] = 1 if s.order[0][4] else 0    # TMS_SPK
    part[0:4] = DIR_MAGIC + bytes([VERSION, len(songs)])
    struct.pack_into("<HHHH", part, 4, lab["freq"], lab["inst"], lab["macro"], lab["shape"])
    for i, o in enumerate(songoffs):
        struct.pack_into("<H", part, 12 + 2 * i, o)
    if len(part) > 65535:
        raise ScoreError("the part is %d bytes" % len(part))
    return bytes(part), songs, insts, iorder, drums


# ---------------------------------------------------------------------------
# THE SEQUENCER, as the machine runs it - read out of the PACKED bytes, so a
# render is the part and not the source. apps/tithe/timus.inc is the other
# copy and SPEC.md 97.10.4 is the order both keep.
# ---------------------------------------------------------------------------

class Chan:
    def __init__(self):
        self.ptr = 0
        self.wait = 0
        self.note = 0
        self.inst = 0
        self.gate = 0
        self.shape = 0
        self.slur = 0
        self.fresh = 0
        self.age = 0
        self.last_f = 0


def u8(p, o):
    return p[o]


def u16(p, o):
    return p[o] | (p[o + 1] << 8)


class Seq:
    """One song, stepped a tick at a time. Emits ACTIONS, not samples:
       ('spk', freq_or_0, ticks) and ('fm', voice, verb, arg) - exactly the
       calls the guest makes, so both renderers and the selfcheck read one
       stream."""

    def __init__(self, part, song, arm, state=0):
        self.p = part
        self.arm = arm
        so = u16(part, 12 + 2 * song)
        self.glen = u8(part, so)
        self.groove = [u8(part, so + 1 + i) for i in range(4)]
        self.rows = u8(part, so + 5)
        self.states = u8(part, so + 6)
        self.ordlen = u8(part, so + 7)
        self.loop = u8(part, so + 8)
        self.tail = u8(part, so + 9)
        self.spk = u8(part, so + 14)    # the order rows carry a SPEAKER lead
        self.ending = False          # end() asked for the tail
        self.finished = False        # ...and it has played: hand back
        self.order = u16(part, so + 10)
        self.ptab = u16(part, so + 12)
        self.freq = u16(part, 4)
        self.insts = u16(part, 6)
        self.macros = u16(part, 8)
        self.shapes = u16(part, 10)
        self.state = state
        self.ch = [Chan() for _ in range(4)]
        self.fmpatch = [None] * 6
        self.fmkeyed = [False] * 6
        self.ord = 0
        self.row = 0
        self.tleft = 0
        self.gi = 0
        self.tick = 0
        self.notes_log = []          # (tick, channel, note|0) for the selfcheck
        self.load_pattern()

    def next_ord(self, o):
        """the order row after o: the loop wraps at the TAIL while the piece
           is not ending, an ending piece jumps to the tail at the next
           boundary, and past the last row a piece with a tail is FINISHED
           (None) where one without loops (SPEC.md 97.10.6)"""
        if self.tail and self.ending and o < self.tail:
            return self.tail
        o += 1
        if self.tail and o == self.tail and not self.ending:
            return self.loop
        if o == self.ordlen:
            return None if self.tail else self.loop
        return o

    def end(self):
        self.ending = True

    def seek(self, o, row):
        """start at order row o, row `row`, as the guest's hand-back does: the
           pattern loaded, then row's worth of ticks stepped (the guest steps
           them quietly and resyncs, which leaves the same state)"""
        self.ord = o
        self.row = 0
        self.tleft = 0
        self.gi = 0
        self.load_pattern()
        for _ in range(row_ticks(self.groove[:self.glen], self.rows)[row]):
            self.step()

    def hz(self, note):
        return u16(self.p, self.freq + 2 * (note - NOTE0))

    def load_pattern(self):
        o = self.order + self.ord * (3 + self.states + self.spk)
        if self.spk and self.arm == "spk":
            lead = self.p[o + 3 + self.states]      # the speaker's own lead
        else:
            lead = self.p[o + 3 + (self.state if self.states > 1 else 0)]
        for c, ph in ((CH_LEAD, lead), (CH_BASS, self.p[o]),
                      (CH_CHORD, self.p[o + 1]), (CH_DRUM, self.p[o + 2])):
            ch = self.ch[c]
            ch.wait = 0
            ch.ptr = 0 if ph == PH_NONE else u16(self.p, self.ptab + 2 * ph)

    # --- the per-tick step ---------------------------------------------------
    def step(self):
        acts = []
        if self.finished:
            return acts
        if self.tleft == 0:
            if self.row == self.rows:
                nxt = self.next_ord(self.ord)
                if nxt is None:
                    self.finished = True
                    return acts
                self.row = 0
                self.ord = nxt
                self.load_pattern()
            for c in range(4):
                ch = self.ch[c]
                if ch.wait == 0:
                    self.event(c, acts)
                ch.wait -= 1
            self.row += 1
            self.tleft = self.groove[self.gi]
            self.gi += 1
            if self.gi == self.glen:
                self.gi = 0
        self.tleft -= 1
        for c in range(4):
            self.chtick(c, acts)
        self.tick += 1
        return acts

    def event(self, c, acts):
        ch = self.ch[c]
        if ch.ptr == 0:                  # a silent channel for the pattern
            ch.wait = 255
            return
        p = self.p
        while True:
            b = p[ch.ptr]
            ch.ptr += 1
            if b == EV_END:
                ch.ptr -= 1
                ch.wait = 255
                return
            if b & 0xE0 == EV_INST:
                ch.inst = b & 0x1F
            elif b & 0xE0 == EV_SHAPE:
                ch.shape = b & 0x1F
            elif b == EV_SLUR:
                ch.slur = 1
            elif b == EV_REST:
                ch.wait = p[ch.ptr]
                ch.ptr += 1
                self.off(c, acts)
                self.notes_log.append((self.tick, c, 0))
                return
            elif b < 0x80:
                ch.wait = p[ch.ptr]
                ch.gate = p[ch.ptr + 1]
                ch.ptr += 2
                self.on(c, b, acts)
                self.notes_log.append((self.tick, c, b))
                return
            else:
                raise ScoreError("bad event byte %02x" % b)

    def rec(self, i):
        return self.insts + INST_REC * i

    def on(self, c, note, acts):
        ch = self.ch[c]
        slur = ch.slur and ch.note != 0
        ch.slur = 0
        ch.note = note
        ch.fresh = 1
        ch.age = 0
        if self.arm == "spk":
            if c == CH_LEAD:
                ch.last_f = self.spk_hz(ch)
                acts.append(("spk", ch.last_f, ch.gate))
            return
        voices = FM_VOICES[c]
        notes = [note]
        if c == CH_CHORD:
            s = self.shapes + 2 * ch.shape
            notes += [note + self.p[s] if self.p[s] else 0,
                      note + self.p[s + 1] if self.p[s + 1] else 0]
        for v, n in zip(voices, notes):
            if n == 0:
                if self.fmkeyed[v]:
                    acts.append(("fm", v, 1, 0))
                    self.fmkeyed[v] = False
                continue
            if self.fmpatch[v] != ch.inst:
                if self.fmkeyed[v]:
                    acts.append(("fm", v, 1, 0))
                    self.fmkeyed[v] = False
                acts.append(("fm", v, 2, bytes(self.p[self.rec(ch.inst):self.rec(ch.inst) + 11])))
                self.fmpatch[v] = ch.inst
            elif self.fmkeyed[v] and not slur:
                acts.append(("fm", v, 1, 0))       # retrigger: the envelope
            acts.append(("fm", v, 0, self.hz(n)))   # restarts only on a key-on
            self.fmkeyed[v] = True

    def off(self, c, acts):
        ch = self.ch[c]
        if ch.note == 0:
            return
        ch.note = 0
        ch.slur = 0
        if self.arm == "spk":
            if c == CH_LEAD:
                acts.append(("spk", 0, 0))
            return
        for v in FM_VOICES[c]:
            if self.fmkeyed[v]:
                acts.append(("fm", v, 1, 0))
                self.fmkeyed[v] = False

    def spk_hz(self, ch):
        """the lead's frequency THIS tick: macro offset, then vibrato"""
        r = self.rec(ch.inst)
        vdel, vsh, mlen, mloop, midx = self.p[r + 11:r + 16]
        a = ch.age
        if a >= mlen:
            a = mloop + (a - mloop) % (mlen - mloop) if mlen > mloop else mlen - 1
        off = self.p[self.macros + midx + a]
        off = off - 256 if off > 127 else off
        n = max(NOTE0, min(NOTE0 + NNOTE - 1, ch.note + off))
        f = self.hz(n)
        if vsh and ch.age >= vdel:
            d = f >> vsh
            f = f + d if ((ch.age - vdel) >> 1) & 1 == 0 else f - d
        return f

    def chtick(self, c, acts):
        ch = self.ch[c]
        if ch.note == 0:
            return
        if ch.fresh:
            ch.fresh = 0
            return
        ch.age += 1
        ch.gate -= 1
        if ch.gate == 0:
            self.off(c, acts)
            return
        if self.arm == "spk" and c == CH_LEAD:
            r = self.rec(ch.inst)
            if self.p[r + 12] or self.p[r + 13] > 1:      # a vibrato or a macro
                f = self.spk_hz(ch)
                if f != ch.last_f:
                    acts.append(("spk", f, ch.gate))
                ch.last_f = f

    def song_ticks(self):
        """ticks for one pass of the order, intro included - and for a piece
           with a tail, its whole order played straight through once"""
        rt = row_ticks([g for g in self.groove[:self.glen]], self.rows)
        return rt[-1] * self.ordlen


# ---------------------------------------------------------------------------
# RENDERING - an approximation, and TITHE-PLAN 13.10 says so
# ---------------------------------------------------------------------------

RATE = 44100


def run_actions(part, song, arm, ticks):
    sq = Seq(part, song, arm)
    return [sq.step() for _ in range(ticks)], sq


def render_spk(tick_acts):
    """PIT channel 2 in mode 3: a square at 1193182/divisor. The kernel's
       duration expiry is snd_tick's, a whole tick."""
    import numpy as np
    spt = RATE / TICK_HZ
    n = int(len(tick_acts) * spt) + 1
    out = np.zeros(n, dtype=np.float32)
    f, left, phase = 0, 0, 0.0
    for t, acts in enumerate(tick_acts):
        if left > 0:
            left -= 1
            if left == 0:
                f = 0
        for a in acts:
            if a[0] == "spk":
                f = 0 if a[1] == 0 else PIT_HZ / (PIT_HZ // a[1])
                left = a[2]
        a0, a1 = int(t * spt), int((t + 1) * spt)
        if f:
            ph = phase + np.arange(a1 - a0) * f / RATE
            out[a0:a1] = np.where((ph % 1.0) < 0.5, 0.22, -0.22)
            phase = (phase + (a1 - a0) * f / RATE) % 1.0
    # the cone: a gentle one-pole low-pass, so the render is not a razor
    from scipy.signal import lfilter
    a = 0.35
    return lfilter([a], [1, a - 1], out).astype(np.float32)


OPL_SLOT = [0, 1, 2, 8, 9, 10, 16, 17, 18]
OPL_OPREG = [0x20, 0x40, 0x60, 0x80, 0xE0]


def opl_fnum(hz):
    """opl_keyon's arithmetic, to the bit (drivers/sound/sound.asm)"""
    fmax = [48, 97, 194, 388, 776, 1552, 3104, 6208]
    for b, m in enumerate(fmax):
        if hz <= m:
            return b, (hz << (20 - b)) // 49716
    raise ScoreError("%d Hz is above the OPL2's ceiling" % hz)


def render_fm(tick_acts):
    try:
        import pyopl
    except ImportError:
        raise ScoreError("the FM render wants pyopl (DOSBox's OPL2): pip install pyopl")
    import numpy as np
    o = pyopl.opl(RATE, 2, 1)
    b0 = [0] * 9

    def wr(r, v):
        o.writeReg(r, v)
    # SOUND.DRV's init (opl_probe): WSE on, melodic, the default patch
    wr(0x01, 0x20)
    wr(0xBD, 0x00)
    defp = [0x21, 0x28, 0xF0, 0x07, 0x00, 0x21, 0x00, 0xF0, 0x07, 0x01, 0x00]

    def patch(v, pb):
        s = OPL_SLOT[v]
        for k in range(5):
            wr(OPL_OPREG[k] + s, pb[k])
        for k in range(5):
            wr(OPL_OPREG[k] + s + 3, pb[5 + k])
        wr(0xC0 + v, pb[10])
    for v in range(9):
        patch(v, defp)
    spt = RATE / TICK_HZ
    chunks, done = [], 0
    for t, acts in enumerate(tick_acts):
        for a in acts:
            if a[0] != "fm":
                continue
            _, v, verb, arg = a
            if verb == 2:
                patch(v, arg)
            elif verb == 1:
                b0[v] &= 0xDF
                wr(0xB0 + v, b0[v])
            elif verb == 0:
                blk, fn = opl_fnum(arg)
                wr(0xA0 + v, fn & 0xFF)
                b0[v] = ((fn >> 8) & 3) | (blk << 2) | 0x20
                wr(0xB0 + v, b0[v])
        want = int((t + 1) * spt) - done
        done += want
        while want > 0:                 # pyopl fills 512 samples at most
            k = min(want, 512)
            buf = bytearray(k * 2)
            o.getSamples(buf)
            chunks.append(np.frombuffer(bytes(buf), dtype="<i2").astype(np.float32) / 32768.0)
            want -= k
    return np.concatenate(chunks)


def write_wav(path, y):
    import numpy as np
    y = np.clip(y, -1, 1)
    pcm = (y * 32000).astype("<i2").tobytes()
    with open(path, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt ")
        f.write(struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16))
        f.write(b"data" + struct.pack("<I", len(pcm)) + pcm)


def fade_tail(y, secs):
    import numpy as np
    n = min(len(y), int(secs * RATE))
    if n:
        y[-n:] *= np.linspace(1, 0, n)
    return y


def wav(ids, arms, secs, outdir, state=0):
    part, songs, _, _, _ = build_part()
    os.makedirs(outdir, exist_ok=True)
    for si, s in enumerate(songs):
        if ids and s.id not in ids:
            continue
        sq = Seq(part, si, "spk")
        one = sq.song_ticks()
        loop_ticks = one - (row_ticks(s.groove, s.rows)[-1] * s.loop)
        ticks = int(secs * TICK_HZ) if secs else one + min(loop_ticks, int(8 * TICK_HZ))
        for arm in arms:
            if s.tail:                  # a RESOLUTION: the hit, the body
                acts = []               # twice, then the tail, and done
                sq = Seq(part, si, arm)
                ptick = row_ticks(s.groove, s.rows)[-1]
                while not sq.finished and len(acts) < 4000:
                    if sq.ord == s.tail - 1 and len(acts) > ptick * (2 * s.tail - 2):
                        sq.end()
                    acts.append(sq.step())
            else:
                sq = Seq(part, si, arm, state=min(state, s.states - 1))
                acts = [sq.step() for _ in range(ticks)]
            y = render_spk(acts) if arm == "spk" else render_fm(acts)
            y = fade_tail(y, 3.0)
            path = os.path.join(outdir, "%s%s-%s.wav" % (
                s.id, "-s%d" % state if state and s.states > 1 else "", arm))
            write_wav(path, y)
            print("%s: %s, %.1f s (one pass %.1f s)" % (path, s.name, len(y) / RATE,
                                                       one / TICK_HZ))


# ---------------------------------------------------------------------------
# emit, list, selfcheck
# ---------------------------------------------------------------------------

def emit(inc_path, bin_path):
    part, songs, insts, iorder, _ = build_part()
    os.makedirs(os.path.dirname(bin_path), exist_ok=True)
    open(bin_path, "wb").write(part)
    L = ["; GENERATED by tools/os88tithemus.py - do not edit.",
         "; TITHE's MUSIC (SPEC.md 97.10): the numbers the sequencer, timus.inc,",
         "; reads the MUSIC PART by, and the names the window shows. The part",
         "; itself is timus.bin in the build tree, built from apps/tithe/music/.",
         "",
         "TM_NSONG    equ %d                   ; the songs `M` steps through..." % len(SONGS),
         "TM_NRES     equ %d                   ; ...and the resolutions after them" % len(RESOLUTIONS),
         ] + ["TM_R_%-7s equ %d                   ; `E`'s index of %s, for the board table"
              % (f[:-4].upper(), i, f) for i, f in enumerate(RESOLUTIONS)] + [
         "TM_NOTE0    equ %d                  ; the frequency table's first note (C1)" % NOTE0,
         "TM_NNOTE    equ %d" % NNOTE,
         "TM_INSTREC  equ %d                  ; an instrument record's bytes" % INST_REC,
         "TM_P_SIZE   equ %d                ; bytes in the part" % len(part),
         "",
         "; the part's own layout (SPEC.md 97.10.2) - this tool is its one source",
         "TMP_FREQ    equ 4                   ; dw: the frequency table",
         "TMP_INST    equ 6                   ; dw: the instrument records",
         "TMP_MACRO   equ 8                   ; dw: the speaker macro pool",
         "TMP_SHAPE   equ 10                  ; dw: the chord shapes, 2 bytes each",
         "TMP_SONGS   equ 12                  ; dw each: a song's header",
         "TMS_GLEN    equ 0                   ; a song header: the groove's length,",
         "TMS_GROOVE  equ 1                   ; ...its four tick counts,",
         "TMS_ROWS    equ 5                   ; ...rows a pattern,",
         "TMS_STATES  equ 6                   ; ...leads an order row carries,",
         "TMS_ORDLEN  equ 7                   ; ...order rows,",
         "TMS_LOOP    equ 8                   ; ...the row the order loops to,",
         "TMS_TAIL    equ 9                   ; ...the row the TAIL starts at (0: none),",
         "TMS_SPK     equ 14                  ; ...1: every order row ends in a SPEAKER lead",
         "TMS_ORDER   equ 10                  ; ...dw the order,",
         "TMS_PTAB    equ 12                  ; ...dw the phrase table",
         "TMI_VDELAY  equ 11                  ; an instrument: the vibrato's delay,",
         "TMI_VSHIFT  equ 12                  ; ...its depth as a shift (0 = none),",
         "TMI_MLEN    equ 13                  ; ...the macro's length,",
         "TMI_MLOOP   equ 14                  ; ...where it loops,",
         "TMI_MIDX    equ 15                  ; ...and where it is in the pool",
         "TME_REST    equ 0x%02X                ; an event: a rest, rows" % EV_REST,
         "TME_INST    equ 0x%02X                ; ...| instrument" % EV_INST,
         "TME_SHAPE   equ 0x%02X                ; ...| chord shape" % EV_SHAPE,
         "TME_SLUR    equ 0x%02X                ; ...the next note slurs" % EV_SLUR,
         "TME_END     equ 0x%02X                ; ...the phrase is over" % EV_END,
         "TM_PHNONE   equ 0x%02X                ; an order row's silent channel" % PH_NONE,
         "",
         "; the window's title per song, in the order `M` steps through them,",
         "; then the resolutions' in the order `E` does",
         "tm_names:"]
    L += ["    dw tm_name%d" % i for i in range(len(songs))]
    for i, s in enumerate(songs):
        L.append("tm_name%d: db 'Tithe - %s', 0" % (i, s.name.replace("'", "`")))
    L += ["",
          "; ...and how many BATTLE STATES each has (TITHE-PLAN 13.4), so the",
          "; title can name the one playing where there is more than one",
          "tm_nstates: db %s" % ", ".join(str(s.states) for s in songs)]
    open(inc_path, "w").write("\n".join(L) + "\n")
    print("%s + %s: %d songs, %d instruments, %d bytes of score"
          % (inc_path, bin_path, len(songs), len(iorder), len(part)))


def listing():
    part, songs, insts, iorder, drums = build_part()
    print("MUSIC part: %d bytes, %d instruments, %d songs" % (len(part), len(iorder), len(songs)))
    for si, s in enumerate(songs):
        sq = Seq(part, si, "spk")
        one = sq.song_ticks() / TICK_HZ
        rows_s = TICK_HZ * len(s.groove) / sum(s.groove)
        nxt = u16(part, 12 + 2 * (si + 1)) if si + 1 < len(songs) else len(part)
        print("  %-12s %-28s %5.1f s a pass, %d patterns of %d rows, %.2f rows/s, %d bytes"
              % (s.id, '"%s"' % s.name, one, len(s.order), s.rows, rows_s,
                 nxt - u16(part, 12 + 2 * si)))


def expected_log(s, arm="fm", state_of=lambda oi: 0):
    """the (tick, channel, note) stream the SOURCE says - the independent side.
       state_of(order row) is the battle state that row's lead was chosen in"""
    rt = row_ticks(s.groove, s.rows)
    ptick = rt[-1]
    out = []
    kinds = [CH_LEAD, CH_BASS, CH_CHORD, CH_DRUM]
    for oi, (leads, b, c, d, spk) in enumerate(s.order):
        names = [spk if (spk and arm == "spk") else leads[state_of(oi)], b, c, d]
        for kind, nm in zip(kinds, names):
            if nm == "-":
                continue
            for e in s.phrases[nm][1]:
                out.append((oi * ptick + rt[e.row], kind, e.notes[0] if e.notes else 0))
    return sorted(out)


def selfcheck():
    bad = []
    part, songs, insts, iorder, drums = build_part()
    if part[:2] != DIR_MAGIC:
        bad.append("the part has no magic")
    ft = freq_table()
    for i, f in enumerate(ft):
        cents = 1200 * __import__("math").log2(f / hz_of(NOTE0 + i))
        if abs(cents) > 45:
            bad.append("note %d rounds %.0f cents off" % (NOTE0 + i, cents))
    for si, s in enumerate(songs):
        sq = Seq(part, si, "fm")
        ticks = sq.song_ticks()
        for _ in range(ticks):
            if s.tail and sq.ord == s.tail - 1:
                sq.end()                # straight through: the body, the tail
            sq.step()
        if s.tail:
            sq.step()                   # the boundary after the tail's last row
            if not sq.finished:
                bad.append("%s: the tail never finished" % s.id)
            # ...and never told to end, it must loop the body and never
            # reach the tail
            lp = Seq(part, si, "fm")
            for _ in range(ticks * 3):
                lp.step()
                if lp.ord >= s.tail or lp.finished:
                    bad.append("%s: reached its tail unasked" % s.id)
                    break
        else:
            # A SEEK lands where playing there does: the hand-back resumes a
            # theme with one (SPEC.md 97.10.6)
            rt = row_ticks(s.groove, s.rows)
            for o, r in ((min(2, len(s.order) - 1), s.rows // 2),
                         (len(s.order) - 1, s.rows - 1)):
                a = Seq(part, si, "fm")
                for _ in range(rt[-1] * o + rt[r]):
                    a.step()
                b = Seq(part, si, "fm")
                b.seek(o, r)
                if [c.note for c in a.ch] != [c.note for c in b.ch] or \
                        (a.ord, a.row) != (b.ord, b.row):
                    bad.append("%s: a seek to %d/%d is not where playing gets"
                               % (s.id, o, r))
        got = sorted(sq.notes_log)
        # the model logs a rest only where a note was sounding; the source
        # names every rest - compare the NOTES, and the rests the model kept
        exp = expected_log(s)
        exp_notes = [e for e in exp if e[2]]
        got_notes = [g for g in got if g[2]]
        if exp_notes != got_notes:
            for a, b in zip(exp_notes, got_notes):
                if a != b:
                    bad.append("%s: the part plays %s where the source says %s" % (s.id, b, a))
                    break
            else:
                bad.append("%s: %d notes in the part against %d in the source"
                           % (s.id, len(got_notes), len(exp_notes)))
        for st in range(1, s.states):   # ...every BATTLE STATE the same way
            q = Seq(part, si, "fm", state=st)
            for _ in range(ticks):
                q.step()
            g = sorted(x for x in q.notes_log if x[2])
            e = [x for x in expected_log(s, state_of=lambda oi, st=st: st) if x[2]]
            if g != e:
                bad.append("%s: state %d plays %d notes against the source's %d"
                           % (s.id, st, len(g), len(e)))
        if s.states > 1:                # ...and a state change lands at the
            rt = row_ticks(s.groove, s.rows)    # NEXT pattern boundary and not
            sw = {2: 1, 5: 2}                   # before it: switched half-way
            q = Seq(part, si, "fm")             # through order rows 1 and 4
            for t in range(ticks):
                o = t // rt[-1]
                if t % rt[-1] == rt[-1] // 2 and o + 1 in sw:
                    q.state = sw[o + 1]
                q.step()

            def st_of(oi):
                return 2 if oi >= 5 else 1 if oi >= 2 else 0
            g = sorted(x for x in q.notes_log if x[2])
            e = [x for x in expected_log(s, state_of=st_of) if x[2]]
            if g != e:
                bad.append("%s: a state change does not wait for the pattern "
                           "boundary" % s.id)
        if s.order[0][4]:               # ...and the SPEAKER's own lead, the
            sp = Seq(part, si, "spk")   # same way against its own source
            for _ in range(ticks):
                if s.tail and sp.ord == s.tail - 1:
                    sp.end()
                sp.step()
            g2 = sorted(x for x in sp.notes_log if x[2] and x[1] == CH_LEAD)
            e2 = [x for x in expected_log(s, "spk") if x[2] and x[1] == CH_LEAD]
            if g2 != e2:
                bad.append("%s: the speaker lead plays %d notes against the "
                           "source's %d" % (s.id, len(g2), len(e2)))
        # every lead note fits the speaker and every FM note the OPL2
        for (t, c, n) in exp_notes:
            if hz_of(n) > 6208 or hz_of(n) < 19:
                bad.append("%s: note %d is outside the OPL2's 19..6208 Hz" % (s.id, n))
                break
        # the loop comes back to the same tick grid: a pattern is whole grooves
        if s.rows % len(s.groove):
            bad.append("%s: the groove does not divide the pattern" % s.id)
        # the speaker arm: every tone carries a DURATION, so a stalled worker
        # can never leave the speaker droning (SPEC.md 97.10.5)
        sp = Seq(part, si, "spk")
        for _ in range(ticks):
            for a in sp.step():
                if a[1] and not a[2]:
                    bad.append("%s: a speaker tone with no duration" % s.id)
                    break
    # the tone and FM render paths agree about frequency arithmetic
    for hz in (41, 82, 440, 1046, 3000, 6208):
        b, fn = opl_fnum(hz)
        if not 0 < fn <= 1023:
            bad.append("F-Number %d for %d Hz" % (fn, hz))
    inc = os.path.join(ROOT, "apps", "tithe", "tisong.inc")
    if os.path.exists(inc):
        txt = open(inc).read()
        if "TM_P_SIZE   equ %d " % len(part) not in txt:
            bad.append("apps/tithe/tisong.inc is stale - run `%s emit`" % sys.argv[0])
    for b in bad:
        print("FAIL", b)
    print("os88tithemus selfcheck: %d songs, %d bytes, %s"
          % (len(songs), len(part), "FAIL" if bad else "ok"))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", nargs="?", default="list", choices=["emit", "wav", "list"])
    ap.add_argument("songs", nargs="*")
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--bin", default=os.path.join("build", "timus.bin"))
    ap.add_argument("--arm", choices=["spk", "fm", "both"], default="both")
    ap.add_argument("--secs", type=float, default=0.0)
    ap.add_argument("--state", type=int, default=0,
                    help="wav: the battle state, 0 normal, 1 pressed, 2 ascendant")
    ap.add_argument("--out", default=os.path.join("build", "tithemus"))
    a = ap.parse_args()
    try:
        if a.selfcheck:
            return selfcheck()
        if a.cmd == "emit":
            emit(os.path.join(ROOT, "apps", "tithe", "tisong.inc"), a.bin)
        elif a.cmd == "wav":
            wav(a.songs, ["spk", "fm"] if a.arm == "both" else [a.arm], a.secs, a.out,
                a.state)
        else:
            listing()
    except ScoreError as e:
        print("os88tithemus: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
