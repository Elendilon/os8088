; =============================================================================
; os8088 - apps/tithe/tigame.inc
;
; THE ROUND LOOP (SPEC.md 97.12, TITHE-PLAN 6 and wave 3): the rules engine
; (tirule.inc) turned into a game two people can play at one machine.
;
; ONE SENTENCE IS THE WHOLE DESIGN, and it is TITHE-PLAN 5.0.2's: the board a
; planner sees is `apply(plan, frozen board)`. The frozen board is the engine's
; state at the end of UPKEEP, copied aside; a plan is an ordered list of the
; engine's own actions; and every edit - a play, an undo, a removal from the
; middle - re-applies the whole list to a fresh copy of the frozen board. There
; is no undo stack and no inverse of any action, and the preview IS the engine,
; so nothing on the glass can disagree with what a commit will do.
;
; AND THE SAME SENTENCE IS WHY HOT-SEAT DOES NOT LEAK (TITHE-PLAN 6.3.1). The
; second planner is shown `apply(their plan, frozen board)` - the SAME frozen
; board the first was - so the first planner's plays, their spend and their
; swaps are nowhere in it. Only the commit of the second applies both.
;
; THE VIEWS. Everything the renderer draws - a hand card, a board cell, the
; numbers on either, the status line - reads a VIEW RECORD (ticard.inc's TI_C_*
; layout), and this file is the only writer of them. Views 0..6 are the
; planner's hand, 7..26 the board's twenty cells in the renderer's own order.
; A cell's view says which ART it wears, and the renderer composes a figure
; from that; so a plan edit rebuilds the cells whose art moved and redraws the
; numbers whose record did, and nothing else.
; =============================================================================

TG_MAXACT   equ 16                  ; actions a plan may hold
TG_PLANSZ   equ 1 + TG_MAXACT * 3   ; a count, then (op, a, b) as tr_apply reads
TI_NVIEW    equ TI_HAND + TI_CELLS

TG_PH_PLAN  equ 0                   ; a player is planning
TG_PH_PASS  equ 1                   ; the pass-the-machine screen
TG_PH_OVER  equ 2                   ; the match is decided

; -----------------------------------------------------------------------------
; tg_new - a new match: two starter decks, fresh seeds, the first upkeep, and
; P1 to plan. Preserves every register.
; -----------------------------------------------------------------------------
tg_new:
    push ax
    push bx
    push cx
    mov word [tr_decka], ti_deck_bulwark + 1
    mov al, [ti_deck_bulwark]
    xor ah, ah
    mov [tr_decka + 2], ax
    mov word [tr_deckb], ti_deck_choir + 1
    mov al, [ti_deck_choir]
    mov [tr_deckb + 2], ax
    call OSAPI_GET_TICKS            ; THE SEEDS ARE THE CLOCK'S: a match is a
    mov [tr_decka + 4], ax          ; pure function of its two decks and two
    mov bx, ax                      ; seeds (TITHE-PLAN 14.1), and a hot-seat
    mov cl, 5                       ; match has no reason to be the same one
    rol bx, cl                      ; twice
    xor bx, 0A5C3h
    mov [tr_deckb + 4], bx
    call tr_setup
    call tr_upkeep
    call tg_save
    mov byte [tg_plan0], 0
    mov byte [tg_plan1], 0
    mov byte [tg_side], 0
    mov byte [tg_ph], TG_PH_PLAN
    mov byte [tg_rnd], 0
    call tg_replay
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_save / tg_load - the engine's state to the frozen board, and back
; Preserves every register.
; -----------------------------------------------------------------------------
tg_save:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov si, tr_sides
    mov di, tg_frz
    mov cx, 2 * TR_SIDESZ
    rep movsb
    mov si, tr_cells
    mov cx, TR_CELLS * TR_CELLSZ
    rep movsb
    pop es
    pop di
    pop si
    pop cx
    ret

tg_load:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov si, tg_frz
    mov di, tr_sides
    mov cx, 2 * TR_SIDESZ
    rep movsb
    mov di, tr_cells
    mov cx, TR_CELLS * TR_CELLSZ
    rep movsb
    pop es
    pop di
    pop si
    pop cx
    ret

; tg_planp - AL = a side -> BX = its plan. Preserves every other register.
tg_planp:
    mov bx, tg_plan0
    or al, al
    jz .out
    mov bx, tg_plan1
.out:
    ret

