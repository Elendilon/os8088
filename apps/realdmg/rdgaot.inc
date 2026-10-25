; =============================================================================
; os8088 - apps/realdmg/rdgaot.inc
;
; A PRECOMPILED cartridge's run-time half (docs/REALDMG-SPEC.md section 20.9):
; what the core's table cannot hold is in a list the host sorted, and a miss
; looks there before it goes to the interpreter. Included by a host that runs
; precompiled code - tools/gbaot/aothost.asm, and the package's RDG_AOT arm -
; after rdgdefs.inc. Its one routine is far-jumped to by the core, so it may
; sit in any segment.
;
; The list: S_AOTLN entries of 8 bytes at S_AOTLSEG:0, the block table's own
; layout (PC, bank key, -, the block's offset and segment), sorted by bank
; key and then PC.
; =============================================================================

; rdg_aotmiss - the core's tr_new2 for a ROM PC in neither its slot nor the
; neighbour, under a FIXED table (REALDMG-SPEC 16.8): SI = the PC, DH = its
; bank key, BX = the slot (the Game Boy's HL in [ss:S_SAVBX]), DL and ES
; free, every other register the Game Boy's. Into the block when the list has
; it, as tr_go goes; else into the interpreter, as tr_kint does. The core runs
; with SP the Game Boy's, so nothing is pushed: the search keeps its bounds in
; the view
rdg_aotmiss:
    mov [ss:S_AOTKEY],dh
    mov es,[ss:S_AOTLSEG]
    mov word [ss:S_AOTLO],0
    mov bx,[ss:S_AOTLN]
    mov [ss:S_AOTHI],bx
.l:
    mov bx,[ss:S_AOTLO]             ; the first entry not below (key, PC)
    cmp bx,[ss:S_AOTHI]
    jae .end
    add bx,[ss:S_AOTHI]
    shr bx,1
    mov [ss:S_AOTMID],bx
    shl bx,1
    shl bx,1
    shl bx,1
    mov dl,[es:bx+2]
    cmp dl,[ss:S_AOTKEY]
    jb .lt
    ja .ge
    cmp [es:bx],si
    jb .lt
.ge:
    mov bx,[ss:S_AOTMID]
    mov [ss:S_AOTHI],bx
    jmp short .l
.lt:
    mov bx,[ss:S_AOTMID]
    inc bx
    mov [ss:S_AOTLO],bx
    jmp short .l
.end:
    cmp bx,[ss:S_AOTLN]
    jae .no
    shl bx,1
    shl bx,1
    shl bx,1
    cmp [es:bx],si
    jne .no
    mov dl,[es:bx+2]
    cmp dl,[ss:S_AOTKEY]
    jne .no
    les dx,[es:bx+4]                ; the block, as tr_go enters one -
    or dx,dx                        ;   unless its image was not loaded
    jz .no                          ;   (REALDMG-SPEC 20.10: offset 0)
    mov [ss:S_JITOUT],dx
    mov [ss:S_JITOUT+2],es
    mov bx,[ss:S_SAVBX]
    jmp far [ss:S_JITOUT]
.no:
    mov bx,[ss:S_SAVBX]             ; the interpreter's, as tr_kint goes
    jmp far [ss:S_AOTINT]

; rdg_aotattach - DS = the view: the list at AX (CX entries) attached, and
; the core's misses pointed at rdg_aotmiss in THIS segment. Every register kept
rdg_aotattach:
    push ax
    mov [S_AOTLSEG],ax
    mov [S_AOTLN],cx
    mov word [S_AOTVEC],rdg_aotmiss
    mov [S_AOTVEC+2],cs
    mov word [S_AOTINT],RDGC_TR_INT
    mov ax,[S_DISP+2]               ; the core
    mov [S_AOTINT+2],ax
    pop ax
    ret
