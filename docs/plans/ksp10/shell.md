# ksp10 / shell - notes (agent "shell")

Files: kernel/ui.inc, driver.inc, assoc.inc, dock.inc, dockmod.inc,
desksc.inc, clock.inc, clockw.inc, blank.inc, shutdown.inc.
Base `833f13e4`. Bytes are `kernsize` section deltas, kern_big / kern_small.

## TAKEN

### batch 1 - ui.inc (big .text -86, small .text -85)

* `ui_bill`: the start stamp is banked in the payload's own two stack slots
  (`xchg ax,[bp+8]` / `xchg dx,[bp+4]`) instead of two pushes, and the pops
  come back in one run with no `add sp, 6`. -4, and 4 bytes shallower at the
  moment a package callback runs. Per callback, not per pixel.
* `ui_drag_ph8` inlined into `ui_drag_phase`, its one caller, as
  `jns / add ax,7 / and ax,-8` - truncation toward zero by biasing a
  negative delta by 7, where it was negate-mask-negate. -11. Plus the
  `mov ax,[si+W_X]` that reloaded the value just stored (big only) -3.
* `ui_dispatch`: `cmp ax,0xFFFF` -> `inc/jz/dec` (-1); the handler resolve
  reads the set's segment only on the AM_ONCMD arm and drops a `push di` that
  ui_bill clobbers anyway (-3).
* `ui_cmd .close` runs through `ui_lcall` and shares `.launch`'s
  `jmp snd_beep` (-5). ui_cmd and ui_dispatch now say they clobber BP
  (ui_dispatch already did, through ui_bill's handler).
* `ui_reboot_post`: one store of `NOFLUSH - borrow` (-3).
* `ui_tm_open`/`ui_svc_open` store `[ui_desc]` themselves; the SI save
  wrapper and `ui_so_call` are gone (-5 big, -7 small).
* `ui_sys_open`: `[ld_said]` read-and-cleared with `xchg`, leaving AH = 0 for
  the index, and `jnz .back` (-6). `ui_tm_back` and `ui_sys_find` drop
  register saves their one caller (ui_sys_open, which banks everything) does
  not need, and ui_tm_back tail-jumps (-5, -7).
* `.evloop` loads CX/DX = EV_A/EV_B once for every event species; the three
  handler copies are gone and `.wake` takes `mov si, cx` (-18).
* `ui_raise`: the "front it unless it is frontmost" question the content
  press, the title press and the right button each spelled out (17 bytes a
  copy) is one routine (-15 net).

## REFUSED

## CROSS-FILE
