; =============================================================================
; apps/bonanza/fam/bzfwalk.inc - a family part's WALK over its OWN records
; (SPEC.md 130.25.6.10): bz_flist built, at the play's start, each slot's list
; of the course's records whose kind is the family's, so a hook walks those
; and never the whole prop table (PLAYGROUND's 66, of which a family has a
; handful).  A list holds record INDEXES (a byte each), in record order:
;
;       call xx_walk            ; ES = the course, BX = the list, CX its count
;       jcxz .x
;   .l: call xx_rec             ; ES:SI the record of the index at [BX]
;       ...                     ; (its ELEMENT, bz_fmark's BX: the byte at [BX])
;       inc bx
;       loop .l
;
; xx_recp the same off BP, for a hook whose BX is busy.
; =============================================================================

; BZ_FWALK name: DI = the slot's bytes (bz_fsl + BZF_SLOT slot) -> ES = the
; course, BX = the slot's list (DS), CX its count.  Preserves all else.
%macro BZ_FWALK 1
%if BZF_SLOT != 8
 %error "BZ_FWALK's slot arithmetic is BZF_SLOT = 8, a list header 2"
%endif
%1:
    mov es, [bz_cseg]
    mov bx, di
    sub bx, bz_fsl
    shr bx, 1
    shr bx, 1
    mov cl, [bz_fls + 1 + bx]
    xor ch, ch
    mov bl, [bz_fls + bx]
    xor bh, bh
    add bx, bz_flst
    ret
%endmacro

; BZ_FWALKA name: AL = the slot (a hook's entry AL) -> as BZ_FWALK.
; Preserves all else.
%macro BZ_FWALKA 1
%1:
    mov es, [bz_cseg]
    mov bl, al
    xor bh, bh
    shl bx, 1
    mov cl, [bz_fls + 1 + bx]
    xor ch, ch
    mov bl, [bz_fls + bx]
    xor bh, bh
    add bx, bz_flst
    ret
%endmacro

; BZ_FREC name, reg: the index at DS:reg (BX or BP) -> SI its record in the
; course (ES's).  Preserves all else.
%macro BZ_FREC 2
%1:
    push cx
    mov cl, [ds:%2]
    xor ch, ch
    mov si, cx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    pop cx
    ret
%endmacro

; -----------------------------------------------------------------------------
; THE WAKE (SPEC.md 130.25.6.11): a family that schedules its STEP writes the
; bz_nstep it next needs into bz_fwk (BZ_FSETWK; 0 every step).  Between, the
; engine does not call it (bz_fstp) - unless a play starts, a respawn, the
; walk's slice moves or the material changes, when every STEP runs.  A STEP
; that schedules finds the nearest of its timers' next flips in bz_fwkk
; (BZ_FTNEXT: a timer counts only when its lane is in the walk's slice or its
; cell in the window - a flip anywhere else marks nothing and refills nothing),
; and a CELL or CONTACT that changes what the STEP must watch writes 0.
; -----------------------------------------------------------------------------

; BZ_FSETWK name: DI = the slot's bytes, AX = the wake -> bz_fwk.  Preserves all.
%macro BZ_FSETWK 1
%1:
    push bx
    mov bx, di
    sub bx, bz_fsl
    shr bx, 1
    shr bx, 1
    mov [bz_fwk + bx], ax
    pop bx
    ret
%endmacro

; BZ_FTNEXT name, ON, MASK, TT: a timer's next turn into bz_fwkk - the
; engine's bz_ftnext (bzfam.inc, far through bz_ftnp, which bz_fstp points;
; one copy for every family), told where the record keeps ON and MASK (SEED
; the byte after MASK) and TT (0 a popspike's timer, 1 a turntable's).  ES:SI
; = the record, DL its element.  Preserves all but AX.
%macro BZ_FTNEXT 4
%1:
    push bx
    mov ax, %2 | %4 << 8
    mov bx, %3
    call far [bz_ftnp]
    pop bx
    ret
%endmacro
