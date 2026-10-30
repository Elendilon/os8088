# ksp15 agent "snd" - SOUND.DRV's resident keep under 6KB

Kernel size pass 15 (`docs/plans/completed/ksp15/BRIEF.md`). Assignment:
`drivers/sound/`, `snd_keep` (what a machine with no mixer keeps resident,
SPEC.md 34.15.1) from 6,392 to under 6,144; bonus `snd_keepmix` from 9,937
toward 9,216. Branch `ksp15-snd`, base `49ad5d67` (`e4896481` plus the brief).
Figures are ASSEMBLED bytes off the image and its symbol map
(`tests/unit/t_sndonce.py` prints the two keeps). **No kernel source changed**
(`git diff 49ad5d67 -- kernel/ drivers/os88drv.inc apps/os88api.inc` is
empty), so all four kernels are byte-identical to the base and no ABI moved.

## BASE AND TIP

| SOUND.DRV | base | tip | delta |
|---|---:|---:|---:|
| **`snd_keep`** (no mixer) | 6,392 -> 7KB claim | **6,106 -> 6KB** | **-286** |
| **`snd_keepmix`** (a mixer) | 9,937 -> 10KB | **9,551 -> 10KB** | **-386** |
| image (unpacked; the load claim) | 11,737 -> 12KB | 11,369 -> 12KB | -368 |
| `NOPICOMEM=1` `snd_keep` | 6,209 -> 7KB | **5,949 -> 6KB** | -260 |
| `NOPICOMEM=1` `snd_keepmix` | 9,754 -> 10KB | 9,394 -> 10KB | -360 |
| `NOPICOMEM=1` image | 11,224 -> 11KB | 10,864 -> 11KB | -360 |

