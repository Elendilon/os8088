; =============================================================================
; apps/bonanza/fam/rotor.asm - BONANZA's ROTOR FAMILY (SPEC.md 137.25.20, story
; 9.8): the WINDMILL's doorway (SPEC.md 137.12.6.2) out of the resident image -
; whether the ball's circle is low enough to touch it, and the gate at the
; step's n - behind the PROP hook (bit 6), DOOR, which the engine asks through
; bz_fone with DL = BZ_FK_WINDMILL (fam/bzdoor.inc).  The capture an open
; doorway makes, and the transit after it, are the TUBE family's (a windmill is
; a tube with a door): a course with a windmill names `tube` too.  The rotor's
; LANES stay the package's (lane machinery).  Home RESIDENT (137.25.6.9).
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"         ; the course tables' equates (BZ_FK0, BZ_FID_*, ...)
%include "bzlink.inc"           ; the package's constants and bss (pxlink)

    db 'BF'
    db BZ_FID_ROTOR
    db BZ_FAMV_ROTOR
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_PROP
    db 1, BZ_FK_WINDMILL         ; its KEY
    db 0
    dw 0, 0, 0, 0, 0, 0         ; hooks 0 - 5: none
    dw ro_prop                  ; hook 6, PROP: +24 (SPEC.md 137.25.20.2)
%if $ - $$ != BZF_HDR + 2
 %error "a part with the PROP hook has a 26-byte header (SPEC.md 137.25.20.2)"
%endif

; PROP, DOOR (the only question a windmill is asked): BX = the point (BL u,
; BH v), the windmill [bz_pdi] -> AL 0 not touching, 1 CLOSED with AH = eG,
; 2 OPEN
ro_prop:
    mov es, [bz_cseg]
    mov dx, bx
    call bz_ztouchp
    mov al, 0
    jnc .out
    call bz_gate
    mov al, 2
    jc .out
    mov ah, bl
    dec ax
.out:
    retf

; bz_gate - the doorway's windmill ([bz_pdi]) at the step's n (137.12.6.2):
; phase = (n + seed) AND (P - 1), OPEN while phase < c0 or phase >= c1.  CF = 1
; open; else CF = 0 and BL = its gate's restitution eG (record +19).
; Clobbers AX, BX, SI.
bz_gate:
    mov bl, [bz_pdi]
    xor bh, bh
    call bz_lrecsi
    mov ax, [bz_nstep]
    add ax, [es:si + BZP_SEED]
    and al, [es:si + BZP_MASK]
    cmp al, [es:si + BZP_TC0]
    jb .open
    cmp al, [es:si + BZP_TC1]
    jae .open
    mov bl, [es:si + BZP_TEG]
    clc
    ret
.open:
    stc
    ret


%define FC_LRECSI
%define FC_H4
%include "fam/bzfcopy.inc"
%include "fam/bzztouch.inc"

; the part's RAM form against its row's ceiling in bbcourse.FAMILIES (paras)
%if $ - $$ > BZ_FAMP_ROTOR * 16
 %error "the rotor part passes its FAMILIES paras ceiling: raise it there"
%endif
