; =============================================================================
; apps/bonanza/fam/archway.asm - BONANZA's ARCHWAY FAMILY (SPEC.md 128.39, the
; props round's P10): an arch over a path that a ball ROLLS UNDER - a CEILING -
; held equal to bbcourse.ArchFamily at every step.
;
; An archway cell is a FLAT FLOOR in the grid with NO OBS (its record is no
; owner: a pad may stand under the arch); its record's +18 is its CLEARANCE C,
; a signed word of whole px - the highest the ball's contact may be inside it.
; Two hooks:
;   CELL  every archway cell in the window: with the ball's whole-px z (Z,
;         [bz_gz + 1]) above C, the window's copy a WALL (kind nibble
;         BZ_AR_WALL; the rest of its 4 bytes kept), so the engine's own wall
;         test stops the ball at the arch's face; the slot: +0 LO, the highest
;         C walled (8000h none), +2 HI, the lowest C left open (7FFFh none),
;         +4 CC, the centre's C (7FFFh: the centre is no archway cell).
;   STEP  Z > CC: z = CC (fraction 0) and a rising gvz -(gvz >> BZ_AR_RSH)
;         (the underside's rebound), Z = CC; then Z <= LO or Z > HI asks for
;         the refill (bz_fref) that writes the walls again from the new z.
; No RESET: a play's start and a respawn place the ball and refill (bz_place),
; which runs CELL before any STEP reads the slot.
;
; A FAMILY PART (SPEC.md 128.25.6.2), linked against the package's bss as the
; others are (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

AR_CLR      equ 18              ; the element's record: its clearance (word)

    db 'BF'
    db BZ_FID_ARCHWAY
    db BZ_FAMV_ARCHWAY
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_STEP | BZ_FH_CELL
    db 1, BZ_FK_ARCHWAY         ; one kind
    db 0
    dw 0, 0, 0, ar_step, 0, ar_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif

; CELL: the window's archway cells walled above the ball, the slot's band
ar_cell:
    call ar_slot                ; DI = the slot
    mov word [di], 8000h        ; LO, HI, CC
    mov ax, 7fffh
    mov [di + 2], ax
    mov [di + 4], ax
    mov dx, [bz_gz + 1]         ; DX = Z
    mov es, [bz_cseg]
    mov si, [bz_poff]
    mov cl, [bz_nprop]
    xor ch, ch
    jcxz .x
.r:
    cmp byte [es:si], BZ_FK_ARCHWAY
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
    mov ax, [es:si + AR_CLR]    ; AX = C
    cmp bl, BZN_C
    jne .c
    mov [di + 4], ax            ; (the centre's)
.c:
    cmp dx, ax
    jle .o
    and byte [bz_nbr + bx + 2], 0f0h    ; Z > C: a WALL, its surface kept
    or byte [bz_nbr + bx + 2], BZ_AR_WALL
    cmp ax, [di]
    jle .n
    mov [di], ax                ; LO = max(LO, C)
    jmp short .n
.o:
    cmp ax, [di + 2]
    jge .n
    mov [di + 2], ax            ; HI = min(HI, C)
.n:
    add si, 32
    loop .r
.x:
    retf

; STEP: the centre's ceiling, then the band's refill
ar_step:
    call ar_slot
    mov ax, [bz_gz + 1]         ; AX = Z
    cmp ax, [di + 4]
    jle .b
    mov ax, [di + 4]            ; above the underside: z = CC, fraction 0
    mov byte [bz_gz], 0
    mov [bz_gz + 1], ax
    cwd
    mov [bz_gz + 3], dl
    mov bx, [bz_gvz]            ; a rising gvz: -(gvz >> BZ_AR_RSH)
    or bx, bx
    jle .b
%rep BZ_AR_RSH
    sar bx, 1
%endrep
    neg bx
    mov [bz_gvz], bx
.b:
    cmp ax, [di]                ; Z <= LO or Z > HI: the walls written again
    jle .f
    cmp ax, [di + 2]
    jle .x
.f:
    mov byte [bz_fref], 1
.x:
    retf

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "ar_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
ar_slot:
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
 %error "the window's centre is its fifth cell (BZN_C 16): ar_cell's compare"
%endif
%if $ - $$ > BZ_FAMP_ARCHWAY * 16
 %error "the archway part passes its FAMILIES paras ceiling: raise it there"
%endif
