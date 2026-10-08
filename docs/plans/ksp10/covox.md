# Kernel size pass 10 - agent "covox": notes

Files: kernel/ctrl.inc, kernel/snd.inc, drivers/sound/{sound.asm,covox.inc,
sndpkg.inc}. Special job: the Covox Speech Thing (#229, fe9a559), which had
never had a size pass - +292 CTRL.DRV (big) / +258 (small) and +259 of
SOUND.DRV's assembled image at that commit.

## TAKEN

### Batch 1 - the Covox, both halves (no resident byte moves)

kern_big and kern_small `kernsize` sections: +0 / +0 (all of it is CTRL.DRV
and SOUND.DRV).

| artefact | base | batch 1 | delta |
|---|---:|---:|---:|
| CTRL.DRV kern_big (plain) | 11,450 | 11,301 | -149 |
| CTRL.DRV kern_small (image) | 4,621 | 4,490 | -131 |
| SOUND.DRV sound.bin | 6,721 | 6,637 | -84 |
| SOUND.DRV image (drv) | 6,529 | 6,445 | -84 |

CTRL.DRV (kernel/ctrl.inc):
* `cp_snd_lptok` deleted: a Covox port is `cp_snd_rowok`'s entry
  CPS_NROW + n (= its tier SND_RT_LPT + n), the table grown by 3 bytes and the
  row shortcut skipped for a port (+4).
* `cp_snd_radios`: ONE loop over the seven glyphs (rows step down, ports step
  across); the port's dot is "the Covox row owns the dot and this glyph is
  [snd_route]".
* `cp_snd_paint`: labels through a `CPSTAGEX` table instead of a four-arm
  ladder; CX/DX stepped rather than recomputed by `mul`; the port loop runs BX
  on from the rows, the digit staged from 'LPT' + ('1' - CPS_NROW).
* `cp_snd_click`: the tier row by one divide instead of four compares (guarded
  by %if on the band geometry); the port path's `cmp`+`sub` folded; `.got`
  shared by the label's first-answered search; "already a Covox that sounds"
  is `cp_snd_row == 3`; the Test button's out-of-range `jg .done` (a relaxed
  5-byte jcc) goes to a near `.tout`.
* `cp_snd_row`: [snd_route] loaded once; LPTDAC tested as a byte.
* `cp_snd_tiers`: its fourth entry was never read (row 3 branches to .lpt
  first) - gone.
* NOT Covox, same file: `cp_vid_click` had a relaxed 5-byte `jl .rows`; the
  radio rows now sit between the button and the desktop row, so every jump is
  short and the `.donej` trampoline is gone.

SOUND.DRV (drivers/sound/):
* `cvx_latch` written in line in `cvx_probe` (its one caller) as a two-value
  loop (AAh xor FFh = 55h, SF ends it); the verdict is CF and the restore path
  keeps it, so no pushf/popf; cvx_ports stored unconditionally (the base or 0
  via `sbb/and`); the range test `cmp dh, 4`; loop ends on the tier bit's SF;
  the "none answered" CF is one `cmp byte [si+DSV_TIERS], 10h`; ES not saved
  (drv_stamped restores it). Ends by falling into `snd_upnm`.
* `snd_upnm`: the MPU-401's and the Covox's "first one up names the row" tail,
  shared.
* `cvx_tier` became `snd_tier`'s tail; the tier rides the stack instead of
  `[cvx_ask]` (byte gone); index through DI (NOT BX: drv_tier_x reads the row
  through BX after the call - the first version clobbered it and covoxdrv
  caught it); a non-Covox tier reads cvx_ports[-1], a never-written zero.
* `snd_tier`: `cmp ah, SND_RT_SB / je .want` replaces the two-compare
  `>= LPT` / `>= SB` ladder (identical for every AH).
* `cvx_v_info`: `cmp ax, 1` gives CF for zero.
* `inc byte [drv_up]` where it is known 0.

### BUG FIXED (its own paragraph in the commit)

`snd_entry`'s DRVV_READY jumped to `.nosb` - written when that label was the
end of attach. The MPU-401 (34.13) and Covox (34.14) probes were later added
BELOW it, so every load re-ran both at READY: the MPU's reset and UART
command sent again with [mpu_base]/[mpu_own] cleared and re-found, and the
three LPT latches written again. READY now jumps to `.ready`, past the
probes, which is what its comment always said. 0 bytes.

## REFUSED

* SOUND.DRV: dropping the Covox's DSV_NAME ('Covox' + the store, ~11 bytes):
  nothing in the kernel reads DSV_NAME today, but it is a published cell.
* SOUND.DRV: cvx_tier re-reading the BIOS table at 0040:0008 instead of
  keeping cvx_ports (~2 bytes net): a BDA that changed after attach would
  change which port is the DAC.
* SOUND.DRV: the `jmp short $+2` I/O delays in the latch test (8 bytes): a
  timing change on fast ISA machines.

## CROSS-FILE

(none yet)
