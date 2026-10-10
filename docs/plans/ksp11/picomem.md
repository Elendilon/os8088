# Kernel size pass 11 - agent "picomem": notes

Concept: the PicoMEM work - merges `eb1be371` (the card's NE2000 on its real
memory map, SPEC.md 72.2; SOUND.DRV's PicoMEM IRQ handling, 34.10.1) and
`a3818217` (the PicoMEM tier in SOUND.DRV by default, the USB mouse 9.12.7,
B: from the card 18.97.6, Restart warm-resets 18.100.1). Files:
`kernel/disk.inc` (my hunks only: `dsk_fdd_park_x`, `dsk_fdd_pmemu`, its call
in `dsk_fdd_probe`), `drivers/sound/{picomem,sb}.inc`, `drivers/sound/sound.asm`,
`drivers/ether/ne2000.inc`, `drivers/usbmouse/usbmouse.asm`.

Branch `ksp11-picomem`, cut from `elendilon` at `2a05e31f`.

## Base `2a05e31f`

| | kern_big | kern_small |
|---|---:|---:|
| `.text` / `.bss` / `.cold` | 43,428 / 5,190 / 37,943 | 32,022 / 3,073 / 23,479 |
| `.lowbss` / `.vgabuf` | 5,598 / 336 | 2,868 / 0 |
| **resident** | **92,495** | **61,442** |
| `.ovl` / `.ovlw` | 2,471 / 5,086 | 2,076 / 1,480 |

`kern_dos` (`build/kerndos.bin`, a part of `DOS.O88`): 33,243 bytes.

Drivers - UNPACKED image + bss, which is what `drv_load` claims (rounded up to
whole KB, `mem_bytes_kb_x`):

| driver | image | bss | image+bss | claim |
|---|---:|---:|---:|---:|
| SOUND.DRV | 6,946 | 176 | 7,122 | 7 KB |
| ETHER.DRV | 16,400 | 496 | 16,896 | 17 KB |
| USBMOUSE.DRV | 1,410 | 0 | 1,410 | 2 KB |

What the concept cost them (assembled, `nasm` on the trees named): SOUND.DRV
6,637 without the PicoMEM tier (`NOPICOMEM=1`) -> 7,122 with it, **+485**, all
of it attach code and its state, resident for as long as the driver is
mounted; ETHER.DRV 16,778 (`e002a0e9`) -> 16,896, +118; USBMOUSE.DRV 1,151 ->
1,410, +259.

The kernel half: `.cold` +40 on both kernels is the warm reset at the head of
`dsk_fdd_park_x` (this is where "Restart warm-resets" lives - kernel, not a
driver); `.ovlw` +85 on kern_big is `dsk_fdd_pmemu` and its call. **On
kern_small the PicoMEM costs `.ovlw` nothing**: `dsk_fdd_pmemu` is
`%ifdef KERN_BIG`, so KERN-SMALL-CUT-PLAN 7's FAT-window floor (the cap that
binds kern_small's `.ovlw`) is untouched by this concept. On kern_big the
`.ovlw` ceiling is the FAT window plus `dsk_secbuf`, 5,120 bytes by sector:
the +85 took kern_big's payload spare from 119 to 34.

## TAKEN

### Batch 1 - the kernel half (`kernel/disk.inc`, `tools/stkbalance.py`)

kern_big `.cold -5`, `.ovlw -11` (resident 92,495 -> 92,490); kern_small
`.cold -5` (61,442 -> 61,437); kern_dos 33,243 -> 33,183 (-60).

* **`dsk_fdd_park_x`'s warm reset, -5 on both kernels.** CX is 0 when the
  ramp's `loop` runs out, which is the only way onto the warm-reset path, so
  `mov es, cx` with `[es:0x472]` replaces `mov ax, 0x40 / mov es, ax` with
  `[es:0x72]` (-3) - the same byte, 0040:0072h. The `popf / cli` pair that
  only existed to balance the stack for the walker before a jump that never
  comes back is gone (-2): IF is still 0 from the ramp's `cli` to the reset
  vector, and the machine state at `FFFF:0000` is identical but for SP, which
  POST does not read. 40 -> 35 bytes.
* **`tools/stkbalance.py`: a far jump to a LITERAL address ends the path**
  (`FARLIT`). `jmp 0xFFFF:0x0000` leaves every routine the walk can see, so
  nothing in the corpus will ever pop what it leaves; a far jump to a LABEL
  (`jmp KERNEL_SEG:sched_unhook`) is still a tail call and still walked.
  `tests/unit/t_stkbalance.py` carries both halves - the QUIET case (the warm
  reset's shape, which the old walker reported) and a LOUD one (a far jump to
  a label at depth must still be caught). It is the only literal far jump in
  `kernel/`, `apps/`, `drivers/`, `boot/` and `kerndos/`.
* **`dsk_fdd_park_x` is not assembled into kern_dos** (`%ifndef KD_BUILD`),
  -60 bytes of the DOS program. kern_dos includes `disk.inc` whole, and
  `kd_leave` parks with its own loop (`kerndos/kdentry.inc`); nothing there
  calls this one - `sched_unhook`, its only caller, is not in that root. NOT
  the concept's bytes alone: 20 of the 60 are the park's, the other 40 the
  PicoMEM's.
* **`dsk_fdd_pmemu` saves nothing; its caller already has, -11 `.ovlw` on
  kern_big.** The call moves in `dsk_fdd_probe` from before the probe's five
  pushes to after them, the yes path leaving through a new `.pops` (the
  probe's own pop tail, after the DOR restore, which the PicoMEM path never
  touched and still does not). So BX, CX, DX and ES are banked once instead of
  twice; AL comes back = the unit on every no path, which is all `.fdc` reads
  (BX, CX, DX, ES are each written before use below it - checked line by
  line). `test byte [es:bx+0x40B2]` reaches the attribute 16KB up without
  `add bx, 0x400`, and the `test` leaves CF = 0 for the yes exit. 77 + 8 = 85
  -> 64 + 10 = 74. The published state is unchanged on both paths: the
  PicoMEM path still sets no `fdd_dbg_ran` bit (the call sits above that
  store) and now writes `[fdd_unit]`, which only the probe reads. Returns
  kern_big's window-half spare from 34 to 45 bytes.

Proved: `tests/picomem.py` (the `kern` leg cuts `dsk_fdd_pmemu` and
`dsk_fdd_park_x` out of `disk.inc` as they ship and runs them under unicorn
against a model of the card - unit 0/1 served or not, Restart warm-resets with
1234h at 0040:0072 and FFFF:0000, the no-card machine parks both units and
int 19h's) all ok. No emulator here has a PicoMEM, so the probe's new call
site is proved by reading plus `fddpark` on MartyPC (the no-card path).