; tg_frzside - AL = a side -> DI = its FROZEN record. Preserves the rest.
tg_frzside:
    mov di, tg_frz
    or al, al
    jz .out
    add di, TR_SIDESZ
.out:
    ret

; -----------------------------------------------------------------------------
; tg_replay - the planner's board: the frozen one, their plan applied, and
; every view from it. Preserves every register.
; -----------------------------------------------------------------------------
tg_replay:
    push ax
    push bx
    push si
    call tg_load
    mov word [tr_err], 0
    mov al, [tg_side]
    call tg_planp
    mov si, bx
    mov [tr_ps], al
    call tr_apply
    call tg_views
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_ecell - board cell CX -> SI = the engine's cell, AL = its side, AH = its
; column (0 FRONT, 1 REAR), DL = its lane. Preserves every other register.
;
; THE BOARD IS DRAWN P1's REAR FIRST: column 0 is P1's rear, 1 P1's front, 2
; P2's front and 3 P2's rear (SPEC.md 97.2.1), where the engine counts each
; side's front first. Swapping the first two is the whole of the map, and it
; is its own inverse (tg_bcol).
; -----------------------------------------------------------------------------
tg_ecell:
    push bx
    push cx
    mov ax, cx
    mov cl, TI_ROWS
    div cl                          ; AL = the board column, AH = the lane
    mov dl, ah
    mov bl, al
    xor bh, bh
    mov al, [tg_bcol + bx]          ; side x 2 + column
    mov ah, al
    shr al, 1
    and ah, 1
    mov cl, dl
    call tr_cell
    pop cx
    pop bx
    ret

; the board column for side x 2 + column, and the reverse: the same four
tg_bcol:    db 1, 0, 2, 3

; -----------------------------------------------------------------------------
; tg_views - every view record from the engine's state, and the HUD's numbers
; Preserves every register.
;
; A CELL WHOSE RECORD CHANGED IS MARKED in tg_vdirty, so an edit redraws the
; numbers that moved and not twenty; a cell whose ART changed is what
; tg_sync compares against the art its poses were composed with (tg_cart).
; -----------------------------------------------------------------------------
tg_views:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, [tg_side]               ; THE HAND is the planner's FROZEN hand -
    call tg_frzside                 ; a card played stays in its slot, marked
    mov si, di                      ; played, so an undo puts it back where it
    xor cx, cx                      ; was rather than at the end
.hand:
    cmp cx, TI_HAND
    jae .cells
    mov al, TR_EMPTY
    cmp cl, [si + SD_NHAND]
    jae .hset
    mov bx, cx
    mov al, [bx + si + SD_HAND]
.hset:
    call tg_vtmp_card               ; the card's own record, into tg_vtmp
    mov ax, cx
    call tg_vput
    inc cx
    jmp short .hand
.cells:
    xor cx, cx
.cell:
    cmp cx, TI_CELLS
    jae .played
    push cx
    call tg_ecell                   ; SI = the cell, AH = its column
    mov [tg_ecol], ah
    mov al, [si + CE_CARD]
    call tg_vtmp_card
    mov [tg_vtmp + TI_C_COL], ah
    cmp al, TR_EMPTY
    je .cput
    call tg_vtmp_live               ; ...and what it is doing THERE
.cput:
    pop cx
    mov ax, cx
    add ax, TI_HAND
    call tg_vput
    jnc .cnext
    mov bx, cx                      ; the record moved: its numbers are owed
    mov byte [tg_vdirty + bx], 1
.cnext:
    inc cx
    jmp short .cell
.played:
    ; --- WHICH HAND SLOTS ARE EMPTY: past the hand's end, and every play in
    ; the plan (tg_pslot says which slot each one came from)
    mov al, [tg_side]
    call tg_frzside
    mov bl, 0FFh                    ; every slot, then clear the real ones
    mov cl, [di + SD_NHAND]
    mov al, 1
.pm:
    or cl, cl
    jz .pd
    not al
    and bl, al
    not al
    shl al, 1
    dec cl
    jmp short .pm
.pd:
    mov al, [tg_side]
    push bx
    call tg_planp
    mov cl, [bx]
    mov si, bx
    pop bx
    xor ch, ch
    mov di, tg_pslot0
    cmp byte [tg_side], 0
    je .ps
    mov di, tg_pslot1
.ps:
    jcxz .pset
