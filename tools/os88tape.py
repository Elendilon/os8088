#!/usr/bin/env python3
"""os88tape - the HOST reference codec for os8088's cassette tape format.

SPEC.md 88 is the contract; docs/plans/CASSETTE-PLAN.md 4 is the design record
behind it.  This file is to the tape what tools/os88lz.py is to the compressed
stream and tools/weavesim.py is to the .WAB bundle: an independent second
implementation, written from the contract rather than from the assembly, so
that the machine's output can be checked BYTE FOR BYTE rather than by eye.

It matters more here than anywhere else in the tree.  No emulator in this
project can execute a cassette read at all - MartyPC's PPI returns a hardwired
zero for the cassette data line whenever the motor is on
(build/martypc/src/crates/marty_core/src/devices/ppi.rs:856-864, `// TODO:
Implement cassette data input`) - so a host codec that agrees with the format
is most of the verification the format is ever going to get before it meets a
real deck.  The format is therefore settled HERE, before a byte of 8086 is
written.

TWO ROMS, and `--rom` is not optional.  A record laid down by GLaBIOS opens
with one zero START BIT that the IBM 5150 ROM does not emit (GLABIOS.ASM:11448
against PCBIOS.ASM:5324-5331), so a 256-zero-byte record is 4,153 bits from an
IBM machine and 4,154 from a GLaBIOS twin.  It does not affect interoperability
- each reader searches for the leader and a stray zero bit in front of it is
simply not leader - but a golden built for one ROM never matches the other, and
86Box's cassette machines are `ibmpc`/`ibmpc82`, i.e. the IBM ROM.

WHAT IT DOES:
    build      a file  -> a tape image (the BIOS bit stream, or a .cas)
    parse      a tape image -> the records on it, validated
    selfcheck  round-trip every fixture, re-derive every timing table SPEC.md
               88 quotes, and check the CRC against its published residue

THE TABLES ARE PRINTED, NOT TYPED.  docs/plans/CASSETTE-PLAN.md 0.4 fixes seven
constants and every wall-clock figure in SPEC.md 88 is derived from them; a
hand-computed table is what put two unrepresentable `lastblk` values into an
earlier draft of the design.  `--selfcheck` regenerates them so the document
can be checked against arithmetic instead of against somebody's memory.
"""

import argparse
import os
import struct
import sys

# --- the bit timings (docs/plans/CASSETTE-PLAN.md 0.4) -----------------------
# The PIT's input clock, and the two divisors the BIOS writes into channel 2.
# A bit is ONE FULL CYCLE of the square wave at that divisor, so its period is
# divisor / PIT_HZ seconds.  These are the ROM's own numbers: GLABIOS.ASM:809
# (`BEEP_1K7 EQU 1184`) and its half for a zero.
PIT_HZ = 1193182.0
DIV_ONE = 1184                      # bit 1 = ~1007 Hz = 992.30 us
DIV_ZERO = 592                      # bit 0 = ~2015 Hz = 496.15 us
SEC_ONE = DIV_ONE / PIT_HZ
SEC_ZERO = DIV_ZERO / PIT_HZ

# The record's fixed furniture (CASSETTE-PLAN 4.1).
LEADER_BITS = 2048                  # 256 bytes of FFh
SYNC_BYTE = 0x16                    # written MSB first, after one zero sync bit
TRAILER_BITS = 32                   # 4 bytes of FFh
BLOCK = 256                         # the BIOS's data block, and its CRC unit

# The fixed per-record cost the design quotes, in seconds, by ROM.  These are
# NOT derived from the bit timings alone: they include the motor spin-up, which
# is a CPU loop on IBM (PCBIOS.ASM:5489-5500, 421.3 ms at 4.772728 MHz) and a
# PIT-delta wait on GLaBIOS (GLABIOS.ASM:11386-11402).
TP_FIX = {"ibm": 2.4912, "glabios": 2.5704}
TP_FIX_QUOTED = 2.60                # what the UI's estimate uses, rounded UP:
                                    # an estimate that runs late on a stopped
                                    # machine is the wrong direction of error

