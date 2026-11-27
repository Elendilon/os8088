# Driver size pass 2: sound (`drivers/sound/`, SOUND.DRV)

Agent **sound**, branch `dsp2-sound`, cut from `1b01907f1` (the brief's
commit on `aa6b428`). Two code commits, both in `drivers/sound/` (the
second with SPEC.md's two figures): `504c3ac52` attach-only, `392bb8bd0`
resident; then this note and `docs/INDEX.md`.

The target was what #363 (ESS AudioDrive DMA routes at attach, SPEC.md
34.5.8) and #408 (the auto-init probe and the DMA lab, 34.5.9) added since
dsp1's tip `e7668bd73`: `sb.inc` +483 lines, SOUND.DRV +700 image / +569
file. Every routine either added or changed was read first:
`sbl_ess_setup` and its four helpers, `sbl_f_aiprobe` and its silence,
`sbl_find`, `sbl_arm_half`, `sbl_dma_auto`, `sbl_dleft`, `sbl_halt`,
`sbl_go_on`, `sbl_stop_stream`, `sbl_v_open`'s two new tests,
`snd_hwinfo`, the three DMA cells and the ISR's new lab hook (empty in the
shipped build). The sweep after it took dsp1's `sbl_hdma_auto` item,
`sbl_hdma_find`, and the one primitive every DSP byte goes through,
`sbl_dsp_wr`.

**The speed story first, because #363 made the hot path slower.** It
routed the single-cycle ISR's re-arm (`sbl_arm_half`) through
`sbl_dma_auto`, the change dsp1 refused for exactly that reason, and made
the 8237's ports variables: **+288 cycles (+14%) on every single-cycle
block IRQ** - which since #408 is every block on an STPC board as well as
on a DSP 1.x. The tip takes back 239 of the 288 and keeps DMA 3, smaller
than the base by 29 resident bytes (section 2.1); the other 49 cost 42
bytes and are the owner's call (section 4).

## 1. BASE AND TIP

Assembled in this worktree, the Makefile's `nasm` line per arm
(`-DPICOMEM`, none, `-DPICOMEM -DSNDDIAG`, `-DDRV_ORG=0xC000`); file is
`os88drv.py --compress-if=lz4`. The base is `1b01907f1`'s build, which
matched `build/sound.bin`, `build/snddiag/sound.bin` and
`build/sound.hma.bin` byte for byte. "Keep" is what RAM holds after the
attach's shrink (`DRV_H_KEEP`, SPEC.md 34.15.1); the kernel rounds it up to
512.

| build | image | file | `snd_keep` | `snd_keeppm` | `snd_keepmpu` | `snd_keepmix` |
|---|---:|---:|---:|---:|---:|---:|
| shipped (PicoMEM), base | 10,965 | 9,458 | 5,820 | 5,936 | 6,108 | 8,541 |
| shipped, tip | **10,835** | **9,354** | **5,791** | 5,907 | 6,079 | **8,512** |
| delta | **-130** | **-104** | **-29** | -29 | -29 | **-29** |
| `NOPICOMEM=1`, base -> tip | 10,440 -> 10,310 (-130) | 8,980 -> 8,910 (-70) | 5,779 -> 5,750 | (no run) | 5,951 -> 5,922 | 8,384 -> 8,355 |
| SNDDIAG (`build/snddiag/sound.drv`) | 13,055 -> 12,933 (-122) | 10,837 -> 10,738 (-99) | 7,779 -> 7,750 | 7,895 -> 7,866 | 8,067 -> 8,038 | 10,500 -> 10,471 |
| HMA copy (`sound.hma.bin`) | 10,965 -> 10,835 | - | (the same, + C000h) | | | |

