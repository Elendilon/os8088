#!/usr/bin/env python3
"""os88venc - any video to a .V88 (SPEC.md 98.2.1; VIDEO-PLAN wave 8).

    python3 tools/os88venc.py IN.MP4 OUT.V88 [--preset herc] [--box WxH]
        [--layout cga|herc|lin80] [--fit fit|fill|stretch]
        [--start S] [--end S] [--fps F] [--profile 5150-st225]
        [--audio pcm8|adpcm4|none] [--rate HZ]
        [--dither bayer|bluenoise|threshold] [--stable N]
        [--gamma G] [--contrast C] [--brightness B] [--invert]
        [--title T] [--credits C] [--keysecs S] [--poster K | --poster-at S]
        [--clip N]
        [--preview-png DIR] [--quiet]

THE FRONT END, AND THE BUDGETS. ffmpeg decodes and scales the source to a
canvas whose DISPLAYED shape is the source's (the layout's pixels are not
square: CGA's are 5:12, Hercules' 29:45), grey, at a frame rate the audio
divides exactly. Each grey frame is dithered to MONO1 by an ORDERED
threshold anchored to the canvas - so a still area dithers identically
frame after frame and costs nothing - and a pixel within `--stable` grey
levels of its threshold keeps the value it had, so a source's own noise
does not flip it. That frame is the TARGET.

The stream is the SCREEN chasing the target under the machine's limits
(VIDEO-PLAN 3.2), taken from a PROFILE:
  - the DISK: a bucket of bytes refilled at the profile's rate less the
    audio's, holding at most one second - a frame may spend what quieter
    frames left, which is the burst allowance;
  - the CPU: the same for decode cycles at the profile's average share of
    the machine, with a per-frame ceiling on top (a scene cut drawn in one
    or two frames, never one frame over its own period).
A frame whose changes fit is exact. One that does not commits its changed
spans in order of pixels fixed per cycle - AGED, so an error that has sat
on the screen outranks a fresh one of the same size - until a bucket or the
ceiling says stop, and the rest is still wrong on the next frame and
competes again. Keyframes (SPEC.md 98.1.3) are the screen, not the target:
a seek shows exactly what a play would.

The cost model is os88vid's (wave 0's, CGA on MartyPC, cycles), plus the
interrupt's audio copy. ffmpeg is needed for this and for nothing else in
the tree; numpy likewise.
"""
import argparse
import math
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os88vid as vid                                         # noqa: E402

try:
    import numpy as np
except ImportError:                                           # pragma: no cover
    np = None

# --------------------------------------------------------------------------
# profiles and presets
# --------------------------------------------------------------------------
# disk: bytes a second the stream may take, audio included; avg/peak: the
# share of a frame period decode may take over any second / in any frame.
# rate/audio: the default sound. "predicted" profiles are arithmetic, not a
# field reading (docs/FIELD-MACHINES.md).
PROFILES = {
    "5150-st225": dict(disk=60000, avg=0.50, peak=0.85, rate=11025,
                       audio="pcm8",
                       what="the owner's 5150: ST-225 on an ST11M, DMA. "
                            "BADAPPLE's 57.7 KB/s plays there"),
    "5150-picomem2": dict(disk=150000, avg=0.40, peak=0.80, rate=22050,
                          audio="pcm8",
                          what="a 5150 with a PicoMEM 2: fast storage the "
                               "CPU copies, so a lower CPU share "
                               "(predicted)"),
    "floppy": dict(disk=15000, avg=0.50, peak=0.85, rate=5512,
                   audio="pcm8",
                   what="a 360 KB floppy, a cylinder a call (predicted)"),
    "286": dict(disk=150000, avg=1.50, peak=2.50, rate=22050, audio="pcm8",
                what="a 6 MHz 286: ~3x the 8088's cycles (predicted)"),
    "lossless": dict(disk=None, avg=None, peak=None, rate=22050,
                     audio="pcm8", what="no limits: every change, exactly"),
}

