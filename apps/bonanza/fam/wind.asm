; =============================================================================
; apps/bonanza/fam/wind.asm - BONANZA's WIND FAMILY (SPEC.md 137.34): the
; BLOWER, a fan grate on a flat floor that PUSHES the ball while the ball's
; cell is in the element's REGION, along its FACE, by its STRENGTH weighted by
; the ball - glass S << BZ_WD_GSH, rubber S, steel S >> BZ_WD_SSH.  Facing UP
; (an UPDRAFT) it pushes an AIRBORNE ball below its TOP while gvz <
; BZ_WD_LIFT, and with `lift` LAUNCHES a grounded one the push out-lifts
; gravity on.  Steady, or in GUSTS off the step counter: blowing on step n
; while ((n + seed) AND mask) < ON.  Its state is a BYTE, the fan's SPIN
; counter: WD_SPIN while it blows with the ball in its region, one less a step
; after, the fan's lane turning (a frame every 4 steps) while it is not 0.  A
; blower with `flag` has its pennant as the lane instead, and its fan does not
; spin.  A gusting blower without a flag has a WISP, a second element the tool
; makes: its lane is the region's squiggles, there while the gust blows.
; bbcourse.WindFamily is the model, step for step.
;
; A blower's record (137.34.3): +16 its byte's FSB, +18 the face (0 +x, 1 -x,
; 2 +y, 3 -y, 4 up) OR the flags WD_FLIFT (8), WD_FFLAG (16), +19 S, +20 - +23 the
; region X0 Y0 X1 Y1 (inclusive), +24 ON (0 steady), +26 the period's MASK,
; +28 the SEED, +30 an updraft's TOP (whole px).  A wisp's: +18 its blower.
; The SLOT (+0 the count, +1 on the elements, record order) is RESET's.
;
; THE FORCE-FIELD CORE is wd_field: one element's push given its record and
; the ball's cell.  A family that PULLS (magnets) is the same routine with the
; push's sign and weighting from its own record (SPEC.md 137.34.9).
;
; A FAMILY PART (SPEC.md 137.25.6.2), linked against the package's bss
; (bzlink.inc: no code label).  Entered by `call far` with DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

WD_FSB      equ 16              ; the record's fields (SPEC.md 137.34.3)
WD_DIR      equ 18
WD_STR      equ 19
WD_X0       equ 20
WD_Y0       equ 21
WD_X1       equ 22
WD_Y1       equ 23
WD_ON       equ 24
WD_MASK     equ 26
WD_SEED     equ 28
WD_TOP      equ 30
WD_FLIFT    equ 8               ; +18's flags over the face (bzcourse.inc's BZ_WD_FLIFT, BZ_WD_FFLAG)
WD_FFLAG    equ 16

    db 'BF'
    db BZ_FID_WIND              ; (bzcourse.inc's: the ID is FAMILIES' alone)
    db BZ_FAMV_WIND
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_STEP | BZ_FH_POSE
    db 2, BZ_FK_BLOWER          ; two kinds, the blower and its wisp
    db 0
    dw wd_reset, 0, 0, wd_step, wd_pose, 0
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 137.25.6.2)"
%endif
%if BZ_WD_GSH != 1 || BZ_WD_SSH != 2
 %error "wd_field's weighting is one shift left for glass and two right for steel"
%endif
%if BZF_SLOT != 8
 %error "wd_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
%if BZ_FK_WISP != BZ_FK_BLOWER + 1 || BZ_WD_FANP != 4 || WD_FLIFT != BZ_WD_FLIFT || WD_FFLAG != BZ_WD_FFLAG
 %error "the kinds are blower, wisp; a fan's frame is (n >> 2) AND 3; the flags bzcourse.inc's"
%endif

; RESET (either class): the slot's list of the course's wind elements, record
; order.  Over bz_nprop, not bz_nlane: a play's RESET (bz_pinit) runs before
; bz_pread counts the lanes.  No lane is marked: a respawn leaves the step
; counter and the spin bytes (ATTEMPT) as they were, and a play's start draws
; every lane at its true pose (bz_lfull)
wd_reset:
    call wd_slot
    mov byte [di], 0
    mov cl, [bz_nprop]
    xor ch, ch
    jcxz .out
    mov es, [bz_cseg]
    mov si, [bz_poff]
    xor bx, bx
.l:
    mov al, [es:si]
    sub al, BZ_FK_BLOWER
    cmp al, 2
    jae .n
    inc byte [di]
    mov al, [di]
    cbw                         ; (the count: at most 7)
    xchg ax, bp
    mov [ds:di + bp], bl
