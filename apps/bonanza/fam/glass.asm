; =============================================================================
; apps/bonanza/fam/glass.asm - BONANZA's GLASS FAMILY (SPEC.md 128.25.8,
; 128.25.18): the CRACKED TILE (`crack`) and the GLASS PATH tile (`glass`),
; held equal to bbcourse.GlassFamily at every step.
;
; A FAMILY PART (SPEC.md 128.25.6.2), linked against the package's bss as the
; probe is (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
;
; A crack's state is a BYTE of bz_fst (its FSB a multiple of 8, the tool lays
; byte elements first): 0 WHOLE, 1 cracked by one glass IMPACT, 2 - T + 1
; COUNTING to its break (T = BZ_CRACK_TS steel, BZ_CRACK_TR rubber), 0FFh
; BROKEN - which the CELL hook makes a VOID in the window, its kill the floor
; less 3 units.  A glass tile's is a bit, REVEALED.  The slot's +0 counts the
; cracks counting, so STEP walks nothing while it is 0; its +1 the cracks
; BROKEN, so CELL walks nothing while that is 0 (SPEC.md 128.19.10 item 8).  A TOUCH is the
; centre in the element's cell having begun step 6 grounded (bz_fair 0) or a
; contact this step (bz_nland moved from bz_fnl); the latter is an IMPACT.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

GL_BROKEN   equ 0FFh
GL_PARTNER  equ 18              ; EXPLORATORY (SPEC.md 128.25.18.1): a vanishing
GL_COMP     equ 19              ; crack's partner's index + 1 (0 none); 1 the companion

    db 'BF'
    db BZ_FID_GLASS
    db BZ_FAMV_GLASS
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_CONTACT | BZ_FH_STEP | BZ_FH_POSE | BZ_FH_CELL
    db 2, BZ_FK_CRACK           ; two kinds: crack, glass
    db 0
    dw gl_reset, 0, gl_contact, gl_step, gl_pose, gl_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif
%if BZ_FK_GLASS != BZ_FK_CRACK + 1
 %error "the part's run of kinds is crack, glass"
%endif

; RESET (either class: every crack is RESPAWN, cleared by the engine): no
; crack counting; the cracks BROKEN COUNTED again (+1: 0 when the engine has
; cleared them, the right count for a class that would keep one, SPEC.md
; 128.19.10 item 8); every crack's and glass tile's lane MARKED (its pose may
; have gone back) - every RECORD's, not every lane's: a GROUP MEMBER has no
; lane of its own and bz_fmark marks its group's (SPEC.md 128.32.5)
gl_reset:
    call gl_slot
    mov word [di], 0            ; (+0 none counting, +1 none broken)
    mov cl, [bz_nprop]
    xor ch, ch
    jcxz .out
    mov es, [bz_cseg]
    mov si, [bz_poff]
    xor bx, bx
