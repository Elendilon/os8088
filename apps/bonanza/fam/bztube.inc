; =============================================================================
; apps/bonanza/fam/bztube.inc - THE TUBE's rules (SPEC.md 137.12.6.1, 137.17.17),
; ONE source (SPEC.md 137.25.20.3): included by the TUBE family's part,
; fam/tube.asm, and written so the package could include it as it is to make
; the tube resident again (as before story 9.8; no switch for that is built,
; the family's home superseded it).  Either way the helpers it calls -
; bz_lrecsi, bz_vmax, bz_h4, bz_setz, bz_psync - are the includer's: the
; package's own, or the part's copies (fam/bzfcopy.inc), which answer the same.
; The one difference is how a step in the tube ENDS, the includer's two macros:
;   BZT_GOING   still in the tube (bz_ps from its facts, bz_psync)
;   BZT_EXITED  out of it: the window refilled round OUT (resident: bz_win9f
;               here; the part answers AL = 1 and the engine's thunk refills)
; ES = the course throughout.
; =============================================================================
%ifnmacro BZT_GOING
 %macro BZT_GOING 0
    jmp bz_psync
 %endmacro
 %macro BZT_EXITED 0
    call bz_win9f
    ret
 %endmacro
%endif

; bz_capture - prop BL's tube takes the ball (137.12.6.1): the entry speed
; s_in = max(|gvx|, |gvy|); the centre at segment 0's start - IN's centre, a
; windmill's at its DOORWAY (the midpoint of IN's -x or -y edge) - on IN's
; floor there (IN is the window's centre); every velocity 0, grounded, no
; squash, no bz_gh, off the platform; the tube's first segment; bz_ntube + 1.
; Clobbers AX, BX, CX, DX, SI, DI.
bz_capture:
    xor bh, bh
    call bz_lrecsi
    inc bx
    mov [bz_tube], bl
    call bz_vmax
    mov [bz_tsin], ax
    mov bx, 0808h               ; BL = u, BH = v: the centre ...
    cmp byte [es:si + BZP_KIND], BZ_PK_WINDMILL
    jne .at
    cmp byte [es:si + BZP_TGVX], 0
    jne .dy
    xor bl, bl                  ; ...the -x doorway's midpoint
    jmp short .at
.dy:
    xor bh, bh                  ; ...the -y one's
.at:
    mov cl, 4
    xor ah, ah
    mov al, [es:si + BZP_WX]
    shl ax, cl
    add al, bl
    mov [bz_gx + 1], ax
    xor ah, ah
    mov al, [es:si + BZP_WY]
    shl ax, cl
    add al, bh
    mov [bz_gy + 1], ax
    xor ax, ax
    mov [bz_gx], al
    mov [bz_gx + 3], al
    mov [bz_gy], al
    mov [bz_gy + 3], al
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    mov [bz_gvz], ax
    mov [bz_air], al
    mov [bz_sqf], ax            ; (and bz_ghv)
    mov [bz_btok], al           ; wave 6: a capture spends the boost's token,
    mov [bz_bgr], al            ; and (6b) closes the grace
    mov [bz_onp], al
    mov [bz_tseg], al
    mov di, [es:si + BZP_TSEGS]
    mov ax, [es:di]
    mov [bz_tcnt], ax
    inc word [bz_ntube]
    mov dx, bx
    mov si, bz_nbr + BZN_C
    call bz_h4
    call bz_setz
    jmp bz_psync

; bz_transit - a step in a tube (137.12.6.1): the ghost along its segment,
; the count down; at 0 the segment's END exactly and the next; after the last,
; the EXIT - KEEP grounded along the mouth at max(s_in, BZ_TMIN), LAUNCH
; airborne at the record's velocity (a take-off), DROP airborne along the
; mouth as KEEP with gvz 0 - and the window refilled round OUT.  Clobbers
; AX, BX, CX, DX, SI, DI.
bz_transit:
    mov bl, [bz_tube]
    dec bx
    xor bh, bh
    call bz_lrecsi
    mov al, [bz_tseg]
    xor ah, ah
    mov cl, 4
    shl ax, cl
    mov di, [es:si + BZP_TSEGS]
    add di, ax                  ; DI = the segment (BZ_SEGREC bytes)
    mov ax, [es:di + 2]
    cwd
    add [bz_gx], ax
    adc [bz_gx + 2], dx
    mov ax, [es:di + 4]
    cwd
    add [bz_gy], ax
    adc [bz_gy + 2], dx
    mov ax, [es:di + 6]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    dec word [bz_tcnt]
    jnz .out
    xor ax, ax                  ; the segment's END, exactly
    mov [bz_gx], al
    mov [bz_gx + 3], al
    mov [bz_gy], al
    mov [bz_gy + 3], al
    mov [bz_gz], al
    mov ax, [es:di + 8]
    mov [bz_gx + 1], ax
    mov ax, [es:di + 10]
    mov [bz_gy + 1], ax
    mov ax, [es:di + 12]
    mov [bz_gz + 1], ax
    mov al, ah
    cbw
    mov [bz_gz + 3], ah
    inc byte [bz_tseg]
    mov al, [bz_tseg]
    cmp al, [es:si + BZP_TNSEG]
    jae .exit
    mov ax, [es:di + BZ_SEGREC]
    mov [bz_tcnt], ax
.out:
    BZT_GOING                   ; (still in the tube: bz_ps)
.exit:
    xor ax, ax
    mov [bz_tube], al
    mov [bz_tseg], al
    mov ax, [bz_gz + 1]         ; ztop = z, whole px
    mov [bz_ztop], ax
    mov al, [es:si + BZP_TSUB]
    cmp al, BZ_TK_LAUNCH
    jne .keep
    mov ax, [es:si + BZP_TGVX]  ; LAUNCH: the cannon's velocity, a take-off
    mov [bz_gvx], ax
    mov ax, [es:si + BZP_TGVY]
    mov [bz_gvy], ax
    mov ax, [es:si + BZP_TGVZ]
    mov [bz_gvz], ax
    mov byte [bz_air], 1
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    jmp short .win
.keep:                          ; KEEP grounded, DROP airborne: along the
    cmp al, BZ_TK_DROP          ; mouth at max(s_in, BZ_TMIN), gvz 0
    mov al, 0
    jne .k1
    inc ax
.k1:
    mov [bz_air], al
    mov ax, [bz_tsin]
    cmp ax, BZ_TMIN
    jae .v
    mov ax, BZ_TMIN
.v:
    xor dx, dx
    mov cl, [es:si + BZP_TDIR]  ; 0 +x, 1 -x, 2 +y, 3 -y
    test cl, 1
    jz .vs
    neg ax
.vs:
    test cl, 2
    jnz .vy
    xchg ax, dx
.vy:
    mov [bz_gvx], dx
    mov [bz_gvy], ax
    xor ax, ax
    mov [bz_gvz], ax
.win:
    cmp byte [bz_air], 0        ; round 3b (137.17.17): a DROP or LAUNCH exit
    je .w9                      ; takes the token unless a boost is spent
    call bz_atok
.w9:
    BZT_EXITED                  ; the window round OUT (bz_ps with it)

; bz_atok - round 3b (137.17.17): a launch OUT OF THE AIR (a spring under a
; contact, a tube's DROP or LAUNCH exit) takes the boost's token unless a
; boost is spent: bz_btok = 1 - bz_bsp, bz_zoff = bz_ztop.  Clobbers AX.
bz_atok:
    mov ax, [bz_ztop]
    mov [bz_zoff], ax
    mov al, [bz_bsp]
    xor al, 1
    mov [bz_btok], al
    ret

