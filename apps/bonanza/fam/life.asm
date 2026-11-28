; =============================================================================
; apps/bonanza/fam/life.asm - BONANZA's LIFE FAMILY (SPEC.md 137.55): one kind,
; the HEART (27), taken when the ball's centre is in its cell (CONTACT) and
; its one state bit, COLLECTED, clear -
;   +1 on the game's lives (bz_lives, never past BZ_LVMAX), once an attempt
;   (ATTEMPT) - or, record +19 BZ_PU_ONCE, once a GAME: taking it sets bz_lfx
;   bit 1, which the rounds keep as a bit a pad in the slot (bz_nlife) and
;   hand back at the next play of that pad's course - and HIDDEN (pose 0, no
;   take) outside a game's course (bz_lfx bit 0 clear: EXPLORE, a free play,
;   a replay, a demo, the benchmark), or once its pad's course has given it.
; Its cue is the sparkles RISING (bz_cue bit 2, bz_cuef) for BZ_LF_RISE steps:
; the slot's byte +0, which STEP counts down - no flash, since this is a thing
; gained, not a thing that runs out.  Bits 0 and 1 of bz_cue are PICKUPS', and
; kept.  RESET (a respawn: a play's start finds the slot zero) ends the rise.
; bbcourse.LifeFamily is the model, step for step.
;
; A FAMILY PART (SPEC.md 137.25.6.2), linked against the package's bss as the
; probe is (build/bonanza-art/bzlink.inc: no code label).  Entered by `call
; far` with DS = ES = the package, AL = the slot, AH = the argument (CONTACT,
; POSE: the kind), BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"
%include "fam/bzfwalk.inc"

    db 'BF'
    db BZ_FID_LIFE              ; (bzcourse.inc's: the ID is FAMILIES' alone)
    db BZ_FAMV_LIFE
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_CONTACT | BZ_FH_STEP | BZ_FH_POSE
    db 1, BZ_K_LIFE             ; one kind
    db 0
    dw lf_reset, 0, lf_contact, lf_step, lf_pose, 0
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 137.25.6.2)"
%endif

; RESET: the rise ended, its cue bit cleared, every life's lane MARKED (its
; pose may have moved: a play's start, a respawn)
lf_reset:
    call lf_slot
    mov byte [di], 0
    and byte [bz_cue], 3        ; (bits 0 and 1 PICKUPS')
    mov cl, [bz_nprop]
    xor ch, ch
    jcxz .out
    mov es, [bz_cseg]
    mov si, [bz_poff]
    xor bx, bx
.l:
    cmp byte [es:si], BZ_K_LIFE
    jne .n
    call far [bz_fmkp]          ; its lane MARKED, the next walk made (bz_fmark; BX the element)
.n:
    add si, 32
    inc bx
    loop .l
.out:
    retf

; CONTACT: a life not yet COLLECTED and not HIDDEN is taken - its bit set,
; its lane marked, bz_nfev counted (the PICKUP sound), a life given (to
; BZ_LVMAX at most), a ONCE one's bz_lfx bit 1 set, and the rise begun
lf_contact:
    call lf_slot
    call lf_bit                 ; SI its byte in bz_fst, AL its bit, DL +19
    test [si], al
    jnz .out
    call lf_hid
    jc .out
    or [si], al
    call far [bz_fmkp]          ; its lane MARKED, the next walk made (bz_fmark; BX the element)
    inc word [bz_nfev]
    test dl, BZ_PU_ONCE         ; ONCE a game: the rounds keep it for the pad
    jz .l1                      ; (bz_nlife)
    or byte [bz_lfx], 2
.l1:
    cmp byte [bz_lives], BZ_LVMAX
    jae .l2
    inc byte [bz_lives]
.l2:
    mov byte [di], BZ_LF_RISE   ; its cue: the sparkles RISING
    xor ax, ax                  ; (its STEP every step now: 137.25.6.11)
    call lf_setwk
.out:
    retf

; STEP: the rise counted down; bz_cue bit 2 while it runs (bits 0 and 1 kept)
lf_step:
    call lf_slot
    mov al, [bz_cue]
    and al, 3
    cmp byte [di], 0
    je .c
    dec byte [di]
    jz .c
    or al, 4
.c:
    mov [bz_cue], al
    xor ax, ax                  ; (137.25.6.11: the rise running, every step;
    cmp byte [di], 0            ; none, none until CONTACT starts one)
    jne .w
    mov ax, [bz_nstep]
    add ax, 4000h
.w:
    call lf_setwk
    retf

    BZ_FSETWK lf_setwk

; POSE: 1 the heart, 0 gone - COLLECTED, or HIDDEN
lf_pose:
    call lf_bit
    test [si], al
    jnz .z
    call lf_hid
    jc .z
    mov al, 1
    retf
.z:
    mov al, 0
    retf

; DL = the element's +19 -> CF = 1 HIDDEN: outside a game's course (bz_lfx
; bit 0 clear), or a ONCE life its pad's course has given this game (bit 1).
; Preserves all but the flags.
lf_hid:
    test byte [bz_lfx], 1
    jz .yes
    test byte [bz_lfx], 2
    jz .no
    test dl, BZ_PU_ONCE
    jz .no
.yes:
    stc
    ret
.no:
    clc                         ; (test cleared it already: kept for the reader)
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "lf_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
lf_slot:
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
; (record +16, FSB), DL its flags (+19).  Clobbers CL.
lf_bit:
    push bx
    push es
    mov es, [bz_cseg]
    mov cl, 5
    shl bx, cl
    add bx, [bz_poff]
    mov dl, [es:bx + 19]
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

%if $ - $$ > BZ_FAMP_LIFE * 16
 %error "the life's part passes its FAMILIES paras ceiling: raise it there"
%endif
