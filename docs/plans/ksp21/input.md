# ksp21 agent "input" - the keyboard, mouse, serial and font files

Kernel size pass 21 (`docs/plans/ksp21/BRIEF.md`), section 2's `input` row:
`mouse.inc`, `mouproto.inc`, `vmmouse.inc`, `vmmabi.inc`, `keyboard.inc`,
`keymaps.inc`, `keyfont.inc`, `keyfont-data.inc`, `serial.inc`, `font.inc`.
Branch `ksp21-input`, base `3fc4e9d09` (the brief). Figures are ASSEMBLED
bytes, `tools/kernsize.py --json` absolutes; resident = `.text` + `.bss` +
`.cold` + `.lowbss` + `.vgabuf` + `.vga` (+ `.mega` on kern_mega).
Per-routine figures are `tools/os88rdiff.py kernel` spans.

Outside the row, edited and said so: `tests/unit/t_pc1mouse.py` (a source
reader of `kbm_isr`, taught the new spellings and broken on purpose),
`tests/megaseg.txt` (kern_mega's allowance over kern_big, 3,778 -> 3,784
with its reason, items 10, 16 and 17) and SPEC.md 9.14 (item 10's body, stated
there).

## BASE AND TIP

| kernel | `.text` | `.bss` | `.cold` | resident base | resident tip | delta |
|---|---:|---:|---:|---:|---:|---:|
| **kern_big** | 39,510 -> 39,446 | 4,973 -> 4,972 | 37,830 -> 37,807 | 90,225 | **90,137** | **-88** |
| kern_small | 29,101 -> 29,067 | 2,843 -> 2,842 | 20,860 -> 20,837 | 55,672 | **55,614** | **-58** |
| kern_emu | 39,756 -> 39,688 | 4,973 -> 4,972 | 37,830 -> 37,807 | 90,471 | **90,379** | **-92** |
| kern_mega | 45,275 -> 45,217 | 5,204 -> 5,203 | 53,078 -> 53,046 | 134,293 | **134,202** | **-91** (`.mega` 24,800 unchanged) |

`.lowbss`, `.vgabuf`, `.vga` and `.mega` are unchanged on all four.
`KERN_SIZE` crosses no rung on any kernel (kern_big 95,744; kern_mega's
conventional 61,952 of 68,096). Module images: KEYBOARD.DRV, SERIAL.DRV and
every other image are unchanged in size and code (nothing in `.modq` or
`.mods` was edited; only the build number in their headers moves). `make`, `make small`, `make emu` and `make mega` build at
the tip; the fast tier is green at every commit (54 passed, 4 skipped for
want of the C toolchain and pagedesk), `hotpar` and `stkbalance` among it.
`tools/stkbalance.py` over the kernel corpus, base against tip: 0 unbalanced
paths on both (5,153 entries walked at the base, 5,152 at the tip).

## TAKEN

Per kernel, big / small / emu / mega, in bytes of the section named.

