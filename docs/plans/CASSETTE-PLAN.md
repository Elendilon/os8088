# The IBM 5150 cassette port — saving files to tape, and reading them back

> **STATUS: PROPOSED. NOTHING HERE IS BUILT.** Not a line of it exists in the
> tree: no `apps/tape/`, no `TAPE.O88`, no API cell, no test row, no SPEC
> section. Everything below is a design, and §16 is the list of decisions that
> are the user's rather than this document's.
>
> **The section number is 88.** Verified this session:
> `grep -oE '^## [0-9]+\.' SPEC.md | tail -15` shows 73 through 87 taken and
> nothing above; §82 is `CHART`.
>
> **Two things must be settled before a wave is started**, and they are §16's
> first two rows. The design writes to **PIT channel 0**, which SPEC.md §34.1
> forbids in as many words *and carries a recorded refusal about*
> (SPEC.md:44076-44098) — so §5.1's kernel cell is an amendment to a binding
> rule, not a nine-byte package edit. And **no instrument in this project can
> exercise a cassette read at all**, so the central claim of §0.3 goes to the
> field or goes unverified — and neither registered 5150 in
> docs/FIELD-MACHINES.md mentions a deck, a cable or the port.

Design angle, in one sentence: **the tape is hostile input, the deck is
unreliable, the BIOS cannot report a write error, there is no seek, and the
machine is completely stopped for nine seconds at a time — everything below
follows from those five facts, and the UI's whole job is to make the last one
legible rather than to pretend it away.**

---

## 0. The measurement that makes this a plan

### 0.1 `int 15h AH=02` cannot succeed on a running os8088, and nobody would find that from a screenshot

`READ_HALF_BIT` latches **PIT channel 0** and discriminates a leader half-bit
against `0378h` = 888 and a full data bit against `06F0h` = 1776
(PCBIOS.ASM:5103, :5239-5240, :5288-5299). Those constants only make sense at
**mode 3's two readable counts per PIT clock**: a 0-bit is 496.15 µs = 592 PIT
clocks = **1,184 counter units**, a 1-bit is 992.30 µs = 1,184 clocks =
**2,368 units**, and 1,776 is the midpoint.

`kernel/sched.inc:352` puts channel 0 in **mode 2** and says why in its own
comment, verified verbatim this session:

> *"the counter now decrements by 1 per input clock — **the BIOS default mode 3
> steps by 2** and wraps twice per period, useless for elapsed reads
> (SPEC.md 8.1)"*

`sch_fast_on` (`kernel/sched.inc:485`) and `sch_fast_off` (`:505`) both re-emit
`0x34`, so **the machine is in mode 2 for the life of the session**. Under
mode 2 every reading halves: a leader half-bit reads 592 against a threshold
of 888, `jnc` restarts the search, and after `DX = 16250` transitions
(PCBIOS.ASM:5090) the call returns **`AH = 04`, "no data leader"** — *the same
answer as an empty deck, a stopped deck and an unplugged cable.*

GLaBIOS agrees independently and from a clean-room implementation: its
thresholds are `(BEEP_1K7+BEEP_2K)/2` = **888** for the leader half-bit
(GLABIOS.ASM:11725) and `BEEP_1K7+BEEP_2K` = **1776** for the full data bit
(:6020), the same pair, and its own source comment at :6017 says *"raw timer
counter readings are doubled, so must be adjusted by 2x"*.

**This is a precondition, not an improvement.** It is also the one load-bearing
claim in this document derived from reading a listing rather than from a
measurement, because no emulator here can run the path (§10.4). §13.1 item 1 is
the field A/B that confirms it.

### 0.2 …and there is a SECOND ch0 dependency, on the WRITE path, in GLaBIOS only

`CAS_MOTOR_WAIT` (GLABIOS.ASM:11386-11402) is reached for **AH=02 and AH=03
alike** — `JPE CAS_MOTOR_WAIT` at :11327, then `JZ CAS_WRITE / JMP CAS_READ`
at :11401-11402 — and its first act is `MOV AX, 500 / CALL IO_DELAY_MS`.
`IO_DELAY_MS` is **PIT-delta based** and its constant is
`MOV BX, 1193 * 2` (GLABIOS.ASM:5893), under a header comment that states the
assumption outright (:5880-5881):

> *"Note: Mode 3 (Square Wave) decrements the readable counter by 2, so the
> effective frequency of the counter is actually 2,386,364 Hz."*

Under os8088's mode 2 the counter advances 1,193,182 units a second, so the
500 ms wait accumulates its 1,193,000 units in **999.85 ms**. **Every GLaBIOS
record — read or write — spends an extra ~500 ms of spin-up that nothing
asked for.**

IBM's spin-up is a different mechanism and is immune: `BEGIN_OP`
(PCBIOS.ASM:5489-5500) is a pure CPU loop, `MOV BL,42H` × `MOV CX,700H` ×
`LOOP`, = 66 × 1792 × 17 clocks = 2,010,624 clocks = **421.3 ms at
4.772728 MHz**, whatever the PIT is doing.

So the bracket goes on **both** directions. On a read it is correctness; on a
GLaBIOS write it is 500 ms a record; on an IBM write it is a no-op that costs
two `out` triples.

### 0.3 The fixed cost of one record — three numbers, not one

Five patterns measured under MartyPC on a GLaBIOS `8P` ROM, with the machine
in os8088's **mode 2** (which is what the residual identifies it as):

| CX | blocks | measured | tape bits alone | residual |
|---:|---:|---:|---:|---:|
| 256 × `00` | 1 | 4.117 s | 1.024 s | 3.09 |
| 1024 × `00` | 4 | 7.284 s | 4.10 s | 3.19 |
| 1024 × `FF` | 4 | 11.268 s | 8.20 s | 3.07 |
| 1024 random | 4 | 9.217 s | 6.14 s | 3.07 |
| 4096 mostly-`00` | 16 | 19.735 s | 16.6 s | 3.09 |

**The residual is a constant ~3.07 s and it closes to the byte**, which is what
identifies it. Its parts, on GLaBIOS:

```
   0.50000 s   motor spin-up, IO_DELAY_MS(500)      GLABIOS.ASM:11388
 + 0.50000 s   ...AGAIN, because ch0 is in mode 2   GLABIOS.ASM:5893 (0.2)
 + 0.00050 s   the leading zero START bit           GLABIOS.ASM:11448
 + 2.03223 s   2048 leader one-bits at 992.30 us    GLABIOS.ASM:11441-11446
 + 0.00050 s   the sync bit (0, 496.15 us)          GLABIOS.ASM:11466
 + 0.00546 s   the sync byte 16h, 3 ones 5 zeros    GLABIOS.ASM:11471
 + 0.03175 s   32 trailer one-bits                  (after the last block)
 = 3.0704 s
```

**So the 2.491 s "ROM arithmetic" that an earlier draft discarded was right all
along — for the IBM ROM**, which has no start bit (`WRITE_BLOCK` goes straight
from `CALL BEGIN_OP` at PCBIOS.ASM:5324 to `MOV CX,0800H` and the leader at
:5327-5331) and whose spin-up is the PIT-independent 421.3 ms:
0.4213 + 2.0699 = **2.4912 s**.

| ROM | ch0 mode during the call | fixed cost per record |
|---|---|---:|
| IBM 5150 (04/24/81, 10/19/81, 10/27/82) | irrelevant — `BEGIN_OP` is a CPU loop | **2.49 s** |
| GLaBIOS `8P`, §5.1's bracket taken | mode 3 | **2.57 s** |
| GLaBIOS `8P`, no bracket (today) | mode 2 | **3.07 s**, measured 3.1 |

> **Every user-facing figure in this document is cut at `TP_FIX = 2.6 s`** —
> the larger of the two *bracketed* costs, rounded up. It over-predicts the
> IBM 5150 by 0.11 s a record and the GLaBIOS twin by 0.03, which is the right
> direction of error: an estimate that runs late on a machine that is stopped
> is the wrong one.

### 0.4 The three constants everything else is built from

```
TP_FIX    = 2.60 s   per record, BIOS fixed cost, bracketed          (0.3)
TP_COAST  = 0.56 s   the reel coast at each record boundary          (7.2)
TP_PAINT  = 0.007 s  the pre-freeze repaint, damage-rect only        (7.7)
```

and the tape rate, which is `ones x 0.99230 + zeros x 0.49615` ms a byte:

| data | ones/byte | ms/byte | one 258-byte block |
|---|---:|---:|---:|
| all `00` | 0 | 3.9692 | **1.024 s** |
| plain text | 3.4 | 5.6561 | **1.459 s** |
| compressed / random | 4.0 | 5.9538 | **1.536 s** |
| all `FF` | 8 | 7.9384 | **2.048 s** |

**Every published duration ROUNDS UP**, for §0.3's reason: 32,768 bytes
computes to 308.5 s and is published as **5:09**, not 5:08.

**Every table in §3.5, §3.6 and §6.3 is derived from those seven numbers by
`tools/os88tape.py --selfcheck`, and MUST NOT be computed by hand** — §15
wave 2 makes the reference codec the thing that prints them, because a hand
table is what put two unrepresentable `lastblk` values into an earlier draft
and would have put them into the test fixture with it.

---

## 1. Architecture

> **One package owns the window, the state machine, the format, every checksum,
> all file I/O — and the `int 15h` transport. There is no driver. The kernel
> gains two API cells and nothing else.**

### 1.1 The user's if/else, answered plainly

> *"This can be a driver accessible from file manager if you can do it in 200b
> or less. Else, an app."*

**The condition cannot be met at any price, so: an app.** Not because the bytes
do not fit — a File-menu item that launches an app measures **109 bytes as
built / 106 attributable** (`.text` +17, `.cold` +92, `.bss` 0), comfortably
inside 200 — but because **a driver has nowhere to put the feature**:

- `drivers/os88drv.inc:34-36`, verified verbatim this session: *"**You have no
  window, no instance and no menu.** You are not an app: no dock tile, no Task
  Manager row, no callbacks from the window manager. The Control Panel is your
  user interface and the kernel owns it."*
