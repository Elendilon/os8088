; =============================================================================
; apps/bonanza/fam/tube.asm - BONANZA's TUBE FAMILY (SPEC.md 130.25.20, story
; 9.8): the tube's rules (SPEC.md 130.12.6.1) out of the resident image - the
; drain at step 4, a capture (a windmill's open doorway's too: a windmill is a
; tube with a door) and step 1's transit - behind the PROP hook (bit 6), which
; the engine asks only through bz_fone with DL = BZ_FK_TUBE (fam/bzthunk.inc).
; Home RESIDENT (SPEC.md 130.25.6.9): fetched once at the package's start.
; The rules are fam/bztube.inc's and fam/bzztouch.inc's, ONE source; the
; helpers they call are fam/bzfcopy.inc's copies.  No slot, no state bit: the
; tube's state is the package's own (bz_tube, bz_tseg, bz_tcnt, bz_tsin).
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"         ; the course tables' equates (BZ_FK0, BZ_FID_*, ...)
%include "bzlink.inc"           ; the package's constants and bss (pxlink)

    db 'BF'
    db BZ_FID_TUBE
    db BZ_FAMV_TUBE             ; (bz_ffetch checks it against the course's list)
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_PROP
    db 1, BZ_FK_TUBE            ; one kind: its KEY
    db 0
    dw 0, 0, 0, 0, 0, 0         ; hooks 0 - 5: none
    dw tu_prop                  ; hook 6, PROP: +24 (SPEC.md 130.25.20.2)
%if $ - $$ != BZF_HDR + 2
 %error "a part with the PROP hook has a 26-byte header (SPEC.md 130.25.20.2)"
%endif

; PROP: AH the question, BX the element -> AL
tu_prop:
    mov es, [bz_cseg]
    cmp ah, BZ_PQ_CAPTURE
    je .cap
    ja .tr
    cmp byte [bz_air], 0        ; DRAIN: grounded, or airborne with z at most
    je .dc                      ; IN's floor + BZ_CLIMB at the centre's point
    push bx
    call bz_ztouch
    pop bx
    mov al, 0
    jnc .out
.dc:
    call bz_capture             ; (BL the tube)
    mov al, 1                   ; captured: the step ends
.out:
    retf
.cap:
    call bz_capture             ; CAPTURE: BL the windmill
    retf
.tr:
    call bz_transit             ; TRANSIT: AL 1 when it EXITED (the engine
    retf                        ; refills the window round OUT)

%macro BZT_GOING 0              ; (fam/bztube.inc's two ends, the part's way)
    call bz_psync
    mov al, 0
    ret
%endmacro
%macro BZT_EXITED 0
    mov al, 1
    ret
%endmacro
%define FC_LRECSI
%define FC_H4
%define FC_SETZ
%define FC_PSYNC
%define FC_VMAX
%include "fam/bzfcopy.inc"
%include "fam/bzztouch.inc"
%include "fam/bztube.inc"

; the part's RAM form against its row's ceiling in bbcourse.FAMILIES (paras)
%if $ - $$ > BZ_FAMP_TUBE * 16
 %error "the tube part passes its FAMILIES paras ceiling: raise it there"
%endif