# --- the format (CASSETTE-PLAN 4.2, 4.3) -------------------------------------
HDR_MAGIC = b"O8TP"
BODY_MAGIC = b"OT"
TP_VER = 1
TP_KIND_FILE = 0
TP_MAXFILE = 32768

F_CZ = 0x01                         # payload is a 'CZ' container THIS writer made
F_PRECOMP = 0x02                    # payload was already compressed on disk
F_LZB = 0x04                        # when F_CZ: 0 = LZ4, 1 = LZB
F_KNOWN = F_CZ | F_PRECOMP | F_LZB

HDR_SIZE = BLOCK                    # the header record is EXACTLY one block
BODY_PRE = 8                        # 'OT', seq, nrec, paylen, ckfile


class TapeError(Exception):
    """A tape that cannot be trusted.  Every message names the field."""


# =============================================================================
# CRC-16/CCITT - the BIOS's own, and the file's
# =============================================================================
# Preset 0xFFFF, polynomial 0x1021, MSB-first, no reflection.  Derived from
# CRC_GEN (PCBIOS.ASM:5460-5487 - the RCR/RCL overflow trick plus XOR 0810h
# plus RCL IS poly 0x1021) and confirmed against GLaBIOS's named constants
# CAS_CRC_PRE / CAS_CRC_RES / CAS_CRC_POLY.
#
# ONE algorithm, two uses, and the difference is only what happens at the end:
#   * the BIOS transmits it ONE'S-COMPLEMENTED, high byte first, and a reader
#     that runs the received bytes through the same register lands on the
#     residue 0x1D0F;
#   * `ckfile` (CASSETTE-PLAN 4.4) is the SAME register over the payload, NOT
#     complemented.
# Bit-serial rather than table-driven on purpose: the machine pays ~100 clocks
# a byte, which is 0.7 s over 32 KB against a 309-second transfer, and a
# 256-entry table would spend 512 bytes of a package to save half a second.
CRC_PRE = 0xFFFF
CRC_POLY = 0x1021
CRC_RESIDUE = 0x1D0F


def crc16(data, crc=CRC_PRE):
    """The register, MSB-first, one bit at a time."""
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ CRC_POLY) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def crc_on_wire(data):
    """What the BIOS appends after a 256-byte block: complemented, high first."""
    c = crc16(data) ^ 0xFFFF
    return bytes(((c >> 8) & 0xFF, c & 0xFF))


def crc_check_block(block_and_crc):
    """A block plus its two CRC bytes leaves the register at CRC_RESIDUE."""
    return crc16(block_and_crc) == CRC_RESIDUE


# =============================================================================
# The bit stream
# =============================================================================
class BitWriter:
    """Bits in the order the tape sees them, MSB-first within a byte.

    A .cas file IS this stream packed MSB-first with no header of any kind
    (CASSETTE-PLAN 12.9), which is why 86Box can read what this writes.
    """

    def __init__(self):
        self.bits = bytearray()

    def bit(self, b):
        self.bits.append(1 if b else 0)

    def ones(self, n):
        self.bits.extend(b"\x01" * n)

    def byte(self, v):
        for i in range(7, -1, -1):      # MSB first
            self.bit((v >> i) & 1)

    def data(self, buf):
        for v in buf:
            self.byte(v)

    def seconds(self):
        """Wall-clock length of what has been written, at the ROM's timings."""
        ones = sum(self.bits)
        return ones * SEC_ONE + (len(self.bits) - ones) * SEC_ZERO

    def packed(self):
        """MSB-first into bytes; the tail is padded with zero bits."""
        out = bytearray()
        acc = 0
        n = 0
        for b in self.bits:
            acc = (acc << 1) | b
            n += 1
            if n == 8:
                out.append(acc)
                acc = 0
                n = 0
        if n:
            out.append((acc << (8 - n)) & 0xFF)
        return bytes(out)


