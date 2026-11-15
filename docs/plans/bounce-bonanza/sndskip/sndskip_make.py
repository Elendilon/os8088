#!/usr/bin/env python3
"""The audition's WAVs and tables out of build/skout (after sndskip.py's rec / base / stat runs).
    python3 build/sndskip_make.py [--dst DIR]"""
import argparse, json, os, subprocess, sys, wave
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "tests")]
import os88marty as M, bonanza_perf as P
CLK = float(M.GUEST_HZ)
SUB = 1.0 / P.STEP_HZ
SRC = os.path.join(ROOT, "build", "skout")
NAMES = {0: "reference", 1: "few", 2: "medium", 3: "lot", 4: "realistic"}
CRS = {5: "summit", 3: "mill"}
RAWSFX = {"spk": ".pc_speaker.wav", "adlib": ".adlib_music_synthesizer.wav"}


def raw(path):
    import sndcheck
    r, x, _ = sndcheck.load(path)              # (tolerates the capture's header, as the rows do)
    return r, np.asarray(x, dtype=np.float64) * 32767.0


def passage(j, arm):
    r, x = raw(j["cap"] + RAWSFX[arm])
    whole = len(x) / r
    a, b = int(j["c0"] / CLK * r), int((j["c1"] / CLK + 0.6) * r)
    return r, x[a:b], whole


def env(x, r, ms=50):
    n = int(r * ms / 1000)
    k = len(x) // n
    return np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(axis=1))


def zc(x, r, ms=100):
    """the dominant pitch a window, by zero crossings (a square wave's)"""
    n = int(r * ms / 1000)
    k = len(x) // n
    y = x[:k * n].reshape(k, n) - x.mean()
    s = (y[:, 1:] >= 0) != (y[:, :-1] >= 0)
    return s.sum(axis=1) / 2.0 / (ms / 1000.0)


