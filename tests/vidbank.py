#!/usr/bin/env python3
"""VIDEO.O88's XMS BANK: a streamed .V88 BIGGER than the pool, played with a
FIFO of chunks in XMS ahead of the ring - docs/plans/VIDEO-XMS-PLAN.md 4,
SPEC.md 98.3.18.2.

    make && python3 tests/vidbank.py

WHY QEMU: docs/TESTING.md's closed list, entry 1 - XMS is a 286-and-up store
and every MartyPC machine is an 8088. `-m 2` gives the machine 1 MB above the
first, and the clip is ~1.35 MB, so the whole-file hold (98.3.18) cannot be
taken and the player must bank instead. Nothing here is timed; every wait is
on guest state.

The clip is LIN80, 640 x 200, so the bracket writes it straight to A000 at
the centred origin and the picture is read back off the card (plane 0: a
MONO1 byte goes to all four, SPEC.md 98.1.2) at the gate's holds
(`vp_stopat`, tests/vidplay.py's), against the reference decode.

LEG play (B: the clip's disk throughout):
  1. the file opens with a BANK - [vp_xbank] 1, [vp_xbn] slots, nothing of
     the file held ([vp_xhave] 0);
  2. Play, held before frame 20: with the hook stopped the ring fills and
     then THE BANK DOES, to every slot it has - the reader's idle time;
  3. held again before each key frame: the picture is the decode's, so the
     chunks came down out of the bank in order and whole;
  4. the play runs to the last frame with no error.
LEG swap (the instrument is tests/vidxms.py's, a disk swap):
  5. Play again, held before frame 20 until the bank is full - then B: is
     changed to a BLANK floppy under the running player;
  6. the hold moves to the furthest key frame whose data lies inside what the
     ring and the bank had between them, and THAT FRAME IS RIGHT - every byte
     after the ring's came out of XMS, there being no disk to read;
  7. released, the play must NOT reach the end: what neither held is the
     blank disk's. That is what says the swap bites.

VERIFIED TO FAIL: with `call vp_bstep` taken out of the reader's loop the
bank stays empty (step 2), and with vp_bfill's head left unmoved step 3's
picture differs.
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)
import os88qemu                                             # noqa: E402
import os88build                                            # noqa: E402
import os88geom as geom                                     # noqa: E402
import os88ui                                               # noqa: E402
import os88vid as vid                                       # noqa: E402
import xmcheck                                              # noqa: E402
from cycweb import pkg_syms                                 # noqa: E402
from vidxms import Q, u16, u32                              # noqa: E402
from pxswin import qpoke                                     # noqa: E402

NF, FPS, WB, H = 300, 30.0, 80, 200
HOLD0 = 20
ASK_KB, PRE_KB = 4096, 256          # the header's bank and prefill
VOK_LOWMEM = 7
VOK_BUF = 10                    # vosd.inc: the box says the prefill
CHUNK = 32768


def clip(tmp):
    """300 frames of 640 x 200 at ~4.5 KB of change each: ~1.35 MB, which
    is more than `-m 2` has above 1 MB and less than a 1.44 MB floppy"""
    import random
    rnd = random.Random(5088)
    cv = bytearray(WB * H)
    paths = []
    for f in range(NF):
        for _ in range(490):
            a = rnd.randrange(WB * H - 8)
            cv[a:a + 8] = bytes(rnd.getrandbits(8) for _ in range(8))
        p = os.path.join(tmp, "f%03d.pbm" % f)
        vid._write_pbm(p, WB, H, bytes(cv))
        paths.append(p)
    out = os.path.join(tmp, "CLIP.V88")
    vid.encode_frames(paths, out, FPS, None, "lin80", "vidbank clip")
    # THE FILE'S ASK (98.3.18.3), as --bank 4096 --prefill would write it:
    # a bank bigger than this machine's, and a prefill of PRE_KB
    d = bytearray(open(out, "rb").read())
    struct.pack_into("<HH", d, vid.H_XBANK, ASK_KB, PRE_KB)
    open(out, "wb").write(d)
    vid.verify_v88(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mem", type=int, default=2,
                    help="QEMU -m (MB): the pool is what is above the first")
    a = ap.parse_args()
    os.chdir(ROOT)
    syms, _ = pkg_syms("apps/video/video.asm", ("apps/",))
    pkg = os88build.at("build/video.o88")
    sysimg0 = os88build.at("build/os8088.img")
    for p in (pkg, sysimg0):
        if not os.path.exists(p):
            sys.exit("vidbank: no %s - run `make`" % p)
    bad = []
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "build")) as tmp:
        v88 = clip(tmp)
        size = os.path.getsize(v88)
        rd88 = vid.Reader(v88)
        tg = vid.Geom(vid.LAY_LIN80, WB, 480)
        ty0 = (480 - H) // 2 // tg.banks * tg.banks
        row0 = tg.base[ty0]
        print("   clip: %d frames, %d bytes (%d KB), %d keys"
              % (rd88.frames, size, size // 1024, len(rd88.keys)))
        disk = os.path.join(tmp, "vidbank.img")
        blank = os.path.join(tmp, "blank.img")
        sysimg = os.path.join(tmp, "sys.img")
        shutil.copy(sysimg0, sysimg)
        for out, files in ((disk, [v88, pkg]), (blank, [])):
            subprocess.run([sys.executable, "tools/os88disk.py", "-o", out,
                            "--size", "1440"] + files, check=True,
                           capture_output=True)
        q = Q(tmp, sysimg, disk, a.mem)
        for _ in range(150):
            if os.path.exists(q.sock):
                break
            time.sleep(0.2)
        xmcheck.wait_desktop(q.sock, "vidbank")
        S = xmcheck.sym
        ui = os88ui.UI(q, mouse=object(), sym=S, verbose=False)

        def wait(cond, what, secs):
            if not os88qemu.acted(q, cond, secs=secs, what=what, poll=0.05):
                raise SystemExit("vidbank: timed out waiting for %s (%s)"
                                 % (what, state()))

        x, y = geom.drive_pt(q, "B", S)
        xmcheck.dblclick(q.sock, x, y)
        box = {}

        def diskwin():
            for w in ui.windows():
                if w.visible and ui.fs_of(w) == (1, 0, 1):
                    box["w"] = w
                    return True
            return False
        if not os88qemu.acted(q, diskwin, secs=30, what="drive B",
                              poll=0.05):
            sys.exit("vidbank: drive B's window did not open")
        os88qemu.pace(q, 1)
        w = box["w"]
        i, _ = ui.entry("CLIP.V88", w)
        before = set(o.i for o in ui.windows())
        xmcheck.dblclick(q.sock, *ui.row_xy(w, i - ui.scroll(w)))

        def player():
            for o in ui.windows():
                if o.i not in before and o.visible:
                    box["p"] = o
                    return True
            return False
        if not os88qemu.acted(q, player, secs=30, what="the player",
                              poll=0.05):
            sys.exit("vidbank: the Video Player's window did not open")
        rec = q.read(S("wm_wins") + box["p"].i * geom.WIN_SIZE, geom.WIN_SIZE)
        base = u16(rec, geom.W_SEG) << 4

        def rb(n):
            return q.read(base + syms[n], 1)[0]

        def rw(n):
            return u16(q.read(base + syms[n], 2))

        def rd(n):
            return u32(q.read(base + syms[n], 4))

        def state():
            return ("done=%d err=%d ready=%d played=%d lc=%d pc=%d k=%d "
                    "bank=%d xon=%d bn=%d cnt=%d hs=%d beof=%d held=%d"
                    % (rw("vp_done"), rb("vp_err"), rb("vp_ready"),
                       rb("vp_played"), rw("vp_lc"), rw("vp_pc"),
                       rw("vp_k"), rb("vp_xbank"), rb("vp_xon"),
                       rw("vp_xbn"), rw("vp_xcnt"), rw("vp_xhs"),
                       rb("vp_xbeof"), rb("vp_held")))

        def poke(n, v):
            qpoke(q, [(base + syms[n], struct.pack("<H", v & 0xFFFF))])

        if not os88qemu.acted(q, lambda: rb("vp_loaded") == 1, secs=30,
                              what="the clip's header", poll=0.05):
            sys.exit("vidbank: the clip did not open")
        if rb("vp_ok") != 1:
            sys.exit("vidbank: the player will not play the clip here")

        # --- 1: a bank, not a hold
        print("   opened: %s xhave=%d" % (state(), rd("vp_xhave")))
        if rb("vp_xbank") != 1 or rb("vp_xon") != 1:
            sys.exit("vidbank: no bank was taken (%s)" % state())
        bn = rw("vp_xbn")
        if bn < 4 or rd("vp_xhave"):
            bad.append("the bank is %d slots, %d bytes held"
                       % (bn, rd("vp_xhave")))
        print("   the bank: %d slots, %d KB" % (bn, bn * 32))

        def screen():
            raw = q.read(0xA0000 + row0, WB * H)
            return b"".join(raw[tg.base[ty0 + yy] - row0:
                                tg.base[ty0 + yy] - row0 + WB]
                            for yy in range(H))

        def hold_at(n, what, secs=60):
            wait(lambda: rb("vp_held") == 1 and rw("vp_done") == n,
                 "the hold before frame %d (%s)" % (n, what), secs)
            wait(lambda: rb("vo_on") == 0, "the box to come down", 30)

        def check(n):
            got = screen()
            want = vid.decode_at(rd88, n - 1)
            diff = sum(1 for j in range(len(got)) if got[j] != want[j])
            print("   hold before frame %3d: %d bytes of %d differ  (%s)"
                  % (n, diff, len(got), state()))
            if diff:
                bad.append("the screen before frame %d differs in %d bytes"
                           % (n, diff))

        def release(nxt):
            qpoke(q, [(base + syms["vp_stopat"], struct.pack("<H", nxt)),
                      (base + syms["vp_held"], b"\0")])

        # --- 2: THE PREFILL fills the bank before frame 0 (98.3.18.3): the
        # file asks nothing, so 10 s at its mean - more than the bank holds
        keys = [k[0] for k in rd88.keys if HOLD0 < k[0] < NF]
        poke("vp_stopat", HOLD0)
        q.hmp("sendkey p")
        wait(lambda: rb("vp_ready") == 1, "the play to start", 60)
        q.hmp("stop")
        pfn, cnt0, done0 = rw("vp_pfn"), rw("vp_xcnt"), rw("vp_done")
        ask = (rw("vp_hxb"), rw("vp_hxp"))
        toast = rb("vo_toast")
        q.hmp("cont")
        print("   the first frame due: the file asks %d KB, %d first; the "
              "prefill %d slots, the bank has %d, %d drawn, toast %d"
              % (ask + (pfn, cnt0, done0, toast)))
        if ask != (ASK_KB, PRE_KB) or pfn != PRE_KB // 32 or cnt0 < pfn:
            bad.append("the file's ask %r: the prefill asked %d slots of %d "
                       "and the bank had %d at the first frame"
                       % (ask, pfn, bn, cnt0))
        if toast != VOK_LOWMEM:
            bad.append("a bank of %d KB under the file's %d did not say Low "
                       "memory (toast %d)" % (bn * 32, ASK_KB, toast))
        hold_at(HOLD0, "the first")
        check(HOLD0)
        # --- 3: every key frame right
        for n in keys:
            release(n)
            hold_at(n, "a key frame")
            check(n)
        # --- 4: to the end
        release(0xFFFF)
        wait(lambda: rb("vp_ready") == 0 and rb("vp_played") == 1,
             "the first play to end", 120)
        print("   first play: %s" % state())
        if rw("vp_done") != NF or rb("vp_err"):
            bad.append("the play through the bank drew %d of %d (error %d)"
                       % (rw("vp_done"), NF, rb("vp_err")))

        def prefilled(what):
            """Play with the gate's hold on the prefill's end: the bank
            full, the box saying so, and no frame drawn yet"""
            qpoke(q, [(base + syms["vp_played"], b"\0"),
                      (base + syms["vp_pfwait"], b"\1"),
                      (base + syms["vp_hxp"], b"\xff\xff"),
                      (base + syms["vp_stopat"], struct.pack("<H", HOLD0))])
            q.hmp("sendkey p")
            wait(lambda: rb("vo_kind") == VOK_BUF and rw("vp_xcnt") == bn,
                 what, 120)
            q.hmp("stop")
            txt = q.read(base + syms["vo_text"], 20).split(b"\0")[0]
            st = (txt, rb("vo_on"), rb("vp_ready"), rw("vp_done"))
            q.hmp("cont")
            print("   %s: the box says %r (on %d), ready %d, %d drawn"
                  % (what, txt.decode("ascii", "replace"), st[1], st[2],
                     st[3]))
            if st != (b"Buffering 100%", 1, 0, 0):
                bad.append("the prefill's box was %r on %d, ready %d, %d "
                           "drawn" % st)

        # --- 5: Esc while it fills cancels the play, nothing drawn
        prefilled("the prefill held")
        q.hmp("sendkey esc")
        wait(lambda: rb("vp_played") == 1 and rb("vp_sess") == 0,
             "Esc to cancel", 30)
        print("   Esc: %s" % state())
        if rw("vp_done") != 0 or rb("vp_err"):
            bad.append("Esc in the prefill drew %d (error %d)"
                       % (rw("vp_done"), rb("vp_err")))

        # --- 6: the prefill whole, B: blank, and Space plays from the bank
        prefilled("the prefill held again")
        q.hmp("stop")
        lc, cnt = rw("vp_lc"), rw("vp_xcnt")
        q.hmp("change floppy1 %s raw" % blank)
        q.hmp("cont")
        # the reader started at the cluster under frame 0's super-packet:
        # chunk c is file bytes from there, so what ring and bank hold ends
        # at least at (lc + cnt) chunks past the first super-packet less a
        # cluster
        first = min(k[3] for k in rd88.keys if k[3])
        lo = first - 4096
        reach = lo + (lc + cnt) * CHUNK
        ring = lo + lc * CHUNK
        fits = [k for k in rd88.keys
                if k[3] and HOLD0 < k[0] and k[3] + k[4] * 512 <= reach]
        print("   swapped at lc=%d cnt=%d: the ring reaches %d, ring and "
              "bank %d; key frames inside: %s"
              % (lc, cnt, ring, reach, [k[0] for k in fits]))
        if not fits or fits[-1][3] <= ring:
            bad.append("no key frame lies past the ring and inside the bank "
                       "- the swap leg proves nothing")
        else:
            n = fits[-1][0]
            qpoke(q, [(base + syms["vp_stopat"], struct.pack("<H", n))])
            q.hmp("sendkey spc")
            wait(lambda: rb("vp_ready") == 1, "Space to start the play", 30)
            hold_at(n, "past the swap", 120)
            check(n)
            # --- 7: what neither held is the blank disk's
            release(0xFFFF)
            ok = os88qemu.acted(q, lambda: rb("vp_ready") == 0, secs=60,
                                what="the play to stop", poll=0.05)
            print("   after the bank: %s" % state())
            if ok and rw("vp_done") == NF and not rb("vp_err"):
                bad.append("with B: blank the play STILL reached the end - "
                           "the swap does not bite")
            if not ok:
                q.hmp("sendkey esc")
        q.close()
    if bad:
        print("\nvidbank: FAIL")
        for b in bad:
            print("  - " + b)
        return 1
    print("\nvidbank: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