| # | item | big | small | emu | mega | hotness, cycles |
|---:|---|---:|---:|---:|---:|---|
| 1 | **kl_control_x in one pass of tests** (`.cold`): `[sch_cur]` read once into CL; QUERY, SET 0, RELEASE and CANCEL go straight to the module-present test; only SET 1..4 and HOLD load, so `.call` asks SET alone (the second `or ah, ah` went); the key map armed through `rmk_8` with AL = SET rather than AL = 0 under a push/pop (kbd_down past its arm is a pure query of scancode AL, the answer unread); the RAW record by `mov al, I_RECSZ / mul dh`; the three refusals one `cbw / stc` tail, placed mid-routine so kern_mega's SEG_REAL block no longer pushes them out of short reach (they were `jcc/jmp near` there) | -23 | -23 | -23 | **-32** | a control call (task context): every path fewer instructions |
| 2 | **osapi_keyboard's refusal becomes RAW**: an owner the public cell refuses (DH >= INST_MAX on HOLD, RELEASE, RAW, >5) is handed on as `mov al, KBDV_RAW`, whose own owner test answers AX = 1, CF = 1 on every task - the refusal was a second copy (`mov ax, 1 / stc / jmp`) | -4 | -4 | -4 | -4 | an API call |
| 3 | **kbm_isr's self-chain refusal shares the eaten byte's EOI tail** (`KBM_EAT`, a macro expanded once per kernel): `.selfchain`'s `mov al,20h / out 20h,al / pop ds / pop ax / iret` IS the 61h-pulse path's last seven bytes. kern_small also loses its `jmp .chain` - the macro there goes after the chain, so the keypad-5 press falls into `.chain`. The PARITY nop before `mou_isr` goes with the odd byte | -8 | -10 | -8 | -8 | **H2, per key: every path the same instructions and the same taken jumps** (the self-chain `je` is backward now); kern_small's keypad-5 press -15 clocks |
| 4 | **kbm_isr's PC1 filter as one range test**: `mov ah, al / sub ah, KBM_PC1_L / cmp ah, 2 / jbe .pc1eat` for three compares and three `je` (AH is free in the `mem` expansion); the three codes' adjacency is a `%error` in the macro | -2 | 0 | -2 | -2 | H2 on a PC1 only (skipped elsewhere): 12 bytes -> 10, fetch-bound ~48 -> ~40 clocks a key |
| 5 | **font_char tests the index once**: `sub al, FONT_FIRST` at the top and one unsigned compare against the span (an unprintable character wraps above every live span, 223 the highest); the `sub` at `.rows` goes. On SEAMCUT kernels font_ch_hi takes the index (`[font_span]`, `FONT_SEAM_x - FONT_FIRST`) and font_ch_spill adds FONT_FIRST back for EXTD.DRV's cut (+2) | -2 | -4 | -2 | -2 | **H2, per glyph: a compare and a not-taken branch fewer** (~8 clocks, 4 bytes of fetch) |
| 6 | **font_ch_hi falls into font_ch_drop**: spill and seam moved above it, so the seam arm's last `jmp short` goes; the live CP850 path is not moved | -2 | 0 | -2 | -2 | the seam arm only (cold) |
| 7 | **font_run_cell tests the index once** (item 5's form against `[font_span]`); on kern_small its `.outq` jump comes into short reach too | -4 | -5 | -4 | -4 | **H2, per cell: faster** (as 5) |
| 8 | **font_run_scell keeps the character on the stack** (AX pushed last, `pop ax / push ax` before font_char), so `[font_rn_ch]` goes from `.bss`; the band built from two byte loads (`mov dl,[r0] / mov dh,0 / add bx,dx / mov dl,[rn]`) for the word load and byte add-with-carry | -5, -1 `.bss` | -5, -1 | -5, -1 | -5, -1 | H3 (a cell a clip region cuts): ~5 bus clocks fewer of ~5,000 |
| 9 | **font_run_x's prologues** (kern_big's paths): `[font_rn_pl]` = 0 and `[font_rn_k7]` = x & 7 as one word (`mov ah, cl / and ax, 0700h`, ZF still the phase's for NOUNAL); both dither seeds test CL (the run's x) for `[font_rn_k7]`; the planar prologue's xm/bm built in DX (banked at `.plok`, next written as VGA_GC; `.plno` pops it back) and stored as one word; the planar dither's dt/xm one word; `.rm`'s phase test `test cx, 7` and `.rmu`'s shift `and cl, 7` for the CS-relative cell reads. Adjacencies asserted | -24 | 0 | -24 | -24 | **per run (H2): every one fewer bytes and clocks**; the row loops (H1) are untouched and stay at an EVEN shift (`.p1` -12, `.rmpx`/`.rmrow` -14, `.rmurow`/`.rmumid` -16) |
| 10 | **osapi_mouse_rel through CS** on the real-mode kernels (three `cs:` prefixes for `push ds` / KDS / `pop ds`), and the PARITY nop after mou_p2_off with its odd byte. kern_mega's CS is a read-only selector in protected mode: it keeps both, so tests/megaseg.txt's figure rises with the reason (3,778 -> 3,784 with 16 and 17: kern_mega did not grow, kern_big shrank under it) | -2 | 0 | -2 | 0 | an API call: ~35 clocks faster |
| 11 | **mou_lockon tail-jumps to mou_p2_off**, its keep's `ret` being mou_newround's just above (`je mou_newround.ret / jmp mou_p2_off`) | -1 | 0 | -1 | -1 | once a session |
| 12 | **mou_byte's drain clear by `dec byte [mou_drain]`** (1 there: `.drain` read it non-zero and every writer stores 1), and the PARITY nop after mou_apply with it | -2 | -2 | -2 | -2 | the drain window's close only |
| 13 | **font.inc's two pads in one parity run**: font_ink's (VGA kernels) and fnt_unlazy's (every kernel) both sat between the same pinned routines, so on the VGA kernels they cancelled; both go there, kern_small keeps fnt_unlazy's | -2 | 0 | -2 | -2 | never executed |
| 14 | **kbd_down's arm stores BH** (`mov [kbd_dnmap+bx], bh`, BH = 0 while BX counts 15..0) and **kbm_poll0 tail-jumps past kbd_ovspend's `push ax`** (`kbd_ovspend.banked`), whose `pop ax` is its own bank - the pair keeps kbm_isr..mou_isr even | -2 | -2 | -2 | -2 | the arm once; a modal poll ~27 clocks faster |
| 15 | **vmm_poll banks AX..BP through kent_bp** (kern_emu's VMware pointer): the ladder's ~95 8088-cycles are tens of 386 cycles against the backdoor's trapping `in` | 0 | 0 | -4 | 0 | kern_emu, a hypervisor only: under 1% of a poll |
| 16 | **osapi_mouse's re-hook arm takes ES = 0 from DI** (`mov es, di` while DI is still 0) for `xor ax, ax / mov es, ax` - AX is popped or reloaded below; kern_mega loads MEGA_SEG0 either way | -2 | 0 | -2 | 0 | inside an FSX bracket only: faster |
| 17 | **mouse_unhook's ES = 0 out of BX's zero** (`xor bx, bx / mov es, bx`); AX is written before it is read, as its kern_mega arm already said | -2 | -2 | -2 | 0 | at reboot |
| | **total** | **-88** | **-58** | **-92** | **-91** | |

### Hot paths

* No khp1 pick was reverted or made slower. Every H1/H2 change above is the
  same instructions (3), or fewer instructions and bytes (4, 5, 7, 9, 10):
  counted in the column, in the 8088's `max(clocks, 4 x bytes)` terms.
* `hotpar` green at every commit on kern_big and kern_small. Four PARITY pads
  went, each WITH its odd partner (3, 10, 12) or as a redundant pair (13);
  kern_emu's and kern_mega's hot routines (not gated) were checked against
  the base by the same table and every one keeps its parity.
* No `int 13h` path touched: nothing on the mount, listing, read-ahead,
  FAT-window, directory-write or loader path is in this row's files.

### Equivalence

Scratch unicorn harnesses against the BASE and TIP kernels' own assembled
bytes (scratch `nasm -f bin` + map at each commit), base against tip:

| harness | covers | kernels | cases | result |
|---|---|---|---:|---|
| `h_klctl` | kl_control_x and osapi_keyboard over AL 0..7/80/FF x AH 0/1/4/5/FF x DH 0/1/max-1/max/FE/FF x worker/UI x module present/absent x mod_need CF x module answer (gone, ok, bad, drop through kl_drop_x) x flags; kl_release_inst slots 0..13 | big, small | 38,568 each | identical registers, CF, IF, the inst_tab bytes and the call log (mod_need, rmk_8, KL_CMD with its AX and owner, mod_drop) - except the public refusal's undocumented ZF/SF/PF/OF/AF (6,720 cases; CF, IF, DF, AX identical) |
| `h_kbmisr` | kbm_isr and kbm_i15, every path: armed, mouse, PS/2 gate (64h), kbm_ivec 24h/54h, PC1 row, module eats or passes, self-chain, eight scancodes, KB_FLAG, AX | big, small | 24,576 / 12,288 | identical registers, frame flags, ports in/out, the BIOS call, kbm_p5, the map, kbd_ae - the ROM's int 09h call compared on AL only (AH there is the scan's, spent: kbm_shf clobbers it at the base) |
| `h_font` | font_char, font_run_cell, font_run_scell on CGA and Hercules, AL 0..255, both span sizes, font_ch_on, edges | big, small | 13,351 / 13,372 | identical framebuffer, registers, cells; flags differ only on REFUSED glyphs (font_char's and the scell's, which no caller reads: `add cx, 8` follows every font_run_scell) |
| `h_frx` | font_run_x end to end, mono (live and disabled, every phase) and planar (vid_planes = 4: both xm/bm cases, gfx_mono1 x gfx_dis), ports logged | big, mega | 2,000+ / 600 | identical framebuffer, registers, cells, port log; a planted `mov dh, 1` for item 9's `mov dh, 0` goes red (18 of 300) |
| `h_misc` | kbd_down (its arm), kbm_poll, kbm_pollm with int 16h, the module slots and snd_beep stubbed | big, small | 1,200 each | identical |
| `h_rel` | osapi_mouse_rel from a foreign DS, random cells and flags | big, emu | 2,000 each | identical, DS and flags preserved |
| `h_mou` | osapi_mouse (the re-hook arm: both lines, both ports, a stolen vector or not) and mouse_unhook (every base pattern, the PS/2 vector or not) with port I/O logged | big, small, emu | 600 each | identical registers, port log and IVT (our two ISRs compared by NAME: they moved) |

