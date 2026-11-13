#!/usr/bin/env python3
"""BONANZA: a play recorded, and replayed on the guest and on the host model, the same run (SPEC.md 128.11.12, 128.11.17.2).

    make bonanzadisk && python3 tests/bonanza_replay.py [--leg record|replay|inject|all]
    python3 tests/bonanza_replay.py --red hopbit|framekeys     (a red arm, below)
    python3 tests/bonanza_replay.py --check                     (the host half only)

Physics is a function of the step count and the key byte alone, so a play is
its course, its ball and a byte a step (128.11.12.1): the package RECORDS
every step's key byte into bz_rlog (BZR1, run-length pairs), and R on the
desktop REPLAYS it.  This row holds the recorder, the player and
bbcourse.Physics.run_log to one another:

  1  RECORD (the CGA): N on the desktop (the course a play starts on: FIRST,
     then TRIAL - [bz_crsel] must name TRIAL, and [bz_matsel] TRIAL's ball),
     Enter, then REAL keys held and released through MartyPC's debug server
     at chosen frames for about 600 frames - every arrow, Space (a Hop),
     Left Shift (Grip), the chord off H's lip and the bounce over the gap -
     and Esc.  At every frame's bz_presented the guest's state is read (the
     eight values and 128.11.8.1's).  Then bz_rlog is read out: its runs,
     decoded, run through bbcourse.Physics from the course's start must
     equal the guest's state at EVERY one of those frames and at the play's
     end; and the log must be COMPLETE - `BZR1`, the course and the ball the
     play's, flags COMPLETE and not TRUNCATED, its step count the play's
     final nstep and the sum of its runs.
  2  REPLAY, both cards: R on the CGA that recorded it, and on the Hercules
     with the CGA's log poked into bz_rlog: every frame's state equals the
     model's after that many of the log's steps, the replay ends the frame
     after the log's last step, its end state is the PLAY's end state (the
     CGA's frames fall differently from the Hercules's; the steps do not),
     and a replay records nothing (bz_rlog unchanged by it).
  3  INJECT, both cards: three logs the row builds on the host - rubber with
     every key bit (each arrow, Space, Left Shift), a Hop from the ground, a
     Hop at its contact and a bounce CAUGHT by Grip; steel stunned on F;
     glass shattered on F and respawned - each PROVED on the model first
     (those events, at those steps), poked into bz_rlog and replayed with R,
     every frame against the model.

--red NAME builds a broken package in a temporary directory (never build/)
and PASSES only if the record leg FAILS - at its own check:
  hopbit     the recorder stores the key byte WITHOUT bit 4 (Space): the
             model run off the log parts from the play at its first Hop
  framekeys  the recorder appends once a FRAME instead of once a step - a
             frame of no step (about 9% of the CGA's: 0.911 steps a frame)
             appends a byte, a frame of two one: the model run off the log
             parts from the play at the first key change after such a frame
             (checked before the log's step count, which this also breaks)
"""
import argparse
import os
import struct
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import os88marty as M          # noqa: E402
import os88ui                  # noqa: E402
import bbcourse as BB          # noqa: E402
import bonanza_ring as R       # noqa: E402
import bonanza_phys as P       # noqa: E402

K = BB
CX = K.K_R | K.K_D                  # the chord along +wx: off H's lip, over the gap
PLAY_FRAMES = 600
# the record leg's script: frame -> keys pressed (+) and released (-) at that
# frame's bz_presented.  Space at 12 (a Hop), every arrow, Left Shift, the
# chord off H's lip at 60 (the bounce on F and over the gap), Grip over G,
# Space in the air and on the ground again, and everything up before Esc
SCRIPT = {
    12: ["+Space"], 15: ["-Space"],
    25: ["+ArrowLeft"], 31: ["-ArrowLeft", "+ArrowUp"], 37: ["-ArrowUp", "+ArrowRight"],
    43: ["-ArrowRight", "+ArrowDown"], 49: ["-ArrowDown"],
    60: ["+ArrowRight", "+ArrowDown"],
    230: ["+ShiftLeft"], 260: ["-ShiftLeft"],
    300: ["+Space"], 303: ["-Space"], 330: ["+Space"], 334: ["-Space"],
    360: ["-ArrowRight", "-ArrowDown", "+ArrowLeft"], 400: ["-ArrowLeft", "+ArrowUp"],
    430: ["+ShiftLeft"], 460: ["-ArrowUp", "-ShiftLeft", "+ArrowDown"], 500: ["-ArrowDown", "+ArrowRight"],
    520: ["+Space"], 524: ["-Space"], 560: ["-ArrowRight"],
}