# the box a canvas is fitted into, by name (VIDEO-PLAN 2.3)
PRESETS = {
    "cga": ("cga", 640, 200),
    "cga-small": ("cga", 320, 100),
    "herc": ("herc", 400, 200),
    "herc-mid": ("herc", 480, 232),
    "herc-full": ("herc", 720, 348),
    "vga": ("lin80", 320, 240),
    "vga-mid": ("lin80", 400, 300),
    "vga-full": ("lin80", 640, 480),
    # Live windowed's sizes (VIDEO-PLAN 3.4): small canvases a worker blits
    "live-cga": ("cga", 320, 100),
    "live-herc": ("herc", 240, 116),
    "live-vga": ("lin80", 160, 120),
}

CYC_AUDIO = 13.0        # the interrupt's copy of a PCM8 byte into the
                        # card's buffer (rep movsw, ~25 cycles a word)
REC_OVER = 6 + 10       # a record's header and its ten list terminators


def need_tools():
    if np is None:
        sys.exit("os88venc: needs numpy (pip install numpy)")
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            sys.exit("os88venc: needs %s on the PATH (apt-get install "
                     "ffmpeg)" % t)


def probe(path):
    """(width, height, display aspect, fps, duration, has audio)"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,sample_aspect_ratio,"
         "duration:format=duration", "-of", "default=nw=1", path],
        capture_output=True, text=True, check=True).stdout
    v, audio, dur = {}, False, None
    cur = {}
    for line in out.splitlines() + ["codec_type=end"]:
        k, _, val = line.partition("=")
        if k == "codec_type":
            if cur.get("codec_type") == "video" and not v:
                v = cur
            if cur.get("codec_type") == "audio":
                audio = True
            cur = {}
        cur[k] = val
        if k == "duration" and val not in ("", "N/A"):
            dur = max(dur or 0, float(val))
    if not v:
        raise vid.V88Error("%s: no video stream" % path)
    w, h = int(v["width"]), int(v["height"])
    n, _, d = v.get("r_frame_rate", "30/1").partition("/")
    fps = float(n) / float(d or 1)
    sar = v.get("sample_aspect_ratio", "1:1")
    sn, _, sd = sar.partition(":")
    try:
        sar = float(sn) / float(sd) if float(sn) > 0 else 1.0
    except (ValueError, ZeroDivisionError):
        sar = 1.0
    return w, h, w * sar / h, fps, dur, audio


def canvas_size(layout, bw, bh, dar, fit):
    """(width px, height, crop) of the canvas in a bw x bh box of `layout`
    for a source of display aspect `dar`. `fit` keeps the whole picture and
    shrinks the canvas to its shape (no bars: a bar would be screen the
    canvas does not need); `fill` crops the source to the box's shape;
    `stretch` fills the box and distorts. Width in whole bytes."""
    pw, ph = vid.ASPECT[vid.LAYOUT_BY_NAME[layout]]
    par = pw / ph                          # a pixel's width over its height
    box = bw * par / bh                    # the box's displayed aspect
    if fit == "fit":
        if dar >= box:
            w, h = bw, round(bw * par / dar)
        else:
            w, h = round(bh * dar / par), bh
        return max(8, w // 8 * 8), max(2, min(bh, h)), None
    w, h = bw // 8 * 8, bh
    if fit == "fill":
        return w, h, box
    return w, h, None


# --------------------------------------------------------------------------
# dithering: ordered, anchored to the canvas
# --------------------------------------------------------------------------
def bayer(n):
    m = np.array([[0]])
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / m.size


def bluenoise(n=64, seed=88):
    """A void-and-cluster threshold map (Ulichney, 1993): blue noise, so the
    dither has no pattern to beat against the picture - at a little more
    data than Bayer's, whose regular pattern runs and repeats better."""
    rnd = np.random.default_rng(seed)
    g = np.exp(-(np.arange(-n // 2, n // 2) ** 2) / (2 * 1.5 ** 2))
    k = np.fft.fft2(np.fft.ifftshift(np.outer(g, g)))

    def energy(b):
        return np.real(np.fft.ifft2(np.fft.fft2(b) * k))
    b = (rnd.random((n, n)) < 0.1).astype(float)
    while True:                             # relax the initial pattern
        e = energy(b)
        hi = np.unravel_index(np.argmax(np.where(b > 0, e, -1e9)), b.shape)
        b[hi] = 0
        e = energy(b)
        lo = np.unravel_index(np.argmin(np.where(b == 0, e, 1e9)), b.shape)
        if lo == hi:
            b[hi] = 1
            break
        b[lo] = 1
    rank = np.zeros((n, n))
    ones = int(b.sum())
    b1 = b.copy()
    for r in range(ones - 1, -1, -1):
        e = energy(b1)
        i = np.unravel_index(np.argmax(np.where(b1 > 0, e, -1e9)), b.shape)
        b1[i] = 0
        rank[i] = r
    b1 = b.copy()
    for r in range(ones, n * n):
        e = energy(b1)
        i = np.unravel_index(np.argmin(np.where(b1 == 0, e, 1e9)), b.shape)
        b1[i] = 1
        rank[i] = r
    return (rank + 0.5) / (n * n)


def threshold_map(kind, w, h):
    if kind == "threshold":
        return np.full((h, w), 0.5)
    m = bayer(8) if kind == "bayer" else bluenoise()
    reps = (-(-h // m.shape[0]), -(-w // m.shape[1]))
    return np.tile(m, reps)[:h, :w]


class Ditherer:
    """THE ENDS ARE SOLID. A threshold map spread over the whole of 0..255
    puts its lowest cell at grey 2 and its highest at 253, so a black that
    a lossy source delivers as 3 lights ONE dot in every 8 x 8 tile, and a
    white as 252 darkens one - an even grid of dots over every flat area,
    which also costs bytes as the noise flickers them. So the map spans
    `clip`..255-`clip`: at or below the first a pixel is black, at or above
    the second white, and the steps between keep their spacing"""

    def __init__(self, kind, w, h, stable, invert, clip=16):
        self.t = clip + threshold_map(kind, w, h) * (255.0 - 2 * clip)
        self.stable, self.invert = stable, invert
        self.prev = None

    def __call__(self, grey):
        g = grey.astype(float)
        if self.invert:
            g = 255.0 - g
        on = g > self.t
        if self.prev is not None and self.stable:
            keep = np.abs(g - self.t) < self.stable
            on = np.where(keep, self.prev, on)
        self.prev = on
        return np.packbits(on, axis=1)          # bit 7 = the leftmost


# --------------------------------------------------------------------------
# the budgeted encoder
# --------------------------------------------------------------------------
def span_cost(bs, run):
    """(cycles, bytes) of one span in the stream, wave 0's model: its
    list's entry and a skip byte (a segment's set-up amortised in)"""
    n = len(bs)
    if run or (n >= 7 and bs.count(bs[:1]) == n):
        c = vid.CYC_RUN[0] + vid.CYC_RUN[1] * n
        b = 2 + (2 if n < 256 else 3)
    elif n <= 6:
        c = vid.CYC_P[n - 1]
        b = 1 + n
    else:
        c = vid.CYC_SLICE[0] + vid.CYC_SLICE[1] * n
        b = 1 + n + (1 if n < 256 else 2)
    return c + 20, b


class Budget:
    """A token bucket: `per` a frame, holding at most `cap`, starting half
    full (the player fills its ring before the first frame)"""

    def __init__(self, per, cap):
        self.per, self.cap = per, cap
        self.level = cap / 2 if per is not None else None

    def tick(self):
        if self.per is not None:
            self.level = min(self.cap, self.level + self.per)

    def room(self):
        return math.inf if self.per is None else self.level

    def spend(self, n):
        if self.per is not None:
            self.level -= n


class Encoder:
    def __init__(self, g, prof, fps, audio_cyc, audio_bps):
        self.g = g
        period = vid.HZ / fps
        self.period = period
        if prof["avg"] is None:
            self.cpu = Budget(None, None)
            self.peak = math.inf
            self.disk = Budget(None, None)
        else:
            self.cpu = Budget(prof["avg"] * period - audio_cyc,
                              (prof["avg"] * period - audio_cyc) * fps)
            self.peak = prof["peak"] * period - audio_cyc
            vb = prof["disk"] * 0.99 - audio_bps     # super-packet padding
            if vb <= 0:
                raise vid.V88Error("the sound alone is %d bytes a second, "
                                   "and the profile's disk is %d"
                                   % (audio_bps, prof["disk"]))
            self.disk = Budget(vb / fps, vb)
        self.base = np.array(g.base, dtype=np.int64)
        self.idx = self.base[:, None] + np.arange(g.wb)
        self.screen = np.zeros((g.h, g.wb), dtype=np.uint8)
        self.age = np.zeros((g.h, g.wb), dtype=np.float32)
        self.surf = bytearray(65536)
        self.sv = np.frombuffer(self.surf, dtype=np.uint8)
        self.tsurf = bytearray(65536)
        self.tv = np.frombuffer(self.tsurf, dtype=np.uint8)
        self.wv = np.zeros(65537, dtype=np.float64)
        self.stats = dict(frames=0, exact=0, cut=0, bytes_left=0)

    def frame(self, target, audio=b""):
        """(the frame's writes, its record): the target's changes, or as
        many of them as the budgets allow, best first"""
        g = self.g
        self.cpu.tick()
        self.disk.tick()
        self.stats["frames"] += 1
        diff = target != self.screen
        self.age = np.where(diff, self.age + 1, 0)
        ys, xs = np.nonzero(diff)
        if not len(ys):
            self.stats["exact"] += 1
            return [], vid.record([], g, audio)
        self.tv[self.idx] = target
        sp = vid.spans((self.base[ys] + xs).tolist(), self.tsurf, g)
        cyc_room = min(self.cpu.room(), self.peak)
        byte_room = self.disk.room()
        costs = [span_cost(bs, run) for a, bs, run in sp]
        order = None
        er, eb = cyc_room - vid.CYC_FRAME, byte_room - REC_OVER
        for attempt in range(8):
            tc = sum(c for c, b in costs)
            tb = sum(b for c, b in costs)
            if tc <= er and tb <= eb:
                chosen = sp
            else:
                if order is None:
                    order = self.rank(target, sp, costs, er, eb)
                chosen, uc, ub = [], 0, 0
                for i in order:
                    c, b = costs[i]
                    if uc + c > er or ub + b > eb:
                        continue
                    chosen.append(sp[i])
                    uc += c
                    ub += b
                chosen.sort()
            rec = vid.record(chosen, g, audio)
            # the model's estimate is per span; the record is measured, and
            # a frame over its ceiling tries again with the estimate scaled
            mc = vid.cycles_of(rec)
            if mc <= cyc_room and len(rec) - len(audio) <= byte_room:
                break
            er *= min(0.97, cyc_room / mc)
            eb *= min(0.97, byte_room / max(1, len(rec) - len(audio)))
        if chosen is sp:
            self.stats["exact"] += 1
        else:
            self.stats["cut"] += 1
            self.stats["bytes_left"] += int(diff.sum()) - sum(
                len(bs) for a, bs, r in chosen)
        for a, bs, run in chosen:
            self.surf[a:a + len(bs)] = bs
        self.screen = self.sv[self.idx]
        return chosen, rec

    def rank(self, target, sp, costs, er, eb):
        """The spans' indexes, most pixels fixed per unit of the scarcer
        budget first; a pixel wrong for a while outweighs a fresh one"""
        g = self.g
        xor = np.bitwise_xor(target, self.screen)
        bits = np.unpackbits(xor, axis=1).reshape(g.h, g.wb, 8).sum(2)
        self.wv[:] = 0
        self.wv[self.idx] = bits * (1.0 + self.age / 8.0)
        cs = np.concatenate(([0.0], np.cumsum(self.wv)))
        pri = []
        for i, (a, bs, run) in enumerate(sp):
            c, b = costs[i]
            pri.append(((cs[a + len(bs)] - cs[a]) /
                        max(c / max(er, 1.0), b / max(eb, 1.0)), i))
        pri.sort(reverse=True)
        return [i for p, i in pri]

    def charge(self, rec, abytes):
        """What the record actually costs, measured, off the buckets (the
        sound's bytes are taken off the disk's rate at the start)"""
        c = vid.cycles_of(rec)
        self.cpu.spend(c)
        self.disk.spend(len(rec) - abytes)
        return c


# --------------------------------------------------------------------------
# the source
# --------------------------------------------------------------------------
def ffmpeg_video(src, w, h, crop_dar, fps_expr, start, end, eq):
    vf = []
    if crop_dar:
        vf.append("crop='if(gt(dar,%f),ih*%f*sar,iw)':'if(gt(dar,%f),ih,"
                  "iw/(%f)/sar)'" % (crop_dar, crop_dar, crop_dar, crop_dar))
    vf += ["fps=%s" % fps_expr, "scale=%d:%d:flags=area" % (w, h)]
    if eq:
        vf.append("eq=%s" % eq)
    vf.append("format=gray")
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", "%.3f" % start]
    cmd += ["-i", src]
    if end:
        cmd += ["-t", "%.3f" % (end - (start or 0))]
    cmd += ["-an", "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "gray",
            "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, dtype=np.uint8).reshape(h, w)
    p.wait()
    if p.returncode:
        raise vid.V88Error("ffmpeg failed on %s" % src)


def ffmpeg_audio(src, rate, start, end, volume):
    cmd = ["ffmpeg", "-v", "error", "-nostdin"]
    if start:
        cmd += ["-ss", "%.3f" % start]
    cmd += ["-i", src]
    if end:
        cmd += ["-t", "%.3f" % (end - (start or 0))]
    af = ["aresample=%d" % rate]
    if volume:
        af.append("volume=%s" % volume)
    cmd += ["-vn", "-ac", "1", "-af", ",".join(af), "-f", "u8", "-acodec",
            "pcm_u8", "-"]
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def auto_levels(src, w, h, crop, start, end, eq):
    """The grey levels the picture really spans - its 1st and 99th
    percentile over a frame a second - so a source that lives in the
    middle greys dithers to the whole of black-to-white. One bit a pixel
    has no contrast to spare."""
    hist = np.zeros(256)
    for f in ffmpeg_video(src, w, h, crop, "1", start, end, eq):
        hist += np.bincount(f.ravel(), minlength=256)
    c = np.cumsum(hist) / max(1.0, hist.sum())
    lo = int(np.searchsorted(c, 0.01))
    hi = int(np.searchsorted(c, 0.99))
    return lo, max(hi, lo + 16)


def stretch(f, lo, hi):
    return np.clip((f.astype(np.int32) - lo) * 255 // (hi - lo), 0,
                   255).astype(np.uint8)


# --------------------------------------------------------------------------
def encode(a, keep=None):
    """`keep`, a list, is given every frame's target: the gate's"""
    need_tools()
    prof = dict(PROFILES[a.profile])
    for k in ("disk", "avg", "peak"):
        if getattr(a, k) is not None:
            prof[k] = getattr(a, k)
    lay, bw, bh = PRESETS[a.preset] if a.preset else (a.layout, None, None)
    if a.layout:
        lay = a.layout
    if a.box:
        bw, bh = (int(v) for v in a.box.lower().split("x"))
    if bw is None:
        raise vid.V88Error("--box or --preset names the canvas")
    L = vid.LAYOUT_BY_NAME[lay]
    banks, stride, rows, _ = vid.LAYOUTS[L]
    if bw > stride * 8 or bh > rows:
        raise vid.V88Error("a %d x %d box does not fit %s (%d x %d)"
                           % (bw, bh, lay, stride * 8, rows))
    sw, sh, dar, sfps, dur, has_audio = probe(a.src)
    w, h, crop = canvas_size(lay, bw, bh, dar, a.fit)
    g = vid.Geom(L, w // 8, h)

    fps = a.fps or min(30.0, sfps)
    audio = a.audio or prof["audio"]
    if audio == "none" or not has_audio:
        afmt, rate, spf, abytes = vid.AUD_NONE, round(fps * 100), 100, 0
    else:
        afmt = vid.AUD_BY_NAME[audio]
        rate = a.rate or prof["rate"]
        spf = max(1, round(rate / fps))
        if afmt == vid.AUD_ADPCM4:
            spf += spf % 2
        abytes = spf // 2 if afmt == vid.AUD_ADPCM4 else spf
    fps = rate / spf
    audio_bps = abytes * fps
    audio_cyc = CYC_AUDIO * abytes if afmt else 0.0

    eq = []
    if a.gamma != 1.0:
        eq.append("gamma=%g" % a.gamma)
    if a.contrast != 1.0:
        eq.append("contrast=%g" % a.contrast)
    if a.brightness:
        eq.append("brightness=%g" % a.brightness)
    frames = ffmpeg_video(a.src, w, h, crop, "%d/%d" % (rate, spf), a.start,
                          a.end, ":".join(eq))
    say = (lambda *x: None) if a.quiet else print
    say("%s: %dx%d %.3f fps -> %s canvas %d x %d, %.3f fps (%d Hz / %d), "
        "audio %s, profile %s"
        % (a.src, sw, sh, sfps, lay, w, h, fps, rate, spf,
           {0: "none", 1: "PCM8", 2: "ADPCM4"}[afmt], a.profile))
    if a.levels == "auto":
        lo, hi = auto_levels(a.src, w, h, crop, a.start, a.end, ":".join(eq))
        say("   levels: grey %d..%d stretched to 0..255" % (lo, hi))
        frames = (stretch(f, lo, hi) for f in frames)
    dith = Ditherer(a.dither, w, h, a.stable, a.invert, a.clip)
    enc = Encoder(g, prof, fps, audio_cyc, audio_bps)
    wr = vid.Writer(g, rate, spf, afmt, abytes, vid.PF_MONO1,
                    title=a.title or os.path.splitext(
                        os.path.basename(a.src))[0][:47],
                    credits=a.credits or "", keysecs=a.keysecs)
    pcm = ffmpeg_audio(a.src, rate, a.start, a.end, a.volume) if afmt else b""
    cyc, recs, n = [], [], 0
    pend = []
    for grey in frames:
        pend.append(dith(grey))
    nf = len(pend)
    if keep is not None:
        keep.extend(pend)
    if not nf:
        raise vid.V88Error("no frames came out of %s" % a.src)
    chunks = vid.audio_chunks(pcm, nf, spf, afmt, vid.key_frames(
        nf, wr.keyint)) if afmt else None
    for f, target in enumerate(pend):
        au = chunks[f] if afmt else b""
        ops, rec = enc.frame(target, au)
        cyc.append(enc.charge(rec, len(au)) + audio_cyc)
        wr.frame(ops, enc.surf, au)
        if a.preview_png and f % max(1, round(fps)) == 0:
            vid.write_png(os.path.join(a.preview_png, "f%05d.png" % f),
                          g.wb, g.h, g.canvas(enc.surf))
        if not a.quiet and f % 300 == 299:
            print("   frame %d of %d" % (f + 1, nf), file=sys.stderr)
    poster = a.poster
    if a.poster_at is not None:
        # THE KEYFRAME NEAREST a moment, not the moment: the poster is a
        # keyframe index (SPEC.md 98.1.1) and the player opens at frame 0
        # whatever it is - it only chooses the picture in the box
        nk = len(wr.keys)
        poster = min(nk - 1, max(0, round(a.poster_at * fps / wr.keyint)))
    res = wr.write(a.out, poster)
    res.update(fps=fps, period=enc.period, audio_cyc=audio_cyc,
               audio_bps=audio_bps, prof=prof, w=w, h=h, layout=lay)
    secs = nf / fps
    st = enc.stats
    say("   %d frames, %.1f s: %d bytes = %.1f KB/s (%.1f video, %.1f "
        "audio)" % (nf, secs, res["bytes"], res["bytes"] / 1024.0 / secs,
                    (res["stream"] - audio_bps * secs) / 1024.0 / secs,
                    audio_bps / 1024.0))
    say("   CPU (wave 0 model, audio copy in): mean %.1f%%, worst %.1f%%; "
        "%d frames exact, %d cut to the budget (%.1f bytes a frame left "
        "wrong)" % (100 * sum(cyc) / nf / enc.period,
                    100 * max(cyc) / enc.period, st["exact"], st["cut"],
                    st["bytes_left"] / max(1, st["cut"])))
    say("   %d keyframes = %d bytes (%.1f%% of the file), poster %d"
        % (res["keys"], res["keybytes"],
           100.0 * res["keybytes"] / res["bytes"], res["poster"]))
    return res


def parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--layout", choices=sorted(vid.LAYOUT_BY_NAME))
    ap.add_argument("--box", help="WxH: the canvas's largest size")
    ap.add_argument("--fit", choices=("fit", "fill", "stretch"),
                    default="fit")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--fps", type=float)
    ap.add_argument("--profile", choices=sorted(PROFILES),
                    default="5150-st225")
    ap.add_argument("--disk", type=float, help="the profile's bytes a "
                    "second, overridden")
    ap.add_argument("--avg", type=float, help="...its average CPU share")
    ap.add_argument("--peak", type=float, help="...its per-frame ceiling")
    ap.add_argument("--audio", choices=("pcm8", "adpcm4", "none"))
    ap.add_argument("--rate", type=int)
    ap.add_argument("--volume", help="ffmpeg's volume= (e.g. 1.5, 3dB)")
    ap.add_argument("--dither", choices=("bayer", "bluenoise", "threshold"),
                    default="bayer")
    ap.add_argument("--stable", type=float, default=6.0,
                    help="grey levels either side of a threshold that keep "
                         "a pixel's last value (0: off)")
    ap.add_argument("--levels", choices=("auto", "none"), default="auto",
                    help="stretch the grey range the source uses to the "
                         "whole of black-to-white")
    ap.add_argument("--clip", type=float, default=16.0,
                    help="grey levels at each end that are solid black "
                         "or white, never a dot")
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--contrast", type=float, default=1.0)
    ap.add_argument("--brightness", type=float, default=0.0)
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--title")
    ap.add_argument("--credits")
    ap.add_argument("--keysecs", type=float, default=vid.KEY_SECS)
    ap.add_argument("--poster", type=int, help="the poster's keyframe "
                    "index (default: the first that is not one flat value)")
    ap.add_argument("--poster-at", type=float, metavar="SECS",
                    help="...or the keyframe nearest this many seconds into the "
                         "clip (after --start)")
    ap.add_argument("--preview-png", metavar="DIR",
                    help="the screen once a second, as PNGs")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--profiles", action="store_true",
                    help="list the profiles and presets")
    return ap


def main():
    ap = parser()
    if "--profiles" in sys.argv:
        for k, p in PROFILES.items():
            print("%-14s %s" % (k, p["what"]))
        for k, (lay, w, h) in PRESETS.items():
            print("%-14s %s %d x %d" % (k, lay, w, h))
        return 0
    a = ap.parse_args()
    if a.preview_png:
        os.makedirs(a.preview_png, exist_ok=True)
    try:
        encode(a)
    except (vid.V88Error, subprocess.CalledProcessError) as e:
        sys.exit("os88venc: %s" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
