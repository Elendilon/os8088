# ksp10 agent "hw" - fsx, vidsel, viddet, xmem, hiber/hb*, clone, compress, extmod, vmmouse

Appended as decided. Bytes are `kernsize`'s section deltas at each batch.

## TAKEN

### Batch 1

| where | what | big | small |
|---|---|---:|---:|
| fsx_run | release loop `mov cx, INST_MAX` -> `mov cl` (CH = 0: the door refuses CX >= 8, the fence clobbers DX/DI only) | -1 text | -1 |
| fsx_mode .modex | four `mov dx, 3xxh` -> `mov dl` (DH stays 3) | -4 text | 0 (GFX_VGA) |
| fsx_mode .fill | `mov al, ch / mov ah, FSXR_SIZE / mul ah` -> `mov al, FSXR_SIZE / mul ch` | -2 | -2 |
| fsx_mode .f1 | TEXT80 on Hercules: B800h -> B000h is one BYTE store of the high byte | -1 | -1 |
| fsx_wait/fsx_insync | the retrace timeout moves INTO fsx_insync (ZF = timed out, CF = not in retrace); both phases are `call/jcc`, insync loses its push/pop AX | -9 | -9 |
| fsx_page | Mode X start address: 19,200 = 4B00h, so the high byte is `page * 4Bh` (8-bit mul) and the low is always 0 | -6 | -6 |
| fsx_page | `mov dx, 3B8h` -> `mov dl`; both arms `jmp short fsx_wait.vsync` (the `.sync` near-jump trampoline is gone, the wait shrank into reach) | -2 | -2 |
| vid_ac_pal | two `mov dx` -> `mov dl` | -2 | 0 |
| vid_span_one | `cmp ax,dx / jbe .no` -> `cmp dx,ax / cmc`: the fit still falls through, now 2 clocks not 4 | -1 | 0 |
| vid_disp_planes | `mov cx,1 / cmp / jne / mov cl,4` | -1 | 0 |
| vid_setmode | Hercules arm `mov dx, 3B8h` x2 -> `mov dl`; mode 12h arm VGA_SEQ -> VGA_GC is `mov dl` | -3 | -2 |
| vid_text | `mov dx, 3BFh` -> `mov dl` | -1 | -1 |
| vid_apply | the six display-extent stores are one two-pass axis loop (lodsw/stosw) | -10 | -10 |
| hb_ok_x | the string chosen directly (`mov bx` writes no flag), no reason round-trip through AL | -10 cold | n/a |
| xm_free | its `stc/ret` refusal is xm_alloc's (`.stc` one byte below xm_alloc's `xor ax,ax`) | -2 | n/a |
| xm_copy | ES*16 as one `mul` instead of two shift pairs (286+ only reaches it) | -5 | n/a |

Batch 1 total: kern_big .text -50, .cold -10 (sum -60); kern_small .text -35.

## REFUSED

* **fsx_mine's range test** (~6 bytes): deliberately kept, its own header says why
  (a sentinel landing in [sch_cur] would grant a bracket to nobody).
* **vid_pop8 -> kret_es** (~6): refused by its own header - vid_setmode/vid_text run
  from the splash before the ladder at the end of `.text` is resident.
  **vid_mono_text -> kret_es** (-2) is refused for the same reason: vid_text calls it.
* **vid_6845_prog as word OUTs** (-2): `out dx, ax` to 3B4h is two byte cycles on
  the 8088 bus, so it is probably equivalent, but it changes the bus pattern to a
  real MDA/Hercules 6845 for two bytes. Not worth the question.
* **vid_apply: fold the m1/m8 copy into the axis loop** (-2 at best, +1 once the
  second copy's DI has to be reloaded): wm8 has no y twin (writing one is vid_pw).
* **vid_disp_init's .jout trampoline**: every reordering measured is the same 26 bytes.
* **hbf_paint/onclick/kinit thunks** sharing a body: they differ in a table index,
  and a register to carry it costs what it saves.
* **clo_fnbuf to .bss**: same resident bytes either way.

## CROSS-FILE

(none yet)