def lenient(log):
    """the log's RUNS as key bytes, whatever its header's step count says (the
    framekeys red breaks that count; its own check comes first)"""
    n = struct.unpack_from("<H", log, 12)[0]
    keys = []
    for i in range(min(n, BB.RLOG_RUNS)):
        k, c = log[BB.RLOG_HDR + 2 * i], log[BB.RLOG_HDR + 2 * i + 1]
        keys += [k] * c
    return keys


def boot(tag, apps, src):
    sym = R.symbols(src)
    ui = os88ui.boot(R.at("build/os8088-360.img"), apps=apps or R.at("build/bonanza360.img"),
                     machine=R.MACHINE[tag])
    return ui, sym


def open_pkg(ui, tag, sym):
    ui.open_drive("B")
    ui.open("BONANZA.O88")
    g = R.Bz(ui, tag, sym)
    ui.settle()
    return g


def record(g):
    """Part 1: N to TRIAL, Enter, the script's real keys, Esc.  -> (failures,
    the log, the frames' states {nstep: (state, state2)}, the end state)"""
    m = g.m
    rd = P.Reader(g)
    fails = []
    m.pause()
    k0 = g.b("bz_crsel")
    m.run()
    g.key("KeyN")
    M.until(m, lambda _: g.b("bz_crsel") != k0, "N to change the course", guest=10)
    m.pause()
    crs, mat = g.b("bz_crsel"), g.b("bz_matsel")
    tcrs = R.course("trial")
    if crs != R.CRS_K["trial"] or mat != tcrs.ball:
        fails.append("record: N chose course %d with ball %d, not TRIAL (%d) with its ball %d" % (
            crs, mat, R.CRS_K["trial"], tcrs.ball))
        return fails, None, {}, None
    m.run()
    m.bp_exec(g.a("bz_presented"))
    g.key("Enter")
    held, seen, frames = set(), {}, 0
    while frames < PLAY_FRAMES:
        assert m.wait_stop(60) == "breakpoint", "the play stopped presenting (frame %d)" % frames
        if not frames:
            g.check_base()
            if g.b("bz_mode") != 0 or g.b("bz_crs") != crs:
                fails.append("record: Enter launched mode %d on course %d, not a play of TRIAL" % (
                    g.b("bz_mode"), g.b("bz_crs")))
                break
        frames += 1
        st, s2, ext = rd.read()
        seen[st[0]] = (st, s2, dict(ext), frames)
        for act in SCRIPT.get(frames, ()):
            name = act[1:]
            if act[0] == "+":
                m.key(name, up=False)
                held.add(name)
            else:
                m.key(name, down=False)
                held.discard(name)
        m.run()
    m.bp_exec()
    m.run()                                     # (the last run may have stopped on bz_presented
    for name in sorted(held):                   # again before the breakpoint was cleared)
        m.key(name, down=False)
    g.key("Escape")
    M.until(m, lambda _: g.b("bz_fs") == 0, "the play ends on Esc", guest=60)
    P.dropped(g, "the recorded play")
    m.pause()
    end = rd.read()
    log = g.read_log()
    m.run()
    return fails, log, seen, end


