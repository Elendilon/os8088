; =============================================================================
; apps/bonanza/bzfam.inc - BONANZA's FAMILIES (SPEC.md 128.25.6, 128.25.7): the
; engine's half of a mechanic that is a code part.  A course names up to three
; families (its FAMILY LIST, BZC2 +45 NFAM / +46 FAMOFF); bz_ffetch (bonanza.asm)
; fetched each one's part, checked its stamp and filled a SLOT RECORD here; the
; hook SITES (bzphys.inc, bzwheel.inc) test bz_fhk and call the two
; dispatchers below, which far-call the part's entries.  A course with no
; family has bz_fhk = 0, bz_fnf = 0, and reaches none of this code.
;
; THE CONTRACT A HOOK SEES (SPEC.md 128.25.6.3): entered by `call far` with
; DS = ES = the package, SS the task's, CLD; AL = its slot (0 - 2), AH = the
; hook's argument, BX = the element's prop index where there is one; `retf`,
; POSE answering AL.  Its slot's bytes are bz_fsl + BZF_SLOT AL.  It may
; clobber AX, BX, CX, DX, SI, DI, BP and ES (the dispatchers keep them for the
; site, POSE's AX excepted) and keeps DS, SS and SP; no OS call; 32 bytes of
; stack at most.
; =============================================================================

BZF_REC     equ 6               ; a slot record (bz_frec): +0 the part's DATA segment,
BZF_RDSEG   equ 0               ; +2 its CODE segment (both bz_ffetch's: op_seg,
BZF_RCSEG   equ 2               ; op_cseg), +4 the course's ID and FAMV for it
BZF_RIDV    equ 4               ; (the row is BZ_P_FAM + ID - 1)
BZ_HK_RESET equ 0               ; the hooks' bit NUMBERS (the dispatchers' AL;
BZ_HK_ENTER equ 1               ; the masks are bzcourse.inc's BZ_FH_*); hook b's
BZ_HK_CONT  equ 2               ; entry is the part's word at 12 + 2b
BZ_HK_STEP  equ 3
BZ_HK_POSE  equ 4
BZ_HK_CELL  equ 5
%if BZF_SLOT != 8 || BZ_FH_RESET != 1 << BZ_HK_RESET || BZ_FH_ENTER != 1 << BZ_HK_ENTER || BZ_FH_CONTACT != 1 << BZ_HK_CONT || BZ_FH_STEP != 1 << BZ_HK_STEP || BZ_FH_POSE != 1 << BZ_HK_POSE || BZ_FH_CELL != 1 << BZ_HK_CELL || BZF_HDR != 12 + 2 * 6
 %error "bzfam.inc's shifts and the hooks' numbering are the tool's (bbcourse.FSLOT, H_*, FAM_HDR)"
%endif

%macro BZ_FAM_VARS 0
; per LAUNCH (bz_ffetch's, bz_cdrop's), never zeroed by bz_pinit
VAR bz_fhk,1                    ; the ACTIVE HOOKS: every fetched part's mask, ORed
VAR bz_fnf,1                    ; ...the families fetched, 0 - 3 (the slots; one word
                                ; with bz_fhk)
VAR bz_ffp,4                    ; the far pointer a dispatch calls through
VAR bz_frec,BZ_FAMMAX * BZF_REC ; the slot records
%endmacro

; -----------------------------------------------------------------------------
; bz_fall - hook AL (its bit NUMBER) of EVERY family of the course that has an
; entry for it, in slot order; bz_fone - of the one family whose run of kinds
; (the part's +9 count, +10 first) holds kind DL.  AH the hook's argument, BX
; the element, both passed through.  -> AX as the last hook called left it
; (POSE's AL the pose), 0 when none was called.  Preserves all but AX.
; -----------------------------------------------------------------------------
bz_fall:
    push dx
    xor dx, dx                  ; DL 0: no kind filter (a kind is 16 - 255)
    jmp short bz_fh0
bz_fone:
    push dx
bz_fh0:
    push bx
    push cx
    push si
    push di
    push bp
    push es
    mov cx, ax                  ; CL the hook, CH its argument
    xor bp, bp                  ; (the answer: none yet)
    xor dh, dh                  ; DH the slot
    mov si, bz_frec
.s:
    cmp dh, [bz_fnf]
    jae .done
    mov es, [si + BZF_RDSEG]    ; (the part's head, read through its data
    or dl, dl                   ; segment)
    jz .call
    mov al, dl                  ; kind - first < count: its family's
    sub al, [es:10]
    cmp al, [es:9]
    jae .next
.call:
    mov al, cl
    cbw
    shl ax, 1
    xchg ax, di
    mov di, [es:di + 12]        ; the entry (0: none)
    or di, di
    jz .next
    mov [bz_ffp], di
    mov ax, [si + BZF_RCSEG]
    mov [bz_ffp + 2], ax
    push cx
    push dx
    push si
    mov al, dh                  ; AL the slot, AH the argument
    mov ah, ch
    push bx
    push ds                     ; (the package keeps the direction flag clear:
    pop es                      ; bz_pinit's rep stosw)
    call far [bz_ffp]
    pop bx
    pop si
    pop dx
    pop cx
    xchg ax, bp
.next:
    add si, BZF_REC
    inc dh
    jmp short .s
.done:
    xchg ax, bp
    pop es
    pop bp
    pop di
    pop si
    pop cx
    pop bx
    pop dx
    ret

; -----------------------------------------------------------------------------
; bz_frst - a RESPAWN's families (SPEC.md 128.25.6.3, 128.25.7.2), from bz_step's
; .resp before the place: the RESPAWN class cleared - bz_fst AND NOT the
; course's RESPAWN MASK, its NFST bytes after the (ID, FAMV) pairs - then RESET
; with AH = 1 (each family marks the lanes whose pose that moved).  DS = ours.
; Preserves every register.
; -----------------------------------------------------------------------------
bz_frst:
    push ax
    push cx
    push si
    push di
    push ds
    push es
    push ds
    pop es
    mov di, bz_fst              ; ES:DI ours, DS:SI the course's list
    mov ds, [bz_cseg]
    mov si, [BZC_FAMOFF]
    mov al, [BZC_NFAM]
    cbw
    shl ax, 1
    add si, ax
    lodsb                       ; NFST, then the mask
    cbw
    xchg ax, cx
    jcxz .r
.c:
    lodsb
    not al
    and al, [es:di]
    stosb
    loop .c
.r:
    pop es
    pop ds
    mov ax, 0100h | BZ_HK_RESET ; AH = 1: the RESPAWN class (a family with no
    call bz_fall                ; RESET entry is not called)
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; bz_ffetch - the course's FAMILY PARTS (SPEC.md 128.25.6.2), right after
; bz_crshdr in bz_cload: for each (ID, FAMV) of its family list (BZC2 +45
; NFAM, +46 FAMOFF), part BZ_P_FAM + ID - 1 fetched and its head checked -
; 'BF', the ID and FAMV the course names, and the image and bss sizes it was
; LINKED against, ours (DS:8, DS:10) - its slot record written (its DATA and
; CODE segments: op_seg, op_cseg, on kern_mega the code selector the far call
; needs) and its mask ORed into bz_fhk.  A part already here is not read
; again, so a second call after anything that may MOVE a part (the arena's
; batch, SPEC.md 128.25.4) re-takes every segment and fetches nothing: the
; segments are never held across a fetch.  A course with no family leaves
; bz_fhk and bz_fnf 0.  CF = 1 a fetch was refused (op_fetch toasted why) or
; a head was not this build's (toasted here, never called): what was fetched
; is bz_cdrop's to give back.  DS = ours.  Preserves ES; clobbers AX, BX, CX,
; DX, SI, DI.
; -----------------------------------------------------------------------------
bz_ffetch:
    push es
    mov word [bz_fhk], 0        ; (and bz_fnf)
    mov si, bz_frec
.f:
    mov es, [bz_cseg]
    mov al, [bz_fnf]
    cmp al, [es:BZC_NFAM]
    jae .out                    ; (CF = 0)
    cbw
    shl ax, 1
    add ax, [es:BZC_FAMOFF]
    xchg ax, bx
    mov ax, [es:bx]             ; AL the ID, AH its FAMV
    mov [si + BZF_RIDV], ax
    add al, BZ_P_FAM - 1
    push ax
    push si
    call op_fetch               ; (it clobbers AX - DI and ES)
    pop si
    pop ax
    jc .out
    call op_cseg
    mov [si + BZF_RCSEG], ax
    mov al, [si + BZF_RIDV]
    add al, BZ_P_FAM - 1
    call op_seg
    mov [si + BZF_RDSEG], ax
    mov es, ax
    cmp word [es:0], 'BF'
    jne .bad
    mov ax, [es:2]              ; the ID and FAMV
    cmp ax, [si + BZF_RIDV]
    jne .bad
    push si
    mov si, 8                   ; our image and bss sizes (OS88_HEADER) against
    mov di, 4                   ; the part's +4 and +6
    cmpsw
    jne .bads
    cmpsw
    pop si
    jne .bad
    mov al, [es:8]              ; its hooks
    or [bz_fhk], al
    inc byte [bz_fnf]
    add si, BZF_REC
    jmp short .f
.bads:
    pop si
.bad:
    mov si, bz_t_shell          ; ('Bonanza: bad part', the shell part's)
    call bz_toast
    stc
.out:
    pop es
    ret
