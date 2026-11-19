; =============================================================================
; apps/bonanza/fam/probe.asm - BONANZA's PROBE FAMILY (SPEC.md 130.25.15), the
; family the hook table and the per-play state are proved with (stories 9.1,
; 9.2): ID 1, one kind, `probe` (16), and NO PHYSICS - every hook the
; smallest thing that makes its call visible, so the guest is held equal to
; bbcourse.ProbeFamily through every hook and a course that names it replays
; exactly as one without it.
;
; A FAMILY PART (SPEC.md 130.25.6.2): a flat binary at org 0, a lazy OP_SEG
; row of BONANZA.O88, LINKED against the package's bss as the shell part is
; (build/bonanza-art/bzlink.inc names no code label, so nothing here can call
; the package).  Every hook is entered by `call far` with DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; it answers
; `retf`, and finds its slot's bytes at bz_fsl + BZF_SLOT AL (pr_slot).
; The slot: +0 RESETs, +1 ENTERs, +2 CONTACTs (a word), +4 STEPs (a word),
; +6 the last ENTER's AH.  The element's one state bit is TOUCHED.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"         ; the course tables' equates (BZ_FK0, BZP_FSB, ...)
%include "bzlink.inc"           ; the package's constants and bss (pxlink)
%include "fam/bzfwalk.inc"

PR_ID       equ BZ_FID_PROBE    ; (bzcourse.inc's: never a literal, SPEC.md 130.25.6.2)
PR_KIND     equ BZ_FK0

    db 'BF'
    db PR_ID
    db BZ_FAMV_PROBE            ; (bzcourse.inc's, bbcourse.famv: bz_ffetch
                                ; checks it against the course's list)
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_ENTER | BZ_FH_CONTACT | BZ_FH_STEP | BZ_FH_POSE | BZ_FH_CELL
    db 1, PR_KIND               ; one kind, from BZ_FK0
    db 0
    dw pr_reset, pr_enter, pr_contact, pr_step, pr_pose, pr_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 130.25.6.2)"
%endif

; RESET: counted (the class in AH: the engine cleared it), and every probe's
; lane MARKED for the walk (a respawn may have furled it)
pr_reset:
    call pr_slot
    inc byte [di]
    mov cl, [bz_nlane]
    xor ch, ch
    jcxz .out
    mov es, [bz_cseg]
    mov si, [bz_poff]
    xor bx, bx
.l:
    cmp byte [es:si], PR_KIND
    jne .n
    call far [bz_fmkp]          ; (its lane MARKED, the walk made: bz_fmark)
.n:
    add si, 32
    inc bx
    loop .l
.out:
    retf

; ENTER: counted, AH kept, TOUCHED set; when it was clear, the element's lane
; MARKED for the walk (its pose moved) and a refill asked for (its overlay)
pr_enter:
    call pr_slot
    inc byte [di + 1]
    mov [di + 6], ah
    call pr_bit                 ; SI = its bz_fst byte, AL its bit
    test [si], al
    jnz .out
    or [si], al
    call far [bz_fmkp]
    mov byte [bz_fref], 1
.out:
    retf

; CONTACT, STEP: counted
pr_contact:
    call pr_slot
    inc word [di + 2]
    retf
pr_step:
    call pr_slot
    inc word [di + 4]
    retf

    BZ_FWALK pr_walk
    BZ_FREC pr_recp, bp

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
pr_slot:
    push ax
    xor ah, ah
    mov di, ax
    shl di, 1
    shl di, 1
    shl di, 1
    add di, bz_fsl
    pop ax
    ret

; POSE: TOUCHED, 1 flying, 0 furled
pr_pose:
    call pr_bit
    and al, [si]
    jz .p
    mov al, 1
.p:
    retf

; CELL: every TOUCHED probe in the window has its cell's +3 bit 7 set in
; bz_nbr - the window, never the grid (SPEC.md 130.25.7.2)
pr_cell:
    call pr_slot                ; (its own records: SPEC.md 130.25.6.10)
    call pr_walk
    mov bp, bx                  ; BP the list, CX its count
    jcxz .x
.r:
    call pr_recp
    mov bl, [ds:bp]             ; BX = the element (pr_bit's)
    xor bh, bh
    cmp byte [es:si], PR_KIND
    jne .n
    mov al, [es:si + 2]         ; dx = wx - window's wx + 1, 0 - 2 (the
    sub al, [bz_nwin]           ; window first: a probe out of it costs no
    inc al                      ; pr_bit)
    cmp al, 2
    ja .n
    mov ah, [es:si + 3]
    sub ah, [bz_nwin + 1]
    inc ah
    cmp ah, 2
    ja .n
    mov dl, ah                  ; DI = bz_nbr + 4 (3 dy' + dx')
    add dl, ah
    add dl, ah
    add dl, al
    xor dh, dh
    shl dx, 1
    shl dx, 1
    mov di, dx
    push cx
    push si
    call pr_bit                 ; (preserves DI)
    test [si], al
    pop si
    pop cx
    jz .n
    or byte [bz_nbr + di + 3], 80h
.n:
    inc bp
    loop .r
.x:
    retf

; BX = an element -> SI = its TOUCHED bit's byte in bz_fst, AL the bit
; (record +16, FSB).  Clobbers CL.
pr_bit:
    push bx
    push es
    mov es, [bz_cseg]
    mov cl, 5
    shl bx, cl
    add bx, [bz_poff]
    mov bl, [es:bx + BZP_FSB]
    pop es
    xor bh, bh
    mov cl, bl
    and cl, 7
    shr bx, 1
    shr bx, 1
    shr bx, 1
    lea si, [bz_fst + bx]
    mov al, 1
    shl al, cl
    pop bx
    ret

; EVERY family row is OP_COMP (SPEC.md 130.25.6.2): one plain lazy row would
; assemble the parts standard's plain-row path, 86 resident bytes, so a part
; too small for LZB to shrink carries zeros until it does - the probe's 48
; (disk and arena bytes only, never the image's)
    times 48 db 0

; the part's RAM form against its row's ceiling in bbcourse.FAMILIES (paras):
; the ARENA reserve counts that ceiling, not these bytes (SPEC.md 130.25.4.2)
%if $ - $$ > BZ_FAMP_PROBE * 16
 %error "the probe's part passes its FAMILIES paras ceiling: raise it there"
%endif
