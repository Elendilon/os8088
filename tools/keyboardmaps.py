#!/usr/bin/env python3
"""Build the optional module's set-1 layout/composition tables (SPEC 9.16).

The rows below are authored character facts, reviewed against Microsoft's
layout diagrams dated 2024-10-24: keyboards/kbdsp.html, kbdla.html and
kbdfr.html under https://learn.microsoft.com/en-us/globalization/.
Only the CP850-representable subset is emitted; Euro is deliberately absent.
No download, locale setting or host keyboard affects a build.
"""
from pathlib import Path
import argparse
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "kernel" / "keymaps.inc"
N = 0x57
DEAD = 0x0100
ROWS = ((list(range(0x02, 0x0E))), list(range(0x10, 0x1C)),
        list(range(0x1E, 0x29)), list(range(0x2C, 0x36)))


def char(c):
    return c.encode("cp850")[0] if c else 0


def layout(name, base, shift, extra, dead, altgr, french_caps=False):
    lo, hi, ag = ([0] * N for _ in range(3))
    for scans, a, b in zip(ROWS, base, shift):
        assert len(scans) == len(a) == len(b), (name, scans, a, b)
        for scan, x, y in zip(scans, a, b):
            lo[scan], hi[scan] = char(x), char(y)
    for scan, (a, b) in extra.items():
        lo[scan], hi[scan] = char(a), char(b)
    for scan in (0x01, 0x0E, 0x0F, 0x1C, 0x39):
        lo[scan] = hi[scan] = {1: 27, 14: 8, 15: 9, 28: 13, 57: 32}[scan]
    for plane, scan in dead:
        (lo, hi, ag)[plane][scan] |= DEAD
    for scan, value in altgr.items():
        c, is_dead = value if isinstance(value, tuple) else (value, False)
        ag[scan] = char(c) | (DEAD if is_dead else 0)
    caps = [0] * ((N + 7) // 8)
    for scan, value in enumerate(lo):
        if not value:
            continue
        c = bytes([value & 255]).decode("cp850")
        sensitive = c.isalpha() and c.upper() != c and char(c.upper()) == hi[scan]
        if french_caps:
            sensitive = scan not in (0x01, 0x0E, 0x0F, 0x1C, 0x29, 0x39, 0x56)
        if sensitive:
            caps[scan >> 3] |= 1 << (scan & 7)
    return name, lo, hi, ag, caps


LAYOUTS = [
    layout("us", ("1234567890-=", "qwertyuiop[]", "asdfghjkl;'", "zxcvbnm,./"),
           ('!@#$%^&*()_+', 'QWERTYUIOP{}', 'ASDFGHJKL:"', 'ZXCVBNM<>?'),
           {0x29: ('`', '~'), 0x2B: ('\\', '|'), 0x56: ('\\', '|')}, (), {}),
    layout("es", ("1234567890'¡", "qwertyuiop`+", "asdfghjklñ´", "zxcvbnm,.-"),
           ('!"·$%&/()=?¿', 'QWERTYUIOP^*', 'ASDFGHJKLÑ¨', 'ZXCVBNM;:_'),
           {0x29: ('º', 'ª'), 0x2B: ('ç', 'Ç'), 0x56: ('<', '>')},
           ((0, 0x1A), (1, 0x1A), (0, 0x28), (1, 0x28)),
           {0x29: '\\', 0x02: '|', 0x03: '@', 0x04: '#', 0x05: ('~', True),
            0x07: '¬', 0x1A: '[', 0x1B: ']', 0x28: '{', 0x2B: '}'}),
    layout("la", ("1234567890'¿", "qwertyuiop´+", "asdfghjklñ{", "zxcvbnm,.-"),
           ('!"#$%&/()=?¡', 'QWERTYUIOP¨*', 'ASDFGHJKLÑ[', 'ZXCVBNM;:_'),
           {0x29: ('|', '°'), 0x2B: ('}', ']'), 0x56: ('<', '>')},
           ((0, 0x1A), (1, 0x1A)),
           {0x29: '¬', 0x0C: '\\', 0x10: '@', 0x1B: '~',
            0x28: ('^', True), 0x2B: ('`', True)}),
    layout("fr", ('&é"\'(-è_çà)=', 'azertyuiop^$', 'qsdfghjklmù', 'wxcvbn,;:!'),
           ('1234567890°+', 'AZERTYUIOP¨£', 'QSDFGHJKLM%', 'WXCVBN?./§'),
           {0x29: ('²', ''), 0x2B: ('*', 'µ'), 0x56: ('<', '>')},
           ((0, 0x1A), (1, 0x1A)),
           {0x03: ('~', True), 0x04: '#', 0x05: '{', 0x06: '[', 0x07: '|',
            0x08: ('`', True), 0x09: '\\', 0x0A: '^', 0x0B: '@',
            0x0C: ']', 0x0D: '}', 0x1B: '¤'}, True),
]


# The keys the layouts translate: the four character rows, the three keys
# every layout adds (0x29, 0x2B and the ISO key 0x56) and Space. Every other
# scan is the BIOS's (klm_scan passes it), so no plane spends a byte on it.
KEYS = sorted(set(s for row in ROWS for s in row) | {0x29, 0x2B, 0x39, 0x56})
KLM_BS = len(KEYS) + 1          # klm_idx's Backspace: one past the keys
# Dead accents are a CODE in the planes (1..5, bytes no layout produces: every
# plane byte is 0 or >= 20h) and klm_deadch turns a code into its CP850 byte.
# The order is the composition table's, one run per accent.
ACCENTS = (("´", "\u0301"), ("`", "\u0300"), ("^", "\u0302"),
           ("¨", "\u0308"), ("~", "\u0303"))


def plan():
    """The plane order and each layout's Caps Lock count.

    Caps Lock is one COMPARE per layout rather than a bitmap: the keys are
    ordered so that every layout's Caps-sensitive set is a PREFIX of the
    order (US's letters, then LA's n-tilde key, ES's c-cedilla key, French
    AZERTY's shift-lock rows), so "does Caps Lock apply" is "index < count".
    That holds while the four sets nest, which this asserts."""
    caps = []
    for name, lo, hi, ag, bits in LAYOUTS:
        assert {s for s in (0x29, 0x2B, 0x56)} <= {s for s in KEYS}
        caps.append({s for s in KEYS if bits[s >> 3] >> (s & 7) & 1})
        assert not any(bits[s >> 3] >> (s & 7) & 1
                       for s in range(N) if s not in KEYS), name
    order = sorted(KEYS, key=lambda s: (-sum(s in c for c in caps), s))
    counts = []
    for (name, *_), c in zip(LAYOUTS, caps):
        assert set(order[:len(c)]) == c, \
            f"{name}: its Caps Lock keys are not a prefix of the plane order"
        counts.append(len(c))
    return order, counts


def plane(values, order):
    accents = [char(a) for a, _ in ACCENTS]
    out = []
    for s in order:
        v = values[s]
        if v & DEAD:
            out.append(accents.index(v & 255) + 1)
        else:
            assert v == 0 or v >= 0x20, (s, v)
            out.append(v)
    return out


def render():
    order, counts = plan()
    index = [0] * N
    for i, s in enumerate(order):
        index[s] = i + 1
    index[0x0E] = KLM_BS
    lines = ["; Generated by tools/keyboardmaps.py; SPEC.md 9.16. Do not edit.",
             "; Each layout is a plane of one CP850 byte per translated key - base,",
             "; shift and AltGr - in klm_idx's key order. A byte below",
             "; KLM_DEAD_N + 1 is not a character: 0 is unmappable and 1..KLM_DEAD_N",
             "; a dead accent's code (klm_deadch). The byte before a layout's base",
             "; plane is how many keys, from the first, follow Caps Lock.",
             f"KLM_KEYS equ {len(order)}",
             f"KLM_IDX_N equ 0x{N:02x}",
             f"KLM_BS equ {KLM_BS}",
             f"KLM_DEAD_N equ {len(ACCENTS)}",
             "; scan -> its key's index + 1, KLM_BS for Backspace, 0 for the BIOS's",
             "klm_idx:"]
    for i in range(0, N, 8):
        lines.append("    db " + ",".join(f"{x}" for x in index[i:i + 8])
                     + f" ; 0x{i:02x}")
    lines.append("klm_deadch:")
    lines.append("    db " + ",".join(f"0x{char(a):02x}" for a, _ in ACCENTS))
    lines.append("klm_maps:")
    lines.append("    dw " + ", ".join(f"klm_map_{l[0]}" for l in LAYOUTS))
    for (name, lo, hi, ag, bits), count in zip(LAYOUTS, counts):
        planes = [("base", lo), ("shift", hi), ("altgr", ag)]
        if name == "us":
            # klm_translate passes US AltGr before reading a plane: none.
            assert not any(ag), "US AltGr needs klm_translate's pass removed"
            planes = planes[:2]
        lines.append(f"    db {count} ; {name}: the first {count} keys follow Caps Lock")
        lines.append(f"klm_map_{name}:")
        for pname, values in planes:
            lines.append(f"; {name} {pname}")
            data = plane(values, order)
            for i in range(0, len(data), 13):
                lines.append("    db " + ",".join(f"0x{x:02x}" for x in data[i:i + 13]))
    # Independent Unicode composition rules, filtered to the declared encoding.
    # One run per accent: a header (accent, pair count), then its (letter,
    # result) pairs; dw 0 ends the table. A miss in the IRQ then scans one
    # accent's run rather than every pair (SPEC.md 9.16.2).
    lines.append("klm_compose:")
    count = 0
    for accent, mark in ACCENTS:
        pairs = []
        for letter in "aAeEiIoOuUyYnN":
            combined = unicodedata.normalize("NFC", letter + mark)
            if len(combined) != 1:
                continue
            try:
                value = char(combined)
            except UnicodeEncodeError:
                continue
            pairs.append(f"    db 0x{ord(letter):02x},0x{value:02x}")
        # A zero header word is the end; the run's loop needs a count >= 1.
        assert char(accent) and 0 < len(pairs) < 256, accent
        lines.append(f"    db 0x{char(accent):02x},{len(pairs)}")
        lines += pairs
        count += len(pairs)
    lines += ["    dw 0", "KLM_COMPOSE_N equ " + str(count), ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render()
    if args.check:
        if not OUT.exists() or OUT.read_text() != expected:
            parser.exit(1, "keyboardmaps: stale kernel/keymaps.inc\n")
        print("keyboardmaps: layout and composition tables current")
    else:
        OUT.write_text(expected)
        print(f"keyboardmaps: wrote {OUT}")


if __name__ == "__main__":
    main()
