; =============================================================================
; os8088 - kerndos/kerndos.asm
;
; **THE ROOT, AND IT IS NOT A KERNEL** (docs/plans/KERN-DOS-PLAN.md 4.2): no
; boot sequence, no task table, no scheduler, no API table, no window manager,
; no drawing layer, no menu, no event loop, no driver layer and no on-demand
; modules. It is a resident INT 21h with a FAT reader under it, so that a DOS
; program can have ~600KB of a 640KB machine.
;
; It %includes the KERNEL'S OWN disk layer rather than re-implementing it, and
; kdshim.inc is what those files name and this root has to answer. Wave 3's
; whole question is how big that shim is: a shim near the size of a
; purpose-written FAT reader means the reuse is not paying, and the plan is
; explicitly allowed to come back with "write a reader instead".
; =============================================================================
cpu 8086
bits 16

%include "kdlayout.inc"         ; the segment ladder and the sizes

; THE SECTIONS, DECLARED IN THE ORDER THEY LAND, which is the kernel's rule
; (SPEC.md 2.6) with the boot overlay left out. `.cold` is ordinary code here
; and not a second rung: nothing in kern_dos is boot-only, because kern_dos is
; not booted.
; **`vstart=0` ON `.lowbss`, AND IT IS NOT DECORATION** (kernel/kernel.asm's
; own declaration): those buffers are reached through SS = LOW_SEG, so their
; labels have to be offsets from the START of that segment. A bare `section`
; gives them the absolute offset they happen to land at in the flat image -
; 0x3BFC here - and then every disk-visible base is 15KB adrift AND not
; 512-aligned, which is the one thing CLAUDE.md's hard rules say answers
; `int 13h` with error 09h. What it looked like from outside was a mount that
; printed its first message and never came back.
section .lowbss nobits vstart=0
section .bss  nobits
section .text
kd_text_start:
; **THE FIRST BYTES OF THE IMAGE ARE A JUMP**, because kern_dos is ENTERED and
; not booted: SPEC.md 87.5's stub reads it into low memory and far-jumps to its
; base (docs/plans/KERN-DOS-PLAN.md 2), so offset 0 has to be somewhere to go.
;
; **AND THE JUMP IS BEFORE THE SHIM'S OWN `section .text`**, which is not a
; style point: kdshim.inc opens `.text` to put its stubs in, so including it
; first puts `fpg_begin`'s `ret` at offset 0. The far jump then returns
; through whatever the loader left on the stack, and what that looks like from
; outside is a loader that printed `go` and a machine that said nothing ever
; again.
%ifdef KD_GATE
    jmp kd_gate_entry
%endif
%include "kdshim.inc"           ; what the kernel's own files name
%include "dskwin.inc"           ; the mount-owned window (SPEC.md 2.1.2)
%include "disk.inc"             ; volumes, mount, the FAT read path
%include "diskw.inc"            ; the FAT write path
%include "kdgate.inc"           ; wave 3's mount-and-read gate, KD_GATE only
section .cold
section .modf
modf_end:                       ; diskw.inc writes this into a module header
                                ; it will never build one of (SPEC.md 2.8)
section .text
kd_text_end:

; --- what the ladder asserted ------------------------------------------------
KTEXT_SIZE equ kd_text_end - kd_text_start
KBSS_SIZE  equ 0
KCOLD_SIZE equ 0
%if (KTEXT_SIZE + KBSS_SIZE + KCOLD_SIZE) > KD_IMG_KB * 1024
 %error "kern_dos outgrew KD_IMG_KB - raise it in kdlayout.inc, and note that \
the whole of kern_dos has about 39KB before the 600KB target is missed \
(docs/plans/KERN-DOS-PLAN.md 1)"
%endif
