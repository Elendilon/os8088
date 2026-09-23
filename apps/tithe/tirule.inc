; =============================================================================
; os8088 - apps/tithe/tirule.inc
;
; THE RULES ENGINE (SPEC.md 97.11, TITHE-PLAN 5 and 6). The only place the
; rules exist on the machine: the game, the AI (wave 4) and the network
; checksum (wave 10) all call it. No graphics, no files, no kernel slots - it
; is arithmetic over the state below, and tools/duelsim.py is its second
; reader: tests/titherules.py replays a match file here and compares the state
; record after every round with the simulator's, to the byte.
;
; SO EVERY DECISION IS MADE IN THE SIMULATOR'S ORDER. Which hit in a lane lands
; first, when an aura is read, which intercessor answers - SPEC.md 97.11.4 pins
; each, and the comment at each site here names the rule. A difference in
; ORDER is a different game and not a rounding error, because a shield absorbs
; the first hit that reaches it (TITHE-PLAN 5.7).
;
; THE CALLER OWNS DS and nothing else is assumed: every string instruction here
; sets ES = DS itself first, because a package's callbacks arrive with ES the
; kernel's (SPEC.md 20).
;
; It needs the card table in front of it (apps/tithe/ticards.inc, GENERATED).
; =============================================================================

TR_LANES    equ 5
TR_EMPTY    equ 0FFh
TR_HAND     equ 7
TR_PILE     equ 50
TR_OPENING  equ 4
TR_STARTHP  equ 20
TR_STARTG   equ 4
TR_INCOME   equ 2
TR_SWAPS    equ 2
TR_CAP      equ 99                  ; gold and souls: the HUD's two digits
TR_ROUNDMAX equ 60                  ; a match past this is a stalemate
TR_STANCE_SNIPE equ 1

TR_A_PLAY   equ 1                   ; a plan's actions (SPEC.md 97.11.6)
TR_A_ORDER  equ 2
TR_A_SWAP   equ 3
TR_A_STANCE equ 4

TR_RES_A    equ 1                   ; ...and a round's result
TR_RES_B    equ 2
TR_RES_DRAW equ 3
TR_RES_STALE equ 4

; --- a CELL: 20 bytes, and a swap moves all of them --------------------------
CE_CARD     equ 0                   ; the card, TR_EMPTY for none
CE_INST     equ 1                   ; its instance id, what an ORDER names
CE_HP       equ 2
CE_SH       equ 3                   ; the shield left this round
CE_ST       equ 4                   ; stance: 0 FRONT, 1 SNIPE
CE_BM       equ 5                   ; ABSOLVE's permanent +melee...
CE_BR       equ 6                   ; ...and +ranged
CE_MARK     equ 7                   ; at 0 HP, dying at casualties
CE_KK       equ 8                   ; ...and its killer had KINDLE
CE_OM       equ 9                   ; THIS ROUND's orders: +melee
CE_OR       equ 10                  ; +ranged
CE_OS       equ 11                  ; +shield
CE_OG       equ 12                  ; +gold
CE_OH       equ 13                  ; +heal
CE_OPI      equ 14                  ; +pierce
CE_OSC      equ 15                  ; SCORCH granted
CE_OWD      equ 16                  ; WARD granted
CE_USED     equ 17                  ; INTERCEDE spent this casualty phase
CE_DOOM     equ 18                  ; dying this casualty phase
TR_CELLSZ   equ 20
TR_CELLS    equ 2 * 2 * TR_LANES    ; side, then column, then lane

; --- a SIDE -------------------------------------------------------------------
SD_HP       equ 0                   ; word, signed: the player
SD_GOLD     equ 2
SD_SOULS    equ 3
SD_INST     equ 4                   ; the next instance id, 1..255
SD_RNG      equ 5                   ; word: the side's shuffle generator
SD_SWAPS    equ 7
SD_DEATHS   equ 8                   ; this round, for REQUIEM
SD_HYMN     equ 9                   ; casualties: a HYMN stands
SD_MART     equ 10                  ; casualties: MARTYRs that died
SD_NHAND    equ 11
SD_HAND     equ 12
SD_NDRAW    equ SD_HAND + TR_HAND
SD_DRAW     equ SD_NDRAW + 1
SD_NDISC    equ SD_DRAW + TR_PILE
SD_DISC     equ SD_NDISC + 1
TR_SIDESZ   equ SD_DISC + TR_PILE

; THE STATE RECORD (SPEC.md 97.11.6): what tr_record writes after every round
TR_RECSIDE  equ 7 + 1 + TR_HAND + 1 + TR_PILE + 1 + TR_PILE
TR_RECSIZE  equ 1 + 2 * TR_RECSIDE + TR_CELLS * 7 + 1

; =============================================================================
; the small things
; =============================================================================

; tr_side - AL = a side -> DI = its record. Preserves every other register.
tr_side:
    push ax
    xor ah, ah
    mov di, TR_SIDESZ
    push dx
    mul di
    pop dx
    add ax, tr_sides
    mov di, ax
    pop ax
    ret

; tr_cell - AL = side, AH = column, CL = lane -> SI = the cell
; Preserves every other register.
tr_cell:
    push ax
    push dx
    shl al, 1
    add al, ah                      ; side * 2 + column
    mov dl, TR_LANES
    mul dl
    add al, cl                      ; ...* 5 + lane: the cell's index, < 20
    mov dl, TR_CELLSZ
    mul dl
    add ax, tr_cells
    mov si, ax
    pop dx
    pop ax
    ret

; tr_blk - SI = an OCCUPIED cell, AH = its column -> BX = its LIVE block
; Preserves every other register.
tr_blk:
    push ax
    push cx
    push dx
    mov cl, ah
    mov al, [si + CE_CARD]
    mov dl, TI_CR_SIZE
    mul dl
    add ax, ti_cardtab + TI_CR_FRONT
    or cl, cl
    jz .have
    add ax, TI_BLK
.have:
    mov bx, ax
    pop dx
    pop cx
    pop ax
    ret

; tr_kwb - BX = a block, DL = a keyword id -> CF=0 and DH = its number when
; the block carries it, CF=1 when it does not. Preserves every other register.
tr_kwb:
    push ax
    push cx
    push si
    lea si, [bx + TI_B_KW]
    mov cx, 3
.k:
    mov al, [si]
    mov ah, al
    and al, 31
    cmp al, dl
    je .hit
    inc si
    loop .k
    pop si
    pop cx
    pop ax
    stc
    ret
.hit:
    mov cl, 5
    shr ah, cl
    mov dh, ah
    pop si
    pop cx
    pop ax
    clc
    ret

