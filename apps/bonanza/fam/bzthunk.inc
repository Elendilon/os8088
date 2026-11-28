; =============================================================================
; apps/bonanza/fam/bzthunk.inc - THE TUBE AS A FAMILY (SPEC.md 137.25.20.2): the
; engine's side of bztube.inc's routines when the TUBE family's part holds
; them - each the PROP hook (bit 6) of the family whose key is BZ_FK_TUBE, asked
; through bz_fone with AH the question.  Included by bzphys.inc (SPEC.md
; 137.25.20.3: the tube's home superseded a resident switch).  ES = the course; every thunk
; preserves all the routine it replaces did, and more.
; =============================================================================

; bz_capture - prop BL's tube (or windmill) takes the ball: CAPTURE.
; Clobbers AX, BH.
bz_capture:
    xor bh, bh
    mov ah, BZ_PQ_CAPTURE
    jmp short bz_tprop

; bz_tdrain - step 4, the centre a plain tube's IN (BX the tube): DRAIN -
; CF = 1 captured (the step ends).  Clobbers AX.
bz_tdrain:
    mov ah, BZ_PQ_DRAIN
bz_tprop:                       ; AH the question, BX the element -> the TUBE
    push dx                     ; family's answer, CF its bit 0
    mov dl, BZ_FK_TUBE
    mov al, BZ_HK_PROP
    call bz_fone
    pop dx
    shr al, 1
    ret

; bz_transit - step 1, a ball in a tube: TRANSIT, and when it EXITED the
; window round OUT, as the routine did itself.  Clobbers AX.
bz_transit:
    mov ah, BZ_PQ_TRANSIT
    call bz_tprop
    jnc .r
    call bz_win9f
.r:
    ret
