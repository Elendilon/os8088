# TITHE — is LZ4 the right codec for the art?

*Taken 2026-09-22 on branch `tithe-plan`. The corpus is the real base art —
seven candidates × four surfaces × eight poses — which is the only real art
this game has and is exactly the shape the question is about: frames that are
nearly identical to each other. `python3 tools/os88tithebase.py sizes`
re-derives every figure.*

## The question

The default is LZ4 (`PKGZ ?= lz4`, SPEC.md §20.13). Three alternatives were
asked about: **GIF**, which is smaller than a BMP and has multi-frame
differencing; **LZB**, the tree's other format; and **a delta of our own**,
storing only what changes between frames.

## The measurement

Bytes, whole corpus. `naive` is eight whole bands a pose set, packed 1bpp;
`OURS` is SPEC.md §97.5.1's shipped form — one ground band plus a bounding-box
sub-band a pose.

| | naive | n+lz4 | n+lzb | n+lzw | OURS | o+lz4 | o+lzb | xor+lz4 |
|---|---|---|---|---|---|---|---|---|
| **total** | 192,192 | 10,971 | 8,404 | **71,723** | 40,966 | **8,419** | 6,561 | 12,171 |

## 1. GIF is 6.5× WORSE, and the codec is not why

**71,723 against 10,971.** A GIF is an *indexed* image — one byte a pixel — so
before its LZW runs it has already thrown away the 8:1 that packing 1bpp gives
for free. LZW then has to win that 8× back and does not come close.

The decode is the worse half. SPEC.md §42.25 is this tree's own precedent: a
picture decoder shipped at **199 cycles a pixel** against a packed arm's 49, and
that was the regression the whole of PAINT-1BPP-PLAN's load half is about. A
56×144 band is 8,064 pixels, so ~200 cycles each is **0.34 s for one band** on a
4.77 MHz 8088 — before it is re-packed to 1bpp to be blittable. LZ4 decodes the
same band's 1,008 packed bytes in **51,000 cycles, 0.011 s**.

**But the frame-differencing question is the right one, and the answer is that
we already do it** — see §3.

## 2. LZB is 22% smaller and LOSES on this machine

`o+lzb` is **6,561 against LZ4's 8,419**. That is a bigger win than the tree's
standing figure — SPEC.md §20.13 has LZB at "ten points" of ratio, measured on
the tree's own binaries, which are mostly *code*; on 1bpp art it is **22%**.
Pixel art and code do not compress alike, and the plan's TITHE-PLAN §1.5 already says so
in the other direction.

It still loses, and the arithmetic is general rather than particular:

- **decode scales with the UNCOMPRESSED size**, at 50.6 cycles a byte for LZ4
  and ~4× that for LZB (SPEC.md §20.13);
- **the disk saving scales with a FRACTION of the COMPRESSED size**, and the
  compressed size is already ~0.2 of the uncompressed here.

So the gap widens with every kilobyte. For this corpus (U = 40,966): LZ4 decodes
in **0.43 s**, LZB in **1.73 s**, and LZB saves 1,858 bytes — under four
sectors, which TITHE-PLAN §1.1's rule (*cost disk work in CALLS, not sectors*) prices at
zero to one `int 13h`. **LZB loses by about 0.9 s.** Scaled to a 60KB faction
part it loses by about **1.5 s**, and it never comes back.

**Where LZB could still be right**: a part read at a screen the user is already
waiting through, which is small and never on the launch path. It is a per-file
choice, so it stays available and is not the default. Nothing in TITHE needs it
today.

## 3. A delta of our own: WE ALREADY HAVE ONE, and the bitstream kind is worse

**Measured, `xor+lz4` is 12,171 against 10,971 — storing the changes ourselves
at the bitstream level is 11% WORSE than not bothering.** The reason is worth
keeping: LZ4 *already* finds the inter-frame redundancy, as one long match back
into the previous frame. XOR replaces those long runs with sparse noise, which
is precisely what a match finder cannot use. A delta helps a codec that has no
window; ours has a 64KB one.

**The delta that does pay is the one in the ART MODEL**, and it is what SPEC.md
§97.5.1 already ships: `OURS` is **40,966 raw against `naive`'s 192,192**, a
**4.7× cut before any compression at all**, for one ground band and a
bounding-box overlay a pose. It costs nothing to decode — the overlay is an
`OR` of whole bytes — where every codec-level scheme costs cycles.

**And it is a KEYFRAME scheme rather than a chain, which is load-bearing.** Each
pose is the ground plus *its own* overlay, so any pose can be built without
decoding the ones before it. GIF's differencing chains frame to frame; the
pacing wheel jumps to whatever pose the clock says (§97.5), so a chain would
have to decode from the last keyframe on every jump. The independence is not a
detail of the format, it is what makes the format usable by this renderer.

The same idea one level up is TITHE-PLAN §4.2.1's layer model — a character is a body plus
a held item rather than a drawn frame — which is the same 4.7×-class win on the
same argument.

## What this decides

1. **Keep LZ4.** It is the default, it is the fastest thing here that
   compresses at all, and on this corpus it lands within 0.2% of what the
   expensive codec achieves *once the art model has done its half*.
2. **Do the differencing in the art model, never in the bitstream.** Ground plus
   overlay for an animation; body plus item for a character. Both are free at
   decode and both keep random access.
3. **Do not write a delta codec.** It was measured and it is worse.
4. **GIF is not a candidate** at any point, for either half.

## The trap to carry forward

**Compression decides DISK. It does not decide RAM.** `OP_COMP` expands a part
into its carve at load (SPEC.md §20.12.7), so what the heap holds is the
*uncompressed* figure — 40,966 here, not 8,419. Every heap number in
TITHE-PLAN §1.5 and every part sizing in TITHE-PLAN §4.3 is an uncompressed number, and the
codec cannot move any of them. Only the art model can, which is the third reason
it is where the work belongs.