def judge_record(log, seen, end, crs_k, mat):
    """the log against the play: -> (failures, the model)"""
    fails = []
    keys = lenient(log)
    p = BB.Physics(R.course_k(crs_k), play=True, mat=mat)
    for n in sorted(seen):
        st, s2, ext, fr = seen[n]
        if n > len(keys):
            fails.append("record: the model run off the LOG parts from the play at frame %d: the play is at step "
                         "%d, the log's runs hold %d steps" % (fr, n, len(keys)))
            return fails, p
        P.advance(p, n, keys)
        if st != p.state() or s2 != p.state2():
            fails.append("record: the model run off the LOG parts from the play at frame %d (%d steps since the "
                         "last frame), step %d:\n      play  %s\n            %s\n      model %s\n            %s" % (
                             fr, n - max([0] + [x for x in seen if x < n]), n, P.show(st), P.show2(s2),
                             P.show(p.state()), P.show2(p.state2())))
            return fails, p
    if log[:4] != b"BZR1":
        fails.append("record: bz_rlog does not start BZR1 (%r)" % log[:4])
        return fails, p
    c, mt, flags, _, steps, nruns, _ = struct.unpack_from("<BBBBIHH", log, 4)
    if (c, mt) != (crs_k, mat):
        fails.append("record: the log names course %d ball %d, the play was %d with %d" % (c, mt, crs_k, mat))
    if not flags & BB.RL_COMPLETE or flags & BB.RL_TRUNC:
        fails.append("record: the log's flags %02X: not COMPLETE, or TRUNCATED" % flags)
    if not (steps == len(keys) == end[0][0]):
        fails.append("record: the log's step count %d, its runs' sum %d, the play's last step %d: not one number" % (
            steps, len(keys), end[0][0]))
    try:
        _, _, dk, _ = BB.decode_log(log)
        q = BB.Physics(R.course_k(crs_k), play=True, mat=mat).run_log(log)
        if q.state() != end[0][:8] or q.state2() != end[1]:
            fails.append("record: Physics.run_log over the log ends at %s, the play at %s" % (
                P.show(q.state()), P.show(end[0])))
    except ValueError as e:
        fails.append("record: bbcourse.decode_log refuses the log: %s" % e)
    return fails, p


def replay(g, log, model_of, end=None, what="replay"):
    """R with LOG in bz_rlog: every frame against the model, the end, nothing
    recorded.  MODEL_OF() -> a fresh Physics at the log's start.  END: the
    play's end state to equal.  -> (failures, frames)"""
    m, tag = g.m, g.tag
    rd = P.Reader(g)
    keys = BB.decode_log(log)[2]
    fails = []
    m.pause()
    g.write_log(log)
    wk = R.Walker(g, t0=True)
    m.bp_exec(wk.t0)
    m.run()                                     # (paused for the write: R needs a running guest,
    g.key("KeyR")                               # and wait_stop measures from this resume)
    assert m.wait_stop(60) == "breakpoint", "R did not start the replay"
    if g.b("bz_mode") != 2:
        fails.append("%s: R launched mode %d, not a replay" % (what, g.b("bz_mode")))
    p = model_of()
    wk.arm()
    frames = 0
    while not fails:
        k = wk.next()
        if k == "t0":
            if g.b("bz_goal") or not (g.b("bz_rn") or g.w("bz_rruns")):
                break
            continue
        if k != "pr":
            continue
        frames += 1
        st, s2, ext = rd.read()
        P.advance(p, st[0], keys)
        bad = P.compare("%s (%s)" % (what, tag), frames, st, s2, ext, p)
        if bad:
            fails.append(bad)
            break
        if frames > len(keys) * 5 // 4 + 50:      # (the CGA steps 0.911 a frame: the
                                                    # bound is a runaway's, not a rate)
            fails.append("%s: the replay ran %d frames past its %d steps" % (what, frames, len(keys)))
    m.bp_exec()
    m.run()
    M.until(m, lambda _: g.b("bz_fs") == 0, "the %s to end" % what, guest=60)
    P.dropped(g, what)
    m.pause()
    st, s2, ext = rd.read()
    after = g.read_log()
    m.run()
    if not fails:
        P.advance(p, st[0], keys)
        stop = p.nstep if p.goal else len(keys)
        if st[0] != stop:
            fails.append("%s: the replay ended after step %d, its log holds %d" % (what, st[0], len(keys)))
        if end is not None and (st != end[0] or s2 != end[1]):
            fails.append("%s (%s): the replay's end state is not the play's:\n      replay %s\n      play   %s" % (
                what, tag, P.show(st), P.show(end[0])))
        if after[:len(log)] != log:
            fails.append("%s: bz_rlog changed under the replay (a replay records nothing)" % what)
    print("%s %s: %d frames to step %d, every frame the model's%s: %s" % (
        tag, what, frames, st[0], " and the end the play's" if end else "", "yes" if not fails else "NO"),
        flush=True)
    return fails, frames


