# Driver size pass 2: input (`KEYBOARD.DRV`, `PC1MOUSE.DRV`, `RAMDISK.DRV`, `CDROM.DRV`)

Branch `dsp2-input`, base `1b01907f1` (the brief, on `aa6b428`, build 445).
The row (`BRIEF.md` section 2): every line under `section .modq`
(`kernel/keyboard.inc`, `kernel/keyfont.inc`) and the data only the module
reads (`kernel/keymaps.inc`, `kernel/keyfont-data.inc`); `drivers/pc1mouse/`,
`drivers/ramdisk/`, `drivers/cdrom/`. **Taken from no row**:
`tools/keyboardmaps.py` (the generator of `keymaps.inc`, in no row) and
`tests/kbdlayouts.py`'s three negative controls, which named the old table
layout by offset (section 7 says how they were kept honest).

Figures are from builds of this worktree. A module's image is its header's
`MOD_H_IMG` (`MODQ_SIZE`, bss tail included); a driver's is `os88drv`'s
`image=` (its bss included). "Granules" are the heap's 512 bytes a claim is
rounded to (SPEC.md 50.2.1). File is what the disk holds (lz4).

## 1. BASE AND TIP

| | kernel | image base -> tip | of which bss | file base -> tip | granules (RAM while loaded) |
|---|---|---:|---:|---:|---:|
| **KEYBOARD.DRV** | kern_big | 5,624 -> **3,879** (-1,745) | 16 / 16 | 2,914 -> **2,502** (-412) | 11 -> **8** |
| | kern_small | 5,624 -> **3,879** (-1,745) | 16 / 16 | 2,914 -> **2,502** (-412) | 11 -> **8** |
| | kern_emu | 5,624 -> **3,879** (-1,745) | 16 / 16 | 2,914 -> **2,502** (-412) | 11 -> **8** |
| | kern_mega | 5,674 -> **3,943** (-1,731) | 16 / 16 | 2,934 -> **2,534** (-400) | 12 -> **8** |
| **PC1MOUSE.DRV** | (one image) | 452 -> **410** (-42) | 0 | 423 -> **399** (-24) | 1 -> 1 |
| | `PC1_SCALE8` arm (`build/pc1slow/`) | 456 -> 418 (-38) | 0 | | 1 -> 1 |
| **RAMDISK.DRV** | (one image) | 5,407 -> **5,401** (-6) | 112 / 112 | 4,604 -> **4,598** (-6) | 11 -> 11 |
| **CDROM.DRV** | (one image) | 8,203 -> 8,209 (+6) | 0 / 0 | 4,644 -> **4,643** (-1) | 17 -> **16 after attach** |

CDROM.DRV loads 8,209 bytes (17 granules) and from the end of its attach
holds 8,037 of them (16 granules): the kernel shrinks the claim to
`DRV_H_KEEP` (SPEC.md 51.1.3). Read off a QEMU boot (section 9):
`DRVR_PARA` = 512 paragraphs.

**Clusters.** `tools/os88diskuse.py --diff`, 360KB images: the system disk
`os8088-360.img` **27 -> 28 free** (KEYBOARD.DRV 6 -> 5 clusters);
`small360.img` 14 -> 14 (KEYBOARD.DRV 3 -> 3, 1KB clusters); no other 360KB
image changed except `util360.img`'s SYSCHECK.O88 +1 byte (its manifest of
the system files, `tools/os88sysman.py`; 15 -> 15 clusters). CDROM.DRV is on
no 360KB disk. On the 512-byte-cluster geometries KEYBOARD.DRV is 6 -> 5
clusters; the three drivers stay where they were (PC1 1, RAMDISK 9, CDROM 10).

**The resident kernels.** `cmp -l` of each `kernel.bin`, base against tip,
built at one commit: **kern_big 2 bytes, kern_small 2, kern_emu 2,
kern_mega 5** - all of them immediates whose VALUE is KEYBOARD.DRV's own
layout (section 5, item 1); same lengths, same instructions. `kernsize.py
--json` on kern_big: identical. kern_small, kern_emu and kern_mega: same
file lengths, the bytes above and nothing else.

