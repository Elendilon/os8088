# Handoff: kernel size pass 2, live state and the lock

**This file is written to be picked up by a DIFFERENT SESSION mid-flight.** It
says what pass 2 is, where it has got to, what is safe to touch while it runs,
and what an independent session can usefully do in parallel without colliding.

Its companion is `docs/HANDOFF-KERNEL-SIZE.md`, which is pass 1's handoff and
still the authority on **method** and on the mistakes not to repeat. Read that
one for *how*; read this one for *where we are*.

Branch: `claude/kernel-size-optimization-p2-zcuuac`, cut from `elendilon` at
`ac1f74f`. One root commit; unshallow the clone before believing any ancestry
answer (CLAUDE.md, "Working in this fork", rule 1).

---

## 1. THE LOCK — read this before running anything

`tools/martylock.py` is new in this pass and exists because two hazards share
one cure:

1. **One machine, one client.** Every emulator test drives MartyPC's debug
   server on `127.0.0.1:9001`. A second client does not error — it *hangs*, or
   silently drives the first one's machine.
2. **A rebuild invalidates the symbol map.** `tools/os88sym.py` refuses an
   address unless a fresh assembly of `kernel.asm` is byte-identical to
   `build/kernel.bin`, and the About box's build number is the **commit count**
   (SPEC.md §14.2).

   **Which step actually fires it is worth knowing**, because a hook or a
   person will eventually need to commit mid-session. The build number reaches
   the assembler through `build/buildnum.inc`, which is generated — only `make`
   runs `tools/buildnum.py`. So **`git commit` alone touches nothing under
   `build/`**: the old count is still on disk, `os88sym` re-assembles to the
   same bytes, and a running session is undisturbed. **`make` is what fires
   it** — it regenerates the count, rebuilds `kernel.bin`, *and rewrites every
   floppy image, including the one the emulator has mounted*, which is the
   worse half. A commit whose `make` is deferred under the lock is safe.

**So the rule is not "hold the lock to use MartyPC". It is: hold the lock to
use MartyPC, OR to `make`, OR to `git commit`, OR to edit `kernel/*`.**

```sh
python3 tools/martylock.py status                       # who has it
python3 tools/martylock.py run --holder <you> --why build -- make   # safest form
python3 tools/martylock.py acquire --holder <you> --why marty \
        --purpose "..." --ttl 45 --wait 1800            # multi-step session
python3 tools/martylock.py renew   --holder <you> --ttl 30
python3 tools/martylock.py release --holder <you>
```

Exit **75** = "held by someone else, retrying is meaningful". Exit 1 = a real
error. Leases expire, so a dead holder does not wedge the lock for ever; a
lapsed lease can be taken and the theft is logged. `build/martylock.log` is the
audit trail — every acquire, release, steal and break, with a name on it.
**Never `break` a lease that has not expired.**

### The lock is PER-CHECKOUT. It does not reach another container.

`build/.martylock` is a directory on one filesystem, so it serialises the
agents sharing **one** checkout and nothing else. A second session running in
its own container has its own clone, its own `build/`, and its own MartyPC —
**it is a different machine, it cannot see this lock, and it does not need
to.** Do not try to coordinate MartyPC across containers; there is nothing to
coordinate.

What *does* cross the boundary is **git**. Two sessions pushing to
`claude/kernel-size-optimization-p2-zcuuac` will collide in the ordinary way,
and the size figures are the casualty: `kernsize` deltas are measured against a
specific base, so a push that moves the base silently invalidates every
measurement taken against it. **So: a second session works on its own branch
and opens a PR, or agrees a file-level split in writing first.** The workstreams
in §5 are chosen to make that easy — items 3 and 5 touch no kernel source at
all.

Where §5 says an item "needs the lock", that means *if you are running in this
container*. In your own, it does not apply.

It is a `mkdir`-based mutex (atomic on POSIX, no `flock` dependency), verified
against 20 concurrent acquirers: exactly one winner, nineteen clean 75s. The
window between `mkdir` and the metadata write is covered by a 60-second grace
in which a metadata-less lock counts as *held*, not as rubble.

---

## 2. What pass 2 is doing

Pass 1 took twelve kernel files and landed −6,656 bytes. Pass 2 takes the next
twelve named in `docs/HANDOFF-KERNEL-SIZE.md` §2, **plus the long tail** — which
that handoff flags as having produced pass 1's single largest finding set.

Coverage is 18 finder agents: one per named file, four tail-sweep groups
covering the remaining ~20 files, one cross-cutting duplication sweep that owns
no file and looks at all of them at once, and one MartyPC bench-baseline agent.

