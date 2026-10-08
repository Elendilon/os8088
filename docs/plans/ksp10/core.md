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

### batch 2 (big -27, small -24; running total big -126, small -83)

* loader.inc: ld_take's `.bad`/`.big` are near jmps to ld_hdr_size's
  identical pair (-2 net, both).
* sched.inc: task_yield moved beside sch_isr so its `jne sch_resume` is a
  SHORT `jne sch_isr.sres` (the ISR's own `jmp sch_resume`) where it was the
  5-byte inverted jcc (-3, both). Hot path got FASTER: unlocked yield 4
  clocks for the untaken jne + the same near jmp, where it was a taken short
  (16) over the near jmp; locked yield +15 (the extra jmp), the rare case.
* instance.inc: inst_park_mk tests in AH, not a second AX push (-3).
* loader.inc: ld_start's `.abort` block sits between step 9 and the re-home,
  so step 8's `jc .abort` is short (-3, both).
* instance.inc: inst_where - the caller instance's drive/dir (or the
  machine's), shared by inst_vol_enter and kernel.asm's osapi_file_here
  (-16, both).
* docs/INDEX.md regenerated: os88index lists this notes file under plans,
  and `make` fails docindex until it does.

### batch 3 (big -61, small -53; running total big -187, small -136)

* instance.inc: inst_vol_enter banks only AX, DX and the flags - inst_where
  keeps BX, and dsk_chdir_q clobbers the flags alone (disk_mount_x banks the
  rest itself): -10, both. It sits under EVERY file API call, so this is ten
  fewer push/pops on each one as well.
* memory.inc: unused banks - mem_avail_lvl_x's DX and DI (and SI on big),
  mem_hifit's DX, mem_regrow's BX (its ladder exit becomes plain pops),
  osapi_sys_snapshot_x's DX (-11 big / -9 small).
* memory.inc: mem_reloc_call's `cmp ah, MEM_LVL_TOP / jbe` was always true
  (the top is 0xFF): one compare, with an %error guarding the constant
  (-5, big).
* memory.inc: osapi_sys_kb_x stores all ten SK_ words in order through one
  stosw pointer, the heap figure before the claim sums (-24, both).
* memory.inc: mem_claim_1's head bound compares SI, not [mem_dma] (-2), and
  publishes the five record words through ES:DI with stosw (-6), both.
* instance.inc: the snapshot's idle-slot test as `inc bl / jz` (-1);
  inst_find_kind's `clc` after a falling-out-equal `jne` (-1). apps.inc:
  app_tmr_track's likewise (-1, big).

## REFUSED

* ct_cw_gfx_pen_cf / ct_cw_gfx_hline look dead from kernel/ (0 sites) but
  apps/os88ui.inc's kernel arm calls them: grep apps/ too.
* SPLCALL -> SPLGATE1 (11 bytes a site): the one resident site
  (disk.inc:1839) is `.cold`, and spl_gate is `.text`.
* KD_INIT dispatched far (would delete fm/tmr/bounce kinit thunks, 18 B):
  cp_kinit is `.text` near-ret, so it needs a 10-byte trampoline pair, plus
  9 bytes of far-pointer dispatch: +1 on big, worse on small.
* app_launch `.show`'s lock-or-not as pushf/popf: -1, not worth the read.
* inst_parksafe as an I_FLAGS bit (-11 big: 12 .bss, 4 in inst_alloc, +5
  in the setter): I_FLAGS IS SSI_FLAGS in the published snapshot (SPEC.md
  29.1.2), so a parksafe bit would leak into an ABI field documented as
  "bit 0 = minimized" for every running declared package.
* api_rxc/api_rsc/api_rn `call KERNEL_SEG:api_far` -> `push cs / call
  api_far` (-3): os88ovlchk judges api_far by its retf and refuses a near
  call to it; BLOBCALL (which it does understand) means an `.ovl` target.

* mem_pg_forget's BX bank (-2): ico_demote's header says it relies on
  mem_pg_forget having "banked the lot"; not proved for fmv_icostale.
* inst_icon_ptr's run expansion as `rep stosw` (-4) costs the ES = DS
  bracket it needs (+4).

## CROSS-FILE

* files.inc's two `call ct_cw_gfx_frame` (files.inc:7436, 7456) are the
  trampoline's only kern_big callers besides os88ui.inc's: recount with
  apps/os88ui.inc before retiring ct_cw_gfx_frame (2N-6 rule).