.pl:
    mov al, [di]
    inc di
    cmp al, TI_HAND
    jae .pn
    push cx
    mov cl, al
    mov al, 1
    shl al, cl
    or bl, al
    pop cx
.pn:
    loop .pl
.pset:
    mov [ti_played], bl

    ; --- THE HUD's NUMBERS, off the same state ----------------------------
    xor al, al
    call tr_side
    call .hp
    mov [ti_p1hp], al
    mov al, [di + SD_GOLD]
    mov [ti_p1gold], al
    mov al, [di + SD_SOULS]
    mov [ti_p1soul], al
    mov al, 1
    call tr_side
    call .hp
    mov [ti_p2hp], al
    mov al, [di + SD_GOLD]
    mov [ti_p2gold], al
    mov al, [di + SD_SOULS]
    mov [ti_p2soul], al
    mov al, [tg_side]
    call tr_side
    mov al, [di + SD_SWAPS]
    mov [ti_swaps], al
    mov al, [tr_round]
    mov [ti_round], al
    mov word [tg_phs], ti_s_p1plans
    cmp byte [tg_side], 0
    je .out
    mov word [tg_phs], ti_s_p2plans
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.hp:                                ; AL = the player's HP, floored at 0
    mov ax, [di + SD_HP]
    or ax, ax
    jns .hpp
    xor ax, ax
.hpp:
    cmp ax, 99
    jbe .hpr
    mov al, 99
.hpr:
    ret

; tg_vput - AX = a view: tg_vtmp into its record. CF=1 if that CHANGED it.
; Preserves every register.
tg_vput:
    push ax
    push cx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov cl, TI_C_SIZE
    mul cl
    add ax, ti_cards
    mov di, ax
    mov si, tg_vtmp
    mov cx, TI_C_SIZE
    push si
    push di
    repe cmpsb
    pop di
    pop si
    je .same
    mov cx, TI_C_SIZE
    rep movsb
    stc
    jmp short .out
.same:
    clc
.out:
    pop es
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_vtmp_card - AL = a card (or TR_EMPTY) -> tg_vtmp = the record a HAND shows
; for it: its costs, both blocks' pairs, its HP and POWER, name and art.
; Preserves every register.
; -----------------------------------------------------------------------------
tg_vtmp_card:
    push ax
    push bx
    push cx
    push di
    push es
    push ds
    pop es
    cld
    push ax
    mov di, tg_vtmp
    mov cx, TI_C_SIZE
    xor al, al
    rep stosb
    pop ax
    mov [tg_vtmp + TI_C_CARD], al
    mov byte [tg_vtmp + TI_C_ART], 0FFh
    mov word [tg_vtmp + TI_C_NAME], ti_s_none
    cmp al, TR_EMPTY
    je .out
    mov bl, al
    xor bh, bh
    mov cl, [ti_cardart + bx]
    mov [tg_vtmp + TI_C_ART], cl
    shl bx, 1
    mov cx, [ti_cardname + bx]
    mov [tg_vtmp + TI_C_NAME], cx
    call tr_crec
    mov al, [bx + TI_CR_COSTG]
    mov [tg_vtmp + TI_C_COST], al
    mov al, [bx + TI_CR_COSTS]
    mov [tg_vtmp + TI_C_SOUL], al
    mov al, [bx + TI_CR_POWER]
    mov [tg_vtmp + TI_C_PWR], al
    cmp byte [bx + TI_CR_KIND], TI_KIND_ORDER
    je .hp                          ; an ORDER has no body: no HP, no power
    mov al, [bx + TI_CR_FRONT + TI_B_HP]
    mov [tg_vtmp + TI_C_HP], al
.hp:
    push bx
    add bx, TI_CR_FRONT
    call tg_blkst
    mov di, tg_vtmp + TI_C_FI1
    call tg_pick
    pop bx
    add bx, TI_CR_REAR
    call tg_blkst
    mov di, tg_vtmp + TI_C_RI1
    call tg_pick
.out:
    pop es
    pop di
    pop cx
    pop bx
    pop ax
    ret

