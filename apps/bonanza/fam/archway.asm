; =============================================================================
; apps/bonanza/fam/archway.asm - BONANZA's ARCHWAY FAMILY (SPEC.md 130.39, the
; props round's P10): an arch over a path that a ball ROLLS UNDER - a CEILING -
; held equal to bbcourse.ArchFamily at every step.
;
; An archway cell is a FLAT FLOOR in the grid with NO OBS (its record is no
; owner: a pad may stand under the arch); its record's +18 is its CLEARANCE C,
; a signed word of whole px - the highest the ball's contact may be inside it.
; With `top` (SPEC.md 130.12.3.7: +21 bit 0 set; else +20 - +22 zero) +20 is
; T, the TOP's height as the window holds it (z0, a byte: 2 px a step) - the
; lintel's or the pipe's top, a FLOOR the ball lands and rolls on - and +22 FZ
; the cell's own z0 in the grid (the floor under it), for CELL's write-back.
; A WALKABLE WALL's element (the same record on a WALL cell: a walkable tube's body, an
; arch's leg) has C = 8000h: always its top.
; Two hooks:
;   CELL  every archway cell in the window: with the ball's whole-px z (Z,
;         [bz_gz + 1]) above C, the window's copy a FLOOR at T (kind nibble
;         BZ_AR_FLOOR, z0 T, its surface and flags kept) - or, with no top, a
;         WALL (kind nibble BZ_AR_WALL, the rest kept) and the centre's CC =
;         C; with Z at or under C, written BACK the FLOOR the grid holds (kind
;         nibble BZ_AR_FLOOR; with a top, z0 the record's +22, the grid's):
;         the window keeps its cells when it moves one cell (bz_win9i), so a
;         cell walled or topped for the last window's Z is written both ways.
;         The engine's own floor test then stops a ball under T less BZ_CLIMB
;         at the face - as it does a wall, the step's fallback putting back
;         one that came into the cell UNDER the slab over C - and lands one
;         over it on the top.  The slot: +0 LO, the highest C
;         walled or topped (8000h none), +2 HI, the lowest C left open (7FFFh
;         none), +4 CC, the centre's C unless it is topped (7FFFh: no ceiling).
;   STEP  Z > CC: z = CC (fraction 0) and a rising gvz -(gvz >> BZ_AR_RSH)
;         (the underside's rebound), Z = CC; then Z <= LO or Z > HI asks for
;         the refill (bz_fref) that writes the cells again from the new z.
; No RESET: a play's start and a respawn place the ball and refill (bz_place),
; which runs CELL before any STEP reads the slot.
;
; A FAMILY PART (SPEC.md 130.25.6.2), linked against the package's bss as the
; others are (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"
%include "fam/bzfwalk.inc"

AR_CLR      equ 18              ; the element's record: its clearance C (word)
AR_TOP      equ 20              ; ...its TOP's height T (byte, the window's z0)
AR_TF       equ 21              ; ...bit 0: it HAS a top (0: +20 zero too)
AR_FZ       equ 22              ; ...with a top, its cell's z0 in the grid (0 none)

    db 'BF'
    db BZ_FID_ARCHWAY
    db BZ_FAMV_ARCHWAY
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_STEP | BZ_FH_CELL
    db 1, BZ_FK_ARCHWAY         ; one kind
    db 0
    dw 0, 0, 0, ar_step, 0, ar_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 130.25.6.2)"
%endif

; CELL: the window's archway cells topped above the ball's band, the slot's
ar_cell:
    call ar_slot                ; DI = the slot
    mov word [di], 8000h        ; LO, HI, CC
    mov ax, 7fffh
    mov [di + 2], ax
    mov [di + 4], ax
    call ar_walk                ; the family's own records (130.25.6.10):
    mov bp, bx                  ; BP the list, CX its count
    jcxz .x
.r:
    call ar_recp
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
    mov dl, [es:si + AR_FZ]     ; DL = a top's z0 in the grid, DH = the kind:
    mov dh, BZ_AR_FLOOR         ; under C the FLOOR the grid holds, written
    cmp [bz_gz + 1], ax         ; back - bz_win9i KEEPS window cells, so one
    jle .o                      ; walled or topped for the last window's Z
    cmp ax, [di]                ; must not stay so (SPEC.md 130.12.3.7 T11)
    jle .t                      ; Z > C: LO = max(LO, C)
    mov [di], ax
.t:
    mov dl, [es:si + AR_TOP]    ; the TOP: a FLOOR at T, its surface and
    test byte [es:si + AR_TF], 1 ; flags kept (SPEC.md 130.12.3.7), the
    jnz .k                      ; centre's CC left open
    mov dh, BZ_AR_WALL          ; no TOP: a WALL (130.39.4), CC = C
    jmp short .c
.o:
    cmp ax, [di + 2]            ; Z <= C: HI = min(HI, C)
    jge .c
    mov [di + 2], ax
.c:
    cmp bl, BZN_C
    jne .k
    mov [di + 4], ax            ; (the centre's ceiling: CC = C)
.k:
    test byte [es:si + AR_TF], 1 ; z0: a top's T over C, its floor's under
    jz .kn                      ; it (no top: the grid's, never written)
    mov [bz_nbr + bx], dl
.kn:
    and byte [bz_nbr + bx + 2], 0f0h    ; the kind, its surface kept
    or [bz_nbr + bx + 2], dh
.n:
    inc bp
    loop .r
.x:
    xor ax, ax                  ; (130.25.6.11: an archway in the window, its
    cmp word [di], 8000h        ; STEP every step; none - LO, HI and CC still
    jne .w                      ; 8000h, 7FFFh, 7FFFh - no STEP until the next
    cmp word [di + 2], 7fffh    ; window)
    jne .w
    cmp word [di + 4], 7fffh
    jne .w
    mov ax, [bz_nstep]
    add ax, 4000h
.w:
    call ar_setwk
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

    BZ_FWALK ar_walk
    BZ_FSETWK ar_setwk
    BZ_FREC ar_recp, bp

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
