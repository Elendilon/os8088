; =============================================================================
; apps/bonanza/fam/gate.asm - BONANZA's SWITCHES, KEYS, GATES and DRAWBRIDGE
; family (SPEC.md 128.41, the props round's P6 and P7), held equal to
; bbcourse.GateFamily at every step.
;
; Four kinds, each a FLAT FLOOR cell of the grid with OBS:
;   PLATE   rolled over (grounded, not shattering) OPENS its CHANNEL (+18)
;   KEY     touched (any way) OPENS its channel; its pose 0 once it has
;   GATE    a WALL in the window while its channel is shut (CELL); +19 its way
;   BRIDGE  +18 its channel, or BZ_GT_TIMED and a popspike's timer (+21 ON,
;           +22 MASK, +23 SEED: DOWN while ((n + seed) AND mask) < on); +19
;           its DECK (signed half units), +20 its grid's +2 byte.  DOWN: CELL
;           writes the grid's floor back (absolute, so a kept cell is right);
;           UP: a NEAR VOID, the deck less BZ_GT_DROP, kind and surface 0 (a
;           broken crack's).  DOWN but the window's centre with the ball's
;           whole-px z under the deck: the near void still (no lift).
; The channels are the slot's +0, a bit each: LATCHING for the attempt (a
; play's start zeroes the slot; a respawn keeps it).  Opening one counts
; bz_nfev (the pickup's sound), asks for the refill (bz_fref) and MARKS every
; element of the channel (bz_fmark).  +1 the timed bridges (RESET's count), so
; STEP walks only for them: a flip between n and n + 1 marked, and refilled
; when in the window.  POSE: a plate 1 pressed, a key 1 not taken, a gate 1
; shut, a bridge 1 up.
;
; A FAMILY PART (SPEC.md 128.25.6.2), linked against the package's bss
; (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the package,
; AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

GT_CH       equ 18              ; the record: the channel (BZ_GT_TIMED)
GT_DECK     equ 19              ; a bridge's deck (a gate's way: the art's)
GT_GKD      equ 20              ; a bridge's grid +2 byte
GT_ON       equ 21              ; a timed bridge's timer
GT_MASK     equ 22
GT_SEED     equ 23
GT_ART      equ 24              ; SPEC.md 128.41.12: a gate's or bridge's ART (no lane of
                                ; its own); an art LANE (kind BZ_FK_GALANE): +19 its channel
GT_AFR      equ 4               ; an art's frames: the cell opens at the last
%if BZ_FK_KEY != BZ_FK_PLATE + 1 || BZ_FK_GATE != BZ_FK_PLATE + 2 || BZ_FK_BRIDGE != BZ_FK_PLATE + 3 || BZ_FK_GATELANE != BZ_FK_PLATE + 4
 %error "the gate family's kinds are consecutive: plate, key, gate, bridge"
%endif

    db 'BF'
    db BZ_FID_GATE
    db BZ_FAMV_GATE
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_CONTACT | BZ_FH_STEP | BZ_FH_POSE | BZ_FH_CELL
    db 5, BZ_FK_PLATE           ; five kinds: plate, key, gate, bridge, an art's lane
    db 0
    dw gt_reset, 0, gt_contact, gt_step, gt_pose, gt_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif

; RESET: the course's timed bridges counted
gt_reset:
    call gt_slot
    call gt_walk
    xor dx, dx
    jcxz .x
.l:
    cmp byte [es:si], BZ_FK_BRIDGE
    jne .n
    cmp byte [es:si + GT_CH], BZ_GT_TIMED
    jne .n
    inc dx
.n:
    add si, 32
    loop .l
.x:
    mov [di + 1], dl
    retf

; CONTACT (AH the kind): a plate under a grounded ball, or a key, opens its
; channel - once
gt_contact:
    cmp ah, BZ_FK_KEY
    je .open
    cmp ah, BZ_FK_PLATE
    jne .out
    cmp byte [bz_air], 0
    jne .out
    cmp byte [bz_mst], BZ_ST_SHAT
    je .out
.open:
    call gt_slot
    call gt_rec
    mov dl, [es:si + GT_CH]     ; DL = the channel
    mov cl, dl
    mov al, 1
    shl al, cl
    test [di], al
    jnz .out
    or [di], al
    inc word [bz_nfev]          ; (the pickup's sound)
    mov byte [bz_fref], 1
    call gt_walk                ; every element of the channel MARKED
    xor bx, bx
    jcxz .out
.l:
    mov al, [es:si]
    sub al, BZ_FK_PLATE
    cmp al, 3
    ja .n
    cmp [es:si + GT_CH], dl
    jne .n
    cmp byte [es:si + GT_ART], 0    ; (an art element has no lane to mark)
    jne .n
    call far [bz_fmkp]          ; (bz_fmark: the walk made; preserves all)
.n:
    add si, 32
    inc bx
    loop .l
.out:
    retf

; STEP: each timed bridge the count about to be made flips MARKED, and the
; window refilled when it is in it
gt_step:
    call gt_slot
    mov al, [bz_nstep]          ; SPEC.md 128.41.12 A5: channel c's art frame
    test al, 1                  ; steps on n AND 7 = 2 c
    jnz .t
    and al, 7
    shr al, 1
    mov cl, al                  ; CL = c
    mov dl, 1
    shl dl, cl
    test [di], dl               ; open?
    jz .t
    mov bl, cl
    xor bh, bh
    cmp byte [di + 2 + bx], GT_AFR - 1
    jae .t
    inc byte [di + 2 + bx]
    cmp byte [di + 2 + bx], GT_AFR - 1
    jb .m
    mov byte [bz_fref], 1       ; (at the last: the cell opens)
.m:
    call gt_walk                ; every art lane of channel c MARKED
    xor bx, bx
    jcxz .t
.ml:
    cmp byte [es:si], BZ_FK_GATELANE
    jne .mn
    cmp [es:si + GT_DECK], al   ; (+19 its channel; AL = c)
    jne .mn
    call far [bz_fmkp]
.mn:
    add si, 32
    inc bx
    loop .ml
.t:
    cmp byte [di + 1], 0
    je .x
    call gt_walk
    xor bx, bx
.l:
    jcxz .x
    cmp byte [es:si], BZ_FK_BRIDGE
    jne .nx
    cmp byte [es:si + GT_CH], BZ_GT_TIMED
    jne .nx
    mov al, [bz_nstep]          ; down on n against down on n + 1
    add al, [es:si + GT_SEED]
    mov ah, al
    inc ah
    mov dl, [es:si + GT_MASK]
    and al, dl
    and ah, dl
    cmp al, [es:si + GT_ON]
    sbb dl, dl
    cmp ah, [es:si + GT_ON]
    sbb dh, dh
    cmp dl, dh
    je .nx
    call far [bz_fmkp]          ; its lane MARKED
    push bx                     ; ...and in the window: the refill
    call gt_win
    pop bx
    jc .nx
    mov byte [bz_fref], 1
.nx:
    add si, 32
    inc bx
    dec cx
    jmp short .l
.x:
    retf

; POSE: AH = the kind, BX = the element -> AL
gt_pose:
    call gt_slot
    call gt_rec
    cmp ah, BZ_FK_GATELANE      ; an art lane: its channel's frame
    jne .ng
    push bx
    mov bl, [es:si + GT_DECK]
    xor bh, bh
    mov al, [di + 2 + bx]
    pop bx
    retf
.ng:
    cmp ah, BZ_FK_BRIDGE
    je .br
    mov cl, [es:si + GT_CH]     ; the channel open: 1
    mov al, [di]
    shr al, cl
    and al, 1
    cmp ah, BZ_FK_PLATE
    je .r
    xor al, 1                   ; (a key, a gate: 1 while shut)
.r:
    retf
.br:
    call gt_down
    xor al, 1                   ; (1 up)
    retf

; CELL: a shut gate's cell a WALL; a bridge's written from its record
gt_cell:
    call gt_slot                ; DI = the slot
    call gt_walk                ; ES:SI the records, CX their count
    jcxz .x
.r:
    mov dh, [es:si]
    sub dh, BZ_FK_GATE          ; DH 0 a gate, 1 a bridge
    cmp dh, 1
    ja .n
    call gt_win                 ; BX = its window cell's offset
    jc .n
    push cx
    or dh, dh
    jnz .br
    call gt_open                ; a gate: shut, a WALL (its surface kept)
    jnz .p
    and byte [bz_nbr + bx + 2], 0f0h
    or byte [bz_nbr + bx + 2], BZ_AR_WALL
    jmp short .p
.br:
    call gt_down                ; (clobbers CL)
    mov dl, [es:si + GT_DECK]   ; DL = the deck
    or al, al
    jz .up
    cmp bl, BZN_C               ; down: the centre, the ball under the deck?
    jne .dn
    mov al, dl
    cbw
    shl ax, 1
    shl ax, 1
    cmp [bz_gz + 1], ax
    jl .up
.dn:
    mov [bz_nbr + bx], dl       ; DOWN: the grid's floor
    mov al, [es:si + GT_GKD]
    mov [bz_nbr + bx + 2], al
    jmp short .p
.up:
    sub dl, BZ_GT_DROP          ; UP: the near void
    mov [bz_nbr + bx], dl
    mov byte [bz_nbr + bx + 2], 0
.p:
    pop cx
.n:
    add si, 32
    dec cx
    jnz .r
.x:
    retf

; ES:SI = a gate's or switched bridge's record, DI = the slot -> ZF clear (and
; AL 1) when it is OPEN: its channel's bit, or for an ART element its channel's
; frame at the last (SPEC.md 128.41.12 A6).  Clobbers CL, AL.
gt_open:
    mov cl, [es:si + GT_CH]
    cmp byte [es:si + GT_ART], 0
    jne .a
    mov al, [di]
    shr al, cl
    and al, 1
    ret
.a:
    push bx
    mov bl, cl
    xor bh, bh
    cmp byte [di + 2 + bx], GT_AFR - 1
    pop bx
    sbb al, al                  ; (0FFh under the last)
    inc al                      ; -> 0 shut, 1 open (ZF from inc)
    ret

; ES:SI = a bridge's record, DI = the slot -> AL 1 down, 0 up.  Clobbers CL.
gt_down:
    cmp byte [es:si + GT_CH], BZ_GT_TIMED
    jne gt_open
    mov al, [bz_nstep]
    add al, [es:si + GT_SEED]
    and al, [es:si + GT_MASK]
    cmp al, [es:si + GT_ON]
    sbb al, al
    neg al
    ret

; ES:SI = a record -> CF clear and BX = its cell's offset in bz_nbr (4 (3 dy'
; + dx'), dx' dy' 0 - 2), or CF set: not in the window.  Clobbers AX.
gt_win:
    mov al, [es:si + 2]         ; AL = wx - the window's wx + 1
    sub al, [bz_nwin]
    inc ax
    cmp al, 2
    ja .out
    mov ah, [es:si + 3]         ; AH = wy - the window's wy + 1
    sub ah, [bz_nwin + 1]
    inc ah
    cmp ah, 2
    ja .out
    mov bl, ah
    add bl, ah
    add bl, ah
    add bl, al
    xor bh, bh
    shl bx, 1
    shl bx, 1
    clc
    ret
.out:
    stc
    ret

; BX = an element -> ES:SI its record.  Preserves all else.
gt_rec:
    push cx
    mov es, [bz_cseg]
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    pop cx
    ret

; -> ES:SI the course's first record, CX the records.  Preserves all else.
gt_walk:
    mov es, [bz_cseg]
    mov si, [bz_poff]
    mov cl, [bz_nprop]
    xor ch, ch
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "gt_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
gt_slot:
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
 %error "the window's centre is its fifth cell (BZN_C 16): gt_cell's compare"
%endif
%if $ - $$ > BZ_FAMP_GATE * 16
 %error "the gate part passes its FAMILIES paras ceiling: raise it there"
%endif
