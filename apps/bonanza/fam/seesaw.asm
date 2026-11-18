; =============================================================================
; apps/bonanza/fam/seesaw.asm - BONANZA's SEE-SAW FAMILY (SPEC.md 128.42, the
; props round's P9), held equal to bbcourse.TiltFamily at every step.
;
; A see-saw is a TILT PLATE of NX x NY cells (2, 4 or 6 along its axis, 1 - 2
; across) on a pivot at its middle, in three POSES: 0 its rest, 1 FLAT, 2 its
; other end down.  Pose P's slope is s = (1 - P), negated when its REST has
; the plus end down; its cell k along the axis is a slope cell at
; z0 = PZ + s (k - L / 2) half units, its slopes byte s along the axis.
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
; A FAMILY PART (SPEC.md 128.25.6.2), linked against the package's bss as the
; probe is (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

TL_NX       equ 18              ; the plate's record
TL_NY       equ 19
TL_FL       equ 20
TL_PZ       equ 21
TL_PLATE    equ 18              ; a lane's: its plate
TLF_AXY     equ 1               ; +20's flags: the axis is y,
TLF_PLUS    equ 2               ; ...the rest has the plus end down
%if TLF_AXY != BZ_TL_FAXY || TLF_PLUS != BZ_TL_FPLUS
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
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif

; RESET: the slot zeroed; every lane marked (its plate is back at rest)
tl_reset:
    call tl_slot
    mov word [di], 0
    mov al, 0ffh                ; (every plate's lanes)
    call tl_mark
    retf

; CELL: every plate cell in the window written from its plate's pose
tl_cell:
    call tl_walk                ; ES:SI the records, CX their count
    xor bp, bp                  ; BP = the record's index
.r:
    jcxz .x
    cmp byte [es:si], BZ_FK_SEESAW
    jne .n
    push cx
    mov bx, bp
    call tl_bptr
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
    mov al, dl                  ; one of the plate's cells?
    sub al, [es:si + 2]
    cmp al, [es:si + TL_NX]
    jae .no
    mov al, dh
    sub al, [es:si + 3]
    cmp al, [es:si + TL_NY]
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
    add si, 32
    inc bp
    dec cx
    jmp short .r
.x:
    retf

; STEP: the ball's weight on a plate
tl_step:
    call tl_slot                ; DI = the slot
    cmp byte [bz_air], 0        ; airborne or shattering: no weight
    jne .off
    cmp byte [bz_mst], BZ_ST_SHAT
    je .off
    mov cl, 4                   ; DL, DH = the ball's cell
    mov ax, [bz_gx + 1]
    shr ax, cl
    mov dl, al
    mov ax, [bz_gy + 1]
    shr ax, cl
    mov dh, al
    call tl_walk
    xor bx, bx                  ; BX = the record's index
.f:
    jcxz .off
    cmp byte [es:si], BZ_FK_SEESAW
    jne .fn
    mov al, dl
    sub al, [es:si + 2]
    cmp al, [es:si + TL_NX]
    jae .fn
    mov al, dh
    sub al, [es:si + 3]
    cmp al, [es:si + TL_NY]
    jb .on
.fn:
    add si, 32
    inc bx
    dec cx
    jmp short .f
.off:
    mov byte [di], 0
    retf
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
    call tl_bptr                ; BX = the pose's byte
    mov al, [bx]
    cmp al, ah
    jne .go
    mov byte [di + 1], 0        ; at the target: the count 0
    pop bx
.x:
    retf
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
    call tl_cellz               ; ...and the ball CARRIED: z = the new floor
    mov bl, [bz_gx + 1]         ; at its point, 16 z0 + s w (w its gu in the
    test byte [es:si + TL_FL], TLF_AXY   ; cell along the axis), h4 in
    jz .w2                      ; quarter px
    mov bl, [bz_gy + 1]
.w2:
    and bx, 15
    cbw
    mov dl, cl                  ; (DL = s)
    mov cl, 4
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
    retf
.wait:
    pop bx
    retf

; POSE: BX = a lane -> AL its plate's pose
tl_pose:
    mov es, [bz_cseg]
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    mov bl, [es:si + TL_PLATE]
    xor bh, bh
    call tl_bptr
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
    mov al, [es:si + TL_PZ]     ; AL = PZ + s (k - L / 2)
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
; (bz_fmark).  Preserves all but ES.
tl_mark:
    push ax
    push bx
    push cx
    push si
    call tl_walk
    xor bx, bx
.l:
    jcxz .x
    cmp byte [es:si], BZ_FK_SEESAWLANE
    jne .n
    cmp al, 0ffh
    je .m
    cmp [es:si + TL_PLATE], al
    jne .n
.m:
    call far [bz_fmkp]
.n:
    add si, 32
    inc bx
    dec cx
    jmp short .l
.x:
    pop si
    pop cx
    pop bx
    pop ax
    ret

; BX = a record's element -> BX = its byte of bz_fst (FSB / 8).  ES = the
; course.  Preserves all else.
tl_bptr:
    push cx
    push si
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    mov bl, [es:si + BZP_FSB]
    xor bh, bh
    mov cl, 3
    shr bx, cl
    add bx, bz_fst
    pop si
    pop cx
    ret

; -> ES:SI the course's first record, CX the records.  Preserves all else.
tl_walk:
    mov es, [bz_cseg]
    mov si, [bz_poff]
    mov cl, [bz_nprop]
    xor ch, ch
    ret

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