.l:
    mov al, [es:si]
    sub al, BZ_FK_CRACK
    cmp al, 1
    ja .n
    call far [bz_fmkp]          ; (its lane MARKED, the walk made: bz_fmark,
    or al, al                   ; which preserves everything)
    jnz .n                      ; a crack, not a companion (its byte is its
    cmp byte [es:si + GL_COMP], 0 ; crack's), BROKEN: counted
    jne .n
    push si
    call gl_byte
    cmp byte [si], GL_BROKEN
    pop si
    jne .n
    inc byte [di + 1]
.n:
    add si, 32
    inc bx
    loop .l
.out:
    retf

; CONTACT: AH = the kind, BX = the element
gl_contact:
    call gl_slot
    mov dx, [bz_nland]
    cmp dx, [bz_fnl]            ; DL... ZF: no contact this step
    mov dl, 0
    je .noimp
    inc dx                      ; DL = 1: an IMPACT
    jmp short .touch
.noimp:
    cmp byte [bz_fair], 0       ; began step 6 airborne, no contact: no touch
    jne .out
.touch:
    cmp ah, BZ_FK_GLASS
    je .glass
    call gl_byte                ; SI = its byte
    mov al, [si]
    cmp al, GL_BROKEN
    je .out
    or dl, dl
    jz .roll
    cmp byte [bz_mat], BZ_MAT_GLASS ; an IMPACT: glass's first cracks it ...
    jne .brk
    or al, al
    jnz .brk
    mov byte [si], 1
    jmp short .mark
.brk:
    cmp al, 2                   ; ... anything else breaks it (a count ends)
    jb .brk2
    dec byte [di]
.brk2:
    mov byte [si], GL_BROKEN
    inc byte [di + 1]           ; (one more broken: CELL walks)
    mov byte [bz_fref], 1
    jmp short .mark
.roll:                          ; rolled on: steel and rubber start counting
    mov ah, [bz_mat]
    cmp ah, BZ_MAT_GLASS
    je .out
    cmp al, 2
    jae .out
    mov al, BZ_CRACK_TR + 1
    cmp ah, BZ_MAT_STEEL
    jne .tr
    mov al, BZ_CRACK_TS + 1
.tr:
    mov [si], al
    inc byte [di]
.mark:
    call gl_mark                ; its lane MARKED and the next walk made
.out:                           ; (bz_fmark, 128.25.6.3)
    retf
.glass:
    call gl_bit
    test [si], al
    jnz .out
    or [si], al
    jmp short .mark

; STEP: each counting crack counted down; at its end BROKEN, a refill asked for
gl_step:
    call gl_slot
    cmp byte [di], 0
    je .out
    mov es, [bz_cseg]
    mov cl, [bz_nprop]
    xor ch, ch
    mov si, [bz_poff]
    xor bx, bx
.l:
    cmp byte [es:si], BZ_FK_CRACK
    jne .n
    cmp byte [es:si + GL_COMP], 0   ; (a companion's byte is its crack's)
    jne .n
    push si
    call gl_byte
    mov al, [si]
    cmp al, 2
    jb .p
    cmp al, GL_BROKEN
    je .p
    dec ax
    cmp al, 1
    jne .keep
    mov al, GL_BROKEN           ; its last step: broken
    dec byte [di]
    inc byte [di + 1]
    mov byte [bz_fref], 1
    jmp short .mk
.keep:
    cmp al, BZ_CRACK_LATE + 1   ; (its last CRACK_LATE steps: pose 2)
    jne .st
.mk:
    call gl_mark                ; its lane marked, the next walk made
.st:
    mov [si], al
.p:
    pop si
.n:
    add si, 32
    inc bx
    loop .l
.out:
    retf

; POSE: AH = the kind, BX = the element -> AL
gl_pose:
    cmp ah, BZ_FK_GLASS
    je .glass
    call gl_byte
    mov ah, [si]
    mov al, 3                   ; broken
    cmp ah, GL_BROKEN
    je .p
    mov al, 0                   ; whole
    or ah, ah
    jz .p
    inc ax                      ; 1 cracked, or counting's first steps
    cmp ah, 2
    jb .p
    cmp ah, BZ_CRACK_LATE + 1
    ja .p
    inc ax                      ; 2: its last CRACK_LATE steps
.p:
    retf
.glass:
    call gl_bit
    and al, [si]
    jz .g
    mov al, 1
.g:
    retf

; CELL: every BROKEN crack in the window made a VOID there - its z0 less 6
; half units (3 units: the kill), kind and surface 0, its flags kept - once
; (a cell bz_win9i kept from the last window is already VOID).  Nothing
; broken (the slot's +1 0, most refills): nothing walked
gl_cell:
    call gl_slot
    cmp byte [di + 1], 0
    je .x
    mov es, [bz_cseg]
    mov si, [bz_poff]
    mov cl, [bz_nprop]
    xor ch, ch
    xor bx, bx
.r:
    cmp byte [es:si], BZ_FK_CRACK
    jne .n
    mov al, [es:si + 2]         ; dx = wx - window's wx + 1, 0 - 2 (the
    sub al, [bz_nwin]           ; window first: a crack out of it costs no
    inc al                      ; gl_byte - every crack of the course is
    cmp al, 2                   ; looked at on every refill, SPEC.md
    ja .n                       ; 128.25.18)
    mov ah, [es:si + 3]
    sub ah, [bz_nwin + 1]
    inc ah
    cmp ah, 2
    ja .n
    mov dl, ah                  ; DI = 4 (3 dy' + dx')
    add dl, ah
    add dl, ah
    add dl, al
    xor dh, dh
    shl dx, 1
    shl dx, 1
    mov di, dx
    push si
    call gl_byte                ; (preserves DI)
    cmp byte [si], GL_BROKEN
    pop si
    jne .n
    mov al, [bz_nbr + di + 2]
    and al, 15
    cmp al, 1                   ; (a FLOOR still: not yet overlaid)
    jne .n
    sub byte [bz_nbr + di], 6
    mov byte [bz_nbr + di + 2], 0
.n:
    add si, 32
    inc bx
    loop .r
.x:
    retf

; BX = an element -> its lane MARKED (bz_fmark), and its PARTNER's: a
; vanishing crack and its companion each name the other (record +18, the
; index + 1; 0 none - every glass tile and every crack that keeps a hole).
; Preserves all.
gl_mark:
    call far [bz_fmkp]
    push bx
    push cx
    push es
    mov es, [bz_cseg]
    mov cl, 5
    shl bx, cl
    add bx, [bz_poff]
    mov bl, [es:bx + GL_PARTNER]
    pop es
    pop cx
    or bl, bl
    jz .o
    dec bx                      ; (BH is the partner's: 0 - 254 < 256)
    xor bh, bh
    call far [bz_fmkp]
.o:
    pop bx
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
gl_slot:
    push ax
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    pop ax
    ret

; BX = a crack -> SI = its byte in bz_fst.  Preserves all else.
gl_byte:
    push bx
    push cx
    push es
    mov es, [bz_cseg]
    mov cl, 5
    shl bx, cl
    add bx, [bz_poff]
    mov bl, [es:bx + BZP_FSB]
    xor bh, bh
    mov cl, 3
    shr bx, cl
    lea si, [bz_fst + bx]
    pop es
    pop cx
    pop bx
    ret

; BX = a glass tile -> SI = its bit's byte in bz_fst, AL the bit.  Clobbers CL.
gl_bit:
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

%if BZF_SLOT != 8
 %error "gl_slot multiplies by BZF_SLOT with shifts"
%endif

; EVERY family row is OP_COMP (SPEC.md 128.25.6.2): zeros so LZB packs it
    times 48 db 0

%if $ - $$ > BZ_FAMP_GLASS * 16
 %error "the glass part passes its FAMILIES paras ceiling: raise it there"
%endif
