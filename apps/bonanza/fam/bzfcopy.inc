; =============================================================================
; apps/bonanza/fam/bzfcopy.inc - the package's helpers a FAMILY PART needs,
; COPIED (SPEC.md 130.25.6.2: a part names no code label of the package, so a
; call into it cannot assemble).  Each answers exactly what the package's
; routine of the same name answers; a part asks for the ones it calls with
; %define FC_<NAME> before including this.  Written once here for every part
; (story 9.8's three), never a copy a part.
; =============================================================================

%ifdef FC_LRECSI
; bz_lrecsi - BX = a prop's index -> SI = its record's offset in the course
; (bzwheel.inc's).  Preserves all else.
bz_lrecsi:
    mov si, bx
    shl si, 1
    shl si, 1
    shl si, 1
    shl si, 1
    shl si, 1
    add si, [bz_poff]
    ret
%endif

%ifdef FC_H4
; bz_h4 - the window cell at SI's floor at the point DL = u, DH = v (0 - 16),
; in quarter px: 8 z0 + sx u + sy v (z0 QUARTER units, SPEC.md 130.48), sx
; the slope byte's low nibble and sy
; its high one, each signed (bzphys.inc's, which reads the products out of
; its table bz_prod: here IMUL, the same numbers).  -> AX.  Clobbers BX, CX.
bz_h4:
    mov bl, [si + 1]            ; sy : sx
    mov al, bl
    mov cl, 4
    shl al, cl
    sar al, cl                  ; sx, signed
    imul dl                     ; sx u
    xchg ax, bx                 ; BX = sx u, AL = the slopes
    sar al, cl                  ; sy, signed
    imul dh                     ; sy v
    add bx, ax
    mov al, [si]
    cbw
    shl ax, 1
    shl ax, 1
    shl ax, 1                   ; 8 z0
    add ax, bx
    ret
%endif

%ifdef FC_SETZ
; AX = h4 -> bz_gz = 64 h4 (bzphys.inc's bz_setz).  Clobbers AX, CX, DX.
bz_setz:
    mov dx, ax
    sar dx, 1
    sar dx, 1
    ror al, 1
    ror al, 1
    and al, 0c0h
    mov [bz_gz], al
    mov [bz_gz + 1], dx
    mov al, dh
    cbw
    mov [bz_gz + 3], ah
    ret
%endif

%ifdef FC_PSYNC
; bz_psync - bz_ps from its facts (bzphys.inc's).  Preserves all.
bz_psync:
    push ax
    mov al, [bz_psp]
    cmp byte [bz_wol], 0
    je .a
    inc ax
.a:
    cmp byte [bz_tube], 0
    je .b
    or al, 2
.b:
    cmp byte [bz_onp], 0
    je .c
    or al, 4
.c:
    mov [bz_ps], al
    pop ax
    ret
%endif

%ifdef FC_VMAX
; bz_vmax - AX = max(|gvx|, |gvy|) (bzphys.inc's).  Clobbers CX, DX.
bz_vmax:
    mov ax, [bz_gvx]
    cwd
    xor ax, dx
    sub ax, dx
    xchg ax, cx
    mov ax, [bz_gvy]
    cwd
    xor ax, dx
    sub ax, dx
    cmp ax, cx
    jae .s
    xchg ax, cx
.s:
    ret
%endif

%ifdef FC_TOFF
; bz_toff - a take-off (bzphys.inc's).  Clobbers AX, DX.
bz_toff:
    mov byte [bz_air], 1
    mov byte [bz_btok], 1
    mov byte [bz_bsp], 0
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    mov [bz_zoff], ax
    mov ax, [bz_gvz]
    cwd
    add [bz_gz], ax
    adc [bz_gz + 2], dx
    ret
%endif

%ifdef FC_ATOK
; bz_atok - a launch out of the air takes the token unless a boost is spent
; (fam/bztube.inc's, which the TUBE part carries itself).  Clobbers AX.
bz_atok:
    mov ax, [bz_ztop]
    mov [bz_zoff], ax
    mov al, [bz_bsp]
    xor al, 1
    mov [bz_btok], al
    ret
%endif