def emit_record(bw, payload, rom):
    """One int 15h AH=03 call's worth: leader, sync, N blocks + CRC, trailer.

    `payload` must be a whole number of 256-byte blocks.  THIS CODEC NEVER PADS
    and neither does the machine (CASSETTE-PLAN 4.1): with CX a multiple of 256
    IBM's pad loop is never entered, which matters because IBM's pad re-reads
    the byte immediately AFTER the caller's buffer and writes it to tape up to
    255 times - an information leak onto removable media, not merely a
    non-determinism.
    """
    if len(payload) == 0 or len(payload) % BLOCK:
        raise TapeError(
            "a record is a whole number of 256-byte blocks; got %d" % len(payload))
    if rom == "glabios":
        bw.bit(0)                       # the START bit, GLaBIOS only
    bw.ones(LEADER_BITS)
    bw.bit(0)                           # the sync bit
    bw.byte(SYNC_BYTE)
    for off in range(0, len(payload), BLOCK):
        block = payload[off:off + BLOCK]
        bw.data(block)
        bw.data(crc_on_wire(block))
    bw.ones(TRAILER_BITS)


# =============================================================================
# The records
# =============================================================================
def _name_field(name):
    """The SPEC.md 19.1 display form: 8.3, NUL-terminated inside 12 bytes."""
    try:
        raw = name.upper().encode("ascii", "strict")
    except UnicodeEncodeError:
        # A refusal is a normal path and it names the field.  Letting Python's
        # own exception out would make a malformed name look like a crash in
        # the codec rather than a bad tape.
        raise TapeError("name %r is not ASCII" % name)
    if len(raw) > 11:
        raise TapeError("name %r is longer than 8.3" % name)
    for ch in raw:
        if not 0x21 <= ch <= 0x7E:
            raise TapeError("name %r has a byte outside 0x21..0x7E" % name)
    return raw + b"\0" * (12 - len(raw))


def geometry(size, recblk):
    """nrec and lastblk, derived - never chosen (CASSETTE-PLAN 4.3).

    Both are recomputed by the reader from the header alone and compared, so a
    tape that disagrees with its own arithmetic is refused rather than trusted.
    """
    cap = recblk * BLOCK - BODY_PRE             # a full record's payload
    nrec = (size + cap - 1) // cap
    tail = size - (nrec - 1) * cap              # the last record's payload
    lastblk = (tail + BODY_PRE + BLOCK - 1) // BLOCK
    return nrec, lastblk, cap


def build_header(name, payload, recblk, flags, usize):
    size = len(payload)
    if not 1 <= size <= TP_MAXFILE:
        raise TapeError("size %d is outside 1..%d" % (size, TP_MAXFILE))
    if not 1 <= recblk <= 16:
        raise TapeError("recblk %d is outside 1..16" % recblk)
    if flags & ~F_KNOWN:
        raise TapeError("flags 0x%02X sets a bit above bit 2" % flags)
    nrec, lastblk, _ = geometry(size, recblk)
    if nrec > 255:
        raise TapeError("%d body records; the field holds 255" % nrec)
    hdr = bytearray(HDR_SIZE)                   # zero, and the pad IS written
    hdr[0:4] = HDR_MAGIC
    hdr[4] = TP_VER
    hdr[5] = TP_KIND_FILE
    hdr[6] = flags
    hdr[7] = recblk
    hdr[8] = lastblk
    hdr[9] = nrec
    struct.pack_into("<H", hdr, 10, crc16(payload))
    hdr[12:24] = _name_field(name)
    struct.pack_into("<I", hdr, 24, size)
    struct.pack_into("<I", hdr, 28, usize)
    return bytes(hdr)


