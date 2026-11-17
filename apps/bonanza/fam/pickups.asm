; =============================================================================
; apps/bonanza/fam/pickups.asm - BONANZA's PICKUPS FAMILY (SPEC.md 128.25.9,
; 128.25.19): three kinds, each taken when the ball's centre is in its cell
; (CONTACT) and its one state bit, COLLECTED, clear -
;   hourglass (19)  +BZ_PU_HGSEC on the limit (bz_tsec; the clocks' next second
;                   shows it), once an attempt (ATTEMPT), and HIDDEN while
;                   there is no limit (exploration, the benchmark): pose 0, no
;                   take
;   speed (20)      bz_wacc = BZ_PU_SACC (every force table's force, bz_ramp)
;                   and bz_vup = BZ_PU_SVUP (the cap), for the ELEMENT's
;                   duration (record +18, steps / 4), RESPAWN
;   jump (21)       bz_mrec's HOP = BZ_PU_JHOP for any ball (it stacks with
;                   rubber's boost: the boost's rule reads the bounce), for its
;                   own duration, RESPAWN
; Record +19 bit 0, OVERWRITE: taking it ENDS the other timed effect.  The two
; timers are this family's SLOT (bz_fsl + BZF_SLOT AL): +0 speed's steps left,
; +2 jump's, +4 the Hop the jump replaced.  STEP counts them down (and puts
; the jump's Hop back over a pad's swap, which copies the material's own),
; ends an effect at 0 and writes bz_cue, the resident sprite path's CUE
; (SPARKLES while an effect lasts, the FLASH in its last BZ_PU_WARN steps);
; RESET (a respawn: a play's start finds everything zero) ends both.  Every
; change of bz_wacc rebuilds BOTH force tables here - bz_ramp's arithmetic,
; written again because a part cannot call the package.
; bbcourse.PickupFamily is the model, step for step.
;
; A FAMILY PART (SPEC.md 128.25.6.2), linked against the package's bss as the
; probe is (build/bonanza-art/bzlink.inc: no code label).  Entered by `call
; far` with DS = ES = the package, AL = the slot, AH = the argument (CONTACT,
; POSE: the kind), BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

    db 'BF'
    db BZ_FID_PICKUPS           ; (bzcourse.inc's: the ID is FAMILIES' alone)
    db BZ_FAMV_PICKUPS
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_CONTACT | BZ_FH_STEP | BZ_FH_POSE
    db 3, BZ_K_HOURGLASS        ; three kinds, hourglass, speed, jump
    db 0
    dw pu_reset, 0, pu_contact, pu_step, pu_pose, 0
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif
%if BZ_K_SPEED != BZ_K_HOURGLASS + 1 || BZ_K_JUMP != BZ_K_HOURGLASS + 2
 %error "the pickups' kinds are one run (the part's +9, +10)"
%endif

; RESET: both timed effects ended (each only when it runs: a play's start has
; none, and the Hop a jump never replaced is not written), the cue cleared,
; and every pickup's lane MARKED (a respawn put the RESPAWN ones back)
pu_reset:
    call pu_slot
    cmp word [di], 0
    je .j
    call pu_soff
.j:
    cmp word [di + 2], 0
    je .m
    call pu_joff
.m:
    mov byte [bz_cue], 0
    mov cl, [bz_nprop]
    xor ch, ch
    jcxz .out
    mov es, [bz_cseg]
    mov si, [bz_poff]
    xor bx, bx
.l:
    mov al, [es:si]
    sub al, BZ_K_HOURGLASS
    cmp al, 3
    jae .n
    call far [bz_fmkp]          ; its lane MARKED, the next walk made (bz_fmark; BX the element)
.n:
    add si, 32
    inc bx
    loop .l
.out:
    retf

; CONTACT (AH the kind): an element not yet COLLECTED is taken - its bit set,
; its lane marked, bz_nfev counted (the PICKUP sound) - and its effect begun
pu_contact:
    mov dl, ah
    call pu_slot
    call pu_bit                 ; SI its byte in bz_fst, AL its bit
    test [si], al
    jnz .out
    cmp dl, BZ_K_HOURGLASS
    jne .take
    cmp word [bz_tsec], 0       ; (hidden: no limit to add to)
    je .out
.take:
    or [si], al
    call far [bz_fmkp]          ; its lane MARKED, the next walk made (bz_fmark; BX the element)
    inc word [bz_nfev]
    cmp dl, BZ_K_HOURGLASS
    jne .timed
    add word [bz_tsec], BZ_PU_HGSEC
.out:
    retf
.timed:
    push es                     ; AX = 4 x the duration (+18), CH the flags (+19)
    mov es, [bz_cseg]
    mov cl, 5
    shl bx, cl
    add bx, [bz_poff]
    mov ax, [es:bx + 18]
    pop es
    mov ch, ah
    xor ah, ah
    shl ax, 1
    shl ax, 1
    cmp dl, BZ_K_SPEED
    jne .jump
    test ch, BZ_PU_OVER         ; SPEED: OVERWRITE ends the jump
    jz .s1
    cmp word [di + 2], 0
    je .s1
    call pu_joff
.s1:
    mov [di], ax
    mov byte [bz_wacc], BZ_PU_SACC
    mov word [bz_vup], BZ_PU_SVUP
    call pu_tab
    retf
.jump:
    test ch, BZ_PU_OVER         ; JUMP: OVERWRITE ends the speed
    jz .j1
    cmp word [di], 0
    je .j1
    push ax
    call pu_soff
    pop ax
.j1:
    cmp word [di + 2], 0        ; (a jump already running keeps the Hop it
    jne .j2                     ; replaced)
    mov dx, [bz_mrec + BZM_HOP]
    mov [di + 4], dx
    mov word [bz_mrec + BZM_HOP], BZ_PU_JHOP
.j2:
    mov [di + 2], ax
    retf

; STEP: each timer counted down, its effect ended at 0; a running jump's Hop
; put back over a pad's swap (bz_setmat copied the material's); bz_cue = bit 0
; while either runs, bit 1 while either has BZ_PU_WARN steps or fewer left
pu_step:
    call pu_slot
    xor dx, dx                  ; DL the cue
    mov ax, [di]
    or ax, ax
    jz .j
    dec ax
    mov [di], ax
    jnz .s1
    push dx
    call pu_soff
    pop dx
    jmp short .j