; tg_vtmp_live - SI = an occupied cell, AH = its column: tg_vtmp's pairs and
; HP become what it has THERE - its live block, its permanent ABSOLVE gains,
; this round's orders - and its stance. Preserves every register.
tg_vtmp_live:
    push ax
    push bx
    push di
    call tr_blk
    call tg_blkst
    mov al, [si + CE_BM]
    add al, [si + CE_OM]
    add [tg_st], al
    mov al, [si + CE_BR]
    add al, [si + CE_OR]
    add [tg_st + 1], al
    mov al, [si + CE_OS]
    add [tg_st + 2], al
    mov al, [si + CE_OH]
    add [tg_st + 3], al
    mov al, [si + CE_OG]
    add [tg_st + 4], al
    mov di, tg_vtmp + TI_C_FI1      ; the same pair in both slots: a character
    call tg_pick                    ; on the board has ONE position
    mov di, tg_vtmp + TI_C_RI1
    call tg_pick
    mov al, [si + CE_HP]
    mov [tg_vtmp + TI_C_HP], al
    mov al, [si + CE_INST]
    mov [tg_vtmp + TI_C_INST], al
    xor al, al
    cmp byte [tg_st + 1], 0         ; a SHOOTER has a stance to show
    je .st
    mov al, TI_CF_RANGED
    cmp byte [si + CE_ST], 0
    je .st
    or al, TI_CF_SNIPE
.st:
    mov [tg_vtmp + TI_C_FLAGS], al
    pop di
    pop bx
    pop ax
    ret

; tg_blkst - BX = a block -> tg_st = its melee, ranged, shield, heal, gold, in
; the order a card shows them. Preserves every register.
tg_blkst:
    push ax
    mov al, [bx + TI_B_M]
    mov [tg_st], al
    mov al, [bx + TI_B_R]
    mov [tg_st + 1], al
    mov al, [bx + TI_B_S]
    mov [tg_st + 2], al
    mov al, [bx + TI_B_H]
    mov [tg_st + 3], al
    mov al, [bx + TI_B_G]
    mov [tg_st + 4], al
    pop ax
    ret

; tg_pick - DI -> two (icon, value) pairs: the first two of tg_st that are not
; zero, and a zero icon where there is no second (it draws as nothing).
; Preserves every register.
tg_pick:
    push ax
    push bx
    push cx
    push di
    mov word [di], 0
    mov word [di + 2], 0
    xor bx, bx
    mov cx, 2
.s:
    cmp bx, 5
    jae .out
    mov al, [tg_st + bx]
    or al, al
    jz .n
    mov ah, al
    mov al, [tg_icon + bx]
    mov [di], ax
    add di, 2
    dec cx
    jz .out
.n:
    inc bx
    jmp short .s
.out:
    pop di
    pop cx
    pop bx
    pop ax
    ret

tg_icon:    db TI_IC_MELEE, TI_IC_BOW, TI_IC_SHIELD, TI_IC_STAR, TI_IC_GOLD

; -----------------------------------------------------------------------------
; tg_abil - DI -> the keywords of view record SI's card, written as `NAME n`
; with two spaces between; DI past them. For a hand card the block is the one
; the FRONT/REAR toggle names, for a board cell its column's. Preserves every
; register bar DI.
; -----------------------------------------------------------------------------
tg_abil:
    push ax
    push bx
    push cx
    push si
    mov al, [si + TI_C_CARD]
    cmp al, TR_EMPTY
    je .out
    mov ah, [si + TI_C_COL]
    call tr_crec
    add bx, TI_CR_FRONT
    cmp byte [bx - TI_CR_FRONT + TI_CR_KIND], TI_KIND_ORDER
    je .blk                         ; an order's effect is its one block
    or ah, ah
    jz .blk
    add bx, TI_BLK
.blk:
    lea si, [bx + TI_B_KW]
    mov cx, 3
    mov byte [tg_kwn], 0            ; nothing written yet
.k:
    lodsb
    or al, al
    jz .n
    cmp byte [tg_kwn], 0
    je .first
    push ax
    mov al, ' '
    stosb
    stosb
    pop ax
.first:
    mov byte [tg_kwn], 1
    push ax
    push si
    mov bl, al
    and bl, 31
    xor bh, bh
    shl bx, 1
    mov si, [ti_kwname + bx]
    call ti_poke
    pop si
    pop ax
    push cx
    mov cl, 5
    shr al, cl
    pop cx
    or al, al                       ; ...and its number, where it has one
    jz .n
    push ax
    mov al, ' '
    stosb
    pop ax
    call ti_u8
.n:
    loop .k
    cmp byte [tg_kwn], 0
    jne .out
    mov si, ti_s_noabil
    call ti_poke
