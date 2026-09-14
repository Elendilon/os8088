; =============================================================================
; os8088 - kerndos/kdos.asm
;
; **kern_dos WITH THE DOS CORE ON TOP** (docs/plans/KERN-DOS-PLAN.md wave 4):
; kerndos.asm's disk layer, then `apps/dos/dos.asm` whole and unedited, then
; kerndos/kdback.inc - which is the SECOND implementation of the twenty-two
; `dos_k_*` doors, going to the kernel's disk layer directly instead of
; through an `OSAPI_*` cell.
;
; **THE PACKAGE IS INCLUDED WHOLE, and that is a finding rather than a
; shortcut.** docs/plans/KERN-DOS-PLAN.md §4.1.2 expected `apps/dos/dos.asm`
; to need splitting so the core could be included on its own; it does not. Assembled under this root the
; whole file - window, console, shortcut writer and all - produced exactly ONE
; conflict, `DVOL_MAX`, and that one is a `%ifndef` (SPEC.md 96.38). What the
; window half costs here is bytes that are never reached, and cutting them is
; a size question for a later wave rather than a condition of this one.
; =============================================================================
cpu 8086
bits 16

%define KD_BACKEND                  ; ...so apps/dos/dos.asm leaves its own
                                    ; twenty-two doors out and kdback.inc's
                                    ; are the ones that get linked

%include "mouproto.inc"             ; the serial packet, shared as SOURCE with
                                    ; kernel/mouse.inc (SPEC.md 96.45)
%include "doscall.inc"              ; CORE_ORG / CORE_MAX / CORE_BSS_SIZE, which
                                    ; the reservation below needs long before
                                    ; `dos.asm` is included (SPEC.md 96.44.5)
%include "kdlayout.inc"
%include "kdlaunch.inc"             ; the launch block's layout and its list;
                                    ; emits nothing until a consumer asks

section .lowbss nobits vstart=0     ; kerndos.asm's own rule, and for its
section .bss  nobits                ; reason: these are reached through SS
kd_b_start:                         ; ...and where kd_entry starts zeroing it
section .text
kd_text_start:
; --- THE FIXED HEADER (kdlayout.inc) ----------------------------------------
; The stub arrives with no symbol table and jumps to KD_SEG:0000, so the first
; eight bytes are a contract: a NEAR jump (`near` spelled out, because nasm
; would shrink a resolved short one and move everything after it) and the two
; words that say where the launch block goes.
%ifdef KD_GATE
    %define kd_head_entry kd_dos_entry
%else
    %define kd_head_entry kd_entry
%endif
    jmp near kd_head_entry          ; KD_H_JMP
    db 0
kd_lbp:  dw kd_lblock               ; KD_H_LBP
kd_lbsz: dw KDL_SIZE                ; KD_H_LBSZ

; --- AND THE API TABLE'S GROUND, WHICH IS A WALL OF REFUSALS ----------------
; **`KERNEL_SEG` IS THIS SEGMENT HERE** (kdlayout.inc), so every
; `call OSAPI_X` that survives into this image is a far call to KD_SEG:0xNNNN
; - which without this is a jump into the middle of the disk layer, with the
; caller's registers, and no way to tell afterwards where it went.
;
; It is not a corner case: `apps/dos/dos.asm` is included WHOLE and has 96
; `OSAPI_*` call sites. Wave 2 measured the LOAD path at 21 procs reaching
; none of them and that measurement stands; what it did not cover is the RUN
; path, where `dos_getkey` polls `dos_mou_read` - so every DOS program that
; waits for a keystroke made one. It presented as a machine spinning in the
; ROM with a key already in the BIOS ring.
;
; So the cells exist and REFUSE. `stc`/`retf` is the published meaning of a
; slot that cannot do what was asked (SPEC.md 20.8), every caller in the tree
; has that path, and a wrong one is then a wrong ANSWER rather than a wild
; jump - which is diagnosable by breakpointing this span. It costs 1,432
; bytes of the image and NOT ONE BYTE OF THE ARENA: the arena's floor is
; LOW_SEG, which KD_IMG_KB fixes, and the image has thousands of bytes of that
; rung spare. Compressed it is a few dozen bytes of the part, being 179 copies
; of one 8-byte row.
KD_API_LO   equ 0x0010              ; the first published cell, and the last -
KD_API_HI   equ 0x05A0              ; apps/os88api.inc owns both, and
                                    ; tests/unit/t_kdapi.py is what stops them
                                    ; drifting apart. 0x0000 and 0x0008 are not
                                    ; published, which is what leaves room for
                                    ; the fixed header above
    times KD_API_LO - ($ - $$) db 0