By commit: the attach-only batch (`504c3ac52`) is image -99, file -81,
keep 0; the resident batch is image -31, file -23, keep -29 (which is -37
of bytes saved and +8 spent on `sbl_dsp_wr`'s fast path, section 2.1).
The image moves no granule: **`DRVM_IMG_SND` stays 22** (10,835 rounds to
11KB; 21 would want 10,752, 83 more), and every keep figure stays in its
granule (12 / 12 / 12 / 17), as at the base: no rung crossed either way,
and the bytes are the figure. Where each run ends against its next step:
`snd_keep` 5,791 is 353 under 6,144; `snd_keepmix` 8,512 is 192 under
8,704.

**Every kernel carries the same bytes**: kern_mega's disks ship
`build/sound.drv` itself, and kern_emu's `build/emuk/sound.drv` is its own
assembly of the same source, byte-identical (10,835 / 9,354; `make -j2
emu` and `make -j2 mega` both pass at the tip). **kern_small carries
none** (SPEC.md 34.0): 0.
Clusters: SOUND.DRV is 19 clusters on `os8088-360.img` at base and tip
(9,458 -> 9,354; 18 would want 9,216); `os88diskuse --diff`: +0 free
across every 360KB image, no other file moved. The 720KB, 1.2MB, 1.44MB
and kern_mega system disks carry the same 104 bytes less.

## 2. TAKEN

Hot means dsp1 BRIEF 1's hot paths. Every item is held to the base by the
differential harness (section 2.3); the cycle figures are section 2b's.

### 2.1 Resident (the run every SB machine keeps)

| item | where | image | hot? | how shown |
|---|---|---:|---|---|
| `sbl_arm_half`: the half's offset branchless (`neg al / cbw / and ax, SBL_HALF` - derived from the geometry as before), computed straight into AX, no DX bank (`sbl_dma_auto` keeps DX) | sb.inc | -7 | **hot** (the single-cycle ISR's re-arm): 1,480 -> 1,227 cycles with the two items below | unit, stream |
| `sbl_dma_auto`: the address parked by two `xchg ax, dx` instead of `push ax / pop ax`; the address port one word load (the cell is a word, below); the mode byte OR'd with the channel and no `and al, 0FCh` first - every caller's mode ends in `01` (49h, 55h, 59h; the lab's is forced to 01 by `snddiag.inc`), and `01 \| 1` is 1, `01 \| 3` is 3 | sb.inc | -4 | **hot** (above): 417 -> 384 | unit (all six mode bytes, both channels, PicoMEM's mask both ways, IF both ways), stream, essdma's exact write list read |
| `sbl_dmaport` a WORD whose high byte nothing writes: `mov dx, [sbl_dmaport]` replaces `mov dl / xor dh, dh` in `sbl_dma_auto`, `sbl_dleft` and the probe; `sbl_pageport` moved to the end of the state block for it, so the three channel cells are three bytes again where they were and every hot word cell after them keeps its alignment | sb.inc state | +1 | `sbl_dleft` is **hot** (verb 9, kern_mega's direct-ring ISR): 178 -> 174 | unit, stream; essdma's byte puts and gets of the cell still read the low byte |
| **`sbl_dsp_wr`: the first status read taken alone** - a DSP is ready at once nearly always, and then CX is never banked or loaded and the ready case falls through; the loop after it reads the SBL_POLLS - 1 left, so a DSP that never goes ready is asked exactly 4,096 times, as before | sb.inc | **+8** | **hot, faster at bytes' cost**: 229 -> 174 cycles a DSP byte; the re-arm sends three | unit (write-busy 0..5,000 polls, timeouts), stream (`sb1-busy`), attach |
| `sbl_hw_start_in`: the block length into BX after the DMA call, no DX bank | sb.inc | -4 | record open | unit, stream |
| `sbl_hdma_auto` (dsp1's queue): the mask byte is `[sbl_hdma]` itself (5/6/7 are their index \| 4), the port by `add dl`, DH already 0 for the page register | sb.inc | -4 | 16-bit start: 564 -> 552 | unit, stream (`sb16-4.05`) |
| `sbl_v_open`: **an unreachable test removed** - the format branch's `cmp byte [sbl_auto], 0` (#408). A format is held only when verb 11 took it, verb 11 takes no format whose cap is unpublished, and `snd_sb_pub` publishes `SND_CAP_STEREO`/`_PCM16` only with `[sbl_auto]`, which the attach settles before the first publish and nothing writes after. The rate test #408 added beside it is reachable (a rate above 22,222 is the package's to ask) and stays | sb.inc | -10 (7 + a jump the layout made short) | open path | stream (formats on `ess-dma3-stpc`, `stpc2.01`: refused by verb 11 with 2 exactly as at the base) |
| `snd_hwinfo`: BL and BH one word load (`sbl_dma` follows `sbl_irq`, `%if`-pinned), the version one word and an `xchg`, and the refusal `or bh, bh / js` (BH is 1, 3 or FFh, only the last with bit 7) | sound.asm | -7 | cold | unit (base 0, DMA 1/3/FFh), attach (HWINFO after every attach and tier change) |
| `sbl_attach`'s 65,536-poll reset through `sbl_f_reset0` (below) | sb.inc | -2 | cold | attach |
| `sbl_f_reset0`: `xor cx, cx` falling into `sbl_f_reset`, for the five 65,536-poll resets | sb.inc | +2 | - | attach |

Resident total **-29** (-37 saved, +8 spent on the `sbl_dsp_wr` fast
path). The `sbl_dsp_wr` item alone
costs bytes; it is taken because it is the primitive every DSP byte goes
through, on the re-arm's own path three times a block (brief 0.2: faster
at a few bytes is welcome; both figures above).

