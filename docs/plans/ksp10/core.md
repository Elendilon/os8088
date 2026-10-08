# ksp10 agent "core" - notes

Files: kernel/kernel.asm, memory.inc, sched.inc, instance.inc, apps.inc,
loader.inc, cpudet.inc. Figures are `kernsize` section deltas against the
blessed baseline at 833f13e4 (big / small).

## TAKEN

### batch 1 (big -99, small -59)

* memory.inc, mem_cp_walk: the "keep the longest run" compare was written
  after both mem_cp_gap and mem_cp_tail calls; it is now the tail of
  mem_cp_sub, their shared body (-7). `.barrier`'s fill-point advance is
  `.stay`'s sum with DI = the claim's own base (-10). mem_cp_walk's
  `mov byte [mem_wpin],0` off the zeroed CX (-1). (COMPACT: kern_big only.)
* memory.inc: mem_hifit `mov word [mem_skip],0` off the zeroed SI (-2);
  mem_bpara `sub si,2` -> two `dec` (-1).
* memory.inc: mem_movable_x shares mem_free_x's exits (the same
  pushf/si frame), mem_free_x moved above it (-6, big); mem_reown_x shares
  mem_free_owner_x's `.done` (-3).
* memory.inc: mem_owned_kb on mem_sum_kb's frame and tail (-5).
* memory.inc: mem_owner_of_x walks with mem_next (-8). BEHAVIOUR NOTE: the
  counted loop matched a FREE record (MC_SEG 0) for BX = 0 and answered its
  stale owner; the header always said CF = 1 "no claim starts there". BX = 0
  reaches it from mem_sum_kb (an instance-slot-0 owner word through
  drv_owns_seg_x), where a stale driver segment in a free record could have
  filed slot 0's claims under System. Now it answers the header.
* kernel.asm: api_cpname - the `push cs / pop es / mov di, api_name` four
  of the five api_copyname callers wrote ahead of it (-15 .text).
* instance.inc: inst_seg_parked's two arms work in the DI it already banks
  and share one exit (-7).
* instance.inc: inst_wchk answers "a LIVE owned window" - inst_of_win and the
  I_STATE test were written after it at both callers (-10).
* instance.inc: app_launch `or [W_FLAGS], al` (byte), I_KIND+I_TASK one word
  store (-5).
* instance.inc: inst_unwin - the destroy, clear and sweep both teardowns
  wrote out (-8).
* sched.inc: sch_dphex2's nibble via `add 90h/daa/adc 40h/daa` (-2).
* apps.inc: app_ball_fill sets its own black (-5); app_ball_step's two
  `neg` one (-4). kern_big only.

## REFUSED

* ct_cw_gfx_pen_cf / ct_cw_gfx_hline look dead from kernel/ (0 sites) but
  apps/os88ui.inc's kernel arm calls them: grep apps/ too.
* SPLCALL -> SPLGATE1 (11 bytes a site): the one resident site
  (disk.inc:1839) is `.cold`, and spl_gate is `.text`.
* KD_INIT dispatched far (would delete fm/tmr/bounce kinit thunks, 18 B):
  cp_kinit is `.text` near-ret, so it needs a 10-byte trampoline pair, plus
  9 bytes of far-pointer dispatch: +1 on big, worse on small.
* app_launch `.show`'s lock-or-not as pushf/popf: -1, not worth the read.

## CROSS-FILE

* files.inc's two `call ct_cw_gfx_frame` (files.inc:7436, 7456) are the
  trampoline's only kern_big callers besides os88ui.inc's: recount with
  apps/os88ui.inc before retiring ct_cw_gfx_frame (2N-6 rule).