%rep (KD_API_HI - KD_API_LO) / 8 + 1
    stc
    retf
    times 6 db 0
%endrep
%if $ - $$ != KD_API_HI + 8
  %error "kern_dos's refusal table does not end where the API table does"
%endif

; --- AND THE HOLE THE CORE GOES IN (SPEC.md 96.44.5) ------------------------
; The same reservation the box makes, for the same reason and at the same
; addresses: the core is a PART both hosts join, so its jump table is at
; CORE_ORG in this segment too and `kern_dos`'s own code begins above the
; budget and the bss block. The stub reads this part first and the core's over
; the hole (96.40.2), so what is in the file here is zeros - which cost the
; disk nothing, the row being OP_COMP, and cost this image the slack in
; CORE_MAX, which is the one number that keeps them honest.
%ifdef DOS_EXTCORE                  ; ...only when the core really IS a part
%if $ - $$ > CORE_ORG
  %error "the refusal table reached CORE_ORG - apps/os88api.inc owns those \
cell offsets, so CORE_ORG has to rise rather than the table move"
%endif
    times CORE_ORG - ($ - $$) db 0
    times CORE_MAX + CORE_BSS_SIZE db 0
%endif

%include "kdshim.inc"
%include "dskwin.inc"
%include "disk.inc"
%include "diskw.inc"
%include "dos.asm"                  ; the DOS core, whole and unedited
%include "kdback.inc"               ; ...over the kernel's disk layer
%include "kdmouse.inc"              ; INT 33h's pointer (SPEC.md 96.45): the
                                    ; port os8088 settled on, decoded through
                                    ; kernel/mouproto.inc
%include "kdentry.inc"              ; the REAL entry: a launch block, a
                                    ; program, and int 19h when it exits
%include "kdosgate.inc"             ; ...and wave 4's, which stages a block
                                    ; and comes in at the same door
; --- and the image's own size, which is what the rung has to clear ---------
; `-f bin` lays the progbits sections out contiguously, so the image is their
; four lengths - and a length is measured INSIDE its own section, `$$` being
; that section's start. Across two sections nasm will not subtract at all
; ("operands differ by a non-scalar"), which is the assembler declining to
; answer a question the caller has got wrong.
section .text
kd_e_text:
KD_S_TEXT equ kd_e_text - $$
section .cold
kd_e_cold:
KD_S_COLD equ kd_e_cold - $$
section .ovlw
kd_e_ovlw:
KD_S_OVLW equ kd_e_ovlw - $$
section .modf
modf_end:
kd_e_modf:
KD_S_MODF equ kd_e_modf - $$
section .bss
kd_e_bss:
KD_S_BSS equ kd_e_bss - $$
section .lowbss
kd_e_lowbss:
KD_S_LOWBSS equ kd_e_lowbss - $$
section .text
kd_text_end:

; **THE WHOLE IMAGE AND NOT `.text`.** FAT_SEG sits on top of this rung, so a
; rung short by a kilobyte puts the FAT snapshot INSIDE the code: measuring
; `.text` alone passed at 40KB on a 45KB image, and the mount then overwrote
; the routine that called it.
KTEXT_SIZE equ KD_S_TEXT + KD_S_COLD + KD_S_OVLW + KD_S_MODF
; **AND THE BSS, WHICH `-f bin` PUTS ABOVE THE IMAGE** and which read `equ 0`
; here while it was thousands of bytes. It is the SAME hazard as the one the
; paragraph above records, one section along: `.bss` is nobits so it costs no
; disk, but it occupies address space between the last emitted byte and
; FAT_SEG - so a rung that clears the image and not the bss puts the FAT
; snapshot in the DOS core's own variables, and nothing says so until a mount
; overwrites a handle table.
KBSS_SIZE  equ KD_S_BSS
KIMG_SIZE  equ KTEXT_SIZE + KBSS_SIZE
%if KIMG_SIZE > KD_IMG_KB * 1024
 %error "kern_dos outgrew KD_IMG_KB - raise it in kdlayout.inc, and note that \
the whole of kern_dos has about 39KB before the 600KB target is missed \
(docs/plans/KERN-DOS-PLAN.md 1)"
%endif

; ...and the same question for `.lowbss`, which sits at LOW_SEG under the
; stack rather than above the image: KD_LOW_KB has to hold the disk layer's
; buffers AND leave room for KD_STACK to grow down into.
%if KD_S_LOWBSS > KD_STACK
 %error "kern_dos's .lowbss buffers reach the stack - raise KD_LOW_KB"
%endif
