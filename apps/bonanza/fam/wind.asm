; =============================================================================
; apps/bonanza/fam/wind.asm - BONANZA's WIND FAMILY (SPEC.md 128.34): the
; BLOWER, a fan grate on a flat floor that PUSHES the ball while the ball's
; centre is in the element's REGION, along its FACE, by its STRENGTH weighted
; by the ball - glass S << BZ_WD_GSH, rubber S, steel S >> BZ_WD_SSH - and,
; facing UP, only an AIRBORNE ball below its TOP while gvz < BZ_WD_LIFT (an
; UPDRAFT).  Steady, or in GUSTS off the step counter: blowing on step n while
; ((n + seed) AND mask) < ON, a function of n alone as a windmill's gate is,
; so the family keeps no state bit.  Its lane is a PENNANT, flying downwind
; while it blows (POSE).  bbcourse.WindFamily is the model, step for step.
;
; The element's record (128.34.3): +18 the face (0 +x, 1 -x, 2 +y, 3 -y,
; 4 up), +19 S, +20 - +23 the region X0 Y0 X1 Y1 (inclusive), +24 ON (0
; steady), +26 the period's MASK, +28 the SEED, +30 an updraft's TOP (whole
; px).  The SLOT (+0 the count, +1 on the blowers' element numbers, record
; order) is written by RESET, so STEP visits the blowers alone.
;
; THE FORCE-FIELD CORE is wd_field: given the element's record and the ball's
; centre cell it applies one element's push.  A family that PULLS (magnets) is
; the same routine with the push's sign and weighting from its own record:
; SPEC.md 128.34.9 says how the two would fold into one family.
;
; A FAMILY PART (SPEC.md 128.25.6.2), linked against the package's bss
; (bzlink.inc: no code label).  Entered by `call far` with DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"

WD_DIR      equ 18              ; the record's fields (SPEC.md 128.34.3)
WD_STR      equ 19
WD_X0       equ 20
WD_Y0       equ 21
WD_X1       equ 22
WD_Y1       equ 23
WD_ON       equ 24
WD_MASK     equ 26
WD_SEED     equ 28
WD_TOP      equ 30

    db 'BF'
    db BZ_FID_WIND              ; (bzcourse.inc's: the ID is FAMILIES' alone)
    db BZ_FAMV_WIND
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_STEP | BZ_FH_POSE
    db 1, BZ_FK_BLOWER          ; one kind, the blower
    db 0
    dw wd_reset, 0, 0, wd_step, wd_pose, 0
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif
%if BZ_WD_GSH != 1 || BZ_WD_SSH != 2
 %error "wd_field's weighting is one shift left for glass and two right for steel"
%endif
%if BZF_SLOT != 8
 %error "wd_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif

; RESET (either class): the slot's list of the course's blowers, record
; order.  Over bz_nprop, not bz_nlane: a play's RESET (bz_pinit) runs before
; bz_pread counts the lanes.  No lane is marked: a pose is a function of the
; step counter, which a respawn leaves as it was, and a play's start draws
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
    cmp byte [es:si], BZ_FK_BLOWER
    jne .n
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

; STEP: each blower of the list - a GUSTING one's lane MARKED where its next
; step's state differs from this one's - and while it blows this step its
; push applied (wd_field).  The ball's cell is the WINDOW's centre, bz_nwin
; (the cell the step's refills left it in: the model's wcell); a ball in a
; tube, holed out or shattering is pushed by nothing - its cell is taken as
; 0FFh, which no region reaches
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
    mov cl, 5
    mov si, bx
    shl si, cl
    add si, [bz_poff]           ; SI = its record
    cmp word [es:si + WD_ON], 0
    je .blow                    ; (steady: blowing, its pose never moves)
    mov ax, [bz_nstep]
    call wd_on                  ; CF: blowing on step n
    sbb ch, ch
    inc ax
    call wd_on                  ; ...and on n + 1, the pose the walk will draw
    sbb al, al
    cmp al, ch
    je .nm
    call far [bz_fmkp]          ; its lane MARKED, the next walk made (bz_fmark)
.nm:
    or ch, ch
    jz .nx
.blow:
    call wd_field
.nx:
    dec bp
    jnz .l
    retf

; POSE: 1 (the pennant flying) while the blower blows on step bz_nstep - the
; next step's - else 0 (furled)
wd_pose:
    mov es, [bz_cseg]
    mov cl, 5
    mov si, bx
    shl si, cl
    add si, [bz_poff]
    mov ax, [bz_nstep]
    call wd_on
    mov al, 0
    adc al, al
    retf

; wd_field - THE FORCE-FIELD CORE: element ES:SI, the centre's cell DL, DH -> its
; push, when the cell is in its region, added to the ball's velocity along its
; face; an updraft's only to an airborne ball below its TOP while gvz <
; BZ_WD_LIFT.  Clobbers AX, BX.
wd_field:
    cmp dl, [es:si + WD_X0]
    jb .out
    cmp dl, [es:si + WD_X1]
    ja .out
    cmp dh, [es:si + WD_Y0]
    jb .out
    cmp dh, [es:si + WD_Y1]
    ja .out
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
    cmp bl, BZ_WD_UP
    je .up
    shr bl, 1                   ; BL 0 x, 1 y; CF the minus sign
    jnc .pos
    neg ax
.pos:
    xor bh, bh
    shl bx, 1
    add [bz_gvx + bx], ax       ; (bz_gvy follows bz_gvx)
.out:
    ret
.up:
    cmp byte [bz_air], 0
    je .out
    mov bx, [bz_gz + 1]         ; whole px
    cmp bx, [es:si + WD_TOP]
    jge .out
    cmp word [bz_gvz], BZ_WD_LIFT
    jge .out
    add [bz_gvz], ax
    ret
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