; tr_kwc - SI = an occupied cell, AH = its column, DL = a keyword id -> as
; tr_kwb, off the cell's live block. Preserves every other register.
tr_kwc:
    push bx
    call tr_blk
    call tr_kwb
    pop bx
    ret

; tr_alive - SI = a cell -> CF=0 when it holds a character that is not
; marked. Preserves every register.
tr_alive:
    cmp byte [si + CE_CARD], TR_EMPTY
    je .no
    cmp byte [si + CE_MARK], 0
    jne .no
    clc
    ret
.no:
    stc
    ret

; tr_akw - SI = a cell, AH = its column, DL = a keyword -> CF=0 (and DH = its
; number) when the cell is ALIVE and its live block carries it
tr_akw:
    call tr_alive
    jc .out
    call tr_kwc
.out:
    ret

; tr_rand - DI = a side -> AX = its generator's next number: xorshift16 with
; shifts 7, 9, 8 (SPEC.md 97.11.5). Preserves every other register.
tr_rand:
    push cx
    push dx
    mov ax, [di + SD_RNG]
    mov dx, ax
    mov cl, 7
    shl dx, cl
    xor ax, dx
    mov dx, ax
    mov cl, 9
    shr dx, cl
    xor ax, dx
    mov dx, ax
    mov cl, 8
    shl dx, cl
    xor ax, dx
    mov [di + SD_RNG], ax
    pop dx
    pop cx
    ret

; tr_shuffle - DI = the side whose generator it is, SI = a pile, CX = its
; count. Fisher-Yates from the END: i = n-1 down to 1, j = rand mod (i+1).
; Preserves every register.
tr_shuffle:
    push ax
    push bx
    push cx
    push dx
    push bp
    cmp cx, 1
    jbe .out
    mov bx, cx
    dec bx                          ; BX = i
.i:
    call tr_rand
    xor dx, dx
    mov bp, bx
    inc bp
    div bp                          ; DX = j
    mov bp, dx
    mov al, [si + bx]
    xchg al, [ds:si + bp]
    mov [si + bx], al
    dec bx
    jnz .i
