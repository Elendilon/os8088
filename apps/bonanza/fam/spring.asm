; =============================================================================
; apps/bonanza/fam/spring.asm - BONANZA's SPRING FAMILY (SPEC.md 130.25.20,
; story 9.8): the SPRING's rule (SPEC.md 130.14.4.6) out of bz_prule, behind
; the CONTACT hook (bz_prule's family dispatch: kind 24).  The slot SPEC.md
; 130.25.10 called POST: the bumper's post stays resident, a clock's collision
; (130.25.10).  Home RESIDENT (130.25.6.9).
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"         ; the course tables' equates (BZ_FK0, BZ_FID_*, ...)
%include "bzlink.inc"           ; the package's constants and bss (pxlink)

    db 'BF'
    db BZ_FID_SPRING
    db BZ_FAMV_SPRING
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_CONTACT
    db 1, BZ_FK_SPRING           ; its KEY
    db 0
    dw 0, 0, sp_contact, 0, 0, 0
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 130.25.6.2)"
%endif

; CONTACT: BX the spring (the centre's owner), after step 6.  bz_prule's
; .spring as it was, with BX - the floor's h4 under the centre, which the hook
; is not handed - found again: a spring's cell is a FLAT FLOOR (the tool's and
; the reader's rule, 130.14.4.1), so step 6 found 16 z0 there
sp_contact:
    mov es, [bz_cseg]
    call bz_lrecsi              ; SI = its record
    mov al, [bz_nbr + BZN_C]
    cbw
    mov cl, 4
    shl ax, cl
    xchg ax, bx                 ; BX = the h4
.spring:                        ; A SPRING (130.14.4.6), never under a
    cmp byte [bz_mst], BZ_ST_SHAT ; shattering ball
    je .out
    mov ax, [bz_nland]          ; this step's CONTACT (a landing, a bounce, a
    cmp ax, [bz_fnl]            ; Hop at the contact, a stun): gvz =
    je .sgr                     ; min(VZMAX, max(SPRING, the gvz it left, 0
    xor ax, ax                  ; when it stopped)), airborne, ztop = z, z not
    cmp [bz_air], al            ; moved - never the SUM (O13)
    je .s0
    mov ax, [bz_gvz]
.s0:
    cmp ax, [es:si + BZP_SGVZ]
    jge .s1
    mov ax, [es:si + BZP_SGVZ]
.s1:
    cmp ax, BZ_VZMAX
    jle .s2
    mov ax, BZ_VZMAX
.s2:
    mov [bz_gvz], ax
    mov byte [bz_air], 1
    mov ax, [bz_gz + 1]
    mov [bz_ztop], ax
    call bz_atok                ; round 3b: a launch out of the air
    jmp short .sl
.sgr:                           ; a ball that BEGAN the step grounded on it:
    cmp byte [bz_fair], 0       ; z its floor (a Hop this step does not add),
    jne .out                    ; gvz = SPRING, the ground Hop's take-off
    mov al, [bz_nbr + BZN_C + 2]
    and al, 0fh
    cmp al, BZ_KFLOOR
    je .sg1
    cmp al, BZ_KGOAL
    jne .out
.sg1:
    mov ax, bx
    push bx
    call bz_setz
    pop bx
    mov ax, [es:si + BZP_SGVZ]
    mov [bz_gvz], ax
    call bz_toff                ; (round 3b, 130.17.17: the launch TAKES the
.sl:                            ; token, bz_toff's; a contact's, bz_atok's)
    mov byte [bz_bgr], 0        ; wave 6b: a spring closes the grace
    inc word [bz_nspr]
.launched:                      ; the shadow's floor for the now airborne ball
    mov byte [bz_ghv], 1        ; (its cell solid: BX the h4)
    mov [bz_gh], bx
.out:
    retf

%define FC_LRECSI
%define FC_SETZ
%define FC_TOFF
%define FC_ATOK
%include "fam/bzfcopy.inc"

; the part's RAM form against its row's ceiling in bbcourse.FAMILIES (paras)
%if $ - $$ > BZ_FAMP_SPRING * 16
 %error "the spring part passes its FAMILIES paras ceiling: raise it there"
%endif