Proved by reading: mou_lockon's tail jump (mou_newround.ret is a bare `ret`),
mou_byte's `dec` (mou_drain's three writers store 1), the pad removals (each
never executed), font_ch_spill's `add al, FONT_FIRST` (EXT_FCUT takes the
character), vmm_poll's ladder (kent_bp pushes AX..BP in kret_es's order).

## REFUSED

* **kl_control_x's refusals by `db 3Dh` skips** (-2 more): os88ovlchk's rule 1
  refuses any data directive in `.cold`; the `jmp short .fail` form is taken.
* **kl_drop_x ending in kl_control_x's `.zero`**, **kl_release_inst through a
  `.cold` entry that sets DH**: each priced at +1 or +4, not taken.
* **mou_p2_byte's phase stores as `inc byte [mou_p2ph]`** (-2) and **mou_byte's
  `.cont` as `inc byte [bx+mou_phase]`** (-1): ~+4 clocks a byte on an H2 ISR.
* **kbd_ovflow's `inc byte [kbd_ovb]`**, **KBM_SCAN's `inc byte [kbm_p5]`**
  (-1 each): a flag that could reach 256 unspent and wrap to "no beep" / "no
  press". **kbd_down's `inc byte [kbd_armed]`** (-1): two racing arms leave 2,
  which KBDDIAG's 'I' row reads as bit 0. **kbd_ovflow's `.drained` store from
  AH** (-1): AH is the head's high byte, 0 only on a BIOS whose buffer sits
  where 40:1E's does.
