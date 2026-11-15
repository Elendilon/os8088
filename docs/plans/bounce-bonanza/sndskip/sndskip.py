#!/usr/bin/env python3
"""BONANZA: the SKIP AUDITION's recordings and figures (scratch, agent SOUND, round 2).

The knob build (nasm -DBZS_SKIPTEST, apps/bonanza/bzgame.inc) is made into build/sk/ by build/sndskip_build.sh.

    python3 build/sndskip.py survey                      # the demos: length, events, notes (speaker)
    python3 build/sndskip.py rec  [--adlib] --kd 5 --take 0..4 --out DIR     # one WAV take (logged breakpoints only)
    python3 build/sndskip.py stat [--adlib] --kd 5 --take 0..4 --out DIR     # the same take under stops: the outputs
    python3 build/sndskip.py base [--adlib] --kd 5 --out DIR                 # the NO-KNOB build's capture

Takes: 0 reference ([bz_sskip] 0), 1 few (16), 2 medium (4), 3 a lot (2), 4 the rule (255).
"""
import argparse
import json
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_perf as P       # noqa: E402

R.LOCAL_SYMS = tuple(R.LOCAL_SYMS) + (("bzs_steps", "s"), ("bzs_spk", "tone"), ("bzs_fm", "call"))
TAKES = {0: ("reference", 0), 1: ("few", 16), 2: ("medium", 4), 3: ("lot", 2), 4: ("realistic", 255)}
SK = os.path.join(ROOT, "build", "sk")
CLK = float(M.GUEST_HZ)
V_SIZE, V_T0, V_KEYS = 26, 6, 18
SUB_MS = 1000.0 / P.STEP_HZ


def boot(adlib, knob=True, wav=None):
    if wav:
        os.environ["MARTYPC_WAV"] = wav
    try:
        ui = os88ui.boot(R.at("build/os8088-360.img"),
                         apps=os.path.join(SK, "bonanza360.img") if knob else R.at("build/bonanza360.img"),
                         machine=P.ADLIB if adlib else R.MACHINE["cga"])
    finally:
        os.environ.pop("MARTYPC_WAV", None)
    return ui


def open_game(ui, knob=True):
    sym = R.symbols(os.path.join(SK, "src") if knob else None)
    ui.open_drive("B")
    ui.open("BONANZA.O88")
    g = R.Bz(ui, "cga", sym)
    ui.settle()
    return g