.n:
    add si, 32
    inc bx
    loop .l
.out:
    retf

; STEP: each element of the list.  A WISP: its lane MARKED on its blower's
; gust's turns.  A BLOWER: a flagged gusting one's lane marked on its turns;
; while it blows this step its push (wd_field) - the ball's cell the WINDOW's
; centre, bz_nwin, and none (0FFh) for a ball in a tube, holed out or
; shattering; and without a flag its SPIN byte - WD_SPIN while it blows with
; the cell in its region, else one less (not under 0) - its fan's lane marked
; where the frame it shows moves
wd_step:
    call wd_slot
    mov dx, [bz_nwin]           ; DL wx, DH wy
    mov al, [bz_tube]
    or al, [bz_hid]
    jnz .dead
    cmp byte [bz_mst], BZ_ST_SHAT
    jne .live
.dead:
    mov dl, 0FFh
.live:
    mov al, [di]                ; (the list's count: a course naming the
    cbw                         ; family places one at least)
    xchg ax, bp
    mov es, [bz_cseg]
.l:
    inc di
    mov bl, [di]
    xor bh, bh
    call wd_rec                 ; SI = its record
    cmp byte [es:si], BZ_FK_WISP
    jne .blower
    call wd_vis                 ; (off the slice its mark would be dropped:
    jnc .nx                     ; no gust test, 137.34.14)
    push si
    mov al, [es:si + WD_DIR]    ; (a wisp: its blower's gust)
    xor ah, ah
    xchg ax, bx
    call wd_rec
    xchg ax, bx
    call wd_turn
    pop si
    jmp short .nx
.blower:
    test byte [es:si + WD_DIR], WD_FFLAG
    jz .nf
    call wd_vis
    jnc .nf
    call wd_turn                ; (a flag: marked on its gust's turns)
.nf:
    mov ch, 0                   ; CH: 1 blowing with the cell in its region
    cmp dl, [es:si + WD_X0]     ; the REGION first: outside it neither the
    jb .nb                      ; push nor the spin wants the gust test
    cmp dl, [es:si + WD_X1]     ; (137.34.14; 0FFh dead is never inside)
    ja .nb
    cmp dh, [es:si + WD_Y0]
    jb .nb
    cmp dh, [es:si + WD_Y1]
    ja .nb
    mov ax, [bz_nstep]
    call wd_on
    jnc .nb
    call wd_field
    adc ch, 0
.nb:
    test byte [es:si + WD_DIR], WD_FFLAG
    jnz .nx
    push bx                     ; THE FAN: its byte, old in AH -> new in CH
    mov bl, [es:si + WD_FSB]
    mov cl, 3
    shr bl, cl
    xor bh, bh
    mov ah, [bz_fst + bx]
    or ch, ch
    mov ch, BZ_WD_SPIN
    jnz .sp
    mov ch, ah
    or ch, ch
    jz .sp
    dec ch
.sp:
    mov [bz_fst + bx], ch
    pop bx
    call wd_vis                 ; (the frames compared only for a lane that
    jnc .nx                     ; can be marked)
    mov al, [bz_nstep]
    call wd_fp                  ; the frame it showed (AH the old byte, n)
    mov cl, al
    mov ah, ch
    mov al, [bz_nstep]
    inc al
    call wd_fp                  ; ...and the one it shows (the new, n + 1)
    cmp al, cl
    je .nx
    call far [bz_fmkp]          ; its lane MARKED, the next walk made (bz_fmark)
.nx:
    dec bp
    jnz .l
    retf

; POSE: a wisp 1 while its blower blows on step bz_nstep (the next step's); a
; flagged blower the same of its own; a fan its frame
wd_pose:
    mov es, [bz_cseg]
    call wd_rec
    mov ax, [bz_nstep]
    cmp byte [es:si], BZ_FK_WISP
    jne .b
    mov bl, [es:si + WD_DIR]
    xor bh, bh
    call wd_rec
    jmp short .on
.b:
    test byte [es:si + WD_DIR], WD_FFLAG
    jz .fan
.on:
    call wd_on
    mov al, 0
    adc al, al
    retf
.fan:
    mov bl, [es:si + WD_FSB]
    mov cl, 3
    shr bl, cl
    xor bh, bh
    mov ah, [bz_fst + bx]
    call wd_fp
    retf

; AH = a fan's spin byte, AL = n's low byte -> AL its frame: (n >> 2) AND 3,
; 0 at rest
wd_fp:
    or ah, ah
    jz .z
    shr al, 1
    shr al, 1
    and al, 3
    ret
.z:
    mov al, 0
    ret

; ES:SI an element whose gust decides its lane, BX the element to mark: MARKED
; when its state on step n + 1 differs from its state on n (none, steady).
; Clobbers AX, CX.
wd_turn:
    mov ax, [bz_nstep]
    call wd_on
    sbb ch, ch
    inc ax
    call wd_on
    sbb al, al
    cmp al, ch
    je .s
    call far [bz_fmkp]          ; its lane MARKED, the next walk made (bz_fmark)
.s:
    ret

; wd_field - THE FORCE-FIELD CORE: element ES:SI, the ball's cell DL, DH -> CF
; set when the cell is in its region, and then its push added to the ball's
; velocity along its face; an updraft's below its TOP to an airborne ball
; while gvz < BZ_WD_LIFT, or with `lift` a grounded ball LAUNCHED when the
; push beats BZ_G: airborne, gvz the push, its take-off z its own.  Clobbers
; AX.
wd_field:
    cmp dl, [es:si + WD_X0]
    jb .out
    cmp dl, [es:si + WD_X1]
    ja .out
    cmp dh, [es:si + WD_Y0]
    jb .out
    cmp dh, [es:si + WD_Y1]
    ja .out
    push bx
    mov al, [es:si + WD_STR]    ; AX = the push: glass S x 2, rubber S, steel S / 4
    xor ah, ah
    mov bl, [bz_mat]
    cmp bl, BZ_MAT_GLASS
    jne .ng
    shl ax, 1
.ng:
    cmp bl, BZ_MAT_STEEL
    jne .w
    shr ax, 1
    shr ax, 1
.w:
    mov bl, [es:si + WD_DIR]
    and bl, 7
    cmp bl, BZ_WD_UP
    je .up
    shr bl, 1                   ; BL 0 x, 1 y; CF the minus sign
    jnc .pos
    neg ax
.pos:
    xor bh, bh
    shl bx, 1
    add [bz_gvx + bx], ax       ; (bz_gvy follows bz_gvx)
.in:
    pop bx
    stc
    ret
.out:
    clc
    ret
.up:
    mov bx, [bz_gz + 1]         ; whole px
    cmp bx, [es:si + WD_TOP]
    jge .in
    cmp byte [bz_air], 0
    je .gnd
    cmp word [bz_gvz], BZ_WD_LIFT
    jge .in
    add [bz_gvz], ax
    jmp short .in
.gnd:
    test byte [es:si + WD_DIR], WD_FLIFT
    jz .in
    cmp ax, BZ_G
    jbe .in
    mov byte [bz_air], 1        ; LAUNCHED (the take-off's own z: bz_toff's)
    mov [bz_gvz], ax
    mov [bz_ztop], bx
    mov [bz_zoff], bx
    jmp short .in
%if bz_gvy != bz_gvx + 2
 %error "wd_field indexes bz_gvx by the axis: bz_gvy must follow it"
%endif

; CF = 1 while element ES:SI blows on step AX: steady (ON 0), or ((AX + seed)
; AND mask) < ON.  Preserves every register.
wd_on:
    cmp word [es:si + WD_ON], 0
    je .yes
    push ax
    add ax, [es:si + WD_SEED]
    and ax, [es:si + WD_MASK]
    cmp ax, [es:si + WD_ON]     ; (CF: under ON)
    pop ax
    ret
.yes:
    stc
    ret

; ES:SI element BX's record (BH 0) -> CF set when its lane can be MARKED: in
; the walk's slice [bz_lr0, bz_lr1) (a lone element's lane is its index) and
; not held OUT of the column band (bz_lout), or a
; GROUP MEMBER (bz_fmark tests its lanes).  Off it, bz_fmark drops the mark,
; so a test that decides only a mark is skipped (SPEC.md 137.34.14).
; Preserves all but the flags.
wd_vis:
    test byte [es:si + BZP_FLAGS], BZ_PF_GRP
    jnz .y
    cmp bl, [bz_lr0]
    jb .n
    cmp bl, [bz_lr1]
    jae .n
    cmp byte [bz_lout + bx], 0  ; (OUT of the column band: dropped too,
    jne .n                      ; 137.19.10 item 12)
.y:
    stc
    ret
.n:
    clc
    ret

; BX = an element -> SI = its record's offset in [bz_cseg].  Clobbers CL.
wd_rec:
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Clobbers AH.
wd_slot:
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    ret

%if $ - $$ > BZ_FAMP_WIND * 16
 %error "the wind part passes its FAMILIES paras ceiling: raise it there"
%endif