def build_bodies(payload, recblk):
    """The body records, in order."""
    size = len(payload)
    nrec, lastblk, cap = geometry(size, recblk)
    ck = crc16(payload)
    out = []
    off = 0
    for seq in range(1, nrec + 1):
        blocks = recblk if seq < nrec else lastblk
        room = blocks * BLOCK - BODY_PRE
        chunk = payload[off:off + min(room, cap)]
        off += len(chunk)
        rec = bytearray(blocks * BLOCK)         # the tail past paylen is ZERO
        rec[0:2] = BODY_MAGIC
        rec[2] = seq
        rec[3] = nrec
        struct.pack_into("<H", rec, 4, len(chunk))
        struct.pack_into("<H", rec, 6, ck)
        rec[BODY_PRE:BODY_PRE + len(chunk)] = chunk
        out.append(bytes(rec))
    if off != size:
        raise TapeError("internal: laid down %d of %d payload bytes" % (off, size))
    return out


def build(name, payload, rom="ibm", recblk=4, flags=0, usize=None):
    """A whole tape image for one file: the header record, then the bodies."""
    usize = len(payload) if usize is None else usize
    hdr = build_header(name, payload, recblk, flags, usize)
    bw = BitWriter()
    emit_record(bw, hdr, rom)
    for rec in build_bodies(payload, recblk):
        emit_record(bw, rec, rom)
    return bw


# =============================================================================
# Reading it back
# =============================================================================
def _sync_at(bits, i):
    """Scan from `i` for leader+sync.  Returns the bit index of the first data
    bit, or None.

    The ROM's own test: at least 256 consecutive one-bits, then a zero (the
    sync bit), then the sync byte 0x16 MSB-first.  256 and not 2,048 - the
    reader needs only an eighth of what the writer lays down
    (CASSETTE-PLAN 4.1), which is the 8x margin that lets records sit
    back-to-back.
    """
    n = len(bits)
    while i < n:
        run = 0
        while i < n and bits[i]:
            run += 1
            i += 1
        if run < 256 or i >= n:
            i += 1
            continue
        j = i + 1                               # consume the sync bit
        if j + 8 > n:
            return None
        val = 0
        for k in range(8):
            val = (val << 1) | bits[j + k]
        if val == SYNC_BYTE:
            return j + 8
        i = j                                   # not ours; keep scanning
    return None


def _read_record(bits, i, nblocks):
    """Read EXACTLY `nblocks` blocks from a synced position.

    THE LENGTH IS DECLARED, NEVER DISCOVERED - CASSETTE-PLAN 4.5's invariant,
    and this is where a host decoder gets it wrong if it is written as a
    scanner.  An all-0xFF payload contains 256 consecutive one-bits and so
    looks exactly like a leader (4.6); a reader that re-scanned between blocks
    would split the record there.  The machine does not, because the header
    told it how many blocks to take, and neither does this.

    Returns (payload, next_bit_index).  Raises on a CRC failure, which is what
    the ROM reports as AH=1.
    """
    out = bytearray()
    for blk in range(nblocks):
        need = (BLOCK + 2) * 8
        if i + need > len(bits):
            raise TapeError("the tape ends inside block %d of %d" % (blk + 1, nblocks))
        chunk = bytearray()
        for byte_i in range(BLOCK + 2):
            v = 0
            base = i + byte_i * 8
            for k in range(8):
                v = (v << 1) | bits[base + k]
            chunk.append(v)
        raw = bytes(chunk)
        if not crc_check_block(raw):
            raise TapeError("CRC error in block %d of %d - the block was "
                            "recovered but is damaged" % (blk + 1, nblocks))
        out.extend(raw[:BLOCK])
        i += need
    return bytes(out), i


