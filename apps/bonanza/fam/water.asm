; =============================================================================
; apps/bonanza/fam/water.asm - BONANZA's WATER FAMILY (SPEC.md 137.36, the
; owner's design P1), held equal to bbcourse.WaterFamily at every step.
;
; A water cell is FLOOR at its top H in the grid (flat, sand, OBS); its element
; record's +18 is its BED B, +19 its top H (signed QUARTER units, SPEC.md
; 137.48.4), +20 its ripple
; (BZ_WR_RIPPLE: a lane; BZ_WR_ALWAYS: animated always, else while the ball is
; in it).  Four hooks:
;   RESET the course's ALWAYS ripples counted (STEP walks for them only then).
;   CELL  every water cell in the window rewritten PER BALL: steel's at B (it
;         sinks down the column and rolls out of the arch), every other ball's
;         at the FLOAT LINE, H less a half unit (it rides IN the water: its
;         lower part behind the top, which the tool keys s + 1 with tops
;         WATER_FLOAT px up).  Idempotent: written from the record, so a cell
;         bz_win9i kept is written to the same.  With the window's CENTRE a
;         water cell: bz_mrec's HTHR raised to BZ_WA_HTHR (no shatter, no stun;
;         the value it replaced kept once, on the way in), bz_se the ball's
;         water entry - sand's force, drag and brake, sand's restitution less a
;         quarter (bz_surfset's work, written again: a part never calls the
;         package) - with bz_surf sand, so the window's own surface test that
;         follows makes no bz_surfset.  With the centre not one and IN set,
;         the HTHR put back and bz_surf 0FFh: that test then rebuilds bz_se.
;         And the ACTIVE ripple the centre's, its entry step kept; the one it
;         replaces MARKED when it stood at pose 1 (it goes back to 0).  A
;         GUARDED arch's exit (+20 WR_GUARDX, WR_GUARDY; SPEC.md 137.35.10) a
;         WALL while its water cell is the centre and the ball not steel, else
;         the FLOOR it is.
;   STEP  IN, airborne and under the float line: gvx = gvy = 0 (it sinks
;         straight down, never out of an arch above its sill), every 32 steps
;         gvz = +BZ_WA_BOB (the WOBBLE; BZ_WA_BOB 0 assembles none), else gvz
;         at least -BZ_WA_SINK; a material that changed asks for the refill
;         (bz_fref); and the ripple lanes whose pose the count about to be
;         made flips are MARKED (bz_fmark): every ALWAYS one each 2^WA_RSH
;         steps, the ACTIVE one each 2^WA_RSH steps from its entry.
;   POSE  ALWAYS: (step >> WA_RSH) & 1; the ACTIVE ripple: ((step - entry) >>
;         WA_RSH) & 1; any other 0 (the picture's rings).
; The slot (bz_fsl + BZF_SLOT AL): +0 the material STEP last saw, +1 IN, +2
; the HTHR replaced (word), +4 the centre's float line (quarter units), +5 the
; ACTIVE ripple's entry step (low byte), +6 the ALWAYS ripples, +7 the ACTIVE
; ripple (its element + 1, 0 none).
;
; A FAMILY PART (SPEC.md 137.25.6.2), linked against the package's bss as the
; probe is (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"
%include "fam/bzfwalk.inc"

WA_IN       equ 1               ; the slot's bytes
WA_HTHR     equ 2
WA_TOP      equ 4
WA_ENT      equ 5
WA_NALW     equ 6
WA_ACT      equ 7
WA_BED      equ 18              ; the element's record: its bed, its top, its ripple
WA_HTOP     equ 19
WA_RIP      equ 20
WR_RIPPLE   equ 1               ; +20's bits: a ripple lane, animated always,
WR_ALWAYS   equ 2               ; the +x arch guarded, the +y arch guarded
WR_GUARDX   equ 4
WR_GUARDY   equ 8
%if WR_RIPPLE != BZ_WR_RIPPLE || WR_ALWAYS != BZ_WR_ALWAYS || WR_GUARDX != BZ_WR_GUARDX || WR_GUARDY != BZ_WR_GUARDY
 %error "the water record's +20 bits are bbcourse's WR_RIPPLE, WR_ALWAYS, WR_GUARDX, WR_GUARDY"
%endif

    db 'BF'
    db BZ_FID_WATER
    db BZ_FAMV_WATER
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_STEP | BZ_FH_POSE | BZ_FH_CELL
    db 1, BZ_FK_WATER           ; one kind
    db 0
    dw wa_reset, 0, 0, wa_step, wa_pose, wa_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 137.25.6.2)"
%endif

; RESET: the ALWAYS ripples counted
wa_reset:
    call wa_slot
    xor dx, dx
    call wa_walk                ; (the family's own records: 137.25.6.10)
.l:
    jcxz .x
    call wa_lrec
    cmp byte [es:si], BZ_FK_WATER
    jne .n
    test byte [es:si + WA_RIP], WR_ALWAYS
    jz .n
    inc dx
.n:
    inc bx
    dec cx
    jmp short .l
.x:
    mov [di + WA_NALW], dl
    retf

; CELL: the window's water cells for this ball, then the centre's rules
wa_cell:
    call wa_slot                ; DI = the slot
    xor ax, ax                  ; (a new window: the STEP runs next, 137.25.6.11)
    call wa_setwk
    call wa_walk                ; ES = the course, BP its list, CL its count
    mov bp, bx                  ; (a byte: 255 props at most)
%if BZ_WA_FBSH                  ; CH = rubber's and glass's floor under the
    mov al, [bz_nstep]          ; top, quarter units (SPEC.md 137.48.4): the
    mov ch, BZ_WA_FBSH          ; bob's phase (the top, or the float line a
    xchg cl, ch                 ; half unit, 2, under it; SPEC.md 137.36.10)
    shr al, cl
    xchg cl, ch
    and al, 1
    shl al, 1
    mov ch, al
%else
    mov ch, 2
%endif
    xor dx, dx                  ; DX = the centre's element's record, 0 none
    and byte [di + WA_IN], 1    ; (bit 1: a water cell in the window, below)
    or cl, cl
    jz .done
.r:
    call wa_recp
    cmp byte [es:si], BZ_FK_WATER
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
    call wa_guard               ; (SPEC.md 137.35.10: its guarded arches)
    mov al, [es:si + WA_HTOP]   ; rubber's and glass's floor, H less CH
    sub al, ch                  ; (SPEC.md 137.36.10) ...
    or byte [di + WA_IN], 2
    cmp byte [bz_mat], BZ_MAT_STEEL
    jne .h
    mov al, [es:si + WA_BED]    ; ... steel's the bed
.h:
    mov [bz_nbr + bx], al
    cmp bl, BZN_C
    jne .n
    mov dx, si
.n:
    inc bp
    dec cl
    jnz .r
.done:
    xor bl, bl                  ; BL = the new ACTIVE ripple (0 none)
    or dx, dx
    jz .out
    mov si, dx                  ; THE CENTRE a water cell: its float line
    mov al, [es:si + WA_HTOP]
    dec ax                      ; (a half unit: 2 quarter units, 137.48.4)
    dec ax
    mov [di + WA_TOP], al
    test byte [es:si + WA_RIP], WR_RIPPLE
    jz .nr
    mov ax, si                  ; (its element + 1)
    sub ax, [bz_poff]
    mov cl, 5
    shr ax, cl
    inc ax
    mov bl, al
.nr:
    test byte [di + WA_IN], 1   ; (on the way in: the HTHR kept)
    jnz .in
    or byte [di + WA_IN], 1
    mov ax, [bz_mrec + BZM_HTHR]
    mov [di + WA_HTHR], ax
.in:
    mov word [bz_mrec + BZM_HTHR], BZ_WA_HTHR
    mov al, [bz_mrec + BZM_ACC] ; bz_se: force max(2, ACC >> 1), drag
    shr al, 1                   ; sand's, brake GRIP, e (EF >> 1) less its
    cmp al, 2                   ; >> BZ_WA_ESH
    jae .f
    mov al, 2
.f:
    mov ah, BZ_WA_SANDK
    mov [bz_se], ax
    mov al, [bz_mrec + BZM_GRIP]
    mov ah, [bz_mrec + BZM_EF]
    shr ah, 1
    mov cl, ah
%rep BZ_WA_ESH
    shr cl, 1
%endrep
    sub ah, cl
    mov [bz_se + 2], ax
    mov byte [bz_surf], BZ_SURF_SAND
    mov ax, ((1 << BZ_WA_SANDK) - 1) * 257  ; bz_dmask, and both remainders
    mov [bz_dmask], al          ; cut to it (bz_surfset's)
    and [bz_drx], ax
    mov al, [bz_se]             ; bz_ftg from the force: bz_ramp written
    add al, [bz_wacc]           ; again, [l] = ((AL + bz_wacc) l + 4) >> 3
    cbw
    push bx
    mov dx, 4
    mov si, bz_ftg
    mov ch, BZ_LVLMAX + 1
    mov cl, 3
.l:
    mov bx, dx
    shr bx, cl
    mov [si], bl
    inc si
    add dx, ax
    dec ch
    jnz .l
    pop bx
    jmp short .act
.out:                           ; the centre not water: on the way out,
    test byte [di + WA_IN], 1   ; HTHR back and bz_surf 0FFh (the window's
    jz .act                     ; test rebuilds bz_se, bz_surfset)
    and byte [di + WA_IN], 2
    mov ax, [di + WA_HTHR]
    mov [bz_mrec + BZM_HTHR], ax
    mov byte [bz_surf], 0FFh
.act:                           ; the ACTIVE ripple: BL the new one
    mov al, [di + WA_ACT]
    cmp al, bl
    je .x
    mov [di + WA_ACT], bl
    mov ah, [bz_nstep]          ; its entry: this step
    xchg ah, [di + WA_ENT]      ; AH = the old one's entry
    or al, al
    jz .x
    dec ax                      ; AL = the old one's element: back to pose
    xor bx, bx                  ; 0 - marked when it stood at 1 and is not
    mov bl, al                  ; an ALWAYS one
    mov al, [bz_nstep]
    sub al, ah
    test al, 1 << BZ_WA_RSH
    jz .x
    call wa_rec
    test byte [es:si + WA_RIP], WR_ALWAYS
    jnz .x
    call far [bz_fmkp]          ; its lane MARKED, the walk made (bz_fmark)
.x:
    retf

; STEP: the sink's stop, wobble and cap; a changed material's refill; the
; ripples' marks
wa_step:
    call wa_slot
    test byte [di + WA_IN], 1
    jz .m
    mov al, [di + WA_TOP]       ; DX = the float line, px (2 z, quarter units)
    cbw
    shl ax, 1
    xchg ax, dx
    cmp byte [bz_mat], BZ_MAT_STEEL
    jne .m
    cmp byte [bz_air], 0        ; STEEL, airborne under the float line:
    je .m                       ; no way across (it sinks STRAIGHT down,
    cmp [bz_gz + 1], dx         ; never out of an arch above its sill),
    jge .m
    xor ax, ax                  ; the wobble, the fall capped
    mov [bz_gvx], ax
    mov [bz_gvy], ax
%if BZ_WA_BOB
    test byte [bz_nstep], 31
    jnz .cap
    mov word [bz_gvz], BZ_WA_BOB
    jmp short .m
.cap:
%endif
    cmp word [bz_gvz], -BZ_WA_SINK
    jge .m
    mov word [bz_gvz], -BZ_WA_SINK
.m:
    mov al, [bz_mat]
    cmp al, [di]
    je .bb
    mov [di], al
    mov byte [bz_fref], 1
.bb:
%if BZ_WA_FBSH
    test byte [di + WA_IN], 2   ; the bob's flip (SPEC.md 137.36.10), a
    jz .rp                      ; water cell in the window and not steel -
    cmp byte [bz_mat], BZ_MAT_STEEL ; the next window rewritten; into the
    je .rp                      ; dip a ball resting on the water goes down
    mov al, [bz_nstep]          ; with its floor (no fall, no landing)
    inc ax
    test al, (1 << BZ_WA_FBSH) - 1
    jnz .rp
    mov byte [bz_fref], 1
    test al, 1 << BZ_WA_FBSH
    jz .rp
    test byte [di + WA_IN], 1
    jz .rp
    cmp byte [bz_air], 0
    jne .rp
    sub word [bz_gz], 4 << 8
    sbb word [bz_gz + 2], 0
%endif
.rp:                            ; the ripples' marks: AL = the count's next
    mov al, [bz_nstep]          ; value's phase
    inc ax
    test al, (1 << BZ_WA_RSH) - 1
    jnz .ac
    cmp byte [di + WA_NALW], 0  ; every ALWAYS ripple flips
    je .ac
    call wa_walk
.wl:
    jcxz .ac
    call wa_lrec
    cmp byte [es:si], BZ_FK_WATER
    jne .wn
    test byte [es:si + WA_RIP], WR_ALWAYS
    jz .wn
    push bx
    mov bl, [bx]                ; (its element: the list's byte)
    xor bh, bh
    call far [bz_fmkp]
    pop bx
.wn:
    inc bx
    dec cx
    jmp short .wl
.ac:                            ; the ACTIVE one flips 2^WA_RSH steps from
    mov bl, [di + WA_ACT]       ; its entry (not an ALWAYS one: marked above)
    or bl, bl
    jz .x
    mov al, [bz_nstep]
    inc ax
    sub al, [di + WA_ENT]
    test al, (1 << BZ_WA_RSH) - 1
    jnz .x
    dec bx
    xor bh, bh
    call wa_rec
    test byte [es:si + WA_RIP], WR_ALWAYS
    jnz .x
    call far [bz_fmkp]
.x:                             ; THE WAKE (137.25.6.11): the ball in or over
    xor ax, ax                  ; water (WA_IN), every step; else the next
    test byte [di + WA_IN], 3   ; ripple turn - an ALWAYS one at (n + 1)
    jnz .w                      ; AND 7 = 0, the ACTIVE one at (n + 1 - ENT)
    mov cx, 4000h               ; AND 7 = 0 - or none
    mov dx, (1 << BZ_WA_RSH) - 1
    cmp byte [di + WA_NALW], 0
    je .wa
    mov ax, -2
    sub ax, [bz_nstep]
    and ax, dx
    inc ax
    mov cx, ax
.wa:
    cmp byte [di + WA_ACT], 0
    je .wb
    mov al, [di + WA_ENT]
    xor ah, ah
    sub ax, 2
    sub ax, [bz_nstep]
    and ax, dx
    inc ax
    cmp ax, cx
    jae .wb
    mov cx, ax
.wb:
    mov ax, cx
    add ax, [bz_nstep]
.w:
    call wa_setwk
    retf

; POSE: BX = the element -> AL its ripple's phase
wa_pose:
    call wa_slot
    call wa_rec
    mov al, [bz_nstep]
    test byte [es:si + WA_RIP], WR_ALWAYS
    jnz .ph
    inc bx
    cmp bl, [di + WA_ACT]
    mov al, 0
    jne .x
    mov al, [bz_nstep]
    sub al, [di + WA_ENT]
.ph:
%rep BZ_WA_RSH
    shr al, 1
%endrep
    and al, 1
.x:
    retf

    BZ_FWALK wa_walk
    BZ_FSETWK wa_setwk
    BZ_FREC wa_lrec, bx
    BZ_FREC wa_recp, bp

; SPEC.md 137.35.10: a water cell's GUARDED arches (ES:SI its record, AL its
; column in the window, 0 - 2, BX its cell's offset in bz_nbr): each one's exit
; in the window gets its kind nibble.  Out of wa_cell's loop, which a body this
; long would push past every short jump.  -> AH the kind.  Preserves all else.
wa_guard:
    mov ah, BZ_WA_KFLOOR        ; SPEC.md 137.35.10: each GUARDED arch's exit
    cmp bl, BZN_C               ; in the window - a WALL with this cell the
    jne .k                      ; centre and the ball not steel (the rail
    cmp byte [bz_mat], BZ_MAT_STEEL ; along the face's top: a ball on the
    je .k                       ; water stays on it), else the FLOOR it is
    inc ah                      ; in the grid (bz_win9i keeps window cells:
.k:                             ; written both ways, it is idempotent)
    test byte [es:si + WA_RIP], WR_GUARDX
    jz .gy
    cmp al, 2                   ; (+x: one column on, in the window)
    jae .gy
    and byte [bz_nbr + bx + 4 + 2], 0f0h
    or [bz_nbr + bx + 4 + 2], ah
.gy:
    test byte [es:si + WA_RIP], WR_GUARDY
    jz .x
    cmp bl, 24                  ; (+y: one row on, in the window)
    jae .x
    and byte [bz_nbr + bx + 12 + 2], 0f0h
    or [bz_nbr + bx + 12 + 2], ah
.x:
    ret

; BX = an element -> ES:SI its record.  Preserves all else.
wa_rec:
    push cx
    mov es, [bz_cseg]
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    pop cx
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "wa_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
wa_slot:
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
 %error "the window's centre is its fifth cell (BZN_C 16): wa_cell's compare"
%endif
%if BZ_WA_KWALL != BZ_WA_KFLOOR + 1
 %error "wa_cell walls a guarded arch's exit with an inc: KIND_WALL is KIND_FLOOR + 1"
%endif
%if $ - $$ > BZ_FAMP_WATER * 16
 %error "the water part passes its FAMILIES paras ceiling: raise it there"
%endif
