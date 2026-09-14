; =============================================================================
; kerndos/kdshim.inc - what the kernel's disk layer NAMES and this root answers
;
; docs/plans/KERN-DOS-PLAN.md 5 is the question this file is the answer to, and
; its size is wave 3's headline: a shim near the size of a purpose-written FAT
; reader means the reuse is not paying.
;
; FOUR KINDS OF ENTRY, and they are kept apart on purpose because only the
; third is real work:
;
;   1 CONSTANTS the kernel's other files define and these three read.
;   2 MACROS whose bodies are about a machine kern_dos does not have - the
;     pointer, the progress widget, the busy bar.
;   3 STUBS: a `ret` where the behaviour belongs to a layer that is not here.
;     Each one is a DECISION and carries the § that made it.
;   4 STATE: the .bss bytes those files read and write.
; =============================================================================

; --- 2: the macros ----------------------------------------------------------
; There is no ARROW here - nothing of kern_dos draws on the screen at all, the
; program owns every pixel - so every cursor bracket compiles away exactly as
; `NOCURDISK` makes it in the kernel. **THE POINTER ITSELF IS NOT MISSING and
; this comment used to say it was carried from `mouse.inc`, which was never
; true**: INT 33h is served by `kerndos/kdmouse.inc` off the port os8088
; settled on (SPEC.md 96.45), and `mouse.inc` is not included by this root.
%macro CURXFER_ON 0
%endmacro
%macro CURXFER_OFF 0
%endmacro
%macro CURBAR_ON 0
%endmacro
%macro CURBAR_OFF 0
%endmacro

; The loading screen is stage 2's and there is none here: kern_dos is JUMPED
; INTO by SPEC.md 87.5's stub, not booted (KERN-DOS-PLAN 4.2), so every
; progress call the mount makes compiles away.
%macro SPLCALL 1
%endmacro
%macro OVLCALL 1
%endmacro

; --- 1: the constants -------------------------------------------------------
; Each is a number kernel/memory.inc, mod.inc or files.inc defines and the
; disk layer reads. They cost nothing and are here rather than %included
; because pulling those three files in is exactly what this root is avoiding.
MEM_P_FATW_N equ 8              ; one FAT window per volume (SPEC.md 18.8.4)
MOD_NENT     equ 8              ; kernel/mod.inc's table, which diskw.inc
FM_NENT      equ 4              ; sizes a run of words against

; ...and the rest, LIFTED VERBATIM from the files that own them rather than
; re-derived, because a constant re-typed is a constant that drifts - which is
; tests/unit/t_mirror.py's whole subject one layer along. Every one is a
; number the disk layer reads and no other file here defines.
; --- from kernel/driver.inc ---
DRVC_DISK   equ 2
DRVC_FILE   equ 5
DRVC_MAX    equ 5
DSV_BLK     equ 16
FSV_APPEND  equ 10
FSV_CHDIR   equ 2
FSV_DELETE  equ 14
FSV_DFREE   equ 22
FSV_ENUM    equ 24
FSV_LIST    equ 0
FSV_MKDIR   equ 18
FSV_READ    equ 6
FSV_READAT  equ 12
FSV_RENAME  equ 16
FSV_RMDIR   equ 20
FSV_RMTREE  equ 28
FSV_STAT    equ 4
FSV_WRITE   equ 8
; --- from kernel/kernel.asm ---
DBG_TAG_FDD   equ 0x4446
; **NINE, AND IT IS kern_big's FIGURE ON PURPOSE** (SPEC.md 96.40.5).
; `dsk_bpb_check` rule 10 refuses a FLOPPY whose FATSz16 is over this, and a
; FAT12 floppy's FAT is 2 sectors at 360KB, 3 at 720KB, 7 at 1.2MB and NINE at
; 1.44MB - so kern_small's 2 let this box mount 360KB disks and nothing else.
; It shipped that way and the field found it in a day: a 286 with a 5.25" A:
; and a 3.5" B: could not run a program off B: whatever disk was in it, and
; the refusal said only "the disk could not be mounted".
;
; IT COSTS THE DOS PROGRAM 3 KB, which is the honest price of reading the
; media people have: FAT_SEG is DSK_FAT_SECS * 512 and LOW_SEG sits on it, so
; 2 -> 9 moves the arena's floor 1,024 -> 4,608 bytes and the handed figure
; 589 -> 586 KB, MEASURED (tests/kdhand.py). A box that cannot read a 1.44MB
; floppy is not a DOS box.
DSK_FAT_SECS equ 9
PKG_FILE_HI  equ 16
; --- from kernel/lz.inc ---
LZ_LZB      equ 1
; --- from kernel/memory.inc ---
MEM_PG_HIGH equ 0xFE
MEM_PG_MED  equ 0xFD
MEM_P_DIRW  equ MEM_PG_HIGH<<8 | 0x02
MEM_P_FATW  equ MEM_PG_MED<<8 | 0x20
; --- from kernel/mod.inc ---
MOD_FMT     equ 1
MOD_STAMP   equ 0               ; SPEC.md 2.8's build stamp: kern_dos builds
                                ; no module, so there is nothing to stamp