def parse(bw_or_bits, rom="ibm"):
    """A tape image -> (header dict, payload).  Every field is checked."""
    bits = bw_or_bits.bits if isinstance(bw_or_bits, BitWriter) else bw_or_bits
    at = _sync_at(bits, 0)
    if at is None:
        raise TapeError("no record found: no leader, or no sync byte after one")
    # THE CLASSIFY READ: exactly one block, which consumes a header exactly and
    # leaves the tape at the first body record (CASSETTE-PLAN 4.5).
    hdr, at = _read_record(bits, at, 1)
    if hdr[0] == 0xA5:
        # Recognised, never written (CASSETTE-PLAN 4.7).
        who = hdr[1:9].decode("ascii", "replace").rstrip()
        raise TapeError("IBM Cassette BASIC record %r - not an os8088 tape" % who)
    if hdr[0:4] != HDR_MAGIC:
        raise TapeError("bad magic %r" % bytes(hdr[0:4]))
    if hdr[4] != TP_VER:
        raise TapeError("version %d is not %d - refused, never guessed" % (hdr[4], TP_VER))
    if hdr[5] != TP_KIND_FILE:
        raise TapeError("kind %d is not a file" % hdr[5])
    flags = hdr[6]
    if flags & ~F_KNOWN:
        raise TapeError("flags 0x%02X sets a bit above bit 2" % flags)
    recblk, lastblk, nrec = hdr[7], hdr[8], hdr[9]
    if not 1 <= recblk <= 16:
        raise TapeError("recblk %d is outside 1..16" % recblk)
    if not 1 <= lastblk <= recblk:
        raise TapeError("lastblk %d is outside 1..recblk(%d)" % (lastblk, recblk))
    if not 1 <= nrec <= 255:
        raise TapeError("nrec %d is outside 1..255" % nrec)
    ckfile = struct.unpack_from("<H", hdr, 10)[0]
    name_raw = bytes(hdr[12:24])
    if 0 not in name_raw:
        raise TapeError("name field is not NUL-terminated inside 12 bytes")
    name = name_raw[:name_raw.index(0)].decode("ascii", "replace")
    for ch in name.encode("ascii", "replace"):
        if not 0x21 <= ch <= 0x7E:
            raise TapeError("name %r has a byte outside 0x21..0x7E" % name)
    size = struct.unpack_from("<I", hdr, 24)[0]
    usize = struct.unpack_from("<I", hdr, 28)[0]
    if not 1 <= size <= TP_MAXFILE:
        raise TapeError("size %d is outside 1..%d" % (size, TP_MAXFILE))

    # The geometry is DERIVED and compared - never trusted (CASSETTE-PLAN 4.3).
    want_nrec, want_lastblk, cap = geometry(size, recblk)
    if want_nrec != nrec:
        raise TapeError("nrec is %d; size/recblk derive %d" % (nrec, want_nrec))
    if want_lastblk != lastblk:
        raise TapeError("lastblk is %d; size/recblk derive %d" % (lastblk, want_lastblk))

    payload = bytearray()
    for seq in range(1, nrec + 1):
        blocks = recblk if seq < nrec else lastblk
        at = _sync_at(bits, at)
        if at is None:
            raise TapeError("header declares %d body records; the tape ends "
                            "after %d" % (nrec, seq - 1))
        rec, at = _read_record(bits, at, blocks)
        if rec[0:2] != BODY_MAGIC:
            raise TapeError("record %d has magic %r" % (seq, bytes(rec[0:2])))
        if rec[2] != seq:
            raise TapeError("record %d says it is %d" % (seq, rec[2]))
        if rec[3] != nrec:
            raise TapeError("record %d says nrec %d, header says %d" % (seq, rec[3], nrec))
        paylen = struct.unpack_from("<H", rec, 4)[0]
        room = blocks * BLOCK - BODY_PRE
        if not 1 <= paylen <= room:
            raise TapeError("record %d paylen %d is outside 1..%d" % (seq, paylen, room))
        if struct.unpack_from("<H", rec, 6)[0] != ckfile:
            # A record spliced in from a DIFFERENT file, caught the instant it
            # arrives rather than at the final checksum (CASSETTE-PLAN 4.4).
            raise TapeError("record %d belongs to a different file" % seq)
        payload.extend(rec[BODY_PRE:BODY_PRE + paylen])

    if len(payload) != size:
        raise TapeError("assembled %d bytes; header declares %d" % (len(payload), size))
    if crc16(payload) != ckfile:
        raise TapeError("file checksum mismatch: the tape is damaged")

    return {
        "name": name, "size": size, "usize": usize, "flags": flags,
        "recblk": recblk, "lastblk": lastblk, "nrec": nrec, "ckfile": ckfile,
    }, bytes(payload)