### 2.2 Attach-only (handed back after the attach on every machine)

| item | image | how shown |
|---|---:|---|
| `sbl_ess_setup` 316 -> 264: one word compare for DSP 3.01; the delay folded into the identity read it always precedes (`sbl_ess_din`, 11 bytes for `sbl_ess_delay`'s 12, one `in` fewer at each of four sites); the part test `or al, 1 / cmp al, 69h`; the port's two bytes read into AX and checked there (`test al, 7`, two compares, then one `xchg`); `mov ax, 7504h`; the refusal tail one unsigned compare (Audio 1 can never be 1 there, since 1 is always usable, so {0, 2, the disk's 3} is `<= 3`); the publish only for DMA 3 (DMA 1 is what `sbl_find` set a moment before) in one word store and one byte | -53 (with the helper) | attach (every route pair x part x disk x stuck register) |
| `sbl_f_aiprobe` 244 -> 208: AX loaded with `[sbl_auto]` and `[sbl_irq]` as one word for the two early outs (`sbl_find`, the one caller, clobbers AX, so the probe no longer banks it); **the slave-PIC arm removed - unreachable**: every line `sbl_irq` can hold is one of `sbl_dsc_irqn`'s {7, 5, 3, 2} or FFh, which the probe has already left on (`sbl_cell`, resident, has assumed it all along); the master's mask by `in al, 21h / out 21h, al`; the samples counted in CX by `loop` (DI not banked) and the count tested by `or ah, al` (AL stays the next flip-flop clear's value, as it was); the 1/2/3 answer, which only `SDG_SET` reads, assembled only with SNDDIAG (`%ifdef` blocks the debug-disk strip removes whole, so `t_debugdisk` holds) | -36 | attach (every machine, STPC, no TC, 120 faulty 8237s - the sample loop's every exit) |
| `sbl_find`: the three cell stores as one word and one byte | -4 | attach; essdma's zeroed-cells check read |
| `sbl_hdma_find`: no `[sbl_hdma] = 0` (the image's zero state at the one attach that runs it, dsp1's `opl_kind` argument); the read-back as one word compare | -6 | attach (`sb16/hdma5..7, 0`, with and without a second 8237) |
| `sbl_f_probe`'s slow retry through `sbl_f_reset0` | -2 | attach |

Attach-only total **-101**.

### 2.3 How equivalence was shown

A scratch differential harness (unicorn 2.1.4, not committed) runs the base
and the tip image under SS != DS, with device models for the 8259, both
8237s (including an STPC that does not reload its count, and a fault mode
that answers the signature with a random bit flipped), the SB DSP and its
mixer, the ESS configuration port, an OPL2/OPL3 with its timer, LPT
latches, the kernel's far cells and its rare door, and real interrupt
delivery (the F2h discovery). It compares the whole port trace in order,
every kernel call with its inputs (pointers by symbol name), every verb's
answer, every register and flag a routine returns, and the driver's state
by symbol name, the IVT and the heap claims. The auto-init probe's 8237
address is the run's own silence, so it is compared as its XOR with the
silence's first paragraph, which is layout-free.

| suite | what | result |
|---|---|---|
| `t_attach` | 642 machines (no card, OPL2/3, DSP 1.05/2.01/3.02/3.01/4.05/4.13 at 220/260 on IRQ 7/5/3/2, XT disk on IRQ 5 on an 8088 and a 286, STPC, no TC, no IRQ, a slow DSP, a write-busy DSP, a dead E1h, no mixer, kern_mega, SB16 DMA 5/6/7/none with and without a second 8237, 120 faulty 8237s, ES1868/ES1869/other with every Audio 1/Audio 2 route pair, a stuck route register, seven config ports, three wrong audio bases) x 3 sequences (ATTACH; ATTACH, HWINFO; ATTACH, HWINFO, TIER off, HWINFO, TIER on, HWINFO, READY, TIER Covox, TIER on, DETACH) | **1,926 runs, 0 differences** in the shipped, `NOPICOMEM` and SNDDIAG arms |
| `t_stream` | 12 machines (incl. ESS on DMA 3, STPC on DMA 1 and 3, kern_mega's CPU_F_PM, a busy DSP, a heap that refuses) x 150 sequences of 40: grants, stages, opens of every kind at every rate edge, formats, feeds, status, verb 9 with the 8237 part way through, pauses, closes, record opens, block IRQs (single-cycle re-arms, direct rings, underruns), the worker's pass, ticks, tier changes, releases | **1,800 sequences, 0 differences** in each of the shipped, `NOPICOMEM` and SNDDIAG arms |
| `t_unit` | the 13 changed resident routines called directly from random registers and state, 200 each | **2,600 calls, 0 differences** - every register, CF, ZF and IF |

Broken on purpose, each goes red: `jbe .refuse` made `jb` (45 ESS runs
differ), the sample's `or ah, al` made `or ah, ah` (81 faulty-8237 runs),
the DMA mode's channel OR made `or al, 1` and a stray `inc dh` in
`sbl_hdma_auto` (317 of 1,300 calls).

## 2b. SPEED

Every path changed that anyone waits on. **Counted**: the instructions each
path actually executed, recorded by the harness under unicorn, fed in order
(branches taken as they were) to `tools/x3cyc.py`'s clock-stepped 8088
model (BIU/EU, the 4-byte queue, DRAM refresh - calibrated to PERFORMANCE.md
Part 2), extended in a scratch copy with `in`/`out`, `pushf`/`popf`, `iret`
and the far cells. A model and not a MartyPC measurement: no design here
turned on a number, so the one MartyPC session was the boot to look
(section 8).

| path (8088 cycles) | dsp1 tip | base | tip | |
|---|---:|---:|---:|---|
| **ISR, single-cycle block re-arm** (DSP 1.x, an STPC board) | 1,990 | 2,278 | **2,039** | -239 (-10.5%) |
| `sbl_arm_half` (the re-arm itself; also `sbl_go_on`'s and the start's) | 1,191 | 1,480 | **1,227** | -253 |
| `sbl_dsp_wr`, DSP ready (every DSP byte) | 229 | 229 | **174** | -55 (-24%) |
| ISR, auto-init underrun (D0h) | 1,315 | 1,315 | **1,260** | -55 |
| `sbl_halt` (D0h; the watchdog, verb 10) | 413 | 413 | **358** | -55 |
| `sbl_hw_start`, auto-init 8-bit (a stream's start) | 2,818 | 2,936 | **2,545** | -391 |
| `sbl_hw_start`, single-cycle | 2,192 | 2,480 | **2,102** | -378 |
| `sbl_dma_auto` (every DMA start) | 302 | 417 | **384** | -33 |
| `sbl_hdma_auto` (a 16-bit start) | 564 | 564 | **552** | -12 |
| `sbl_dleft`, 8-bit (verb 9; kern_mega's direct ISR) | 124 | 178 | **174** | -4 |
| verb 9 (`sbl_v_ppos`, auto-init) | 836 | 882 | **878** | -4 |
| ISR, direct ring, kern_mega (`sbl_dleft`) | 1,318 | 1,358 | **1,354** | -4 |
| ISR, auto-init block (the common case) | 758 | 758 | 758 | 0 |
| `sbl_halt` / `sbl_go_on`, high-speed | 112 / 158 | 128 / 162 | 128 / 162 | 0 |

The re-arm's 2,039 cycles are ~430 us at 4.77 MHz, IRQ to the 14h's last
length byte and the `iret`: at 11 kHz the gap between single-cycle blocks
is ~4.7 samples, and the tip takes ~0.5 of one back. The attach: identical
port traces, so identical hardware time; CPU between the accesses -964
cycles on an SB 2.01, -1,211 on an ES1868 (its setup 7,312 -> 6,996), and
-27,216 on an STPC (its probe's 2,048 samples 374,639 -> 348,135). **No transfer
call** of any kind is added or removed anywhere: the port traces are the
base's, and no path here does an `int 13h`.

The hot routines' PARITY, for a 16-bit bus (no effect on the 8088): the run
from `sbl_hw_start` through the whole SB state block is at an EVEN shift
(`sbl_isr`, `sbl_halt`, `sbl_go_on`, the stream verbs, `sbl_tick`, the
refill and EVERY SB word cell keep the base's alignment - which is why
`sbl_pageport` moved, section 2.1); `sbl_dsp_wr`, `sbl_arm_half`, the OPL
write path and `snd_pkg` are at an odd one (-7 / +1), and so is everything
past the SB state (`mix_kind`, the PicoMEM's tick, the MPU-401's output, the
mixer: -29), by the dmaport word's one byte. `sbl_dmaport` itself is a word
at an even address. The base had already moved most code against dsp1's
tip.

## 3. REFUSED

| item | bytes | why |
|---|---:|---|
| `sbl_arm_half` sending its length through `sbl_dsp_wr3` (BX already holds SBL_HALF - 1) | -10 | +80 cycles on the re-arm, which is the gap |
| `sbl_dma_auto` clobbering DX and `sbl_arm_half` clobbering AX/BX/DX (no callers need them) | -4, -54 cycles a re-arm | `tests/essdma.py` holds both to "every register kept but the documented outputs"; a contract change would loosen a row |
| the DMA cells initialised in the image, `sbl_find`'s stores gone | -11 more | essdma zeroes the cells and requires `sbl_find` itself to set DMA 1 ("never channel 0"), and SPEC/sound.asm's state rule is that no cell starts non-zero |
| a mask cell (`sbl_dmam` = channel \| 4) | -5 resident, -8 cycles a mask | essdma runs `sbl_dma_auto` straight after `sbl_ess_setup` with no `sbl_find` and would read a zero mask unless `sbl_ess_setup` published DMA 1 too (+5 attach): about nothing net |
| the count port in the cell instead of the address port | +1 | -1 in `sbl_dleft`, +1 each in `sbl_dma_auto` (the re-arm's path) and the probe |
| the probe writing its silence over attach-only code that has already run | -17 image | +~5 file: 31 bytes of 80h pack to almost nothing, the code to write them does not |
| `sbl_ess_setup`'s 60h/61h checks as one word compare | -4 | reads 61h after a 60h mismatch: a port access the base does not make |
| `out dx, ax` for the ESS index/data pairs | -4 | two byte cycles on an 8088, but not the same bus shape on a 16-bit machine's bus controller |
| `sbl_f_irqdisc` | ? | `tests/sbirq5.py` and `tests/picomem.py` cut it out of `sb.inc` and run the slice (soak rows): not provable here without them |

## 4. WANTS THE OWNER

1. **The re-arm's DMA programming written in `sbl_arm_half` again**
   (channel-generic: the cells, as `sbl_dma_auto` does): **+42 bytes
   resident** (image +42, file +14, every keep figure +42, no granule
   crossed) for **-141 cycles on every single-cycle block** (2,039 ->
   1,898 - faster than dsp1's 1,990). It is what dsp1 had before #363
   shared the routine. Measured on the scratch build, harness 0
   differences. Not taken: 42 bytes on every SB machine is more than "a
   few", and the tip already recovers 239 of the 288 #363 cost.

No wording, limit, probe or behaviour changed; no granule moved.

## 5. WANTS AN ABI BREAK

None. `sndpkg.inc` is untouched; the package verbs, the driver header, the
DSV table and the SNDDIAG record are as they were.

## 6. CROSS-FILE

- **`DRVM_IMG_SND` (`kernel/driver.inc`) stays 22**: the image is 10,835,
  ceil / 512 = 22. Nothing for the coordinator to change.
- **`tests/essdma.py` stubs `OSAPI_CPU_INFO` at `0060:0155`**
  (`CPU_INFO = 0x0060 * 16 + 0x0155`), but the SDK's cell is
  `KERNEL_SEG:0x0101` since #365's flag day, and the shipped driver calls
  `9A 01 01 60 00` (two sites, base and tip alike). So every essdma leg
  that reaches `sbl_irq5_taken` (every ESS setup case) runs into zeroed
  memory at `0060:0101`: **the row very probably fails at the base** - a
  pre-existing defect, section 9. The fix is that one constant, read from
  the SDK rather than typed. Not mine to edit (a soak row, and not a
  figure of mine).
- **The Makefile's NOPICOMEM comment** says "there is no DMA choice -
  sb.inc programs channel 1 and no other", stale since #363 (channel 1 or
  ESS channel 3, SPEC.md 34.5.8). A comment; 0 bytes.
- **Attach-only code handed back, priced** (dsp1 BRIEF 0.2): SOUND.DRV
  already gives it back (`DRV_H_KEEP`, 34.15.1); the tail past
  `snd_keepmix` is now **2,323 bytes** (base 2,424).

## 7. ROWS TO RUN

All soak unless named. **The ESS and probe paths**: `essdma` (and see
section 6/9: it is expected to need its CPU_INFO cell fixed first),
`snddiag`, `snddiag-vga`, `snddiag-cga`, `sndonce` (the runs' layout:
`sbl_f_reset0` is resident and named from attach-only code, allowed),
`sndkeep`, `debugdisk` (the new `%ifdef SNDDIAG` blocks in the probe are
whole blocks the strip removes), `sbirq5`, `picomem`, `pmlib`, `pmbox`,
`pmbox2`, `pmmarty`, `dossnd`, `dosirq`, `hmadrv`, `hma286`, `hmapool`,
`megasndup`, `megahma`. **The DMA, DSP-write and ISR paths**: `sndplay`,
`sndfmt`, `sndfmtmarty`, `sndcap`, `recorder`, `sndmove`, `audhand`,
`audhuge`, `audholdgap`, `sbrate286`, `vidsnd`, `vidsound`, `vidrmbsnd`,
`vidrmbtwice`, `vidrmbsnd286`, `megasndword`, `megasbhold`, `megasbgap`,
`x3mega`, `midiracksb`, `midiracksbmem`, `midiracksbrate`, `midirackmpu`,
`ringmove-audio`, `ringmove-tracker`, `apspkcard`, `mixersb16`,
`mixervga`, `mixercga`, `mixerherc`, `mixervesa`, `mixerhost`, `fmrefuse`.
**Build**: `buildmatrix`; full tier `megapkg`; fast tier `drvmem` (passed
in every `make`).

Every harness suite was re-run at the final tip (`392bb8bd0`'s bytes) in
all three arms: attach 1,926 / 1,926 / 1,926 runs, stream 1,800 / 1,800 /
1,800 sequences, unit 2,600 calls - 0 differences anywhere.

## 8. LOOKED

One MartyPC boot at the tip, `os8088-360.img` on
`os8088_5150_herc_sb_gla` (the boot sniff mounts SOUND.DRV, SPEC.md
51.3.1), the driver's cells read off the guest by the build's own map:
attached (`sbl_up` 1, hooked, the IRQ 7 vector at its `sbl_isr`), DSP 2.01
at 220h, auto-init KEPT by the probe (MartyPC's 8237 reloads), DMA 1 with
address port 0002h and page 83h, mixer 1, `DRV_H_KEEP` = `snd_keepmix`
(8,512), image 10,835. Then stopped (and its boot-cache holder killed).
The boot ran the build before `sbl_pageport` moved to the end of the state
(the same bytes but for where that one cell lives; the harness, not a
second boot, holds the move).

## 9. DEFECTS FOUND

- **`tests/essdma.py`'s CPU_INFO stub is at a retired cell** (section 6):
  found by reading, not fixed (a soak row I may not run, and the fix is
  only "obviously right" once it is run). The coordinator's final pass will
  see it.
- **SPEC.md 34.5.9 says a probe-failed card refuses stereo and 16-bit
  formats with err 7**: the verb 0 test that would have said so could not
  be reached (section 2.1) - such a package gets **err 2 from verb 11**,
  which refuses the format because its cap is unpublished, exactly as at
  the base. A contract sentence, so not moved; the owner's to reword.
- **sound.asm's `snd_keepmix` banner said "~1.3KB of zeros ship"**; it is
  ~240 bytes (a 192-byte and a 46-byte run). Fixed, comment only (dsp1
  noted it and left it).
- SPEC.md's two stale figures (34.5.9's probe size, 34.15.1's image size)
  updated to the tip's.

No functional defect found in the code read.

## 10. NOT REACHED

- `sbl_v_open`'s six `test byte [sbl_oflags]` after `.irqchk` held in BP
  (dsp1's queue, ~-3: `test bp, imm16` is one byte shorter, less the load).
- `mix_icon`'s invert-draw-invert (dsp1's queue, ~-3).
- `snddiag.inc` itself (the debug disk only; its record is SNDDIAG's ABI).