## 2. TAKEN

### 2.1 KEYBOARD.DRV: the layout tables (-1,497 bytes of image)

`tools/keyboardmaps.py` writes `kernel/keymaps.inc`; the routines that read
it changed with it. Per layout the base had three planes of 87 WORDS (every
scan 00h..56h, CP850 byte + bit 8 = dead) and an 11-byte Caps bitmap: 533
bytes, 2,140 with the pointer table.

* **Only the keys the layouts translate.** klm_scan ever hands klm_translate
  49 scans (the four rows, 29h, 2Bh, Space, the ISO key 56h); 38 of the 87
  rows a plane held were never read. A plane is now 49 BYTES in one shared
  key order, and **`klm_idx`** (87 bytes, shared by all four) maps a scan to
  its index + 1, `KLM_BS` (50) for Backspace, 0 for the BIOS's keys.
* **One byte a key, the dead flag folded in.** No plane holds a byte below
  20h (the control characters of 01h/0Eh/0Fh/1Ch were rows nothing read), so
  a dead accent is a CODE 1..5 and **`klm_deadch`** (5 bytes) turns it into
  its CP850 byte. 0 stays "unmappable".
* **US has no AltGr plane**: klm_translate passes US AltGr before it reads
  one (the generator asserts the plane is empty).
* **Caps Lock is a compare, not a bitmap.** The key order is chosen so that
  every layout's Caps-sensitive set is a PREFIX: US's 26 letters, then LA's
  n-tilde key (27), ES's c-cedilla key (28), then the 18 keys only French
  AZERTY's shift-lock adds (46). The byte before a layout's base plane is its
  count. The generator asserts the nesting and fails if a layout ever breaks
  it.

Tables 2,140 -> 643 bytes (`klm_maps` 9, the four layouts 99 + 148 + 148 +
147, `klm_idx` 87, `klm_deadch` 5). `klm_compose` (110) and the CP850 glyphs
(1,024, plus the 768-byte zeroed ASCII half of `klf_table`, which the
renderer needs contiguous) are unchanged.

### 2.2 KEYBOARD.DRV: the code (-248 bytes, kern_mega -234)

Spans from the two maps (kern_big; kern_mega in brackets where it differs):

