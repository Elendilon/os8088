; =============================================================================
; apps/bonanza/fam/seesaw.asm - BONANZA's SEE-SAW FAMILY (SPEC.md 130.42, the
; props round's P9), held equal to bbcourse.TiltFamily at every step.
;
; A see-saw is a TILT PLATE of NX x NY cells (2, 4 or 6 along its axis, 1 - 2
; across) on a pivot at its middle, in three POSES: 0 its rest, 1 FLAT, 2 its
; other end down.  Pose P's slope is s = (1 - P), negated when its REST has
; the plus end down; its cell k along the axis is a slope cell at
; z0 = PZ + 2 s (k - L / 2) quarter units (SPEC.md 130.48.4), its slopes byte
; s along the axis.
;   the PLATE's record: +16 FSB (a BYTE of bz_fst, the pose: RESPAWN class, so
;          a respawn puts it at rest), +18 NX, +19 NY, +20 TLF_AXY (its axis
;          is y) | TLF_PLUS (its rest has the plus end down), +21 PZ; its
;          anchor (+2, +3) its first cell.  No OBS: no owner.
;   a LANE's record (the second kind): +18 its plate's record.
; Hooks: RESET (the slot zeroed, every lane MARKED: the engine has put every
; plate at rest), CELL (every plate cell in the window written from its pose:
; +0 z0 and +1 the slopes, kind, surface and flags kept; idempotent), STEP (the
; WEIGHT: the ball grounded and whole on a plate's cell, on one half for
; BZ_TL_DW<ball> steps - BZ_TL_TS from FLAT - moves the pose one toward that
; half down: its byte written, the refill asked, its lanes marked, and the ball
; CARRIED, z the new floor at its point), POSE (a lane: its plate's pose).
; The slot (bz_fsl + BZF_SLOT AL): +0 the plate the count is for (its element
; + 1, 0 none), +1 the COUNT.
;
; A FAMILY PART (SPEC.md 130.25.6.2), linked against the package's bss as the
; probe is (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"
%include "fam/bzfwalk.inc"

TL_NX       equ 18              ; the plate's record
TL_NY       equ 19
TL_FL       equ 20
TL_PZ       equ 21
TL_PLATE    equ 18              ; a lane's: its plate
TLF_AXY     equ 1               ; +20's flags: the axis is y,
TLF_PLUS    equ 2               ; ...the rest has the plus end down,
TLF_TIME    equ 4               ; ...it is TIMED (SPEC.md 130.42.11):
TL_MASK     equ 22              ; +22 its period less 1,
TL_FLAT     equ 23              ; +23 its steps FLAT each half period,
TL_SEED     equ 24              ; +24 its seed
%if TLF_AXY != BZ_TL_FAXY || TLF_PLUS != BZ_TL_FPLUS || TLF_TIME != BZ_TL_FTIME
 %error "the plate's +20 flags are bbcourse's TL_FAXY and TL_FPLUS"
%endif
%if BZ_FK_SEESAWLANE != BZ_FK_SEESAW + 1
 %error "the see-saw family's kinds are consecutive: the plate, its lane"
%endif

    db 'BF'
    db BZ_FID_SEESAW
    db BZ_FAMV_SEESAW
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_STEP | BZ_FH_POSE | BZ_FH_CELL
    db 2, BZ_FK_SEESAW          ; two kinds: the plate, its lane
    db 0
    dw tl_reset, 0, 0, tl_step, tl_pose, tl_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 130.25.6.2)"
%endif

; RESET: the slot zeroed; each TIMED plate's byte its pose on this step (the
; engine has just put it at rest) and +2 their count; every lane marked
tl_reset:
    call tl_slot
    xor ax, ax
    mov [di], ax
    mov [di + 2], al
    call tl_walk                ; (the family's own records: 130.25.6.10)
.r:
    jcxz .m
    call tl_recp
    call tl_timed
    jz .n
    mov al, [bz_nstep]
    call tl_tpose
    call tl_sbyte
    mov [bx], al
    inc byte [di + 2]
.n:
    inc bp
    dec cx
    jmp short .r
.m:
    mov al, 0ffh                ; (every plate's lanes)
    call tl_mark
    retf

; CELL: every plate cell in the window written from its plate's pose
tl_cell:
    call tl_slot
    call tl_walk                ; ES = the course, BP its list, CX its count
.r:
    jcxz .x
    call tl_recp
    cmp byte [es:si], BZ_FK_SEESAW
    jne .n
    push cx
    call tl_sbyte
    mov ch, [bx]                ; CH = its pose
    xor di, di                  ; DI = the window cell's offset in bz_nbr
    mov dh, [bz_nwin + 1]       ; DH = wy, DL = wx: the window's rows, by
    dec dh                      ; wy then wx (bz_nbr's order)
    mov bh, 3
.wy:
    mov dl, [bz_nwin]
    dec dl
    mov bl, 3
.wx:
    call tl_on                  ; one of the plate's cells?
    jae .no
    mov al, ch
    push cx
    call tl_cellz
    pop cx
    mov [bz_nbr + di], ax       ; +0 z0, +1 the slopes
.no:
    add di, 4
    inc dl
    dec bl
    jnz .wx
    inc dh
    dec bh
    jnz .wy
    pop cx
.n:
    inc bp
    dec cx
    jmp short .r
.x:
    retf

; STEP: the ball's weight on a plate; then each TIMED plate to its pose on the
; next step (SPEC.md 130.42.11): on a change its byte, the refill, its lanes
; MARKED, and a ball grounded on it CARRIED
tl_step:
    push ax
    call tl_weigh
    pop ax
    call tl_slot                ; DI = the slot
    cmp byte [di + 2], 0        ; no timed plate: nothing to walk
    je .x
    call tl_walk
.t:
    jcxz .x
    call tl_recp
    mov bl, [ds:bp]             ; BX = the record's index
    xor bh, bh
    call tl_timed
    jz .tn
    mov al, [bz_nstep]          ; AL = its pose on n + 1
    inc ax
    call tl_tpose
    push bx
    call tl_sbyte
    cmp [bx], al
    mov [bx], al
    pop bx
    je .tn
    mov byte [bz_fref], 1       ; its window refilled
    push ax
    mov al, bl
    call tl_mark                ; ...its lanes drawn
    pop ax
    cmp byte [bz_air], 0        ; ...and a grounded ball on it CARRIED
    jne .tn
    push bx
    push cx
    push dx
    call tl_bcell
    call tl_on
    jae .tc
    call tl_carry
.tc:
    pop dx
    pop cx
    pop bx
.tn:
    inc bp
    dec cx
    jmp short .t
.x:
    retf

; the WEIGHT (a near proc of STEP's): the ball grounded and whole on a plate's
; cell - not a timed one's - for BZ_TL_DW<ball> steps tips it
tl_weigh:
    call tl_slot                ; DI = the slot
    cmp byte [bz_air], 0        ; airborne or shattering: no weight
    jne .off
    cmp byte [bz_mst], BZ_ST_SHAT
    je .off
    call tl_bcell               ; DL, DH = the ball's cell
    call tl_walk
.f:
    jcxz .off
    call tl_recp
    cmp byte [es:si], BZ_FK_SEESAW
    jne .fn
    mov bl, [ds:bp]             ; BX = the record's index
    xor bh, bh
    call tl_on
    jae .fn
    test byte [es:si + TL_FL], TLF_TIME
    jz .on                      ; (on a TIMED plate: no weight)
    jmp short .off
.fn:
    inc bp
    dec cx
    jmp short .f
.off:
    mov byte [di], 0
    ret
.on:                            ; ES:SI the plate, BX its element
    inc bx
    cmp [di], bl
    je .same
    mov [di], bl                ; a new plate: its count from 0
    mov byte [di + 1], 0
.same:
    dec bx
    push bx
    mov ax, [bz_gx + 1]         ; AX = the ball's place along the axis, gu;
    mov bl, [es:si + 2]         ; BL its anchor, CL its length
    mov cl, [es:si + TL_NX]
    test byte [es:si + TL_FL], TLF_AXY
    jz .a
    mov ax, [bz_gy + 1]
    mov bl, [es:si + 3]
    mov cl, [es:si + TL_NY]
.a:
    xor bh, bh                  ; BX = the pivot, 8 (2 anchor + L)
    xor ch, ch
    shl bx, 1
    add bx, cx
    mov cl, 3
    shl bx, cl
    cmp ax, bx
    pop bx
    je .x                       ; on the pivot: no way down
    mov ah, 0                   ; AH = the TARGET: the pose with the ball's
    jb .t                       ; half down (0 below the pivot at a minus
    mov ah, 2                   ; rest, 2 above it; the other way round at
.t:                             ; a plus rest)
    test byte [es:si + TL_FL], TLF_PLUS
    jz .t2
    xor ah, 2
.t2:
    push bx
    call tl_sbyte               ; BX = the pose's byte
    mov al, [bx]
    cmp al, ah
    jne .go
    mov byte [di + 1], 0        ; at the target: the count 0
    pop bx
.x:
    ret
.go:
    inc byte [di + 1]
    mov cl, BZ_TL_TS            ; CL = the steps it takes: from FLAT any ball's,
    cmp al, 1                   ; from an end the ball's weight
    je .thr
    mov cl, BZ_TL_DWR
    cmp byte [bz_mat], BZ_MAT_STEEL
    jne .g
    mov cl, BZ_TL_DWS
.g:
    cmp byte [bz_mat], BZ_MAT_GLASS
    jne .thr
    mov cl, BZ_TL_DWG
.thr:
    cmp [di + 1], cl
    jb .wait
    mov byte [di + 1], 0        ; TIPPED: the pose one toward the target
    inc ax
    cmp ah, al
    jae .w
    dec ax
    dec ax
.w:
    mov [bx], al
    pop bx
    mov byte [bz_fref], 1       ; the window refilled
    push ax
    mov al, bl
    call tl_mark                ; ...its lanes drawn
    pop ax
    call tl_carry               ; ...and the ball CARRIED
    ret
.wait:
    pop bx
    ret

; ES:SI = a plate, AL = its new pose, DL, DH = the ball's cell (one of the
; plate's) -> the ball CARRIED.  Preserves SI, DI, BP.
tl_carry:
    call tl_cellz               ; the ball CARRIED: z = the new floor
    mov bl, [bz_gx + 1]         ; at its point, 8 z0 + s w (w its gu in the
    test byte [es:si + TL_FL], TLF_AXY   ; cell along the axis), h4 in
    jz .w2                      ; quarter px
    mov bl, [bz_gy + 1]
.w2:
    and bx, 15
    cbw
    mov dl, cl                  ; (DL = s)
    mov cl, 3                   ; (8 z0: z0 quarter units, SPEC.md 130.48.4)
    shl ax, cl
    or dl, dl
    jz .h
    jns .hp
    sub ax, bx
    jmp short .h
.hp:
    add ax, bx
.h:
    mov bl, al                  ; z: the fraction (h4 AND 3) << 6, the whole
    and bl, 3                   ; px h4 >> 2, signed
    mov cl, 6
    shl bl, cl
    mov [bz_gz], bl
    sar ax, 1
    sar ax, 1
    mov [bz_gz + 1], ax
    cwd
    mov [bz_gz + 3], dl
    ret

; POSE: BX = a lane -> AL its plate's pose
tl_pose:
    mov es, [bz_cseg]
    call tl_rec
    mov bl, [es:si + TL_PLATE]
    xor bh, bh
    call tl_rec
    call tl_sbyte
    mov al, [bx]
    retf

; ES:SI = a plate, AL = a pose, DL, DH = one of its cells -> AL its z0, AH its
; slopes byte, CL its slope s (-1, 0, 1).  Preserves all else.
tl_cellz:
    push bx
    mov ah, 1                   ; AH = s = 1 - the pose, negated at a plus
    sub ah, al                  ; rest
    test byte [es:si + TL_FL], TLF_PLUS
    jz .s
    neg ah
.s:
    mov bl, dl                  ; BL = k, BH = L, along the axis
    sub bl, [es:si + 2]
    mov bh, [es:si + TL_NX]
    test byte [es:si + TL_FL], TLF_AXY
    jz .k
    mov bl, dh
    sub bl, [es:si + 3]
    mov bh, [es:si + TL_NY]
.k:
    shr bh, 1
    sub bl, bh                  ; BL = k - L / 2
    shl bl, 1                   ; ...in quarter units (SPEC.md 130.48.4)
    mov al, [es:si + TL_PZ]     ; AL = PZ + 2 s (k - L / 2)
    or ah, ah
    jz .z
    jns .p
    sub al, bl
    jmp short .z
.p:
    add al, bl
.z:
    mov cl, ah                  ; CL = s; AH = its nibble, the high one for y
    and ah, 15
    test byte [es:si + TL_FL], TLF_AXY
    jz .y
    shl ah, 1
    shl ah, 1
    shl ah, 1
    shl ah, 1
.y:
    pop bx
    ret

; AL = a plate's element (0FFh: every plate) -> each of its lanes MARKED
; (bz_fmark).  DI = the slot.  Preserves all but ES.
tl_mark:
    push ax
    push bx
    push cx
    push si
    push bp
    call tl_walk
.l:
    jcxz .x
    call tl_recp
    cmp byte [es:si], BZ_FK_SEESAWLANE
    jne .n
    cmp al, 0ffh
    je .m
    cmp [es:si + TL_PLATE], al
    jne .n
.m:
    mov bl, [ds:bp]
    xor bh, bh
    call far [bz_fmkp]
.n:
    inc bp
    dec cx
    jmp short .l
.x:
    pop bp
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -> DL, DH = the ball's cell.  Preserves all else.
tl_bcell:
    push ax
    push cx
    mov cl, 4
    mov ax, [bz_gx + 1]
    shr ax, cl
    mov dl, al
    mov ax, [bz_gy + 1]
    shr ax, cl
    mov dh, al
    pop cx
    pop ax
    ret

; ES:SI = a plate, DL, DH = a cell -> CF set when it is one of the plate's.
; Preserves all but the flags.
tl_on:
    push ax
    mov al, dl
    sub al, [es:si + 2]
    cmp al, [es:si + TL_NX]
    jae .x
    mov al, dh
    sub al, [es:si + 3]
    cmp al, [es:si + TL_NY]
.x:
    pop ax
    ret

; ES:SI = a record -> ZF clear when it is a TIMED plate.  Preserves all else.
tl_timed:
    cmp byte [es:si], BZ_FK_SEESAW
    jne .x                      ; (ZF clear: so set it)
    test byte [es:si + TL_FL], TLF_TIME
    ret
.x:
    cmp al, al
    ret

; ES:SI = a TIMED plate, AL = a step's low byte n -> AL its pose: t = (n +
; SEED) AND MASK, 1 when (t AND MASK / 2) + FLAT > MASK / 2 (the last FLAT
; steps of each half), else 0 in the first half, 2 in the second.  Preserves
; all else.
tl_tpose:
    push cx
    add al, [es:si + TL_SEED]
    and al, [es:si + TL_MASK]
    mov ch, [es:si + TL_MASK]
    shr ch, 1                   ; CH = the half period less 1
    mov cl, al
    and cl, ch
    add cl, [es:si + TL_FLAT]
    cmp cl, ch
    mov cl, 1
    ja .r
    dec cx
    cmp al, ch
    jbe .r
    mov cl, 2
.r:
    mov al, cl
    pop cx
    ret

; ES:SI = a plate -> BX its byte of bz_fst (FSB / 8).  Preserves all else.
tl_sbyte:
    mov bl, [es:si + BZP_FSB]
    xor bh, bh
    push cx
    mov cl, 3
    shr bx, cl
    pop cx
    add bx, bz_fst
    ret

; BX = a record's element -> SI its record (in [bz_cseg]).  Preserves all else.
tl_rec:
    push cx
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    pop cx
    ret

; DI = the slot -> ES = the course, BP = the slot's list of its records
; (DS), CX their count (bzfwalk.inc).  Preserves all else.
tl_walk:
    push bx
    call tl_fw
    mov bp, bx
    pop bx
    ret
    BZ_FWALK tl_fw
    BZ_FREC tl_recp, bp

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "tl_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
tl_slot:
    push ax
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    pop ax
    ret

%if $ - $$ > BZ_FAMP_SEESAW * 16
 %error "the see-saw part passes its FAMILIES paras ceiling: raise it there"
%endif