* **kbm_i15 inside kbm_isr for a short `jmp .scan`** (-1): it would make
  kbm_isr's local labels kbm_i15's (and tests/kbd4f.py and os88intguide
  anchor `kbm_i15:`), and the head's `jne .chain` would be one byte out of
  reach anyway. **The two heads as one subroutine** (-2): +35 clocks a key.
* **osapi_key_map by a `cs:` source override** (8086: an interrupted `rep`
  with a prefix resumes without it) **or an unconditional kbd_down** (+~180
  clocks on the API that exists to be one call a frame).
* **The glyph index by `mov ah, 8 / mul ah`** (-4 a site): +45 clocks a glyph.
* **font_ch_hi's seam arm as `je .edgeok / jmp .chok`** (-4): in seam mode AL
  is only ever FONT_SEAM_A or _B (font_ch_seam's two callers), but the
  "anything else draws nothing" guard is a refusal path, and taking it out is
  identical by reachability, not by construction.
* **font_run_x's `jne .rmu` short**: still 136 bytes away after item 9.

## WANTS THE OWNER

1. **The keypad-5 press is eaten on kern_big, kern_emu and kern_mega since
   #371** (DEFECTS 1): **0 bytes to put back.** Expanding KBM_EAT after the
   chain on every kernel (kern_small's layout since item 3) lets the press
   fall into `.chain` as it did before #371; every consume path is a jump
   either way, and the sizes are identical. Not taken: it changes what the
   BIOS receives.

## WANTS AN ABI BREAK

None found. OSAPI_KEYBOARD, OSAPI_MOUSE_REL, OSAPI_KEY_MAP and the glyph
cells answer as before; `tools/abi.lock.json` is untouched.

## CROSS-FILE

* **`kernel/winmod.inc:538` (wm's)**: `sub dx, 7 / cmp [di+W_H], dx` assembles
  as `83 EA 07 39 55 08`, which mod_cfix's scan reads as `jmp far 0855:...`
  whenever `.cold`'s home is 0x0855 - `os88rom.py hma`'s proof refused this
  branch's build there mid-pass (WIN95.DRV +0x265). `add dx, -7` (`83 C2 F9`)
  is the same instruction and 0 bytes; the merged ladder lands wherever ten
  branches put it, so the coordinator should know the trap is there.
* **`kernel/extmod.inc`'s font_ch_cut (wm's)**: if EXT_FCUT took AL as the
  INDEX (its `sub al, FONT_FIRST` dropped), font_ch_spill's `add al,
  FONT_FIRST` goes: -2 resident on kern_big/emu/mega, -2 EXTD.DRV.
* **`kernel/instance.inc`'s inst_rel_rec (sys's)**: kl_release_inst banks AX
  only for ser_release_inst after it; called last, its push/pop could go
  (-2) - but the release order is SPEC.md 29.4's.

## ROWS (named, not run - the coordinator's union)

| rows | what of this pass they reach |
|---|---|
| `kbdlayouts`, `kbdlayouttransitions`, `kbdlayoutabort`, `kbdlayoutat`, `kbdlayoutfont`, `kbdlayouthiber`, `kbdlayoutlegacy`, `kbdlayoutreal`, `kbdlayouttext-cga`, `kbdlayouttext-herc`, `kbdlayouttext-vga`, `kbdsettings`, `kbdsettings-small`, `vesakbd` | kl_control_x, osapi_keyboard, kl_release_inst (1, 2), the CP850 glyph paths (5, 6, 7) |
| `kbd4f`, `kbdburst`, `kbdpreempt`, `kbmadopt`, `keymap`, `dosaltenter`, `pc1mouse` | kbm_isr and kbm_i15 (3, 4), kbd_down's arm (14), osapi_key_map's neighbours. `pc1mouse` (a source reader, 0.1 s) was taught and broken on purpose here, red each time |
| `mouseup`, `mousess`, `mouwheel`, `mouerrq`, `mouresume`, `serlease`, `curshape`, `wheel`, `inputchk`, `dosmouse`, `dosmouevt`, `wirefleetsystem` | mou_byte's drain (12), mou_lockon (11), the pads around the mouse ISRs (3, 10, 12) |
| `ps2mouse`, `p2restore`, `p2hiber`, `wheelps2` | mou_p2_off's neighbours, mou_lockon's PS/2 tail (11) |
| `vmmouse` | vmm_poll (15, kern_emu) |
| `dispfsx`, `dispfsxcga`, `dispfsxherc`, `dispmodex`, `wireballmono` | osapi_mouse's re-hook arm inside a bracket (16) |
| `dispreboot`, `p2hiber`, `mouresume` | mouse_unhook (17) on the restart and hibernate sweeps |
| `fonts`, `glyphcost`, `fontpick`, `fontview`, `win1bpp`, `deskflash`, `disptext`, `runclip`, `runclipcga`, `dispseam`, `dispstrad` | font_char, font_ch_hi/spill (5, 6), font_run_cell (7), font_run_scell (8), font_run_x's prologues (9) |
| `small128` | kern_small's kbm_isr (3) and font paths booting on 128KB |
| `api-abi` (fast, run) | the OSAPI cells' shapes |

One boot to look was not taken: every drawing change is proved identical on
the framebuffer by `h_font` and `h_frx` on both 1bpp geometries and the
planar arm.

## DEFECTS FOUND

1. **Keypad 5 is consumed on the OS88_DRIVERS kernels** (introduced by #371,
   `d4349a0a4`): after `mov byte [kbm_p5], 1` KBM_SCAN falls into `.pc1eat`,
   which acknowledges the byte and ends IRQ1 itself (or clears the int 15h
   frame's CF), so a BIOS that delivers keypad 5 (SeaBIOS) never sees it.
   SPEC.md 9.6.4's design is that the BIOS gets it and kbm_key's guard keeps
   one press from being two; 9.15 says ordinary scancodes keep their path.
   kern_small chains as before (its `jmp .chain`, now its layout). Not fixed:
   WANTS THE OWNER 1, at 0 bytes.
2. **kl_control_x loses a module refusal's CF**: after `call far
   [KLFP+KL_CMD]`, CF = 1 with AL != 0 leaves by `or al, al`, which clears
   CF. Unreachable today - klm_control's klm_bad is never reached through
   kl_control_x (every refusal it could give is validated first, and
   klf_enable cannot fail) - and kept exactly as it was; whoever gives the
   module a verb that can fail must fix the shape first.
3. **`os88rom.py`'s cfix proof is a gate on the ladder's VALUE**: a size pass
   that moves `.cold`'s home can trip it through an unrelated module's bytes
   (CROSS-FILE 1). It worked as designed - it refused to stamp a ROM that
   would have been re-pointed wrongly.