.out:
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_play - PLAY hand slot AX into the column the FRONT/REAR toggle names
; out: CF=0 and AX = the BOARD cell it stands in; CF=1 refused, nothing moved
; Preserves every register bar AX.
;
; THE ENGINE DECIDES, the interface asks. The action goes on the end of the
; plan and the plan is re-applied; an action the engine refused (no gold, a
; full column) comes straight back off. So a refusal here is the rules' and
; there is no second copy of them to disagree.
; -----------------------------------------------------------------------------
tg_play:
    push bx
    push cx
    push dx
    push si
    push di
    mov dx, ax                      ; DL = the slot
    cmp byte [tg_ph], TG_PH_PLAN
    jne .no
    mov al, [tg_side]
    call tg_frzside
    cmp dl, [di + SD_NHAND]
    jae .no
    mov bl, dl
    xor bh, bh
    mov dh, [bx + di + SD_HAND]     ; DH = the card
    mov ah, 0                       ; FRONT is the engine's column 0
    cmp word [ti_row], TI_ROW_FRONT
    je .col
    mov ah, 1
.col:
    mov al, [tg_side]               ; WHERE: the topmost empty cell of that
    xor cl, cl                      ; column, as THIS plan leaves it
.lane:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .have
    inc cl
    cmp cl, TR_LANES
    jb .lane
    jmp short .no                   ; full: the engine would say so too
.have:
    mov [tg_plane], cl
    mov [tg_pcol], ah
    mov bl, TR_A_PLAY
    mov bh, dh
    mov cl, ah
    mov ch, dl
    call tg_push                    ; (op, card, column) and the slot it came
    jc .no                          ; from
    call tg_replay
    cmp word [tr_err], 0
    je .ok
    call tg_pop                     ; the engine refused it
    call tg_replay
    jmp short .no
.ok:
    mov al, [tg_side]               ; the board cell it stands in
    shl al, 1
    add al, [tg_pcol]
    mov bl, al
    xor bh, bh
    mov al, [tg_bcol + bx]
    mov cl, TI_ROWS
    mul cl
    add al, [tg_plane]
    xor ah, ah
    clc
    jmp short .out
.no:
    stc
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; tg_push - BL = op, BH = a, CL = b, CH = the hand slot (or 0FFh): onto the
; planner's plan. CF=1 when it is full. Preserves every register.
tg_push:
    push ax
    push bx
    push dx
    push di
    mov dx, bx
    mov al, [tg_side]
    call tg_planp
    mov al, [bx]
    cmp al, TG_MAXACT
    jae .full
    inc byte [bx]
    xor ah, ah
    mov di, tg_pslot0               ; the slot, beside it
    cmp byte [tg_side], 0
    je .ps
    mov di, tg_pslot1
.ps:
    add di, ax
    mov [di], ch
    mov di, ax
    shl di, 1
    add di, ax
    add di, bx
    mov [di + 1], dx                ; op, a
    mov [di + 3], cl                ; b
    clc
    jmp short .out
.full:
    stc
.out:
    pop di
    pop dx
    pop bx
    pop ax
    ret

; tg_pop - the planner's last action off. Preserves every register.
tg_pop:
    push ax
    push bx
    mov al, [tg_side]
    call tg_planp
    cmp byte [bx], 0
    je .out
    dec byte [bx]
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_undo - SPEC.md 97.7's `U` and the UNDO button: the planner's LAST action
; taken back, and the board redrawn where it moved. A window callback, the gfx
; lock held. Preserves every register.
; -----------------------------------------------------------------------------
tg_undo:
    push ax
    push bx
    cmp byte [tg_ph], TG_PH_PLAN
    jne .out
    cmp byte [ti_rv], 0             ; a reveal owns a cell and the hand
    jne .out
    mov al, [tg_side]
    call tg_planp
    cmp byte [bx], 0
    je .out
    mov bl, [ti_played]
    push bx
    call tg_pop
    call tg_replay
    pop bx
    call tg_sync                    ; the cells that moved
    xor bl, [ti_played]             ; ...the hand slots that did
    xor ax, ax
.h:
    cmp ax, [ti_cardn]
    jae .hud
    shr bl, 1
    jnc .hn
    call ti_card_draw
.hn:
    inc ax
    jmp short .h
.hud:
    call ti_res_all
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_sync - bring the board to the views: every cell whose ART moved is
; composed again and put down whole, and every cell whose record moved has its
; numbers redrawn. The gfx lock held. Preserves every register.
; -----------------------------------------------------------------------------
tg_sync:
    push ax
    push bx
    push cx
    push word [ti_ci]
    xor cx, cx