.out:
    pop bp
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tr_draw1 - DI = a side: one card off the TOP (the pile's end), the discard
; reshuffled in when the draw is empty, and over the hand limit it goes to the
; discard (TITHE-PLAN 6.2, 5.10). Preserves every register.
tr_draw1:
    push ax
    push bx
    push cx
    push si
    cmp byte [di + SD_NDRAW], 0
    jne .have
    mov cl, [di + SD_NDISC]
    xor ch, ch
    jcxz .out                       ; both empty: a dry draw, not a loss
    push di
    push es
    push ds
    pop es
    lea si, [di + SD_DISC]
    add di, SD_DRAW
    cld
    rep movsb
    pop es
    pop di
    mov cl, [di + SD_NDISC]
    mov [di + SD_NDRAW], cl
    mov byte [di + SD_NDISC], 0
    lea si, [di + SD_DRAW]
    call tr_shuffle
.have:
    dec byte [di + SD_NDRAW]
    mov bl, [di + SD_NDRAW]
    xor bh, bh
    mov al, [di + SD_DRAW + bx]
    cmp byte [di + SD_NHAND], TR_HAND
    jb .hand
    call tr_discard
    jmp short .out
.hand:
    mov bl, [di + SD_NHAND]
    mov [di + SD_HAND + bx], al
    inc byte [di + SD_NHAND]
.out:
    pop si
    pop cx
    pop bx
    pop ax
    ret

; tr_discard - DI = a side, AL = a card: onto the discard's end
tr_discard:
    push bx
    mov bl, [di + SD_NDISC]
    xor bh, bh
    mov [di + SD_DISC + bx], al
    inc byte [di + SD_NDISC]
    pop bx
    ret

; tr_clearcell - SI = a cell: empty, every field zero
tr_clearcell:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    mov di, si
    xor al, al
    mov cx, TR_CELLSZ
    cld
    rep stosb
    mov byte [si + CE_CARD], TR_EMPTY
    pop es
    pop di
    pop cx
    pop ax
    ret

; =============================================================================
; SETUP (TITHE-PLAN 6.1)
; in:  [tr_decka]/[tr_lena], [tr_deckb]/[tr_lenb], [tr_seeda], [tr_seedb]
; =============================================================================
tr_setup:
    push ax
    push bx
    push cx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov byte [tr_round], 0
    mov byte [tr_result], 0
    mov word [tr_err], 0
    mov si, tr_cells                ; an empty board
    mov cx, TR_CELLS
.cl:
    call tr_clearcell
    add si, TR_CELLSZ
    loop .cl
    xor al, al
.side:
    call tr_side
    push di                         ; the side record, zeroed
    push ax
    mov cx, TR_SIDESZ
    xor al, al
    rep stosb
    pop ax
    pop di
    mov word [di + SD_HP], TR_STARTHP
    mov byte [di + SD_GOLD], TR_STARTG
    mov byte [di + SD_INST], 1
    mov byte [di + SD_SWAPS], TR_SWAPS
    mov bx, tr_decka                ; this side's deck and seed
    or al, al
    jz .a
    mov bx, tr_deckb
.a:
    mov cx, [bx + 4]                ; the seed; 0 would stick at 0
    or cx, cx
    jnz .seed
    inc cx
.seed:
    mov [di + SD_RNG], cx
    mov cx, [bx + 2]                ; the count
    mov [di + SD_NDRAW], cl
    mov si, [bx]
    push di
    add di, SD_DRAW
    rep movsb
    pop di
    lea si, [di + SD_DRAW]
    mov cl, [di + SD_NDRAW]
    xor ch, ch
    call tr_shuffle
    mov cx, TR_OPENING
.op:
    call tr_draw1
    loop .op
    inc al
    cmp al, 2
    jb .side
    pop es
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; tr_mulligan - AL = a side: the hand back onto the draw in hand order, one
; reshuffle, four again (TITHE-PLAN 6.1)
tr_mulligan:
    push ax
    push bx
    push cx
    push si
    push di
    call tr_side
    mov cl, [di + SD_NHAND]
    xor ch, ch
    xor si, si
.b:
    cmp si, cx
    jae .done
    mov bx, di                      ; [di+si] is not an 8086 address
    mov al, [bx + SD_HAND + si]
    mov bl, [di + SD_NDRAW]
    xor bh, bh
    mov [di + SD_DRAW + bx], al
    inc byte [di + SD_NDRAW]
    inc si
    jmp short .b
.done:
    mov byte [di + SD_NHAND], 0
    lea si, [di + SD_DRAW]
    mov cl, [di + SD_NDRAW]
    xor ch, ch
    call tr_shuffle
    mov cx, TR_OPENING
.op:
    call tr_draw1
    loop .op
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE AURAS (SPEC.md 97.11.3), read where the rule reads them
; =============================================================================

; tr_anykw - AL = side, DL = keyword -> CF=0 when any ALIVE character of that
; side carries it on its live block. Preserves every register.
tr_anykw:
    push ax
    push cx
    push dx
    push si
    xor ah, ah
.c:
    xor cl, cl
.r:
    call tr_cell
    push dx
    call tr_akw
    pop dx
    jnc .yes
    inc cl
    cmp cl, TR_LANES
    jb .r
    inc ah
    cmp ah, 2
    jb .c
    stc
    jmp short .out
.yes:
    clc
.out:
    pop si
    pop dx
    pop cx
    pop ax
    ret

; tr_shmax - AL = side, AH = column, CL = lane (occupied), CH = 1 to count
; the cell's orders -> BL = its shield for the round: the live block's, +1 a
; RAMPART above or below in the same column, +1 a VIGIL across, +1 in the
; front for a MUSTER anywhere on the side. Preserves every other register.
tr_shmax:
    push ax
    push cx
    push dx
    push si
    push bx
    call tr_cell
    call tr_blk
    mov dl, [bx + TI_B_S]
    pop bx
    mov bl, dl
    or ch, ch
    jz .no
    add bl, [si + CE_OS]
.no:
    mov dl, TI_KW_RAMPART
    push cx
    dec cl
    js .up
    call tr_cell
    push dx
    call tr_akw
    pop dx
    jc .up
    inc bl
.up:
    pop cx
    push cx
    inc cl
    cmp cl, TR_LANES
    jae .dn
    call tr_cell
    push dx
    call tr_akw
    pop dx
    jc .dn
    inc bl
.dn:
    pop cx
    push ax
    xor ah, 1                       ; the cell across
    call tr_cell
    mov dl, TI_KW_VIGIL
    call tr_akw
    pop ax
    jc .vig
    inc bl
.vig:
    or ah, ah
    jnz .out
    mov dl, TI_KW_MUSTER
    call tr_anykw
    jc .out
    inc bl
.out:
    pop si
    pop dx
    pop cx
    pop ax
    ret

; tr_refill - every character's shield to its round's value. CH = 1 to count
; orders (the combat start) or 0 (upkeep)
tr_refill:
    push ax
    push bx
    push cx
    push si
    xor al, al
.s:
    xor ah, ah
.c:
    xor cl, cl
.r:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .next
    call tr_shmax
    mov [si + CE_SH], bl
.next:
    inc cl
    cmp cl, TR_LANES
    jb .r
    inc ah
    cmp ah, 2
    jb .c
    inc al
    cmp al, 2
    jb .s
    pop si
    pop cx
    pop bx
    pop ax
    ret

; tr_melee - AL = side, AH = column, CL = lane (alive) -> BL = its melee:
; the block's + ABSOLVE's + orders' + a BLESS n above or below in its column
tr_melee:
    push ax
    push cx
    push dx
    push si
    push bx
    call tr_cell
    call tr_blk
    mov dl, [bx + TI_B_M]
    pop bx
    mov bl, dl
    add bl, [si + CE_BM]
    add bl, [si + CE_OM]
    mov dl, TI_KW_BLESS
    push cx
    dec cl
    js .up
    call tr_cell
    push dx
    call tr_akw
    jc .upx
    add bl, dh
.upx:
    pop dx
.up:
    pop cx
    inc cl
    cmp cl, TR_LANES
    jae .out
    call tr_cell
    call tr_akw
    jc .out
    add bl, dh
.out:
    pop si
    pop dx
    pop cx
    pop ax
    ret

; tr_ranged - AL = side, AH = column, CL = lane (alive) -> BL = its ranged:
; the block's + ABSOLVE's + orders' + 1 for every CHORUS in either column of
; the lanes above and below
tr_ranged:
    push ax
    push cx
    push dx
    push si
    push bx
    call tr_cell
    call tr_blk
    mov dl, [bx + TI_B_R]
    pop bx
    mov bl, dl
    add bl, [si + CE_BR]
    add bl, [si + CE_OR]
    mov dl, TI_KW_CHORUS
    mov ch, cl
    dec cl                          ; the lane above...
    call .lane
    mov cl, ch
    inc cl                          ; ...and below
    call .lane
    pop si
    pop dx
    pop cx
    pop ax
    ret
.lane:
    cmp cl, TR_LANES                ; -1 is 0FFh, off the board too
    jae .lx
    push ax
    xor ah, ah
.lc:
    call tr_cell
    push dx
    call tr_akw
    pop dx
    jc .ln
    inc bl
.ln:
    inc ah
    cmp ah, 2
    jb .lc
    pop ax
.lx:
    ret

; =============================================================================
; UPKEEP (TITHE-PLAN 6.2)
; =============================================================================
tr_upkeep:
    push ax
    push cx
    push di
    inc byte [tr_round]
    xor al, al
.s:
    call tr_side
    call tr_draw1
    mov cl, [di + SD_GOLD]
    add cl, TR_INCOME
    cmp cl, TR_CAP
    jbe .g
    mov cl, TR_CAP
.g:
    mov [di + SD_GOLD], cl
    mov byte [di + SD_SWAPS], TR_SWAPS
    mov byte [di + SD_DEATHS], 0
    inc al
    cmp al, 2
    jb .s
    xor ch, ch
    call tr_refill
    pop di
    pop cx
    pop ax
    ret

; =============================================================================
; A PLAN, applied to its own half (TITHE-PLAN 6.0, 6.3)
; in:  AL = the side, SI -> the plan (a count, then op, a, b a action)
; out: SI past it. An illegal action is SKIPPED and counted in [tr_err] -
;      the simulator refuses it, so any count is a disagreement
; =============================================================================
tr_apply:
    push ax
    push bx
    push cx
    push dx
    push di
    mov [tr_ps], al
    call tr_side
    mov cl, [si]
    inc si
    xor ch, ch
    jcxz .out
.act:
    push cx
    mov al, [si]
    mov bl, [si + 1]
    mov bh, [si + 2]
    add si, 3
    push si
    cmp al, TR_A_PLAY
    jne .n1
    call tr_play
    jmp short .done
.n1:
    cmp al, TR_A_ORDER
    jne .n2
    call tr_order
    jmp short .done
.n2:
    cmp al, TR_A_SWAP
    jne .n3
    call tr_swap
    jmp short .done
.n3:
    cmp al, TR_A_STANCE
    jne .bad
    call tr_stance
    jmp short .done
.bad:
    stc
.done:
    jnc .ok
    inc word [tr_err]
.ok:
    pop si
    pop cx
    loop .act
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tr_crec - AL = a card -> BX = its record
tr_crec:
    push ax
    push dx
    mov dl, TI_CR_SIZE
    mul dl
    add ax, ti_cardtab
    mov bx, ax
    pop dx
    pop ax
    ret

; tr_pay - DI = the side, AL = a card: out of the hand (the FIRST copy) and
; its cost off the pools. CF=1 when it is not in hand or cannot be paid for,
; and then nothing has moved. Preserves every register.
tr_pay:
    push ax
    push bx
    push cx
    push si
    mov cl, [di + SD_NHAND]
    xor ch, ch
    xor si, si
    mov bx, di                      ; [di+si] is not an 8086 address
.f:
    cmp si, cx
    jae .no
    cmp [bx + SD_HAND + si], al
    je .have
    inc si
    jmp short .f
.have:
    call tr_crec
    mov ah, [di + SD_GOLD]
    cmp ah, [bx + TI_CR_COSTG]
    jb .no
    mov ah, [di + SD_SOULS]
    cmp ah, [bx + TI_CR_COSTS]
    jb .no
    mov ah, [bx + TI_CR_COSTG]
    sub [di + SD_GOLD], ah
    mov ah, [bx + TI_CR_COSTS]
    sub [di + SD_SOULS], ah
.sh:                                ; ...and the rest of the hand closes up
    inc si
    cmp si, cx
    jae .cut
    mov bx, di
    mov al, [bx + SD_HAND + si]
    mov [bx + SD_HAND + si - 1], al
    jmp short .sh
.cut:
    dec byte [di + SD_NHAND]
    clc
    jmp short .out
.no:
    stc
.out:
    pop si
    pop cx
    pop bx
    pop ax
    ret

; tr_play - DI = the side, BL = the card, BH = the column: into the TOPMOST
; empty cell (TITHE-PLAN 5.6). CF=1 illegal.
tr_play:
    push ax
    push bx
    push cx
    push dx
    push si
    mov al, bl
    push bx
    call tr_crec
    cmp byte [bx + TI_CR_KIND], TI_KIND_ORDER
    pop bx
    je .no
    mov al, [tr_ps]
    mov ah, bh
    xor cl, cl
.r:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .lane
    inc cl
    cmp cl, TR_LANES
    jb .r
    jmp short .no                   ; the column is full
.lane:
    mov al, bl
    call tr_pay
    jc .no
    call tr_clearcell
    mov [si + CE_CARD], bl
    mov al, [di + SD_INST]
    mov [si + CE_INST], al
    inc al                          ; 1..255, and round again
    jnz .i
    inc al
.i:
    mov [di + SD_INST], al
    mov ah, bh
    call tr_blk
    mov al, [bx + TI_B_HP]
    mov [si + CE_HP], al
    mov al, [bx + TI_B_S]
    mov [si + CE_SH], al
    clc
    jmp short .out
.no:
    stc
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tr_order - DI = the side, BL = the card, BH = the instance it goes on.
; An ORDER names a CHARACTER and not a cell (TITHE-PLAN 5.9.1). CF=1 illegal.
tr_order:
    push ax
    push bx
    push cx
    push dx
    push si
    mov al, bl
    push bx
    call tr_crec
    cmp byte [bx + TI_CR_KIND], TI_KIND_ORDER
    pop bx
    jne .no
    mov al, [tr_ps]
    xor ah, ah
.c:
    xor cl, cl
.r:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .next
    cmp [si + CE_INST], bh
    je .found
.next:
    inc cl
    cmp cl, TR_LANES
    jb .r
    inc ah
    cmp ah, 2
    jb .c
    jmp short .no
.found:
    mov al, bl
    call tr_pay
    jc .no
    push bx
    call tr_crec
    lea bx, [bx + TI_CR_FRONT]      ; the order's effect is its one block
    mov al, [bx + TI_B_M]
    add [si + CE_OM], al
    mov al, [bx + TI_B_R]
    add [si + CE_OR], al
    mov al, [bx + TI_B_S]
    add [si + CE_OS], al
    mov al, [bx + TI_B_G]
    add [si + CE_OG], al
    mov al, [bx + TI_B_H]
    add [si + CE_OH], al
    mov dl, TI_KW_PIERCE
    call tr_kwb
    jc .np
    add [si + CE_OPI], dh
.np:
    mov dl, TI_KW_SCORCH
    call tr_kwb
    jc .ns
    mov byte [si + CE_OSC], 1
.ns:
    mov dl, TI_KW_WARD
    call tr_kwb
    jc .nw
    mov byte [si + CE_OWD], 1
.nw:
    pop bx
    mov al, bl                      ; spent the round it is played
    call tr_discard
    clc
    jmp short .out
.no:
    stc
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tr_swap - DI = the side, BL/BH = two of its cells (column x 5 + lane). An
; empty cell is legal content (TITHE-PLAN 5.6). CF=1 illegal.
tr_swap:
    push ax
    push bx
    push cx
    push si
    push di
    cmp byte [di + SD_SWAPS], 0
    je .no
    dec byte [di + SD_SWAPS]
    mov al, bl
    call .cellof
    mov di, si
    mov al, bh
    call .cellof
    mov cx, TR_CELLSZ
.x:
    mov al, [si]
    xchg al, [di]
    mov [si], al
    inc si
    inc di
    loop .x
    clc
    jmp short .out
.no:
    stc
.out:
    pop di
    pop si
    pop cx
    pop bx
    pop ax
    ret
.cellof:                            ; AL = column x 5 + lane -> SI
    push ax
    push cx
    xor ah, ah
    mov cl, TR_LANES
    div cl                          ; AL = column, AH = lane
    mov cl, ah
    mov ah, al
    mov al, [tr_ps]
    call tr_cell
    pop cx
    pop ax
    ret

; tr_stance - DI = the side, BL = its cell, BH = the stance. CF=1 illegal.
tr_stance:
    push ax
    push cx
    push si
    mov al, bl
    xor ah, ah
    mov cl, TR_LANES
    div cl
    mov cl, ah
    mov ah, al
    mov al, [tr_ps]
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .no
    mov [si + CE_ST], bh
    clc
    jmp short .out
.no:
    stc
.out:
    pop si
    pop cx
    pop ax
    ret

; =============================================================================
; COMBAT (TITHE-PLAN 6.5, SPEC.md 97.11.4)
; =============================================================================

; a HIT, decided at the lane's start and applied in order
HT_E        equ 0                   ; the side it lands on
HT_COL      equ 1                   ; the column, or 2 for the PLAYER
HT_LANE     equ 2
HT_DMG      equ 3
HT_PIERCE   equ 4
HT_RNG      equ 5                   ; a ranged hit
HT_VOLLEY   equ 6
HT_SCORCH   equ 7
HT_KINDLE   equ 8
TR_HITSZ    equ 10
TR_PLAYER   equ 2

tr_resolve:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov ch, 1                       ; shields, after BOTH plans
    call tr_refill
    xor cl, cl
.lane:
    mov [tr_lr], cl
    call tr_lane
    mov cl, [tr_lr]
    inc cl
    cmp cl, TR_LANES
    jb .lane
    call tr_casualties
    call tr_spoils
    xor bl, bl                      ; THE VICTORY CHECK (TITHE-PLAN 6.8)
    mov al, 0
    call tr_side
    cmp word [di + SD_HP], 0
    jg .a
    or bl, 1
.a:
    mov al, 1
    call tr_side
    cmp word [di + SD_HP], 0
    jg .b
    or bl, 2
.b:
    ; bit 0 = A is down, bit 1 = B is down: A down alone is B's win
    mov al, 0
    cmp bl, 3
    jne .n3
    mov al, TR_RES_DRAW
    jmp short .set
.n3:
    cmp bl, 1
    jne .n1
    mov al, TR_RES_B
    jmp short .set
.n1:
    cmp bl, 2
    jne .set
    mov al, TR_RES_A
.set:
    mov [tr_result], al
    mov si, tr_cells                ; this round's orders are spent
    mov cx, TR_CELLS
.oc:
    push cx
    mov di, si
    add di, CE_OM
    push es
    push ds
    pop es
    xor al, al
    mov cx, CE_OWD - CE_OM + 1
    cld
    rep stosb
    pop es
    pop cx
    add si, TR_CELLSZ
    loop .oc
    cmp byte [tr_result], 0
    jne .out
    cmp byte [tr_round], TR_ROUNDMAX
    jb .out
    mov byte [tr_result], TR_RES_STALE
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tr_lane - lane [tr_lr]: every hit DECIDED from the lane's start, then
; applied in order - side 0's front melee, front ranged, rear ranged, then
; side 1's - then the lane's unmarked healers
tr_lane:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov word [tr_nhit], 0
    push es                         ; every slot starts clean: tr_hitpush
    push ds                         ; clears the NEXT one as it goes, and the
    pop es                          ; first is last lane's otherwise
    mov di, tr_hits
    mov cx, 6 * TR_HITSZ
    xor al, al
    cld
    rep stosb
    pop es
    mov di, tr_hits
    xor al, al                      ; AL = the attacking side
.as:
    xor ah, ah                      ; AH = its column
.ac:
    mov cl, [tr_lr]
    call tr_cell
    call tr_alive
    jc .anext
    mov dl, TI_KW_PIERCE            ; what every hit of this character carries
    call tr_kwc
    jnc .pi
    xor dh, dh
.pi:
    add dh, [si + CE_OPI]
    mov [tr_hpierce], dh
    mov byte [tr_hkindle], 0
    mov dl, TI_KW_KINDLE
    call tr_kwc
    jc .nk
    mov byte [tr_hkindle], 1
.nk:
    or ah, ah
    jnz .rng                        ; the rear has no melee
    call tr_melee
    or bl, bl
    jz .rng
    mov [di + HT_DMG], bl
    call tr_mtarget                 ; -> BL = column, BH = lane
    call tr_hitpush
.rng:
    call tr_ranged
    or bl, bl
    jz .anext
    mov [di + HT_DMG], bl
    mov bh, [si + CE_ST]
    call tr_rtarget                 ; -> BL = column, BH = lane
    or ah, ah                       ; THE REAR BONUS: from our rear into
    jz .nb                          ; their front, in this lane
    or bl, bl
    jnz .nb
    inc byte [di + HT_DMG]
.nb:
    mov byte [di + HT_RNG], 1
    mov dl, TI_KW_VOLLEY
    call tr_kwc
    jc .nv
    mov byte [di + HT_VOLLEY], 1
.nv:
    mov dl, TI_KW_SCORCH
    call tr_kwc
    jnc .sc
    cmp byte [si + CE_OSC], 0
    je .nsc
.sc:
    mov byte [di + HT_SCORCH], 1
.nsc:
    call tr_hitpush
.anext:
    inc ah
    cmp ah, 2
    jb .ac
    inc al
    cmp al, 2
    jb .as

    mov di, tr_hits                 ; ...and APPLIED, in that order
    mov cx, [tr_nhit]
    jcxz .heal
.h:
    push cx
    call tr_hitapply
    pop cx
    add di, TR_HITSZ
    loop .h
.heal:
    xor al, al
.hs:
    xor ah, ah
.hc:
    mov cl, [tr_lr]
    call tr_heal
    inc ah
    cmp ah, 2
    jb .hc
    inc al
    cmp al, 2
    jb .hs
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tr_hitpush - DI = the hit being built (HT_DMG and the flags set), AL = the
; attacking side, BL = the target column, BH = its lane: finish it and move on.
; The flags a hit does not set are cleared here, for the next one.
tr_hitpush:
    push ax
    xor al, 1
    mov [di + HT_E], al
    mov [di + HT_COL], bl
    mov [di + HT_LANE], bh
    mov al, [tr_hpierce]
    mov [di + HT_PIERCE], al
    mov al, [tr_hkindle]
    mov [di + HT_KINDLE], al
    add di, TR_HITSZ
    inc word [tr_nhit]
    push cx                         ; the next one starts clean
    push di
    push es
    push ds
    pop es
    xor al, al
    mov cx, TR_HITSZ
    cld
    rep stosb
    pop es
    pop di
    pop cx
    pop ax
    ret

; tr_mtarget - AL = the attacking side, lane [tr_lr] -> BL = column (or
; TR_PLAYER), BH = lane. TITHE-PLAN 5.4's melee, and GUARD (SPEC.md 97.11.3):
; a guard in the front of the lane above or below takes the gap-punish itself
tr_mtarget:
    push ax
    push cx
    push dx
    push si
    xor al, 1
    mov cl, [tr_lr]
    mov bh, cl
    xor ah, ah
    call tr_cell
    mov bl, 0
    cmp byte [si + CE_CARD], TR_EMPTY
    jne .out
    inc ah
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .player
    xor ah, ah                      ; a gap: is a GUARD beside it?
    mov dl, TI_KW_GUARD
    mov ch, cl
    dec cl
    cmp cl, TR_LANES
    jae .g2
    call tr_cell
    call tr_akw
    jnc .guard
.g2:
    mov cl, ch
    inc cl
    cmp cl, TR_LANES
    jae .rear
    call tr_cell
    call tr_akw
    jnc .guard
.rear:
    mov bl, 1
    jmp short .out
.guard:
    mov bl, 0
    mov bh, cl
    jmp short .out
.player:
    mov bl, TR_PLAYER
.out:
    pop si
    pop dx
    pop cx
    pop ax
    ret

; tr_rtarget - AL = the attacking side, BH = the shooter's stance, lane
; [tr_lr], [tr_hpierce] -> BL = column (or TR_PLAYER), BH = lane. SNIPE past a
; front whose shield is gone after PIERCE; WALLED, it falls back and hits the
; wall (TITHE-PLAN 5.4 rule 3)
tr_rtarget:
    push ax
    push cx
    push dx
    push si
    xor al, 1
    mov cl, [tr_lr]
    mov dh, bh
    mov bh, cl
    xor ah, ah
    call tr_cell                    ; SI = their front
    cmp dh, TR_STANCE_SNIPE
    jne .front
    cmp byte [si + CE_CARD], TR_EMPTY
    je .snipe
    mov dl, [si + CE_SH]
    sub dl, [tr_hpierce]
    jbe .snipe                      ; no shield left after PIERCE: open
    jmp short .hitf                 ; WALLED
.snipe:
    inc ah
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .player
    mov bl, 1
    jmp short .out
.front:
    cmp byte [si + CE_CARD], TR_EMPTY
    jne .hitf
    inc ah
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .player
    mov bl, 1
    jmp short .out
.hitf:
    mov bl, 0
    jmp short .out
.player:
    mov bl, TR_PLAYER
.out:
    pop si
    pop dx
    pop cx
    pop ax
    ret

; tr_hitapply - DI = a hit: the player, or a character and then its SCORCH
; and its VOLLEY, in that order
tr_hitapply:
    push ax
    push bx
    push cx
    push dx
    push si
    mov al, [di + HT_E]
    cmp byte [di + HT_COL], TR_PLAYER
    jne .char
    call tr_playerhit
    jmp .out
.char:
    mov ah, [di + HT_COL]
    mov cl, [di + HT_LANE]
    mov bl, [di + HT_DMG]
    mov bh, [di + HT_PIERCE]
    mov dl, [di + HT_RNG]
    mov dh, [di + HT_KINDLE]
    call tr_hit                     ; -> BL = the overkill
    cmp byte [di + HT_SCORCH], 0
    je .vol
    or bl, bl
    jz .vol
    or ah, ah
    jnz .vol
    inc ah                          ; into the character behind it
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .scx
    xor bh, bh                      ; no PIERCE on the carry
    call tr_hit
.scx:
    dec ah
.vol:
    cmp byte [di + HT_VOLLEY], 0
    je .out
    mov ch, cl                      ; 1 to the lanes above and below
    dec cl
    call .one
    mov cl, ch
    inc cl
    call .one
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.one:
    cmp cl, TR_LANES
    jae .ox
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .ox
    push bx
    mov bl, 1
    mov bh, [di + HT_PIERCE]
    mov dl, 1
    mov dh, [di + HT_KINDLE]
    call tr_hit
    pop bx
.ox:
    ret

; tr_playerhit - DI = a hit on the player of side AL, in lane [tr_lr].
; STANDFAST: an alive character with it in the lane ABOVE OR BELOW takes it
; off - a player is only hit through a lane with nobody in it, so a keyword
; that guarded its own lane could never fire (SPEC.md 97.11.3)
tr_playerhit:
    push ax
    push cx
    push dx
    push si
    push di
    mov dl, TI_KW_STANDFAST
    mov ch, [tr_lr]
    mov cl, ch
    dec cl
    call .lane
    jnc .out
    mov cl, ch
    inc cl
    call .lane
    jnc .out
    mov dl, [di + HT_DMG]
    xor dh, dh
    call tr_side
    sub [di + SD_HP], dx
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret
.lane:                              ; CL = a lane: CF=0 when a STANDFAST stands
    cmp cl, TR_LANES
    jae .ln
    xor ah, ah
.lc:
    call tr_cell
    push dx
    call tr_akw
    pop dx
    jnc .ly
    inc ah
    cmp ah, 2
    jb .lc
.ln:
    stc
.ly:
    ret

; tr_hit - one hit on the character at side AL, column AH, lane CL: BL
; damage, BH pierce, DL = 1 ranged, DH = the attacker's KINDLE.
; Shield first - PIERCE ignores that much of it - then BULWARK's floor under
; the shield, SANCTUARY's floor under the HP for a ranged hit, then HP.
; out: BL = the OVERKILL, what went past a death, for SCORCH
; Preserves every other register.
tr_hit:
    push ax
    push cx
    push dx
    push si
    push bx
    mov [tr_tkk], dh
    mov [tr_trng], dl
    call tr_cell
    cmp byte [si + CE_MARK], 0
    jne .zero
    mov dl, [si + CE_SH]            ; eff = max(0, shield - pierce)
    sub dl, bh
    jae .eff
    xor dl, dl
.eff:
    cmp dl, bl                      ; absorbed = min(damage, eff)
    jbe .ab
    mov dl, bl
.ab:
    sub [si + CE_SH], dl
    sub bl, dl                      ; BL = the rest
    push dx
    mov dl, TI_KW_BULWARK
    call tr_kwc
    jc .nbw
    cmp [si + CE_SH], dh
    jae .nbw
    mov [si + CE_SH], dh
.nbw:
    pop dx
    mov byte [tr_floor], 0
    cmp byte [tr_trng], 0
    je .nf
    push ax                         ; SANCTUARY in the target's lane
    push si
    xor ah, ah
    mov dl, TI_KW_SANCTUARY
.sn:
    call tr_cell
    push dx
    call tr_akw
    pop dx
    jc .sx
    mov byte [tr_floor], 1
.sx:
    inc ah
    cmp ah, 2
    jb .sn
    pop si
    pop ax
.nf:
    or bl, bl
    jz .zero
    mov al, [si + CE_HP]
    sub al, bl                      ; hp - rest, signed
    jl .low
    cmp al, [tr_floor]
    jg .lives                       ; hp - rest > floor
.low:
    cmp byte [tr_floor], 0
    je .dies
    mov byte [si + CE_HP], 1
    jmp short .zero
.lives:
    mov [si + CE_HP], al
    jmp short .zero
.dies:
    sub bl, [si + CE_HP]            ; the overkill: rest - hp
    mov byte [si + CE_HP], 0
    mov byte [si + CE_MARK], 1
    mov al, [tr_tkk]
    mov [si + CE_KK], al
    pop ax                          ; the caller's BX, with BL replaced
    mov bh, ah
    jmp short .ret
.zero:
    pop bx
    xor bl, bl
.ret:
    pop si
    pop dx
    pop cx
    pop ax
    ret

; tr_heal - side AL, column AH, lane CL: an alive healer spends its pool down
; TITHE-PLAN 5.5.1's chain - itself, across, above, below, diagonal up,
; diagonal down - and a character healed off zero is pulled back
tr_heal:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call tr_cell
    call tr_alive
    jc .out
    call tr_blk
    mov dl, [bx + TI_B_H]
    add dl, [si + CE_OH]
    or dl, dl
    jz .out
    push dx
    mov dl, TI_KW_MERCY
    call tr_anykw
    pop dx
    jc .pool
    inc dl
.pool:
    mov [tr_pool], dl
    mov di, tr_chain
    mov ch, 6
.step:
    push ax
    push cx
    mov dl, [di]                    ; 1 = the other column
    or dl, dl
    jz .col
    xor ah, 1
.col:
    add cl, [di + 1]                ; the lane step
    cmp cl, TR_LANES
    jae .skip
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .skip
    call tr_blk
    mov dl, [bx + TI_B_HP]          ; the top of it
    sub dl, [si + CE_HP]
    jbe .skip
    cmp dl, [tr_pool]
    jbe .amt
    mov dl, [tr_pool]
.amt:
    add [si + CE_HP], dl
    mov byte [si + CE_MARK], 0
    mov byte [si + CE_KK], 0
    sub [tr_pool], dl
.skip:
    pop cx
    pop ax
    add di, 2
    cmp byte [tr_pool], 0
    je .out
    dec ch
    jnz .step
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

tr_chain:   db 0, 0,  1, 0,  0, -1,  0, 1,  1, -1,  1, 1

; =============================================================================
; CASUALTIES (TITHE-PLAN 6.6): WARD, INTERCEDE, then the deaths in scan order
; =============================================================================
tr_casualties:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov byte [tr_ndie], 0
    xor cl, cl                      ; lane, then side, then column
.r:
    xor al, al
.s:
    xor ah, ah
.c:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .next
    cmp byte [si + CE_MARK], 0
    je .next
    cmp byte [si + CE_OWD], 0
    je .ic
    mov byte [si + CE_HP], 1        ; WARD: it holds at 1
    mov byte [si + CE_MARK], 0
    jmp short .next
.ic:
    call tr_intercede
    jnc .next                       ; somebody died instead
    mov bl, [si + CE_KK]
    call tr_doom
.next:
    inc ah
    cmp ah, 2
    jb .c
    inc al
    cmp al, 2
    jb .s
    inc cl
    cmp cl, TR_LANES
    jb .r

    xor al, al                      ; HYMN: does one stand, not dying?
.hy:
    call tr_side
    mov byte [di + SD_HYMN], 0
    mov byte [di + SD_MART], 0
    mov dl, TI_KW_HYMN
    xor ah, ah
.hc:
    xor cl, cl
.hr:
    call tr_cell
    cmp byte [si + CE_DOOM], 0
    jne .hn
    push dx
    call tr_akw
    pop dx
    jc .hn
    mov byte [di + SD_HYMN], 1
.hn:
    inc cl
    cmp cl, TR_LANES
    jb .hr
    inc ah
    cmp ah, 2
    jb .hc
    inc al
    cmp al, 2
    jb .hy

    xor bx, bx                      ; ...and the deaths, in list order
.d:
    cmp bl, [tr_ndie]
    jae .mart
    push bx
    shl bx, 1
    shl bx, 1
    mov al, [tr_die + bx]
    mov ah, [tr_die + bx + 1]
    mov cl, [tr_die + bx + 2]
    mov dl, [tr_die + bx + 3]       ; KINDLE
    call tr_death
    pop bx
    inc bx
    jmp short .d
.mart:
    xor al, al                      ; MARTYR: the rest of its side heal 3
.ms:
    call tr_side
    mov ch, [di + SD_MART]
.mm:
    or ch, ch
    jz .mn
    push cx
    xor ah, ah
.mc:
    xor cl, cl
.mr:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .mx
    call tr_blk
    mov dl, [si + CE_HP]
    add dl, 3
    cmp dl, [bx + TI_B_HP]
    jbe .mh
    mov dl, [bx + TI_B_HP]
.mh:
    mov [si + CE_HP], dl
.mx:
    inc cl
    cmp cl, TR_LANES
    jb .mr
    inc ah
    cmp ah, 2
    jb .mc
    pop cx
    dec ch
    jmp short .mm
.mn:
    inc al
    cmp al, 2
    jb .ms
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tr_doom - side AL, column AH, lane CL onto the death list, BL = KINDLE
tr_doom:
    push bx
    push si
    push dx
    mov dl, bl
    mov bl, [tr_ndie]
    xor bh, bh
    shl bx, 1
    shl bx, 1
    mov [tr_die + bx], al
    mov [tr_die + bx + 1], ah
    mov [tr_die + bx + 2], cl
    mov [tr_die + bx + 3], dl
    inc byte [tr_ndie]
    call tr_cell
    mov byte [si + CE_DOOM], 1
    pop dx
    pop si
    pop bx
    ret

; tr_intercede - SI = a marked cell at side AL, column AH, lane CL. An alive
; neighbour with INTERCEDE that has not spent it - above, below, then across -
; dies instead and this one holds at 1. CF=0 when one did.
tr_intercede:
    push ax
    push bx
    push cx
    push dx
    push si                         ; the caller reads the dying cell's KINDLE
    push di                         ; after this, so SI comes back unmoved
    mov di, si
    mov dl, TI_KW_INTERCEDE
    mov ch, cl
    dec cl                          ; above
    call .try
    jnc .done
    mov cl, ch
    inc cl                          ; below
    call .try
    jnc .done
    mov cl, ch
    xor ah, 1                       ; across
    call .try
    jnc .done
    stc
    jmp short .out
.done:
    mov byte [di + CE_HP], 1        ; the one it saved
    mov byte [di + CE_MARK], 0
    clc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.try:
    cmp cl, TR_LANES
    jae .tn
    call tr_cell
    cmp byte [si + CE_USED], 0
    jne .tn
    push dx
    call tr_akw
    pop dx
    jc .tn
    mov byte [si + CE_USED], 1
    xor bl, bl                      ; an intercessor's killer had no KINDLE
    call tr_doom
    clc
    ret
.tn:
    stc
    ret

; tr_death - side AL, column AH, lane CL dies; DL = its killer's KINDLE. The
; card to its owner's discard, POWER + KINDLE + the killer's HYMN in souls to
; the other side, ABSOLVE in its lane, a MARTYR counted
tr_death:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .out
    push dx
    mov dl, TI_KW_MARTYR
    call tr_kwc
    pop dx
    jc .nm
    call tr_side
    inc byte [di + SD_MART]
.nm:
    push ax
    mov al, [si + CE_CARD]
    call tr_crec
    mov bh, [bx + TI_CR_POWER]
    pop ax
    add bh, dl                      ; + KINDLE
    push ax
    xor al, 1
    call tr_side                    ; DI = the killer's side
    add bh, [di + SD_HYMN]
    add bh, [di + SD_SOULS]
    cmp bh, TR_CAP
    jbe .so
    mov bh, TR_CAP
.so:
    mov [di + SD_SOULS], bh
    pop ax
    call tr_side                    ; DI = the dead one's own
    push ax
    mov al, [si + CE_CARD]
    call tr_discard
    pop ax
    inc byte [di + SD_DEATHS]
    call tr_clearcell
    push ax                         ; ABSOLVE: its lane and the two beside it
    push cx
    mov ch, cl
    dec cl
.al:
    cmp cl, TR_LANES
    jae .anl
    xor ah, ah
.ab:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .an
    cmp byte [si + CE_DOOM], 0
    jne .an
    mov dl, TI_KW_ABSOLVE
    call tr_kwc
    jc .an
    cmp byte [si + CE_BM], 9
    jae .am
    inc byte [si + CE_BM]
.am:
    cmp byte [si + CE_BR], 9
    jae .an
    inc byte [si + CE_BR]
.an:
    inc ah
    cmp ah, 2
    jb .ab
.anl:
    inc cl
    mov dh, ch
    inc dh
    cmp cl, dh                      ; up to the lane below it
    jbe .al
    pop cx
    pop ax
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; SPOILS (TITHE-PLAN 6.7): GOLD, LEVY, STEWARD in gold; PYRE, REQUIEM in souls
; =============================================================================
tr_spoils:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    xor al, al
.s:
    call tr_side
    mov byte [tr_rear], 0           ; the side's rear column, for STEWARD
    mov ah, 1
    xor cl, cl
.rc:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .rn
    inc byte [tr_rear]
.rn:
    inc cl
    cmp cl, TR_LANES
    jb .rc
    xor ah, ah
.c:
    xor cl, cl
.r:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .next
    call tr_blk
    mov ch, [bx + TI_B_G]           ; CH = gold, [tr_so] = souls
    add ch, [si + CE_OG]
    mov byte [tr_so], 0
    mov dl, TI_KW_LEVY
    call tr_kwb
    jc .nl
    add ch, dh
.nl:
    mov dl, TI_KW_PYRE
    call tr_kwb
    jc .np
    mov [tr_so], dh
.np:
    mov dl, TI_KW_STEWARD
    call tr_kwb
    jc .ns
    add ch, [tr_rear]
.ns:
    mov dl, TI_KW_REQUIEM
    call tr_kwb
    jc .nr
    mov dl, [di + SD_DEATHS]
    add [tr_so], dl
.nr:
    add ch, [di + SD_GOLD]
    cmp ch, TR_CAP
    jbe .g
    mov ch, TR_CAP
.g:
    mov [di + SD_GOLD], ch
    mov ch, [di + SD_SOULS]
    add ch, [tr_so]
    cmp ch, TR_CAP
    jbe .so
    mov ch, TR_CAP
.so:
    mov [di + SD_SOULS], ch
.next:
    inc cl
    cmp cl, TR_LANES
    jb .r
    inc ah
    cmp ah, 2
    jb .c
    inc al
    cmp al, 2
    jb .s
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE STATE RECORD (SPEC.md 97.11.6) - DI -> TR_RECSIZE bytes. Advances DI.
; =============================================================================
tr_record:
    push ax
    push bx
    push cx
    push si
    push es
    push ds
    pop es
    cld
    mov al, [tr_round]
    stosb
    xor bl, bl
.s:
    mov al, bl
    push di
    call tr_side
    mov si, di
    pop di
    mov ax, [si + SD_HP]            ; the player, clamped to a byte
    or ax, ax
    jge .p
    xor ax, ax
.p:
    cmp ax, 255
    jbe .p2
    mov ax, 255
.p2:
    stosb
    mov al, [si + SD_GOLD]
    stosb
    mov al, [si + SD_SOULS]
    stosb
    mov al, [si + SD_INST]
    stosb
    mov ax, [si + SD_RNG]
    stosw
    mov al, [si + SD_SWAPS]
    stosb
    mov bh, TR_HAND                 ; the three piles, padded with 0FFh
    lea si, [si + SD_NHAND]
    call .pile
    mov bh, TR_PILE
    call .pile
    mov bh, TR_PILE
    call .pile
    inc bl
    cmp bl, 2
    jb .s
    mov si, tr_cells                ; the board, side then column then lane
    mov cx, TR_CELLS
.c:
    cmp byte [si + CE_CARD], TR_EMPTY
    jne .full
    mov al, TR_EMPTY
    stosb
    xor ax, ax
    stosw
    stosw
    stosw
    jmp short .cn
.full:
    push si
    push cx
    mov cx, CE_BR + 1               ; card inst hp sh st bm br
    rep movsb
    pop cx
    pop si
.cn:
    add si, TR_CELLSZ
    loop .c
    mov al, [tr_result]
    stosb
    pop es
    pop si
    pop cx
    pop bx
    pop ax
    ret
.pile:                              ; SI -> a count and its bytes; BH = its
    push cx                         ; size. Advances SI past ALL of them
    lodsb
    stosb
    mov cl, al
    xor ch, ch
    rep movsb                       ; the live ones...
    mov cl, bh
    sub cl, al                      ; ...and the rest of the array, padded
    add si, cx
    mov al, TR_EMPTY
    rep stosb
    pop cx
    ret

; =============================================================================
; the state
; =============================================================================
tr_decka:   dw 0, 0, 0              ; the deck, its count, the seed
tr_deckb:   dw 0, 0, 0
tr_round:   db 0
tr_result:  db 0
tr_err:     dw 0                    ; illegal actions skipped
tr_ps:      db 0                    ; the side a plan is being applied for
tr_lr:      db 0                    ; the lane being fought
tr_nhit:    dw 0
tr_hpierce: db 0
tr_hkindle: db 0
tr_tkk:     db 0
tr_trng:    db 0
tr_floor:   db 0
tr_pool:    db 0
tr_ndie:    db 0
tr_rear:    db 0
tr_so:      db 0
tr_hits:    times 6 * TR_HITSZ db 0
tr_die:     times TR_CELLS * 2 * 4 db 0
tr_sides:   times 2 * TR_SIDESZ db 0
tr_cells:   times TR_CELLS * TR_CELLSZ db 0