# =============================================================================
# Timing - the tables SPEC.md 88 quotes
# =============================================================================
def record_seconds(payload_len, rom, data_bits_ones=None):
    """Wall-clock for one record: the fixed cost plus its own bits."""
    bw = BitWriter()
    emit_record(bw, b"\0" * payload_len, rom)
    return TP_FIX[rom] + bw.seconds()


def file_seconds(size, recblk=4, rom="ibm", ones_per_byte=4.0):
    """A whole file, at a stated data density.

    `ones_per_byte` is the only thing that varies: a bit 1 is 992.30 us and a
    bit 0 is 496.15, so the SAME record is 1.024 s of all-zero data and 2.048 s
    of all-FF.  4.0 is compressed/random, 3.4 is plain text
    (CASSETTE-PLAN 0.4).
    """
    nrec, lastblk, cap = geometry(size, recblk)
    ms_per_byte = (ones_per_byte * SEC_ONE + (8 - ones_per_byte) * SEC_ZERO)
    total = TP_FIX_QUOTED + (HDR_SIZE + 2) * ms_per_byte    # the header record
    for seq in range(1, nrec + 1):
        blocks = recblk if seq < nrec else lastblk
        total += TP_FIX_QUOTED + blocks * (BLOCK + 2) * ms_per_byte
    return total, nrec