def injects():
    """the inject leg's logs, built and PROVED on the model: -> [(name, course K,
    material, keys, proof line, ok)]"""
    trial = R.course("trial")
    k_trial = R.CRS_K["trial"]

    def run(keys, mat=0):
        p = BB.Physics(trial, play=True, mat=mat)
        for k in keys:
            p.step(k)
            if p.goal:
                break
        return p
    out = []
    keys = [0] * 4 + [K.K_L] * 5 + [K.K_R] * 5 + [K.K_U] * 5 + [K.K_D] * 5 + [0] * 10 + [K.K_HOP] * 2
    p = run(keys + [0] * 60)
    c1 = [e[1] for e in p.events if e[0] in ("bounce", "land") and e[1] > len(keys) - 2]
    t = c1[0] if c1 else len(keys) + 20
    keys += [0] * max(1, t - len(keys) - 3) + [K.K_HOP] * 2 + [0] * 30
    p = run(keys + [CX] * 200)
    to = [e[1] for e in p.events if e[0] == "takeoff" and e[1] > len(keys)]
    ct = [e[1] for e in p.events if e[0] in ("bounce", "land") and to and e[1] > to[0]]
    if to and ct:
        keys += [CX] * (to[0] - len(keys)) + [CX | K.K_GRIP] * (ct[0] - to[0] + 2) + [CX] * 40 + [0] * 20
    p = run(keys)
    q = run(keys[:ct[0] - 2] + [CX] * 4) if ct else None
    kinds = [e[0] for e in p.events]
    caught = ct and [e for e in p.events if e[1] == ct[0] and e[0] == "land"] and q is not None and \
        [e for e in q.events if e[1] == ct[0] and e[0] == "bounce"]
    bits = 0
    for k in keys:
        bits |= k
    out.append(("rubber", k_trial, 0, keys, "every key bit (%02X), a Hop, a Hop at its contact, a bounce CAUGHT by Grip "
                "at step %s; events %s" % (bits, ct[0] if ct else None, kinds),
                bits == 0x3F and "hop" in kinds and "hopc" in kinds and bool(caught)))
    for mat, ev in ((1, "stun"), (2, "shatter")):
        keys = [0] * 4 + [CX] * 200
        p = run(keys, mat)
        kinds = [e[0] for e in p.events]
        keys = keys[:p.nstep]
        out.append((BB.MAT_NAMES[mat], k_trial, mat, keys, "%s on F; events %s" % (ev, kinds),
                    ev in kinds and (ev != "shatter" or "respawn" in kinds)))
    return out


def run_all(legs, apps=None, src=None):
    fails, logs, ends = [], {}, {}
    inj = injects() if "inject" in legs else []
    for name, _, _, _, what, ok in inj:
        if not ok:
            fails.append("inject %s: the model does not prove it (%s)" % (name, what))
    if fails:
        return fails
    for tag in ("cga", "herc"):
        if tag == "herc" and "replay" not in legs and "inject" not in legs:
            break
        booted, sym = boot(tag, apps, src)
        with booted as ui:                      # (the UI is what the context YIELDS)
            g = open_pkg(ui, tag, sym)
            if tag == "cga" and ("record" in legs or "replay" in legs):
                f, log, seen, end = record(g)
                fails += f
                if not f:
                    k, mat = log[4], log[5]
                    f2, p = judge_record(log, seen, end, k, mat)
                    fails += f2
                    print("cga record: %d frames of TRIAL, %d steps, %d runs; the model run off the log equals the "
                          "play at every frame and at its end: %s; events %s" % (
                              len(seen), end[0][0], struct.unpack_from("<H", log, 12)[0], "yes" if not f2 else "NO",
                              ", ".join(sorted(set(e[0] for e in p.events if e[0] != "corner")))), flush=True)
                    if not f2:
                        logs["play"], ends["play"] = log, end
            if "replay" in legs and "play" in logs:
                log = logs["play"]
                k, mat = log[4], log[5]
                f, _ = replay(g, log, lambda: BB.Physics(R.course_k(k), play=True, mat=mat), ends["play"],
                              "replay of the CGA's play")
                fails += f
            if "inject" in legs:
                for name, k, mat, keys, what, _ in inj:
                    log = BB.encode_log(keys, course=k, mat=mat)
                    f, _ = replay(g, log, lambda k=k, mat=mat: BB.Physics(R.course_k(k), play=True, mat=mat),
                                  None, "inject %s" % name)
                    fails += f
        if fails:
            break
    return fails


