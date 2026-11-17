; =============================================================================
; apps/bonanza/fam/spike.asm - BONANZA's SPIKE FAMILY (SPEC.md 128.38, the
; owner's design P5 and P8), held equal to bbcourse.SpikeFamily at every step.
;
; Three kinds, each a FLAT FLOOR cell of the grid (OBS, never SAFE) rewritten
; in the 9-cell window PER BALL by CELL, as WATER's are (SPEC.md 128.36):
;   SPIKES     the floor's base B in the grid; record +18 LOW (B less a half
;              unit), +19 TIP (B plus a half unit).  Steel's window holds TIP
;              (pushed up onto the tips, a climb, and it rolls on); every other
;              ball's LOW - so it drops onto them and LANDS - and, with the
;              window's CENTRE a spike cell, bz_mrec's HARD, HSTEPS and HTHR
;              are SHATTER, BZ_SHA_STEPS and 0: any landing there is the hard
;              landing's shatter (glass's pieces, rubber's POP: the ball part's
;              shatter entries), and the respawn as today.  The values replaced
;              are kept once, on the way in, and put back on the way out.
;   POPSPIKES  the same on a TIMER: +20 ON, +21 the period's MASK, +22 SEED; UP
;              while ((n + seed) AND mask) < on, n bz_nstep's low byte.  Up:
;              as SPIKES.  Down: B for every ball (an ordinary floor).  Its lane
;              is the spikes, pose 1 up.
;   MEMBRANE   a crystal film, FLOOR for glass alone: +18 its floor's z0; every
;              other ball's window holds a NEAR VOID there (z0 less 3 units,
;              kind and surface 0, its flags kept: a broken crack's), so it falls
;              through.
; Hooks: RESET (the course's popspikes counted, so STEP walks only for them),
; CELL (above; idempotent, written from the record), STEP (a changed material
; asks for the refill, bz_fref; a popspike whose pose the count about to be
; made flips is MARKED, bz_fmark, and refills the window when it is in it),
; POSE (a popspike's: 1 up).  The slot (bz_fsl + BZF_SLOT AL): +0 the material
; STEP last saw, +1 IN (the centre a killing spike at the last refill), +2 the
; HARD and HSTEPS replaced, +4 the HTHR replaced, +6 the popspikes.
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

SP_IN       equ 1               ; the slot's bytes
SP_HARD     equ 2
SP_HTHR     equ 4
SP_NPOP     equ 6
SP_LOW      equ 18              ; the record: LOW, TIP (signed half units),
SP_TIP      equ 19              ; a popspike's ON, MASK, SEED
SP_ON       equ 20
SP_MASK     equ 21
SP_SEED     equ 22
SP_MZ       equ 18              ; a membrane's: its floor's z0
%if BZ_FK_POPSPIKES != BZ_FK_SPIKES + 1 || BZ_FK_MEMBRANE != BZ_FK_SPIKES + 2
 %error "the spike family's kinds are consecutive: spikes, popspikes, membrane"
%endif
%if BZM_HSTEPS != BZM_HARD + 1 || BZ_SHA_STEPS > 255
 %error "sp_cell writes HARD and HSTEPS as one word"
%endif

    db 'BF'
    db BZ_FID_SPIKE
    db BZ_FAMV_SPIKE
    dw BZL_IMAGE, BZL_BSS
    db BZ_FH_RESET | BZ_FH_STEP | BZ_FH_POSE | BZ_FH_CELL
    db 3, BZ_FK_SPIKES          ; three kinds: spikes, popspikes, membrane
    db 0
    dw sp_reset, 0, 0, sp_step, sp_pose, sp_cell
%if $ - $$ != BZF_HDR
 %error "the family part's header is BZF_HDR bytes (SPEC.md 128.25.6.2)"
%endif

; RESET: the course's popspikes counted
sp_reset:
    call sp_slot
    xor dx, dx
    call sp_walk
.l:
    jcxz .x
    cmp byte [es:si], BZ_FK_POPSPIKES
    jne .n
    inc dx
.n:
    add si, 32
    dec cx
    jmp short .l
.x:
    mov [di + SP_NPOP], dl
    retf

; CELL: the window's cells of the family for this ball, then the centre's rule
sp_cell:
    call sp_slot                ; DI = the slot
    call sp_walk                ; ES:SI the records, CX their count
    xor dx, dx                  ; DL = the centre kills, DH = the kind less SPIKES
    or cx, cx
    jnz .r
    jmp .done
.r:
    mov dh, [es:si]
    sub dh, BZ_FK_SPIKES
    cmp dh, 2
    ja .n
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
    cmp dh, 2
    je .mem
    mov al, [es:si + SP_TIP]    ; steel's: the tips
    cmp dh, 1
    jne .up
    mov ah, [bz_nstep]          ; a popspike DOWN: its base, every ball's
    add ah, [es:si + SP_SEED]
    and ah, [es:si + SP_MASK]
    cmp ah, [es:si + SP_ON]
    jb .up
    dec ax
    jmp short .w
.up:
    cmp byte [bz_mat], BZ_MAT_STEEL
    je .w
    mov al, [es:si + SP_LOW]    ; every other ball's: LOW, and the centre kills
    cmp bl, BZN_C
    jne .w
    mov dl, 1
.w:
    mov [bz_nbr + bx], al
    jmp short .n
.mem:
    cmp byte [bz_mat], BZ_MAT_GLASS
    je .n
    mov al, [es:si + SP_MZ]     ; not glass: a NEAR VOID, its kill 3 units down
    sub al, 6
    mov [bz_nbr + bx], al
    mov byte [bz_nbr + bx + 2], 0
.n:
    add si, 32
    dec cx
    jz .done
    jmp .r
.done:
    or dl, dl
    jz .out
    cmp byte [di + SP_IN], 0    ; THE CENTRE KILLS: on the way in the values
    jne .in                     ; replaced kept
    mov byte [di + SP_IN], 1
    mov ax, [bz_mrec + BZM_HARD]
    mov [di + SP_HARD], ax
    mov ax, [bz_mrec + BZM_HTHR]
    mov [di + SP_HTHR], ax
.in:
    mov word [bz_mrec + BZM_HARD], BZ_HARD_SHATTER | BZ_SHA_STEPS << 8
    mov word [bz_mrec + BZM_HTHR], 0
    retf
.out:                           ; not: on the way out, put back
    cmp byte [di + SP_IN], 0
    je .x
    mov byte [di + SP_IN], 0
    mov ax, [di + SP_HARD]
    mov [bz_mrec + BZM_HARD], ax
    mov ax, [di + SP_HTHR]
    mov [bz_mrec + BZM_HTHR], ax
.x:
    retf

; STEP: a changed material's refill; each popspike the count about to be made
; flips MARKED, and the window refilled when it is in it
sp_step:
    call sp_slot
    mov al, [bz_mat]
    cmp al, [di]
    je .p
    mov [di], al
    mov byte [bz_fref], 1
.p:
    cmp byte [di + SP_NPOP], 0
    je .x
    call sp_walk
    xor bx, bx
.l:
    jcxz .x
    cmp byte [es:si], BZ_FK_POPSPIKES
    jne .nx
    mov al, [bz_nstep]          ; up on n against up on n + 1
    add al, [es:si + SP_SEED]
    mov ah, al
    inc ah
    mov dl, [es:si + SP_MASK]
    and al, dl
    and ah, dl
    cmp al, [es:si + SP_ON]
    sbb dl, dl
    cmp ah, [es:si + SP_ON]
    sbb dh, dh
    cmp dl, dh
    je .nx
    call far [bz_fmkp]          ; its lane MARKED
    mov al, [es:si + 2]         ; ...and in the window: the refill
    sub al, [bz_nwin]
    inc al
    cmp al, 2
    ja .nx
    mov al, [es:si + 3]
    sub al, [bz_nwin + 1]
    inc al
    cmp al, 2
    ja .nx
    mov byte [bz_fref], 1
.nx:
    add si, 32
    inc bx
    dec cx
    jmp short .l
.x:
    retf

; POSE: BX = a popspike -> AL 1 up, 0 down
sp_pose:
    push cx
    mov es, [bz_cseg]
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    pop cx
    mov al, [bz_nstep]
    add al, [es:si + SP_SEED]
    and al, [es:si + SP_MASK]
    cmp al, [es:si + SP_ON]
    sbb al, al
    neg al
    retf

; -> ES:SI the course's first record, CX the records.  Preserves all else.
sp_walk:
    mov es, [bz_cseg]
    mov si, [bz_poff]
    mov cl, [bz_nprop]
    xor ch, ch
    ret

; AL = the slot -> DI = its bytes, bz_fsl + BZF_SLOT AL.  Preserves all else.
%if BZF_SLOT != 8
 %error "sp_slot's three shifts are BZF_SLOT = 8 (bbcourse.FSLOT)"
%endif
sp_slot:
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
 %error "the window's centre is its fifth cell (BZN_C 16): sp_cell's compare"
%endif
%if $ - $$ > BZ_FAMP_SPIKE * 16
 %error "the spike part passes its FAMILIES paras ceiling: raise it there"
%endif
