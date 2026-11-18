; =============================================================================
; apps/bonanza/fam/bzdoor.inc - THE WINDMILL'S DOORWAY as the ROTOR family's
; (SPEC.md 130.25.20.2): step 5's question, asked where the ball's circle meets
; the doorway's edge (bz_step's .wdoor and .ndoor, bz_swalls' .edoor).
; =============================================================================

; bz_door - DX = the point (DL = u, DH = v, integer gu before the step's x
; push), the windmill [bz_pdi]: the ROTOR family's PROP hook, DOOR -> AL 0 not
; touching (the edge is a wall), 1 CLOSED with BL = its gate's eG (the knock),
; 2 OPEN (swallowed: the caller captures).  Preserves all but AX and BX.
bz_door:
    push dx
    mov bx, dx
    mov ax, BZ_PQ_DOOR << 8 | BZ_HK_PROP
    mov dl, BZ_FK_WINDMILL
    call bz_fone
    pop dx
    mov bl, ah
    ret