.c:
    cmp cx, TI_CELLS
    jae .out
    mov [ti_ci], cx
    mov ax, cx
    call ti_ck_cell
    mov bx, cx
    mov al, [ti_ck]
    cmp al, [tg_cart + bx]
    je .art
    mov word [ti_cfbeg], 0          ; ALL EIGHT FRAMES: a character that is
    mov word [ti_cfend], 2 * TI_POSES ; drawn now may swing next
    call ti_cell_build
    mov byte [bx + ti_clock], 0
    mov byte [ti_dok], 0            ; whole, not a transition
    mov ax, cx
    call ti_feature
    mov byte [tg_vdirty + bx], 1
.art:
    cmp byte [tg_vdirty + bx], 0
    je .n
    mov byte [tg_vdirty + bx], 0
    call ti_cell_xy
    call ti_cellnum
.n:
    inc cx
    jmp short .c
.out:
    pop word [ti_ci]
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_commit - the COMMIT button. P1's seals their plan and hands the machine
; over; P2's resolves the round. A window callback, the gfx lock held.
; Preserves every register.
; -----------------------------------------------------------------------------
tg_commit:
    push ax
    push bx
    push si
    cmp byte [tg_ph], TG_PH_PLAN
    jne .out
    cmp byte [ti_rv], 0
    jne .out
    call ti_rv_atk_flush
    cmp byte [tg_side], 0
    jne .resolve
    mov byte [tg_side], 1           ; --- P1 is done: nothing of their plan
    mov word [tg_msg1], ti_s_sealed ; is left on the glass for P2 to read
    mov word [tg_msg2], ti_s_pass2
    jmp short .pass
.resolve:
    call tg_load                    ; --- BOTH PLANS, on the frozen board, and
    mov word [tr_err], 0            ; the round fought
    xor al, al
    call tg_planp
    mov si, bx
    call tr_apply
    mov al, 1
    call tg_planp
    mov si, bx
    call tr_apply
    call tr_resolve
    mov byte [tg_plan0], 0
    mov byte [tg_plan1], 0
    mov byte [tg_side], 0
    call tg_result                  ; tg_msg1 = what happened
    cmp byte [tr_result], 0
    jne .over
    call tr_upkeep                  ; the next round's frozen board
    call tg_save
    mov word [tg_msg2], ti_s_pass1
.pass:
    mov byte [tg_ph], TG_PH_PASS
    call tg_replay
    call tg_screen
    jmp short .out
.over:
    call tg_save
    mov byte [tg_ph], TG_PH_OVER
    mov word [tg_msg2], ti_s_again
    call tg_views
    call tg_screen
.out:
    pop si
    pop bx
    pop ax
    ret

; tg_result - tg_msg1 = the round's outcome, as a line in tg_buf1 or the
; match's end. Preserves every register.
tg_result:
    push ax
    push bx
    push si
    push di
    push es
    push ds
    pop es
    cld
    xor al, al
    call tr_side
    call tg_views.hp
    mov bl, al
    mov al, 1
    call tr_side
    call tg_views.hp
    mov bh, al
    mov di, tg_buf1
    mov si, ti_s_round
    call ti_poke
    mov al, [tr_round]
    call ti_u8
    mov si, ti_s_p1hp
    call ti_poke
    mov al, bl
    call ti_u8
    mov si, ti_s_p2hp
    call ti_poke
    mov al, bh
    call ti_u8
    mov byte [di], 0
    mov word [tg_msg1], tg_buf1
    mov al, [tr_result]
    or al, al
    jz .out
    mov si, ti_s_p1wins
    cmp al, TR_RES_A
    je .res
    mov si, ti_s_p2wins
    cmp al, TR_RES_B
    je .res
    mov si, ti_s_draw
    cmp al, TR_RES_DRAW
    je .res
    mov si, ti_s_stale
.res:
    mov [tg_msg1], si
