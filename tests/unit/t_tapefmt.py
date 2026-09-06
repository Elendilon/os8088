#!/usr/bin/env python3
"""docs/plans/CASSETTE-PLAN.md wave 2 - the cassette tape format round-trips.

`tools/os88tape.py` is the REFERENCE implementation of SPEC.md 88's tape
format and the package's `tapefmt.inc` will be the copy, so this row is what
makes that claim mean something before the copy exists.

**It carries more weight than a normal format row, because no emulator in this
project can execute a cassette read at all.** MartyPC's PPI returns a hardwired
zero for the cassette data line whenever the motor is on
(`build/martypc/src/crates/marty_core/src/devices/ppi.rs:856-864`, whose own
comment is `// TODO: Implement cassette data input`), and QEMU models no
cassette of any kind. So the machine's half of this format meets a real reader
for the first time on somebody's actual 5150. What can be pinned down on the
host is pinned down here, first, and the 8086 is written against it.

The awkward cases are the point, not the volume:

  * **an all-0xFF payload**, which contains 256 consecutive one-bits and so
    looks exactly like a LEADER (SPEC.md 88, CASSETTE-PLAN 4.6). A decoder
    written as a scanner splits the record there; the real reader does not,
    because the header declared how many blocks to take. This row is what
    caught that in `os88tape.py` itself.
  * **the geometry edges** - a payload one byte under, exactly on, and one
    byte over a record's capacity, at every `recblk` from 1 to 16. `nrec` and
    `lastblk` are DERIVED by the reader and compared against what the tape
    claims, so an off-by-one in either direction is a refusal rather than a
    misassembly.
  * **both ROMs.** GLaBIOS emits a leading zero START bit per record and the
    IBM 5150 ROM does not (GLABIOS.ASM:11448 against PCBIOS.ASM:5324-5331), so
    a 256-zero-byte record is 4,153 bits from one and 4,154 from the other.
    Tapes still cross freely - a stray zero bit in front of a leader is not
    leader - and that is asserted here rather than assumed, because 86Box's
    cassette machines are `ibmpc`/`ibmpc82`, i.e. the IBM ROM, and a golden
    built for the wrong one would never match.
  * **the refusals**, every one of them, because a tape is hostile input by
    SPEC.md 19's rule and more so than a disk: nothing on the machine wrote
    the bytes and no filesystem checked them.

HOW TO MAKE IT FAIL ON PURPOSE (docs/WRITING-TESTS.md 1): change `TP_VER` in
`tools/os88tape.py` without changing it here and the version rows go red; drop
the `ckfile` comparison out of `parse()` and the spliced-record row goes red;
make `_read_record` re-scan for a leader between blocks and the all-0xFF rows
go red with `record 1 is 256 bytes; 512 declared`.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))

import os88tape as T                                            # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append("%s%s" % (name, (": " + detail) if detail else ""))


def refuses(name, fn):
    """`fn` must raise TapeError.  Anything else - including success - fails."""
    try:
        fn()
    except T.TapeError:
        return
    except Exception as e:                                      # noqa: BLE001
        FAILS.append("%s: raised %s, not TapeError" % (name, type(e).__name__))
        return
    FAILS.append("%s: accepted it" % name)


def main():
    # --- the CRC is the BIOS's, and its residue is the proof ----------------
    blk = bytes(range(256))
    check("CRC residue", T.crc_check_block(blk + T.crc_on_wire(blk)))
    for pos in (0, 7, 128, 255, 256, 257):
        bad = bytearray(blk + T.crc_on_wire(blk))
        bad[pos] ^= 0x80
        check("CRC catches a flip at %d" % pos, not T.crc_check_block(bytes(bad)))

    # --- round trip, both ROMs, every recblk, the awkward payloads ----------
    payloads = {
        # A MAXIMAL 8.3 NAME, first: twelve characters plus a NUL is thirteen
        # bytes, which the format's first draft could not hold at all - the
        # field was 12 and this file is what would have caught it.
        "TAPEDATA.TXT": b"maximal name" * 20,
        "TINY.TXT": b"x",
        "TWO.TXT": b"ab",
        "TEXT.TXT": (b"The quick brown fox jumps over the lazy dog.\r\n" * 40),
        "ZEROS.BIN": b"\0" * 1500,
        "ONES.BIN": b"\xff" * 1500,             # <-- the false-leader case
        "MIXED.BIN": bytes(range(256)) * 6,
        "MAXFF.BIN": b"\xff" * T.TP_MAXFILE,    # the worst case, at full size
    }
    for rom in ("ibm", "glabios"):
        for recblk in (1, 2, 4, 8, 16):
            for name, payload in payloads.items():
                try:
                    hdr, got = T.parse(T.build(name, payload, rom=rom, recblk=recblk),
                                       rom=rom)
                except T.TapeError as e:
                    check("round trip %s %s recblk=%d" % (rom, name, recblk), False, str(e))
                    continue
                check("round trip %s %s recblk=%d" % (rom, name, recblk),
                      got == payload, "%d bytes back, %d out" % (len(got), len(payload)))
                check("name %s %s recblk=%d" % (rom, name, recblk),
                      hdr["name"] == name.upper(), hdr["name"])
                check("size %s %s recblk=%d" % (rom, name, recblk),
                      hdr["size"] == len(payload))

    # --- the geometry edges, at every recblk --------------------------------
    for recblk in range(1, 17):
        cap = recblk * T.BLOCK - T.BODY_PRE
        for size in (1, cap - 1, cap, cap + 1, 2 * cap, 2 * cap + 1):
            if not 1 <= size <= T.TP_MAXFILE:
                continue
            nrec, lastblk, _ = T.geometry(size, recblk)
            check("geometry recblk=%d size=%d: lastblk in range" % (recblk, size),
                  1 <= lastblk <= recblk, "lastblk=%d" % lastblk)
            room = (nrec - 1) * cap + (lastblk * T.BLOCK - T.BODY_PRE)
            check("geometry recblk=%d size=%d: it fits" % (recblk, size),
                  room >= size, "room %d < size %d" % (room, size))
            # ...and one block fewer must NOT fit, or lastblk is not minimal
            if lastblk > 1:
                tight = (nrec - 1) * cap + ((lastblk - 1) * T.BLOCK - T.BODY_PRE)
                check("geometry recblk=%d size=%d: lastblk is minimal" % (recblk, size),
                      tight < size, "lastblk %d is one too many" % lastblk)

    # --- the two ROMs, pinned to the bit -------------------------------------
    def rec_bits(rom):
        bw = T.BitWriter()
        T.emit_record(bw, b"\0" * 256, rom)
        return len(bw.bits)

    check("a 256-zero-byte record is 4,153 bits on IBM", rec_bits("ibm") == 4153,
          str(rec_bits("ibm")))
    check("...and 4,154 on GLaBIOS", rec_bits("glabios") == 4154, str(rec_bits("glabios")))

    # tapes cross freely, both directions
    for wrote, reads in (("glabios", "ibm"), ("ibm", "glabios")):
        try:
            _, got = T.parse(T.build("X.BIN", b"cross" * 60, rom=wrote), rom=reads)
            check("a %s tape parses as %s" % (wrote, reads), got == b"cross" * 60)
        except T.TapeError as e:
            check("a %s tape parses as %s" % (wrote, reads), False, str(e))

    # --- never pad: every CX this format issues is a multiple of 256 --------
    # IBM's pad loop re-reads the byte AFTER the caller's buffer and writes it
    # to tape up to 255 times, which is an information leak onto removable
    # media (CASSETTE-PLAN 4.1).  The format's defence is that it never asks.
    for recblk in (1, 4, 16):
        for size in (1, 300, 5000, T.TP_MAXFILE):
            nrec, lastblk, _ = T.geometry(size, recblk)
            for seq in range(1, nrec + 1):
                blocks = recblk if seq < nrec else lastblk
                check("CX is a whole number of blocks (recblk=%d size=%d rec=%d)"
                      % (recblk, size, seq), (blocks * T.BLOCK) % T.BLOCK == 0)
    refuses("a record that is not a whole number of blocks",
            lambda: T.emit_record(T.BitWriter(), b"\0" * 100, "ibm"))

    # --- the refusals --------------------------------------------------------
    refuses("size 0", lambda: T.build("Z.BIN", b"", rom="ibm"))
    refuses("size over TP_MAXFILE",
            lambda: T.build("Z.BIN", b"\0" * (T.TP_MAXFILE + 1), rom="ibm"))
    refuses("recblk 0", lambda: T.build("Z.BIN", b"abc", recblk=0))
    refuses("recblk 17", lambda: T.build("Z.BIN", b"abc", recblk=17))
    refuses("a flag bit above bit 2", lambda: T.build("Z.BIN", b"abc", flags=0x08))
    refuses("a name longer than 8.3", lambda: T.build("TOOLONGNAME.TXT", b"abc"))
    check("a maximal 8.3 name fits the field",
          len(T._name_field("ABCDEFGH.IJK")) == T.NAME_LEN
          and T._name_field("ABCDEFGH.IJK")[12] == 0,
          "12 chars + NUL must fit in %d" % T.NAME_LEN)
    refuses("a name with a space", lambda: T.build("A B.TXT", b"abc"))
    refuses("a name with a high byte", lambda: T.build("A\x80.TXT", b"abc"))
    refuses("an empty tape", lambda: T.parse(bytearray(5000), rom="ibm"))
    refuses("a tape of pure leader", lambda: T.parse(bytearray(b"\x01" * 5000), rom="ibm"))

    # header-field refusals, mutated in the BIT stream where the machine sees them
    base = (T.LEADER_BITS + 1 + 8)               # ibm: no start bit

    def mutated(off, value):
        bw = T.build("R.BIN", b"payload" * 60, rom="ibm")
        bits = bytearray(bw.bits)
        for k in range(8):
            bits[base + off * 8 + k] = (value >> (7 - k)) & 1
        return lambda: T.parse(bytes(bits), rom="ibm")

    refuses("a corrupt magic byte", mutated(0, ord("X")))
    refuses("an unknown version", mutated(4, 2))
    refuses("a kind that is not a file", mutated(5, 1))
    refuses("a reserved flag bit set", mutated(6, 0x80))
    refuses("recblk 0 on the tape", mutated(7, 0))
    refuses("recblk 17 on the tape", mutated(7, 17))
    refuses("lastblk 0 on the tape", mutated(8, 0))
    refuses("lastblk above recblk", mutated(8, 200))
    refuses("nrec 0 on the tape", mutated(9, 0))
    refuses("an IBM Cassette BASIC header", mutated(0, 0xA5))

    # a body record spliced in from a DIFFERENT file must be caught the instant
    # it arrives, not at the final checksum (CASSETTE-PLAN 4.4)
    a = T.build("A.BIN", b"aaaa" * 300, rom="ibm", recblk=4)
    b = T.build("B.BIN", b"bbbb" * 300, rom="ibm", recblk=4)
    rec_bits_len = 4153 + (T.BLOCK + 2) * 8 * 3          # header + 3 more blocks
    spliced = bytearray(a.bits[:rec_bits_len]) + bytearray(b.bits[rec_bits_len:])
    refuses("a record spliced in from another file",
            lambda: T.parse(bytes(spliced), rom="ibm"))

    # --- and the tool's own selfcheck agrees ---------------------------------
    check("os88tape --selfcheck passes", T.selfcheck() == 0)

    if FAILS:
        print("t_tapefmt: %d FAILED" % len(FAILS))
        for f in FAILS[:25]:
            print("  " + f)
        if len(FAILS) > 25:
            print("  ...and %d more" % (len(FAILS) - 25))
        return 1
    print("t_tapefmt: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