MOD_VER     equ 5

MODFP_STRIDE equ MOD_NENT * 4   ; kernel/mod.inc's far-pointer stride, which
                                ; diskw.inc's module header sizes against
BUILD_NUM    equ 0              ; the About box's, which there is no About box
                                ; for; SPEC.md 14.2 makes it the commit count

; --- 3: the stubs -----------------------------------------------------------
; A `ret` here is a DECISION and each carries the § that made it.  None of
; them is a shortcut: every one is a layer kern_dos does not have, and the
; disk layer calls into it from paths that are about the DESKTOP rather than
; about the file.
section .text

; **A STUB'S RETURN KIND IS PART OF ITS CONTRACT, and getting it wrong
; assembles perfectly.** The kernel's disk layer reaches these across a
; SEGMENT - `call KERNEL_SEG:fpg_busy`, `call COLD_SEG:desk_zones_paint_x` -
; because in the kernel they live in another one; here they are all in the
; one image and the call is still FAR, so the stub owes a `retf`. A near
; `ret` leaves the pushed CS on the stack, and what that looks like from
; outside is a mount that prints its first message, runs, and lands back at
; the image's own offset 0 some dozens of instructions later. It cost a
; morning; SPEC.md 20's "a package author never writes retf" is the same
; hazard one layer along.
;
; The FAR group - the nine the disk layer reaches through a segment.
; The progress widget (SPEC.md 12.8) draws, and there is nothing to draw on:
; the DOS program owns the screen, which is what the whole feature is for.
fpg_begin:
fpg_busy:
fpg_end:
; The gfx lock guards a framebuffer nothing here touches (KERN-DOS-PLAN 4.2:
; no drawing layer), and the display shim answers which screen a rect is on.
cw_gfx_lock:
cw_gfx_unlock:
cw_mem_disp:
; ...and the desktop's volume zones (SPEC.md 26.1) and the Disk window's
; number formatter, both reached from `.cold` through COLD_SEG.
desk_zones_paint_x:
fmf_fm_utoa:
kd_nothing_far:
    retf

; The NEAR group.
fpg_step:
desk_zmark_x:
fmv_gneed:
fmv_mark:
kd_nothing:
    ret

; --- the refusals, which are not the same thing as the stubs above ----------
; A stub returns having done nothing because there was nothing to do.  These
; RETURN A REFUSAL, because the caller asked a question this machine cannot
; answer and a silent success would be a wrong answer.
;
; The driver layer is the big one and it is KERN-DOS-PLAN 6.1 lever 4 in code:
; ONE VOLUME CLASS, BIOS floppies and the boot partition, so DVK_DRV volumes
; and the whole DSV_FS file-system-in-a-driver path (SPEC.md 51.8) refuse at
; the fence rather than being carried.
drv_blk_call_x:
drv_cls_fp_x:
drv_cls_svc_x:
drv_fs_call:
; On-demand kernel modules (SPEC.md 2.8) need a boot volume to read from and a
; heap to put them in, and are how the kernel gets FORMAT and CLONE off its
; own footprint.  kern_dos has no feature that wants one.
mod_need:
mod_drop:
; Decompression (SPEC.md 20.13) is for packages, drivers and the kernel's own
; modules.  A DOS program's file is bytes on a disk.
lz_decomp_x:
kd_refuse:
    stc
    ret

; The clock, which is the one stub that is NOT a stub: SPEC.md 18.6's FAT
; timestamp is written from it, so a file this machine creates would carry
; 1980-01-01 without it.  The ROM has the answer and kern_dos asks it
; directly - there is no clock ladder here (SPEC.md 37) and no rung to pick.
cw_clk_snapshot:
    retf                        ; FAR, like the rest of the cw_ shims