The goal is met with 38 bytes to spare (`NOPICOMEM=1` 195). The bonus is not:
`snd_keepmix` is 335 bytes above 9,216, and WANTS THE OWNER 2 is the only
lever left that reaches it (the popup's 968-byte band).

Every other includer of a `drivers/sound/*.inc`:

| includer | includes | base | tip |
|---|---|---:|---:|
| `MIXER.O88` (`apps/mixer`) | `sndpkg.inc`, `apps/os88mixui.inc` | image 3,467 | **3,353** (-114: the rectangle table; its band stays 48 rows, bss 1,056) |
| `VIDSND.O88` (`tests/vidbench/vidsnd.asm`) | `picomem.inc` | 5,632 | 5,632 - same size, not byte-identical: the four attach-only tables moved inside `PM_ONCE`, which this package expands in place |
| `tests/picomem/sbhx.asm`, `vshx.asm` | `picomem.inc`, sb.inc cut by `tests/picomem.py` | - | assemble; the slice still finds `sbl_hook`/`sbl_cell` |
| MIDIRack, RealDMG, XTMP3 (all arms), the Mixer's verbs | `sndpkg.inc` only | - | byte-identical (`sndpkg.inc` untouched) |
| `SOUND.DRV`'s HMA image (`sound.hma.bin`) | all | - | builds (`make`) |

## TAKEN

Bytes are `snd_keep` / `snd_keepmix` (shipped build). Nothing below changes
what any machine does; hot paths are named with their cycles.

### Where code lives

* **An SB Pro stereo stream's mixer half into the MIXER's run** (`sb.inc`'s
  new `SBL_PRO` macro, expanded by `sound.asm` after `mixer.inc`):
  `sbl_pro_st`, a new `sbl_pro_end` (the 0Eh restore `sbl_stop_stream` had
  inline) and `sbl_m0e`. **-112 / +6.** It is the only code in `sb.inc` that
  touches the CT1345, and it is reached only for a stream verb 11 accepted as
  stereo on a DSP 3.xx - which `snd_sb_pub` allows only with `[mix_kind]` = 2
  - and, for the restore, behind `[sbl_pst]`, which only `sbl_pro_st` sets.
  SPEC.md 34.15.1 already argued exactly that guard for the call; the code
  simply had not followed the argument. `t_sndonce`'s doors are now
  `sbl_hw_start` (the caller) and `sbl_stop_stream`, where `sbl_pro_st` was.
* **The PicoMEM's attach-only tables past `snd_keepmix`**: `pm_irqs`,
  `pm_pmirq`, `pm_sbports` and `pm_irq` are read and written only by `pm_init`
  and `sbl_f_irqdisc`, both inside `DRVV_ATTACH`. Into `PM_ONCE`. **-18 / -18.**

### Folds and shapes

* **`opl_keyon` halves 6208 instead of reading `opl_fmax`**: block b's
  ceiling is exactly `6208 >> (7 - b)` for all eight (an `%rep` asserts it
  against the formula); the scan runs down from block 7 and stops at the
  smallest block that holds the frequency. Checked exhaustively against the
  table for every frequency 19..6208. SI is no longer used, so its push/pop
  went. **-23 / -23.** Not hot: once a note.
* **Verbs 5 and 6 are one body** (`sbl_v_rw`, BP = 1 for a stage): the range
  check on the pool's side, the chunk loop once, the stage the no-exchange
  case. DX was never touched and is no longer saved. BP is free - the kernel
  banks it round every driver call and `sbl_stream_op` already spends it.
  With `sbl_v_close` taking `sbl_v_feed`'s stale exit: **-41 / -41.** Cycles:
  per 512-byte chunk a stage adds `or bp, bp` / `jnz` taken (~19) and a read
  that plus the exchange (~65) and an `mov es, [sbl_poolseg]` it used to do
  once - under 1% of the ~6,800-cycle chunk it is inside, and neither verb is
  on a listed hot path (the per-sample copy is `sbl_fill_guard`'s, untouched).
* **The two opens share `sbl_rec`** - the record's eight common stores,
  `pm_rchk`, the new generation and the publish, last, as both did. **-28 /
  -28.** Once an open.
* **A grant's owner rides in `sbl_gr_act`'s low byte** (100h + instance, so
  the word is never 0 - the kernel's 0FFh included): `sbl_gr_inst`'s 16 bytes
  of state and the claim's extra store went. Every reader already compared
  the owner as a BYTE behind the word's own test. **-25 / -25.**
* **`sbl_cell` masks the line** for both its callers (`sbl_hook`,
  `sbl_unhook`), dead `CLC`s after a `TEST`/`XOR`/equal compare (`sbl_dsp_wr`
  - one fewer instruction on every DSP write, ISR included - `sbl_f_reset`,
  `mpu_put`, `mpu_v_open`, `mpu_v_close`, `sbl_v_feed`, `sbl_v_grant` x2,
  `sbl_v_read`, `sbl_dma_get`), `sbl_v_busy` as `mov al, [sbl_str_act]` /
  `cbw` (the byte is 0 or 1 at every store), `sbl_hcheck`'s equal compare as
  the CF = 0: **-28 / -28** together.
* **`opl_owned`** compares the owner byte in place (no AX) and shares its
  tail; **`opl_claim`** and **`opl_regok`** share theirs (`CLC_OR_STC`):
  **-13 / -13.**

### The mixer's run (`snd_keepmix` only)

* **`os88mixui.inc`'s ten fixed rectangles are a table** of five-byte rows
  drawn in the same order where `MX_RECT` was twenty bytes of stores and a
  call each: **-114** (and -114 of `MIXER.O88`). The five thumb rectangles,
  whose x is a variable, keep the macro. *(`apps/os88mixui.inc` is in no
  agent's row - taken here, being SOUND.DRV's popup.)*
* **SOUND.DRV's band is 44 rows** (`MIXUI_H`, default 48): the last ink is
  the long scale marks' row 43, and `volume_popup` fills the panel white
  before the first band and draws nothing else inside it, so rows 44..47 were
  white written over white. **-88.** `MIXER.O88` keeps 48 - its window's
  ground under those rows is not proven white, so it is not touched.
* **`mix_get`'s two identical `and` arms** are one, and **`mix_to_pct`**
  rounds in byte arithmetic (`mul dl`, `adc ah`) - the quotient is <= 100 for
  every max and value the masks allow, checked exhaustively: **-16.**

**Pixel identity** of the two `os88mixui.inc` changes is checked by a
scratch unicorn harness that runs the base's and the tip's `mixui_draw`
(`SOUND.DRV` images, the kernel's API page as `retf`s and a fixed random
font behind `OSAPI_FONT_GLYPHS`) for every value 0..100: the tip's 44 rows
equal the base's first 44, and the base's rows 44..47 are all white
(181 inked bytes in the band, so the comparison is not of two blanks).

## REFUSED

* **`sbl_arm_half` through `sbl_dma_auto`** (~-25): it is the DSP 1.x's
  re-arm from INSIDE the block ISR - the "audible gap mitigation" - and the
  call, `sbl_dma_auto`'s own push/pop and the register moves are ~60 cycles
  added to that gap. Hot path.
* **A `min(CX, SBL_DCHUNK)` helper for the four chunk loops** (~-12): two of
  them are `sbl_fill_guard`'s, the path that moves every sample, and
  `sbl_live`'s header already refuses a call there.
* **`OS88_RET_LADDER`** (`drivers/os88drv.inc`): most of the driver's pop
  shapes need a rung that is not labelled, and labelling one is an edit to
  the frozen, fingerprinted SDK (`tools/abilock.py`); the one labelled rung
  (`os88_r_si`) has too few users below `snd_keep` to pay its six bytes.
* **`MIXUI_H` 44 for `MIXER.O88`**: see above - not proven pixel-identical.

## WANTS THE OWNER

1. **A third keep point: the PicoMEM's and the MPU-401's resident halves
   after the core** (`[core] [PicoMEM] [MPU] [mixer] [attach]`, `DRV_H_KEEP`
   the end of the last run the attach found a user for). On a machine with
   neither - most of them - `snd_keep` would fall by ~330 more (PicoMEM 123:
   `pm_runaway` 76, `pm_tick` 47; MPU 215: `mpu_put`, `mpu_hush`, the four
   verbs and `mpu_nomidi` - `mpu_detach`, `pm_tickpub` and `pm_rchk` stay
   resident, `snd_pkg` tests `[mpu_base]` for the four verbs, and the
   `call pm_runaway` in `sbl_tick` takes the `[pm_up]` test that is inside
   it today, so a PicoMEM machine pays nothing). It is not a functionality
   change, but it is a new layout rule beyond SPEC.md 34.15.1's two, with
   `t_sndonce` to extend, so it is put rather than taken. Not taken: this
   pass's figure stands without it.
2. **The popup's band in the popup's own claim** (the bonus): `volume_band`
   is 968 bytes of every mixer machine's keep, used only while the popup is
   up - and the popup already claims a heap block for the screen it covers.
   Composing there takes `snd_keepmix` to ~8,600 (9KB). It needs
   `apps/os88gfx.inc` to compose into a band in ANOTHER segment (today every
   `GFXE_BAND_BUF` access is DS-relative), a shared-library change across
   every package that includes it - which is why it is a proposal. Without it
   the bonus is 335 bytes away.
3. **(alternative to 2) order the runs `[core] [mixer] [MPU] [PicoMEM]`**: an
   SB Pro (a mixer, no MPU, no PicoMEM) would keep ~9,190 (9KB) - and a
   machine with an MPU and no mixer would keep the whole mixer (+3.4KB). A
   trade between machine classes, so the owner's.

## WANTS AN ABI BREAK

None.

## CROSS-FILE

None. `apps/os88mixui.inc` (no agent's row) is taken above, and said so.

## ROWS RUN

Once, after the last code commit, `python3 tools/os88test.py soak -k ...
--marty-jobs 1`: **23 ok, 0 failed** - `sndonce`, `sndkeep`, `sndmove`,
`sndplay`, `recorder`, `sndfmt`, `sndcap`, `ringmove-audio`, `sbirq5`,
`picomem`, `pmlib`, `pmmarty`, `mpupin`, `midirackmpu`, `midiracksb`,
`midirackfm`, `fmpatch`, `fmrefuse`, `gorillasmusic` (which breakpoints
`opl_keyon` and reads the pitch), `covoxdrv`, `mixerhost`, `mixervga`,
`mixersb16`. The first pass SKIPPED `pmlib`/`pmmarty` (no `libpmhost` in a
fresh worktree: `tools/picomem/build.sh` built it) and FAILED `mpupin` on a
missing `mcopy` (`apt-get install mtools`); all three passed on the re-run.
`t_sndonce` was broken on purpose (`sbl_hw_start` out of its doors) and
named `sbl_pro_st` as the reach past `snd_keep`. `make`, `make small`,
`make emu` and `make mega` build; the fast tier is 66/66. No row reaches an
SB Pro's stereo stream (MartyPC's card is a DSP 2.01, QEMU's an SB16), so
`SBL_PRO` is verbatim code moved, its guard argued above and held by
`t_sndonce`. Not run: `waverackrec` (2,400 s declared; its record path is
`recorder`'s verb 4 and verb 6, which ran).

## DEFECTS FOUND

* `sbl_v_open_in`'s header says "`sbl_total` holds the capture CAPACITY";
  nothing in verb 4 writes `[sbl_total]` since SPEC.md 34.6.5 retired the
  grant capture, and nothing reads it for an input stream (verb 1 refuses
  one, the ISR's input leg and verb 9 read `[sbl_consumed]`). A stale
  comment, not a defect in behaviour; left for the next edit of that header.