def play(g, tr):
    m = g.m
    g.key("KeyD")
    M.until(m, lambda _: g.b("bz_fs") == 1, "the demo starts", guest=60)
    M.until(m, lambda _: g.b("bz_fs") == 0, "the demo's frames", guest=120 * P.DEMO_CAP // P.BENCH)
    m.pause()
    hits = tr.hits
    assert not tr.overflowed
    m.run()
    return hits


def frame_stats(g, hits, names):
    """the logged hits -> the calls' times, sub-ticks a call, gaps"""
    by = {g.a(n) & 0xFFFFF: n for n in names}
    calls, cur = [], None
    for h in hits:
        n = by.get(h["addr"] & 0xFFFFF)
        if n == "bzs_frame":
            cur = [h["cycles"], 0, 0]
            calls.append(cur)
        elif n == "bz_presented":               # (after the last frame the desktop's title steps: not a call's)
            cur = None
        elif cur is not None and n == "bzs_steps.s":
            cur[1] += 1
        elif cur is not None and n in ("bzs_spk.tone", "bzs_fm.call"):
            cur[2] += 1
    pres = [h["cycles"] for h in hits if by.get(h["addr"] & 0xFFFFF) == "bz_presented"]
    return calls, pres


def summarize(calls, pres, g, knob):
    gaps = [(b[0] - a[0]) / CLK * 1000 for a, b in zip(calls, calls[1:])]
    late = {}
    for c in calls:                     # a sub-tick stepped i-th from the call's end is i sub-ticks late
        for i in range(c[1]):
            k = c[1] - 1 - i
            late[k] = late.get(k, 0) + 1
    per = {}
    for c in calls:
        per[c[1]] = per.get(c[1], 0) + 1
    st = P.stats(gaps)
    out = {"calls": len(calls), "frames": len(pres), "secs": (calls[-1][0] - calls[0][0]) / CLK,
           "gap_mean": st["mean"], "gap_p95": st["p95"], "gap_max": st["max"],
           "gap_hist": {k: sum(1 for x in gaps if lo <= x < hi) for k, lo, hi in (
               ("<25ms", 0, 25), ("25-42", 25, 42), ("42-58", 42, 58), ("58-75", 58, 75), (">=75", 75, 1e9))},
           "subs_per_call": per, "subtick_late": late, "outputs": sum(c[2] for c in calls),
           "c0": calls[0][0], "c1": calls[-1][0]}
    if knob:
        out["skipped"] = g.w("bz_ssn")
        out["loop_frames"] = g.w("bz_ssf")
    for n in ("bz_rframes", "bz_rmiss", "bz_nhvy", "bz_nbnc", "bz_nland"):
        if n in g.sym:
            out[n] = g.w(n)
    return out


def rec(a, knob=True):
    name, val = TAKES[a.take]
    arm = "adlib" if a.adlib else "spk"
    tag = "%s_kd%d_%d_%s%s" % (arm, a.kd, a.take, name, "" if knob else "_noknob")
    cap = os.path.join(a.out, "raw_" + tag)
    with boot(a.adlib, knob, wav=cap) as ui:
        g = open_game(ui, knob)
        m = g.m
        P.load_demo(g, a.kd)
        P.set_snd(g, True)
        if knob:
            m.pause()
            g.putb("bz_sskip", val)
            m.run()
        names = ["bzs_frame", "bzs_steps.s", "bzs_spk.tone", "bzs_fm.call", "bz_presented"]
        ad = [g.a(n) for n in names]
        with M.bp_trace(m, *ad, log=ad, cap=900000) as tr:
            hits = play(g, tr)
        R.dropped(g, "the demo")
        calls, pres = frame_stats(g, hits, names)
        summ = summarize(calls, pres, g, knob)
        summ["arm"] = g.b("bzs_arm")
        M.pace(m, 0.5)
        m.pause()
        summ["cyc_end"] = m.status()["cycles"]
    summ["tag"], summ["cap"] = tag, cap
    json.dump(summ, open(os.path.join(a.out, tag + ".rec.json"), "w"))
    print(json.dumps(summ))


def stat(a):
    """the same take under STOPS (no capture): every tone / batch with the song's sub-tick and the voices' stamps"""
    name, val = TAKES[a.take]
    arm = "adlib" if a.adlib else "spk"
    tag = "%s_kd%d_%d_%s" % (arm, a.kd, a.take, name)
    with boot(a.adlib) as ui:
        g = open_game(ui)
        m = g.m
        P.load_demo(g, a.kd)
        P.set_snd(g, True)
        m.pause()
        g.putb("bz_sskip", val)
        m.run()
        tone, call = g.a("bzs_spk.tone") & 0xFFFFF, g.a("bzs_fm.call") & 0xFFFFF
        outs = []

        def on_hit(mm, rec):
            raw = bytes(mm.read(g.a("bzs_v"), 8 * V_SIZE))
            v = [(struct.unpack_from("<H", raw, i * V_SIZE + V_T0)[0], raw[i * V_SIZE + V_KEYS], raw[i * V_SIZE])
                 for i in range(6)]
            now = g.w("bzs_nsub")
            if rec["addr"] == tone:
                r = mm.regs()
                outs.append({"k": "tone", "c": rec["cycles"], "now": now, "hz": r["ax"], "dur": r["cx"],
                             "tok": g.w("bzs_stok"), "v": v})
            else:
                n = g.w("bzs_fmn")
                outs.append({"k": "oplw", "c": rec["cycles"], "now": now,
                             "b": bytes(mm.read(g.a("bzs_fmb"), 2 * n)).hex(), "v": v})
        with M.bp_trace(m, tone, call, on_hit=on_hit, cap=40000) as tr:
            play(g, tr)
        R.dropped(g, "the demo")
        raw = bytes(m.read(g.a("bzs_v"), 8 * V_SIZE))
        res = {"outs": outs, "skipped": g.w("bz_ssn"), "loop_frames": g.w("bz_ssf"), "end_nsub": g.w("bzs_nsub"),
               "fxseq": g.w("bzs_fxseq")}
    json.dump(res, open(os.path.join(a.out, tag + ".stat.json"), "w"))
    print("%s: %d outputs, skipped %d of %d frames, %d sub-ticks" % (tag, len(outs), res["skipped"],
                                                                    res["loop_frames"], res["end_nsub"]))


def survey(a):
    with boot(False) as ui:
        g = open_game(ui)
        m = g.m
        for kd in range(1, 7):
            P.load_demo(g, kd)
            P.set_snd(g, True)
            names = ["bzs_frame", "bzs_steps.s", "bzs_spk.tone", "bzs_fm.call", "bz_presented", "bzs_trig", "bzs_kv",
                     "bzs_fx1"]
            ad = [g.a(n) for n in names]
            with M.bp_trace(m, *ad, log=ad, cap=900000) as tr:
                hits = play(g, tr)
            R.dropped(g, "the demo")
            by = {g.a(n) & 0xFFFFF: n for n in names}
            cnt = {}
            for h in hits:
                n = by.get(h["addr"] & 0xFFFFF)
                cnt[n] = cnt.get(n, 0) + 1
            t = [h["cycles"] for h in hits if by.get(h["addr"] & 0xFFFFF) == "bzs_frame"]
            secs = (t[-1] - t[0]) / CLK
            print("BZD%d: %.1f s, %d frames, %d effects triggered (%.2f/s), %d effect sub-ticks, %d notes keyed "
                  "(%.1f/s), %d tones (%.1f/s), misses %d, heavy %d" % (
                      kd, secs, cnt.get("bz_presented", 0), cnt.get("bzs_trig", 0), cnt.get("bzs_trig", 0) / secs,
                      cnt.get("bzs_fx1", 0), cnt.get("bzs_kv", 0), cnt.get("bzs_kv", 0) / secs,
                      cnt.get("bzs_spk.tone", 0), cnt.get("bzs_spk.tone", 0) / secs, g.w("bz_rmiss"), g.w("bz_nhvy")),
                  flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("survey", "rec", "stat", "base"))
    ap.add_argument("--adlib", action="store_true")
    ap.add_argument("--kd", type=int, default=5)
    ap.add_argument("--take", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "skout"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.mode == "survey":
        survey(a)
    elif a.mode == "rec":
        rec(a)
    elif a.mode == "base":
        a.take = 0
        rec(a, knob=False)
    else:
        stat(a)


if __name__ == "__main__":
    main()