def onsets(arm, st):
    """-> (per source: notes sounded, keyed), the onsets' lateness in sub-ticks and in ms, outputs"""
    outs = st["outs"]
    segs, cur = [], []                      # THE DEMO's outputs alone: the title plays before and after it, and
    for o in outs:                          # the song's clock starts again at each (the longest run is the demo's)
        if cur and o["now"] < cur[-1]["now"]:
            segs.append(cur)
            cur = []
        cur.append(o)
    segs.append(cur)
    outs = max(segs, key=len)
    # the song's clock against the guest's: an output's time less its sub-tick's, least over the run
    off = min(o["c"] / CLK - o["now"] * SUB for o in outs[5:])
    late_s, late_ms = [], []
    sounded, seen_t0 = {}, {}
    keyed = {}
    pk = None
    for o in outs:
        if pk is not None:
            for i in range(6):
                keyed[i] = keyed.get(i, 0) + ((o["v"][i][1] - pk[i][1]) & 0xFF)
        pk = o["v"]
    fx = 0
    ptok = None
    for o in outs:
        hits = []
        if o["k"] == "tone":
            tok = o["tok"]
            src = tok >> 8
            if o["hz"] and tok != ptok:
                if src == 1:
                    fx += 1
                elif src in (2, 3, 4):
                    hits.append({2: 5, 3: 0, 4: 1}[src])
            ptok = tok
        else:
            b = bytes.fromhex(o["b"])
            for i in range(0, len(b), 2):
                reg, val = b[i], b[i + 1]
                if 0xB0 <= reg <= 0xB8 and val & 0x20:
                    c = reg - 0xB0
                    if c == 7:
                        fx += 1
                    elif c <= 6:
                        hits.append(min(c, 5))
        for vi in hits:
            t0 = o["v"][vi][0]
            if seen_t0.get(vi) == t0:
                continue                    # (the same note again: a pitch change, or the lead back after a blip)
            seen_t0[vi] = t0
            sounded[vi] = sounded.get(vi, 0) + 1
            late_s.append((o["now"] - t0) & 0xFFFF)
            late_ms.append((o["c"] / CLK - t0 * SUB - off) * 1000)
    return sounded, keyed, late_s, late_ms, fx, len(outs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dst", default=os.path.join(ROOT, "build", "skwav"))
    ap.add_argument("--tables", action="store_true", help="the figures only: no WAV is written")
    a = ap.parse_args()
    os.makedirs(a.dst, exist_ok=True)
    for arm in ("spk", "adlib"):
        for kd in (5, 3):
            recs = {}
            for t in range(5):
                p = os.path.join(SRC, "%s_kd%d_%d_%s.rec.json" % (arm, kd, t, NAMES[t]))
                if os.path.exists(p):
                    recs[t] = json.load(open(p))
            if not recs:
                continue
            cut = {t: passage(j, arm) for t, j in recs.items()}
            peak = max(np.abs(x).max() for _, x, _ in cut.values())
            gain = 0.89 * 32767 / peak                # one gain for the set: -1 dBFS at the set's loudest sample
            print("\n== %s, %s (BZD%d): one gain for the set, x%.3f (the set's peak %d of 32767)" % (
                arm, CRS[kd].upper(), kd, gain, peak))
            ref_env = None
            for t, j in sorted(recs.items()):
                r, x, whole = cut[t]
                out = os.path.join(a.dst, "%s_%s_%d_%s.wav" % (arm, CRS[kd], t, NAMES[t]))
                if not a.tables:
                  subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.4f" % (j["c0"] / CLK), "-t", "%.4f" % (
                    len(x) / r), "-i", j["cap"] + RAWSFX[arm], "-af", "volume=%.5f" % gain, "-ar", "44100", "-ac", "1",
                    "-c:a", "pcm_s16le", out], check=True)
                r2, y = raw(out)
                rms = np.sqrt((y ** 2).mean()) / 32767
                e = env(x, r)
                active = (e > 0.02 * peak).mean()
                if t == 0:
                    ref_env = e
                # the capture's clock is the guest's: the whole file's length against the cycles run
                drift = whole - j["cyc_end"] / CLK
                late = j["subtick_late"]
                tot = sum(late.values())
                l1 = sum(v for k, v in late.items() if int(k) == 1) / tot
                l2 = sum(v for k, v in late.items() if 2 <= int(k) < 8) / tot
                print("  %-28s %5.1f s %4.1f MB  rms %.3f  sounding %3.0f%% of 50 ms windows | frames %4d, sound calls "
                      "skipped %4d (%4.1f%%) | gap between sound calls mean %4.1f ms p95 %4.1f | sub-ticks output 1 "
                      "late %4.1f%%, 2+ late %4.1f%% | tones/batches %4d | missed refreshes %d | file - cycles %+.3f s" % (
                          os.path.basename(out), len(y) / r2, os.path.getsize(out) / 1e6, rms, 100 * active,
                          j["loop_frames"], j["skipped"], 100.0 * j["skipped"] / j["loop_frames"], j["gap_mean"],
                          j["gap_p95"], 100 * l1, 100 * l2, j["outputs"], j["bz_rmiss"], drift))
            # the outputs, from the stat runs
            ref = None
            for t in range(5):
                p = os.path.join(SRC, "%s_kd%d_%d_%s.stat.json" % (arm, kd, t, NAMES[t]))
                if not os.path.exists(p):
                    continue
                snd, keyed, ls, lms, fx, n = onsets(arm, json.load(open(p)))
                if t == 0:
                    ref = (snd, fx)
                ls, lms = np.array(ls), np.array(lms)
                names = {0: "lead", 1: "bass", 2: "chord", 3: "chord", 4: "chord", 5: "drum"}
                agg, aggk = {}, {}
                for vi, c in snd.items():
                    agg[names[vi]] = agg.get(names[vi], 0) + c
                for vi, c in keyed.items():
                    aggk[names[vi]] = aggk.get(names[vi], 0) + c
                lost = {k: ref_n - agg.get(k, 0) for k, ref_n in ((kk, sum(c for vi, c in ref[0].items() if names[vi] == kk))
                                                                 for kk in ("lead", "bass", "chord", "drum")) if ref_n}
                order = ("lead", "bass", "chord", "drum")
                print("  %-10s outputs %4d | notes sounded/keyed %s | fewer than the reference: %s | "
                      "effect onsets %d (ref %d) | onset late, sub-ticks: 0: %2.0f%% 1: %2.0f%% 2: %2.0f%% 3+: %2.0f%% | "
                      "ms: median %3.0f p90 %3.0f max %3.0f" % (
                          NAMES[t], n, " ".join("%s %d/%d" % (k, agg.get(k, 0), aggk.get(k, 0)) for k in order if aggk.get(k)),
                          " ".join("%s %d" % (k, v) for k, v in lost.items()), fx, ref[1],
                          100 * (ls == 0).mean(), 100 * (ls == 1).mean(), 100 * (ls == 2).mean(), 100 * (ls >= 3).mean(),
                          np.median(lms), np.percentile(lms, 90), lms.max()))
            # the reference against the NO-KNOB build's capture
            p = os.path.join(SRC, "%s_kd%d_0_reference_noknob.rec.json" % (arm, kd))
            if os.path.exists(p) and 0 in recs:
                j = json.load(open(p))
                r, x, _ = passage(j, arm)
                r0, x0, _ = cut[0]
                e, e0 = env(x, r), env(x0, r0)
                k = min(len(e), len(e0))
                best = max(np.corrcoef(e[s:k], e0[:k - s])[0, 1] for s in range(0, 4))
                line = "  the reference against the NO-KNOB build's capture: %.1f s / %.1f s, rms %.0f / %.0f, 50 ms envelope correlation %.3f" % (
                    len(x) / r, len(x0) / r0, np.sqrt((x ** 2).mean()), np.sqrt((x0 ** 2).mean()), best)
                if arm == "spk":
                    f, f0 = zc(x, r), zc(x0, r0)
                    k = min(len(f), len(f0))
                    same = (np.abs(f[:k] - f0[:k]) <= 0.06 * np.maximum(f0[:k], 1)).mean()
                    line += ", the 100 ms windows' pitch within 6%%: %.0f%%" % (100 * same)
                print(line)


if __name__ == "__main__":
    main()