- A file-manager verb is **run-to-completion under the gfx lock**
  (`kernel/files.inc:3953-3958`; SPEC.md §12.8.3: *"The freeze IS a gfx-lock
  hold"*). One entry, one return. It cannot own a Start button, a Stop button
  or a moving picture.
- A driver's only drawing surface is a Control Panel page of 221×121 px, which
  **cannot animate** — `cp_tick_due_x` hard-gates on
  `cmp byte [cp_sel], CP_ITIME` — and the item list is **9 of 9 full**, with
  `CP_CH` unable to grow because CGA is 200 rows and `kernel/ctrl.inc:60-67`
  already spends the last 4 px of margin.

**The File-menu hook is costed and REFUSED, not deferred.** `FM_NFILE equ 10`
carries its own comment *"MENU_POPMAX is 11, so this is the last one that
fits"* (`kernel/files.inc:1796`) against `MENU_POPMAX equ 11`
(`kernel/menu.inc:208`) — both verified this session, both identical on
kern_big and kern_small. **The File menu has exactly one free slot, and a
twelfth item assembles and is silently unreachable.** Spending the last
irreplaceable slot on a peripheral that one machine model in the world has, to
hit a byte number nobody asked to be hit, is the decision a maintainer regrets
in a year — and a menu slot is not denominated in bytes, so the 200-byte budget
does not address the cost at all. §12.1 keeps it priced.

### 1.2 Why the transport is in the package and not a `.DRV`

| shape | resident kernel | runs on kern_small? | verdict |
|---|---:|---|---|
| `TAPE.DRV` + `TAPE.O88` | **129** — 51 `.text`, 38 `.bss`, ~40 `.cold` | **no** | **refused** |
| kernel module (a third entry in an existing `.DRV`) | ~0–41 | yes | refused — no window either |
| **one package + two API cells** | **47** | **yes** | **taken** |

1. **A `TAPE.DRV` costs 129 resident bytes of which 89 land in
   `KERN_CODE_MAX`.** The bill: a `drv_tab` row 16 + `drv_memk` word 2 +
   `drv_cfgbit` byte 1 + `'TAPE.DRV',0` 9 + `'Tape',0` 5 = 33 `.text`; a new
   `DRVC_TAPE = 6` is 4 `.text` (`drv_fptr6`/`drv_fseg6`) + 38 `.bss`
   (`drv_owner` +2 via `resw DRVC_MAX`, `drv_svc` +36 via
   `resb DSV_SIZE*(DRVC_MAX-1)`); plus a `SYSTEM.CFG` bit, a Drivers-page row
   and a **mandatory** `tests/unit/t_drvmem.py` row.
2. **`kern_small` loads no `.DRV` of any kind.** `%define OS88_DRIVERS 1` sits
   inside `%ifdef KERN_BIG` (`kernel/kernel.asm:316-319`, verified), so
   `SYSTEM.CFG` is never read and no driver reaches that disk. `MIN_RAM_KB` is
   **196** for kern_big and **128** for kern_small
   (`kernel/kernel.asm:2083-2087`). **So a 5150 with 128–195 KB runs
   kern_small — exactly the machine class most likely to still have a deck
   attached — and a driver-hosted transport would spend 129 resident bytes to
   REMOVE the machine the feature is named after.**
3. **The layering objection has one surviving edge and it is real.** The
   driver would arbitrate nothing a package cannot (it cannot read
   `snd_ch2mode` either, being kernel `.bss`) — but `drv_shutdown_x` is the
   **only** hook the machine runs before `int 19h`
   (`kernel/ui.inc:2814-2822`), and §3.7 states what that costs a package.
   That is the one argument for a driver this design does not defeat; it
   bounds it instead.

**And the precedent an earlier draft leaned on does not carry the weight.**
`tests/sysbench/sysbench.asm:2386-2408` does bank and restore ports 60h/61h
byte-for-byte inside one `pushf`/`cli`…`popf` behind the model-byte gate — but
it touches no PIC and no PIT, its own comment sizes the window at *"a few
microseconds"*, and `tests/` is by CLAUDE.md's Layout rule **software that does
not ship**. It supports §2.1's four-instruction model-byte gate and nothing
beyond it. **The nine-second bracket needs its own argument, and §5.1 is that
argument, made against SPEC.md §34.1 rather than by analogy.**

### 1.3 The UI task, not a worker

`OSAPI_WM_ONWAKE` (0x0458, `apps/os88api.inc:3334`) is the one callback that
runs on the UI task **without** the gfx lock and is expressly allowed to call
the file slots. `OSAPI_WM_WAKE` (0x0450) posts one from any context, at most
one queued per window, and `evq_push` calls `sch_wake_ui`
(`kernel/events.inc:80`) so a posted wake runs the UI task immediately.
**One record per wake, re-post only while there is work.** RunCPM's slice shape
(SPEC.md §74.1).

**A background worker is refused.** It would buy nothing — the thing it would
overlap with is the UI task, which cannot run during a record either, because
IRQ0 is masked. It would cost one of 13 task slots (6 on kern_small), a
§20.6 rule 7 amendment (`int 15h` is on no worker-callable list), and a
`[fd_req]`-style staged/committed handshake because *a worker may not touch a
file*.

**On stack depth, both options are unmeasured and this document says so on both
sides.** The ROM's cassette frame depth is measured nowhere in this tree;
`tools/stkdepth.py` reads source and cannot walk a ROM. `W_ONWAKE` runs on
`SS:STK0_TOP`, a 1,024-byte region the UI task does not share with a worker
slice (STACK-SLOTS-PLAN §12.1) — but it is also the **deepest context in the
machine** at that moment (`ui_task` → `evq_pop` → `wm_wake_disp` → `ui_bill` →
`wm_pkgcall` → the handler → `tp_xfer` → the ROM), and `SCH_MAGIC` at
`STK0_BOT` is read only by `sch_switch`, which cannot run while IRQ0 is masked.
**So the margin is unknown, not comfortable.** §15 wave 5 takes the number with
`tools/stkwater.py` on the `_cas` twin during a record; if it will not fit, the
answer is a shallower call chain into `tp_xfer`, not a worker.

Package header byte +15 stays `OS88_STACK_192` for form; no worker is spawned.

### 1.4 Files

**New:**

```
apps/tape/tape.asm          the package: header, entry, window, state machine
apps/tape/tapefmt.inc       the record format - build, parse, validate, CRC-16
apps/tape/tapexfr.inc       the int 15h transport, the IMR bracket, the PIT
                            cell calls, the floppy-motor wait, the signal sniff
apps/tape/tapeui.inc        OSAPI_WM_GEOM-driven layout, painters, the coast
apps/tape/reels.inc         8 x 16x16 masked hub phases (8 x 66 = 528 bytes)
tests/tapesim/tapesim.asm   the FAKE-TRANSPORT build: %includes tapefmt.inc,
                            tapeui.inc and a MEMORY transport of the same
                            shape. Built by `make bench`, never shipped.
                            WEAVE-SPEC 1.2's rule: shared as SOURCE, never
                            as a copy
tools/os88tape.py           the HOST reference codec: builds and verifies a
                            bit-exact tape stream and the os8088 record layout,
                            --rom ibm|glabios, --selfcheck. os88lz.py's shape
tests/unit/t_tapefmt.py     fast row over that codec
tests/unit/t_tapedet.py     fast row over the detection predicate, against a
                            COMMITTED fixture (9.2)
tests/tapesim.py            soak: the whole program over the fake transport
tests/tapehostile.py        soak: 29 malformed tape images, one per check
tests/tapecomp.py           soak: the compression contract on the machine
tests/tapehw.py             soak: the SHIPPED arm on a _cas twin
tests/taperefuse.py         soak: the two detection gates and the 2 s sniff
tests/tapequantum.py        soak: a QUANTUM=2 kernel keeps its tick rate
```

**Changed:** `kernel/kernel.asm` (two `OSAPI_JSLOT` cells + two 6-byte stubs +
two `.cold` bodies; the table assertion `161 * 8` → `163 * 8`, verified at
`kernel/kernel.asm:3849`, and `osapi_table_end` 0x0518 → 0x0528);
`kernel/sched.inc` (`sch_fast_on`'s guard, `sch_account`'s guard, one `.bss`
byte); `kernel/snd.inc` (`spk_tone`/`spk_pcm_start` refuse while the PIT is
lent); `kernel/compress.inc` (one new DL verb on `cmz_verb`);
`apps/os88api.inc` (two `%define`s and their contract blocks); `Makefile`;
`tests/suite.py` (nine rows plus the fixture rules); `SPEC.md` (the new section 88, the §34.1
amendment, and §14's corrections);
`tools/martypc/configs/os8088_machines.toml` (one `[[machine]]` block).

**`tests/textsites.txt` is NOT changed, and that is a claim §15 wave 5 has to
make good**: every string this window draws goes through `OSAPI_FONT_RUN`
(§7.4), so the package introduces **no** transparent-text call site and the
ratchet's count does not move. A file not in that list *may not call
transparent text at all* — which is exactly the case a new package hits — so
if any surface turns out to need transparency, it is registered with which of
SPEC.md §6.6.2's six cases it is, in the same commit, or the build fails.

**No kernel knob.** The test seam is a **second package build**
(`-DTAPE_FAKE`), which costs no `$(KNOBS)` name, no `$(VIDSTAMP)` entry, no
mandatory `t_buildmatrix.py` row and no extra kernel assembly inside the
`full` tier's `buildmatrix` row. The one exception is **`TAPEMODE2=1`**
(§13.1 item 1), a field A/B for §0.1 and §0.2.

---

## 2. Detection, and the refusal

### 2.1 Two gates, and the model byte alone is a false positive on three of this project's own thirteen ROMs

**Gate 1 — the board.** `F000:FFFE == 0FFh`, `sb_sw1`'s shape verbatim
(`tests/sysbench/sysbench.asm:2386-2390`):

```asm
    push es
    mov  ax, 0xF000
    mov  es, ax
    cmp  byte [es:0xFFFE], 0xFF   ; FF = 5150. FE/FB = XT, FC = AT, FD = PCjr
    pop  es
    jne  .nohw                    ; -> TP_HW_MODEL, and bank the byte we read
```

Four instructions, no side effect, no port touched, stable for the session.

**Correction to the brief: no shipped kernel byte reads this today.**
`kernel/stkdiag.inc:520` is inside `%ifdef STK_DIAG` (a `STKDIAG=1` knob
build) and parses nothing; `tests/sysbench` and `tests/bootdiag` do not ship.
There is no `OSAPI_*` slot that answers the model byte and this design adds
none — the package reads it itself, for zero kernel bytes.

**Gate 2 — the BIOS, and it is not optional.** Walked this session over all
thirteen GLaBIOS ROMs in `build/martypc/run/media/roms/GLaBIOS/`:

| model byte at `0x1FFE` | ROMs | of those, cassette dispatch at `F000:F859` |
|---|---:|---|
| `FF` (a 5150) | 5 — `0.2.5_8PC`, `0.2.6_8P`, `0.2.6_8PC`, `0.4.0_8P`, `0.4.0_8PC` | **2** — `0.2.6_8P` and `0.4.0_8P` only |
| `FE` (an XT) | 8 | 0 |

The two cassette builds begin `FB 80 FC 03 76` at `F000:F859` (`STI /
CMP AH,3 / JBE`); the other eleven begin `FB B4 86 80 FC` (`STI /
MOV AH,86h / CMP AH,1`). GLaBIOS sets `ARCH_ID = 0FFh` for the 5150 target and
then `CASSETTE = 0` for the sub-types — so **three ROMs in this tree report
model `FF` and answer `AH=86h`**, and `rom_set = "glabios_pc"`, which every
`_gla` twin here boots, resolves to one of them.

```asm
    mov  ah, 0x01           ; MOTOR OFF - the resting state. No relay click, no
    int  0x15               ; spin-up delay (both ROMs' spin-up is inside
    jc   .nobios            ; AH=02/03 only): microseconds. CF=1 = this BIOS
                            ; has no cassette support. TEST CF, NEVER a
                            ; particular AH - IBM answers 80h (PCBIOS.ASM:5040)
                            ; and GLaBIOS 86h (GLABIOS.ASM:11265)
```

Both gates run **once, in the entry proc**, into one cached byte `[tp_hw]`.
SPEC.md §47 rule 5's cost corollary — *"a greying test runs on every paint, so
it must be cheap … the answer belongs in a value someone already computed"* —
is satisfied by construction.

**Gate 2 is not side-effect-free and §3.8 says so.** `CASSETTE_IO`'s first
instruction is `STI` (PCBIOS.ASM:5003; GLABIOS.ASM:11262), and GLaBIOS's
`CAS_MOTOR_OFF` is an **unprotected** read-modify-write of port 61h with IF=1
(:11376-11380). So the gate runs **before any window is shown and before any
sound can be playing**, and it is the only `AH=01` on a cold path.

**`0xFD` (PCjr) is refused, deliberately.** 5150CAXX accepts it and the port is
real, but os8088 has never booted a PCjr, there is no profile or code for one
anywhere in the tree, and the PCjr's motor reportedly needs a second port-B
bit. Admitting a machine nobody has tried is not generosity; it is an untested
code path with a relay on the end.

**`[cpu_tier]` is refused as a gate.** SPEC.md §60.2 is binding: *"the tier is
INFORMATION, not permission … questions about what the processor IS, never
about what hardware exists."* A cassette socket is a board fact, and
`CPU_8086` admits every XT clone anyway.

**Gate 3, the POST wrap test, is refused for v1** — §11 item 9.

### 2.2 What may be greyed, and what may not

SPEC.md §47 rule 4: one predicate, three consumers — the test that greys, the
test that refuses the click, and the words are the same call.

| fact | greyable? | why |
|---|---|---|
| not a 5150 / no cassette BIOS (`[tp_hw] != TP_HW_OK`) | **yes** | stable, knowable without doing the thing, cached at launch |
| a transfer is running | **yes** | our own state |
| another Tape window holds the deck (§5.1's claim) | **yes** | a kernel fact, answered by a cell |
| no file chosen (Save) | **yes** | our own state |
| the file is bigger than `TP_MAXFILE`, or than the largest free run | **yes** | `OSAPI_FILE_FIND_RAW` + `OSAPI_MEM_AVAIL`, both cheap, both facts |
| a deck is plugged in | **no** | unknowable without playing tape |
| Play/Record pressed, tape cued, azimuth, level | **no** | `AH=04` / `AH=02` / `AH=01` are the answers, at runtime |
| the tape is blank | **no** | 12–90 seconds of `AH=02` is the answer |

**Start is NEVER greyed for a transient reason, and never on an error.** Every
failure in the bottom half of that table is fixable by the user in five
seconds, and `apps/ftpd/ftpd.asm:978-1013` carries the argument in the tree
already: **§77.17 meeting §48.5, *"a greyed button is a dead end you cannot
retry from."*** After an error the caption becomes `Retry` and stays live.

With `[tp_hw] != TP_HW_OK` the window still opens, Save/Load/Verify are
dithered (§47 rule 3 — grey rounds to black on 1bpp, so `gfx_pen_dis` makes
`font_ink` checkerboard the caption, which `os88ui_btn` handles at
`apps/os88ui.inc:370-378`), and the status line names **which gate failed**:

```
No cassette port.  This is an IBM PC 5150 feature; the machine reports
model FE.
```
```
No cassette port.  The ROM in this machine has no cassette support
(int 15h answered 86h).
```

One byte of state, and the difference between "the software is broken" and
"this machine cannot do this."

### 2.3 The two-second signal sniff

**A read against a stopped deck, a blank tape or an unplugged cable is
12–90 seconds of dead machine, and the two ROMs differ by a factor of five:**

- **IBM: one pass of 16,250.** `MOV SI, 7` (PCBIOS.ASM:5084) is the retry
  count, and it is decremented **only at W16** (:5192-5195), on a bad sync byte
  *after* a leader was found. A dead line exhausts `MOV DX,16250` (:5090) and
  W6 jumps straight to W17 (:5085-5087). At ~3,650 clocks a transition
  (`READ_HALF_BIT`'s `CX=100` poll, four instructions of eight bytes, so the
  8088's fetch floor does not bind) that is **~12.4 s**; priced instead at
  GLaBIOS's *measured* 5,359 clocks a poll call it is 18.2 s. **12–18 s.**
- **GLaBIOS: 5 x 16,000.** `MOV BP, 5` (GLABIOS.ASM:11672) x
  `MOV CX, BHB<1000>` = 16,000 half-bit units (:11693). **89.84 s MEASURED**
  under MartyPC (428,696,716 cycles / 4,772,728).

Twelve seconds of frozen machine as the *first* thing a user experiences is
already unacceptable, and **announcing it is strictly worse than not spending
it.** Before the first `AH=02` of any read, behind both detection gates:

```asm
tp_sniff:                       ; out: CF=0 the line is moving, CF=1 it is dead
    mov  ah, 0x00 / int 0x15    ; motor ON (AH=00 has no spin-up: GLaBIOS's
                                ; JPE at :11327 does not take it, IBM's
                                ; MOTOR_ON at :5044 is three instructions)
    in   al, 0x62 / and al, 0x10 / mov ah, al     ; PPI port C BIT 4, banked
    ; poll for a CHANGE, bounded at ~2 s off apps/os88pit.inc's pit_now
    mov  ah, 0x01 / int 0x15    ; motor OFF, on every path
```

**It runs with interrupts fully live and masks nothing.** Two reasons: it
measures a level *change* over two seconds, not a period, so an ISR costs at
most one poll sample out of tens of thousands; and `pit_now`'s high half comes
from the BIOS tick at `0040:006C` (`apps/os88pit.inc:48`), which needs IRQ0 to
advance over a 2-second span. **~40 bytes**, no timing precision.

If nothing moves in two seconds:

```
No signal from the recorder.  Press Play, check the cable and the
volume, then click Load again.               [ Try again ]  [ Load anyway ]
```

**`Load anyway` is not decoration and it is not optional.** The design's own
cue instruction is *"wind to just before the file, press PLAY"* — which is
inter-file blank tape, exactly where a level change over two seconds is least
certain. A false negative there is the software blaming hardware that is fine,
and §48.5's rule that a refusal must not be a dead end applies to a refusal
this design invented as much as to a greyed button. §13.1 item 5 asks the field
how static a real deck's inter-file tape actually is.

**What the sniff does not catch, stated:** a tape playing silence, noise that
fakes a leader, and a mis-cued tape all still cost the full timeout — and noise
of plausible cycle lengths can loop GLaBIOS's leader search with no timeout and
no retry decrement at all (:11720-11727, the `JB CAS_READ_HEADER_START` arm
does not touch BP).

**Only the negative branch is testable anywhere in this project.** MartyPC's
`calc_port_c_value` returns a hardwired `0` for the data line whenever the
motor is on — `// TODO: Implement cassette data input`,
`build/martypc/src/crates/marty_core/src/devices/ppi.rs:856-864`, read this
session — so nothing here can make the sniffed bit change. A plausible **wrong**
implementation passes identically: poll bit 5 instead of bit 4 with ch2 gated
off and that reads constant too, and on iron it would report "signal present"
for a dead deck. So `tests/taperefuse.py` asserts the **port and the mask at a
breakpoint**, not merely the elapsed time (§10.2).

---

## 3. The transport

### 3.1 `tp_xfer` — one record, in order

```
; tp_xfer - move ONE record.
; in:   AL = 2 (read) or 3 (write)
;       ES:BX = the record buffer, BX = 0, ES = a PINNED heap claim's base
;       CX = bytes: 256 (classify) or exactly what the header declared
; out:  CF/AH/DX/BX exactly as the ROM leaves them
; CONTEXT: the W_ONWAKE handler, on the UI task, gfx lock NOT held.
; It does not return for 4.1 to 8.8 seconds.

 1.  refuse unless [tp_hw] == TP_HW_OK and CX is 256..4096 and a multiple of
     256                                          -> CF=1, AH=0x80
 2.  FIRST RECORD OF AN OPERATION ONLY:
     a. OSAPI_PIT_LEND AL=2 - CLAIM the PIT and the speaker for the whole
        operation (5.1). CF=1 = another Tape window has it, or [sch_fast] is
        set (a QUANTUM= kernel), or the speaker is mid-tone. REFUSE IN WORDS.
     b. wait, bounded ~3 s off pit_now, for 0040:0040 to reach 0 - the floppy
        motor countdown. The ROM's int 08h chain is what decrements it, and
        IRQ0 is about to be masked for MINUTES, so without this the drive
        spins for the whole transfer.
 3.  pushf / cli                        ; so the bank and the mask are atomic
 4.  bank port 0x21 (the IMR) and port 0x61
 5.  mask: IRQ0, IRQ3, IRQ4 always      or al, 0x19
          + IRQ1 ON A WRITE ONLY        or al, 0x1B      (see 3.3)
     IRQ2/5/6/7 are left exactly as found.
 6.  OSAPI_PIT_LEND AL=1                ; ch0 -> mode 3, divisor 0. BOTH
                                        ; directions (0.1 and 0.2). The cell
                                        ; sets [sch_pitbios], which is what
                                        ; makes step 9's residual tick harmless
 7.  popf                               ; IF comes back; the ROM STIs anyway
 8.  int 15h AH=02/03                   <-- THE FREEZE, 4.1 to 8.8 s
 9.  cli                                ; THE VERY FIRST INSTRUCTION AFTER IT.
                                        ; Both ROMs UNMASK IRQ0 THEMSELVES on
                                        ; the way out - PCBIOS.ASM:5206-5208
                                        ; (W18), GLABIOS.ASM:11359-11362 - and
                                        ; a tick has certainly been latched
                                        ; across a 9-second mask, so one WILL
                                        ; fire inside the ROM's own tail. That
                                        ; window is irreducible; this closes
                                        ; every instruction after it
10.  bank AX, BX and DX (the ROM's whole answer)
11.  OSAPI_PIT_LEND AL=0                ; ch0 -> mode 2, [sch_pit_last]
                                        ; re-seeded, [sch_pitbios] cleared.
                                        ; PRESERVES AX/BX/DX AND THE FLAGS,
                                        ; which is why it can stand here
12.  mov ah, 0x01 / int 15h             ; MOTOR OFF - BEFORE the IMR restore,
                                        ; because GLaBIOS's AH=01 goes through
                                        ; CAS_TIMER_ON_MOTOR_OFF and UNMASKS
                                        ; IRQ0 (:11352-11362). After the
                                        ; restore it would undo it
13.  pushf / cli
14.  restore the IMR byte for byte from the bank
15.  restore port 0x61 with bits 0 and 1 CLEARED - not banked (3.8)
16.  popf
17.  LAST RECORD OF AN OPERATION, and every refusal path:
     OSAPI_PIT_LEND AL=3 - release the claim. The cell puts ch2 back to
     spk_pcm_idle's exact resting state (0xB6, no count) and hands the speaker
     back to the sound layer.
18.  map AX/BX/DX -> CF/AH and answer   (8.4 rows 22 and 22a)
```

The `pushf`/`cli` windows are microseconds each and bracket only the
save/restore, never the transfer.

### 3.2 `cli` does not work, and the 8259 is the only instrument

`CASSETTE_IO`'s **first instruction is `STI`** (PCBIOS.ASM:5002-5003;
GLABIOS.ASM:11262; and every GLaBIOS ROM binary in the run tree begins `FB` at
`F000:F859`), and IBM's exits with `RET 2`, which **discards the caller's
pushed flag word**. So a caller's `cli` is undone before a single tape bit
moves and the caller returns with IF **set** regardless.

**5150CAXX's `asm cli` / `int86x` / `asm sti` around every `AH=02/03`
(5150CAXX.H:95-97, 117-119, 150-152, 184-186) is inert.** It works in practice
only because DOS is idle. The `cli` in step 3 above is there solely to make the
port-21h read-modify-write atomic, which is CLAUDE.md's §1 rule and `sb_sw1`'s
idiom — it is not protecting the transfer.

### 3.3 The interrupt budget, and the IRQ1 asymmetry

**The write budget is 248.08 µs** — half of a 0-bit's 496.15 µs period, because
`WRITE_BIT` polls **one whole phase** of the mode-3 square wave on port C
bit 5 (PCBIOS.ASM:5440-5447: poll high, poll low, then reload;
GLABIOS.ASM:11587-11597 is the same shape). It is a **hard threshold, not a
probability**: the CPU polls every ~7 µs, so either it saw the level before the
ISR or the level is still asserted after. Below it, corruption is *zero*; above
it, corruption — and **the write cannot report it**.

**The read budget is also 248.08 µs, but it is spent differently and it fails
loudly.** `READ_BYTE` sums BOTH half-bits and compares the **period** against
`06F0h` = 1776 (PCBIOS.ASM:5236-5240; GLaBIOS's `ADD AX,DX` then
`CMP DX, BEEP_1K7+BEEP_2K` at :6010-6021). A 0-bit's period is 1,184 counter
units and a 1-bit's is 2,368, so either must move 592 units — 296 PIT clocks =
**248.08 µs** — to cross. And a late edge **cancels within a bit**: it
lengthens one half and shortens the next by the same amount, so only an edge on
a *bit boundary* distorts anything, and then it distorts two adjacent bits in
opposite directions. The failure is a wrong byte, which the block's own CRC-16
catches at 1-in-65,536 and reports as `AH=1`.

The leader search is the **most tolerant** phase, not the strictest: at
PCBIOS.ASM:5103 `MOV DX,0378H` = 888 against a *half*-bit, and
`JNC W4` (:5119-5121) restarts only on a half-bit that reads **short**. A
lengthened one still counts as leader. The single strict place is the **sync
bit**, where a 0 half-bit at 592 units must stay under 888 — 296 units =
124.04 µs — and missing it costs a retry, not data.

os8088's tick handler is **394 µs at the absolute floor and ~783 µs in full**
(`sch_account` 500 cycles = 104.8 µs and `sch_switch` 1,521 cycles = 318.7 µs
are both *measured*, SCHED-IDLE-PLAN §1.3). That is **1.6x to 3.2x over**. The
mouse ISR is worse: `mou_apply` calls `cur_move` and draws the arrow inside the
ISR, and PERFORMANCE.md's floor for a small `gfx_*` call is **756 µs** — 3x the
whole budget.

**And the ROMs disagree about who masks what:**

| | IBM 04/24/81, 10/19/81, 10/27/82 | GLaBIOS `CASSETTE=1` |
|---|---|---|
| `AH=02` read | masks IRQ0 at W7 (`PCBIOS.ASM:5105-5107`), unmasks at W18 (`:5206-5208`) | masks in `CAS_MOTOR_WAIT` (`:11394-11398`), unmasks in `CAS_TIMER_ON_MOTOR_OFF` (`:11359-11362`) |
| `AH=03` write | **never touches port 21h** — `WRITE_BLOCK` `:5300-5399` walked end to end, zero hits | **masks IRQ0** — same `CAS_MOTOR_WAIT`, both directions |
| `AH=01` motor off | leaves the IMR alone | **unmasks IRQ0** (`:11352-11362`) |
| IRQ1/3/4 | never masked, IF set throughout | same |

So on a genuine IBM 5150 a write runs with os8088's tick **live**. **We mask
IRQ0, IRQ3 and IRQ4 ourselves on both directions, on every ROM** — which
removes the ROM fork and makes an IBM 5150 and a GLaBIOS twin behave
identically. It also means **the IRQ0 half of the bracket is untestable on
GLaBIOS by construction** (§10.2's `tapehw` row says so in its `why`), because
that ROM would freeze the tick with our bracket deleted.

**IRQ1 is the one asymmetry, and it is decided by which failure is silent:**

- **On a WRITE, IRQ1 is MASKED.** `AH=03` ends `SUB AX,AX / RET`
  (PCBIOS.ASM:5399-5400) and **can never report an error**, so a keystroke that
  stretches one bit past 248 µs produces a corrupt tape the user discovers
  minutes later on playback, if ever. There is nothing to abort — a write always
  terminates. **Silent, permanent, unrecoverable → mask it.** The window says
  so: *"Do not type while writing."*
- **On a READ, IRQ1 is LEFT LIVE.** A read can hang without bound on noise, and
  both ROMs poll `0040:0071` bit 7 (`BIOS_BREAK`) in every read loop and clear
  it at entry — PCBIOS.ASM:5010, :5093-5095, :5108-5109, :5154-5155;
  GLABIOS.ASM:11297, :11695, :11712, :11764. **Ctrl+Break aborts a cassette
  read, for zero bytes of ours.**

  **Correction to an earlier draft: os8088 DOES own `int 09h`.** `mouse_init`
  writes `kbm_isr` into `0000:0024` on **every tier** (`kernel/mouse.inc:573-589`,
  with the comment at :575-577 saying so), and `kbm_old9` is at :2914. The
  conclusion survives — `kbm_isr` chains unconditionally to the banked ROM
  handler with `jmp far [cs:kbm_old9]` (:2453) — but the **cost** is ours, not
  the ROM's: every keystroke during a read runs `sch_wake_ui` and `kbd_ovflow`
  (:2373-2385) *before* the chain, inside the read's timing window. §13.1 item 6
  measures it; until then the design's own rule applies and an instruction count
  is not a measurement.

The rule, in one line: **mask where the failure is silent; keep the escape
where the failure is loud.**

**A replacement `int 09h` in the package is REFUSED** — §11 item 8.

### 3.4 The record size

There is a **2.6-second floor per record that no software can remove** (§0.3),
and the machine is dead for all of it. A block is 258 bytes on tape (256 data +
2 CRC), so 1.536 s at the compressed rate.

| `recblk` | payload | tape/record | wall/record | overhead | worst-case Stop latency |
|---:|---:|---:|---:|---:|---:|
| 1 | 248 B | 1.54 s | 4.14 s | 62.9% | 4.7 s |
| 2 | 504 B | 3.07 s | 5.67 s | 45.8% | 6.2 s |
| **4** | **1,016 B** | **6.14 s** | **8.74 s** | **29.7%** | **9.3 s** |
| 8 | 2,040 B | 12.29 s | 14.89 s | 17.5% | 15.5 s |
| 16 | 4,088 B | 24.58 s | 27.18 s | 9.6% | 27.7 s |

**Default `TP_RECBLK = 4`.** Carried in the header, so a tape written otherwise
still reads. Stop latency is the record's wall time plus one coast (§0.4): a
click landing at the start of a record is honoured when that record ends.

Below it the tape time runs away: 512-byte records cost another ~40 s on a
16 KB file to move Stop from 9.3 s to 6.2 s, and 6.2 s is not "responsive"
either. Above it the freeze stops being something a caption can honestly carry
— **fifteen seconds of a stopped machine is where a user concludes the button
is broken** — and the retry unit (§4.5) doubles with it.

### 3.5 The whole-file model, with every term in it

```
total =   TP_FIX + hdrblk
        + (nrec-1) x (TP_FIX + recblk x blk)
        + (TP_FIX + lastblk x blk)
        + (nrec+1) x (TP_COAST + TP_PAINT)
```

**The last term is not decoration.** §7.7 sequences the coast and the
pre-freeze paint strictly before each record, so both are additive wall time
the user waits through — 0.567 s a record, 19.4 s on a 33-record file. An
earlier draft's model omitted them and was 5-6% optimistic for a reason it
never counted, which is precisely the error §0.3 spends a section avoiding.
**Carry `TP_COAST` and `TP_PAINT` as named constants**, so a change to §6.2's
ramp moves every caption with it.

With `TP_FIX` 2.6, `hdrblk` 1.09 (224 zero bytes + 32 content + 2 CRC),
`blk` 1.536 (compressed) and `TP_COAST + TP_PAINT` = 0.567:

| payload (compressed) | nrec | lastblk | wall |
|---:|---:|---:|---:|
| 1,016 B | 1 | 4 | **13.6 s** |
| 4,064 B | 4 | 4 | **41.5 s** |
| 9,000 B | 9 | **4** | **1:28** |
| 18,704 B | 19 | **2** | **2:58** |
| 32,768 B (`TP_MAXFILE`) | 33 | **2** | **5:09** |

**The two boundary rows are boundary rows on purpose and go into the fixture
corpus explicitly.** An earlier draft tabulated `lastblk` 3 for both 9,000 and
18,704; both are wrong by §4.3's own formula, and for 9,000 the value is not
merely imprecise but **unrepresentable** — three blocks hold 768 − 8 = 760
payload bytes and the tail is 872. §8 row 7 makes `lastblk` an **exact-equality
hostile-input check**, so a wrong tabled value copied into `t_tapefmt`'s corpus
would either reject valid tapes or agree with a wrong implementation. Hence
§0.4's rule: the table is printed by `tools/os88tape.py --selfcheck`, never
typed.

**The top row is kern_big's.** §6.5 states the per-kernel ceiling.

### 3.6 The freeze paragraph — for SPEC.md section 88, the release note and the About box

> **What "does not freeze" means here.** The IBM cassette interface has **no
> DMA**: the data path is PPI port C bit 4 in and PIT channel 2 out, polled on
> port C bit 5, and **nothing is wired to an 8237 DREQ**. The 8088 *is* the
> modem, and a bit is discriminated by its period — 496 µs for a zero, 992 for
> a one. **Any interrupt that runs longer than 248 microseconds makes the CPU
> miss an edge or mis-time one, and the tape is corrupted, not merely slowed.**
> os8088's own tick handler is 394–783 µs and its mouse ISR draws the arrow,
> which starts at 756 µs.
>
> **This is a HARDER freeze than a floppy transfer, not a softer one.** §7.4's
> cursor tracking rests on two claims and both die here: `int 13h` runs with
> **IF set** — §15.3.8 measured 21 consecutive ticks taken inside one, with not
> one IRQ0 lost — and the CPU in there is *waiting*, parked on IRQ6 while DMA
> moves the data, so a frame drawn from the timer ISR costs no real time at
> all. §7.4.1.1 already writes down what happens when that half is removed, one
> device along, for the hard-disk driver: *"this is our own driver polling an
> ATA controller, not a BIOS parked on IRQ6, so a cursor draw costs real
> time."* Here it is one step worse still — **a draw longer than 248 µs does
> not slow the transfer, it corrupts it.**
>
> So for the duration of a record the scheduler, the mouse, the keyboard and
> every kernel drawing primitive are switched off, deliberately and completely.
> **A machine running a tape operation is about 6% available.** What ships
> instead is four narrower promises. **The transfer is cut into 1,016-byte
> records**, one `int 15h` each, so a file is broken into 8.7-second intervals.
> **Each interval is announced before it starts, with its length** — the block
> in flight is on the progress bar and the caption reads *"stopped for about 9
> seconds"*. **Between records the machine is entirely alive** — the reels coast
> to a stop, the counter advances, the pointer comes back, other programs run,
> and Stop is honoured. **And a read can be stopped mid-record with
> Ctrl+Break**, which both ROMs test three times per loop.
>
> What is **not** claimed: the machine is not multitasking during a record, the
> pointer does not move inside one, a click made inside one is lost outright,
> the clock loses the whole transfer, and a 16 KB file is about two and a half
> minutes each way whatever we do — the tape moves 168 bytes a second and no
> amount of software changes that.

### 3.7 The clock, one accounting sample, and the one thing that survives a Restart

`[ticks]` is incremented once per **delivered** IRQ0 (`kernel/sched.inc:1917`),
and the 8259 latches at most one pending IRQ0 per line, so an IF-masked window
of *N* ticks delivers exactly one. `clk_tick` advances the wall clock purely
from `[ticks]` deltas (`kernel/clock.inc:1671-1690`) and `clk_probe` has
exactly one caller, `clk_init` at `:139`. **There is no periodic RTC resync
anywhere.**

**A 5150 cannot get the time back.** SPEC.md §37.0.1: all four rungs of the
clock ladder are chips a 5150 does not have, so `[clk_tier]` is 0. A 5-minute
transfer loses 5 minutes of wall clock, permanently. The app measures it
exactly — it knows the bits it moved and their periods — and says so once, as a
toast (`OSAPI_TOAST` 0x0380, any context, ~20 bytes of package):

```
Clock is about 5 min 9 s slow - set it in Control Panel > Date/Time.
```

**It must NOT catch `[ticks]` up.** `blk_pass` compares `ticks - [blk_t0]`
against `[ss_idle]` (`kernel/blank.inc:314-320`), so adding the lost ticks
would fire the screen saver **the instant the transfer ended** — the machine
appearing to die at the finish line. `OSAPI_CLK_ADV` is the proper fix and it
is **deferred** (§12.2).

**One tick per record is charged against a mode-3 counter, on every record.**
Not "somehow": both ROMs unmask IRQ0 themselves before returning (§3.1 step 9),
a tick is certainly latched across a nine-second mask, and it fires inside the
ROM's own tail. `[sch_pitbios]` (§5.1) makes `sch_account` **skip** that
sample, which costs 6 resident bytes and removes the whole of it — the sample
was garbage anyway, `[sch_pit_last]` being ~50 counter wraps stale. **What
cannot be closed** is that if that tick reaches `sch_switch` and hands the CPU
to another task, that task's `pit_now` (`apps/os88pit.inc:63`, `neg ax` on a
mode-2 assumption) reads **2x fast** until we are scheduled again and step 11
runs — at most one quantum, 54.9 ms. Its only consumers are package animation
pacers, so the visible effect is one frame's worth of hurry. Stated, bounded,
not hidden.

**The motor is NOT put back across a Restart, and that is the driver argument
this design does not defeat.** `OSAPI_WM_ONCLOSE` (0x0468) is called for every
way of *closing the window*, and it calls `int 15h AH=01` unconditionally. But
`ui_cmd_reboot` (`kernel/ui.inc:2799-2851`) flushes the Control Panel, calls
`drv_shutdown_x` — *"detach every loaded driver (SPEC.md 51.2): int 19h resets
no hardware"* — takes `gfx_lock`, calls `vid_reboot` and jumps to
`sched_unhook`. **There is no `wm_ask_close`, no window notification, nothing
that reaches a package at all.** So System ▸ Restart with a transfer armed
rides the reboot with port B bit 3 still clear and the deck still turning.
The honest claim is therefore **"the relay stays energised until POST rewrites
port 61h, about a second later"**, not "the motor is always put back". The tree
has exactly one mechanism for *hardware must be put back before `int 19h`* and
it is `drv_tab`-only; §16 row 3 puts that back in front of the user, and
`tests/tapehw.py` breaks at `ui_rb_go`/`dsk_rb_go` and reads port 61h bit 3 the
way `tests/fddpark.py` reads the FDC.

### 3.8 Timer 2, the speaker, and a race no caller can close

`WRITE_BLOCK` sets port 61h bit 0 (timer-2 gate) and clears bit 1 (speaker
data), programs channel 2 to mode 3 per bit, and leaves it in **mode 0 with a
count of 1** with both bits unrestored (PCBIOS.ASM:5314-5323, :5384-5394);
GLaBIOS leaves mode 0 and **no count at all** (:11548-11549).
`kernel/snd.inc:38-43` owns exactly those with a one-owner/one-mode state
machine (SPEC.md §34.1).

**Step 15 restores 61h bits 0 and 1 CLEARED — not banked — and step 17's cell
writes control word `0xB6` with no count.** That is `spk_pcm_idle`'s exact
resting state (`kernel/snd.inc:317-336`: `and al, 0xFC` then `mov al, 0xB6`),
and it matters: a *banked* restore of a gate bit that was set for a tone leaves
a 65536-count mode-3 square wave on the speaker — an **audible 18.2 Hz rattle**
lasting until something else reprograms ch2. Bits 2–7 are preserved; bit 3 is
the motor and belongs to the cassette.

**A tape and a tune cannot share timer 2, and since §5.1 that is a REFUSAL
rather than a hope.** `OSAPI_PIT_LEND AL=2` refuses when `[snd_ch2mode]` is
non-zero, and while the claim is held `spk_tone`/`spk_pcm_start` refuse with
CF=1. So a tone playing when Go is pressed **refuses the transfer** and says
so, and a tone started during one refuses instead of being truncated. That
retires what an earlier draft carried as a stated-but-unenforceable refusal and
as deferred item 12.3.

**The race that remains belongs to the BIOS and no caller can close it.**
`CASSETTE_IO` STIs on its first instruction, and both ROMs' MOTOR_ON/MOTOR_OFF
are **unprotected read-modify-writes of port 61h with IF=1** —
PCBIOS.ASM:5044-5057, GLABIOS.ASM:11324-11327 and :11376-11380. On a
pre-emptive kernel an IRQ0 between the `IN` and the `OUT` can switch tasks, and
a 61h write by that task (which the kernel itself takes care to do under
`pushf`/`cli`) is then lost — or the motor bit is. **This is the same hazard
§11 item 8 refuses a package `int 09h` over**, and it applies to our own
`AH=00`/`AH=01` calls; the difference is that the `STI` is inside the ROM and
there is no version of this feature that avoids it. What the design does
instead is **minimise the count**: gate 2 is one `AH=01` at launch before any
window is shown, the sniff is one pair, and step 12 is the only `AH=01` on the
hot path — one per record rather than one per refusal.

One more GLaBIOS-only side effect, for the record: `CAS_MOTOR_ON` clears the
speaker DATA bit as well (`AND AL, NOT MASK PBSP AND NOT MASK PBCM`,
GLABIOS.ASM:11325), so on that ROM a motor-on silences a playing tone. With
§5.1's claim in place nothing can be playing, which is the second reason for it.

---

## 4. The tape format

### 4.1 What the BIOS gives you, what it does not, and where the two ROMs differ

One `int 15h AH=03` lays down one complete, independently findable record:

```
  1 bit   0            start bit    -- GLaBIOS ONLY (GLABIOS.ASM:11448)
  2048    1            LEADER  = 256 bytes of FFh               2.0322 s
  1 bit   0            sync bit
  1 byte  16h          sync byte, MSB first                     5.458 ms
  N x [ 256 data bytes + 2 CRC bytes ]                          1.536 s each
  32      1            TRAILER = 4 bytes of FFh                 31.8 ms
```

**The leading zero bit is a write-side difference between the two ROMs and
nothing else.** GLaBIOS emits it — `CALL CAS_WRITE_BIT ; start output bit is 0`
at :11448, documented in its own format comment at :11418-11424 — and IBM does
not: `WRITE_BLOCK` goes from `CALL BEGIN_OP` (PCBIOS.ASM:5324) straight to
`MOV CX,0800H` and the leader (:5327-5331). **A 256-zero-byte record is 4,153
bits from an IBM 5150 and 4,154 from a GLaBIOS twin.** It does not affect
interoperability — each reader searches for the leader
(PCBIOS.ASM:5088-5121 / GLABIOS.ASM:11685-11744) and an extra zero bit in front
of it is simply not leader — so tapes cross freely; but the host codec must
know which side wrote them, which is why `tools/os88tape.py` takes
`--rom ibm|glabios` and `t_tapefmt` holds **two** goldens (§10.2).

CRC-16/CCITT: preset `0xFFFF`, polynomial `0x1021`, MSB-first, no reflection,
**transmitted one's-complemented, high byte first**, verified on read against
residue `0x1D0F`. Derived from `CRC_GEN` (PCBIOS.ASM:5460-5487 — the `RCR/RCL`
overflow trick plus `XOR 0810h` plus `RCL` *is* poly `0x1021`), confirmed
independently by GLaBIOS's named constants `CAS_CRC_PRE/RES/POLY`, and verified
numerically by simulation.

The reader needs only **512 half-cycles = 256 one-bits = 254 ms** of leader
against the 2,048 bits the writer emits — an **8x margin**, which is what makes
back-to-back records work with a motor stop/start between them.

**What it does not give: no filename, no length, no directory, no seek, no
end-of-file, no end-of-tape, no linkage between records, no write verification,
and no integrity statement above the 256-byte block.** All of that is the
format's job.

Three BIOS behaviours the format is built around:

- **A read scans forward to the next leader, for free.** The deck need only be
  cued *before* the record wanted.
- **A read of `CX` < the record's length leaves the tape INSIDE that record**;
  the next call scans past the remainder and lands on the following record's
  leader. That is how skipping works, and it is why a file's header must be its
  **own record**, exactly one block long.
- **`CX = 1` costs exactly what `CX = 256` costs**, because the last block is
  padded to 256 — **and the two ROMs pad differently.** IBM's `WR_BLOCK` loop is
  `MOV AL,ES:[BX] / CALL WRITE_BYTE / JCXZ W25 / INC BX / DEC CX`
  (PCBIOS.ASM:5353-5357): once CX reaches 0 the advance is skipped and the loop
  re-reads `ES:[buffer+N]` — **the byte immediately AFTER the caller's buffer** —
  and writes it to tape up to 255 times. GLaBIOS preserves AL across
  `CAS_WRITE_BYTE` and its pad loop never reloads (:11506-11511), so it repeats
  the last **data** byte.

> **This design never pads, on either ROM, because every `CX` it issues is a
> multiple of 256.** With `CX = 256k` IBM's `OR CX,CX / JNZ WR_BLOCK`
> (:5376-5377) sees CX and DX reach zero together and the pad loop is never
> entered. **That is a security property and not only a determinism one**:
> IBM's pad is an information leak onto removable media, and §8 row 24 is the
> rule rather than the mechanism.

### 4.2 Header record — 256 bytes exactly, written with `CX = 256`

Write all 256 bytes yourself rather than letting the ROM pad. Two reasons: the
result is deterministic and host-reproducible on both ROMs, and a pad the
writer chose cannot contain the 32-consecutive-`FF` run that would false-trigger
a leader search (§4.6).

**The corollary is that there are 224 free bytes and no reason to squeeze a
field.** The 6 ms/byte pressure applies to the *body* records, not here.

```
off  size  field      contents and rule
 +0    4   magic      'O','8','T','P'. The first word is 0x384F, os8088's own
                      family word (SPEC.md 20.2); 'TP' disambiguates. FOUR
                      bytes and not two: this reader is handed hundreds of
                      blocks over a tape's life and 16 bits of magic is one
                      false header in 65,536. It costs nothing - it lives
                      inside a block padded to 256 either way. MUST NOT begin
                      0xA5, which is IBM Cassette BASIC's header magic AND the
                      TRS-80's sync byte.
 +4    1   ver        1. A version this reader does not know is REFUSED, never
                      guessed - SPEC.md 20.2's v1/v2 precedent.
 +5    1   kind       0 = a FILE. Anything else is refused.
 +6    1   flags      bit 0  the payload is a 'CZ' container THIS writer made
                      bit 1  the payload was already compressed on disk
                      bit 2  the LZ format when bit 0 is set (0=LZ4, 1=LZB)
                      bits 3..7 MUST BE ZERO
 +7    1   recblk     256-byte blocks per FULL body record, 1..16.
                      recbytes = recblk * 256; capacity = recbytes - 8.
 +8    1   lastblk    blocks in the LAST body record, 1..recblk. It is what
                      lets the reader ask for the RIGHT CX without having read
                      the preamble it is inside (4.5), and it saves up to
                      3 blocks = 4.61 s per file over padding the tail.
 +9    1   nrec       body records that follow, 1..255
+10    2   ckfile     CRC-16/CCITT (0x1021, preset 0xFFFF, MSB-first, NOT
                      complemented) over all `size` payload bytes. EVERY body
                      record repeats it - see 4.4.
+12   12   name       the SPEC.md 19.1 display form: 8.3, NUL-terminated
                      inside 12 bytes, every byte before the NUL in 0x21..0x7E.
+24    4   size       the payload's byte count. 1..TP_MAXFILE (32,768).
+28    4   usize      what it EXPANDS to (== size when uncompressed).
                      INFORMATIONAL ONLY - it is what the scan list prints,
                      and it may NEVER size a claim or a check.
+32  224   zero       written zero, NEVER READ. Not "reserved for future use":
                      reading it is how a future writer's field becomes an old
                      reader's bug.
```

**There is deliberately no header checksum.** The BIOS's own CRC-16 already
covers these 256 bytes at 1-in-65,536, and a second CRC over the same bytes
adds nothing. What the BIOS cannot say is whether the block is *ours* and
whether the fields are *sane*, and those are answered by the 32-bit magic and
by §8's range checks. Written down because it is exactly the field a reviewer
adds by reflex.

### 4.3 Body record — `recblk × 256` bytes (`lastblk × 256` for the last)

```
off  size  field
 +0    2   'O','T' = 0x544F. DELIBERATELY a different word from the header's
           first, so neither kind can be parsed as the other. Both tested,
           both ways.
 +2    1   seq      1..nrec
 +3    1   nrec     repeated, so a body found without its header names the
                    file's shape immediately ("...part 3 of 9 went by")
 +4    2   paylen   payload bytes in THIS record, 1..(this record's capacity)
 +6    2   ckfile   the header's, REPEATED
 +8  ...   payload; the tail past paylen is written ZERO and read as nothing
```

Records 1..nrec−1 carry exactly `recbytes − 8` bytes; record `nrec` carries the
remainder, in `lastblk × 256 − 8` bytes of capacity. So:

- `nrec == ceil(size / (recblk*256 − 8))` **exactly**
- `lastblk == ceil((size − (nrec−1)*(recblk*256 − 8) + 8) / 256)` **exactly**

Both are derivable from the header alone and both are checked (§8 rows 6, 7).

Eight bytes of preamble costs **48 ms** of tape against a record whose floor is
8.74 s — **0.5%**. What it buys is that a mis-assembly is caught in one record
instead of at the end of the file, minutes later.

### 4.4 `ckfile` in every preamble, not an arbitrary file id

The block CRC catches **corruption**. It cannot catch **mis-assembly**: the user
stops the deck between records, winds back a little and restarts, and every
block recovered is CRC-perfect while the file is wrong.

**Repeating `ckfile` in every body preamble is the same two bytes as an
arbitrary `fid` and is strictly stronger**: a record spliced in from a
*different* file is rejected **the instant it arrives** rather than at the final
checksum. Two writes of the *same* content share `ckfile` and splicing them is
harmless, because the bytes are identical; two writes of *different* content
differ, and are caught.

**Reuse the BIOS's own CRC-16/CCITT** — same polynomial, same preset, same code
path, not complemented, over the whole payload. Not because it is stronger than
a sum, but because `tools/os88tape.py` must implement that CRC anyway to build
a tape image, so the machine and the host share **one** algorithm. That is
`t_mirror.py`'s doctrine applied before the mirror exists.

Cost: bit-serial at ~100 clocks/byte ⇒ **0.7 s over 32 KB**, against a
309-second transfer — **0.22%**. A 256-entry table would spend 512 bytes to save
half a second; refused. CRC-32 would cost 4 free header bytes, ~80 bytes of code
and double the cycles, and lose the algorithm-reuse argument; refused.

Checked **after** the last record is assembled and **before** a byte reaches the
disk. A mismatch means the file is not created at all.

### 4.5 The read-length invariant, the ROM bug behind it, and why the retry unit is the FILE

> **NEVER issue a read whose `CX` exceeds what the record holds.** Every read is
> either **256 bytes** (classify) or **exactly the `recblk × 256` /
> `lastblk × 256` the header already declared.**

**An earlier draft justified this against an unsettled splice risk. It is not
unsettled and it is not a splice — it is a heap buffer overrun in the GLaBIOS
ROM, driven by tape content, and the invariant does not close it.** Traced this
session:

```
GLABIOS.ASM:11674  MOV DI, BX                 ; DI = output buffer, set ONCE
             11675  PUSH CX                    ; the original request
             11758  POP CX  / PUSH CX          ; CX RE-ARMED to the original
             11769  STOSB                      ; ...and DI is NEVER reset
             11789  CALL CAS_READ_WORD         ; the two CRC bytes
             11790  JC CAS_READ_ERR            ; a dropout HERE...
             11804  DEC BP / JNZ CAS_READ_HEADER_START   ; ...retries, BP = 5
```

`CAS_READ_HEADER_START` is *before* the `POP CX / PUSH CX`, so every retry
re-arms CX to the original byte count while DI stands where the last `STOSB`
left it. A dropout inside the two CRC bytes is reachable with **any** CX
including multiples of 256, so a 1,016-byte read can resync onto the next
leader and store up to 1,016 more bytes at the advanced DI, up to four more
times: **~5,080 bytes written into a 1,016-byte buffer, ~4 KB into whatever
follows it on the heap.** And on a *successful* retry `AH = 0` and
`DX = orig − CX = CX`, so an `AH==0 && DX==CX` post-condition **passes**.

**IBM's ROM is safe here** and the contrast is instructive: `JCXZ W12`
(PCBIOS.ASM:5158-5163) stops the store the moment CX reaches 0, and SI — the
retry counter — is decremented only at W16 (:5192-5195), which is unreachable
once the block loop has been entered. This is specific to the GLaBIOS `8P`
ROM, which is **the one arm this project can actually execute** (§10.3).

**Two defences, and the design takes both:**

1. **A third post-condition the ROMs both support.** `BX` on return is the
   end-of-output pointer — GLABIOS.ASM:11816 `MOV BX,DI`, and IBM's own header
   comment at PCBIOS.ASM:5090-5094 says *"BX POINTS 1 BYTE PAST LAST BYTE PUT
   IN MEM"*. With `BX = 0` on entry, **require `AH==0 && DX==CX && BX==CX`**. A
   retry that re-armed CX leaves `BX > CX` and is rejected. (§8 row 22a.)
2. **The record buffer is the LAST region of the claim and is `5 × recbytes`
   long.** Five, because BP starts at 5 and that is the most the ROM can write.
   At the default `recblk = 4` that is 5,080 bytes, rounded to 5 KB; the
   classify buffer is `5 × 256` = 1,280, rounded to 2 KB. Sized from the
   header's own `recblk` at read time, so a foreign `recblk = 16` tape asks for
   20 KB and is refused with the arithmetic on the glass rather than
   overrunning.

**The consequence, and it must be adopted with the invariant: the unit of retry
is the FILE, not the record.** Identifying a body record before reading it costs
a 256-byte read that consumes its first block, after which the rest of that
record can never be recovered — the next call scans forward past it. So on any
body failure the reader **stops, keeps nothing, and says**:

> *Block 4 of 19 could not be read (CRC error — the block was recovered but is
> damaged). Rewind to just before the file and press Retry.*

`Retry` re-runs the whole scan-and-load. Cost: one re-read of the file — 2:58
for a 19-record file — **and only when a dropout actually happens.** §12.4 keeps
record-granular retry deferred.

**The header record being exactly one block is what makes the invariant free.**
A `CX=256` classify read of a header consumes it *exactly*, leaving the tape at
the first body record; the header then declares both body lengths.

### 4.6 The false leader — a second, independent argument for compressing

The reader's leader test is *"≥ 256 consecutive one-bits"*. **32 consecutive
`0xFF` bytes inside a payload satisfy it.** During a scan that burns one of the
read's retries (the sync byte then fails), and exhausting them ends the scan
with `AH=04`, reported as *"no tape"*.

Uncompressed data hits this readily — a 1bpp bitmap's white ground, a
complemented zero-fill, an unused buffer. Compressed data essentially never
does. **This is a second, independent argument for §6, and for writing our own
zero pad.** It is in the design record because nobody derives it twice.

### 4.7 IBM's `0xA5` header — recognised, never written

IBM Cassette BASIC's header record is 256 bytes of which 16 are significant:
`+0` `0xA5`, `+1` an 8-byte SPACE-padded name, `+9` a type byte (`0x80` =
tokenised BASIC), `+10` a word length, `+12`/`+14` a load segment and offset —
`0060:081E` in 5150CAXX's stub.

**Compatibility is refused on four structural grounds**, each sufficient: all
sixteen bytes are spoken for, with no room for a compression flag, a format
selector, a whole-file checksum, a record index or a 32-bit size; three of them
describe a **memory image** that Cassette BASIC *acts on*, and a file has no
address; eight bytes cannot hold an 8.3 name; and a tape we wrote with an `0xA5`
header, played into ROM BASIC, would load our bytes to `0060:081E` and
**execute them as tokenised BASIC**. That is not interoperability.

**But recognise it.** The scan already holds the first 256 bytes of every
record. `cmp byte [buf], 0xA5` and reporting `IBM BASIC: <8 chars>` costs about
a dozen bytes and turns *"this tape is unreadable"* into *"this tape has three
BASIC programs on it and none of ours"*.

---

## 5. The two kernel cells

> **This is the only part of the design that lands in the kernel, it is 47
> resident bytes, and one of the two amends a rule SPEC.md §34.1 records a
> refusal about. §16 row 1 is the decision.**

### 5.1 `OSAPI_PIT_LEND` — because a package may not write PIT channel 0

SPEC.md §34.1 (SPEC.md:44076-44098) is binding and says, verbatim:

> **"PIT channel 0 is never written.** Not re-rated, not re-moded, not 'sped up
> and divided'."

and then, in the same section:

> **"Rejected, recorded so it is never re-litigated:** re-rating ch0 … breaks
> §8.1's radix, the floppy motor countdown and every tick-denominated
> constant"

**§0.1's bracket re-MODES ch0 — the exact prohibited operation — and an earlier
draft did it from a PACKAGE, in nine bytes, without citing §34.1 or §8.1
once.** Three things make that unshippable rather than merely irregular:

1. **The restore cannot be a constant.** `sch_fast_on`
   (`kernel/sched.inc:467-499`) loads 32768, 21845 or 16384 out of `sch_fdivs`
   (`:522`) and is armed system-wide by `make QUANTUM=`
   (`kernel/kernel.asm:4736-4739`), by fsx (`kernel/fsx.inc:221`) and around PCM
   (`kernel/snd.inc:296-301`). A blind `0x34 / 0 / 0` restore with `[sch_fast]`
   still set leaves `sch_isr`'s sub-tick divider (`kernel/sched.inc:1832-1845`)
   dividing an 18.2 Hz tick by N — **the wall clock runs N times slow for the
   rest of the session, silently.** And it cannot be read back: a 5150 has an
   **8253**, which has no Read-Back command at all, and even the 8254's
   read-back returns the current count and a status byte, never the programmed
   reload value. **So "every port is banked in a register and put back byte for
   byte" is FALSE for both PIT channels** and an earlier draft's claim to that
   effect is withdrawn.
2. **`sch_fast_off` re-seeds `[sch_pit_last]` after touching ch0** (`:512-514`)
   *"or the first full tick after this charges a whole bracket's worth of
   garbage to somebody"*. A package cannot reach that word.
3. **The ch2 half is `snd_ch2mode`'s** (`kernel/snd.inc:39, 336`), which a
   package can neither read nor write, so after a tape write the kernel's
   ownership byte would describe a chip that no longer holds that mode.

Every one of those is a fact only the kernel knows. So the bracket goes where
the knowledge is:

```
%define OSAPI_PIT_LEND      KERNEL_SEG:0x0520
OSAPI_PL_ENTER   equ 1      ; AL - hand ch0 to the ROM
OSAPI_PL_LEAVE   equ 0      ;    - take it back
OSAPI_PL_CLAIM   equ 2      ;    - take the PIT and the speaker for an OPERATION
OSAPI_PL_RELEASE equ 3      ;    - give them back
;
; Lend PIT channel 0 to a ROM routine whose constants assume the BIOS's own
; mode 3, for the length of one BIOS call, and take it back exactly as
; sch_fast_off does (SPEC.md 8.1, 34.1). THE SCHEDULER OWNS CHANNEL 0 AND THIS
; IS THE ONLY OTHER SITE THAT WRITES IT. A package may not, and could not
; restore it correctly if it tried: an 8253 has no read-back, so the divisor
; is not knowable from outside sched.inc.
;
; in:   AL = one of the four above. BX, CX, DX, SI, DI, BP, DS, ES untouched.
;
; out:  AL=2 CLAIM   CF=0 you hold the PIT and the speaker until you release.
;                    CF=1, AH = why, and nothing changed:
;                      1  [sch_fast] is set - a QUANTUM= kernel, or fsx or PCM
;                         has ch0 re-rated. The divisor would not survive the
;                         round trip, so the answer is no, not "probably".
;                      2  [snd_ch2mode] is non-zero - the speaker owns ch2.
;                      3  somebody already holds the claim.
;       AL=1 ENTER   ch0 -> mode 3, divisor 0. [sch_pitbios] = 1, which makes
;                    sch_account SKIP its sample: the ROM unmasks IRQ0 itself
;                    on the way out (PCBIOS.ASM:5206, GLABIOS.ASM:11359) and
;                    the tick that fires in its tail would otherwise be
;                    charged against a counter stepping by 2. Requires the
;                    claim; CF=1 otherwise.
;       AL=0 LEAVE   ch0 -> mode 2, divisor 0, [sch_pit_last] re-seeded from
;                    sch_pit_now, [sch_pitbios] = 0.
;                    **PRESERVES AX, BX, DX AND THE FLAGS**, so it can be the
;                    first thing after the int 15h without banking the ROM's
;                    answer first.
;       AL=3 RELEASE 61h bits 0 and 1 cleared, ch2 control word 0xB6 with no
;                    count - spk_pcm_idle's exact resting state
;                    (kernel/snd.inc:317-336). The speaker is the sound
;                    layer's again.
;
; While the claim is held, sch_fast_on and spk_tone/spk_pcm_start answer CF=1.
; That is 34.1's one-owner rule working in both directions, and it is what
; makes "a tape and a tune cannot share timer 2" a refusal instead of a hope.
;
; IT DOES NOT TOUCH THE PIC. Port 21h is the caller's (3.1 steps 4, 5, 14) -
; 34.1 claims the PIT and the speaker, not the interrupt mask.
;
; context: any task, lock held or not. Every write is inside one pushf/cli..
; popf, which is 34.1's ch0 latch-atomicity rule.
```

**The SPEC.md §34.1 amendment that must ride in the same commit**, narrow and
written as an exception rather than a relaxation:

> **Channel 0 is written by `sched.inc` alone.** `sch_pit_lend` is the second
> site and the only one outside `sched_init`/`sch_fast_on`/`sch_fast_off`: it
> hands the chip to a ROM routine whose own constants assume the BIOS's mode 3,
> for the length of one BIOS call, with IRQ0 masked by the caller throughout,
> and it **refuses whenever `[sch_fast]` says the divisor is not 65536** — so
> §8.1's radix is never in question, because the lend cannot happen on a kernel
> where it would be. `[sch_pitbios]` suppresses the one `sch_account` sample the
> ROM's own IRQ0 unmask makes unavoidable. The recorded refusal above stands
> unchanged: re-rating ch0 *for pacing* is still rejected, and this is not that.

### 5.2 `OSAPI_COMPRESS` — because a package cannot compress anything today

`cmz_pack` lives in `CLONE.DRV`'s `.modl` image, reached only through
`mod_fp`/`CMZFP` from kernel `.cold` (`kernel/files.inc:4531` is its one call
site), and the SDK publishes `OSAPI_DECOMP` (0x04F8) with **no encoder beside
it**. And *"a driver talking to another driver"* is not available as a shape:
`CLONE.DRV` is an **on-demand kernel module**, not a loadable driver
(`kernel/mod.inc:218-236` — the `.DRV` extension is *"for the attributes and
nothing else"*); it has no `drv_tab` row, no `DRVC_*` class and no
`DSV_PKGCALL`, so `OSAPI_DRV_CALL` cannot reach it.

The precedent for the fix is exact: **`OSAPI_FILE_DLG`** (0x0150,
`apps/os88api.inc:565`; the kernel cell is `OSAPI_JSLOT api_fdlg_open` at
`kernel/kernel.asm:2801` — an earlier draft called it `OSAPI_FDLG_OPEN`, which
is not a symbol in this tree) is already a package-callable cell whose body
fetches a module: `mov al, MOD_FDLG / call mod_need` then
`call far [FDFP + …]`, with `fdlg_reap_x` doing the matching `mod_drop`.

```
%define OSAPI_COMPRESS      KERNEL_SEG:0x0518
%define OSAPI_LZ_LZ4        0
%define OSAPI_LZ_LZB        1
OSAPI_CMP_NOGAIN equ 1
OSAPI_CMP_NOMEM  equ 2
OSAPI_CMP_NODISK equ 3
;
; Compress a block, the way File > Compress does (SPEC.md 20.15, 22.22). The
; encoder lives in CLONE.DRV; this cell fetches it, runs it and drops it, so a
; package sees one far call and never learns that a module exists. The
; counterpart of OSAPI_DECOMP (0x04F8), published since 20.13 with no encoder
; beside it.
;
; in:   AX = the SOURCE segment; the bytes at AX:0000
;       CX = the source length, 1..0xFFFF. 0 and >= 64K are refused before
;            anything is claimed (cmz_pack's CX is 16 bits)
;       DX = the OUTPUT segment; the stream at DX:0000, CX bytes of room
;
; out:  CF=0 - AX = the packed length, ALWAYS < CX
;              BL = the format used: OSAPI_LZ_LZ4 or OSAPI_LZ_LZB - exactly
;                   the byte a 'CZ' container's +2 wants (today always LZB)
;       CF=1 - AX = why, and NOTHING was written to DX:
;              OSAPI_CMP_NOGAIN  it did not get smaller. Store it plain. This
;                                is the ORDINARY answer for an already-
;                                compressed file and is NOT an error.
;              OSAPI_CMP_NOMEM   the TABLES would not fit even at the 1,024
;                                window. Nothing was claimed.
;              OSAPI_CMP_NODISK  the module could not be fetched: the SYSTEM
;                                disk is not in the BOOT drive. mod_need goes
;                                to [dsk_bootvol] and ONLY there
;                                (kernel/files.inc:4550-4553).
;
;       Everything else preserved - BX (aside from BL), CX, DX, SI, DI, BP,
;       DS and ES all come back. The output is a WHOLE STREAM (the T word, the
;       symbols and the raw tail, 20.13.7) and NOT a 'CZ' container: the
;       8-byte header is yours to write, because you may want the file's and
;       you may want none.
;
; IT CLAIMS THE TABLES AND NOTHING ELSE: CMZ_PREV (8,192) + 2*(window+1)
; bytes, halving the window from CMZ_WMAX 16,384 to CMZ_WMIN 1,024 until it
; fits - so 41 KB at the full window down to 11 KB at the minimum. YOUR TWO
; BUFFERS ARE YOURS and are not copied. Ratio cost of the halving: 68.9% at
; 16,384 against 71.4% at 4,096 (SPEC.md 20.15.1).
;
; context: THE UI TASK, GFX LOCK NOT HELD. It reads a file (mod_need) and
;       takes the heap, so it is 20.6 rule 7's forbidden half exactly like the
;       file slots - and W_ONWAKE is where a package may do both.
;       cmz_pack reports through OSAPI_FS_PROG every 512 source bytes
;       (kernel/compress.inc:277), and THOSE CALLS ARE INERT FOR THIS CALLER:
;       nothing has armed the kernel's progress widget, and "unarmed it is a
;       compare and a return" (apps/os88api.inc:1106-1107). Paint your
;       "Compressing..." caption, RELEASE THE LOCK, then call - the call is
;       ~3.2 s and a lock held across it hides the pointer for all of it,
;       which 6.7 spends a paragraph explaining is the difference between two
;       pictures.
```

**Correction to an earlier draft, and it is why this contract reads as it
does.** That draft's body called `cmz_claim` from kernel `.cold` and mandated
the gfx lock. Neither works. `cmz_claim` is at `kernel/compress.inc:1192`,
inside `section .modl` (opened at `:95`, `.text` does not resume until `:1423`)
— a module image cut out of `kernel.bin`, loaded into a heap claim and
reachable only through a `mod_fp` far entry; it addresses `[cs:cmz_u]`,
`[cs:cmz_k]`, `[cs:cmz_w]` **CS-relative in CLONE.DRV's own segment** and
reaches memory through `call COLD_SEG:mmf_mem_claim`. So the body as specified
**does not assemble**. And it claims the wrong thing: its own layout comment
(`:1177-1181`) is *"base + 0 the source, base + KU*64 the output,
base + (2*KU+1)*64 head[]/prev[]"* — it allocates **the source and output
regions themselves**, which a caller that already holds its payload would be
paying for twice. The "75 KB at the full window for a 16 KB source" figure was
that double count.

**So the ladder goes in the module, as a new DL verb, and `CLO_NENT` stays 2.**
`kernel/clone.inc:164-167` states the convention three lines above the constant
an earlier draft quoted: *"`CLE_DISP equ 0` — **ONE entry for the cloner: the
image dispatches on DL itself, so four verbs cost one mod_fp slot**"*, and the
second slot is already the compressor's (`modl_e_cmz: call cmz_verb`, `:198`),
where `cmz_verb` is itself a DL dispatcher (`cmp dl, FMC_UNCOMP * 2`,
`kernel/compress.inc:610`). The new verb branches **before** `cmz_verb`'s
Disk-window selection block (`:601-608`), claims
`CMZ_PREV/1024 + window/512 + 1` KB with a halving ladder, calls `cmz_pack`
with the caller's AX/DX and BX = the table segment, frees, and returns
`cmz_pack`'s own CF and AX. **~60 bytes of `.modl`, 0 resident, no new slot.**

### 5.3 What the two cells cost

| item | `.text` | `.bss` | `.cold` | `.modl` |
|---|---:|---:|---:|---:|
| `OSAPI_COMPRESS`: table cell (8) + `call COLD_SEG:… / retf` stub (6) | **14** | 0 | | |
| …its `.cold` body: bank DS→`KERNEL_SEG`, bank AX/CX/DX, `mod_need MOD_CLONE`, `call far [CLFP + 4]` with the new DL, `mod_drop` | | | ~55 | |
| `OSAPI_PIT_LEND`: cell (8) + stub (6) | **14** | 0 | | |
| …its `.cold` body: four arms, two `out` triples, the `sch_pit_now` re-seed, the 61h/ch2 idle | | | ~95 | |
| `[sch_pitbios]` | | **1** | | |
| `sch_fast_on`'s guard (`cmp byte [sch_pitbios],0 / jne .out`) | 6 | | | |
| `sch_account`'s guard, same shape | 6 | | | |
| `spk_tone` / `spk_pcm_start` guard | 6 | | | |
| the cloner's new DL verb and its table ladder | | | | ~60 |
| **TOTAL** | **46** | **1** | **~150** | **~60** |

**Resident +47**, of which all 47 land in `KERN_CODE_MAX`, the guard CLAUDE.md
says cannot be raised. Table assertion `161 * 8` → `163 * 8`
(`kernel/kernel.asm:3849`), `osapi_table_end` 0x0518 → 0x0528.

`OSAPI_JSLOT` is 8 bytes (`kernel/kernel.asm:2702-2713`) and `api_decomp`
(`:4055`) is the identical 6-byte `call COLD_SEG:… / retf` stub, so both
figures are read off shapes already in the tree rather than estimated.

---

## 6. Compression

### 6.1 The insight that removes most of the design

`OSAPI_FILE_READ_AT` (0x0358) is **raw**: it hands back the packed bytes exactly
as they sit, wrapper and all, and `OSAPI_FILE_FIND_RAW` (0x0500) gives the
matching on-disk size (SPEC.md §20.14.3 — *"THE CELL A COPIER WANTS"*).
`dskw_czstamp` re-derives the directory hint from the first eight bytes of any
whole-file write (`kernel/diskw.inc:2966-2999`). And every reader on the machine
expands a `'CZ'` file transparently.

> **The tape payload is exactly the bytes that will land on the destination
> disk. The tape layer never expands and never re-wraps, and the reader calls
> NO decoder at all — not even `OSAPI_DECOMP`.**

Expanding on the way out would *lose* the compression; expanding on the way back
would silently convert the user's compressed file into a plain one.

### 6.2 The "already compressed" test — one bit, zero extra I/O

```
1. FILE_FIND_RAW the source into a 24-byte record
2. if (word [rec+22] & OSAPI_FIND_CZ):        ; apps/os88api.inc:3158-3165
       a 'CZ' container. ALREADY COMPRESSED. Carry raw. flags bit 1.
3. else if the name ends .O88 / .DRV / .OVL / .WSM / .WPV:
       read the first cluster; word[0] == 0x384F -> a package or driver IMAGE.
       CARRY IT VERBATIM AND NEVER WRAP IT (6.3 below). byte[3] bit 3 says
       whether the image is already packed; report it as flags bit 1.
4. else: plain. THE ONLY case where compressing buys anything.
```

Step 2 costs **nothing** — bit 0 of the flags word is read out of the directory
sector the walk was holding anyway.

And it is not merely an optimisation, it is what stops the feature making files
bigger: measured with the shipped reference encoder, `cmz_pack`'s mirror
**refuses outright (CF=1, "no gain")** on `calc.o88`, `notepad.o88`,
`paint.o88` and `readme.txt`, and a second LZ4 pass gets **99.4%, 99.8%, 99.9%
and 100.2%** — `readme.txt` **grows by two bytes**.

### 6.3 What compression is worth on tape

Measured on this tree's own `build/readme-plain.txt` (16,304 bytes; LZB by the
shipped reference encoder gives 7,607), with tape times from §0.4's constants:

| | records | wall | shape of it |
|---|---:|---:|---|
| **plain, one `AH=03` call** | 1 | **96.0 s** | one 96-second dead machine |
| **plain, in 1 KB records** | 1 + 17 | **153.0 s** | seventeen freezes of ~8.4 s |
| **LZB (7,607 B), in 1 KB records** | 1 + 8 | **75.7 s** | eight freezes of ~8.7 s |

**Compression does not merely save time — it PAYS FOR the chunking overhead and
buys 20.3 seconds on top.** The responsive design is *cheaper* than the
unresponsive one. That is the strongest possible form of the user's *"everything
being written should be compressed"* requirement and of `recblk = 4`, and it
survives both the higher measured fixed cost of §0.3 and the coast-and-paint
term §3.5 adds.

### 6.4 The disk-swap consequence, stated plainly

`mod_need` goes to `[dsk_bootvol]` **and only there**
(`kernel/files.inc:4550-4553`). On a one-floppy 5150, compressing a file that
lives on another disk means system disk in, file disk back — SPEC.md §2.8.5's
swap. So the package **asks first**:

```
NOTES.TXT is 16,304 bytes - 2 min 33 s of tape.
Compressing it first would make it about 7,600 - 1 min 16 s.
Compress?   [Yes]  [No]
```

and, if the module cannot be fetched or the heap will not fund the tables,
refuses only the *compression*, not the transfer:

```
The system disk is not in the drive; writing NOTES.TXT uncompressed.
```

That is §48.5's rule — a permanent refusal and a transient one must not be coded
alike — and it keeps the feature working on a machine that cannot reach
`CLONE.DRV`.

### 6.5 Whole-file staging, and the claim layout

Both directions hold the whole payload in one **pinned** heap claim
(`MC_RLOC = 0` is the default, SPEC.md §66 — it must stay pinned, because a
compaction between the call and the ROM's first `mov al, es:[bx]` would move it
under the ROM).

- **Write**: `FILE_FIND_RAW` → claim → `FILE_READ_AT` at offset 0 → optionally
  `OSAPI_COMPRESS` into a second claim and write the 8-byte `'CZ'` header in
  front, **keeping the result only if `packed + 8 < size`** → cut records.
- **Read**: parse the header → claim → fill from records → verify `ckfile` →
  **one** `OSAPI_FILE_WRITE`.

This removes the whole-cluster chunking rule and FTPD's expensive per-transfer
`OSAPI_FILE_DFREE` re-derivation (SPEC.md §77.40 — 105 ms a call, 44% of an
18-second upload); `DFREE` is asked **once per operation**, banked. More
importantly it is the only shape in which **`ckfile` is verified before any file
is created**, so a corrupt tape leaves nothing behind rather than a half-written
file.

**The claim is `payloadKB + recslackKB` KB**, the payload at base offset 0 and
the record buffer at `base + payloadKB × 64` paragraphs, so **both** are
addressed with `BX = 0` — which the ROM requires, its inner loops doing
`INC BX` with no segment fixup (PCBIOS.ASM:5158, :5356). Heap bases are
1 KB-aligned, so this is satisfied by construction. `recslackKB` is
`ceil(5 × recbytes / 1024)` — **5 KB at the default `recblk = 4`** — for
§4.5's ROM overrun; the classify buffer is 2 KB for the same reason.

**`TP_MAXFILE = 32,768`** is the format's sanity bound: 32 KB is already 5:09 of
tape each way. **The LIVE ceiling is `OSAPI_MEM_AVAIL`'s largest run and it is
much lower on the machine this feature is named after**, so publish it per
kernel rather than letting §3.5's last row imply otherwise:

| machine | free heap at the desktop | realistic largest payload |
|---|---:|---:|
| kern_big, 640 KB | hundreds of KB | **32,768** (the format bound) |
| **kern_small, 128 KB** | **~50.5 KB** (`tests/small128.py`) | ~**20 KB** with a Disk window open, and compression refuses outright (11 KB of tables + two buffers will not fit) |

A file over either refuses with the arithmetic on the glass:

```
BEVERLY.MOD is 42,177 bytes - about 6 min 32 s of tape. The format
carries at most 32,768 (about 5 minutes). Refused.
```
```
PAINT.O88 is 21,977 bytes; the largest free block is 18 KB.
Close an application, or compress the file first.
```

---

## 7. The user interface

### 7.1 The window — laid out from `OSAPI_WM_GEOM`, never from a fixed rect table

**A fixed 320 × 146 content box does not fit CGA, which is the adapter of the
machine class this feature is named after.** `kernel/ctrl.inc:60-67` states the
arithmetic in the kernel's own source: *"CGA is 200 rows with a 20px bar and a
24px dock, so wm_fit's ceiling is 176 - 1 - 20 = **155**"*. `wm_fit`
(`kernel/wm.inc:409-458`) clamps `W_H` to `[vid_dock_y0] - MBAR_H - 1`, and
`wm_geom` (`kernel/wm.inc:6112-6117`) returns content = `W_H - (TITLE_H + 1)`
= 155 − 19 = **136**. `apps/os88api.inc:2255` says the same from the other side:
*"638x300 on a CGA comes back 638x155"*. The Control Panel, the kernel's own
reference for a window sized to fit every adapter, is `CP_CH equ 132`.

So:

- **publish an `OS88_PREFER` row** (`apps/os88api.inc:2260`, seven arguments:
  `name, vga_w, vga_h, herc_w, herc_h, cga_w, cga_h`; nine shipped packages
  already do this);
- **every rect is computed at paint time from `OSAPI_WM_GEOM`** (0x01B0), not
  tabulated;
- **the CGA arrangement is ≤ 136 content rows**, and the two footer lines fold
  into the status line there;
- and CLAUDE.md's obligation applies: **look at it on a 1bpp adapter before
  calling it done** (SPEC.md §39.4, §47.2).

The VGA/Hercules arrangement, at 320 × 146 content:

```
+========================================================================+
| =  Tape                                                                |
+========================================================================+
|                                                                        |
|   +----------------------------------------------------------------+   |
|   |     ,-'''-.                                    ,-'''-.         |   |
|   |    /  \|/  \        ####################      /  \|/  \        |   |   the
|   |   |  --O--  |       ####################     |  --O--  |       |   |   cassette:
|   |    \  /|\  /        ####################      \  /|\  /        |   |   drawn from
|   |     `-...-'                                    `-...-'         |   |   primitives
|   +----------------------------------------------------------------+   |   + two 16x16
|                                                                        |   masked hubs
|   PAPER.TEX                      18,704 bytes  (30,112 unpacked)       |
|   [########|########|########|::::::::|        |        |        ]     |   one cell
|   Block  4 of 19  -  stopped for about  9 seconds                      |   PER RECORD
|                                                                        |
|   (o) Save    ( ) Load    ( ) Catalog          [x] Compress            |
|                                                                        |
|   [ Choose... ]  [    Go    ]  [  Verify  ]  [  Stop  ]                |
|                                                                        |
|   Stop takes effect at the end of the block.  Do not type while        |
|   writing.  Ctrl+Break stops a read at once.                           |
+========================================================================+
```

The progress bar has **one cell per record**, not a smooth fill: `########` for
records done, `::::::::` **for the record in flight right now**, empty for the
rest. That is the single most important pixel in the design, because it is what
the user stares at for 8.7 seconds. The bar does not lie about being smooth,
and it carries *"we are in segment 4"* through the whole freeze.

The two numbers in the status line are **fixed-width and right-aligned**, which
is what makes §7.7's per-record repaint four cells instead of forty-four.

**Content x is a multiple of 8 by default**, and this needed checking rather
than asserting: SPEC.md §11.94's snap is now **opt-out**, not opt-in —
`kernel/wm.inc:4283-4340`, *"what moved is what a window that never calls at
all gets, and that is now ALIGNED"*, with `WF_NOSNAP` as the stored bit and
`wm_create`'s `mov word [bx+W_FLAGS], 1` as the whole of how the default is
applied. So the package calls nothing and gets alignment, and `font_run`'s
single-store fast path with it.

### 7.2 The animation — a decelerating coast, priced at 16×16 and not at 12×12

**Not a spinner, and this argument goes into SPEC.md section 88 verbatim so that
nobody "fixes" it later:**

> A continuous spinner implies continuous motion, and stopped dead for nine
> seconds it reads as **hung** — SPEC.md §7.1.4.3 records this project shipping
> a lit-but-frozen pointer and the field reporting it as a stutter, at a
> timescale of *milliseconds*. Nine seconds of a spinner frozen mid-turn is the
> same defect three orders of magnitude larger. And a one-notch-per-record
> advance is not motion either: a quarter-turn every 8.74 s is a visual
> revolution every ~35 seconds, which is a progress indicator with a cassette
> drawn on it.

**The reels COAST.** At every record boundary, the moment the machine comes
back, they spin an **8-frame decelerating burst over 560 ms** and stop.

| | |
|---|---|
| **mapping** | **8 frames = one full visual revolution = one record.** A four-spoke hub has 90° symmetry, so eight phases at 11.25° is a complete revolution. The mapping MEANS something: one turn of the reels is one block on tape. |
| **direction** | **Save = forwards (0,1,…,7); Load and Verify = backwards (7,6,…,0).** Physically a cassette runs the same way for both; this is a *legibility* choice and it is the user's, honoured as asked. The take-up reel's phase is offset by 2 so the two do not look mechanically linked. |
| **sprites** | one table of **8 × 16×16 masked phases**, `OSAPI_ICON_DRAW` (0x04B8, SPEC.md §25.6 — the masked sprite, any x). A record is `ICO_STAGE_SZ = 2 + ICO_STAGE_H * (ICO_STAGE_WW * 4)` = **66 bytes** (`kernel/icons.inc:51`), not 64: `icon_draw_x` reads a two-byte `ww`/`rows` header and refuses any width but one word (`:88`). **8 × 66 = 528 bytes.** |
| **cost** | **~10 ms a 16×16**, and the number is in the tree: PERFORMANCE.md:11039, *"**`ICON_DRAW` at ~10 ms a 16×16** is more than Set 84's 6.7 for a 12×12 would predict"*, cross-checked there against the palette's 111 ms (eight of them plus sixteen fills). **Set 84's 6.7 ms is a 12×12 figure and must not be quoted for this.** |
| **per frame** | two hubs (20 ms) + one `gfx_lock`/`gfx_unlock` pair (**1.94 ms**, PERFORMANCE.md:1304) = **~22 ms**. |
| **the ramp** | **28, 35, 44, 55, 69, 86, 108, 135 ms — 560 ms total.** Every interval clears the 22 ms of work, so the deceleration is real from the first frame; a ramp starting at 22 would be draw-bound at the top and what the user would see is a flat burst that then slows, which is exactly the constant-rate burst this section rejects. 8 × 22 = **176 ms of drawing inside a 560 ms coast** — 31% of the coast, **1.9% of the record**. |
| **hub radii** | **REFUSED.** A shrinking supply reel and a growing take-up would be three states each, 24 records = 1,584 bytes — and it has to be in the *record*, because `ICON_DRAW` is masked and a smaller disc drawn where a larger one was leaves the outer ring standing. Tape position is the progress bar's job; the reels are fixed. |
| **the body** | the cassette shell, window and labels are drawn **from primitives, on both kernels**, once at open and on every expose. See below. |
| **1bpp** | **no grey anywhere in the cassette.** Solid black on white: an outline circle, straight spokes, a filled hub. SPEC.md §39.4 — grey rounds to black on both 1bpp adapters, so a "dimmed" reel would be a black disc on the only machine that will ever run this. |
| **tape cost** | **zero.** The motor is off between records and the deck does not care. |

**A composed `OSAPI_GFX_BLIT1` band for the cassette body is REFUSED, and the
reason is the machine the whole architecture was chosen for.** On kern_small
that slot is `stc / ret` — `kernel/kernel.asm:6413`, *"kern_small carries the
SLOT and not the body"*, and `apps/os88api.inc:946` publishes the same thing to
packages: *"CF=1 = REFUSED and nothing drawn … TEST CF AND HAVE A SECOND
PATH"*. A band would leave the cassette **blank** on the 128–195 KB 5150 that
§1.2 spends its whole argument on. Fifteen `gfx_*` calls once per open is
~11–40 ms — a quarter of the fifteen-call title bar that ships on every window
today (40.0 ms, SPEC.md §39.3.2) — and it needs no buffer, no `.bss` and no
second arm. (CLAUDE.md also forbids quoting PERFORMANCE.md's 756 µs as a floor
a design must beat, which is how the band got justified in an earlier draft.)

**What paces the frames, and it is deliberately NOT `OSAPI_WM_TIMER`.**
`OSAPI_WM_TIMER` (0x0438) and `OSAPI_WM_ONDRAG` (0x0430) are **kern_big's
alone** — `apps/os88api.inc:2033-2041`: *"which answer CF = 1 on the kernel that
has neither"*. The coast therefore runs inside **one `W_ONWAKE` turn**, paced by
`apps/os88pit.inc`'s `pit_now` (838 ns units, latch plus both reads inside one
`pushf`/`cli`…`popf`). Three rules taken verbatim from SPEC.md §11.99.4:
**sample the deadline at the TOP of the frame** so the drawing is absorbed by
the wait rather than added to it; compare with `js`, not `jb` (two free-running
counters); and **miss a frame rather than chase one** — `cy_worker`'s shape
(`apps/cyclone/cyclone.asm:3981-4001`: *"chasing the deadline IS the judder"*).

**Every frame arms a clip, and the clip is the two 16×16 hub rects and nothing
else.** That is what keeps eight lock pairs a coast from being eight arrow
blinks: SPEC.md §7.1.4's hide is **deferred** and `wm_clip_set` spends it only
if the cursor is reachable, which measured **30 of 31 refreshes keeping the
pointer on screen** (PERFORMANCE.md:1300). A consequence to accept rather than
contradict: SPEC.md §25 clips `icon_draw` **whole-icon**, so a partly-covered
hub is skipped entirely rather than torn — correct, but it means a covered
window's reels stop, and the caption must not say otherwise.

The arrow tracks throughout the coast, because IRQ3/IRQ4 are unmasked between
records and the mouse ISR draws it. A Stop click landing inside the coast is
queued and honoured before the next record starts — **≤ 560 ms**.

### 7.3 Every draw burst is five calls, in this order

This design's `W_ONWAKE` handler paints from a wake with the lock unheld, which
is **exactly** the shape `apps/ftpd/ftpd.asm:1986-2010` carries a 25-line
correction for:

> *"**AND THE CLIP, WHICH WAS MISSING.** NOTHING has armed a clip for us …
> `wm_draw_win` KILLS the region before the title bar (`mov word [wm_clip_n],
> 0`) and never re-arms it … Without this the log lines are drawn straight over
> whatever window is on top, which is what the field saw (SPEC.md 77.33)."*

So, per coast frame and around the pre-freeze paint:

```
    OSAPI_WM_GEOM       ; jc -> not one pixel of us shows: skip, stay dirty
    OSAPI_GFX_LOCK
    OSAPI_WM_CLIP_SET   ; jc -> unlock and skip. The gfx_* primitives take
                        ;       ABSOLUTE screen coordinates
    ...draw...
    OSAPI_GFX_UNLOCK    ; the clip dies here; nothing to undo
```

`fd_paint_now`'s visibility bail before it even takes the lock is the model.
SPEC.md §20.6 rule 5 states the same discipline for the other lock-free context.

### 7.4 Text is `OSAPI_FONT_RUN`, everywhere, with no exceptions to register

CLAUDE.md's hard rule, and the one this project fails a build over. **Every
string this window draws goes through `OSAPI_FONT_RUN` (0x0258)**: the status
line, the block counter, the file/size line, the catalog rows, the button
captions, the refusal sentences and the footer. Not one transparent call site,
so `tests/textsites.txt` does not move — and that file's own header says why it
matters here in particular: *"A file NOT in this list may not call transparent
text at all — that is the case that matters, **because it is what a new package
hits**"*.

The one place transparency is *reasoned about* is the buttons, and it is
`os88ui.inc`'s existing answer rather than a new one: `OS88UI_FILL` on **every**
button, always, because `Go`'s caption becomes `Retry` and `Verify` and
`font_char` is transparent, so without the flag the second caption ORs on top of
the first. `OS88UI_DOWN` implies the fill; **`OS88UI_DIS` wins over both** — the
SDK names this design's exact case, *"a Stop button whose stream ended … a
greyed-down button would be a black box with a dithered caption in it."*

If any surface turns out to need transparency after all, it is registered in
`tests/textsites.txt` **with which of SPEC.md §6.6.2's six cases it is**, in the
same commit, and §15 wave 5 carries that or the build fails.

### 7.5 Buttons, and the three-edge gesture

`apps/os88ui.inc`, included **at the end of the source, immediately before
`OS88_BSS`** (the header and `OS88_ICON16` are at fixed image offsets).
**Geometry is a POINTER**: `BX` → a 4-word inclusive rect, so the drawn control
and the clickable control read the same four words and cannot drift. Buttons are
four contiguous 8-byte rects in one array, so `os88ui_bfind`
(`apps/os88ui.inc:931-953`) strides them and answers index+1.

| edge | what it does |
|---|---|
| `W_ONCLICK` | `os88ui_bfind` → `os88ui_arm` → `tp_setdown` draws the pressed look. **It does not act.** |
| `W_ONDRAG` (0x0430, **kern_big only**; `CF=1` on kern_small) | `os88ui_armed` *peeks*, re-finds, tracks down/off/down |
| `W_ONMOUSEUP` (0x01F0) | put it up **first and unconditionally**, then `os88ui_fire`, re-find; equal and non-zero fires, anything else is a cancel |

**No capability test on `W_ONDRAG`** — on kern_small the control still goes down
on the press and up on the release, which *is* SPEC.md §13.8.2's static fallback
(FTPD's own decision, `apps/ftpd/ftpd.asm:6960-7130`).

Two rules the tree paid for: **`[tp_down]` is what the PAINTERS read**, never a
flag threaded from the press, so a `W_PAINT` arriving mid-gesture draws the
pressed control pressed; and **`tp_setdown` is the ONE writer and returns having
drawn nothing if the answer did not change** — `W_ONDRAG` fires once per pointer
*movement*, so repainting each delivery is the flicker the down state exists to
prevent, arriving through the other door.

### 7.6 The greying table, Verify, and the cue-confirm

| state | Choose… | Go | Verify | Stop |
|---|---|---|---|---|
| no hardware (`[tp_hw] != TP_HW_OK`) | live | **grey** | **grey** | grey |
| another Tape window holds the deck | live | **grey** | **grey** | grey |
| idle, no file chosen (Save mode) | live | **grey** | **grey** | grey |
| idle, file chosen | live | live | live | grey |
| cueing or running | **grey** | **grey** | **grey** | **live** |
| **after ANY transient error** | live | **live**, captioned `Retry` | live | grey |

Greying is `OSAPI_GFX_PEN` (0x0310) taking the answer in `CF` — *"a call site is
`call <ok-test>` then `call gfx_pen_cf`"* — never `CDGRAY` by hand, which is the
bug this project fixed five separate times. `os88ui_btn` takes the pen once, in
one place, so SPEC.md §47 rule 1 stops being something to remember.

**Verify is a first-class BUTTON, not a menu item.** `AH=03` returns `AH=0`
unconditionally (`SUB AX,AX / RET`, PCBIOS.ASM:5399-5400), so running off the
end of the tape, a jammed deck, a disconnected cable, RECORD not engaged and a
perfect recording are the **same answer**. So:

- **the app never says "written."** It says: *"19 blocks sent. A write cannot
  tell whether the tape ran out — rewind and press Verify."*
- Verify is the read path with the commit replaced by a comparison: every block
  CRC (the BIOS's), every preamble field, `ckfile` over the assembled payload,
  then `ckfile` against a fresh CRC over the file **as it sits on disk** (raw,
  `READ_AT`) — so a pass proves *the tape holds this file*.
- It costs one more pass and writes nothing, and it is the default prompt after
  every write.

**The cue-confirm, before the motor starts, on every operation:**

```
PAPER.TEX - 19 blocks, about 3 minutes.
Wind the tape to a blank space, press RECORD and PLAY on the deck,
then press Go.                                        [ Go ]  [ Cancel ]
```

Not ceremony: **starting the relay without RECORD engaged wastes five minutes
and produces a blank tape that reads as a bug.** The read side is *"Wind to just
before the file, press PLAY, then press Go."*

### 7.7 The state machine, and the ordering of the pre-freeze paint

```
    TS_IDLE --Save/Verify--> TS_STAGE --> TS_CUE --Go--> TS_REC
        |  \--Load/Catalog------> TS_SNIFF --> TS_CUE --Go--> TS_SCAN
        |         |  no signal in 2 s
        |         +--> TS_ERR ("Press Play, check the cable...  [Load anyway]")
        ^
        |                              TS_COAST <---+  (8 frames, 560 ms;
        |                                   |          Stop lands here)
        |                                   v
        |                              TS_REC / TS_SCAN
        |                                   |
        +---- TS_DONE <-- ok ---- TS_FAIL <-+
              (toast, motor off,  (report + Retry; NOTHING was written)
               clock warning,
               "press Verify")
```

**One `W_ONWAKE` turn while a transfer is running:**

```
1. TS_COAST - 8 decelerating frames, 560 ms, geom/lock/clip per frame,
   [tp_stop] polled between them.

2. Check [tp_stop]. If set: int 15h AH=01, OSAPI_PIT_LEND AL=3, tidy, do NOT
   re-post.

3. DRAW THE FREEZE BEFORE IT HAPPENS, and DRAW ONLY WHAT CHANGED:
     a. geom / lock / clip
     b. advance the progress cell to THE BLOCK IN FLIGHT (::::::::) - one
        small gfx_fill, ~1 ms
     c. rewrite the TWO fixed-width numbers in "Block  4 of 19 - stopped for
        about  9 seconds" - four cells of font_run, ~3.6 ms. NOT the caption.
     d. unlock.                                     ~7 ms in total
   THE GREYING IS NOT HERE. Choose... , Go and the mode radios are greyed
   ONCE, at the TS_IDLE -> TS_REC/TS_SCAN transition. They do not change again
   until the transfer ends, so repainting them per record is ~50 ms and five
   visible control flickers x 34 - SPEC.md 77.17's rule ("a control whose look
   never changes gets no dirty bit") and PERFORMANCE.md's headline rule, both
   inside a loop that runs 34 times.
     e. RELEASE THE GFX LOCK                        <-- the part that matters

4. File-half work if this state has any (legal: W_ONWAKE is on the UI task and
   holds no lock).

5. ONE record through tp_xfer.                      <-- THE FREEZE

6. Advance the state; OSAPI_WM_WAKE to come back - or stop.
```

**Releasing the lock before the ROM call is not an optimisation, it is the
difference between two pictures.** `gfx_lock` hides the cursor for the length of
a hold, so holding it across the call would take the arrow off the screen for
nine seconds — **and a vanished pointer reads as a crash.** Released, the arrow
is **frozen but present**, over a screen that says exactly what is happening,
which reads as thinking. It costs nothing: nothing else can run during the call,
so the lock protects nothing. **The same reasoning is why §5.2 publishes
`OSAPI_COMPRESS` as callable without the lock** — a 3.2-second hold there would
hide the pointer for exactly the same reason, and the `OSAPI_FS_PROG` calls an
earlier draft justified it with are inert for this caller.

**Re-post only while there is work.** A handler that always re-posts spins the
UI task at ~1,400 wakes/s (SPEC.md §74.1).

**`OSAPI_WM_ONCLOSE` (0x0468)** is called for every way of closing the window,
on the UI task with the lock held. It calls `int 15h AH=01` **unconditionally**
— the motor is a relay on the user's deck — releases the PIT claim, restores the
IMR if a record was somehow in flight, and frees the claims. It answers `CF=0`,
but refuses mid-transfer with a toast (`Stop the tape first`), because a claim
handed to the ROM cannot be freed while the ROM is in it. **It is not called on
a Restart** — §3.7.

### 7.8 A second instance, and what it would do if nothing stopped it

Packages are multi-instance by default. Two Tape windows share one deck, one
port-B motor bit, one PIC mask and one PIT ch0 — and **between A's records the
machine is fully alive**, so B's `W_ONWAKE` can start its own record: B's motor
off lands inside A's operation, B's records interleave into A's tape, and A's
write **cannot report any of it** because `AH=03` returns `SUB AX,AX / RET`.
That is the silent-and-permanent failure class §3.3's whole IRQ1 rule is built
around, arriving through a door an earlier draft never checked. The read side
catches it (§8 check 13: `seq` must be exactly the next value); the write side
cannot.

**§5.1's claim is the guard, and it needs no new mechanism:**
`OSAPI_PIT_LEND AL=2` is taken for the whole operation and answers `AH=3`
(*somebody already holds it*) to the second window, which refuses in words and
greys Go (§7.6 row 2). `tests/tapesim.py` launches two and asserts the second
refuses.

### 7.9 What Stop does, precisely, at each moment

| when | what happens | what the user sees |
|---|---|---|
| idle | greyed | — |
| during the coast (≤ 560 ms) | latched; the transfer parks before the next record | the reels stop mid-coast; `Stopped after block 4 of 19.` |
| **mid-record, mouse** | **nothing — the click is physically lost.** IRQ3/4 are masked, the 8250 is one byte deep with no FIFO, and the button state is *in* the dropped packets | which is why the footer says `Stop takes effect at the end of the block` |
| **mid-record, Ctrl+Break, READ** | the ROM bails within ~5 loop iterations | back in about a second, `AH=04` |
| **mid-record, WRITE** | nothing at all — neither ROM's write path has a break test | up to 8.8 s, and the footer said so |
| after a stop, on a READ | nothing partial ever reached the disk | `Stopped. Nothing was written to B:.` |
| after a stop, on a WRITE | **a partial file is on the tape** | `4 of 19 blocks are on the tape. It cannot be read back.` |

`mou_isr` resyncs automatically on the bit-6 packet header
(`kernel/mouse.inc:3053-3060`), so the arrow catches up at the next whole packet
and nothing needs draining.

### 7.10 Reading: Catalog, Load, and how a bad read reads

A tape has no directory and there is **no seek**. The reader is a **scanner**,
which is what every prior-art system converged on (the C64's `FOUND <name>`, the
Spectrum's `Program: <name>`), and what the machine genuinely adds over
5150CAXX's answer (*"be sure you note down this value and your current tape
position"*) is that **the scan NAMES what goes past.**

**Catalog** — repeated `AH=02` with `CX = 256`, one block, buffer zeroed before
each:

```
'O8TP' -> a header. Validate (8). List name / size / usize.
'OT'   -> a body. "...PAPER.TEX part 3 of 19 went by" - we joined mid-file.
0xA5   -> an IBM Cassette BASIC record. Print its 8-character name.
other  -> "unknown record".
AH=04  -> end of tape, or nothing playing.
TS_COAST between every one of them.
```

**Never scan with `CX` > 256.** A larger read consumes and CRC-checks a whole
record you may not want, at 1.5 s a block, and a dirty block in a file you were
skipping would end the scan with `AH=01`.

**Load** — scan for the next `'O8TP'` whose name matches; validate;
`OSAPI_FILE_DFREE` **once**, banked; refuse if free < `size` **before a single
body record is read**; then `nrec` reads at the declared lengths; assemble;
check `ckfile`; **one** `OSAPI_FILE_WRITE`, asking before replacing.

**Skipping under program control is refused and the window says so.** A
19-record file is 20 calls at ~3.7 s each — **74 seconds of frozen machine** —
which is worse than telling the user to press Fast Forward. **The deck answers
"the third file on the tape"; the software does not.**

**A failed read:**

```
   PAPER.TEX                       18,704 bytes  (30,112 unpacked)
   [########|########|########|!!!!!!!!|        |        |        ]
   Block  4 of 19  -  CRC error - the block was recovered but is damaged

   Rewind to just before the file and press Retry.  Nothing has been
   written to B:.

   [ Choose... ]   [   Retry   ]   [  Verify  ]   [  Stop  ]
```

`AH=1` and `AH=2` are **different sentences**, because they mean different
things to the user's hands:

- `AH=1` → *"CRC error — the block was recovered but is damaged."*
- `AH=2` → *"Bad signal — check the volume and the head."*
- `AH=4` → *"No more data. That is the end of the tape, or nothing is
  playing."*

---

## 8. Hostile input — 29 checks, every field a tape can lie about

SPEC.md §19's rule is that every byte off a disk is hostile. A tape is worse in
three specific ways: **nobody but us has ever written one**, there is no mount to
validate it, and **a mis-synced read delivers somebody else's data with a VALID
CRC.**

### 8.1 The header record

| # | field | what a bad tape can do | the check |
|---:|---|---|---|
| 1 | `magic` | any four bytes | exact compare with `'O8TP'`. Anything else is *not a header*: name it and keep scanning. |
| 2 | `ver` | claim a future version | **exact** equality with 1. Refuse, never guess. |
| 3 | `kind` | anything | exact equality with 0. |
| 4 | `flags` | set reserved bits | bits 3–7 **must be zero**; bit 2 meaningless unless bit 0. An unknown format bit refuses *before* a file nothing on the machine can open is created. |
| 5 | `recblk` | 0, or 200 | `1 <= recblk <= 16`, **and** `5 × recblk × 256` must fit the claim (§4.5). A mismatch with this reader's default is **not** an error — that is what the field is for. |
| 6 | `nrec` | 0, 255, or a lie | `>= 1`, **and exactly** `ceil(size / (recblk*256 − 8))`. A lie here sends the reader hunting for records that do not exist — minutes of frozen machine per phantom record. |
| 7 | `lastblk` | 0, or > recblk, or inconsistent | `1 <= lastblk <= recblk`, **and exactly** `ceil((size − (nrec−1)*(recblk*256 − 8) + 8) / 256)`. |
| 8 | `name` | no NUL in 12; control bytes; `.`; `..`; a path | a NUL within 12; every byte before it in `0x21..0x7E`; then hand the string to `OSAPI_FILE_WRITE` and let **`dskw_name83`** (`kernel/diskw.inc:3697`) be the **single** validator — it rejects an empty stem, a leading dot, a second dot, a 9th stem character, a 4th extension character and every illegal symbol, answering `FERR_NAME`. **Do NOT substitute `'_'` the way §19.1's *display* path does** — substituting on a *write* silently targets a different file. |
| 9 | `size` | 0; `0xFFFFFFFF`; larger than the claim or the volume | `1 <= size <= TP_MAXFILE`; `<= OSAPI_MEM_AVAIL`'s largest run minus the record slack; `<= OSAPI_FILE_DFREE` (asked once, before the first body record). |
| 10 | `usize` | anything | **never sizes anything.** Display only. |
| 11 | the 224 pad bytes | anything | **not read.** Do not "reserve for future use" by reading them. |

### 8.2 The body records

| # | check |
|---:|---|
| 12 | the two magics differ by construction; test both ways |
| 13 | `seq` must equal **exactly** the next expected value — not "in range". This is also the read side's guard against §7.8's second instance. |
| 14 | `nrec` must equal the header's, exactly |
| 15 | `ckfile` must equal the header's, exactly — this is what rejects a spliced record **on arrival** rather than at the end |
| 16 | `1 <= paylen <= (this record's blocks × 256 − 8)` |
| 17 | the running total must never exceed `size` — checked **before** each copy |
| 18 | the total must equal `size` exactly at `seq == nrec` |
| 19 | `CRC-16(payload) == ckfile` — the backstop, before a byte reaches the disk |

### 8.3 The payload, on its way to the disk

| # | check |
|---:|---|
| 20 | **when flags bit 0 is set**, the `'CZ'` container's own fields: `word[+0] == 0x5A43`, `byte[+3] == 0`, `byte[+2] <= 1`, `dword[+4] >= size − 8` and `<= 16 MB`. **Ten bytes of code, and it is NOT decoded to prove it** — the whole-file CRC has already proved the bytes are bit-identical to what was written. |
| 21 | a `.o88` / `.DRV` / `.OVL` is **never** wrapped in `'CZ'`, on either leg — SPEC.md §22.22.1: it would make a file `ld_check_hdr` cannot start. An explicit refusal, not a consequence of check 20. |
| **29** | **NEW, and it is the one an earlier draft's table was blind to.** `dskw_czstamp` (`kernel/diskw.inc:2966-2996`) derives the compression hint from the first eight bytes of **every** whole-file write, unconditionally: `cmp word [es:bx], DSK_CZ_MAG` then `cmp al, LZ_LZB / ja .out`, and *"a size that does not fit, or is no bigger than the file, is stamped as it comes: the READ refuses either as `FERR_IO`"*. So a tape record with flags bit 0 **CLEAR** whose payload merely *begins* `43 5A xx 00` passes all 28 checks above, is written by `OSAPI_FILE_WRITE`, and **is stamped compressed on the volume** — after which every read of that file answers `FERR_IO` or expands garbage. **The check: if the payload's first word is `DSK_CZ_MAG` and `byte[+2] <= 1`, then flags bit 0 MUST be set and row 20 must pass; otherwise refuse the file rather than writing it.** One compare, and trivially testable host-side — a `tapehostile` image whose payload is `43 5A 00 00 …` with `flags = 0`. |

### 8.4 The BIOS's own traps

| # | trap | the rule |
|---:|---|---|
| 22 | **`DX`, not `CX` — and `DX` is meaningless unless `AH=0`. The two ROMs disagree, which is the whole reason for the rule.** GLaBIOS returns `DX = the original CX` on a no-leader failure (`POP DX / SUB DX,CX` at GLABIOS.ASM:11814-11815 with CX zeroed by `JCXZ CAS_READ_ERR` at :11699), which is where the measured `DX = 0x0100` for a 256-byte request comes from. IBM **zeroes** it: `SUB DX,DX ; ZERO NUMBER OF BYTES READ` at W17, PCBIOS.ASM:5202 — and on a partial error returns a meaningful count from W15's `POP DX / SUB DX,CX` (:5184-5185) | require `AH=0 && DX==CX`; never touch a byte past `DX` |
| 22a | **`BX` is the third post-condition and it is what catches §4.5's GLaBIOS retry.** `MOV BX,DI` at GLABIOS.ASM:11816; IBM's own comment at PCBIOS.ASM:5093 is *"BX POINTS 1 BYTE PAST LAST BYTE PUT IN MEM"* | with `BX = 0` on entry, require `BX == CX` as well |
| 23 | **A stale buffer.** A short or failed read leaves the previous record's bytes in place, and they will pass a magic check | **zero the record buffer before every `AH=02`.** Mandatory. |
| 24 | **The pad.** IBM's pad byte is `ES:[buffer + CX]` — **memory past the caller's buffer**, written to removable media up to 255 times (PCBIOS.ASM:5353-5357). GLaBIOS repeats the last data byte (:11506-11511) | **every `CX` is a multiple of 256, so neither pad is ever entered** (§4.1). This is a security property, not only a determinism one. Ignore everything past `paylen`; never infer a length from the tape |
| 25 | **`AH=03` always returns 0** | never say "written" on the strength of `AH`. §7.6. |
| 26 | **CF, never AH, for an unsupported call** — IBM answers `80h`, GLaBIOS `86h` | §2.1 gate 2 |
| 27 | **`BX + CX` must not exceed 65,536** — the inner loops `INC BX` with no segment fixup and wrap silently inside the segment | the buffer is a claim base with `BX = 0`, satisfied by construction (§6.5) |
| 28 | **The motor is a relay on someone's tape deck, and the tape names its own destination.** `AH=01` on every exit path including refusals — with the one exception §3.7 states, a Restart, which reaches no package at all. And `OSAPI_FILE_WRITE` replaces silently, so **ask before replacing**, and write only into the acting Disk window's folder. A hidden+system target is already refused twice over — §19's species filter keeps them out of listings and `dskw_write_x` answers `FERR_PROT` — which is §22.22.1's *"two independent gates, neither of them a name list"* arriving for free |

**For the record, one thing 5150CAXX does NOT do**, corrected from an earlier
draft: it does not print a byte count beside an `AH=04`. `CheckForErrors`'s
`case 4` arm calls `Quit(EXIT_FAILURE)` (5150CAXX.H:809-811) before
`DoOperation` reaches its *"%u out of %u bytes read successfully"* line (:980).
Its real weakness is the other two: `AH=1` and `AH=2` fall through and the
partial count is then printed **as "read successfully"**.

---

## 9. The byte budget

### 9.1 Resident kernel, against the live tree

`python3 tools/kernsize.py --build build`, run this session:

```
sections   text 50,676  bss 5,959  cold 38,059  lowbss 9,182  vgabuf 848
rungs      image 56,832 (197 left)   cold 38,400 (341 left)   low 9,728 (34 left)
accrued    image 315/512 (61%)   cold 171/512 (33%)
footprint  KERN_SIZE 110,592 of KERN_BUDGET 129,536 -> 18,944 spare (37 steps)
segment    .text+.bss 56,635 of KERN_CODE_MAX 65,536 -> 8,901 left
```

| item | `.text` | `.bss` | `.cold` |
|---|---:|---:|---:|
| `OSAPI_COMPRESS` (§5.2): cell 8 + stub 6 | 14 | 0 | ~55 |
| `OSAPI_PIT_LEND` (§5.1): cell 8 + stub 6 | 14 | 0 | ~95 |
| `[sch_pitbios]` | | 1 | |
| `sch_fast_on`, `sch_account`, `spk_tone`/`spk_pcm_start` guards | 18 | | |
| **TOTAL** | **46** | **1** | **~150** |

**Sum +197.** After: `.text` 50,722, `.bss` 5,960, `.cold` ~38,209. Image accrued
**315/512 → 362/512**; cold accrued **171/512 → 321/512**. Segment
**56,635 → 56,682 of 65,536 → 8,854 left.**

**No rung is crossed** — the image rung has 197 bytes left against 47 spent, the
cold rung 341 against 150 — and per CLAUDE.md **that is not a claim that it is
free**: 197 bytes is 197 bytes of slack spent that belongs to whoever comes next,
and the guard will bill them the whole 512. **Of it, 47 land in
`KERN_CODE_MAX`, the guard that cannot be raised**, and 47 is the number §16
row 1 asks the user about.

Compare: a `TAPE.DRV` would have cost **129 resident, 89 of them in the binding
guard**, and excluded kern_small — and it would still have needed
`OSAPI_PIT_LEND`, because §34.1 binds a driver exactly as it binds a package.

`CLONE.DRV`: **+~60 bytes of module image, 0 resident, no new `mod_fp` slot**
(§5.2). kern_small: identical, because it carries `CLONE.DRV` too
(`SMALLDRIVERS = $(KMODS)`, `Makefile:7151`).

### 9.2 The package

| part | bytes |
|---|---:|
| header, icon, About (`OSAPI_ABOUT_SET`, SPEC.md §12.2) | 300 |
| window creation, `OS88_PREFER`, `WM_GEOM`-driven layout, `W_PAINT` | 1,100 |
| the cassette shell drawn from primitives (~15 `gfx_*` calls + coordinates) | 350 |
| 8-phase hub table — 8 × 66 (`ICO_STAGE_SZ`, `kernel/icons.inc:51`) | 528 |
| `os88ui.inc` (button + glyph + bfind + the three-edge gesture) | 1,400 |
| the state machine (Save / Load / Catalog / Verify / Retry) | 1,400 |
| format build and parse + the 29 checks of §8 | 950 |
| CRC-16 | 60 |
| transport: `int 15h`, the IMR bracket, the `PIT_LEND` calls, the sniff, the motor wait | 420 |
| catalog list and its strings | 800 |
| file I/O glue (`FIND_RAW`, `READ_AT`, `WRITE`, `DFREE`, the dialog, compression) | 700 |
| refusal strings, status/time/number formatting, the standing sentences | 1,300 |
| **image ≈ 9,308; bss ≈ 420 (state + resolved rects + the staging pointers)** | |
| **on disk, lz4-packed at ~80%** | **≈ 7,450** |

Budget **≤ 9,000 packed**, against `APP_MAX_SIZE` = 0xF000 = 61,440 for image +
bss (`apps/os88api.inc:93`) — a factor of six of headroom. Comparable packed
sizes: `telnet.o88` 3,998, `calc.o88` 5,289, `ftpd.o88` 12,713.

**There is no band buffer in this budget and that is deliberate** (§7.2): a
1bpp cassette panel of 288 × 56 would be 2,016 bytes that must survive an
expose, so `.bss` or a claim — and it would draw nothing at all on kern_small.

Runtime heap: **one pinned claim of `(payloadKB + 5) KB`** (§6.5), sized from
`OSAPI_MEM_AVAIL` (never `int 12h`), floor 6 KB or the app refuses with the
arithmetic; a 2 KB scan claim; plus `OSAPI_COMPRESS`'s transient **11–41 KB of
tables**, freed before the motor starts.

### 9.3 The disk — and the placement decision, with the count

Measured this session by walking the FAT of every shipped image:

| image | cluster | free clusters | free bytes |
|---|---:|---:|---:|
| `os8088.img` (1.44 MB system) | 512 | 2,353 | 1,204,736 |
| `os8088-120.img` (1.2 MB) | 512 | 1,877 | 961,024 |
| `os8088-720.img` (720 KB) | 1,024 | 459 | 470,016 |
| **`os8088-360.img` (360 KB system)** | 1,024 | **100** | **102,400** |
| `apps.img` (1.44 MB) | 512 | 2,194 | 1,123,328 |
| `apps120.img` | 512 | 1,718 | 879,616 |
| `apps720.img` | 1,024 | 377 | 386,048 |
| **`apps360.img` (360 KB apps)** | 1,024 | **27** | **27,648** |

**`TAPE.O88` ships in `SYSTEM/` on the SYSTEM disk, not on the apps disk.** The
5150 is a 360 KB machine, and at that geometry ~8 clusters are **8% of the
system disk's 100** and **30% of the apps disk's 27**. It is also right on the
merits: a tool that drives the machine's own hardware belongs beside the Task
Manager (SPEC.md §28.3). Plus one directory slot.

| geometry | `TAPE.O88` ≈ 7,450 B | cost on the system disk |
|---|---:|---|
| 1.44 MB | 15 clusters | 15 of 2,353 (0.6%) |
| 1.2 MB | 15 | 15 of 1,877 (0.8%) |
| 720 KB | 8 | 8 of 459 (1.7%) |
| **360 KB** | **8** | **8 of 100 (8.0%)** |

**Not on the kern_small disks?** It *is* — that is the point of §1.2. It reaches
no driver, so SPEC.md §24.5's requirement filter does not exclude it, and it
refuses itself honestly on a small heap (§6.5's per-kernel ceiling) rather than
needing a second build. `make smallapps` needs no small arm.

**The ceiling is ~100 free clusters on `os8088-360.img` — about 100 KB, not
18 KB**, and it is *today's* figure, shared with everything else that lands on
that disk. If the package ever approaches it the answer is an explicit `%if` in
the Makefile with a stated reason, **not a silent overflow** — the four gates
that walk "every shipped image" (`t_image`, `t_diskverify`, `t_canary`,
`t_blobruns`) each hold their own list.

---

## 10. The test plan

### 10.1 The seam, and why it is a package build

**No emulator in this project can host a cassette read.** MartyPC's PPI returns
a hardwired `0` for the data line when the motor is on
(`build/martypc/src/crates/marty_core/src/devices/ppi.rs:856-864`,
`// TODO: Implement cassette data input`). QEMU has no XT-class machine and
SeaBIOS dispatches no `AH=00..03`. 86Box models a cassette on
`ibmpc`/`ibmpc82`/`ibmpcjr` but has no debugger and no automation socket, and no
`vm/` profile here is a 5150.

**Cassette belongs on CLAUDE.md's closed list as entry 8 — and it is the first
entry with no QEMU fallback either.**

The transport is therefore behind a **source seam**, and the seam is a **second
package build**, not a kernel knob:

```
apps/tape/tapexfr.inc      the int 15h transport   -> TAPE.O88   (ships)
tests/tapesim/tapesim.asm  %includes tapefmt.inc, tapeui.inc and a MEMORY
                           transport of the same shape, built with
                           -DTAPE_FAKE   -> build/tapefake.o88
                           (make bench, never shipped)
```

Shared as **source**, never as a copy — WEAVE-SPEC §1.2's rule,
`apps/weave/wfxc.c`'s shape. It costs the kernel nothing, adds no `$(KNOBS)`
entry, and `tests/unit/t_buildmatrix.py` never sees it. **This is strictly
better than a `TAPEFAKE=` kernel knob**, which would cost a `$(KNOBS)` name, a
`$(VIDSTAMP)` entry, a **mandatory** `t_buildmatrix.py` row and one extra kernel
assembly inside the `full` tier's 180-second `buildmatrix` row — for a seam that
is not in the kernel at all.

It is honest on this tree's own precedent, and the precedent is exact:
`FDDABSENT=1` *"forces the verdict for unit 1 with no port touched, so the
**decision** is testable here while the **conversation** stays the 5150's."* Its
dishonest twin would be a build that made the *shipped* path look like it
worked — **and `tapehw` is the guard against exactly that, once its assertions
are about something a ROM does not already provide (§10.2).**

### 10.2 The rows

Measured this session on a 4-core box: **`fast` is 53 registered rows declaring
251.7 s and finishing in 20.2 s of wall clock against a 30 s ceiling** — the
ceiling is enforced on `wall = time.time() - t0` (`tools/os88test.py:605-616`),
not on the declared sum, and the lane fans out. So the honest statement is
**~9.8 s of wall headroom**, and two new fast rows add roughly `secs / cores`
to it. **`full` is 12 rows declaring 658.0 s** — already over its 600 s ceiling
*in declarations* and comfortably inside it in the only unit that is enforced.
**Nothing here goes in `full`.**

Every row that opens an artefact `make all` does not build **declares it with
`wants=`**, because `tests/suite.py`'s own header records what skipping that
costs: *"eleven images under tests/ had a Makefile rule, no builder, and a row
that died on FileNotFoundError several frames from the cause"* (`:76-91`). The
precedent shape is `wants=("build/mseg360.img",)` at `:992`.

| row | tier | secs | needs / wants | what it asserts | **break it on purpose** |
|---|---|---:|---|---|---|
| `tapefmt` | fast | 5 | — | `tools/os88tape.py` round-trips the awkward corpus (empty, 1, 255, 256, 257, 1016, 1017, **9,000**, **18,704**, 32,767, 32,768, all-`00`, all-`FF`, a payload containing **32 consecutive `FF`**, a payload whose CRC complement contains `0x16`, and a payload beginning `43 5A 00 00`). Every §3.5 and §6.3 figure is **printed by `--selfcheck`, not typed**. **Plus TWO hand-computed reference streams compared BIT FOR BIT**, one per ROM: 256 zero bytes is `1 + 2048 + 1 + 8 + 2064 + 32 = 4154` bits from GLaBIOS and **4153** from IBM (no start bit, §4.1); leader at bits 1..2048 / 0..2047; sync byte `00010110`; receiver residue `0x1D0F`. And every layout constant mirrored against `apps/tape/tapefmt.inc` (`t_mirror`'s shape) | change the CRC preset to `0x0000` → the residue assertion reddens. Flip the bit order in the packer → the **sync-byte** assertion reddens **while the round trip still passes**, which is why the reference streams are there. Drop `--rom` and hold one golden → one of the two ROM arms reddens |
| `tapedet` | fast | 5 | — | the two-gate predicate against a **committed fixture** under `tests/`: the model byte and the five discriminating bytes at `F000:F859` for each of the thirteen GLaBIOS ROMs and both IBM revisions, plus the negative cases `FE`, `FB`, `FC`, `FD`, `00`. **Asserts the corpus size first** (`assert len(rows) >= 15`), the way `_kernel_sources()` asserts `len(src) >= 30` for the same reason | point the gate at the model byte alone → **the three `FF`-with-no-cassette rows redden** (`0.2.5_8PC`, `0.2.6_8PC`, `0.4.0_8PC`). This is the row that would have caught the trap before it cost a session |
| `tapedetsweep` | soak | 20 | needs `marty` | walk **every** ROM actually present in `build/martypc/run/media/roms/GLaBIOS/` and assert the fixture still describes them, so a new upstream ROM set is caught | add a ROM to the tree and not to the fixture → red. **Split out of `tapedet` because that directory is staged only by `make marty`** (`tools/martypc/build.sh:76-80`) and `build/` is gitignored, so a fast row that walked it would report `ok` in 0.0 s on every stock tree — `dispcp`/`mkclick` exactly (docs/WRITING-TESTS.md §1) |
| `tapesim` | soak | 150 | needs `marty`; wants `build/tapefake360.img` | `-DTAPE_FAKE`: open; greying in all six states; Choose; the estimate; the cue-confirm; Save; the record loop; Stop mid-coast; the produced stream read back on the host with `os88tape.py` and compared **byte for byte**; then Load it back and diff the file. **Launch a SECOND instance and assert it refuses in words** (§7.8). **The animation direction is asserted on the PHASE BYTE, not on a call count**: sample `[tp_phase]` in the package's bss across a coast (`tests/paintanchor.py:53-59,120-125` is the worked example for reaching package bss through `pkg_seg` + a map offset) and require the sequence **strictly increasing mod 8 on Save and strictly decreasing on Load** | **reverse the phase table on purpose → red.** `bp_count` cannot do this: it returns `len(seen)`, deduped on the guest instruction count (`tools/os88marty.py:2279-2332`), so "forward count > 0" and "backward count > 0" are the same assertion written twice and swapping Save and Load leaves all three numbers unchanged |
| `tapehostile` | soak | 120 | needs `marty`; wants the fixture disk | **one malformed tape image PER CHECK, 29 of them, built by `tools/os88tape.py` at make time and carried ON the fixture disk** — not generated at row time. Each asserts that **its own check fires, names itself, and that NO FILE IS CREATED** | **delete any single check → exactly one image reddens.** That is the property the row exists to have; a suite of checks with no per-check image proves none of them is live. Check 29's image is the one whose payload is `43 5A 00 00 …` with `flags = 0` |
| `tapecomp` | soak | 90 | needs `marty`; wants the fixture disk | the compression contract on the machine, `tests/lzcomp.py`'s shape: break on the transport entry and read `ES:BX`/`CX` — a **plain** source must hand over the compressor's output with an 8-byte `'CZ'` header; a source already `'CZ'` must hand over bytes **byte-identical** to the file on disk; a `.o88` is **never** wrapped. Assert `OSAPI_CMP_NOGAIN` on a second pass. **And measure `cmz_pack`'s actual cycles per byte on a 16 KB file off MartyPC's counter** — the number the whole CPU-versus-tape trade rests on and which nobody has ever taken. **Also run one leg on `os8088_5150_cga_128k`** (already in `tools/martypc/configs/os8088_machines.toml`) so `OSAPI_CMP_NOMEM`'s refusal has a test at all | make the writer unwrap-and-rewrap a `'CZ'` file → the two buffers differ. Raise `CMZ_WMIN` above what the 128 KB machine can fund → the NOMEM leg reddens |
| `tapehw` | soak, `alone=True` | 180 | needs `marty`; wants the `_cas` twin | **THE SHIPPED ARM**, on `os8088_5150_cga_cas` (§10.3). One real `int 15h AH=03` of 1,016 bytes. **The assertions are about things no ROM here provides**: (a) at a breakpoint on the instruction after step 5's `out 0x21`, the IMR **value written** — a value assertion, which dies if the mask constant changes; (b) **IRQ3 and IRQ4 are masked** — inject serial mouse packets during the record and assert **none is delivered**; (c) the IMR is restored **before** the `AH=01`, read at a breakpoint between steps 12 and 14; (d) port 61h bits 0/1 came back **clear**, not banked; (e) PIT ch0's mode is 2 again after the call, read through the cell's own leave path; (f) port 61h bit 3 at `ui_rb_go`/`dsk_rb_go` with a transfer armed, `tests/fddpark.py`'s shape, documenting §3.7's Restart exposure rather than asserting it away | **delete `or al, 0x18` → (b) reddens.** That is a real positive control. **The IRQ0 half is deliberately NOT asserted and the row's `why` says so**: GLaBIOS masks IRQ0 itself in `CAS_MOTOR_WAIT` (:11394-11398) for both directions, so "`ticks` does not advance across a record" is true with our whole bracket deleted, and a row asserting it would be green either way — docs/WRITING-TESTS.md §1's exact failure. The one ROM where it is load-bearing is IBM's `AH=03`, which §10.4 says is unreachable here |
| `taperefuse` | soak | 60 | needs `marty` | on the **default** `_gla` twin (`8PC`, no cassette BIOS): the window opens, Save/Load/Verify are dithered, the status line names **gate 2**, and no port was touched. Then on the `_cas` twin: the **2-second sniff** refuses in ~2 s and not ~90 — **and asserts the port and the mask**, that the poll reads `0x62` with `0x10`, at a breakpoint. Then `Load anyway` proceeds | remove gate 2 → the buttons come up live and the first Load costs 90 seconds. Change the poll to bit 5 → the port/mask assertion reddens, where the elapsed-time assertion alone would not: **only the negative branch of the sniff is testable anywhere in this project** (§2.3), so the row must assert the mechanism and not the outcome |
| `tapequantum` | soak | 90 | needs `marty` | build with `QUANTUM=2` into a private tree (`tools/os88build.py`, never the shared `build/`), boot, arm a transfer, and assert **`OSAPI_PIT_LEND AL=2` refuses with `AH=1`** and the app says so — then assert `[sch_fast]` is still 2 and the delivered tick rate still agrees with it | make the cell restore divisor 0 blind instead of refusing → the tick rate halves and the row reddens. This is the row for §5.1's whole reason for existing |

Waits use `os88marty.until(..., guest=N)` on the package's own state byte,
**never `time.sleep`** — a loaded box hands the guest ~37% less work and a sleep
fails looking like the thing under test (SOAK-PARALLEL §1).
`os88marty.quiesce()` on the state bytes rather than the framebuffer wherever
the assertion is about state.

**Both fast rows declare 5 s deliberately.** The runner's UNDERRAN guard is
`res.row.secs >= 5.0` (`tools/os88test.py:568`), so a row declared at 1 s sits
in a blind spot by construction — which is precisely how a row that walks an
absent directory reports `ok` in 0.0 s for ever.

### 10.3 One new MartyPC twin, asserted by CONTENT

```toml
[[machine]]
name = "os8088_5150_cga_cas"
type = "Ibm5150v256K"
rom_set = "glabios_pc_0.2.6"     # GLABIOS_0.2.6_8P.ROM - CASSETTE = 1
```

Verified bootable: banner `GLaBIOS`, reset date `06/16/24`, model `FF`,
`F000:F859` = `FB 80 FC 03 76 09 …` (`STI / CMP AH,3 / JBE`), and os8088 settles
to a desktop.

**Correction to an earlier draft: `tests/unit/t_machines.py` needs no
teaching.** Its check 3 iterates `os88marty.IBM_TWIN` only
(`tests/unit/t_machines.py:160-176`), whose four entries are the IBM→GLaBIOS
pairs (`tools/os88marty.py:1505-1510`); `os8088_5150_cga_cas` is not in it, so
nothing compares it to anything. Check 1 (the machine exists in the TOML) and
check 2 (no test names an IBM romset) are both satisfied as written.

**The real risk is the mirror image, and it is what the rows must guard
against.** A `_cas` machine outside `IBM_TWIN` is covered by nothing and may
drift from `os8088_5150_cga_gla` in more than `rom_set`; `os88marty.assert_rom`
decides IBM-vs-GLaBIOS off the banner at `0xFE001`
(`tools/os88marty.py:1551-1580`) and **cannot distinguish `8P` from `8PC`** —
both say `GLaBIOS`; and the `glabios_pc` alias is defined **twice** in
`build/martypc/run/configs/rom_definitions/romdef_glabios.toml` (priority 2 →
`0.2.6_8PC` at `:58`, priority 4 → `0.4.0_8PC` at `:131`), so which ROM the
default twin boots is a precedence question no test here settles. **So
`tapehw` and `taperefuse` assert the ROM by CONTENT**: read `F000:F859` and
require `FB 80 FC 03 76` on the `_cas` machine and `FB B4 86` on the default
twin. Two lines, and immune to both the alias precedence and a silent romset
fallback.

### 10.4 What cannot be tested here, stated so nobody assumes otherwise

- **A cassette read, on any instrument in this project.** MartyPC returns 0;
  QEMU has no 5150; 86Box needs an `ibmpc82` profile and a ROM CONTRIBUTING §6
  keeps out of the tree, and would give a *look*, not an assertion.
- **The positive branch of the sniff** — nothing here can make the data line
  change (§2.3).
- **The mode-3 fix (§0.1, §0.2).** MartyPC's read fails before the thresholds
  are reached, so the fix that makes reads possible on iron has **no emulator
  gate**. It is derived from the IBM listing and from GLaBIOS's independent
  agreement, and it goes to the field behind `TAPEMODE2=1`.
- **The IRQ0 half of the mask bracket**, because GLaBIOS does it itself and IBM
  is unreachable (§10.2, `tapehw`).
- **Whether the bits land on tape, and at what error rate.** Field only.

---

## 11. What is refused, and why

1. **A driver reachable from the file manager.** Not a byte question — a fact
   about the ABI twice over. `FMC_OPEN..FMC_PASTEIN`, `FMC_COUNT = 26`, a
   26-word `fm_jmp` and four fixed menus (`kernel/files.inc:3883-4006`) with
   **no extension point a driver can publish into**; and
   `drivers/os88drv.inc:34-36`.
2. **`TAPE.DRV`.** §1.2. 129 resident bytes, 89 of them in the binding guard, to
   *remove* the 128–195 KB 5150 — and it would still need §5.1's cell.
3. **A `DRVC_TAPE = 6` class.** Falls with the driver. (For the record: 6 is
   free; **3 is RETIRED, not free** — a class number is ABI.)
4. **A `File ▸ Tape…` menu item.** 109 bytes as built, and it fits 200 — and it
   costs the **last free slot in the File menu** for an item permanently greyed
   on every machine that is not a 5150. §1.1, §12.1.
5. **Tape as a drive letter (`DRVC_FILE`/`DVK_FILE`).** Refused by the ABI, not
   by taste, on five facts: `disk_mount`'s `.fsmount` path calls `FSV_CHDIR`
   then `FSV_LIST` inside **one far call with the gfx lock held and nothing else
   running** (`kernel/disk.inc:3190-3234`, and `:2412-2418` states the fence) —
   mounting means playing the whole tape at 168 B/s before the Disk window paints
   a row; `FSV_ENUM`'s ordinal must be dense **and stable across calls in which
   the kernel writes on another volume** (SPEC.md §62.9.1), and re-walking to
   ordinal *k* on a tape means rewinding, between which the user's hand has been
   on the transport; `FSV_STAT` resolves a name synchronously, i.e. minutes;
   `FSV_DFREE` has no answer; and a Refresh re-lists. A drive letter also
   *asserts* browsability, and a tape is a queue you play.
6. **A Control Panel page.** The item list is 9 of 9 (`CP_ITEMS` 6 + a
   hand-written 3), `CP_CH` cannot grow (CGA is 200 rows, `kernel/ctrl.inc:60-67`),
   SPEC.md §31.1's answer (a scrolling item list) does not exist, a page cannot
   animate, and every callback runs with the lock **held**.
7. **A background worker, and fsx.** §1.3. And `fsx_run` calls
   `inst_pkg_fence`, which needs an owning instance and `KIND_PKG`; for a
   package fsx freezes every other task for the whole bracket, which is the
   opposite of the requirement.
8. **A replacement `int 09h` in the package, to catch Esc mid-record.** Refused
   on four grounds, and the first is decisive. **(a)** It buys Esc on the
   direction where Ctrl+Break already works and on the direction where it does
   not (write) it *injects the jitter*: one keypress is a make **and** a break
   code, so two ISRs land inside one bit period, on the direction that
   **cannot report an error**, after which the user has just pressed Stop and
   will not Verify. **(b)** Any figure for what those ISRs cost would be an
   instruction count against a **hard 248.08 µs cliff whose failure mode is a
   silently corrupt tape** — and §3.3 already owes a measurement for the
   `kbm_isr` + `kbd_ovflow` + `sch_wake_ui` + ROM chain that runs on the READ
   side today. **(c)** Its port-61h read-modify-write races the BIOS on the
   motor bit (bit 3) and the timer-2 gate (bit 0), from an ISR that can fire
   between the BIOS's own `IN` and `OUT` on the same port — §3.8's race,
   deliberately not multiplied. **(d)** It is a **new SDK rule** — *a package
   may install a hardware interrupt vector, in a heap claim* — that would have
   to be written into SPEC.md §20.6 and that the next package author copies
   badly.
9. **The POST wrap-test hardware probe as a third gate.** It is real (IBM's
   TEST.13, `PCBIOS.ASM:1046-1086`), silent, needs no tape and energises no
   relay, and it detects the *port* rather than the badge. Refused for v1 on one
   specific ground: **its acceptance window is a constant nobody here has
   measured.** IBM's `[0x410, 0x540)` implies one PC4 edge per full timer-2
   period; MartyPC's `calc_port_c_value` returns `(timer_in) << 4` — one edge
   per *half* period — and would fail IBM's own bounds. Writing that constant
   from arithmetic is exactly what PERFORMANCE.md rule 3 exists to prevent. And
   it is not a gate anyway: a POST-131 machine with an oxidised relay may still
   record, so it belongs as a **warning**, behind one field measurement
   (§13.1 item 4).
10. **Bit-banging our own encoder.** The refusal that costs the user something
    real, so the arithmetic is here in full. It is the *only* way to get a
    watchable in-transfer animation: `WRITE_BIT` spends 248–496 µs per bit
    waiting for a timer-2 edge and `READ_HALF_BIT` has ~150–190 µs of slack
    after each, which at ~2,000 edges/s is **~300 ms of drawing per second of
    transfer — 30 fps**. It would also let the motor stay on across records and
    cut the 2,048-bit leader to ~400 (the reader needs 256), taking the
    per-record tax from 2.6 s to ~0.4 s and a 16 KB file from 138 s to 100 s.
    It costs ~400–600 bytes of package image, and it is bit-compatible with the
    ROM format (the CRC is ~20 bytes). **It is refused for v1 on TESTABILITY,
    not size.** The read side is a CPU-timed poll loop —
    `READ_HALF_BIT`'s `MOV CX,100` — which is why 5150CAXX refuses a 286 and a
    NEC V20 outright; and **no instrument in this project can exercise a
    cassette read at all.** Shipping an unverifiable decoder that writes to the
    user's only backup medium is worse than shipping a slow, verified one.
    See 12.5 below.
11. **An in-record animation from a replacement `int 08h`.** Three conditions
    and a hazard for two frames a second: it works only during a **write**, only
    on the genuine **IBM ROM** (GLaBIOS masks IRQ0 itself for both directions,
    GLABIOS.ASM:11394-11398), only at ~16 bytes of Hercules VRAM per tick at a
    50% margin — and it would draw from an ISR into a framebuffer whose **cursor
    save-under a package cannot reach** (`cur_lazy`/`cur_unlazy` are
    kernel-only), so it would smear the arrow. For scale, the splash's own
    IRQ0-drawn `spl_stars` is **4.14 ms — 16.7x the entire 248 µs budget.**
12. **Sound during a transfer** — but as a REFUSAL now, not a stated
    limitation. §3.8 and §5.1: `OSAPI_PIT_LEND AL=2` answers `AH=2` when
    `[snd_ch2mode]` is non-zero, and holds the speaker for the operation.
13. **Recompressing an already-`'CZ'` file, expanding anything on the read path,
    and wrapping a `.o88`/`.DRV`/`.OVL` in `'CZ'`.** §6.2, §8 rows 20–21.
14. **Automatic rewind, seek, or "skip to the third file".** §7.10. 74 seconds
    of frozen machine is worse than telling the user to press Fast Forward.
15. **A tape directory at the head of the tape.** It would be a lie the moment
    anything was appended, which is why none of the four prior-art systems has
    one.
16. **Writing every block twice (the C64's answer).** It doubles a 309-second
    transfer to 618. os8088 has a stronger lever pointing the other way —
    compression — which the C64 did not have.
17. **A header checksum** (§4.2), **a 256-entry CRC table** (§4.4: 512 bytes of
    claim to save 0.7 s of a 309-second transfer), and **timestamps or
    attributes in the header** (`dskw_commit` stamps the write with a clock that
    has just lost the whole transfer; and a hidden+system file cannot be
    selected in the file manager at all).
18. **The `/F` speed tweak** (1250/2500 Hz, 1.24x). It needs 8,208 bytes of heap
    to shadow 8 KB of ROM at offset `0xE000` exactly, and the divisor offsets
    (`FA2D`-or-`FA34`, `FA28`-or-`FA2F`) are the **IBM ROM's** — GLaBIOS is not
    byte-compatible there, so it would silently do nothing on every field twin.
    24% for that is not a trade.
19. **An `OS88_ASSOC16` block for `.TAP`.** An earlier draft declared one *"at
    zero kernel cost"*. **There is no `.TAP` file anywhere in this design**: §4
    defines a tape RECORD layout written to magnetic tape, and §7.10 writes
    exactly one disk file per Load — the user's payload under its own name from
    the header. `tools/os88pkg.py` would validate and ship the block happily,
    and what would actually ship is a live association to a file type that
    cannot exist, so the first user who names something `NOTES.TAP` gets it
    opened by the tape program. Dropped. If an on-disk tape index is ever
    wanted, it is a §4 addition with its own §8 rows, because it would be a file
    off a disk and §19's rule applies to it too.

---

## 12. Deferred, with the arithmetic attached

| # | item | cost | why it waits |
|---:|---|---|---|
| **12.1** | **The `File ▸ Tape…` item.** One `MENU_DIS`-twinned item whose thunk stages the selection into `assoc_doc`, sets `[assoc_dapp]` and `[ui_post]`, and returns `FMD_NONE` — `assoc_post_x`'s tail (`kernel/assoc.inc:645-685`) with a fixed program | **109 as built / 106 attributable** (`.text` 17, `.cold` 92, `.bss` 0), **and the File menu's last free slot** | The blocker is not the bytes (§1.1). Also `assoc_post_x` does not exist on kern_small (SPEC.md §54.0) and `fm_bar_gate_x` is only *called* `%ifndef KERN_SMALL` (`kernel/ui.inc:233-239`), so the hybrid needs a second route for the machine class the feature is named after. Revisit if the File menu ever scrolls, or on the fifth menu-bar cell (`AM_COUNT` 4 of `MENU_APPMAX` 5) at **190 as built / 187 attributable** |
| **12.2** | **`OSAPI_CLK_ADV`** — `AX` = ticks; reaches `[clk_acc]`/`[clk_last]` **without moving `[ticks]`** and re-stamps `[blk_t0]` | ~14 resident + ~20 `.cold` | A package can reach none of those symbols. §3.7's toast is 95% of the value for 20 bytes of package and no ABI, on a machine class that has no RTC at any rung. Revisit if a second consumer appears |
| **12.3** | ~~A "is PIT ch2 busy" query on the sound layer~~ | — | **RETIRED, not deferred.** §5.1's `OSAPI_PIT_LEND AL=2` answers it and holds it, which is what turns §3.8 from a stated limitation into a refusal |
| **12.4** | **Record-granular retry** — re-read block 4 alone (8.74 s) instead of the file (2:58 at 19 records) | ~250 bytes of package | Needs **two** things settled, and §4.5 has now settled the harder half in the wrong direction: GLaBIOS's `CAS_READ_ERR` **does** re-enter the header search with CX re-armed and DI un-reset, which is a heap overrun and not merely a splice. Record-granular retry would have to aim a read at a record whose length it has not read, which is exactly the shape that triggers it. It also assumes every record on the tape is the same length, which a foreign record breaks. **Revisit only against the IBM ROM, where `JCXZ W12` makes the overrun impossible** — and even then, only for a machine that has been shown to have one |
| **12.5** | **The bit-banged transport** | ~400–600 bytes of package image | §11 item 10 is the refusal. What would change it: a cassette deck on a field 5150 (so the read path can be calibrated against a real analogue chain), or a MartyPC cassette device. The prize is 30 fps, 8.74 s → 6.5 s a record, a 16 KB file 138 s → 100 s, and a genuinely animated window |
| **12.6** | **Files over `TP_MAXFILE`**, as a multi-tape-record continuation | ~400 bytes plus `vol`/`part` in the header | A 42 KB file is 6:32 each way, and a continuation needs a resume prompt, a part id and a "wrong part" refusal. The refusal at 32 KB is honest and costs 20 bytes |
| **12.7** | **The POST wrap test as a WARNING** (§11 item 9) | ~90 bytes, ~3 ms once at launch | Needs one field reading: the real PC4 edge interval with the motor off and ch2 at count 1235. `make stkdiag`'s shape — one boot, one number |
| **12.8** | **A MartyPC cassette device** | ~200–300 lines of Rust, **clean-roomed** | It is the difference between a feature with two gates and a feature with almost none. **86Box's `cassette.c` is PCE's, GPLv2, and CONTRIBUTING.md §6 forbids vendoring**, so it must be written from the format description — which §4.1 now contains in full. The gap is one match arm in `calc_port_c_value` (`ppi.rs:861`) plus a tape-image device. A decision for whoever owns the MartyPC pin |
| **12.9** | **An 86Box `ibmpc82` profile** | one `vm/` directory, plus a ROM this tree may not carry | 86Box **does** emulate the cassette (`ibmpc` caps at 64 KB and cannot boot either kernel; **`ibmpc82` is 64–256 KB** and can), the keys go in **`[Storage controllers]`** (`cassette_enabled`, `cassette_file` with a `wp://` prefix, `cassette_mode = save`), and **`.cas` IS the BIOS bit stream packed MSB-first with no header** — so `tools/os88tape.py --rom ibm` writes byte-identical `.cas` files and can decode one 86Box produced. **The `--rom` flag is not optional for this**: 86Box's cassette machines are `ibmpc`/`ibmpc82`, i.e. the IBM ROM, and a GLaBIOS-shaped golden with its leading zero bit would never match. The *session* is manual and the **verdict is a host-side script over the file it left behind**. It is the only place the **read** path can be exercised without a deck |

---

## 13. The field request — T1, and it starts with a purchase, not a run

### 13.0 THE PREREQUISITE, and it is a gate on the whole feature

**Neither registered IBM 5150 in `docs/FIELD-MACHINES.md` mentions a cassette
deck, a cable or the port** — the words do not appear in either machine entry
(`:48-146`, `:148-192`), and 5150 #1 is *"intentionally, entirely period."*

> **Ask before building anything: is the DIN-5 cassette port populated on
> 5150 #1, and is there a working data cassette deck and a cable?**

**A deck and a DIN-5 cable are a purchase, not a config change.**
`docs/FIELD-MACHINES.md`'s own rule is that the marginal cost of one more
benchmark row is nothing and the marginal cost of one more **trip** is seven
manual steps. **If the answer is no, this feature has no verification path for
its central claim, and that should be RECORDED rather than worked around.**

A second question, and it is cheap: **which ROM is in 5150 #1?** The tree names
the 27-Oct-82 revision; 5150CAXX probes *two* divisor addresses precisely
because IBM shipped more than one. This design does not patch those constants —
which is one more argument for not patching them — but §0.3's fixed-cost table
has a per-ROM row and the field run should say which one it is reading.

### 13.1 What a run settles, batched onto one disk

Six gestures, and the program prints its own verdict on the glass
(`docs/FIELD-MACHINES.md`'s rule: when the field question is about logic,
publish the state and let the machine print it):

1. **Does mode 3 fix the read? (§0.1.)** Boot with and without the bracket —
   **`TAPEMODE2=1` is the A/B knob**, and it exists precisely because **this is
   the only load-bearing claim in the design derived from a listing rather than
   from observation.** Read a known tape in both arms. If the un-bracketed arm
   answers `AH=04` and the bracketed arm reads the file, the finding is
   confirmed.
2. **The ERROR RATE — the number that actually decides whether this is
   usable.** Write a known 4 KB file; note the tape counter; wind back; Load it;
   read the *bytes matched / first mismatch offset* line **off the glass**. Then
   **read the same tape three more times WITHOUT rewriting it.** *Whether it
   worked once* is not the question; *how many blocks of four reads come back
   CRC-clean* is.
3. **Wall clock against the model.** Save and Load a 32 KB compressed file,
   timed with a watch. The model predicts **5:09** each way at `TP_FIX = 2.6`,
   and on a genuine IBM ROM it should come in ~3.6 s FASTER over 34 records
   (§0.3's 2.49 s row). More than ~10% out is a finding, and the direction
   matters. **Report the ROM date with the number**, because the two ROMs are
   4% apart and the model knows it.
4. **The PC4 wrap interval**, with the motor off and ch2 at count 1235, for
   §12.7. MartyPC's `calc_port_c_value` DOES model loopback with the motor
   **off** — `(timer_in) << 4` — so IBM's `[0x410, 0x540)` window would fail
   there, and **only iron can settle it.**
5. **How static is inter-file tape?** Play blank tape between two files with the
   motor on and watch the sniff's verdict. §2.3's false-negative risk is exactly
   this, and `Load anyway` exists because the answer is not known.
6. **What does a keystroke cost a read?** Type steadily through a 1,016-byte
   read and count the CRC errors against a silent control. §3.3 leaves IRQ1 live
   on the read deliberately and prices the cost at *an instruction count, which
   is not a measurement* — the design's own rule, applied to itself.

**Publish the mode on the glass** — which ROM date, which record size, whether
the read took the mode-3 bracket, and which transport. A run that does not say
which experiment it ran answers neither, the way `gfxbench` names the adapter it
found.

**Do NOT ask for**: anything about the bit encoding, the CRC, the block padding,
the record layout or the byte counts — all settled host-side by `tapefmt`.
Anything about redraw cost. And not how long a write takes with no deck —
measured here, exactly, in §0.3.

---

## 14. SPEC and SDK corrections that must ride in the same commits

Neither of the first two is this feature's fault; both would break an
implementer working from the published text, and this design **publishes an API
cell whose contract is one of them.**

**14.1 — `SPEC.md:32474`, §20.15.1's `cmz_pack` register block.** It publishes
`BX = a scratch segment of CMZ_TBL (8,192) bytes`. Two errors. **It omits `DI`
entirely** — the window's *mask*, a required input, and `cmz_pack`'s first
action is `mov [cs:cmz_mask], di` (`kernel/compress.inc:126`). And **`CMZ_TBL`
does not exist anywhere in the tree** — `grep CMZ_TBL SPEC.md kernel/ tools/`
returns exactly that one line — where the real requirement is
`CMZ_PREV + 2*(DI+1)` = 8,192 + 2×window = **40,962 bytes at the 16,384
window**, five times the published figure. The correct block is at
`kernel/compress.inc:100-118`, verified this session, and **§5.2's cell contract
must be written against that and not against SPEC.md.**

**14.2 — `kernel/lz.inc:111`'s clobber banner.** It says *"DS and ES come back
the caller's."* Verified false for outputs over 64 KB: `lz_dbump`
(`kernel/lz.inc:267-272`) does `mov ax, es / add ax, 0x1000 / mov es, ax` with
**no `push es`**, and the `.out` unwind pops `cx, dx, bx, si, di, bp, ds` only.
The `out:` line is right; the clobber line is wrong.

**14.3 — SPEC.md §34.1's channel-0 rule** gains §5.1's narrow exception, in the
same commit as the cell. Written as an exception with a refusal attached, not as
a relaxation.

**14.4 — corrections an earlier draft got wrong, recorded so they are not
"fixed" into errors:**

- **SPEC.md §20.6's slot numbers are CORRECT.** `SPEC.md:30185-30186` gives
  `0x0160 inst_pkg_spawn (X)` and `0x0168 inst_pkg_alive`, matching
  `kernel/kernel.asm:2805-2808`. There is nothing to fix. What *is* wrong is a
  draft's own citation of `OSAPI_FDLG_OPEN`, which is not a symbol: the SDK
  spells it **`OSAPI_FILE_DLG`** (`apps/os88api.inc:565`) and the kernel cell is
  `api_fdlg_open` (`kernel/kernel.asm:2801`). The slot, 0x0150, is right.
- **SPEC.md §11.94's snap is opt-OUT, not opt-in** (`kernel/wm.inc:4283-4340`),
  so a window that never calls `OSAPI_WM_SNAP` is aligned. §7.1 relies on that
  and it is correct as it stands.

**Also worth fixing while nearby**: SPEC.md §74.1's slot table
(`OSAPI_WM_WAKE` is **0x0450** and `OSAPI_WM_ONWAKE` **0x0458**, not
0x0428/0x0430 — 0x0430 is now `OSAPI_WM_ONDRAG`), §13.9's `W_ONTIMER` heading
(0x0440, not 0x0430), `apps/os88api.inc:1866-1877`'s copy of §20.6 rule 7
(missing `OSAPI_DRV_CALL`, which SPEC.md lists), and
`apps/os88api.inc:1865`'s *"Your stack is SCH_STACK (384) bytes"*, which §8.7's
class scheme replaced.

---

## 15. Implementation order

Each wave leaves the tree green and shippable, and each is independently
testable.

| wave | what | gate |
|---:|---|---|
| **0** | **Ask §13.0's field prerequisite, and get §16 rows 1 and 2 answered.** Then land §14.1, §14.2 and §14.4's SDK-name correction | `python3 tools/checkdocs.py` |
| **1** | **Write SPEC.md section 88 — before the code**, together with 14.3's SPEC.md §34.1 amendment. §3.6's freeze paragraph, §4.1's two-ROM pad and start-bit note, §4.2's field table, §4.5's invariant and the GLaBIOS overrun, §7.2's "why not a spinner", and §11's refusals are the load-bearing parts | `checkdocs.py`, and `make test-fast` |
| **2** | **`tools/os88tape.py`** with `--rom ibm|glabios` and `--selfcheck`, **`t_tapefmt`**, **`t_tapedet`** and its committed ROM fixture. **The format is settled before a byte of 8086 is written, and §0.4's tables become things the tool PRINTS.** This matters more here than anywhere else in the tree, because no emulator can check the machine | `make test-fast` |
| **3** | **`OSAPI_PIT_LEND`** (§5.1) — the cell, `[sch_pitbios]`, the three kernel guards, and the §34.1 amendment made good. **`tests/tapequantum.py`** is its gate and can be written before any tape code exists: a `QUANTUM=2` kernel, a caller that asks for the lend, an assertion that it is refused and the tick rate is intact | `make test-full`, then `os88test.py soak -k 'tapequantum'` |
| **4** | **`OSAPI_COMPRESS`** (§5.2) — the cell and the cloner's new DL verb. **`tapecomp`, including the `cmz_pack` cycle measurement and the 128 KB NOMEM leg**, so the CPU-versus-tape trade stops being modelled | `make test-full`, then `soak -k 'tapecomp'` |
| **5** | **`TAPE.O88` with `-DTAPE_FAKE` only**: `OS88_PREFER` and `WM_GEOM` layout, buttons, greying, the state machine, the coast, the format, the 29 checks, file I/O, the second-instance refusal. **Every string through `OSAPI_FONT_RUN`, and `tests/textsites.txt` unchanged — or the build fails.** `tapesim`, `tapehostile`, and the fixture disk with its 29 malformed images. **Take the stack water mark** with `tools/stkwater.py` on a fake-transport record and write the number into §1.3 | `soak -k 'tape*'` |
| **6** | **`tapexfr.inc`'s real half** — `int 15h`, the IMR bracket, the `PIT_LEND` calls in §3.1's exact order, the **floppy-motor wait**, the **2-second sniff** with `Load anyway`. The `_cas` MartyPC twin with content-asserted ROM, `tapehw` with its four positive controls, `taperefuse`, `tapedetsweep`. **Re-take the stack water mark on the real transport** — this is where the ROM's own frame lands | `soak -k 'tape*'` |
| **7** | The field disk and T1 — **if and only if §13.0's answer was yes** | a photograph, and §13.1's six readings |

---

## 16. The open questions — the ones that are the user's, not this document's

| # | question | what hangs on it |
|---:|---|---|
| **1** | **May a new kernel cell write PIT channel 0?** SPEC.md §34.1 says *"PIT channel 0 is never written"* and carries a **recorded refusal** about re-rating it. §5.1 is a narrow exception — one call's worth, IRQ0 masked, refused outright on a `QUANTUM=` kernel — but it is still an amendment to a rule written to stop this conversation recurring. **Cost: 47 resident bytes, all in `KERN_CODE_MAX`.** If the answer is no, **the READ path is impossible** and the honest v1 is write-and-verify-only on a machine that can never read its own tapes back — which is arguably not a feature at all. There is no third option: an 8253 has no read-back, so a package cannot restore what it did not know. |
| **2** | **Is there a deck?** §13.0. Is the DIN-5 port populated on 5150 #1, and is there a working data cassette recorder and cable? **If not, §0.1's finding, the error rate, the wall-clock model and the whole read path go unverified for ever**, because §10.4 lists every instrument here and none of them can do it. It is legitimate to build it anyway and say so in SPEC.md section 88; it is not legitimate to build it and imply it was tested. |
| **3** | **Is "the motor keeps turning through a Restart" acceptable?** §3.7: `ui_cmd_reboot` reaches `drv_shutdown_x` and no package, so System ▸ Restart with a transfer armed leaves the relay energised until POST rewrites port 61h ~a second later. **The tree has exactly one mechanism for "hardware must be put back before `int 19h`" and it is `drv_tab`-only** — so this is the one surviving argument for the `TAPE.DRV` §1.2 refuses on 129 resident bytes and the loss of kern_small. Accept the second of relay, or re-open the driver? |
| **4** | **Is refusing sound for the length of a transfer right?** §5.1's claim holds ch2 and the speaker for the whole operation, so a tone playing when Go is pressed **refuses the transfer** and a tone started during one is refused. That is SPEC.md §34.1's one-owner rule honoured exactly, and it is stricter than the "clipped beep" an earlier draft accepted. Five minutes of no sound is a long time. |
| **5** | **`TP_MAXFILE = 32,768`, or a multi-tape-record continuation?** 32 KB is 5:09 each way and the refusal costs 20 bytes and prints the arithmetic; the continuation is ~400 bytes plus two header fields plus a "wrong part" refusal (§12.6). And on kern_small the *live* ceiling is ~20 KB whatever the format says (§6.5). |
| **6** | **Confirm the `0xA5` refusal.** §4.7 refuses IBM Cassette BASIC compatibility on four structural grounds, the sharpest being that a tape we wrote with an `0xA5` header, played into ROM BASIC, would load our bytes to `0060:081E` and **execute them as tokenised BASIC**. Recognising the record in the Catalog costs a dozen bytes and is proposed; writing one is refused. |
| **7** | **Two new API cells is two new API cells.** §9.1 spends 47 resident bytes and two of the 163 table slots on a peripheral that exactly one machine model in the world has. Both cells are general (`OSAPI_COMPRESS` is the missing counterpart of `OSAPI_DECOMP`, published since §20.13 with no encoder beside it; `OSAPI_PIT_LEND` is the only correct way for anything to hand ch0 to a ROM routine) — but neither has a second consumer today. |
