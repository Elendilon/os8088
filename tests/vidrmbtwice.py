#!/usr/bin/env python3
"""vidrmbtwice - two plays of a Catch-shaped file in kern_mega's REAL-MODE
bracket, on a Sound Blaster, with the glyph table COPIED above 1MB: what a
play SOUNDS like from its first sample and what its text is drawn from
(SPEC.md 53.2.3, 98.3.24; KERN-MEGA-PLAN 14.129, 14.130, 14.131).

    python3 tests/vidrmbtwice.py [--keep]

The owner's Victory 286 (4 MB, a Paradise PVGA1A whose option ROM is slow,
a PicoMEM's Sound Blaster) on the 9abdcaae kern_mega pair reported three
things in one evening, and this row is all three:

  - 07-Miku.V88 played with NO SOUND, every try, between files that had it.
    The player's FSXF_REAL list wrote the file's name as vp_name's 13 bytes;
    the kernel reads it to its NUL and takes the next byte as the next
    entry, so a name under 12 characters put a 0 - FSXL_END - where
    FSXL_DRV DRVC_SOUND was, and the bracket carried no sound driver
    (14.130). The file here is CATCH.V88, nine characters.
  - every play's first second was STATIC. The sound-ahead lead (98.1.8) of
    a file whose key leads are apart is read on the desktop into the ring's
    slot by its SELECTOR - the bank in place, above 1MB - and was staged in
    the bracket out of the conventional ring's paragraph instead: the
    file's head, played as sound (14.131).
  - from the owner's second play on, the full screen's text (the buffering
    line, here "Paused") was NOISE in the right colour: the glyph table's
    copy (MEM_K_FONT) is above 1MB on kern_mega and the bracket handed
    OSAPI_FONT_GLYPHS its selector (14.129). FONTSLOW=1 forces the copy -
    86Box does not slow an option ROM down - so this boots a private
    `make FONTSLOW=1 mega` tree.

86Box's mr286 (vm/at286-port, 4 MB, an OTi VGA, the IDE disk the MR BIOS
serves) with an SB2.0 at IRQ 7, its DAC captured; SOUND.DRV wanted. C: holds
the arm's VIDEO.O88 and a clip shaped like vidmegaclaims's (16 colours on
320 x 200n, two pages flipped, PCM8 FOUR frames ahead with the key leads
apart) whose sound is WHITE NOISE, so a capture matches it in one place. It
opens the file and plays it to its end TWICE, pausing each play four
seconds in with Space. Asserted, of each play:

  1. a real-mode bracket ([fsx_rmode] 1) and the card OPEN in it
     ([vp_snd] 1, [vp_sopn] 1 in the bracket's copy of the player);
  2. while paused, the glyph table the player draws from
     ([vo_gseg]:[vo_goff], a real segment) holds the kernel's 760 glyph
     bytes, byte for byte - and play 2's "Paused" box is play 1's, pixel
     for pixel;
  3. the capture's first non-silent sample starts the file's own sound,
     within START_SLACK frames of where the file's starts, and its first
     half second is the file's whole - nothing that is not the file's;

and no kern_mega FAULT or CLOSED.

THE FAILING CASES (docs/WRITING-TESTS.md 1), each verified on the tree it
went in with: the 13-byte name copy back in vcold.asm's vp_rmklist takes 1
red (the card never opened) and 3 with it; vp_rdoor's vp_lstage out takes 3
red (the lead from the wrong memory); fsx.inc's glyph copy out (fsx_rfont
left 0) takes 2 red.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(ROOT, "tools"), HERE]
import os88box                                                # noqa: E402
import os88build                                              # noqa: E402
import os88geom as G                                          # noqa: E402
import os88vid as vid                                         # noqa: E402

C_ZONE = (592, 165)
FIRST = (160, 127)
HALF = 11025                    # the samples the start is checked over
START_SLACK = 3                 # ...and the frames it may start late by
FAILS = []


def want(cond, what):
    print("   %s  %s" % ("ok  " if cond else "FAIL", what), flush=True)
    if not cond:
        FAILS.append(what)


def runs(b):
    out = bytearray()
    last = None
    for x in b:
        if x != last:
            out.append(x)
            last = x
    return bytes(out)


def card_bytes(path, skip=0):
    """the card's bytes back out of 86Box's capture (tests/vidsound.py's
    reading), from host sample SKIP"""
    import sndcheck
    rate, vals, _ = sndcheck.load(path)
    return bytes(max(0, min(255, int(round(v * 128.0)) + 128))
                 for v in vals[skip:]), len(vals)


def check_start(label, got, ref, abytes):
    """3: the play's capture, from its first non-silent sample, is REF's
    sound - the file's, a half second of it whole, starting within
    START_SLACK frames of where the file's sound starts. NOT from the first
    byte: a play from a key loses a block of its first record tails on
    EVERY kernel here (kern_big's shipped player the same to the run on this
    clip - a defect of its own, KERN-MEGA-PLAN 14.131's last paragraph), and
    what this asks is the bracket's: nothing that is not the file's"""
    g = runs(got)
    k = 0
    while k < len(g) and g[k] == 0x80:
        k += 1
    if k >= len(g):
        want(False, "%s 3. the card played the file's sound (SILENT)"
             % label)
        return
    z = next(i for i, x in enumerate(ref) if x != 0x80)
    w, wi, last = bytearray(), [], None
    for i, x in enumerate(ref[z:z + START_SLACK * abytes + 2 * HALF]):
        if x != last:
            w.append(x)
            wi.append(i)
            last = x
    w = bytes(w)
    at = w.find(g[k:k + 32])
    if at < 0:
        want(False, "%s 3. the card's first sound is the file's (its first "
             "32 distinct samples are nowhere near the file's start: %s)"
             % (label, g[k:k + 8].hex()))
        return
    e = next(j for j in range(at, len(wi)) if wi[j] - wi[at] >= HALF)
    n = next((i for i in range(e - at) if k + i >= len(g)
              or g[k + i] != w[at + i]), e - at)
    want(wi[at] <= START_SLACK * abytes and n == e - at,
         "%s 3. the card's first sound is the file's, %.1f frames into it, "
         "and its first half second whole (%d of %d distinct samples)"
         % (label, wi[at] / float(abytes), n, e - at))


def clip():
    """vidmegaclaims's Catch-shaped clip with WHITE NOISE for its sound, made
    once into build/vidrmbtwice/: a sine is periodic, so a capture of one
    matches the file at any period and cannot say which frame it starts on;
    noise matches at exactly one place"""
    out = os.path.join(ROOT, "build", "vidrmbtwice", "CATCH.V88")
    if os.path.exists(out):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    src = tempfile.mkdtemp(prefix="vidrmbtwice")
    mkv = os.path.join(src, "src.mkv")
    subprocess.run(
        ["ffmpeg", "-v", "error",
         "-f", "lavfi", "-i", "testsrc2=s=320x200:r=24:d=3",
         "-f", "lavfi", "-i", "mandelbrot=s=320x200:r=24,trim=duration=3",
         "-f", "lavfi", "-i", "life=s=320x200:r=24:mold=10:ratio=0.3:"
         "life_color=#ff8000:death_color=#002040,trim=duration=3",
         "-f", "lavfi", "-i", "rgbtestsrc=s=320x200:r=24:d=3",
         "-f", "lavfi", "-i", "anoisesrc=d=12:c=white:r=22050:a=0.5:"
         "seed=88",
         "-filter_complex",
         "[0:v]format=yuv420p[a];[1:v]format=yuv420p[b];"
         "[2:v]format=yuv420p[c];[3:v]format=yuv420p[d];"
         "[a][b][c][d]concat=n=4:v=1:a=0,noise=alls=70:allf=t+u[v]",
         "-map", "[v]", "-map", "4:a", "-c:v", "ffv1", "-c:a", "pcm_u8",
         mkv], check=True)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88venc.py"),
                    mkv, out + ".part", "--quiet", "--preset", "vga4-full",
                    "--pixfmt", "vga4", "--palette", "colour16", "--screen",
                    "320x200n", "--flip", "--pages", "2", "--scene-palettes",
                    "--audio", "pcm8", "--rate", "22050", "--fps", "24"],
                   check=True)
    os.rename(out + ".part", out)
    shutil.rmtree(src, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    t = os88build.tree("FONTSLOW=1", targets=(
        "mega.img", "megak/apps/video.o88")).apply()
    os.environ["OS88_MEGA_BUILD"] = t.dir
    os.environ["OS88_MEGA_SND"] = "sb2.0"
    import os88mega86box as M
    import os88sym
    v88 = clip()
    r = vid.Reader(v88)
    ref = b"".join(r.sound(f) for f in range(r.frames))
    tmp = tempfile.mkdtemp(prefix="vidrmbtwice")
    cap = os.path.join(tmp, "cap")
    os.environ["MARTYPC_WAV"] = cap
    wav = cap + ".sound_blaster.wav"
    vhd = os.path.join(tmp, "c.vhd")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "os88hdd.py"),
                    "--out", vhd, "--noboot", "--spt", "17", "--heads", "15",
                    "--cyls", "100",
                    "--file", "CATCH.V88=" + v88,
                    "--file", "VIDEO.O88=" + os.path.join(
                        t.dir, "megak", "apps", "video.o88")],
                   check=True, stdout=subprocess.DEVNULL)
    vs = {}
    for ln in open(os.path.join(t.dir, "megak", "apps", "video.map")):
        mm = re.match(r"\s+([0-9A-F]+)\s+([0-9A-F]+)\s+(\w+)\s*$", ln)
        if mm:
            vs[mm.group(3)] = int(mm.group(1), 16)
    off, _, _ = os88sym._parse_map(os.path.join(t.dir, "megak",
                                                "kernel.map"))
    low = 0x0EA0 * 16
    m = M.launch(os.path.join(t.dir, "mega.img"), cimg=vhd, cfg=0x01,
                 apps=os.path.join(ROOT, "build", "megaapps.img"),
                 label="vidrmbtwice", machine="os8088_xt_vga")
    b = m.b
    b.cmd("hold")
    boxes, starts = [], []

    def player():
        raw = b.memr(b.sym("inst_tab"), G.INST_MAX * G.I_RECSZ)
        for i in range(G.INST_MAX):
            rr = raw[i * G.I_RECSZ:(i + 1) * G.I_RECSZ]
            nm = rr[G.I_NAME:G.I_NAME + 16].split(bytes(1))[0]
            if rr[G.I_STATE] == 1 and nm == b"Video Player":
                return rr[G.I_SPTR] | rr[G.I_SPTR + 1] << 8
        return None

    def cw(name, n=2):                  # the bracket's copy of the player
        d = b.memr(b.word("fsx_rseg") * 16 + vs[name], n)
        return d[0] | d[1] << 8 if n == 2 else d[0]

    try:
        b.ui_done(cap_ms=10000)
        since = sum(1 for _ in open(os.path.join(b.run, "stderr.log"),
                                    errors="replace"))
        fs = b.word("font_seg")
        glyphs = b.memr(b.lin(fs) + b.word("font_base"), 760)
        print("   the glyph table: selector %04X, base %06X (the copy: "
              "above 1MB)" % (fs, b.lin(fs)))
        if b.lin(fs) < 0x100000:
            FAILS.append("the glyph table is not the copy above 1MB - "
                         "FONTSLOW did not reach the kernel")
        b.to(*C_ZONE)
        b.click(2)
        b.pause(8000)
        b.ui_done(limit_ms=60000)
        b.to(*FIRST)
        b.click(2)
        b.until(lambda: player() is not None, "the Video Player to start",
                60000, 100)
        b.pause(10000)
        b.ui_done(limit_ms=60000)
        for n in (1, 2):
            lab = "play %d:" % n
            starts.append(os.path.getsize(wav) if os.path.exists(wav) else 0)
            b.tap("space", gap=300)
            b.until(lambda: b.byte("fsx_task") != 0xFF, "the bracket", 20000,
                    50)
            b.pause(4000)                   # (past the half second 3 reads:
            rm = b.byte("fsx_rmode")        # a halted card's DAC is silence)
            snd, sopn = cw("vp_snd", 1), cw("vp_sopn", 1)
            b.tap("space", gap=300)         # PAUSED: the box
            b.pause(1500)
            gs, go = cw("vo_gseg"), cw("vo_goff")
            seen = b.memr(gs * 16 + go, 760)
            png = os.path.join(tmp, "paused%d.png" % n)
            b.cmd("screenshot %s" % png)
            boxes.append(png)
            b.tap("space", gap=300)
            want(rm == 1 and snd == 1 and sopn == 1,
                 "%s 1. a real-mode bracket ([fsx_rmode] %d) and the card "
                 "open in it ([vp_snd] %d, [vp_sopn] %d)" % (lab, rm, snd,
                                                             sopn))
            want(seen == glyphs, "%s 2. the text's glyphs at %04X:%04X are "
                 "the kernel's table (%d of 760 bytes differ)"
                 % (lab, gs, go, sum(x != y for x, y in zip(seen, glyphs))))
            b.until(lambda: b.byte("fsx_task") == 0xFF, "the play to end",
                    90000, 200)
            b.ui_done(limit_ms=60000, lock=False)
            b.pause(2000)
        starts.append(None)
        bad = []
        for k, ln in enumerate(open(os.path.join(b.run, "stderr.log"),
                                    errors="replace")):
            mf = os88box.FAULT.search(ln)
            if k >= since and mf and int(mf.group(2), 16) < 0xF000 and \
                    int(mf.group(2), 16) not in (0x0060, 0x0028):
                bad.append(ln.strip())
    except SystemExit as e:
        want(False, "the machine stopped answering or a step missed: %s" % e)
        bad = []
    finally:
        b.quit(remove=not a.keep)
    if len(boxes) == 2:
        try:
            from PIL import Image, ImageChops
            i1, i2 = Image.open(boxes[0]), Image.open(boxes[1])
            box = (16, 40, 144, 64)         # "Paused": its ground and text
                                            # (VO_YOFF 4 rows, a character
                                            # in; 86Box doubles 320 x 200)
            diff = ImageChops.difference(i1.crop(box).convert("RGB"),
                                         i2.crop(box).convert("RGB"))
            want(diff.getbbox() is None, "2. play 2's \"Paused\" box is play "
                 "1's, pixel for pixel (differ in %s)" % (diff.getbbox(),))
        except ImportError:
            print("   (no PIL: the boxes' pixels not compared)")
    if os.path.exists(wav) and len(starts) == 3:
        import sndcheck
        _, vals, _ = sndcheck.load(wav)
        # the two plays' halves of the capture, by the host samples it held
        # at each Space (a sample is a 16-bit word after a 44-byte header)
        cut = max(0, (starts[1] - 44) // 2)
        g1, _ = card_bytes(wav)
        check_start("play 1:", g1[:cut], ref, r.abytes)
        check_start("play 2:", g1[cut:], ref, r.abytes)
    else:
        want(False, "3. the card's capture (%s)" % wav)
    if bad:
        want(False, "no kern_mega FAULT: %s" % bad[0])
    if a.keep or FAILS:
        print("vidrmbtwice: kept %s" % tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print("vidrmbtwice: %s" % ("FAIL - %d" % len(FAILS) if FAILS else "ok"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
