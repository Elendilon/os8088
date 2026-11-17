; =============================================================================
; apps/bonanza/fam/water.asm - BONANZA's WATER FAMILY (SPEC.md 128.32, the
; owner's design P1), held equal to bbcourse.WaterFamily at every step.
;
; A water cell is FLOOR at its top H in the grid (flat, sand, OBS); its element
; record's +18 is its BED B and +19 its top H (signed half units).  Two hooks:
;   CELL  every water cell in the window rewritten PER BALL: steel's at B (it
;         sinks down the column and rolls out of the arch), every other ball's
;         left at H (one continuous top).  Idempotent: bz_win9i keeps cells of
;         the last window, already rewritten.  With the window's CENTRE a water
;         cell: bz_mrec's HTHR raised to BZ_WA_HTHR (no shatter, no stun; the
;         value it replaced kept once, on the way in), bz_se the ball's water
;         entry - sand's force, drag and brake, and sand's restitution less a
;         quarter (bz_surfset's work, written again: a part never calls the
;         package) - with bz_surf sand, so the window's own surface test that
;         follows makes no bz_surfset.  With the centre not one and IN set, the
;         HTHR put back and bz_surf 0FFh: that test then rebuilds bz_se.
;   STEP  IN, airborne and below the centre's top: gvx = gvy = 0 (it sinks
;         straight down, never out of an arch above its sill) and gvz at least
;         -BZ_WA_SINK (steel sinks, never too fast to read);
;         and a material that changed (a pad's, a respawn's) asks for the
;         refill (bz_fref), so the next window is rewritten for the new ball.
; No state bits (a water cell has no state), no RESET: a play's start finds
; the slot zero and bz_mrec fresh, and a respawn's place refills the window
; (CELL), which puts HTHR back before any flag's material is copied.
; The slot (bz_fsl + BZF_SLOT AL): +0 the material STEP last saw, +1 IN, +2
; the HTHR replaced (word), +4 the centre's top, whole px (word).
;
; A FAMILY PART (SPEC.md 128.25.6.2), linked against the package's bss as the
; probe is (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

WA_IN       equ 1               ; the slot's bytes
WA_HTHR     equ 2
WA_TOP      equ 4
WA_BED      equ 18              ; the element's record: its bed, its top
WA_HTOP     equ 19

    db 'BF'
    db BZ_FID_WATER
    db BZ_FAMV_WATER
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_STEP | BZ_FH_CELL
    db 1, BZ_FK_WATER           ; one kind
    db 0
    dw 0, 0, 0, wa_step, 0, wa_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif

; CELL: the window's water cells for this ball, then the centre's rules
wa_cell:
    call wa_slot                ; DI = the slot
    mov es, [bz_cseg]
    mov si, [bz_poff]
    mov cl, [bz_nprop]
    xor ch, ch
    xor dx, dx                  ; DX = the centre's element's record, 0 none
.r:
    cmp byte [es:si], BZ_FK_WATER
    jne .n
    mov al, [es:si + 2]         ; AL = wx - the window's wx + 1, 0 - 2
    sub al, [bz_nwin]
    inc ax
    cmp al, 2
    ja .n
    mov ah, [es:si + 3]         ; AH = wy - the window's wy + 1
    sub ah, [bz_nwin + 1]
    inc ah
    cmp ah, 2
    ja .n
    mov bl, ah                  ; BX = 4 (3 AH + AL)
    add bl, ah
    add bl, ah
    add bl, al
    xor bh, bh
    shl bx, 1
    shl bx, 1
    cmp byte [bz_mat], BZ_MAT_STEEL
    jne .h
    mov al, [es:si + WA_BED]    ; steel: the cell's z0 the bed
    mov [bz_nbr + bx], al
.h:
    cmp bl, BZN_C
    jne .n
    mov dx, si
.n:
    add si, 32
    loop .r
    or dx, dx
    jz .out
    mov si, dx                  ; THE CENTRE a water cell: its top, px
    mov al, [es:si + WA_HTOP]
    cbw
    shl ax, 1
    shl ax, 1
    mov [di + WA_TOP], ax
    cmp byte [di + WA_IN], 0    ; (on the way in: the HTHR kept)
    jne .in
    mov byte [di + WA_IN], 1
    mov ax, [bz_mrec + BZM_HTHR]
    mov [di + WA_HTHR], ax
.in:
    mov word [bz_mrec + BZM_HTHR], BZ_WA_HTHR
    mov al, [bz_mrec + BZM_ACC] ; bz_se: force max(2, ACC >> 1), drag
    shr al, 1                   ; sand's, brake GRIP, e (EF >> 1) less its
    cmp al, 2                   ; >> BZ_WA_ESH
    jae .f
    mov al, 2
.f:
    mov ah, BZ_WA_SANDK
    mov [bz_se], ax
    mov al, [bz_mrec + BZM_GRIP]
    mov ah, [bz_mrec + BZM_EF]
    shr ah, 1
    mov cl, ah
%rep BZ_WA_ESH
    shr cl, 1
%endrep
    sub ah, cl
    mov [bz_se + 2], ax
    mov byte [bz_surf], BZ_SURF_SAND
    mov ax, ((1 << BZ_WA_SANDK) - 1) * 257  ; bz_dmask, and both remainders
    mov [bz_dmask], al          ; cut to it (bz_surfset's)
    and [bz_drx], ax
    mov al, [bz_se]             ; bz_ftg from the force: bz_ramp written
    add al, [bz_wacc]           ; again, [l] = ((AL + bz_wacc) l + 4) >> 3
    cbw
    mov dx, 4
    mov si, bz_ftg
    mov ch, BZ_LVLMAX + 1
    mov cl, 3
.l:
    mov bx, dx
    shr bx, cl
    mov [si], bl
    inc si
    add dx, ax
    dec ch
    jnz .l
    retf
.out:                           ; the centre not water: on the way out,
    cmp byte [di + WA_IN], 0    ; HTHR back and bz_surf 0FFh (the window's
    je .x                       ; test rebuilds bz_se, bz_surfset)
    mov byte [di + WA_IN], 0
    mov ax, [di + WA_HTHR]
    mov [bz_mrec + BZM_HTHR], ax
    mov byte [bz_surf], 0FFh
.x:
    retf

; STEP: the sink's cap; a changed material's refill
wa_step:
    call wa_slot
    cmp byte [di + WA_IN], 0
    je .m
    cmp byte [bz_air], 0
    je .m
    mov ax, [bz_gz + 1]         ; z's whole px, under the centre's top:
    cmp ax, [di + WA_TOP]       ; no way across (it sinks STRAIGHT down,
    jge .m                      ; never out of an arch above its sill),
    xor ax, ax                  ; and the fall capped
    mov [bz_gvx], ax
    mov [bz_gvy], ax
    cmp word [bz_gvz], -BZ_WA_SINK
    jge .m
    mov word [bz_gvz], -BZ_WA_SINK
.m:
    mov al, [bz_mat]
    cmp al, [di]
    je .x
    mov [di], al
    mov byte [bz_fref], 1
.x:
    retf

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "wa_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
wa_slot:
    push ax
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    pop ax
    ret

%if BZN_C != 16
 %error "the window's centre is its fifth cell (BZN_C 16): wa_cell's compare"
%endif
%if $ - $$ > BZ_FAMP_WATER * 16
 %error "the water part passes its FAMILIES paras ceiling: raise it there"
%endif
