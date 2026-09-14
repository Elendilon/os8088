; =============================================================================
; kerndos/kdosgate.inc - wave 4's entry, now a LAUNCH BLOCK STAGER
;
; **kern_dos's REAL entry is `kdentry.inc`** and this no longer duplicates it.
; W4 shipped the whole of `dos_run`'s setup here, which was right while the
; handoff did not exist and became a second copy the day it did. So what is
; left is the ONE thing this gate is for: it stages a launch block out of its
; own constants and jumps to the real entry, where the stub stages one out of
; a running os8088 and jumps to exactly the same place.
;
; That makes the block's ABI testable on a machine with **no kernel, no
; handoff, no hard disk and no part table** - `python3 tests/kdos.py` is four
; seconds - and it is the reason the ABI is a block at all rather than a pile
; of pokes: two producers, one consumer, one gate.
;
; It is behind KD_GATE and no shipping path defines it.
; =============================================================================
%ifdef KD_GATE
section .text

kd_dos_entry:
    cli
    mov ax, KD_SEG              ; enough of a machine to fill a block in: the
    mov ds, ax                  ; real entry does this again for itself, and
    mov es, ax                  ; has to, because the stub arrives with no
    mov ax, LOW_SEG             ; segment of ours set at all
    mov ss, ax
    mov sp, KD_STACK
    sti
    cld

    mov si, kd_g_boot
    call kd_puts

    ; --- the block, as the handoff will stage it ------------------------------
    mov di, kd_glb
    mov word [di+KDL_MAGIC], KDL_SIG & 0xFFFF
    mov word [di+KDL_MAGIC+2], KDL_SIG >> 16
    mov word [di+KDL_VER], 1
    mov word [di+KDL_FLAGS], KDLF_REBOOT
    mov word [di+KDL_TLEN], KDL_MINE
    mov word [di+KDL_RSVD], 0

    ; **THE MACHINE'S OWN KB, OUT OF THE BDA** (0040:0013, which is `int 12h`'s
    ; own answer). The real handoff banks the same word for the same reason: it
    ; is the only place the size of conventional memory is written down, and a
    ; constant here would be a guess about somebody else's machine.
    push ds
    mov ax, 0x0040
    mov ds, ax
    mov ax, [0x0013]
    pop ds
    mov [di+KDL_CAP], ax
    mov word [di+KDL_UNIT], 1   ; B:, kerndos.asm's reason: A: carries the
                                ; loader and the blob raw and has no volume

    ; --- and the fields, which on this arm are two constants and five zeros ---
    ; The gather the BOX does is kdlaunch.inc's table walked the other way;
    ; here there is no box, so the two that matter are written by hand and the
    ; rest are the zeros a fresh image already holds.
    add di, KDL_BODY
    push di
    mov si, kd_g_prog           ; dos_name, the first row of the table
    mov cx, 16
    rep movsb
    pop di
    add di, 16 + DOS_ARGSZ + (DOS_ENVN * DOS_ENVBUF) + 32 + 2
    mov byte [di], 1            ; dos_vol: B:, matching KDL_UNIT above

    mov word [kd_lbp], kd_glb   ; ...and the pointer the stub would have read
    jmp kd_entry                ; out of the header at KD_H_LBP

kd_g_boot: db 13, 10, 'kern_dos gate: staging a launch block', 13, 10, 0
kd_g_prog: db 'KDHELLO.COM', 0, 0, 0, 0, 0

; --- what the kernel's own kernel.asm would have given the disk layer -------
; `dsk_vol_fixed` is a two-instruction thunk in kernel.asm:7030 and it is
; COPIED here rather than shortened. The obvious shortening - `jmp
; dkf_dsk_vol_fixed`, on the reasoning that `.cold` is not another segment
; here so the call need not be far - is WRONG, because near or far is a
; property of the BODY and not of the distance: `dkf_dsk_vol_fixed` ends in
; `retf` whatever segment it is in. kdback.inc's header has the rest of it.
section .text
dsk_vol_fixed:
    call COLD_SEG:dkf_dsk_vol_fixed
    ret

section .bss
kd_glb:
    resb KDL_SIZE

; --- and the DOS core's own bss ---------------------------------------------
; **IT GOES IN `.bss` AND NOT AT THE END OF AN IMAGE.** In the package,
; `os88_image_end` is where the loader zeroes from (SPEC.md 21 step 5) and the
; DBSS table is offsets from it. Here there is no loader and no image end:
; the same table lands in the root's own `.bss`, addressed through DS exactly
; as before, and the name is all that has to be kept.
section .bss
os88_image_end:
    resb DOS_BSS_SIZE + CON_BSS

section .text
%endif                          ; KD_GATE