| routine (base) | base | tip | what |
|---|---:|---:|---|
| klm_scan + klm_focus_owner | 357 + 134 | 294 + arms 82 + klm_off 5 | the focus owner written at its one caller; **layout 0 passes after three pushes** (`cmp [klm_layout], 1 / jb klm_off`: CF = 1 from the compare, four pops) instead of eight; the scan kept in BP (DI never touched, so neither banked); the window count clamped in AL (`cbw / xchg`), the loop `dec si / js`, the owner by `xlat`; the pause/prefix tests inverted so their rare arms sit in reach and the common path falls through; **the printable classification one `klm_idx` read** where it was up to eleven compares; Backspace one more index value. `xor ah, ah` at `.key` was a dead store. Base's modifier tests were all NASM's out-of-range pairs (`jne +3 / jmp near`): now short |
| klm_translate | 195 | 31 + shcaps 28 + chord 31 + control 46 | the layout's plane pointer from `cbw / add / xchg` (13 bytes where 20 built the word index); **one test for any Alt/Ctrl and one for any Shift/Caps** - the plain key falls straight through to the byte read; the AltGr/Ctrl logic in `klm_chord` (same answers: right Alt, or left Alt with either Ctrl, is AltGr; left Alt alone passes; a Ctrl alone is a control key); the Caps test `cmp bl, [cs:si-1]` where it was a bitmap read through two shifts by CL |
| klm_character | 115 | 15 + deadkey 41 + compose 64 | the ordinary character falls into klm_single (no taken jump); a dead key decodes its code through `klm_deadch`; the accent-then-Space exit shares the found pair's `jmp klm_single` |
| klm_store, klm_lost, klm_next | 101 | 101 | the ring-bounds test one unsigned compare (`lea si, [bx-KBD_BUFB] / cmp si, 20h`); its `push ax / pop ax` round KLM_BDA mega-only (only mega's SMSW takes AX); `.tail` falls into the exit |
| the exits | 13 | 20 | **`klm_eaten` is `db 0A8h`** (`test al, 0F9h`: CF = 0, and the next byte, klm_pass's `stc`, is its immediate) - no `clc / jmp`; and a second copy of the ten-byte exit beside klm_store, so both the scan's tests and the store's reach one short |
| klm_control + klm_hold + klm_release + klm_status + klm_return | 217 | 161 | SI and BP never banked (nothing on these paths writes them: klf_enable banks its own SI, and `cw_gfx_lock`/`unlock` keep every register); **HOLD and RELEASE one owner test** (`cmp al, KBDV_RELEASE / jbe klm_hold`; the built-in owner's byte is `verb XOR RELEASE`); klf_enable's refusal tests dropped (it returns CF = 0 always - `kbdlayoutfont` pins it - and ksp21's DEFECTS 2 says kl_control_x would lose such a CF anyway); `cbw` and `or bl, bl` in klm_status; the arms ordered round the ladder for short reach |
| klm_seed | 99 [109] | 90 [100] | the modifier and prefix bytes, and the Pause and Caps-held bytes, stored as two words (adjacency asserted) |
| keyfont.inc | 226 | 206 | klf_enable's DS banked round the copy only; klf_disable reads the active byte once and its suspended arm shares the store; the CLCs no caller reads (klf_disable, klf_suspend, klf_rearm: klm_status sets the control call's CF, kl_drop_x answers AX = 0) gone, **klf_enable's kept** (pinned); klf_lock one `mov bl, 0` with the flags kept and `inc bx` |

`stkbalance` (the fast tier) walks every path: 0 findings. Two things it
taught: an `%error` string naming a label marks the label ADDRESSED (an
entry walked from depth 0), so the new `%if`s name none; and an unreferenced
global after a `db` skip is an entry too, so `klm_scanret` is gone. A jump
table for the control verbs was tried and dropped: two bytes, and the gate
cannot follow its arms.

### 2.3 PC1MOUSE.DRV (-42 image, -24 file)

* p1_probe and p1_keyinit written in DRVV_ATTACH, p1_sample in the worker's
  loop (each had one caller); the ROM word read `mov ax, [0FFFDh]` with no BX
  bank.
* p1_keyinit's success and failure tails were the same IMR restore: one now,
  CF carried across it by its own `pushf / popf`. The data port loaded once
  for the five-byte sequence (p1_kbout keeps DX).
* p1_kbout and p1_kbin share their exits (`stc` falls into the pops, a `jc`
  skips the write). **Every poll loop is the same instructions** (`in / test /
  jz / loop`), so the bounded waits are the same length in time.
* P1_ACCEL's sign test `or dx, dx / jns` for `test dx, 8000h / jz` (-2 bytes
  each expansion); the left button's bit by `adc cl, 0` (CL is 0, CF is the
  answer). `tests/unit/t_pc1mouse.py`'s spellings are all kept: the
  `p1_sample:` label still opens the body it reads, and `p1_exit` sits before
  the worker so that body ends where it did.

### 2.4 RAMDISK.DRV (-6 image, -6 file)

The +7 since `e7668bd73` was RDPV_MOUNTC's rung on rd_pkg's ladder. MOUNTC is
`RDPV_MAX`, so `cmp bl, RDPV_MOUNTC / ja .none / je .mountc` is the range
test and the top verb in one compare, and `cmp bl, RDPV_STATE / je .state /
ja .mount` the same for MOUNT. A `%if` pins the verb order; `rdpkg.inc` is
not touched (package-facing ABI).

### 2.5 CDROM.DRV: the probe handed back (+6 image, -1 file, -1 granule loaded)

dsp1 (`cdram.md` 6) priced the attach-only code at ~200 bytes and needing a
loader that could shrink a driver's claim. **SOUND.DRV's `DRV_H_KEEP` is that
loader** (SPEC.md 51.1.3, kern_big's `%1_att`, zero resident bytes). So
`cd_bases`, `cd_probe` and `cd_ident` (172 bytes) move from `atapi.inc` to
the END of `cdrom.asm`, after every cell of the state, and cd_attach writes
`DRV_H_KEEP = cd_keep` (6 bytes) once its probe found the drive: 17 granules
-> 16. Nothing reaches the dropped bytes again (one caller each; a second
ATTACH is refused `DRVE_TWICE` by cd_attach's test of `cd_base`, a cell
before the offset; a refused attach frees the image). The state's zeros now
ship, being no longer the image's tail, and lz4 still packs the file a byte
smaller. kern_emu takes the shrink too (it is kern_big); kern_mega's image
above 1MB is no heap claim and the kernel passes it by, as for SOUND.DRV.
SPEC.md 119.2 says so. The probe stays in a `.asm` the Makefile already
lists, so no rule changed.

### 2.6 Equivalence (all scratch, none committed)

| harness | what | result |
|---|---|---|
| `hscan` | klm_scan on BASE and TIP module bytes (each with its own resident `.text`), state set and compared BY NAME: every scan 00..FF x every modifier byte x layout 0..4; then 20 modifier bytes x 7 pending accents x E0 prefix x 4 layouts; pause 0/1/5, Caps held, five window/instance tables x foreign x focus, the BIOS Pause bit, ten ring head/tail states x overrun counts. Compared: CF, every register, every state byte, the BDA page, `kbd_ovn`/`kbd_ovb`/`ui_post`, the ORDERED write log, stack depth <= 48 | kern_big **473,852 cases**, 0 differences; the 149,564-case sample on kern_small, kern_emu and kern_mega, 0 differences |
| `hctl` | klm_control, every verb 0..9/80h/FFh x layout argument x owner (0, 1, 5, INST_MAX-1, INST_MAX, FEh, FFh) x 72 module states x two BDA snapshots x the drawing lock free/ours/another's; then klf_enable/disable/suspend/rearm called directly. Compared: AX, CF, registers, the write log by name, lock/unlock calls, how it left (retf, or the far jump to kl_drop_x and with what), the whole 1,792-byte glyph table, the kernel's font words | 22,536 cases on each of the four kernels, **0 differences**; one deliberate: klf_disable's `klf_active = 0` store now runs after its POPF (504 cases), a byte only ever read under the drawing lock this routine holds, never from an IRQ |
| `hpc1` | PC1MOUSE attach over 3 CPU answers x 6 ROM words x 5 scripted controllers x 3 replies x 3 IMRs; DETACH/READY/refused verbs; the worker over seven counter/button sequences, both arms (`PC1_SCALE8` too) | 618 cases each arm, 0 differences (ports in order, poll counts, kernel calls with registers, writes by name) |
| RAMDISK | rd_pkg for every BL 0..FF from two flag states: the arm reached | 512 cases, 0 differences |
| `relmap` | CDROM.DRV: every label walked instruction by instruction through the address map the two symbol maps give | 371 labels, the one difference the `DRV_H_KEEP` store; a planted changed constant goes red |
| `kbdlayouts`' negative controls | the three new offsets (`key()`, through `klm_idx`) read back the bytes they mean: FR base 10h `a`, LA base 0Dh `¿`, FR AltGr 0Bh `@` | checked by reading the built image, not by running the row |

## 3. SPEED

**KEYBOARD.DRV, per keystroke** (klm_scan, the IRQ path). `tools/x3cyc.py`'s
8088 model (BIU queue, bus, refresh) over the instructions Unicorn executed,
both images from the same state; clocks / instructions / bytes fetched:

| keystroke (ES, one native window in front) | base | tip | |
|---|---:|---:|---:|
| layout 0 (BIOS input, only a glyph hold loaded) | 357 | **233** | -124 |
| `a` make | 2,866 | **1,954** | -912 |
| `a` break | 1,418 | **1,116** | -302 |
| Space make | 2,652 | 1,954 | -698 |
| `m` make (last row) | 2,910 | 1,954 | -956 |
| Left Shift make / break | 1,382 / 1,382 | 1,130 / 1,130 | -252 |
| `A` with Shift held | 2,866 | 2,028 | -838 |
| `A` with Caps Lock | 3,012 | 2,088 | -924 |
| Caps Lock make | 1,544 | 1,256 | -288 |
| dead acute | 2,450 | 1,684 | -766 |
| `e` after the acute (composed) | 3,132 | 2,316 | -816 |
| `x` after the acute (two words) | 3,996 | 3,110 | -886 |
| AltGr+2 | 2,648 | 2,050 | -598 |
| Ctrl+C | 2,717 | 2,006 | -711 |
| left Alt+F (BIOS shortcut) | 2,098 | 1,544 | -554 |
| E0 prefix / grey Right | 1,116 / 1,270 | 946 / 1,020 | -170 / -250 |
| F1 / Enter | 1,932 / 1,858 | 1,400 / 1,400 | -532 / -458 |
| Backspace cancelling an accent | 1,688 | 1,414 | -274 |
| `q` on FR with a DOS (RAW) window in front | 1,466 | 1,146 | -320 |

Over the whole 149,564-case sample: **224.8M -> 169.5M clocks (-24.6%), no
case slower**; the smallest saving 114 clocks, the largest 988. A letter's
make and break together: 4,284 -> 3,070 clocks, ~0.9 ms -> ~0.64 ms of IRQ
time on the XT.

**klm_control** (task context, cold): not priced; every path is the same or
fewer instructions.

**PC1MOUSE.DRV, per tick** (the worker's own instructions, kernel calls
excluded, same model): still 796 -> **710** clocks, moving 838 -> 764, a
button held 800 -> 710. Attach: the same port operations in the same order;
its poll loops are unchanged.

**RAMDISK.DRV**: the package-verb dispatch one or two compares fewer
(cold). **CDROM.DRV**: no code on any path changed; the probe runs from the
end of the image.

**Disk work**: no `int 13h`, controller command, packet or XMS move added or
removed anywhere. A selected layout reads a 2,502-byte KEYBOARD.DRV where it
read 2,914 (5 sectors, was 6): one call either way on a contiguous file.

## 4. REFUSED

* **PC1MOUSE's counter reads by immediate port** (`out 0D4h, al / in al,
  0D5h` for `mov dx / out dx / inc dx / in dx`): -4 bytes, ~12 clocks a read
  faster - and ~2 clocks less between selecting the V6335D's register and
  reading it. No emulator models the chip and the field PC1 is the only
  check (SPEC.md 9.15): a timing change nobody can test, refused.
* **`loopnz` in p1_kbout/p1_kbin's waits** (-2 bytes each): the same poll
  count, ~6% less time per poll, so the bounded waits end sooner. A limit
  lowered.
* **A jump table for klm_control's verbs** (-2 bytes): stkbalance cannot
  follow its arms, so the control paths would leave the gate.
* **Every one of klm_control's tests short**: hold's `jae klm_bad` is the
  one remaining out-of-range pair (3 bytes, cold); the two other orders
  tried were 1 and 2 bytes larger.
* **KEYBOARD.DRV's 768 zero bytes** (the ASCII half of `klf_table`): the
  renderer indexes one contiguous table from FONT_FIRST to 255, so they are
  RAM either way; lz4 packs them to a few bytes.
* **Moving `klf_saved_seg`/`base` to a fixed low offset** (so a future size
  change would stop moving the resident immediate of section 5 item 1): it
  would have to sit before `klf_table`, which `kbdlayouttransitions` holds
  byte-identical across the wake repair - and klf_rearm rewrites it there.

## 5. WANTS THE OWNER

1. **The resident kernel moves by VALUE only, under the MODS_SIZE ruling's
   shape** (BRIEF section 1). `osapi_font_glyphs` (`kernel/kernel.asm`) reads
   `klf_saved_seg` - KEYBOARD.DRV's bss, `MODQ_IMG + 1` - as an immediate
   (`les dx, [es:klf_saved_seg]`), on every kernel; kern_mega reads
   `klf_saved_base` and `klf_saved_seg` with two `mov`s, and its
   `kl_control_x` stores `klm_scan` (the scan entry's offset) into `kl_rfp`.
   Any KEYBOARD.DRV saving moves them. `cmp -l`, base against tip at one
   build number: kern_big `kernel.bin` offsets 4598-4599 (0x15E9 -> 0x0F18),
   kern_small 4538-4539, kern_emu 4602-4603, kern_mega 4714-4715 and
   4719-4720 (`klf_saved_base`/`seg` 0x161D/0x161B -> 0x0F5A/0x0F58) and
   112633 (`klm_scan` 0x1B7 -> 0x177, the low byte) - and **nothing else**: same instructions, same
   lengths, every size and rung as it was. The coordinator's ruling names
   `MODS_SIZE`; this is the same kind (the module's own layout), listed here
   so the owner sees it used. **Without it** the bss could be padded so the
   three words keep their old offsets (and code padded before `klm_scan` on
   kern_mega): the claim would stay 11 granules (12 on kern_mega) and only
   the file's -412 would remain.
2. **klf_disable's `klf_active = 0` after its POPF** (section 2.6, `hctl`):
   the same order of writes; the store is no longer inside the CLI window.
   `klf_active` is read only by keyfont.inc's routines, all under the drawing
   lock klf_disable holds. -8 bytes.
3. **CDROM.DRV's attach now shrinks its own claim** (SPEC.md 51.1.3's
   mechanism, a second user): -512 bytes of RAM on a CD-ROM machine from
   attach on. Listed because the Drivers page's figure for a LOADED CD-ROM
   is now 16 granules where `DRVM_IMG_CD` (the not-loaded estimate) says 17,
   as it does for SOUND.DRV.

## 6. WANTS AN ABI BREAK

None. `rdabi.inc`, `rdpkg.inc`, `cdpkg.inc`, the driver header, every verb,
OSAPI_KEYBOARD and the module's header, entry table and stamp are as they
were.

## 7. CROSS-FILE

* **`DRVM_IMG_*` (`kernel/driver.inc`, the coordinator's): none moved.**
  PC1 1 (410 bytes), RAM 11 (5,401), CD 17 (8,209 at load). `drvmem` passes.
* **`tests/kbdlayouts.py`** (a soak row) named the old planes by offset
  (`klm_map_fr + scan*2`, `+ 87*4 + 0x0b*2`) for its three negative
  controls; `key()` now finds the byte through the image's own `klm_idx` and
  `KLM_KEYS` from the map, and refuses a scan that is not a translated key.
  The three offsets were read back out of the built image (section 2.6); the
  row itself was not run.
* **`util360.img`'s SYSCHECK.O88 +1 byte**: its system-file manifest follows
  every driver and module size (`tools/os88sysman.py`); nothing to do.
* **`klm_focus_owner`'s `mul` by WIN_SIZE** (~75 clocks a keystroke, once per
  window examined): a 24-byte table of window offsets (12 on kern_small)
  would take ~45 clocks off. Mine to take; not taken, bytes over clocks on a
  path already 30% faster. Priced for whoever wants it.
* **`stkbalance`'s two blind spots met here** (`tools/`, nobody's): an
  `%error` message naming a label makes the label an entry, and a global
  reached only by falling past a `db` skip reads as unreferenced. Both are
  worked round in the source; the tool's reading of `%error` lines could
  skip quoted strings.

## 8. ROWS TO RUN

| rows | what of this branch they reach |
|---|---|
| `kbdlayouts`, `kbdlayoutfont`, `kbdlayouttransitions`, `kbdlayoutat`, `kbdlayoutabort`, `kbdsettings`, `kbdsettings-small`, `kbdlayouttext-vga`, `kbdlayouttext-cga`, `kbdlayouttext-herc`, `kbdlayouthiber`, `kbdlayoutlegacy`, `kbdlayoutreal`, `vesakbd` | every KEYBOARD.DRV routine and table; `osapi_font_glyphs`' and kern_mega `kl_control_x`'s moved immediates (`kbdlayoutfont`, `kbdlayouttransitions`, `kbdlayoutreal`); `kbdlayouts` with its re-aimed negative controls |
| `pc1mouse` | PC1MOUSE.DRV's source shape (`t_pc1mouse.py`, read and kept) |
| `rdmount`, `thewire`, `thewirexms`, `fsclass`, `rdboot` | RAMDISK.DRV's package verbs (`RDPV_STATE`, `RDPV_MOUNT`, `RDPV_MOUNTC`) |
| `cdrom`, `cdromsim`, `cdromempty`, `megacdrom`, `win16mscdex`, `x3live386` | CDROM.DRV's attach and shrink, every verb after it |
| `drvmem`, `drvverb`, `megapkg` (fast, run in every `make`) | the Drivers page's figures, the verb tables |

## 9. LOOKED

One QEMU boot (CDROM.DRV is QEMU's: a 286 and an ATAPI drive), the
`cdromtest` gate disk and `build/cdfix.iso`, driven by a scratch script, not
the row: the CD-ROM row's `DRVR_PARA` **512 paragraphs (16 granules)**,
header word +4 = `cd_keep` (1F65h), the drive found at 170h unit 0 ("QEMU
DVD-ROM"), volume D:, and the CD's root and `DOCS` listed exactly as
`tools/os88cdiso.py` says they must. KEYBOARD.DRV and PC1MOUSE.DRV were not
booted: their module and driver bytes ran under the harnesses of section 2.6
on every kernel that builds them.

## 10. DEFECTS FOUND

None in behaviour. Three facts worth knowing:

* **Most of klm_scan's tests were NASM's out-of-range pairs**: an 8086 `jcc`
  past 127 bytes assembles as the inverse `jcc +3` and a `jmp near`, so every
  printable key took five TAKEN jumps through the modifier tests (and two in
  klm_translate). Nothing was wrong; it was slow. A disassembly showed it; the
  source does not.
* **The resident kernel holds KEYBOARD.DRV's layout** (section 5 item 1):
  every module change that moves the bss moves an immediate in
  `osapi_font_glyphs`; on kern_mega a change before `klm_scan` moves one in
  `kl_control_x`. Whoever sizes this module next will meet it.
* **ksp21's DEFECTS 2 is now moot in the module**: klm_control no longer
  tests a klf_enable refusal that could not happen.

## 11. NOT REACHED

* **klm_compose as a 5 x 14 matrix** over the letter list `aAeEiIoOuUyYnN`
  (70 + 14 bytes for 110, a letter scan instead of a pair scan): ~-15 bytes
  net of code, the same cost per composed key. Needs the generator and a
  dead-code index in klm_dead.
* **klm_store's first `klm_next` written in line**: +6 bytes, ~35 clocks a
  printable key faster.
* **RAMDISK.DRV, dsp1's queue** (`cdram.md` 10): the load-time values of
  `rd_extkb`/`rd_extb`/`rd_extpara`/`rd_sext` into the trailing zero run
  (file only), the error-tail triplets, the chain walkers, `rd_page_need`'s
  header tests. Not started. RAMDISK.DRV's attach-only code is far short of
  the 281 bytes a granule would need, so `DRV_H_KEEP` buys it nothing.
