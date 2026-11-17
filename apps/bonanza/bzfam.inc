; =============================================================================
; apps/bonanza/bzfam.inc - BONANZA's FAMILIES (SPEC.md 128.25.6, 128.25.7): the
; engine's half of a mechanic that is a code part.  A course names up to three
; families (its FAMILY LIST, BZC2 +45 NFAM / +46 FAMOFF); bz_ffetch (bonanza.asm)
; fetched each one's part, checked its stamp and filled a SLOT RECORD here; the
; hook SITES (bzphys.inc, bzwheel.inc) test bz_fhk and call the two
; dispatchers below, which far-call the part's entries.  A course with no
; family has bz_fhk = 0, bz_fnf = 0, and reaches none of this code.  THE HOOK
; LISTS (SPEC.md 128.25.6.3, the owner's F6): bz_ffetch builds, per hook, the
; far entries of only the families that have it, so a dispatch walks those and
; nothing else.
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
BZF_RIDV    equ 4               ; (its row bz_ftab's: a fetch family's own, or the bundle's)
BZ_HK_RESET equ 0               ; the hooks' bit NUMBERS (the dispatchers' AL;
BZ_HK_ENTER equ 1               ; the masks are bzcourse.inc's BZ_FH_*); hook b's
BZ_HK_CONT  equ 2               ; entry is the part's word at 12 + 2b
BZ_HK_STEP  equ 3
BZ_HK_POSE  equ 4
BZ_HK_CELL  equ 5
BZ_HK_PROP  equ 6               ; story 9.8 (SPEC.md 128.25.20.2): through bz_fone
                                ; only, its entry at the part's +24
BZ_NHOOK    equ 7               ; the hooks: one LIST each (bz_fhl)
BZF_HE      equ 8               ; a list's ENTRY: +0 the hook's far entry (its
BZF_HESLOT  equ 4               ; offset, the part's code segment), +4 the slot,
BZF_HEKN    equ 5               ; +5 the family's kinds (the part's +9), +6 its
BZF_HEKF    equ 6               ; first kind (+10), +7 unused
BZF_HL      equ BZ_FAMMAX * BZF_HE ; a hook's list (bz_fhn its length)
BZ_PQ_DRAIN equ 0               ; ...its questions (AH): the TUBE family's step-4
BZ_PQ_CAPTURE equ 1             ; drain, a capture, step 1's transit; the ROTOR
BZ_PQ_TRANSIT equ 2             ; family's doorway at step 5
BZ_PQ_DOOR  equ 3
%if BZF_HL != 32 || BZF_HE != 8
 %error "the dispatch and bz_ffetch find a hook's list with a shift: BZF_HL 32 (BZ_FAMMAX 4)"
%endif
%if BZF_SLOT != 8 || BZ_FH_RESET != 1 << BZ_HK_RESET || BZ_FH_ENTER != 1 << BZ_HK_ENTER || BZ_FH_CONTACT != 1 << BZ_HK_CONT || BZ_FH_STEP != 1 << BZ_HK_STEP || BZ_FH_POSE != 1 << BZ_HK_POSE || BZ_FH_CELL != 1 << BZ_HK_CELL || BZ_FH_PROP != 1 << BZ_HK_PROP || BZF_HDR != 12 + 2 * 6
 %error "bzfam.inc's shifts and the hooks' numbering are the tool's (bbcourse.FSLOT, H_*, FAM_HDR)"
%endif

%macro BZ_FAM_VARS 0
; per LAUNCH (bz_ffetch's, bz_cdrop's), never zeroed by bz_pinit
VAR bz_fhk,1                    ; the ACTIVE HOOKS: every fetched part's mask, ORed
VAR bz_fnf,1                    ; ...the families fetched, 0 - 3 (the slots; one word
                                ; with bz_fhk)
VAR bz_fhn,2 * BZ_NHOOK         ; THE HOOK LISTS (bz_ffetch's): each hook's
VAR bz_fhl,BZ_NHOOK * BZF_HL    ; length, bytes (a word), and its list
VAR bz_fmkp,4                   ; bz_fmark's far pointer, which every dispatch writes:
                                ; a hook MARKS a lane by `call far [bz_fmkp]`
VAR bz_frec,BZ_FAMMAX * BZF_REC ; the slot records
%endmacro

; -----------------------------------------------------------------------------
; bz_fall - hook AL (its bit NUMBER) of EVERY family of the course that has an
; entry for it, in slot order; bz_fone - of the one family whose run of kinds
; (the part's +9 count, +10 first) holds kind DL.  AH the hook's argument, BX
; the element, both passed through.  -> AX as the last hook called left it
; (POSE's AL the pose), 0 when none was called.  Preserves all but AX.  Each
; walks the hook's LIST (bz_ffetch's): only the families that have the hook,
; each entry's far pointer called where it lies (SPEC.md 128.25.6.3).
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
    mov word [bz_fmkp], bz_fmark ; (the hooks' MARK, at the package's CS now:
    mov [bz_fmkp + 2], cs       ; a region can move between plays)
    xor bp, bp                  ; (the answer: none yet)
    mov dh, ah                  ; DH the argument
    xor ah, ah
    shl ax, 1
    xchg ax, si
    mov di, [bz_fhn + si]
    mov cl, 4
    shl si, cl
    add si, bz_fhl              ; SI = the hook's list, DI its end
    add di, si
.s:
    cmp si, di
    jae .done
    or dl, dl
    jz .call
    mov al, dl                  ; kind - first < count: its family's
    sub al, [si + BZF_HEKF]
    cmp al, [si + BZF_HEKN]
    jae .next
.call:
    push dx
    push si
    push di
    push bx
    mov al, [si + BZF_HESLOT]   ; AL the slot, AH the argument
    mov ah, dh
    push ds                     ; (the package keeps the direction flag clear:
    pop es                      ; bz_pinit's rep stosw)
    call far [si]
    pop bx
    pop di
    pop si
    pop dx
    xchg ax, bp
    or dl, dl                   ; (bz_fone: the one family called - the runs of
    jnz .done                   ; kinds are disjoint)
.next:
    add si, BZF_HE
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
; bz_fmark - THE HOOKS' MARK (SPEC.md 128.25.6.3): lane BX MARKED for the walk
; (bz_latt) and the next walk MADE (bz_lqt 0) - the quiet walk reads no mark,
; so a mark alone, with the camera still, was never walked: a crack broken by
; a landing fell the ball through an undrawn hole (the owner, 2026-11-16).  A
; family part reaches it by `call far [bz_fmkp]`, which every dispatch points
; here, BX the element (its lane).  A GROUP MEMBER (SPEC.md 128.32.5: its
; record's flag GRP, +8 - +15 its group lanes, 0FFh after the last) marks
; every lane it lists.  Preserves everything.
; -----------------------------------------------------------------------------
bz_fmark:
    mov byte [bz_lqt], 0
    push bx
    push cx
    push si
    push es
    mov es, [bz_cseg]           ; (by the record's flag, never by bz_nlane: a
    call bz_lrecsi              ; RESET at bz_pinit runs before bz_pread sets it)
    test byte [es:si + BZP_FLAGS], BZ_PF_GRP
    jnz .grp
    mov byte [bz_latt + bx], 1
    jmp short .d
.grp:
    mov cx, BZ_GRP_LMAX
.l:
    mov bl, [es:si + BZP_LROW]  ; (BH 0: an element's index is a byte)
    cmp bl, 0ffh
    je .d
    mov byte [bz_latt + bx], 1
    inc si
    loop .l
.d:
    pop es
    pop si
    pop cx
    pop bx
    retf

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
; NFAM, +46 FAMOFF), its part row (bz_ftab: a `fetch` family's own, a
; `resident` one's the BUNDLE, SPEC.md 128.25.6.9, found inside it by
; bz_fbfind) fetched and its head checked - 'BF', the ID and FAMV the course
; names, and the image and bss sizes it was LINKED against, ours (DS:8,
; DS:10) - its slot record written (its DATA and CODE segments: op_seg,
; op_cseg, on kern_mega the code selector the far call needs) and its mask
; ORed into bz_fhk.  A part already here is not read again, so a second call
; after anything that may MOVE a part (the arena's batch, SPEC.md 128.25.4)
; re-takes every segment and fetches nothing: the segments are never held
; across a fetch.  A course with no family leaves bz_fhk and bz_fnf 0.  CF =
; 1 a fetch was refused (op_fetch toasted why) or a head was not this build's
; (toasted here through op_say, quiet inside a bracket; never called): what
; was fetched is bz_cdrop's to give back.  DS = ours.  Preserves ES;
; clobbers AX, BX, CX, DX, SI, DI.
; -----------------------------------------------------------------------------
bz_ffetch:
    push es
    push ds
    pop es
    call bz_fhz                 ; no hook, no slot, every hook's list empty
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
    mov bx, bz_ftab - 1
    xlatb                       ; AL = its part row
    push ax
    push si
    call op_fetch               ; (it clobbers AX - DI and ES)
    pop si
    pop dx                      ; DL = the row
    jc .out
    mov al, dl
    call op_cseg
    mov [si + BZF_RCSEG], ax
    mov al, dl
    call op_seg
    mov [si + BZF_RDSEG], ax
%if BZ_NFRES
    cmp dl, BZ_P_FBUN
    jne .head
    call bz_fbfind              ; the family inside the bundle: the record
    jc .bad                     ; re-aimed at it
.head:
%endif
    mov es, [si + BZF_RDSEG]
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
    mov ah, [es:8]              ; its hooks, each one's LIST given its entry
    or [bz_fhk], ah             ; (SPEC.md 128.25.6.3): the hook's far entry
    xor bx, bx                  ; (the part's word at 12 + 2b), its code
.h:                             ; segment, the slot, the run of kinds (+9,
    shr ah, 1                   ; +10); BX = 2b.  A bit whose entry is 0 has
    jnc .hn                     ; none (a red arm's)
    mov dx, [es:bx + 12]
    or dx, dx
    jz .hn
    mov di, bx
    mov cl, 4
    shl di, cl
    add di, [bz_fhn + bx]
    add word [bz_fhn + bx], BZF_HE
    mov [bz_fhl + di], dx
    mov cx, [si + BZF_RCSEG]
    mov [bz_fhl + di + 2], cx
    mov cl, [bz_fnf]
    mov [bz_fhl + di + BZF_HESLOT], cl
    mov cx, [es:9]
    mov [bz_fhl + di + BZF_HEKN], cx
.hn:
    inc bx
    inc bx
    or ah, ah
    jnz .h
    inc byte [bz_fnf]
    add si, BZF_REC
    jmp .f
.bads:
    pop si
.bad:
    mov si, bz_t_shell          ; ('Bonanza: bad part', the shell part's) through
    call op_say                 ; op_say: OP_SAYGATE (bz_fs) holds it quiet in a
.out:                           ; game round's bracket (SPEC.md 53.7); CF = 1
    pop es
    ret

; bz_fhz - no hook active, no slot (bz_fhk, bz_fnf 0) and every hook's LIST
; empty: bz_ffetch's start, bz_cdrop's.  ES = DS = ours.  Clobbers AX, CX, DI.
bz_fhz:
    xor ax, ax
    mov [bz_fhk], ax
    mov di, bz_fhn
    mov cx, BZ_NHOOK
    rep stosw
    ret

bz_ftab:                        ; a family ID's part row, ID 1 first (bzcourse.inc)
    BZ_FTAB

%if BZ_NFRES
; -----------------------------------------------------------------------------
; bz_fbfind - record SI's family inside the RESIDENT BUNDLE (SPEC.md 128.25.6.9),
; whose segments the record holds: the bundle's headers walked from BZ_BALB
; (the balls are its head, SPEC.md 128.25.5.2),
; each a part's own but its +11, its PARAGRAPHS there (the step to the next),
; to the one whose +2 is the record's ID; the record's data segment is then
; OSAPI_SEG's SEG_SUBC over the bundle's at that paragraph, its reach the
; family's paragraphs - the bundle's data segment plus them on every real-mode
; kernel, on kern_mega the data half of a PAIR based there, the same pair
; each time it is asked (so a second bz_ffetch makes none), moving with the
; arena and going with it - and its code segment the same distance from it as
; the bundle's code segment is from the bundle's data: 0 on a real-mode
; kernel, a pair's -8 on kern_mega (128.25.6.9).  So a part runs at its own
; org 0 bundled or alone.  CF = 1 no such header, or no selector (the sum
; of the distance and the selector carries on kern_mega: CF cleared after it).
; DS = ours.
; Clobbers AX, BX, CX, DX, ES.
; -----------------------------------------------------------------------------
bz_fbfind:
    mov dx, [si + BZF_RDSEG]    ; the bundle's data segment, its headers' ES
    mov es, dx
    sub [si + BZF_RCSEG], dx    ; ...its code segment's distance from it
    mov dl, [si + BZF_RIDV]     ; DL = the ID
    mov bx, BZ_BALB             ; BX = a header's byte, from the first: past
                                ; the three balls at the bundle's head (128.25.5.2)
    xor cx, cx
.w:
    cmp word [es:bx], 'BF'
    stc
    jne .x                      ; (CF = 1: no such family here)
    mov cl, 4
    mov ax, bx
    shr ax, cl                  ; AX = its paragraph in the bundle
    mov cl, [es:bx + BZF_HPARAS] ; CX = its paragraphs
    jcxz .z                     ; (0: a malformed bundle - refused, never a loop)
    cmp dl, [es:bx + 2]
    je .hit
    add ax, cx                  ; the next header's paragraph...
    mov cl, 4
    shl ax, cl
    xchg ax, bx                 ; ...and byte
    jmp short .w
.z:
    stc
    jmp short .x
.hit:
    mov dx, [si + BZF_RDSEG]
    mov bl, SEG_SUBC
    call OSAPI_SEG              ; DX = its data segment (the pair's data half)
    jc .x
    mov [si + BZF_RDSEG], dx
    add [si + BZF_RCSEG], dx    ; (on kern_mega the distance is -8, FFF8h, and
    clc                         ; the sum CARRIES: without this CF = 1 refused
.x:                             ; every resident family there, 128.25.6.9)
    ret
%endif