The shared brief every agent reads is
`/tmp/claude-0/-home-user-os8088/40187755-8575-5715-9ba3-7340ed11d249/scratchpad/pass2/BRIEF.md`
(session-local — if you are a different session, the durable copy of its rules
is this file's §5 plus pass 1's handoff).

### The phases, in order
1. Baseline — **done**: `kernsize`, plus `sysbench`/`gfxbench` per adapter.
   *Deviation from pass 1, decided by the repo owner:* **the baseline soak is
   deliberately NOT run.** It takes ~4 h and was fixed and fully run at the end
   of pass 1. Instead the full soak runs once at the END, and any failing row is
   then re-run against the baseline commit to classify it as pre-existing or
   newly broken.
2. Find — one agent per file, assembled byte counts, cross-file duplicates
   reported from both ends.
3. Consolidate and de-duplicate. Pass 1's de-dup moved the total by 528 bytes
   and found 12% of `.cold` claims double-counted.
4. **Adverse review**, grouped by shared risk rather than by file.
5. **Integration review** — what only appears in combination.
6. Implement in large sequential batches, each gating with `make` +
   `os88test.py fast` + `os88ovlchk.py` + a `stkbalance` diff.
7. Full soak + bench comparison.

Phases 4 and 5 are not optional. In pass 1 they removed about a fifth of the
proposed bytes and found **four real bugs that were not size findings at all**.

---

## 3. The baseline, measured on this tree

```
.text 52,916 · .bss 5,829 · .cold 38,927 · .lowbss 9,096 · .vgabuf 848
.ovl 1,425 · .ovlw 5,263 · .boot2 2,439
KERN_SIZE  114,176 of KERN_BUDGET 129,536 -> 15,360 spare (30 steps)
.text+.bss  58,745 of KERN_CODE_MAX 65,536 ->  6,791 left
rungs: image 58,880 (135 left) · cold 39,424 (497 left)
       low 10,240 (120 left)   · vgabuf 1,024 (176 left)
```

### The bench baseline's machine configs are part of the measurement

The end-of-pass comparison **must use the same three configs**:
`os8088_5150_cga_gla`, `os8088_5150_herc_gla`, `os8088_xt_vga`. Swapping in the
IBM-ROM configs later — if somebody drops a real dump into
`tools/martypc/roms/` — compares two different machines rather than two points
on one.

Two things fell out of taking it that are worth knowing before quoting any of
those numbers. **There is no `os8088_5150_vga` machine in this tree at all**:
the calibration 5150 has no VGA card, so VGA exists only on the XT-class
machines and `os8088_xt_vga` is the only option. And because CGA and Hercules
ran on their GLaBIOS twins, **BIOS-mediated timings — the floppy block, boot
ms — are not period-accurate and must not be quoted as PERFORMANCE.md field
figures.** Everything CPU-bound is unaffected: that code is os8088's own and
the BIOS is not on its path, which is exactly the class a size pass can
regress.

Note these differ from pass 1's closing figures: the tree has moved since
(the Weave waves merged, and the task-stack commit `ac1f74f`). **These are the
numbers pass 2 is measured against**, not the ones in pass 1's handoff.

Two of them are worth flagging to whoever picks this up:

* **`.lowbss` has 120 bytes left in its rung** — the tightest of the four. A
  `.lowbss` saving is therefore unusually likely to actually return a rung.
  The two big claimants are `dskwin.inc` (3,584) and `sched.inc`'s task stacks
  (2,730).
* **The 64KB segment is no longer the binding constraint** — pass 1 took it from
  2,432 bytes free to 7,055, and it is 6,791 now. Justify pass 2 on
  `KERN_BUDGET`, not on the window.

---

## 4. What is safe to touch while pass 2 runs

**Safe, no lock needed:** reading anything; `tools/kernsize.py` (it assembles
into temp directories and never writes `build/kernel.bin`); any `docs/` edit
that you do not commit.

**Needs the lock:** `make`, any target that builds, `git commit`, editing
`kernel/*`, anything that opens MartyPC.

**Do not do at all while pass 2 is mid-implementation:** merge this branch, or
rebase it. The batches gate on each other and a moved base invalidates the
measurements taken so far.

---

## 5. If you are an independent session, here is work that does not collide

Ranked by value, and each is genuinely disjoint from the agent fleet:

1. **A field run on real hardware.** `docs/FIELD-MACHINES.md` says who has the
   iron and what a run costs them. Nothing in this pass can measure a real 8088,
   and pass 1's worst outcome was a predicted cost that shipped unmeasured and
   turned out to be double its prediction. **The Hercules reading in
   `docs/MONO-RECLAIM-PLAN.md` has never been taken and it is the adapter with
   most to gain.**