.out:
    pop es
    pop di
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_screen - the PASS screen (or the match's end): the whole content black,
; and two lines. NOTHING OF EITHER PLAN IS ON IT, which is the point: it is
; what stands between one planner and the next (TITHE-PLAN 6.3.1).
; Preserves every register.
; -----------------------------------------------------------------------------
tg_screen:
    push ax
    push bx
    push cx
    push dx
    push si
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [ti_ox]
    mov bx, [ti_oy]
    mov cx, ax
    add cx, [ti_cw_box]
    dec cx
    mov dx, bx
    add dx, [ti_ch_box]
    dec dx
    call OSAPI_GFX_FILL
    mov dx, [ti_ch_box]
    shr dx, 1
    sub dx, 12
    add dx, [ti_oy]
    mov si, [tg_msg1]
    call .line
    add dx, 16
    mov si, [tg_msg2]
    call .line
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.line:                              ; SI centred at row DX
    push si
    xor cx, cx
.len:
    cmp byte [si], 0
    je .have
    inc si
    inc cx
    jmp short .len
.have:
    pop si
    shl cx, 1
    shl cx, 1
    shl cx, 1
    neg cx
    add cx, [ti_cw_box]
    sar cx, 1
    jns .x
    xor cx, cx
.x:
    add cx, [ti_ox]
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN
    ret

; -----------------------------------------------------------------------------
; tg_resume - the pass screen was clicked away: the next planner's board, from
; nothing. A window callback, the gfx lock held. Preserves every register.
; -----------------------------------------------------------------------------
tg_resume:
    push ax
    cmp byte [tg_ph], TG_PH_PLAN
    je .out
    cmp byte [tg_ph], TG_PH_OVER
    jne .next
    call tg_new
    jmp short .go
.next:
    mov byte [tg_ph], TG_PH_PLAN
    call tg_replay
.go:
    call tg_redraw
.out:
    pop ax
    ret

; tg_redraw - a new planner's window from nothing: the hand's units, every
; cell whose art moved, and the whole board. Preserves every register.
tg_redraw:
    push ax
    mov word [ti_hover], -1
    mov word [ti_hovc], -1
    call ti_units_build             ; the hand is another player's, or new
    call tg_cells                   ; ...and so may every cell be
    call ti_ground
    call ti_board
    call ti_all
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_fill - THE TESTS' FULL BOARD, asked for by a byte (tg_fillq) the worker
; services the way it services ti_rpq: a key is a player's.
; Preserves every register.
;
; THE RENDERER'S ROWS MEASURE A FULL BOARD - twenty figures, every art once -
; and a real match starts EMPTY, so they would be measuring nothing. This is
; the position they measure: each of the twenty cells holds the first card to
; wear art N (ti_artcard, generated), and each hand is seven of them. It is a
; legal engine state - HP and shields off the cards' own blocks, instances
; unique, both pools full - so the numbers and the status line read as the
; game's. [tg_fillq] = 2 leaves P1's FRONT column empty, for a row that plays.
; -----------------------------------------------------------------------------
tg_fill:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call tg_load
    xor cx, cx
.c:
    cmp cx, TI_CELLS
    jae .hand
    call tg_ecell                   ; SI = the cell, AH = its column
    call tr_clearcell
    cmp byte [tg_fillq], 2          ; 2: P1's FRONT column left empty, for a
    jne .put                        ; row that plays into it (titherv)
    cmp cx, TI_ROWS
    jb .put
    cmp cx, 2 * TI_ROWS
    jb .next
.put:
    mov bx, cx
    mov al, [ti_artcard + bx]
    mov [si + CE_CARD], al
    mov dl, cl
    add dl, 100                     ; above anything a plan will number
    mov [si + CE_INST], dl
    call tr_blk
    mov al, [bx + TI_B_HP]
    mov [si + CE_HP], al
    mov al, [bx + TI_B_S]
    mov [si + CE_SH], al
.next:
    inc cx
    jmp short .c
.hand:
    xor al, al
    call tr_side
    mov si, ti_artcard
    call .deal
    mov al, 1
    call tr_side
    mov si, ti_artcard + TI_HAND
    call .deal
    call tg_save
    mov byte [tg_plan0], 0
    mov byte [tg_plan1], 0
    mov byte [tg_side], 0
    mov byte [tg_ph], TG_PH_PLAN
    call tg_replay
    call tg_redraw
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.deal:                              ; DI = a side, SI -> seven cards, and the
    mov byte [di + SD_NHAND], TI_HAND ; pools to play any of them
    mov byte [di + SD_GOLD], TR_CAP
    mov byte [di + SD_SOULS], TR_CAP
    xor bx, bx
.d:
    mov al, [si + bx]
    push bx
    add bx, di
    mov [bx + SD_HAND], al
    pop bx
    inc bx
    cmp bx, TI_HAND
    jb .d
    ret

; tg_cells - every cell whose art moved, composed again (drawn by the caller)
tg_cells:
    push bx
    push cx
    push word [ti_ci]
    xor cx, cx
.c:
    cmp cx, TI_CELLS
    jae .out
    mov [ti_ci], cx
    mov ax, cx
    call ti_ck_cell
    mov bx, cx
    mov al, [ti_ck]
    cmp al, [tg_cart + bx]
    je .n
    mov word [ti_cfbeg], 0
    mov word [ti_cfend], 2 * TI_POSES
    call ti_cell_build
    mov byte [bx + ti_clock], 0
.n:
    mov byte [tg_vdirty + bx], 0
    inc cx
    jmp short .c
.out:
    pop word [ti_ci]
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tg_btn_hit - (CX, DX) -> AL = 1 on UNDO, 2 on COMMIT, 0 on neither
; Preserves every register bar AX.
; -----------------------------------------------------------------------------
tg_btn_hit:
    push bx
    push dx
    xor al, al
    cmp byte [ti_horiz], 0
    je .vert
    cmp cx, [ti_cmx]                ; the fullscreen column: UNDO over COMMIT
    jb .out
    mov bx, [ti_cmx]
    add bx, [ti_cmw]
    cmp cx, bx
    jae .out
    mov bx, [ti_hy]
    add bx, TI_HLIFT
    cmp dx, bx
    jb .out
    add bx, [ti_cardh]
    cmp dx, bx
    jae .out
    mov al, 1
    cmp dx, [ti_cmsplit]
    jb .out
    mov al, 2
    jmp short .out
.vert:
    push cx                         ; the strip's row under the hand
    mov ax, [ti_cardn]
    call ti_card_pos
    add bx, [ti_cgap]
    pop cx
    xor al, al
    cmp dx, bx
    jb .out
    add bx, [ti_cardh]
    cmp dx, bx
    jae .out
    mov bx, [ti_cardx]
    cmp cx, bx
    jb .out
    add bx, [ti_cardw]
    cmp cx, bx
    jae .out
    mov al, 1
    mov bx, [ti_cardx]
    add bx, [ti_undow]
    cmp cx, bx
    jb .out
    mov al, 2
.out:
    pop dx
    pop bx
    ret

TG_BUFW     equ 40

ti_s_p1plans: db '   P1 PLANS', 0
ti_s_p2plans: db '   P2 PLANS', 0
ti_s_none:  db 0
ti_s_noabil: db 'NO SPECIAL ABILITY', 0
ti_s_sealed: db 'PLAYER 1 HAS COMMITTED', 0
ti_s_pass2: db 'PASS TO PLAYER 2 - CLICK TO PLAN', 0
ti_s_pass1: db 'PASS TO PLAYER 1 - CLICK TO PLAN', 0
ti_s_again: db 'CLICK FOR A NEW MATCH', 0
ti_s_p1hp:  db '   P1 HP ', 0
ti_s_p2hp:  db '   P2 HP ', 0
ti_s_p1wins: db 'PLAYER 1 WINS', 0
ti_s_p2wins: db 'PLAYER 2 WINS', 0
ti_s_draw:  db 'BOTH FALL - A DRAW', 0
ti_s_stale: db 'SIXTY ROUNDS - A STALEMATE', 0

tg_ph:      db 0                    ; TG_PH_*
tg_fillq:   db 0                    ; the tests' full board, asked for
tg_side:    db 0                    ; who is planning
tg_rnd:     db 0
tg_ecol:    db 0
tg_kwn:     db 0
tg_plane:   db 0
tg_pcol:    db 0
tg_phs:     dw ti_s_p1plans         ; the HUD's phase words
tg_msg1:    dw ti_s_none
tg_msg2:    dw ti_s_none
tg_st:      times 5 db 0
tg_vtmp:    times TI_C_SIZE db 0
tg_cart:    times TI_CELLS db 0FEh  ; the art each cell's poses were built with
tg_vdirty:  times TI_CELLS db 0
tg_plan0:   times TG_PLANSZ db 0
tg_plan1:   times TG_PLANSZ db 0
tg_pslot0:  times TG_MAXACT db 0    ; the hand slot each action came from
tg_pslot1:  times TG_MAXACT db 0
tg_buf1:    times TG_BUFW db 0
tg_frz:     times 2 * TR_SIDESZ + TR_CELLS * TR_CELLSZ db 0
ti_cards:   times TI_NVIEW * TI_C_SIZE db 0
