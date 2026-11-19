; =============================================================================
; apps/bonanza/fam/turntable.asm - BONANZA's QUARTER-TURN TURNTABLE FAMILY
; (SPEC.md 130.43, the props round's P11), held equal to bbcourse.TurnFamily at
; every step.
;
; An N x N table (2 or 3), HALF FILLED, turning a quarter turn every Q steps
; (32 or 64): its cells switch between FLOOR and GAP, and it carries nothing - a
; cell that turns into a gap drops the ball.  Each SWITCHING cell is an element
; (a 3 x 3's centre is the PIVOT, a plain floor); the grid holds it as a FLAT
; FLOOR at TZ with OBS, and CELL rewrites it in the 9-cell window.  Its record:
;   +18 TZ     its floor's z0 (quarter units, SPEC.md 130.48.4)
;   +19 SEQ    bit r: a floor at rotation r, the nibble written twice so bit
;              r + 1 is the next rotation's with no wrap
;   +20 QSH    the quarter's shift (Q = 1 << QSH), +21 QMASK (Q - 1)
;   +22 SEED   its phase, +23 WAT: the step of a quarter its WARNING starts (Q:
;              none) - a floor whose next rotation is a gap shows its seam
; With m = (n + SEED) AND 255 (n bz_nstep's low byte): the rotation r = m >>
; QSH AND 3, the step of the quarter t = m AND QMASK; the POSE 2 a gap (SEQ's
; bit r clear), 1 the warning (t >= WAT and bit r + 1 clear), else 0.
; Hooks (no slot, no RESET: stateless):
;   CELL  each element in the window that is a gap - or is the window's CENTRE
;         with the ball's whole-px z ([bz_gz + 1]) under its top, 4 TZ: the
;         ball has fallen into its hole, and a hole that closes over it must
;         not lift it - a NEAR VOID: TZ less 12 quarter units, kind and surface 0,
;         its flags kept (the membrane's: SPEC.md 130.38); every other
;         element in the window written back a FLOOR (TZ, KIND_FLOOR): the
;         window KEEPS its cells when it moves one cell (bz_win9i), and a cell
;         the centre's rule voided must not stay void once the centre leaves.
;   STEP  each element whose pose differs between n and n + 1 is MARKED
;         (bz_fmark) and, in the window, asks for the refill (bz_fref).  A pose
;         can change only where t of n + 1 is 0 (a turn) or WAT (the warning),
;         so every other element costs the one test.
;   POSE  the element's pose.
;
; A FAMILY PART (SPEC.md 130.25.6.2), linked against the package's bss as the
; others are (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"
%include "fam/bzfwalk.inc"

TT_TZ       equ 18              ; the record
TT_SEQ      equ 19
TT_QSH      equ 20
TT_QMASK    equ 21
TT_SEED     equ 22
TT_WAT      equ 23
TT_VOIDH    equ 12              ; a gap: quarter units under the floor (bbcourse.TT_VOID)
TT_KFLOOR   equ 1               ; a floor's kind byte: KIND_FLOOR, SURF_NORMAL (the
                                ; tool refuses a table on any other surface)

    db 'BF'
    db BZ_FID_TURNTABLE
    db BZ_FAMV_TURNTABLE
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_STEP | BZ_FH_POSE | BZ_FH_CELL
    db 1, BZ_FK_TURNTABLE       ; one kind
    db 0
    dw 0, 0, 0, tt_step, tt_pose, tt_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 130.25.6.2)"
%endif

; CELL: the window's gaps (and a fallen ball's centre) a NEAR VOID
tt_cell:
    call tt_slot                ; (a new window: the STEP runs next, 130.25.6.11)
    push ax
    xor ax, ax
    call tt_setwk
    pop ax
    call tt_walk                ; ES = the course, BP its list, CX its count
    mov bp, bx
    jcxz .x
.r:
    call tt_recp
    cmp byte [es:si], BZ_FK_TURNTABLE
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
    mov al, [bz_nstep]
    call tt_at
    mov dl, [es:si + TT_TZ]     ; DX = a floor's z0 and kind byte
    mov dh, TT_KFLOOR
    cmp al, 2
    je .gap
    cmp bl, BZN_C               ; a floor: the centre's, with the ball under
    jne .w                      ; its top, a gap all the same
    mov al, dl
    cbw
    shl ax, 1                   ; 2 TZ px (quarter units, SPEC.md 130.48.4)
    cmp [bz_gz + 1], ax
    jge .w
.gap:
    sub dl, TT_VOIDH            ; a NEAR VOID: its kill 3 units down
    mov dh, 0
.w:
    mov [bz_nbr + bx], dl       ; (a floor written back too: a cell the
    mov [bz_nbr + bx + 2], dh   ; window KEEPS when it moves, bz_win9i, may
.n:                             ; hold the void the centre's rule wrote)
    inc bp
    loop .r
.x:
    retf

; STEP: each pose the count about to be made changes MARKED, and the window
; refilled when it is in it
tt_step:
    call tt_slot
    mov word [bz_fwkk], 4000h   ; (130.25.6.11: the nearest wake, a distance)
    call tt_walk
.l:
    jcxz .x
    call tt_rec
    cmp byte [es:si], BZ_FK_TURNTABLE
    jne .nx
    mov al, [bz_nstep]          ; t of n + 1: 0 (a turn) or WAT (the warning)
    inc ax
    add al, [es:si + TT_SEED]
    and al, [es:si + TT_QMASK]
    jz .c
    cmp al, [es:si + TT_WAT]
    jne .tn
.c:
    mov al, [bz_nstep]          ; the pose on n against n + 1
    call tt_at
    mov dl, al
    mov al, [bz_nstep]
    inc ax
    call tt_at
    cmp al, dl
    je .tn
    push bx
    mov bl, [bx]                ; (its element: the list's byte)
    xor bh, bh
    call far [bz_fmkp]          ; its lane MARKED
    pop bx
    mov al, [es:si + 2]         ; ...and in the window: the refill
    sub al, [bz_nwin]
    inc ax
    cmp al, 2
    ja .tn
    mov al, [es:si + 3]
    sub al, [bz_nwin + 1]
    inc ax
    cmp al, 2
    ja .tn
    mov byte [bz_fref], 1
.tn:
    mov dl, [bx]                ; its NEXT candidate step, when it can matter
    call tt_next
.nx:
    inc bx
    dec cx
    jmp short .l
.x:
    mov ax, [bz_fwkk]           ; THE WAKE: n + the nearest (130.25.6.11)
    add ax, [bz_nstep]
    call tt_setwk
    retf

; POSE: BX = the element -> AL its pose
tt_pose:
    mov es, [bz_cseg]
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    mov al, [bz_nstep]
    call tt_at
    retf

; ES:SI the record, AL = n's low byte -> AL the pose (0 a floor, 1 the warning,
; 2 a gap).  Preserves all else.
tt_at:
    push cx
    push dx
    add al, [es:si + TT_SEED]   ; AL = m
    mov dl, al
    mov cl, [es:si + TT_QSH]
    shr dl, cl                  ; DL = m >> QSH
    mov cl, dl
    and cl, 3                   ; CL = r
    mov dh, [es:si + TT_SEQ]
    shr dh, cl                  ; DH bit 0: a floor now; bit 1: after the turn
    and al, [es:si + TT_QMASK]  ; AL = t
    mov cl, 2
    test dh, 1
    jz .x                       ; a gap
    dec cx
    test dh, 2
    jnz .f                      ; a floor after the turn too: no warning
    cmp al, [es:si + TT_WAT]
    jae .x                      ; the warning
.f:
    dec cx
.x:
    mov al, cl
    pop dx
    pop cx
    ret

    BZ_FWALKA tt_walk
    BZ_FSETWK tt_setwk
    BZ_FTNEXT tt_next, TT_WAT, TT_QMASK, 1
%if TT_SEED != TT_QMASK + 1
 %error "bz_ftnext reads the SEED at the MASK + 1"
%endif

; AL = the slot -> DI = its bytes (the wake's index; the family keeps no slot
; byte).  Preserves all else.
tt_slot:
    push ax
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    pop ax
    ret
    BZ_FREC tt_rec, bx
    BZ_FREC tt_recp, bp

%if BZN_C != 16
 %error "the window's centre is its fifth cell (BZN_C 16): tt_cell's compare"
%endif
%if $ - $$ > BZ_FAMP_TURNTABLE * 16
 %error "the turntable part passes its FAMILIES paras ceiling: raise it there"
%endif