2. **`tests/int0sweep.py` on the IBM ROM.** Pass 1's worst bug was a divide overflow that hard-locks
   an IBM machine and is merely a wrong clip index on GLaBIOS, and every other
   MartyPC row runs GLaBIOS, so the whole class was invisible.

   **`tools/martypc/roms/` does not exist in a FRESH container** — it is
   gitignored because IBM's ROM cannot be redistributed under this repo's MIT
   licence (CONTRIBUTING.md), so only a dump supplied by hand backs it, and
   because it is never committed, **every new container starts without one
   again.** Supplying it is therefore a per-session act, not a one-off.

   *In pass 2's own session the owner supplied it mid-run*, and it is
   installed and verified: md5 `f453eb2df6daf21ec644d33663d85434`, which is
   exactly what the pinned MartyPC's `romdef_ibm_pcxt.toml` wants for
   `ibm5150_82_v4` chip u33 at 0xFE000. `os8088_5150_cga` and
   `os8088_5150_herc` start on it where they previously failed rc=1, and
   `0xFE001` reads `501476 COPR. IBM` against GLaBIOS's `GLaBIOS [`, with the
   reset vector dated 10/27/82. **Fingerprint, never infer from the config
   name.**

   What pass 2 established about the failure mode, by reading the pinned
   MartyPC's `rom_manager` source rather than inferring it: **a missing IBM ROM
   is a loud immediate startup failure, not a silent substitution.**
   `resolve_requirements` marks the alias "provided" and prints *"has resolved
   the following ROM sets: ibm5150_82_v4"*, then `create_manifest` fails to load
   bytes for it and the process exits rc=1. So pass 1's "silently came up as
   `glabios_pc`" was most likely a *wrapper* retrying another config without
   recording which one finally booted — not a MartyPC behaviour. **The cure is
   the same either way: check what actually loaded, never infer it from the
   config name.** `baseline/romcheck.py` and `romfingerprint.py` in the pass-2
   scratchpad do it three independent ways (the resolved-ROM-set log line, a
   live read of `0xFE001`, and the reset vector at `0xFFFF0`).
3. **A push/pop balance gate for the kernel.** `tools/stkbalance.py` is scoped
   to SHEET and CHART on purpose, because the kernel's ISR tails push and pop
   under different labels. **The kernel therefore has no balance gate at all**,
   and an imbalance introduced in pass 1 went green through `make`, the fast
   tier and stkbalance. Building one that understands ISR tails would be worth
   more than most of the bytes in this pass. It is host-side, so it needs no
   lock and cannot collide.
4. **`docs/LAST-DROP-BYTES.md` upkeep.** It is the live register of `.ovl`-
   eligible bodies and its §7 is the list of merges that look available and are
   not. Every row pass 2 lands or refuses belongs in it. Coordinate before
   editing — say so in the branch — but the file is not otherwise contended.
5. **`tools/os88geom.py`'s `_MIRROR`.** Host tools should read kernel constants
   from there; two independent teams added to it during pass 1 for the same
   reason. Auditing which host tools still hard-code a kernel constant is a
   self-contained job.

---

## 6. The rules that bite hardest, restated

`SS ≠ DS`, so `[bp+disp]` addresses SS. **Sections are different segments** —
`.text` is `KERNEL_SEG`, `.cold` is `COLD_SEG`, `.ovl`/`.ovlw` is the boot
overlay released at `spl_finish`, `.lowbss` is `LOW_SEG` reached through SS —
so a near call across a section boundary assembles cleanly and runs wrong, and
"merge these two identical routines" is only free when both ends are in the
same section. **A NASM local belongs to the last non-local label, so moving code
re-parents every local inside it.** `.bss` cannot hold a non-zero resting value.
`[vid_w]`/`[vid_h]`/`[vid_stride]`, never `SCREEN_W`/`SCREEN_H`. Text is
`font_run`, and `tests/textsites.txt` only goes down. 8086 only: no `pusha`,
no `push imm`, no `movzx`, no 32-bit registers.

**`.ovl` has no partial credit.** A body reached from `ui_task` on any pass,
from an ISR, from a published `OSAPI_*` slot, or through a pointer in a table
that outlives boot is disqualified completely — it is a freed heap claim being
executed. `tests/ovlrefs.txt` is where the "what guarantees this runs before
`spl_finish`?" answer is registered and `tools/os88ovlchk.py` enforces it.

**Think in bytes, not rungs.** The amortised price of a byte is a byte. Quote
`kernsize`'s SUM and its ACCRUED line, never its step count.
