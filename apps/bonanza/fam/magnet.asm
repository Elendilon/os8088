; =============================================================================
; apps/bonanza/fam/magnet.asm - BONANZA's MAGNETS FAMILY (SPEC.md 130.33): one
; kind, `magnet`, a magnet on a post.  Its FIELD is the N cells out from the
; post along its way (record +18: bit 1 the y axis, bit 0 the negative way;
; +20 N).  A SIDE magnet pulls the ball's velocity toward its post, +21 S
; shifted right by k - 1 at the field's k-th cell; a HANGING one (+19 bit 0,
; `face down`: its arm over the field) LIFTS an airborne ball under its
; ceiling (+22, signed px): gvz += S, then gvz -= gvz >> 3 (the damping that
; makes S = 27 a hover against G = 24).  STEEL only, never in a tube nor on a
; holed ball.  ONE FIELD A CELL (the tool refuses two meeting), so the slot
; caches the ball's cell's one magnet and its force, and STEP walks the
; records only when the ball's cell changes.  The WIGGLE: while a magnet pulls,
; its lane's pose is 1 for BZ_MG_WIG steps, then 2, and round again; marked
; through bz_fmkp only where it changes, so an idle magnet costs no frame.
;
; THE FORCE-FIELD CORE is mg_scan (who is in range) and mg_apply (the force):
; a folded MAGNET + WIND family keeps both and changes the sign and the weight.
;
; Slot (BZF_SLOT bytes at bz_fsl + 8 AL): +0 +1 the cell the cache is of, +2
; +3 the pull on gvx and gvy (signed bytes), +4 the lift, +5 the ceiling, +6
; the magnet (its element + 1, 0 none), +7 the wiggle's count.  NO RESET hook:
; a play's start zeroes the slot - a cache of cell (0, 0) with no magnet, true
; since no field may hold that cell (the tool's rule) - and a respawn moves the
; ball's cell, which the same step's STEP sees.
; bbcourse.MagnetFamily is the model, step for step.
;
; A FAMILY PART (SPEC.md 130.25.6.2), linked against the package's bss
; (bzlink.inc: no code label).  Entered by `call far` with DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

    db 'BF'
    db BZ_FID_MAGNET            ; (bzcourse.inc's: the ID is FAMILIES' alone)
    db BZ_FAMV_MAGNET
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_STEP | BZ_FH_POSE
    db 1, BZ_FK_MAGNET          ; one kind
    db 0
    dw 0, 0, 0, mg_step, mg_pose, 0
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 130.25.6.2)"
%endif

; STEP: steel, out of a tube and not holed - the cache refreshed when the ball's
; cell moved (mg_scan), then the cell's magnet's force (mg_apply) and the
; wiggle's count; anything else stops the wiggle
mg_step:
    call mg_slot
    cmp byte [bz_mat], BZ_MAT_STEEL
    jne .stop
    mov al, [bz_tube]
    or al, [bz_hid]
    jnz .stop
    mov cl, 4                   ; DL, DH = the ball's cell (gx >> 12, gy >> 12)
    mov ax, [bz_gx + 1]
    shr ax, cl
    mov dl, al
    mov ax, [bz_gy + 1]
    shr ax, cl
    mov dh, al
    cmp dx, [di]
    je .have
    call mg_stop
    mov [di], dx
    xor ax, ax
    mov [di + 2], ax
    mov [di + 4], ax
    mov [di + 6], al
    call mg_scan
    call mg_one                 ; (a cell change's step: the force, no count -
    jmp short .out              ; it may have STOPPED a wiggle: one change a step)
.have:
    call mg_one
    jc .out
    mov al, [di + 7]            ; the wiggle: 1 .. 2 BZ_MG_WIG, round again
    inc ax
    cmp al, 2 * BZ_MG_WIG
    jbe .w
    mov al, 1
.w:
    mov [di + 7], al
    cmp al, 1                   ; pose 1 begins, or pose 2: its lane MARKED
    je .mk
    cmp al, BZ_MG_WIG + 1
    jne .out
.mk:
    xor bh, bh
    call far [bz_fmkp]          ; (bz_fmark: the walk made; BX the element)
.out:
    retf
.stop:
    call mg_stop
    retf

