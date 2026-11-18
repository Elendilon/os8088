; =============================================================================
; apps/bonanza/fam/spike.asm - BONANZA's SPIKE FAMILY (SPEC.md 130.38, the
; owner's design P5 and P8), held equal to bbcourse.SpikeFamily at every step.
;
; Three kinds, each a FLAT FLOOR cell of the grid (OBS, never SAFE) rewritten
; in the 9-cell window PER BALL by CELL, as WATER's are (SPEC.md 130.36):
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
;   MEMBRANE   a NET OF THREADS, FLOOR for glass alone (the lightest ball):
;              +18 its floor's z0; every other ball's window holds a NEAR VOID
;              there (z0 less 3 units, kind and surface 0, its flags kept: a
;              broken crack's), so it falls through - and while it is under
;              the net in a membrane cell that cell's lane is TORN, pose 1.
; Hooks: RESET (the course's popspikes counted, so STEP walks only for them),
; CELL (above; idempotent, written from the record), STEP (a changed material
; asks for the refill, bz_fref; a popspike whose pose the count about to be
; made flips is MARKED, bz_fmark, and refills the window when it is in it),
; STEP also finds the TORN membrane - the window's centre a membrane, the ball
; not glass and its whole-px z under the net's 4 z0 - and marks the lanes of the
; one it was and the one it is; POSE (a popspike's: 1 up; a membrane's: 1
; TORN).  The slot (bz_fsl + BZF_SLOT AL): +0 the material STEP last saw, +1 IN
; (the centre a killing spike at the last refill), +2 the HARD and HSTEPS
; replaced, +4 the HTHR replaced, +6 the popspikes and membranes (STEP's walk),
; +7 TORN, the torn membrane's element + 1 (0 none).
;
; A FAMILY PART (SPEC.md 130.25.6.2), linked against the package's bss as the
; probe is (bzlink.inc: no code label).  Every hook: `call far`, DS = ES = the
; package, AL = the slot, AH = the argument, BX = the element; `retf`.
; =============================================================================
cpu 8086
org 0
%include "os88api.inc"
%include "bzcourse.inc"
%include "bzlink.inc"
%include "fam/bzfwalk.inc"

SP_IN       equ 1               ; the slot's bytes
SP_HARD     equ 2
SP_HTHR     equ 4
SP_NWALK    equ 6
SP_TORN     equ 7
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
 %error "the family part's header is BZF_HDR bytes (SPEC.md 130.25.6.2)"
%endif

; RESET: the course's popspikes and membranes counted
sp_reset:
    call sp_slot
    xor dx, dx
    call sp_walk                ; (the family's own records: 130.25.6.10)
.l:
    jcxz .x
    call sp_rec
    mov al, [es:si]             ; (popspikes and membranes alone)
    sub al, BZ_FK_POPSPIKES
    cmp al, 1
    ja .n
    inc dx
.n:
    inc bx
    dec cx
    jmp short .l
.x:
    mov [di + SP_NWALK], dl
    retf

; CELL: the window's cells of the family for this ball, then the centre's rule
sp_cell:
    call sp_slot                ; DI = the slot
    call sp_walk                ; ES = the course, BP its list, CX its count
    mov bp, bx
    xor dx, dx                  ; DL = the centre kills, DH = the kind less SPIKES
    or cx, cx
    jnz .r
    jmp .done
.r:
    call sp_recp
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
    inc bp
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
; flips MARKED, and the window refilled when it is in it; the TORN membrane
; found (BP: its element + 1), and on a change both lanes MARKED
sp_step:
    call sp_slot
    mov al, [bz_mat]
    cmp al, [di]
    je .p
    mov [di], al
    mov byte [bz_fref], 1
.p:
    cmp byte [di + SP_NWALK], 0
    je .x
    call sp_walk                ; (CX > 0: NWALK counted them)
    xor bp, bp
.l:
    call sp_rec
    cmp byte [es:si], BZ_FK_MEMBRANE
    je .mem
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
    push bx
    mov bl, [bx]                ; (its element: the list's byte)
    xor bh, bh
    call far [bz_fmkp]          ; its lane MARKED
    pop bx
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
    inc bx
    loop .l
    jmp short .t
.mem:                           ; TORN: the window's centre, not glass, under
    cmp byte [bz_mat], BZ_MAT_GLASS
    je .nx
    mov ax, [es:si + 2]
    cmp ax, [bz_nwin]
    jne .nx
    mov al, [es:si + SP_MZ]     ; ...the net: z < 4 z0, signed
    cbw
    shl ax, 1
    shl ax, 1
    cmp [bz_gz + 1], ax
    jge .nx
    push bx
    mov bl, [bx]                ; (its element: the list's byte)
    xor bh, bh
    lea bp, [bx + 1]
    pop bx
    jmp short .nx
.t:
    mov ax, bp                  ; a change: the lanes of the one it was and
    xchg al, [di + SP_TORN]     ; the one it is MARKED
    cmp al, [di + SP_TORN]
    je .x
    call sp_tmark
    mov ax, bp
    call sp_tmark
.x:
    retf

; AL = a membrane's element + 1, or 0 -> its lane MARKED.  Preserves all but BX.
sp_tmark:
    or al, al
    jz .x
    dec ax
    mov bl, al
    xor bh, bh
    call far [bz_fmkp]
.x:
    ret

; POSE: BX = a popspike -> AL 1 up, 0 down; a membrane -> AL 1 TORN
sp_pose:
    push cx
    mov es, [bz_cseg]
    mov si, bx
    mov cl, 5
    shl si, cl
    add si, [bz_poff]
    pop cx
    cmp byte [es:si], BZ_FK_MEMBRANE
    jne .pop
    push di
    call sp_slot
    mov al, [di + SP_TORN]
    pop di
    dec ax
    sub al, bl                  ; (BH 0: an element's index is a byte)
    cmp al, 1                   ; AL 0 (TORN) -> 1, else 0
    mov al, 0
    adc al, 0
    retf
.pop:
    mov al, [bz_nstep]
    add al, [es:si + SP_SEED]
    and al, [es:si + SP_MASK]
    cmp al, [es:si + SP_ON]
    sbb al, al
    neg al
    retf

    BZ_FWALK sp_walk
    BZ_FREC sp_rec, bx
    BZ_FREC sp_recp, bp

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
