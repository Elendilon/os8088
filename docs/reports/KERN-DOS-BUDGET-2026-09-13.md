# What `kern_dos` would cost, and what the handoff would take

**A measurement, not a description.** Taken 2026-09-13 on a four-core cloud
container, `nasm` 2.16.01, MartyPC at its pinned commit, at
`5410420` on `claude/dos-exec-investigation`. The kernel it describes is
`KERN_SIZE` 113,152 of `KERN_BUDGET` 129,536 (`.text` 49,832, `.bss` 6,006,
`.cold` 40,985), and `kern_small` beside it at 76,800. It is true of that
commit and of no other tree; a later measurement is a new file.

This is **wave 1 of docs/plans/KERN-DOS-PLAN.md**, which says in as many
words that every byte figure in its §1 past the first table is an estimate
and that this comes before any code.

## The answer in three lines

1. **The two windowed arms are 449 KB and 481 KB, and the disk cache between
   them is exactly 32 KB** — both read off one boot, so the difference is
   measured rather than two readings subtracted.
2. **`kern_dos`'s floor is 35.5 KB against a 38.5 KB budget**, where the plan
   estimated ~30.5 KB. That leaves **3.0 KB** for the shim *and* the cache,
   not the ~8 KB plus a 16 KB cache KERN-DOS-PLAN §6 hoped for — and KERN-DOS-PLAN §6.1's levers stop
   being an ordering suggestion and become the thing that makes the target
   reachable. Two of them are priced below and are worth **4.1 KB** together.
3. **The hibernate round trip is 43.4 guest seconds**, three runs inside
   1.5% of each other: 26.2 s to write the image and 17.1 s to read it back.
   KERN-DOS-PLAN §2.1 weighed this as *"a few seconds"* against *"4–5 seconds and then a few
   more"*. It is neither.

---

## 1. The arena: what each arm is worth

Read off one boot of `os8088_5150_herc_sb_gla` — a 4.77 MHz 5150 with a
Sound Blaster, which is the machine KERN-DOS-PLAN §1.1's table was taken on — launching
`DOSSND.COM` once per arm and reading `[dos_akb]` inside the bracket.

| | |
|---|---:|
| the machine | 655,360 |
| below the heap (IVT, BDA, kernel, its modules and its low area) | 113,664 |
| the heap | **541,696 = 529 KB** |

| arm | `[dos_akb]` | |
|---|---:|---|
| 0 `DOS_MEM_KEEP` | **449 KB** | today's default |
| 1 `DOS_MEM_DUMP` | **481 KB** | §18.95's `dirw` cache given back |
| 2 `DOS_MEM_WHOLE` | — | greyed; section 3 below is its ceiling |

**The cache is 32 KB, measured**, and it is measured the right way round:
both figures come from the same boot with the same driver set and the same
region in the same place, so the 32 is a difference and not two independent
readings that happen to differ by that much. KERN-DOS-PLAN §1.1's table predicted 449 and
~481; both stand.

What is left of the 529 KB heap at arm 0 is 529 − 449 − 32 = **48 KB**: the
DOS package's own region (its image is 31,517 and its bss 11,273, so 42 KB
rounded up), the packet driver's 2 KB of buffers (§96.23.7) and the boot's
own claims.

---

## 2. `kern_dos`'s floor, re-derived

KERN-DOS-PLAN §6's table quotes docs/plans/KERN-SMALL-CUT-PLAN.md §1.2. Those figures are a
year of commits old and they are **code only**. Re-derived from today's tree
with `tools/kernsize.py --modules --build build/smallk -DKERN_SMALL`, which
brackets each include with markers in a temporary copy and refuses to report
unless the two binaries are byte-identical:

| | code | `.bss` | `.lowbss` | total | the plan quoted |
|---|---:|---:|---:|---:|---:|
| `disk.inc` | 6,624 | 582 | — | **7,206** | 6,816 |
| `diskw.inc` | 5,311 | 162 | — | **5,473** | 5,077 |
| `dskwin.inc` | — | — | 2,336 | **2,336** | 2,336 |
| `mouse.inc` | 3,419 | 151 | 128 | **3,698** | 3,538 |
| | | | | **18,713** | 17,767 |

### 2.1 The DOS core is 17,667 bytes and not ~12,000

KERN-DOS-PLAN §6's largest row is an estimate with a reason attached — *"the box's image is
30,731 and most of it is window"*. It is not most of it.

Measured by **symbol span** over `DOS.O88`'s own map, with local labels rolled
into the proc above them and nasm's anonymous `..@N` labels attributed to the
last named span (docs/plans/DISK-CPU-PLAN.md §1's second trap, one instrument
along), 31,405 of the image's 31,517 bytes attribute — the missing 112 being
the package header, which `os88pkg` reports separately:

| | image | bss | |
|---|---:|---:|---|
| **core** | 14,636 | 3,031 | INT 21h, the handle layer, PSP/MCB, the loader, FCBs, `dosh.inc`'s built-ins |
| **window** | 11,960 | 1,135 | the pages, the console, `os88ui.inc`, `os88line.inc`, the shortcut writer |
| **drop** | 4,608 | 115 | the packet driver and §96.26's cable translation, which KERN-DOS-PLAN §10 says do not come |
| unclassified | 201 | 129 | 0.6% and 2.9%, listed below |

The rule is by symbol prefix and the residual is printed rather than
absorbed, so what the split assumed is visible: the largest unclassified item
is `dos_cw_back` at 25 bytes, and none of the rest reaches 30.

The bss figure is `DOS_BSS_SIZE` = 4,410 and not the package's 11,273: the
other **6,863 is `CON_BSS`**, the windowed console's, which KERN-DOS-PLAN §6.1 lever 5
leaves behind entirely.

**So the core is 14,636 + 3,031 = 17,667** where KERN-DOS-PLAN §6 carried ~12,000 plus
~1,500 for the PSP, environment and MCB chain — and those 1,500 are already
inside the 17,667, so the row is **+4,167** over its estimate.

### 2.2 The floor, and what is left

```
  18,713   the kernel side (section 2 above)
 +17,667   the DOS core   (section 2.1)
  ======
  36,380 = 35.5 KB

  39,424 = 38.5 KB   the budget: 640 KB - 1,536 (IVT + BDA) - 600 KB
  ------
   3,044 =  3.0 KB   for the shim AND any cache
```

KERN-DOS-PLAN §6 reached ~31 KB and left ~8 KB for the shim, with KERN-DOS-PLAN §6.2 spending 16 KB more
on a read-ahead and taking the target to ~587 KB. On the measured floor there
is no such room, and **KERN-DOS-PLAN §6.1's levers are not an ordering suggestion any
more** — they are what makes 600 KB reachable at all.

### 2.3 Two of the five levers, priced

**Lever 1 — drop the file-window handle layer.** §96.11's 8 KB window is a
heap CLAIM (`dos_wseg` is a segment in bss, not the buffer), so it is not in
the 36,380 above at all and dropping it is worth its 8 KB against the *budget*
rather than against the floor. The code half is `dos_fh_*`, **2,186 bytes over
19 procs** — of which the ten that ARE the window (`fill`, `flush`, `core`,
`enter`, `setup`, `split`, `rdloop`, `wrloop`, `wiloop`, `shrink`) are
**1,803** and the nine that are the handle TABLE stay, DOS needing handles
whatever is under them. KERN-DOS-PLAN §6.1 says *"~−3 KB of code"*; it is 1.8.

**Lever 2 — drop the cursor half of `mouse.inc`.** Spanned the same way over
`kern_small`'s map, 3,228 of that file's 3,419 `.text` bytes attribute to 74
procs:

| | bytes | share |
|---|---:|---:|
| `cur_*` — the pointer | **1,440** | 45% |
| `kbm_*` / `kbd_*` — the keyboard | **781** | 24% |
| the mouse itself | 1,007 | 31% |

KERN-DOS-PLAN §6.1 estimates −1.5 KB for the cursor and the estimate is right: 1,440. **The
keyboard is a second 781 nobody had counted** — `kern_dos` has no event ring
to feed and the ROM's own `int 09h`/`int 16h` serve INT 21h's character
input, so that half need not come either. `mouse.inc`'s carried share is
**~1,007 + 279 of bss and lowbss**, against 3,698 whole.

Taking both levers: **36,380 − 1,803 − 2,412 = 32,165 = 31.4 KB**, leaving
**7.1 KB** for the shim — which is within a few hundred bytes of the number
KERN-DOS-PLAN §6 wrote down, reached by a different route.

Levers 3, 4 and 5 (`diskw.inc`'s long-operation machinery, one volume class,
no console) are **not priced here**. Each is a subset of a file rather than a
family of symbols, so pricing them means classifying 11,935 bytes of
`disk.inc` and `diskw.inc` proc by proc — which is W3's work and not a
measurement that can be taken without it.

---

## 3. What the handoff costs: 43.4 guest seconds

KERN-DOS-PLAN §2 rests on §87.5's resume stub, and its §2.1 asks what including the restore
costs, weighing *"waiting 4–5 seconds to get to desktop again, and THEN a few
more seconds for the restore"* against *"waiting a few seconds for the
restore"*.

Measured on `os8088_xt_hdd` — a 4.77 MHz XT with XT-IDE's option ROM, which is
rung 0 (§52.1), the transport the field machine has and the only one the
resume stub speaks — by bracketing `tests/hibernate.py`'s own verbs with
MartyPC's cycle counter, which costs the guest nothing. Three runs:

| | run 1 | run 2 | run 3 |
|---|---:|---:|---:|
| **WRITE** — [Hibernate] clicked → the ROM's text screen | 26.23 | 26.62 | 26.17 |
| restart → the desktop asking the question | 33.32 | 33.49 | 33.30 |
| **READ** — Resume clicked → the old desktop back | 17.13 | 16.87 | 17.12 |
| **arm 3's own half** (write + read) | **43.37** | **43.48** | **43.28** |
| the whole round trip | 76.69 | 76.97 | 76.59 |

Guest seconds at 4.772727 MHz. The spread is under 1.5%, which is what a
cycle counter on a deterministic guest should give.

**Read the three rows separately, because arm 3 pays two of them and not the
third.** KERN-DOS-PLAN §7's handoff stages the stub and jumps; it does not reboot, so the
33 s middle row — a machine reset, the ROM's POST and memory count, and a
whole os8088 boot — is *not* arm 3's. The floppy arm (KERN-DOS-PLAN §9) is the case that
does pay it, and it pays it with no restore at the end.

So on a machine with a hard disk, arm 3 costs **26 seconds before the DOS
program starts and 17 after it exits**, on top of whatever the program itself
does. That is the number KERN-DOS-PLAN §2.1 wanted and it is an order of magnitude over the
estimate it was weighed against.

Three caveats, stated rather than left to be discovered:

- **It is one machine's figure.** MartyPC agrees with the field 5150 to 0–4%
  on 45 of 47 `gfxbench` rows, but those are CPU and VRAM rows; the XT-IDE
  transport's timing has never been checked against iron here. The right
  place to settle it is docs/FIELD-MACHINES.md's `pc5150`, which has an
  ST-225 on a real ST11M.
- **It is the WHOLE operation and not just the transfer.** The write includes
  `HIBER.DRV` being loaded, the image composed, a 640 KB file allocated on
  FAT16 and the machine torn down; the read includes the extent walk and the
  restore. A sector count would be a smaller and less useful number.
- **It scales with the machine's RAM**, the image being all of conventional
  memory. A 640 KB machine is the worst case and also the one arm 3 is for.

---

## 4. What this changes in the plan

- **KERN-DOS-PLAN §1.1's arms 1 and 2 are confirmed** and its 32 KB cache row is now
  measured.
- **KERN-DOS-PLAN §6's table is +5,100 bytes** against today's tree, of which 4,167 is the
  DOS core row alone, and **KERN-DOS-PLAN §6.1's levers become required rather than
  recommended**. Two of the five are priced here and are worth 4.1 KB.
- **KERN-DOS-PLAN §6.2's 16 KB read-ahead cannot be funded out of slack.** With levers 1
  and 2 taken there is 7.1 KB before the shim is written; the purgeable cache
  KERN-DOS-PLAN §6.2 proposes is therefore the only shape that works, and it has to be
  purgeable in the strong sense — claimed only when the program has not
  taken the memory, not merely given back on demand.
- **section 2.1's cost question is answered and the answer is 43 seconds**, which is
  a product decision rather than a technical one: whether a DOS program worth
  600 KB is worth three quarters of a minute of waiting around it.
- **W3 gains a second question.** It was *"how big is the shim?"*; it is now
  *"how big is the shim, and can levers 3–5 find the rest?"* — because the
  budget after the two priced levers is 7.1 KB and the shim was already the
  plan's largest unknown.

## 5. How to re-derive all of it

```
python3 tools/kernsize.py --modules --build build/smallk -DKERN_SMALL
python3 tools/os88doscost.py [--procs]      # 2 and 2.1
python3 tools/os88doscost.py --mouse        # 2.3 lever 2
```

`tools/os88doscost.py` is **new with this report and ships**, for
`tools/kernsize.py`'s own stated reason: a number nobody can produce in one
command is a number that stops being produced, and W2 performs this split for
real and will want to check its arithmetic against the same reading. Its
header carries the two traps that each cost a wrong number here — a local
label belongs to the proc above it (nasm's anonymous `..@N` ones included),
and sections must be spanned separately, a flat sort having read
`kernel/mouse.inc` at 1,629 bytes for a file the module table prices at 3,419.

The arena figures and the hibernate timings are emulator runs driven with
`tools/os88ui.py` and `tests/hibernate.py`'s own verbs. Nothing here perturbs
what it measures: `kernsize` assembles into a temporary copy and refuses to
report unless the result is byte-identical to the build, `os88doscost`
assembles a copy of `dos.asm` with a `[map all]` line appended, and MartyPC's
cycle counter costs the guest nothing.