def _fmt_mmss(s):
    return "%d:%02d" % (int(s) // 60, int(s) % 60)


def print_tables():
    print("os88tape: the timing tables SPEC.md 88 quotes, re-derived\n")
    print("  bit 0 = %.2f us (divisor %d)   bit 1 = %.2f us (divisor %d)"
          % (SEC_ZERO * 1e6, DIV_ZERO, SEC_ONE * 1e6, DIV_ONE))
    print("  leader %d bits = %.4f s   trailer %d bits = %.4f s\n"
          % (LEADER_BITS, LEADER_BITS * SEC_ONE, TRAILER_BITS, TRAILER_BITS * SEC_ONE))

    print("  ms a byte, by data density:")
    for label, ones in (("all 00", 0), ("plain text", 3.4), ("compressed", 4.0), ("all FF", 8)):
        mspb = (ones * SEC_ONE + (8 - ones) * SEC_ZERO) * 1000.0
        print("    %-12s %5.2f ones/byte    %6.4f ms   one 258-byte block %6.3f s"
              % (label, ones, mspb, 258 * mspb / 1000.0))

    print("\n  the fixed cost of one record:")
    for rom in ("ibm", "glabios"):
        print("    %-9s %.4f s" % (rom, TP_FIX[rom]))
    print("    quoted    %.2f s   (rounded UP; over-predicts both)" % TP_FIX_QUOTED)

    print("\n  a whole file, recblk=4, compressed density:")
    print("    %8s %6s %10s %10s" % ("bytes", "nrec", "one way", "there+back"))
    for size in (1024, 4096, 8192, 16384, 32768):
        secs, nrec = file_seconds(size)
        print("    %8d %6d %10s %10s"
              % (size, nrec, _fmt_mmss(secs), _fmt_mmss(secs * 2)))


# =============================================================================
# selfcheck
# =============================================================================
def selfcheck():
    fails = []

    def check(name, cond, detail=""):
        if cond:
            print("  ok   %s" % name)
        else:
            print("  FAIL %s  %s" % (name, detail))
            fails.append(name)

    print("os88tape --selfcheck\n")

    # --- the CRC, against its own published residue --------------------------
    blk = bytes(range(256))
    check("CRC residue is 0x1D0F", crc_check_block(blk + crc_on_wire(blk)))
    check("CRC of all-zero block is not 0", crc16(b"\0" * 256) != 0)
    # A single flipped bit must break it - the property, not the value.
    bad = bytearray(blk + crc_on_wire(blk))
    bad[17] ^= 0x01
    check("CRC catches a one-bit flip", not crc_check_block(bytes(bad)))

    # --- geometry is exact ---------------------------------------------------
    ok = True
    for recblk in range(1, 17):
        cap = recblk * BLOCK - BODY_PRE
        for size in (1, 2, cap - 1, cap, cap + 1, 5000, TP_MAXFILE):
            if not 1 <= size <= TP_MAXFILE:
                continue
            nrec, lastblk, _ = geometry(size, recblk)
            if not (1 <= lastblk <= recblk) or nrec < 1:
                ok = False
                print("      recblk=%d size=%d -> nrec=%d lastblk=%d"
                      % (recblk, size, nrec, lastblk))
            # every byte must fit
            if (nrec - 1) * cap + (lastblk * BLOCK - BODY_PRE) < size:
                ok = False
                print("      recblk=%d size=%d does not fit" % (recblk, size))
    check("geometry: lastblk in 1..recblk and every byte fits, all recblk", ok)

    # --- round trip, both ROMs ----------------------------------------------
    cases = [
        ("TINY.TXT", b"x"),
        ("HELLO.TXT", b"Hello, tape.\r\n" * 3),
        ("ZEROS.BIN", b"\0" * 1000),
        ("ONES.BIN", b"\xff" * 300),
        ("RAMP.BIN", bytes(range(256)) * 8),
    ]
    for rom in ("ibm", "glabios"):
        for recblk in (1, 4, 16):
            for name, payload in cases:
                try:
                    bw = build(name, payload, rom=rom, recblk=recblk)
                    hdr, got = parse(bw, rom=rom)
                except TapeError as e:
                    check("round trip %s/%s/recblk=%d" % (rom, name, recblk), False, str(e))
                    continue
                check("round trip %s %-10s recblk=%-2d" % (rom, name, recblk),
                      got == payload and hdr["name"] == name.upper(),
                      "payload differs" if got != payload else "name %r" % hdr["name"])

    # --- the two ROMs differ by exactly one bit, and only at the front -------
    a = build("A.BIN", b"\0" * 256, rom="ibm", recblk=1)
    b = build("A.BIN", b"\0" * 256, rom="glabios", recblk=1)
    nrec_a = geometry(256, 1)[0] + 1                    # +1 for the header
    check("glabios is one start bit per record longer",
          len(b.bits) == len(a.bits) + nrec_a,
          "ibm %d, glabios %d, %d records" % (len(a.bits), len(b.bits), nrec_a))
    check("a 256-zero-byte record is 4,153 bits on IBM",
          _one_record_bits("ibm") == 4153, str(_one_record_bits("ibm")))
    check("...and 4,154 on GLaBIOS",
          _one_record_bits("glabios") == 4154, str(_one_record_bits("glabios")))

    # --- a cross-ROM tape still READS (the start bit is not leader) ----------
    ok = True
    try:
        _, got = parse(build("X.BIN", b"abc" * 40, rom="glabios"), rom="ibm")
        ok = got == b"abc" * 40
    except TapeError as e:
        ok = False
        print("      %s" % e)
    check("a GLaBIOS tape parses as IBM (tapes cross freely)", ok)

    # --- refusals ------------------------------------------------------------
    for label, mutate in _refusal_cases():
        bw = build("R.BIN", b"payload" * 50, rom="ibm")
        try:
            raw = bytearray(bw.bits)
            mutate(raw)
            parse(bytes(raw), rom="ibm")
        except TapeError:
            print("  ok   refuses %s" % label)
            continue
        except Exception as e:                              # noqa: BLE001
            print("  FAIL refuses %s (raised %s)" % (label, type(e).__name__))
            fails.append(label)
            continue
        print("  FAIL refuses %s (accepted it)" % label)
        fails.append(label)

    print("\nos88tape: %s" % ("ALL CHECKS PASSED" if not fails
                              else "%d FAILED: %s" % (len(fails), ", ".join(fails))))
    return 1 if fails else 0


def _one_record_bits(rom):
    bw = BitWriter()
    emit_record(bw, b"\0" * 256, rom)
    return len(bw.bits)


def _bitpos_of_first_payload_byte(rom):
    """Where record 0's first data byte starts, in bits."""
    return (1 if rom == "glabios" else 0) + LEADER_BITS + 1 + 8


def _refusal_cases():
    """Each mutates the BIT stream so the header fails one check."""
    base = _bitpos_of_first_payload_byte("ibm")

    def flip_byte(off, value):
        def f(bits):
            for k in range(8):
                bits[base + off * 8 + k] = (value >> (7 - k)) & 1
        return f

    return [
        ("a bad magic byte", flip_byte(0, ord("X"))),
        ("an unknown version", flip_byte(4, 9)),
        ("a kind that is not a file", flip_byte(5, 3)),
        ("a reserved flag bit", flip_byte(6, 0x80)),
        ("recblk = 0", flip_byte(7, 0)),
        ("recblk = 17", flip_byte(7, 17)),
        ("lastblk > recblk", flip_byte(8, 250)),
        ("nrec = 0", flip_byte(9, 0)),
        ("an IBM Cassette BASIC header", flip_byte(0, 0xA5)),
    ]


# =============================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="the host reference codec for os8088's cassette tape format")
    ap.add_argument("--rom", choices=("ibm", "glabios"), default="ibm",
                    help="which ROM laid the tape down; they differ by one "
                         "start bit a record (default: ibm, which is what "
                         "86Box's cassette machines run)")
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="a file -> a tape image")
    b.add_argument("infile")
    b.add_argument("outfile", nargs="?", help="write a .cas (packed MSB-first)")
    b.add_argument("--name", help="the 8.3 name to record (default: the file's)")
    b.add_argument("--recblk", type=int, default=4, help="blocks a body record, 1..16")

    p = sub.add_parser("parse", help="a .cas -> the file on it")
    p.add_argument("infile")
    p.add_argument("outfile", nargs="?")

    sub.add_parser("tables", help="print the timing tables SPEC.md 88 quotes")
    sub.add_parser("selfcheck", help="round-trip every fixture and check the CRC")

    a = ap.parse_args(argv)

    if a.cmd in (None, "selfcheck"):
        return selfcheck()
    if a.cmd == "tables":
        print_tables()
        return 0
    if a.cmd == "build":
        payload = open(a.infile, "rb").read()
        name = a.name or os.path.basename(a.infile)
        bw = build(name, payload, rom=a.rom, recblk=a.recblk)
        secs = TP_FIX[a.rom] * (1 + geometry(len(payload), a.recblk)[0]) + bw.seconds()
        print("%s: %d bytes -> %d records, %d bits, %s of tape (%s)"
              % (name.upper(), len(payload), geometry(len(payload), a.recblk)[0] + 1,
                 len(bw.bits), _fmt_mmss(secs), a.rom))
        if a.outfile:
            open(a.outfile, "wb").write(bw.packed())
            print("wrote %s" % a.outfile)
        return 0
    if a.cmd == "parse":
        raw = open(a.infile, "rb").read()
        bits = bytearray()
        for byte in raw:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        hdr, payload = parse(bytes(bits), rom=a.rom)
        print("%(name)s  %(size)d bytes  %(nrec)d records  "
              "recblk=%(recblk)d lastblk=%(lastblk)d flags=0x%(flags)02X" % hdr)
        if a.outfile:
            open(a.outfile, "wb").write(payload)
            print("wrote %s" % a.outfile)
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