; POSE (BX the element): 0 idle; while it pulls 1, then 2
mg_pose:
    call mg_slot
    inc bx
    cmp bl, [di + 6]
    jne .z
    mov al, [di + 7]
    or al, al
    jz .z
    cmp al, BZ_MG_WIG
    mov al, 1
    jbe .r
    inc ax
.r:
    retf
.z:
    mov al, 0
    retf

; THE FORCE-FIELD CORE, who is in range: the magnet whose field holds cell DL,
; DH (one at most: the tool's rule) -> its element + 1 in [DI + 6] (0 none) and
; its force in +2 - +6 (zeroed by the caller).  Clobbers AX, BX, CX, SI, ES.
mg_scan:
    mov cl, [bz_nprop]
    xor ch, ch
    jcxz .out
    mov es, [bz_cseg]
    mov si, [bz_poff]
    xor bx, bx
.l:
    inc bx                      ; (BX = the element + 1)
    cmp byte [es:si], BZ_FK_MAGNET
    jne .n
    mov al, dl                  ; AL along, AH across: the cell less the post
    sub al, [es:si + 2]
    mov ah, dh
    sub ah, [es:si + 3]
    test byte [es:si + 18], 2
    jz .xa
    xchg al, ah                 ; (a y-axis field)
.xa:
    or ah, ah
    jnz .n
    test byte [es:si + 18], 1
    jz .pos
    neg al                      ; (the negative way)
.pos:
    dec al                      ; AL = k - 1: inside when under N (unsigned)
    cmp al, [es:si + 20]
    jb .hit
.n:
    add si, 32
    loop .l
.out:
    ret
.hit:
    mov [di + 6], bl
    test byte [es:si + 19], 1
    jnz .down
    mov cl, al                  ; a SIDE magnet: S >> (k - 1), toward the post
    mov al, [es:si + 21]
    shr al, cl
    test byte [es:si + 18], 1
    jnz .sg
    neg al
.sg:
    test byte [es:si + 18], 2
    jz .x
    mov [di + 3], al
    ret
.x:
    mov [di + 2], al
    ret
.down:
    mov ax, [es:si + 21]        ; a HANGING one: the lift, the ceiling
    mov [di + 4], ax
    ret

; THE FORCE-FIELD CORE, the force: the cached pull on gvx and gvy; the lift on
; an AIRBORNE ball below the ceiling, gvz += S then gvz -= gvz >> 3.
; Clobbers AX, DX.
mg_apply:
    mov al, [di + 2]
    cbw
    add [bz_gvx], ax
    mov al, [di + 3]
    cbw
    add [bz_gvy], ax
    mov al, [di + 4]
    or al, al
    jz .r
    cmp byte [bz_air], 0
    je .r
    mov al, [di + 5]
    cbw
    cmp [bz_gz + 1], ax         ; z (whole px, signed) under the ceiling
    jge .r
    mov al, [di + 4]
    xor ah, ah
    mov dl, [bz_nstep]          ; the BOBBLE: every BZ_MG_BOBP steps a kick of
    test dl, BZ_MG_BOBP - 1     ; BZ_MG_BOB, up and down in turn
    jnz .nb
    add ax, BZ_MG_BOB
    test dl, BZ_MG_BOBP
    jnz .nb
    sub ax, 2 * BZ_MG_BOB
.nb:
    add ax, [bz_gvz]
    mov dx, ax
    sar dx, 1
    sar dx, 1
    sar dx, 1
    sub ax, dx
    mov [bz_gvz], ax
.r:
    ret

; DI's slot's magnet's force, if it has one (mg_apply): BL = the element, CF
; none.  Clobbers AX, DX.
mg_one:
    mov bl, [di + 6]
    sub bl, 1
    jc .r
    call mg_apply
    clc
.r:
    ret

; DI's slot: the wiggle stopped, the magnet's lane MARKED if it was going.
; Clobbers BX.
mg_stop:
    cmp byte [di + 7], 0
    je .r
    mov byte [di + 7], 0
    mov bl, [di + 6]
    dec bx                      ; (the element: +6 holds it + 1, never 0 here)
    xor bh, bh
    call far [bz_fmkp]
.r:
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "mg_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
mg_slot:
    push ax
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    pop ax
    ret

%if $ - $$ > BZ_FAMP_MAGNET * 16
 %error "the magnet part passes its FAMILIES paras ceiling: raise it there"
%endif