; --- 4: the state ------------------------------------------------------------
section .bss
; sched.inc's, and the two the disk layer really uses: [sch_lock] is inc/dec'd
; around every int 13h and nothing reads it here (one task), and [ticks] is
; the BIOS tick the retry paths time out against.
sch_lock:     resb 1
ticks:        resw 1
; clock.inc's snapshot, which cw_clk_snapshot above fills and diskw.inc reads
; into a directory entry (SPEC.md 18.6).
clk_sn_sec:   resb 1
clk_sn_min:   resb 1
clk_sn_hour:  resb 1
clk_sn_day:   resb 1
clk_sn_mon:   resb 1
clk_sn_year:  resw 1
; ...and one word each for the layers above: the driver class the block calls
; would go to, the Disk window's three, the loader's in-flight flag and the
; module table's file pointer.  Every one is READ by the disk layer on a path
; that is about telling somebody else what happened.
drv_blkcls:   resw 1
fm_fmtrow:    resw 1
fm_ldrv:      resw 1
fm_lmok:      resb 1
ld_pending:   resb 1
mod_fp:       resw 1
boot_cylrun:  resb 1

; --- the strings nothing here shows -----------------------------------------
; Five messages the kernel's own UI puts on the glass when a mount goes wrong.
; kern_dos has no glass; the DOS program gets a DOS error code.
section .text
cp_s_dsdrv:
cp_s_nodrv:
drv_e1_l:
fm_s_swapnd:
ui_s_nodisk_l:
    db 0

; --- 3b: the two pieces of REAL WORK ----------------------------------------
section .cold
; kernel.asm's shared epilogue ladder (docs/plans/HANDOFF-SOAK-FINDINGS.md B2):
; a proc jumps into it at the rung matching how much it pushed. It is entered
; by a near JUMP and not a call, so it costs no stack - which is why the size
; pass could factor it at all.
kretc_es:         pop es
kretc_bp:         pop bp
kretc_di:         pop di
kretc_si:         pop si
kretc_dx:         pop dx
kretc_cx:         pop cx
                  pop bx
                  pop ax
                  ret

; --- the allocator ----------------------------------------------------------
; **A BUMP ALLOCATOR, DOWNWARD FROM THE TOP OF THE MACHINE**, and that shape
; is KERN-DOS-PLAN 6.2 rather than laziness: the only claims the disk layer
; makes here are the FAT window and the directory read-ahead, both caches, and
; the design has them GIVEN BACK the moment the DOS program's own AH=48h wants
; the memory. Claiming downward from the ceiling is what makes that a decrement
; of one word instead of a compaction.
;
; It is NOT kernel/memory.inc: no records, no owners, no purge ranks, no
; compaction, no two ends. mem_free_x accepts any segment and only the most
; recent claim actually returns room, which is all a stack of two caches needs.
section .bss
kd_top:           resw 1        ; the ceiling, in paragraphs: the first
                                ; paragraph NOT ours
kd_floor:         resw 1        ; ...and where the DOS program's memory starts

section .text
; in: AX = KB, BX = owner (ignored); out CF=0 and DX = the segment
mem_claim_x:
    push ax
    mov cl, 6
    shl ax, cl                  ; KB -> paragraphs
    jc .no
    mov dx, [kd_top]
    sub dx, ax
    jc .no
    cmp dx, [kd_floor]
    jb .no
    mov [kd_top], dx
    pop ax
    clc
    ret
.no:
    pop ax
    stc
    ret

; in: DX = the segment, BX = the owner; out nothing
mem_free_x:
    cmp dx, [kd_top]
    jne .keep                   ; not the most recent: the room stays spent,
    ret                         ; which for a stack of two caches cannot arise
.keep:
    ret

; out: AX = KB claimable. There is one level here (KERN-DOS-PLAN 6.1 lever 4),
; so AL's level argument is read and discarded.
mem_avail_lvl_x:
    mov ax, [kd_top]
    sub ax, [kd_floor]
    mov cl, 6
    shr ax, cl
    ret

; SPEC.md 66.2's opt-in. Nothing compacts here, so a claim is as movable as it
; is ever going to be and the declaration is a no-op rather than a refusal.
mem_movable_x:
    ret