.s1:
    or dl, 1
    cmp ax, BZ_PU_WARN
    ja .j
    or dl, 2
.j:
    mov ax, [di + 2]
    or ax, ax
    jz .c
    mov cx, [bz_mrec + BZM_HOP]
    cmp cx, BZ_PU_JHOP
    je .j0
    mov [di + 4], cx
    mov word [bz_mrec + BZM_HOP], BZ_PU_JHOP
.j0:
    dec ax
    mov [di + 2], ax
    jnz .j1
    call pu_joff
    jmp short .c
.j1:
    or dl, 1
    cmp ax, BZ_PU_WARN
    ja .c
    or dl, 2
.c:
    mov [bz_cue], dl
    retf

; POSE (AH the kind): 1 the icon, 0 gone - COLLECTED, or an hourglass while
; there is no limit
pu_pose:
    mov dl, ah
    call pu_bit
    test [si], al
    jnz .z
    cmp dl, BZ_K_HOURGLASS
    jne .one
    cmp word [bz_tsec], 0
    je .z
.one:
    mov al, 1
    retf
.z:
    mov al, 0
    retf

; the speed's effect ended (DI the slot): its timer, bz_wacc and bz_vup 0, the
; tables rebuilt.  Clobbers AX, BX, CX, DX.
pu_soff:
    mov word [di], 0
    mov byte [bz_wacc], 0
    mov word [bz_vup], 0
    ; (falls into pu_tab)

; both force tables rebuilt for bz_wacc: the air's from the material's ACC
; (>> 4), the ground's from the window centre's surface's force (bz_se, >> 3)
; - bz_pinit's, bz_setmat's and bz_surfset's.  Clobbers AX, BX, CX, DX.
pu_tab:
    push di
    mov al, [bz_mrec + BZM_ACC]
    mov di, bz_fta
    mov cl, 4
    call pu_ramp
    mov al, [bz_se]
    mov di, bz_ftg
    mov cl, 3
    call pu_ramp
    pop di
    ret

; bz_ramp, written again: [DI + l] = ((AL + bz_wacc) l + 4) >> CL, l = 0 ..
; BZ_LVLMAX.  Clobbers AX, BX, CH, DX, DI.
pu_ramp:
    add al, [bz_wacc]
    cbw
    mov dx, 4
    mov ch, BZ_LVLMAX + 1
.l:
    mov bx, dx
    shr bx, cl
    mov [di], bl
    inc di
    add dx, ax
    dec ch
    jnz .l
    ret

; the jump's effect ended (DI the slot): its timer 0, the Hop it replaced back
pu_joff:
    mov word [di + 2], 0
    push ax
    mov ax, [di + 4]
    mov [bz_mrec + BZM_HOP], ax
    pop ax
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "pu_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
pu_slot:
    push ax
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    pop ax
    ret

; BX = an element -> SI = its COLLECTED bit's byte in bz_fst, AL the bit
; (record +16, FSB).  Clobbers CL.
pu_bit:
    push bx
    push es
    mov es, [bz_cseg]
    mov cl, 5
    shl bx, cl
    add bx, [bz_poff]
    mov bl, [es:bx + BZP_FSB]
    pop es
    xor bh, bh
    mov cl, bl
    and cl, 7
    shr bx, 1
    shr bx, 1
    shr bx, 1
    lea si, [bz_fst + bx]
    mov al, 1
    shl al, cl
    pop bx
    ret

%if $ - $$ > BZ_FAMP_PICKUPS * 16
 %error "the pickups' part passes its FAMILIES paras ceiling: raise it there"
%endif