REDS = {
    # the recorder stores the run's byte without bit 4 (Space)
    "hopbit": [("bzgame.inc", "    mov ah, [bz_rn]\n    or ah, ah\n    jz .out\n    mov al, [bz_rk]\n",
                "    mov ah, [bz_rn]\n    or ah, ah\n    jz .out\n    mov al, [bz_rk]\n"
                "    and al, 0efh                ; RED hopbit: Space not recorded\n")],
    # the recorder appends once a FRAME: bz_play records the frame's key byte
    # before its steps (a frame of no step too), and bz_step records nothing
    "framekeys": [("bzgame.inc", "    mov byte [bz_resp], 0       ; (a respawn in this frame's steps: the cut)\n",
                   "    mov byte [bz_resp], 0       ; (a respawn in this frame's steps: the cut)\n"
                   "    cmp byte [bz_mode], 0       ; RED framekeys: once a frame\n    jne .redfk\n"
                   "    mov bl, [bz_keys]\n    cmp bl, [bz_rk]\n    jne .redrec\n    cmp byte [bz_rn], 255\n"
                   "    jae .redrec\n    inc byte [bz_rn]\n    jmp short .redfk\n.redrec:\n    call bz_rrec\n"
                   ".redfk:\n"),
                  ("bzphys.inc", "    mov bl, [bz_keys]           ; PLAY: the frame's (bz_input), RECORDED - the\n",
                   "    mov bl, [bz_keys]           ; PLAY: the frame's (bz_input), RECORDED - the\n"
                   "    jmp short .key              ; RED framekeys: not a step's\n")],
}
RED_WANT = {"hopbit": "parts from the play", "framekeys": "parts from the play"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", choices=("record", "replay", "inject", "all"), default="all")
    ap.add_argument("--red", choices=sorted(REDS))
    ap.add_argument("--check", action="store_true",
                    help="the host half only: the inject logs proved on the model, every red arm assembled")
    a = ap.parse_args()
    if a.check:
        bad = 0
        for name, k, mat, keys, what, ok in injects():
            print("bonanza_replay inject %s: %d steps, %s: %s" % (name, len(keys), what, "proved" if ok else "NOT"))
            bad += not ok
        for line in R.check_reds(REDS, "bonanza_replay"):
            print(line)
        assert not bad, "%d inject log(s) not proved on the model" % bad
        return
    legs = ("record", "replay", "inject") if a.leg == "all" else (a.leg,)
    if a.red:
        with tempfile.TemporaryDirectory() as td:
            src, img = R.build_tree(td, REDS[a.red])
            try:
                bad = run_all(("record",), apps=img, src=src)
            except AssertionError as e:
                bad = ["assertion: %s" % e]
            for b in bad:
                print("  red %s: %s" % (a.red, b))
            assert bad, "RED ARM %s: the row stayed GREEN against a broken recorder" % a.red
            assert any(RED_WANT[a.red] in b for b in bad[:1]), \
                "RED ARM %s went red, but not at its own check (%r): %s" % (a.red, RED_WANT[a.red], bad)
        print("bonanza_replay --red %s: PASS (the row fails against the broken package)" % a.red)
        return
    bad = run_all(legs)
    for b in bad:
        print("FAIL %s" % b)
    assert not bad, "%d replay failure(s)" % len(bad)
    print("bonanza_replay (%s): PASS" % ", ".join(legs))


if __name__ == "__main__":
    main()
