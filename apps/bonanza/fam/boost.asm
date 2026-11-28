; =============================================================================
; apps/bonanza/fam/boost.asm - BONANZA's BOOST PADS (SPEC.md 137.40): a plate of
; CHEVRONS on a flat floor that pushes a GROUNDED ball whose centre is on it
; along its FACE (+x, -x, +y, -y) by its STRENGTH S WEIGHTED BY THE BALL (the
; owner's defaults: glass S + (S >> 2), rubber S, steel S - (S >> 2)), or S on
; a `flat` pad (record +18 bit 2, BZ_BP_FFLAT): CONTACT adds the push to
; bz_gvx or bz_gvy, and the next step's force block clamps
; what it left to the caps (VMAXG + bz_vup), as WIND's push relies on.  Not
; rubber's BOOST (SPEC.md 137.16.4: the Hop's rebound turned into height, the
; token bz_btok and bz_nboost) - that is a ball's, in the air; this is a
; floor's, along the ground, for every ball.
;
; Its lane is the chevrons' FLASH, ONE pad lit at a time.  The SLOT (bz_fsl +
; BZF_SLOT AL): +0 the lit pad (its element + 1, 0 none), +1 its steps left.
; CONTACT on the lit pad (or with none lit) lights it for BZ_BP_FLASH steps;
; on another pad while one is lit it puts that one OUT, and this one lights on
; its next step's contact - so a chain of pads changes one pose a step.  STEP
; counts the lit pad down and puts it out at 0.  POSE: 1 for the lit pad.  No
; RESET: a play's start zeroes the slot, and a respawn lets a flash run out.
; bbcourse.BoostFamily is the model, step for step.
;
; A pad's record (SPEC.md 137.40.3): +18 the face (0 +x, 1 -x, 2 +y, 3 -y:
; bit 1 the y axis, bit 0 the minus sign) OR BZ_BP_FFLAT, +19 S, +20 - +31
; zero.
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
%include "fam/bzfwalk.inc"

BP_DIR      equ 18              ; the record's fields (SPEC.md 137.40.3)
BP_STR      equ 19

    db 'BF'
    db BZ_FID_BOOST             ; (bzcourse.inc's: the ID is FAMILIES' alone)
    db BZ_FAMV_BOOST
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_CONTACT | BZ_FH_STEP | BZ_FH_POSE
    db 1, BZ_FK_BOOST           ; one kind, the pad
    db 0
    dw 0, 0, bp_contact, bp_step, bp_pose, 0
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 137.25.6.2)"
%endif
%if BZF_SLOT != 8
 %error "bp_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
%if BZ_MAT_STEEL != 1 || BZ_MAT_GLASS != 2
 %error "bp_contact's weighting reads the material as rubber 0, steel 1, glass 2"
%endif
%if BZ_BP_GSH != 2 || BZ_BP_SSH != 2 || BZ_BP_FFLAT != 4
 %error "bp_contact's weighting is S >> 2 added for glass and taken for steel; flat is +18 bit 2"
%endif
%if bz_gvy != bz_gvx + 2
 %error "bp_contact indexes bz_gvx by the axis: bz_gvy must follow it"
%endif

; CONTACT (AH the kind): a grounded ball, not shattering, on pad BX - the
; flash (lit, kept lit, or another put out), then the push S along the face
bp_contact:
    cmp byte [bz_air], 0
    jne .out
    cmp byte [bz_mst], BZ_ST_SHAT
    je .out
    call bp_slot
    xor ax, ax                  ; (its STEP from now: 137.25.6.11)
    call bp_setwk
    inc bx                      ; BX = the pad + 1 (at most 255: PROP_ALL)
    mov al, [di]
    cmp al, bl
    je .keep
    or al, al
    jz .light
    push bx                     ; ANOTHER pad lit: put it out (its lane
    dec ax                      ; MARKED); this one lights on its next step
    mov bl, al                  ; (BH 0: bp_slot's)
    mov [di], bh                ; (its count is left: +0 0 is out)
    call far [bz_fmkp]          ; (bz_fmark: the walk made; BX the element)
    pop bx
    jmp short .push
.light:
    dec bx
    call far [bz_fmkp]          ; this pad LIT: its lane MARKED
    inc bx
.keep:
    mov [di], bl
    mov byte [di + 1], BZ_BP_FLASH
.push:
    dec bx                      ; SI = its record
    mov cl, 5
    shl bx, cl
    add bx, [bz_poff]
    mov es, [bz_cseg]
    mov al, [es:bx + BP_STR]    ; AL = S, WEIGHTED: glass S + S / 4, rubber S,
    mov bl, [es:bx + BP_DIR]    ; steel S - S / 4 - or S for every ball on a
    mov ah, al                  ; `flat` pad (S <= 127: glass's 158 is a byte)
    shr ah, 1                   ; AH = S >> 2 (BZ_BP_GSH = BZ_BP_SSH = 2)
    shr ah, 1
    test bl, BZ_BP_FFLAT
    jnz .w
    mov cl, [bz_mat]            ; (rubber 0, steel 1, glass 2)
    dec cl
    jl .w
    jnz .add
    neg ah                      ; (steel: S + -(S >> 2), a byte)
.add:
    add al, ah
.w:
    xor ah, ah
    shr bl, 1                   ; BL bit 0: 0 x, 1 y; CF the minus sign
    jnc .pos
    neg ax
.pos:
    and bx, 1                   ; (`flat`, now bit 1, and the address's BH gone)
    shl bx, 1
    add [bz_gvx + bx], ax       ; (bz_gvy follows bz_gvx)
.out:
    retf

; STEP: the lit pad's steps one less; at 0 it is put out, its lane MARKED
bp_step:
    call bp_slot
    xor ax, ax                  ; (a pad lit: every step, 137.25.6.11)
    call bp_setwk
    mov bl, [di]
    or bl, bl
    jnz .lit
    mov ax, [bz_nstep]          ; (idle: no STEP until something wakes it,
    add ax, 4000h               ; 137.25.6.11)
    call bp_setwk
    retf
.lit:
    dec byte [di + 1]
    jnz .out
    mov [di], bh                ; (BH 0: bp_slot's)
    dec bx
    call far [bz_fmkp]          ; (bz_fmark: the walk made; BX the element)
.out:
    retf

    BZ_FSETWK bp_setwk

; POSE: 1 for the lit pad, 0 for every other
bp_pose:
    call bp_slot
    inc bx
    cmp [di], bl
    mov al, 0
    jne .o
    inc ax
.o:
    retf

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL; BH = 0.  Clobbers AH.
bp_slot:
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    mov bh, ah
    ret

%if $ - $$ > BZ_FAMP_BOOST * 16
 %error "the boost part passes its FAMILIES paras ceiling: raise it there"
%endif
