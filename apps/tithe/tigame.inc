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

; A PLAN BLOCK is tr_apply's plan and, beside it, what the interface needs to
; edit one: the hand slot each action spent, and the character an ORDER or a
; STANCE acts on - named as the PLAY in this plan that brought it (TG_P_REF),
; or as its instance when it was on the frozen board (TG_P_TGT). An instance
; alone is not enough: a play's instance is its place in the plan, so taking
; out an earlier play renumbers every later one.
TG_P_SLOT   equ TG_PLANSZ
TG_P_REF    equ TG_P_SLOT + TG_MAXACT
TG_P_TGT    equ TG_P_REF + TG_MAXACT
TG_PBSZ     equ TG_P_TGT + TG_MAXACT
TI_NVIEW    equ TI_HAND + TI_CELLS

TG_PH_PLAN  equ 0                   ; a player is planning
TG_PH_PASS  equ 1                   ; the pass-the-machine screen
TG_PH_OVER  equ 2                   ; the match is decided
TG_PH_RES   equ 3                   ; the round is being fought, on the glass

TG_SCRBAND  equ 32                  ; rows of the pass screen's fill a step
TG_LOGN     equ 64                  ; the round's log: lines kept - the WHOLE
                                    ; round, for the viewer (97.12.10.6)...
TG_LOGW     equ 18                  ; ...and a line's bytes, its NUL included

; -----------------------------------------------------------------------------
; tg_new - a new match: two starter decks, fresh seeds, the first upkeep, and
; P1 to plan. Preserves every register.
; -----------------------------------------------------------------------------
tg_new:
    push ax
    push bx
    push cx
    call OSAPI_GET_TICKS            ; THE SEEDS ARE THE CLOCK'S: a match is a
    mov [tr_decka + 4], ax          ; pure function of its two decks and two
    mov bx, ax                      ; seeds (TITHE-PLAN 14.1), and a hot-seat
    mov cl, 5                       ; match has no reason to be the same one
    rol bx, cl                      ; twice
    xor bx, 0A5C3h
    mov [tr_deckb + 4], bx
    call tg_deal
    pop cx
    pop bx
    pop ax
    ret

; tg_deal - the match the seeds in tr_decka/tr_deckb say, between the two
; starter decks: setup, the first upkeep, and P1 to plan. Preserves every
; register.
tg_deal:
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
    call tr_setup
    call tg_snap_pools              ; (the income is counted from here)
    call tg_upk
    call tg_save
    mov byte [tg_plan0], 0
    mov byte [tg_plan1], 0
    mov byte [tg_side], 0
    mov byte [tg_ph], TG_PH_PLAN
    mov byte [tg_rnd], 0
    call tg_idle
    call tg_replay
    call tg_income_set              ; P1's first turn says what it got
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
;
; ONE ACTION AT A TIME, and the plan is REWRITTEN as it goes (TITHE-PLAN
; 5.0.2): an action the engine refuses now is dropped, and so is one whose
; subject went with it - an ORDER on a character whose play was taken out, a
; STANCE on one no longer standing. [tg_skip] names an entry to take out on
; the way. Every other action is re-resolved against the board as the plan
; leaves it - an ORDER's instance, a STANCE's cell - because a removal ahead
; of it can move both, and what goes back into the plan is exactly what the
; commit will hand the engine.
; -----------------------------------------------------------------------------
tg_replay:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call tg_load
    mov word [tr_err], 0
    mov al, [tg_side]
    mov [tr_ps], al
    call tr_side
    mov [tg_sdi], di
    call tg_planp
    xor cx, cx                      ; CL = the entry read, CH = the one written
.e:
    cmp cl, [bx]
    jb .go
    jmp .done
.go:
    mov dl, cl
    xor dh, dh
    mov si, dx                      ; SI = i
    mov byte [tg_map + si], 0FFh
    cmp cl, [tg_skip]
    jne .take
    jmp .next
.take:
    mov di, si                      ; the action, into the mini-plan
    shl di, 1
    add di, si
    add di, bx
    mov ax, [di + 1]
    mov [tg_mini + 1], ax
    mov al, [di + 3]
    mov [tg_mini + 3], al
    mov al, [bx + si + TG_P_REF]    ; ITS SUBJECT: the play that brought it,
    mov [tg_nref], al               ; renumbered, or a frozen instance
    cmp al, 0FFh
    je .frz
    push bx
    mov bl, al
    xor bh, bh
    mov al, [tg_map + bx]
    mov [tg_nref], al
    cmp al, 0FFh
    je .orph
    mov bl, al
    mov al, [tg_pinst + bx]
    pop bx
    jmp short .have
.orph:
    pop bx                          ; its play is gone, and so is it
    jmp .next
.frz:
    mov al, [bx + si + TG_P_TGT]
.have:
    mov ah, [tg_mini + 1]
    cmp ah, TR_A_ORDER
    jne .nord
    mov [tg_mini + 3], al           ; the order's instance
.nord:
    cmp ah, TR_A_STANCE
    jne .nst
    call tg_findinst                ; ...the stance's cell
    jnc .stc
    jmp .next
.stc:
    mov [tg_mini + 2], al
.nst:
    mov di, [tg_sdi]
    mov al, [di + SD_INST]          ; what a PLAY will be numbered
    mov [tg_ninst], al
    push word [tr_err]
    push si
    mov al, [tg_side]
    mov si, tg_mini
    mov byte [si], 1
    call tr_apply
    pop si
    pop ax
    cmp ax, [tr_err]
    je .kept
    mov [tr_err], ax                ; refused: dropped
    jmp short .next
.kept:
    mov dl, ch
    xor dh, dh
    mov di, dx                      ; DI = k
    mov [tg_map + si], dl
    mov al, [tg_ninst]
    mov [tg_pinst + di], al
    mov al, [bx + si + TG_P_SLOT]
    mov [bx + di + TG_P_SLOT], al
    mov al, [bx + si + TG_P_TGT]
    mov [bx + di + TG_P_TGT], al
    mov al, [tg_nref]
    mov [bx + di + TG_P_REF], al
    mov ax, di
    shl di, 1
    add di, ax
    add di, bx
    mov ax, [tg_mini + 1]
    mov [di + 1], ax
    mov al, [tg_mini + 3]
    mov [di + 3], al
    inc ch
.next:
    inc cl
    jmp .e
.done:
    mov [bx], ch
    mov byte [tg_skip], 0FFh
    call tg_views
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tg_findinst - AL = an instance -> AL = the planner's cell holding it
; (column x 5 + lane, the engine's own naming), CF=1 when none does.
; Preserves every other register.
tg_findinst:
    push bx
    push cx
    push si
    mov bl, al
    or bl, bl
    jz .no
    mov al, [tg_side]
    xor ah, ah
.c:
    xor cl, cl
.l:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .n
    cmp [si + CE_INST], bl
    je .yes
.n:
    inc cl
    cmp cl, TR_LANES
    jb .l
    inc ah
    cmp ah, 2
    jb .c
.no:
    stc
    jmp short .out
.yes:
    mov al, ah
    mov ch, TR_LANES
    mul ch
    add al, cl
    clc
.out:
    pop si
    pop cx
    pop bx
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
    ; the plan (its TG_P_SLOT column says which slot each one spent)
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
    lea di, [bx + TG_P_SLOT]
    pop bx
    xor ch, ch
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
    call tg_greys                   ; ...and what the planner cannot pay for
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

; -----------------------------------------------------------------------------
; tg_greys - WHAT THE PLANNER CANNOT DO (SPEC.md 97.12.10.3): each hand slot's
; shortfall in gold and souls against the pool the plan leaves - a slot whose
; shortfall MOVED is owed a redraw (ti_gchg) - and which of the planner's two
; columns are FULL (ti_colfull; ti_hudq when that moved). Nothing is drawn.
; Preserves every register.
; -----------------------------------------------------------------------------
tg_greys:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, [tg_side]
    call tr_side                    ; DI = the planner, as the plan leaves them
    xor bx, bx
.s:
    cmp bx, TI_HAND
    jae .cols
    xor dx, dx                      ; DL = gold short, DH = souls short
    mov ax, bx
    mov cl, TI_C_SIZE
    mul cl
    mov si, ax
    cmp byte [ti_cards + si + TI_C_CARD], TR_EMPTY
    je .put
    mov al, [ti_cards + si + TI_C_COST]
    sub al, [di + SD_GOLD]
    jbe .g0
    mov dl, al
.g0:
    mov al, [ti_cards + si + TI_C_SOUL]
    sub al, [di + SD_SOULS]
    jbe .put
    mov dh, al
.put:
    cmp dl, [ti_shg + bx]
    jne .chg
    cmp dh, [ti_shs + bx]
    je .n
.chg:
    mov [ti_shg + bx], dl
    mov [ti_shs + bx], dh
    mov cl, bl
    mov al, 1
    shl al, cl
    or [ti_gchg], al
.n:
    inc bx
    jmp short .s
.cols:
    xor dl, dl                      ; DL = the full columns, a bit each
    xor ah, ah                      ; the engine's column 0 is FRONT
.col:
    mov al, [tg_side]
    xor cl, cl
.lane:
    call tr_cell
    cmp byte [si + CE_CARD], TR_EMPTY
    je .open
    inc cl
    cmp cl, TR_LANES
    jb .lane
    mov cl, ah                      ; every lane taken: FULL
    mov al, 1
    shl al, cl
    or dl, al
.open:
    inc ah
    cmp ah, 2
    jb .col
    cmp dl, [ti_colfull]
    je .out
    mov [ti_colfull], dl
    mov byte [ti_hudq], 1           ; ...the HUD's toggle says so (ti_owed)
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE UPKEEP, SAID (SPEC.md 97.12.10.5): what each player's pool gained since
; they last committed - the round's spoils and the upkeep's income together -
; and the card the upkeep drew, or discarded from a full hand.
; -----------------------------------------------------------------------------

; tg_snap_pools - each side's gold and souls as they stand: what the next
; turn's income is counted from. Preserves every register.
tg_snap_pools:
    push ax
    push bx
    push di
    xor bx, bx
.s:
    mov al, bl
    call tr_side
    mov al, [di + SD_GOLD]
    mov [tg_pg + bx], al
    mov al, [di + SD_SOULS]
    mov [tg_pso + bx], al
    inc bx
    cmp bx, 2
    jb .s
    pop di
    pop bx
    pop ax
    ret

; tg_upk - tr_upkeep, and what it DREW for each side: the card and the slot
; it went to (tg_drew, tg_newslot), or the card it discarded from a full hand
; (tg_disc). Preserves every register.
tg_upk:
    push ax
    push bx
    push cx
    push di
    xor bx, bx
.b:
    mov al, bl
    call tr_side
    mov al, [di + SD_NHAND]
    mov [tg_nh0 + bx], al
    inc bx
    cmp bx, 2
    jb .b
    call tr_upkeep
    xor bx, bx
.a:
    mov al, bl
    call tr_side
    shl bx, 1
    mov word [tg_newslot + bx], 0FFFFh
    shr bx, 1
    mov byte [tg_drew + bx], TR_EMPTY
    mov byte [tg_disc + bx], TR_EMPTY
    mov cl, [di + SD_NHAND]
    cmp cl, [tg_nh0 + bx]
    jbe .full
    dec cl                          ; THE HAND GREW: the last slot is new
    xor ch, ch
    push bx
    mov bx, cx
    mov al, [di + SD_HAND + bx]
    pop bx
    mov [tg_drew + bx], al
    shl bx, 1
    mov [tg_newslot + bx], cx
    shr bx, 1
    jmp short .n
.full:
    cmp byte [tg_nh0 + bx], TR_HAND ; ...or it was FULL and the card went to
    jb .n                           ; the discard's end (a dry draw is neither)
    mov cl, [di + SD_NDISC]
    or cl, cl
    jz .n
    dec cl
    xor ch, ch
    push bx
    mov bx, cx
    mov al, [di + SD_DISC + bx]
    pop bx
    mov [tg_disc + bx], al
.n:
    inc bx
    cmp bx, 2
    jb .a
    pop di
    pop cx
    pop bx
    pop ax
    ret

; tg_income_set - the planner's upkeep as the status line's note: `INCOME +4G
; +1S  DREW PIKEMAN`, or `HAND FULL - PIKEMAN DISCARDED`. It draws nothing.
; Preserves every register.
tg_income_set:
    push ax
    push bx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov bl, [tg_side]
    xor bh, bh
    mov al, bl
    call tr_side                    ; (DI is reused below: banked in SI)
    mov si, di
    mov di, tg_incbuf
    push si
    mov si, ti_s_income
    call ti_poke
    pop si
    mov al, [si + SD_GOLD]
    sub al, [tg_pg + bx]
    call tg_sgn
    mov al, 'G'
    stosb
    mov al, [si + SD_SOULS]
    sub al, [tg_pso + bx]
    jz .drew
    push ax
    mov al, ' '
    stosb
    pop ax
    call tg_sgn
    mov al, 'S'
    stosb
.drew:
    mov al, [tg_drew + bx]
    cmp al, TR_EMPTY
    je .disc
    mov si, ti_s_drew
    push ax                         ; (ti_poke leaves AL at the NUL)
    call ti_poke
    pop ax
    call .name
    jmp short .end
.disc:
    mov al, [tg_disc + bx]
    cmp al, TR_EMPTY
    je .end
    mov si, ti_s_hfull
    push ax
    call ti_poke
    pop ax
    call .name
    mov si, ti_s_discd
    call ti_poke
.end:
    mov byte [di], 0
    mov word [tg_prompt], tg_incbuf
    call tg_note_at
    pop es
    pop di
    pop si
    pop bx
    pop ax
    ret
.name:                              ; AL = a card: its name at DI
    push bx
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov si, [ti_cardname + bx]
    call ti_poke
    pop bx
    ret

; tg_sgn - AL signed as `+n` or `-n` at DI. Preserves every register bar DI.
tg_sgn:
    push ax
    mov ah, '+'
    or al, al
    jns .p
    mov ah, '-'
    neg al
.p:
    xchg al, ah
    stosb
    mov al, ah
    call tg_num
    pop ax
    ret

; tg_new_seen - the NEW card is hovered: it is seen, and its corner goes
; (ti_frame, before the hovered card is drawn). Preserves every register.
tg_new_seen:
    push ax
    push bx
    mov bl, [tg_side]
    xor bh, bh
    shl bx, 1
    mov ax, [ti_hover]
    cmp ax, [tg_newslot + bx]
    jne .out
    mov word [tg_newslot + bx], 0FFFFh
.out:
    pop bx
    pop ax
    ret

; tg_note - SI = a sentence: the status line says it until the pointer moves
; (SPEC.md 97.12.10.3), the way a pending action's question is said. A window
; callback, the lock held. Preserves every register.
tg_note:
    mov [tg_prompt], si
    call tg_note_at
    jmp ti_hud_status

; tg_note_at - a note is up, with the pointer where the last frame read it
; (ti_hover_ck): only a MOVE takes it back, not the first hover a redraw
; finds under a pointer that has not moved. Preserves every register.
tg_note_at:
    push ax
    mov byte [ti_note], 1
    mov ax, [ti_mx]
    mov [tg_nx], ax
    mov ax, [ti_my]
    mov [tg_ny], ax
    pop ax
    ret

; tg_note_off - a note is taken back when the pointer moves (ti_frame).
; Preserves every register.
tg_note_off:
    cmp byte [ti_note], 0
    je .out
    push ax
    mov ax, [ti_mx]                 ; ...the pointer has to have MOVED
    cmp ax, [tg_nx]
    jne .off
    mov ax, [ti_my]
    cmp ax, [tg_ny]
.off:
    pop ax
    je .out
    mov byte [ti_note], 0
    mov byte [tg_cconf], 0          ; (a COMMIT's question goes with it)
    mov word [tg_prompt], 0
.out:
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
    mov ax, di                      ; A HAND CARD THAT CHANGED has a stale
    sub ax, ti_cards + TI_C_SIZE    ; bank (SPEC.md 97.4.12.1): the next
    mov cl, TI_C_SIZE               ; hover must not put the old card down
    div cl
    cmp al, TI_HAND
    jae .chg
    xor ah, ah
    mov si, ax
    mov byte [si + ti_cvalid], 0
.chg:
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
    cmp byte [bx + TI_CR_KIND], TI_KIND_ORDER
    jne .rear                       ; AN ORDER HAS NO POSITION: its one block,
    mov di, tg_vtmp + TI_C_RI1      ; the round's effect, is what it shows in
    call tg_pick                    ; either row, so FRONT/REAR changes nothing
    jmp short .out                  ; on it (SPEC.md 97.4.8.2) - REAR used to
.rear:                              ; show its empty rear block
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
    push si                         ; FULL: the engine would say so too, and
    mov si, ti_s_nfront             ; the player is told which (97.12.10.3)
    or ah, ah
    jz .nfull
    mov si, ti_s_nrear
.nfull:
    call tg_note
    pop si
    jmp short .no
.have:
    mov [tg_plane], cl
    mov [tg_pcol], ah
    mov bl, TR_A_PLAY
    mov bh, dh
    mov cl, ah
    mov ch, dl
    call tg_act                     ; (op, card, column) and the slot it came
    jnc .took                       ; from
    push si                         ; REFUSED: the pool is what refuses a play
    mov si, ti_s_ngold              ; into an open column
    push bx
    mov bl, dl
    xor bh, bh
    cmp byte [ti_shg + bx], 0
    jne .ncost0
    mov si, ti_s_nsoul
    cmp byte [ti_shs + bx], 0
    jne .ncost0
    mov si, ti_s_nplay              ; (the engine's, and not the pool's)
.ncost0:
    pop bx
    call tg_note
    pop si
    jmp short .no
.took:
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

; tg_act - BL = op, BH = a, CL = b, CH = the hand slot (or 0FFh), and the
; subject in [tg_nref]/[tg_ntgt]: onto the end of the planner's plan, and the
; plan applied again. CF=1 when the engine refused it, and then it is not in
; the plan - the replay dropped it. Preserves every register.
tg_act:
    push ax
    push bx
    push dx
    push di
    mov dx, bx
    mov al, [tg_side]
    call tg_planp
    mov al, [bx]
    cmp al, TG_MAXACT
    jae .no
    mov [tg_n0], al
    inc byte [bx]
    xor ah, ah
    mov di, ax
    mov [bx + di + TG_P_SLOT], ch
    mov al, [tg_nref]
    mov [bx + di + TG_P_REF], al
    mov al, [tg_ntgt]
    mov [bx + di + TG_P_TGT], al
    mov ax, di
    shl di, 1
    add di, ax
    add di, bx
    mov [di + 1], dx                ; op, a
    mov [di + 3], cl                ; b
    call tg_replay
    mov al, [bx]
    cmp al, [tg_n0]
    je .no
    clc
    jmp short .out
.no:
    stc
.out:
    mov byte [tg_nref], 0FFh
    mov byte [tg_ntgt], 0
    pop di
    pop dx
    pop bx
    pop ax
    ret

; tg_subject - board cell CX -> [tg_nref]/[tg_ntgt] name the character there
; the way a plan does (TG_P_REF, TG_P_TGT). CF=1 when the cell is not the
; planner's or nobody stands in it. Preserves every register.
tg_subject:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    call tg_ecell                   ; SI = the cell, AL = its side
    cmp al, [tg_side]
    jne .no
    cmp byte [si + CE_CARD], TR_EMPTY
    je .no
    mov dl, [si + CE_INST]
    mov byte [tg_nref], 0FFh
    mov [tg_ntgt], dl
    mov al, [tg_side]               ; ...brought by a PLAY in this plan? The
    call tg_planp                   ; instance column is only a play's own
    xor cx, cx
.p:
    cmp cl, [bx]
    jae .yes
    mov di, cx
    cmp [tg_pinst + di], dl
    jne .n
    mov si, cx
    shl si, 1
    add si, cx
    add si, bx
    cmp byte [si + 1], TR_A_PLAY
    jne .n
    mov [tg_nref], cl
    mov byte [tg_ntgt], 0
    jmp short .yes
.n:
    inc cx
    jmp short .p
.yes:
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
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_remove - AL = an entry of the planner's plan: taken out, the rest applied
; again - with anything it orphaned dropped - and the board redrawn where it
; moved (TITHE-PLAN 5.0.2). A window callback, the gfx lock held. Preserves
; every register.
; -----------------------------------------------------------------------------
tg_remove:
    push ax
    push bx
    cmp byte [tg_ph], TG_PH_PLAN
    jne .out
    cmp byte [ti_rv], 0             ; a reveal owns a cell and the hand
    jne .out
    mov [tg_skip], al
    mov bl, [ti_played]
    push bx
    call tg_replay
    pop bx
    call tg_edited
.out:
    pop bx
    pop ax
    ret

; tg_edited - BL = the played bits before an edit: the board, the hand (or the
; plan list) and the HUD brought to the plan as it is now. Preserves every
; register.
tg_edited:
    push ax
    push bx
    call tg_sync                    ; the cells that moved
    cmp byte [tg_list], 0
    je .hand
    call tg_list_draw
    jmp short .hud
.hand:
    xor bl, [ti_played]             ; ...the hand slots that did, and the ones
    or bl, [ti_gchg]                ; whose shortfall moved (97.12.10.3)
    mov byte [ti_gchg], 0
    xor ax, ax
.h:
    cmp ax, [ti_cardn]
    jae .hud
    shr bl, 1
    jnc .hn
    call ti_card_fast               ; (from its bank: an edit moves a card's
.hn:                                ; slot or its grey, and not the card)
    inc ax
    jmp short .h
.hud:
    call ti_res_all
    pop bx
    pop ax
    ret

; tg_undo - SPEC.md 97.7's `U`: the planner's LAST action taken back
tg_undo:
    push ax
    push bx
    mov al, [tg_side]
    call tg_planp
    mov al, [bx]
    or al, al
    jz .out
    dec al
    call tg_remove
.out:
    pop bx
    pop ax
    ret

; tg_reset - the list's RESET ALL row: the whole plan gone. (`R` is the
; music's - SPEC.md 97.7's fake round, which this file's real one now calls.)
tg_reset:
    push ax
    push bx
    cmp byte [tg_ph], TG_PH_PLAN
    jne .out
    cmp byte [ti_rv], 0
    jne .out
    mov al, [tg_side]
    call tg_planp
    mov byte [bx], 0
    mov bl, [ti_played]
    push bx
    call tg_replay
    pop bx
    call tg_edited
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
    call tg_sync1
    jnc tg_sync
    ret

; tg_sync1 - the NEXT cell tg_sync would touch, and only that one: CF=0 one
; was brought to its view, CF=1 none was owed. Preserves every register.
;
; ONE A CALL so the worker can take the round's arrival a cell a frame
; (tg_res_step) rather than all of them inside one - the other side's plan
; is up to ten characters composed from nothing, and in one call that was the
; longest stall of the round.
tg_sync1:
    push ax
    push bx
    push cx
    push word [ti_ci]
    xor cx, cx
.c:
    cmp cx, TI_CELLS
    jae .none
    mov bx, cx
    mov ax, cx
    call ti_cell_key                ; the art, and a shooter's stance
    cmp al, [tg_cart + bx]
    jne .do
    cmp byte [tg_vdirty + bx], 0
    jne .do
    inc cx
    jmp short .c
.do:
    mov [ti_ci], cx
    cmp al, [tg_cart + bx]
    je .art
    mov word [ti_cfbeg], 0          ; ALL EIGHT FRAMES: a character that is
    mov word [ti_cfend], 2 * TI_POSES ; drawn now may swing next
    call ti_cell_build
    call tm_run                     ; (the eight frames are most of the cell,
    mov byte [bx + ti_clock], 0     ; SPEC.md 97.12.9)
    mov byte [ti_dok], 0            ; whole, not a transition
    mov ax, cx
    call ti_feature
    call tm_run
.art:
    mov byte [tg_vdirty + bx], 0
    call ti_cell_xy
    call ti_cellnum
    call tm_run                     ; the music a cell at a time
    clc
    jmp short .out
.none:
    stc
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
    cmp byte [tg_cconf], 0          ; ASKED ALREADY: this is the answer
    jne .go
    call tg_idlecheck               ; A PLAN WITH NOTHING IN IT, from a hand
    jc .go                          ; that could have done something, is asked
    mov si, ti_s_cconf              ; about once (SPEC.md 97.12.10.4) - and
    call tg_note                    ; nothing else is: banking gold is play
    mov byte [tg_cconf], 1
    jmp short .out
.go:
    call ti_rv_atk_flush
    call tg_idle
    cmp byte [tg_side], 0
    jne .resolve
    mov byte [tg_side], 1           ; --- P1 is done: nothing of their plan
    mov word [tg_msg1], ti_s_sealed ; is left on the glass for P2 to read
    mov word [tg_msg2], ti_s_pass2
    jmp short .pass
.resolve:
    call tg_res_begin               ; --- BOTH PLANS, and the round fought on
    jmp short .out                  ; the glass a lane at a time (tg_res_step)
.pass:
    mov byte [tg_ph], TG_PH_PASS
    call tg_replay
    call tg_screen
.out:
    pop si
    pop bx
    pop ax
    ret

; tg_idlecheck - CF=0 when the planner's plan is EMPTY and they could have
; done something: a card in the hand they can pay for, and a column with room
; (SPEC.md 97.12.10.4). CF=1 otherwise. Preserves every register.
tg_idlecheck:
    push ax
    push bx
    mov al, [tg_side]
    call tg_planp
    cmp byte [bx], 0
    jne .no                         ; something is planned: no question
    cmp byte [ti_colfull], 3
    je .no                          ; nowhere to play anything
    xor bx, bx
.s:
    cmp bx, TI_HAND
    jae .no
    mov ax, bx
    call ti_rv_played
    jc .n
    push bx
    mov ax, bx
    mov bl, TI_C_SIZE
    mul bl
    mov bx, ax
    cmp byte [ti_cards + bx + TI_C_CARD], TR_EMPTY
    pop bx
    je .n
    mov al, [ti_shg + bx]
    or al, [ti_shs + bx]
    jz .yes                         ; a card it can pay for
.n:
    inc bx
    jmp short .s
.yes:
    clc
    jmp short .out
.no:
    stc
.out:
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
    mov di, tg_mbuf
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
    mov word [tg_msg1], tg_mbuf
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
    mov bx, [ti_oy]                 ; IN BANDS, with the music between them
.band:                              ; (SPEC.md 97.12.9): the whole content in
    mov ax, [ti_ox]                 ; one fill was over two ticks of an 8088,
    mov cx, ax                      ; and it is where a round hands over - the
    add cx, [ti_cw_box]             ; resolution's music ending under it
    dec cx
    mov dx, bx
    add dx, TG_SCRBAND - 1
    mov si, [ti_oy]
    add si, [ti_ch_box]
    dec si
    cmp dx, si
    jbe .bfit
    mov dx, si
.bfit:
    call OSAPI_GFX_FILL
    call tm_run
    mov bx, dx
    inc bx
    cmp bx, si
    jbe .band
    mov dx, [ti_ch_box]
    shr dx, 1
    sub dx, 12
    add dx, [ti_oy]
    mov si, [tg_msg1]
    call .line
    add dx, 16
    mov si, [tg_msg2]
    call .line
    call tm_run
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

; tg_onscreen - CF=0 when the window is showing the pass screen (or the
; match's end), CF=1 when it is showing the board. Preserves every register.
;
; THE BOARD IS UP IN TWO PHASES, not one: a planner's AND the round being
; fought. A repaint asked `is it the planning phase?` and drew the pass
; screen for anything else - so a window uncovered mid-round lost the board
; and the log to a screen saying the first planner had committed.
tg_onscreen:
    cmp byte [tg_ph], TG_PH_PASS
    je .yes
    cmp byte [tg_ph], TG_PH_OVER
    je .yes
    stc
    ret
.yes:
    clc
    ret

; -----------------------------------------------------------------------------
; tg_resume - the pass screen was clicked away: the next planner's board, from
; nothing. A window callback, the gfx lock held. Preserves every register.
; -----------------------------------------------------------------------------
tg_resume:
    push ax
    cmp byte [tg_ph], TG_PH_PLAN    ; only a PASS screen or the match's end
    je .out                         ; is clicked away - a round being fought
    cmp byte [tg_ph], TG_PH_RES     ; is not
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
    call tg_income_set              ; ...and says what the upkeep brought them
    call ti_hud_status              ; (SPEC.md 97.12.10.5)
.out:
    pop ax
    ret

; tg_redraw - a new planner's window from nothing: the hand's units, every
; cell whose art moved, and the whole board. Preserves every register.
tg_redraw:
    push ax
    mov word [ti_row], TI_ROW_FRONT ; A NEW PLANNER STARTS ON FRONT: the row
                                    ; is where a played card goes, and the
                                    ; last player's REAR carried over to the
                                    ; next (SPEC.md 97.4.8.2)
    call tg_idle
    mov word [ti_hover], -1
    mov word [ti_hovc], -1
    call ti_units_build             ; the hand is another player's, or new
    call tg_cells                   ; ...and so may every cell be
    call tm_run
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
; game's. [tg_fillq] = 2 leaves P1's FRONT column empty, for a row that plays,
; and 3 is not a full board at all but a DEALT MATCH, off the two seeds in
; tg_tseed - the one mode a row can hold to tools/duelsim.py hand for hand.
; -----------------------------------------------------------------------------
tg_fill:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp byte [tg_fillq], 3          ; 3: A DEALT MATCH off the seeds the test
    jne .full                       ; wrote (tg_tseed), which tools/duelsim.py
    mov ax, [tg_tseed]              ; deals the same way - so the row can hold
    mov [tr_decka + 4], ax          ; every hand and board to the simulator's
    mov ax, [tg_tseed + 2]
    mov [tr_deckb + 4], ax
    call tg_deal
    call tg_redraw
    jmp .ret
.full:
    mov word [tg_newslot], 0FFFFh   ; (no card of this board is NEW)
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
.ret:
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
    call ti_cell_key
    mov bx, cx
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


; =============================================================================
; PLANNING BY HAND: an ORDER armed and placed, a SWAP of two cells, a STANCE,
; and the PLAN as a list any entry of which can be removed (TITHE-PLAN 6.3)
; =============================================================================

TG_LROW     equ 8                   ; the list's row pitch: the system face
TG_LMAXR    equ 32                  ; rows a list is ever given

; -----------------------------------------------------------------------------
; tg_card_click - hand slot AX was clicked: an ORDER is ARMED (a character is
; clicked next), anything else is PLAYED (tirv.inc). A window callback, the
; gfx lock held. Preserves every register.
; -----------------------------------------------------------------------------
tg_card_click:
    push ax
    push bx
    call tg_unsel                   ; a pending swap is abandoned
    push ax
    mov bl, TI_C_SIZE
    mul bl
    mov bx, ax
    mov al, [ti_cards + bx + TI_C_CARD]
    pop bx                          ; BX = the slot
    cmp al, TR_EMPTY
    je .out
    push bx
    call tr_crec
    cmp byte [bx + TI_CR_KIND], TI_KIND_ORDER
    pop bx
    je .order
    call tg_disarm
    call tg_prompt_set0
    mov ax, bx
    call ti_rv_play
    jmp short .out
.order:
    cmp [tg_arm], bl                ; the armed one again: disarmed
    jne .arm
    call tg_disarm
    call tg_prompt_set0
    jmp short .out
.arm:
    call tg_disarm                  ; ...another order armed is let go
    mov [tg_arm], bl                ; (this one is hovered: already lit)
    mov byte [ti_note], 0
    mov word [tg_prompt], ti_s_pord
    call ti_hud_status
.out:
    pop bx
    pop ax
    ret

; tg_idle - nothing pending and the panel on the hand: a turn's boundary
tg_idle:
    mov byte [tg_list], 0
    mov word [tg_lbl], ti_s_plan
    mov word [tg_sel], -1
    mov byte [tg_arm], 0FFh
    mov word [tg_tgt], -1
    mov word [tg_prompt], 0
    mov byte [ti_note], 0
    mov byte [tg_cconf], 0
    mov byte [tg_cqarm], 0
    mov word [tg_lscroll], 0
    ret

; -----------------------------------------------------------------------------
; tg_disarm - an ORDER armed is let go: its card put back as it rests, and the
; target under the pointer with it (SPEC.md 97.12.10.2). The gfx lock held.
; Preserves every register.
; -----------------------------------------------------------------------------
tg_disarm:
    push ax
    mov al, [tg_arm]
    cmp al, 0FFh
    je .out
    mov byte [tg_arm], 0FFh
    xor ah, ah
    cmp byte [tg_list], 0           ; (the plan list is where the hand was)
    jne .tgt
    call ti_card_fast
.tgt:
    mov ax, -1
    call tg_tgt_set
.out:
    pop ax
    ret

; tg_tgt_set - AX = the cell an armed ORDER would land on, or -1: its numbers
; INVERTED, as a swap's first end's are, and the last one's put back. The gfx
; lock held. Preserves every register.
tg_tgt_set:
    cmp ax, [tg_tgt]
    jne .go
    ret
.go:
    push ax
    push bx
    push word [ti_ci]
    mov bx, [tg_tgt]
    mov [tg_tgt], ax
    push ax
    cmp bx, -1
    je .new
    mov [ti_ci], bx
    call ti_cell_xy
    call ti_cellnum
.new:
    pop ax
    cmp ax, -1
    je .out
    mov [ti_ci], ax
    call ti_cell_xy
    call ti_cellnum
.out:
    pop word [ti_ci]
    pop bx
    pop ax
    ret

; tg_tgt_track - the pointer moved: while an ORDER is armed, the planner's own
; character under it is its target, and is shown so (SPEC.md 97.12.10.2). The
; worker's frame, the lock held. Preserves every register.
tg_tgt_track:
    cmp byte [tg_arm], 0FFh
    jne .go
    ret
.go:
    push ax
    push cx
    push dx
    push si
    mov ax, [ti_hovc]
    cmp ax, -1
    je .set
    mov cx, ax
    call tg_ecell                   ; SI = the cell, AL = its side
    cmp al, [tg_side]
    jne .none
    cmp byte [si + CE_CARD], TR_EMPTY
    je .none
    mov ax, cx
    jmp short .set
.none:
    mov ax, -1
.set:
    call tg_tgt_set
    pop si
    pop dx
    pop cx
    pop ax
    ret

; tg_prompt_set0 - no prompt, and the HUD's status line says so
tg_prompt_set0:
    mov byte [ti_note], 0
    mov byte [tg_cconf], 0
    cmp word [tg_prompt], 0
    je .out
    mov word [tg_prompt], 0
    call ti_hud_status
.out:
    ret

; tg_unsel - a swap's first cell forgotten, and its numbers put back
tg_unsel:
    push ax
    push bx
    mov ax, [tg_sel]
    cmp ax, -1
    je .out
    mov word [tg_sel], -1
    push word [ti_ci]
    mov [ti_ci], ax
    call ti_cell_xy
    call ti_cellnum
    pop word [ti_ci]
    call tg_prompt_set0
.out:
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_cell_click - board cell AX was clicked at (CX, DX): an armed ORDER goes on
; the character there; else the STANCE MARK under a shooter's feet toggles
; (SPEC.md 97.12.10.1); else it is one end of a SWAP. A window callback, the gfx lock held. Preserves every
; register.
; -----------------------------------------------------------------------------
tg_cell_click:
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, ax                      ; SI = the cell
    push cx
    mov cx, si
    call tg_subject                 ; is it the planner's, and who is there
    pop cx
    jnc .mine
    push cx                         ; ...an empty cell of the planner's is
    push si                         ; still a swap's end
    mov cx, si
    call tg_ecell
    pop si
    pop cx
    cmp al, [tg_side]
    je .swap
    call tg_disarm                  ; the other side's: whatever was pending
    call tg_unsel                   ; is let go
    call tg_prompt_set0
    jmp .out
.mine:
    cmp byte [tg_arm], 0FFh         ; --- an ORDER, armed ------------------
    je .nord
    call tg_unsel
    mov al, [tg_side]
    push di
    call tg_frzside
    mov bl, [tg_arm]
    xor bh, bh
    mov al, [bx + di + SD_HAND]
    pop di
    mov ch, [tg_arm]
    mov bh, al
    mov bl, TR_A_ORDER
    xor cl, cl                      ; (the instance: the replay resolves it)
    mov dl, [ti_played]
    mov byte [tg_arm], 0FFh         ; LET GO WITHOUT A DRAW: the edit puts the
    mov ax, [tg_tgt]                ; slot down empty and the target's numbers
    mov word [tg_tgt], -1           ; back, once each
    cmp ax, -1
    je .notgt
    push bx                         ; (BX is the action: op and card)
    mov bx, ax
    mov byte [tg_vdirty + bx], 1
    pop bx
.notgt:
    push cx
    call tg_act
    pop cx
    call tg_prompt_set0
    mov bl, dl
    call tg_edited
    mov al, ch                      ; ...and a REFUSED order is still in the
    xor ah, ah                      ; hand, lit: put it back as it rests
    call ti_rv_played
    jc .out
    push si
    mov si, ti_s_nord               ; (and the status line says so)
    call tg_note
    pop si
    cmp byte [tg_list], 0
    jne .out
    call ti_card_fast
    jmp .out
.nord:
    mov ax, si                      ; --- the STANCE MARK ------------------
    call ti_cell_flags
    test al, TI_CF_RANGED
    jz .swap
    push ax
    mov ax, si
    call tg_mark
    pop ax
    jc .swap
    call tg_unsel
    mov byte [ti_hstat], 1          ; ...and the HUD says the new one
    call tg_stance_find             ; the subject already has a stance entry:
    jc .newst                       ; taking it out IS the toggle back
    mov dl, [ti_played]
    mov bl, dl
    call tg_remove
    jmp .out
.newst:
    mov ah, 1                       ; the other stance
    test al, TI_CF_SNIPE
    jz .st
    xor ah, ah
.st:
    mov cl, ah
    mov bl, TR_A_STANCE
    xor bh, bh                      ; (the cell: the replay resolves it)
    mov ch, 0FFh
    mov dl, [ti_played]
    call tg_act
    mov bl, dl
    call tg_edited
    jmp short .out
.swap:
    mov ax, [tg_sel]                ; --- a SWAP's two ends -----------------
    cmp ax, -1
    jne .second
    mov [tg_sel], si                ; the first: its numbers inverted, and
    push word [ti_ci]               ; the HUD asks for the second
    mov [ti_ci], si
    call ti_cell_xy
    call ti_cellnum
    pop word [ti_ci]
    mov byte [ti_note], 0
    mov word [tg_prompt], ti_s_pswap
    call ti_hud_status
    jmp short .out
.second:
    cmp ax, si
    jne .do
    call tg_unsel                   ; the same cell again: let go
    jmp short .out
.do:
    mov cx, ax                      ; the engine names a cell column x 5 +
    call tg_local                   ; lane, on its own side
    mov bh, al
    mov cx, si
    call tg_local
    mov cl, al
    mov bl, TR_A_SWAP
    mov ch, 0FFh
    mov byte [tg_nref], 0FFh        ; A SWAP HAS NO SUBJECT: it names two
    mov byte [tg_ntgt], 0           ; CELLS, and whoever tg_subject last found
    call tg_unsel                   ; there is not what it is about - carried,
                                    ; removing that play orphaned the swap
    mov dl, [ti_played]
    call tg_act
    jnc .swapped
    push si                         ; REFUSED: say why (97.12.10.3)
    mov si, ti_s_nswap
    cmp byte [ti_swaps], 0
    je .sw0
    mov si, ti_s_nswap2
.sw0:
    call tg_note
    pop si
.swapped:
    mov bl, dl
    call tg_edited
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tg_local - board cell CX -> AL = the engine's name for it, column x 5 +
; lane. Preserves every other register.
tg_local:
    push dx
    push si
    push cx
    call tg_ecell
    mov al, ah
    mov cl, TR_LANES
    mul cl
    add al, dl
    pop cx
    pop si
    pop dx
    ret

; tg_stance_find - CF=0 and AL = the entry that already sets a stance on the
; subject in [tg_nref]/[tg_ntgt]; CF=1 when none does. Preserves the rest.
tg_stance_find:
    push bx
    push cx
    push si
    push ax
    mov al, [tg_side]
    call tg_planp
    xor cx, cx
.e:
    cmp cl, [bx]
    jae .no
    mov si, cx
    shl si, 1
    add si, cx
    cmp byte [bx + si + 1], TR_A_STANCE
    jne .n
    mov si, cx
    mov al, [bx + si + TG_P_REF]
    cmp al, [tg_nref]
    jne .n
    cmp al, 0FFh
    jne .yes
    mov al, [bx + si + TG_P_TGT]
    cmp al, [tg_ntgt]
    je .yes
.n:
    inc cx
    jmp short .e
.no:
    pop ax
    stc
    jmp short .out
.yes:
    pop ax
    mov al, cl
    clc
.out:
    pop si
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tg_mark - AX = a cell, (CX, DX) = the pointer: CF=0 when it is on the cell's
; STANCE MARK (SPEC.md 97.12.10.1) - the band's foot, across the mark's 48
; columns. It does not ask whether a shooter stands there. Preserves every
; register.
; -----------------------------------------------------------------------------
tg_mark:
    push ax
    push bx
    push si
    push word [ti_ci]
    mov [ti_ci], ax
    push dx
    xor dx, dx
    mov bx, TI_ROWS
    div bx                          ; AX = the column
    call ti_col_insx                ; ...and the band's inset in it
    mov si, ax
    pop dx
    call ti_cell_xy                 ; AX = x, BX = y
    add ax, si
    add ax, 8                       ; the mark's ink, 48 of the band's 64
    cmp cx, ax
    jb .no
    add ax, 48
    cmp cx, ax
    jae .no
    add bx, [ti_insy]
    add bx, [ti_bh]                 ; the band's foot...
    cmp dx, bx
    jae .no
    call ti_mark_rows
    sub bx, ax                      ; ...and the mark's rows over it
    cmp dx, bx
    jb .no
    clc
    jmp short .out
.no:
    stc
.out:
    pop word [ti_ci]
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE PLAN LIST, in the panel where the hand was (TITHE-PLAN 6.3: "shown as a
; numbered list in the card panel and any entry may be removed")
; -----------------------------------------------------------------------------

; tg_list_toggle - the panel's left button and `L`: the hand, or the plan
tg_list_toggle:
    push ax
    cmp byte [tg_ph], TG_PH_PLAN
    jne .out
    cmp byte [ti_rv], 0
    jne .out
    call tg_disarm                  ; (an armed order's card leaves the glass)
    mov al, 1                       ; the hand -> the PLAN; any list -> the
    cmp byte [tg_list], 0           ; hand
    je .set
    xor al, al
.set:
    call tg_list_go
.out:
    pop ax
    ret

; tg_list_go - AL = what the panel shows: 0 the hand, 1 the plan, 3 the last
; round's log (SPEC.md 97.12.10.6). The gfx lock held. Preserves every
; register.
tg_list_go:
    push ax
    mov [tg_list], al
    mov word [tg_lscroll], 0
    mov byte [tg_cqarm], 0
    mov word [ti_hover], -1
    mov word [tg_lbl], ti_s_plan
    or al, al
    jz .draw
    mov word [tg_lbl], ti_s_hand
.draw:
    call ti_panel
    pop ax
    ret

; tg_logview - SPEC.md 97.7's `H`: the last round's LOG in the panel, or back
; to where it was opened from (97.12.10.6). Preserves every register.
tg_logview:
    push ax
    cmp byte [tg_ph], TG_PH_PLAN
    jne .out
    cmp byte [ti_rv], 0
    jne .out
    call tg_disarm
    mov al, [tg_lback]
    cmp byte [tg_list], 3
    je .go                          ; open: back to where it came from
    mov al, [tg_list]
    mov [tg_lback], al
    mov al, 3
.go:
    call tg_list_go
.out:
    pop ax
    ret

; tg_concede - the list's CONCEDE row and `Q`: the FIRST asks, the second
; ends the match for the other player (SPEC.md 97.12.10.6). A window
; callback, the gfx lock held. Preserves every register.
tg_concede:
    push ax
    push si
    cmp byte [tg_ph], TG_PH_PLAN
    jne .out
    cmp byte [ti_rv], 0
    jne .out
    cmp byte [tg_cqarm], 0
    jne .yes
    mov byte [tg_cqarm], 1          ; ASKED: the row says so, and the HUD
    mov si, ti_s_cqask
    call tg_note
    mov byte [tg_cqarm], 1          ; (tg_note's own resets leave it be)
    cmp byte [tg_list], 1
    jne .out
    call tg_list_draw
    jmp short .out
.yes:
    call ti_rv_atk_flush
    mov al, TR_RES_B                ; THE OTHER PLAYER WINS
    mov si, ti_s_p1con
    cmp byte [tg_side], 0
    je .who
    mov al, TR_RES_A
    mov si, ti_s_p2con
.who:
    mov [tr_result], al
    mov [tg_msg1], si
    mov word [tg_msg2], ti_s_again
    call tg_idle
    mov byte [tg_ph], TG_PH_OVER
    call tg_screen
.out:
    pop si
    pop ax
    ret

; tg_list_box - AX, BX = the list's top left, CX = its width, DX = its height
tg_list_box:
    cmp byte [ti_horiz], 0
    je .v
    mov ax, [ti_cardpitch]          ; across the fullscreen hand's seven
    mov dx, TI_HAND
    mul dx
    sub ax, 8
    mov cx, ax
    mov ax, [ti_panx]
    mov bx, [ti_hy]
    mov dx, [ti_cbrows]
    ret
.v:
    mov ax, [ti_cardpitch]          ; ...or down the strip's
    mul word [ti_cardn]
    sub ax, TI_CARDGAP
    mov dx, ax
    mov ax, [ti_cardx]
    mov bx, [ti_by]
    mov cx, [ti_cardw]
    ret

; tg_list_geo - where the rows are: [tg_lx] (a byte in from the box, so a
; row's cells are byte columns and GFX_SCROLL can move them), [tg_ly],
; [tg_lw] characters a row - A LOG LINE'S WIDTH in the log, never the box's -
; and [tg_lrows]. Preserves every register.
tg_list_geo:
    push ax
    push bx
    push cx
    push dx
    call tg_list_box
    add ax, 8
    mov [tg_lx], ax
    add bx, 3
    mov [tg_ly], bx
    sub cx, 16
    shr cx, 1
    shr cx, 1
    shr cx, 1
    mov bx, TG_BUFW - 1
    cmp byte [tg_list], 2           ; THE LOG IS NEVER WIDER THAN ITS LINES:
    jb .cap                         ; padding a fullscreen row to the box's
    mov bx, TG_LOGW - 1             ; 39 cells for a 17-cell line was more
.cap:                               ; than half of every row it drew (and the
                                    ; viewer, 3, is the same log)
    cmp cx, bx
    jbe .w
    mov cx, bx
.w:
    mov [tg_lw], cx
    mov ax, dx
    sub ax, 6
    xor dx, dx
    mov bx, TG_LROW
    div bx
    cmp al, [tg_lrcap]              ; (a test may ask for fewer, to make the
    jbe .r                          ; log scroll: tests/tithelog.py)
    mov al, [tg_lrcap]
    xor ah, ah
.r:
    mov [tg_lrows], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tg_list_show - the list's ground, then the list: a SWITCH to it, once
tg_list_show:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    mov al, CBLACK
    call OSAPI_SET_COLOR
    call tg_list_box
    add cx, ax
    dec cx
    add dx, bx
    dec dx
    call OSAPI_GFX_FILL
    push ax
    mov al, CWHITE
    call OSAPI_SET_COLOR
    pop ax
    call OSAPI_GFX_FRAME
    push ds                         ; the ground is fresh: every row is empty
    pop es
    cld
    mov di, tg_rowlen
    mov cx, TG_LMAXR
    xor al, al
    rep stosb
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    jmp tg_list_draw

; -----------------------------------------------------------------------------
; tg_list_draw - the list whole: every row of the plan and RESET under the
; last - or, in the log, its last lines. A row is drawn only as wide as its
; text or what it overwrites (tg_row_put), and a row that was empty and
; stays empty costs nothing, so an edit redraws what changed width and not
; the box. Preserves every register.
; -----------------------------------------------------------------------------
tg_list_draw:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld
    call tg_list_geo
    cmp byte [tg_list], 2           ; THE LOG, while a round is fought: its
    jne .plan                       ; last lines, as many as the box holds
    mov ax, [tg_logn]
    xor dx, dx
    sub ax, [tg_lrows]
    jbe .lall
    mov dx, ax
    mov ax, [tg_lrows]
    jmp short .lset
.lall:
    mov ax, [tg_logn]
.lset:
    mov [tg_lfirst], dx
    mov [tg_ln], ax
    mov [tg_lused], ax              ; ...and all of it is drawn after this
    mov ax, [tg_ltot]
    mov [tg_ldrn], ax
.rows:                              ; (its last lines, row by row)
    xor ax, ax
.r:
    cmp ax, [tg_lrows]
    jae .rout
    mov di, tg_buf1
    cmp ax, [tg_ln]
    jae .rput
    push ax
    add ax, [tg_lfirst]
    call tg_log_line
    pop ax
.rput:
    mov byte [di], 0
    call tg_row_put
    call tm_run                     ; the music a row at a time: a whole list
    inc ax                          ; is the round's opening, in its panel
    jmp short .r                    ; (SPEC.md 97.12.9)
.rout:
    jmp .out
.plan:
    cmp byte [tg_list], 3
    jne .plan1
    jmp .view
.plan1:
    mov al, [tg_side]
    call tg_planp
    mov cl, [bx]
    xor ch, ch
    mov [tg_ln], cx
    call tg_lwin                    ; [tg_le] rows of entries, and whether
    xor ax, ax                      ; they scroll (97.12.10.6). AX = the row
.pr:
    cmp ax, [tg_lrows]
    jb .prgo
    jmp .out
.prgo:
    mov di, tg_buf1
    mov bx, [tg_lrows]
    sub bx, 3
    cmp ax, bx
    jb .pent
    push ax                         ; --- THE THREE COMMAND ROWS, at the foot
    sub ax, bx
    mov si, ti_s_reset
    cmp word [tg_ln], 0
    jne .c0
    mov si, ti_s_noplan
.c0:
    or ax, ax
    jz .cw
    mov si, ti_s_vlog
    cmp word [tg_logn], 0
    jne .c1
    mov si, ti_s_nolog
.c1:
    cmp ax, 1
    je .cw
    mov si, ti_s_conc
    cmp byte [tg_cqarm], 0
    je .cw
    mov si, ti_s_conc2
.cw:
    call ti_poke
    pop ax
    jmp short .pput
.pent:
    call tg_lrow_item               ; AX = the row -> BX = the entry, or an
    cmp bx, -1                      ; arrow (-2 up, -3 down), or nothing (-1)
    je .pput
    cmp bx, -2
    jne .pdn
    cmp word [tg_lscroll], 0
    je .pput
    mov si, ti_s_up
    push ax
    call ti_poke
    pop ax
    jmp short .pput
.pdn:
    cmp bx, -3
    jne .pe
    mov si, ti_s_dn
    push ax
    call tg_lmore
    jnc .pdn0
    call ti_poke
.pdn0:
    pop ax
    jmp short .pput
.pe:
    push ax
    mov ax, bx
    call tg_entry_text
    pop ax
.pput:
    mov byte [di], 0
    call tg_row_put
    call tm_run                     ; the music a row at a time
    inc ax
    jmp .pr

.view:                              ; --- THE LAST ROUND'S LOG, and BACK -----
    mov ax, [tg_logn]
    mov [tg_ln], ax
    call tg_lwin
    xor ax, ax
.vr:
    cmp ax, [tg_lrows]
    jb .vrgo
    jmp .out
.vrgo:
    mov di, tg_buf1
    mov bx, [tg_lrows]
    dec bx
    cmp ax, bx
    jb .vent
    mov si, ti_s_back               ; the foot: BACK
    push ax
    call ti_poke
    pop ax
    jmp short .vput
.vent:
    call tg_lrow_item
    cmp bx, -1
    je .vput
    cmp bx, -2
    jne .vdn
    cmp word [tg_lscroll], 0
    je .vput
    mov si, ti_s_up
    push ax
    call ti_poke
    pop ax
    jmp short .vput
.vdn:
    cmp bx, -3
    jne .ve
    mov si, ti_s_dn
    push ax
    call tg_lmore
    jnc .vdn0
    call ti_poke
.vdn0:
    pop ax
    jmp short .vput
.ve:
    push ax
    mov ax, bx
    call tg_log_line
    pop ax
.vput:
    mov byte [di], 0
    call tg_row_put
    call tm_run
    inc ax
    jmp .vr
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; THE LIST'S WINDOW (SPEC.md 97.12.10.6). The plan's entries - or the log's
; lines - take the rows the list's foot leaves: three command rows under the
; plan, BACK under the log. When there are more than those rows hold, the
; first and last of them are ARROWS and the rest a window [tg_lscroll, ...).
; -----------------------------------------------------------------------------

; tg_lwin - [tg_le] = the rows the items get, [tg_lsc] = 1 when they scroll.
; Preserves every register.
tg_lwin:
    push ax
    mov ax, [tg_lrows]
    sub ax, 3                       ; the plan's three command rows...
    cmp byte [tg_list], 3
    jne .h
    add ax, 2                       ; ...or the log's one BACK
.h:
    jns .pos
    xor ax, ax
.pos:
    mov [tg_le], ax
    mov byte [tg_lsc], 0
    cmp ax, [tg_ln]
    jae .out
    cmp ax, 3                       ; (a window needs a row between arrows)
    jb .out
    mov byte [tg_lsc], 1
.out:
    pop ax
    ret

; tg_lrow_item - AX = an item row -> BX = the item it shows, -2 the up arrow,
; -3 the down arrow, -1 nothing. Preserves every other register.
tg_lrow_item:
    cmp byte [tg_lsc], 0
    jne .sc
    mov bx, -1
    cmp ax, [tg_ln]
    jae .out
    mov bx, ax
.out:
    ret
.sc:
    mov bx, -2
    or ax, ax
    jz .out
    mov bx, [tg_le]
    dec bx
    cmp ax, bx
    mov bx, -3
    je .out
    mov bx, ax
    dec bx
    add bx, [tg_lscroll]
    cmp bx, [tg_ln]
    jb .out
    mov bx, -1
    ret

; tg_lmore - CF=1 when the window has items below it. Preserves every
; register.
tg_lmore:
    push ax
    mov ax, [tg_le]
    sub ax, 2
    add ax, [tg_lscroll]
    cmp ax, [tg_ln]
    cmc                             ; CF=1: scroll + shown < n
    pop ax
    jnc .no
    ret
.no:
    clc
    ret

; tg_list_scroll - AX = rows to move the window by, signed; clamped, and the
; list drawn again if it moved. The gfx lock held. Preserves every register.
tg_list_scroll:
    push ax
    push bx
    cmp byte [tg_list], 1
    je .go
    cmp byte [tg_list], 3
    jne .out
.go:
    cmp byte [tg_lsc], 0
    je .out
    add ax, [tg_lscroll]
    jns .lo
    xor ax, ax
.lo:
    mov bx, [tg_ln]                 ; the last window: n less what it shows
    sub bx, [tg_le]
    add bx, 2
    cmp ax, bx
    jle .hi
    mov ax, bx
.hi:
    cmp ax, [tg_lscroll]
    je .out
    mov [tg_lscroll], ax
    call tg_list_draw
.out:
    pop bx
    pop ax
    ret

; tg_log_line - AX = a line of the log buffer: DI -> it copied to tg_buf1,
; DI past it. Preserves every register bar DI.
;
; IT SETS ES ITSELF. The copy is `stosb`, and the worker's frame reaches here
; with ES on whatever it last composed through - the scratch part, an art
; part - so the line went THERE, into another segment, and tg_buf1 still
; held the line before it: the log drew each line twice and wrote a stray
; one into the scratch part. The window callbacks happened to arrive with
; ES = DS, which is why the whole-list draw never showed it.
tg_log_line:
    push ax
    push bx
    push si
    push es
    push ds
    pop es
    cld
    mov bx, TG_LOGW
    mul bx
    add ax, tg_log
    mov si, ax
    mov di, tg_buf1
    call ti_poke
    pop es
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_row_put - list row AX gets the NUL text at tg_buf1: padded only to what
; was there before (tg_rowlen), so a shorter line leaves nothing behind and a
; row that was empty and stays empty is not drawn at all. One font_run, which
; lays its own ground (SPEC.md 6.1). Preserves every register.
; -----------------------------------------------------------------------------
tg_row_put:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov bx, ax
    mov di, tg_buf1
    xor cx, cx
.l:
    cmp byte [di], 0
    je .have
    inc di
    inc cx
    jmp short .l
.have:
    cmp cx, [tg_lw]
    jbe .c
    mov cx, [tg_lw]
    mov di, tg_buf1
    add di, cx
.c:
    mov dl, [tg_rowlen + bx]        ; what the row held
    xor dh, dh
    mov [tg_rowlen + bx], cl        ; ...and what it will
    cmp dx, [tg_lw]
    jbe .p
    mov dx, [tg_lw]
.p:
    cmp cx, dx
    jae .end
    mov byte [di], ' '
    inc di
    inc cx
    jmp short .p
.end:
    mov byte [di], 0
    jcxz .out                       ; empty, and was
    mov ax, bx
    mov cx, TG_LROW
    mul cx
    add ax, [tg_ly]
    mov dx, ax
    mov cx, [tg_lx]
    mov si, tg_buf1
    mov ax, (CBLACK << 8) | CWHITE
    call OSAPI_FONT_RUN             ; (NO tm_run here: a row is one short
.out:                               ; line now, and the music's own chain
                                    ; under a list draw under a board repaint
                                    ; was 22 bytes past the worker's 256-byte
                                    ; slice - tests/unit/t_stkclass.py)
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_log_draw1 - ONE log line onto the glass, if one is owed: from the
; worker's frame while a round is fought. Preserves every register.
;
; THE LOG WAS REDRAWN WHOLE FOR EVERY LINE ADDED, every row padded to the
; box - measured on a 4.77 MHz 8088 in fullscreen at up to 275 ms of a lane's
; 330, inside the worker's frame, with the music waiting at the top of the
; loop for all of it. Now a line is drawn ONCE, one a frame, as wide as a log
; line; and when the box is full the rows above it move up by OSAPI_GFX_SCROLL
; (SPEC.md 5.5) - under a millisecond - rather than being lettered again.
; -----------------------------------------------------------------------------
tg_log_draw1:
    cmp byte [tg_list], 2
    jne .ret
    push ax
    mov ax, [tg_ltot]
    cmp ax, [tg_ldrn]
    jne .go
    pop ax
.ret:
    ret
.go:
    push bx
    push cx
    push dx
    push si
    push di
    call tg_list_geo
    mov ax, [tg_ltot]               ; the oldest line owed, in the buffer -
    sub ax, [tg_ldrn]               ; which keeps the last TG_LOGN, so a
    cmp ax, [tg_logn]               ; backlog longer than that has lost its
    jbe .inbuf                      ; head, and is taken from what is left
    mov ax, [tg_logn]
    mov bx, [tg_ltot]
    sub bx, ax
    mov [tg_ldrn], bx
.inbuf:
    mov bx, [tg_logn]
    sub bx, ax
    mov ax, bx
    call tg_log_line
    mov byte [di], 0
    mov ax, [tg_lused]
    cmp ax, [tg_lrows]
    jb .room
    mov ax, [tg_lx]                 ; FULL: everything up a row. The rect is
    mov bx, [tg_ly]                 ; the rows' own cells, byte columns both
    mov cx, [tg_lw]                 ; ends, so the scroll is legal and what
    shl cx, 1                       ; it vacates is exactly one row
    shl cx, 1
    shl cx, 1
    add cx, ax
    dec cx
    push ax
    mov ax, [tg_lrows]
    mov dx, TG_LROW
    mul dx
    add ax, bx
    dec ax
    mov dx, ax
    pop ax
    mov si, TG_LROW
    call OSAPI_GFX_SCROLL
    jnc .moved
    call tg_list_draw               ; refused (the window is covered): the
    jmp short .out                  ; whole list, which is the old way
.moved:
    push es                         ; ...the lengths move with the rows, and
    push ds                         ; the vacated one is repainted WHOLE -
    pop es                          ; its content is unspecified (5.5)
    cld
    mov di, tg_rowlen
    mov si, tg_rowlen + 1
    mov cx, TG_LMAXR - 1
    rep movsb
    pop es
    mov bx, [tg_lrows]
    dec bx
    mov al, [tg_lw]
    mov [tg_rowlen + bx], al
    mov ax, bx
    jmp short .put
.room:
    inc word [tg_lused]
.put:
    call tg_row_put
    inc word [tg_ldrn]
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tg_entry_text - AX = an entry: DI -> its row, `NN WHAT WHO`, DI past it.
; Preserves every register bar DI.
tg_entry_text:
    push ax
    push bx
    push cx
    push si
    mov cx, ax
    inc al
    call ti_u8
    mov al, ' '
    stosb
    mov al, [tg_side]
    call tg_planp
    mov si, cx
    shl si, 1
    add si, cx
    add si, bx                      ; SI -> the action - 1
    mov al, [si + 1]
    cmp al, TR_A_PLAY
    jne .n1
    mov al, 'F'                     ; PLAY: the column and the card
    cmp byte [si + 3], 0
    je .col
    mov al, 'R'
.col:
    stosb
    mov al, ' '
    stosb
    mov al, [si + 2]
    jmp short .name
.n1:
    cmp al, TR_A_ORDER
    jne .n2
    push si
    mov si, ti_s_lord               ; ORDER: the order card
    call ti_poke
    pop si
    mov al, [si + 2]
    jmp short .name
.n2:
    cmp al, TR_A_SWAP
    jne .n3
    push si
    mov si, ti_s_lswap              ; SWAP: the two cells
    call ti_poke
    pop si
    mov al, [si + 2]
    call .cell
    mov al, ' '
    stosb
    mov al, [si + 3]
    call .cell
    jmp short .out
.n3:
    push si                         ; STANCE: which, and on whom
    mov bl, [si + 3]
    mov si, ti_s_lfront
    or bl, bl
    jz .sw
    mov si, ti_s_lsnipe
.sw:
    call ti_poke
    pop si
    mov al, [si + 2]                ; the cell -> who stands there
    xor ah, ah
    mov bl, TR_LANES
    div bl                          ; AL = column, AH = lane
    mov cl, ah
    mov ah, al
    mov al, [tg_side]
    push si
    call tr_cell
    mov al, [si + CE_CARD]
    pop si
    cmp al, TR_EMPTY
    je .out
.name:
    xor ah, ah
    mov bx, ax
    shl bx, 1
    push si
    mov si, [ti_cardname + bx]
    call ti_poke
    pop si
.out:
    pop si
    pop cx
    pop bx
    pop ax
    ret
.cell:                              ; AL = column x 5 + lane -> `F3` / `R1`
    xor ah, ah
    mov bl, TR_LANES
    div bl
    mov bl, 'F'
    or al, al
    jz .cf
    mov bl, 'R'
.cf:
    mov al, bl
    stosb
    mov al, ah
    add al, '1'
    stosb
    ret

; tg_list_hit - (CX, DX) -> AL = the list row under it - an entry, or the
; RESET row after the last - and 0FFh for none. Preserves every register bar
; AX. The rows are where tg_list_draw last put them.
tg_list_hit:
    push bx
    push cx
    push dx
    push si
    push di
    mov si, cx
    mov di, dx
    call tg_list_box                ; AX, BX = the box, CX its width
    cmp si, ax
    jb .no
    add ax, cx
    cmp si, ax
    jae .no
    mov ax, di
    sub ax, [tg_ly]
    jb .no
    xor dx, dx
    mov bx, TG_LROW
    div bx
    cmp ax, [tg_lrows]
    jae .no
    jmp short .out
.no:
    mov al, 0FFh
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    ret

; tg_list_click - list row AL was clicked: an entry is REMOVED, the row after
; the last is RESET (TITHE-PLAN 5.0.2). Preserves every register.
tg_list_click:
    push ax
    push bx
    xor ah, ah
    mov bx, [tg_lrows]
    cmp byte [tg_list], 3
    je .view
    sub bx, 3                       ; --- the plan's three command rows ----
    cmp ax, bx
    jb .item
    sub ax, bx
    jnz .c1
    mov byte [tg_cqarm], 0
    call tg_reset
    jmp short .out
.c1:
    cmp ax, 1
    jne .c2
    call tg_logview
    jmp short .out
.c2:
    call tg_concede
    jmp short .out
.view:
    dec bx                          ; --- the log's BACK ---------------------
    cmp ax, bx
    jb .item
    call tg_logview
    jmp short .out
.item:
    cmp byte [tg_cqarm], 0          ; (a concede asked is let go by any other
    je .ni                          ; row)
    mov byte [tg_cqarm], 0
    call tg_prompt_set0
    call tg_list_draw
.ni:
    call tg_lrow_item
    cmp bx, -2
    jne .dn
    mov ax, [tg_le]                 ; an arrow: a window up...
    sub ax, 2
    neg ax
    call tg_list_scroll
    jmp short .out
.dn:
    cmp bx, -3
    jne .ent
    mov ax, [tg_le]                 ; ...or down
    sub ax, 2
    call tg_list_scroll
    jmp short .out
.ent:
    cmp bx, -1
    je .out
    cmp byte [tg_list], 3           ; a LOG line is read, not removed
    je .out
    mov al, bl
    call tg_remove
.out:
    pop bx
    pop ax
    ret


; =============================================================================
; THE ROUND, FOUGHT ON THE GLASS (TITHE-PLAN 6.4 and 6.5)
;
; P2's commit applies both plans to the frozen board and the board shows it at
; once - THE OPPONENT'S PLAN ARRIVES ALL AT ONCE, which is the owner's ruling
; and the same rule that keeps a plan from leaking. Then the engine's three
; calls (tr_res_begin, tr_lane per lane, tr_res_end) are made ONE A FRAME from
; the worker: a lane is fought, its melee CLASHES and its bolts FLY from the
; side that shot, and when they have landed its numbers change and the LOG,
; in the panel where the hand was, says what happened. Casualties and spoils
; are the last step, and a hold after them is the round's last look before the
; screen that ends it. Nothing is decided here - the engine did that - so a
; missed frame is a slower round and never a different one.
; =============================================================================

; tg_res_begin - both plans, the board they make, and the fight begun. A
; window callback, the gfx lock held. Preserves every register.
tg_res_begin:
    push ax
    push bx
    push si
    push di
    push es
    push ds
    pop es
    cld
    call tg_load
    mov word [tr_err], 0
    xor al, al
    call tg_planp
    mov si, bx
    call tr_apply
    mov al, 1
    call tg_planp
    mov si, bx
    call tr_apply
    call tg_snap_pools              ; what each player kept: the next income
    call tr_res_begin
    mov al, TM_RQ_RES               ; THE RESOLUTION MUSIC cuts in (97.10.6):
    call tm_post                    ; what the music's `R` fakes, for real
    mov byte [tg_plan0], 0
    mov byte [tg_plan1], 0
    mov byte [tg_side], 0
    mov byte [tg_ph], TG_PH_RES
    mov byte [tg_rs], 0
    mov byte [tg_rsync], 0
    mov byte [tg_rwait], 0         ; the arrival first, then the hold
    mov byte [tg_list], 2           ; the panel is the LOG now
    mov word [tg_logn], 0
    mov word [tg_ltot], 0
    mov word [tg_ldrn], 0
    mov word [tg_lused], 0
    mov di, tg_buf1
    mov si, ti_s_round
    call ti_poke
    mov al, [tr_round]
    call ti_u8
    mov byte [di], 0
    call tg_log_add
    call tg_views
    mov word [tg_phs], ti_s_resolving
    mov word [ti_hover], -1
    mov word [ti_hovc], -1
    ; WHAT MOVED AND NOTHING ELSE, AND NOT ALL AT ONCE. This was ti_board
    ; and ti_all - the whole window again - and measured 880 ms of a 4.77 MHz
    ; 8088 in fullscreen with the music stopped for it. What the commit
    ; changes is the HUD's phase, the pools, the panel - here - and the cells
    ; the other side's plan filled, which the worker composes and puts down
    ; ONE A FRAME (tg_sync1), so the arrival is a cascade and not a freeze.
    call tm_run                     ; (the UI task holds the lock the worker
    call ti_hud_draw                ; would step the music from, so it steps
    call tm_run                     ; it here, between the three)
    call ti_res_all                 ; ...and the CELLS arrive a frame at a
    call tm_run                     ; time, from the worker (tg_res_step)
    call ti_panel
    mov byte [tg_rarr], 1
    pop es
    pop di
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_res_step - one step of the round, from the worker's frame. The gfx lock
; held, the window's region armed. Preserves every register.
; -----------------------------------------------------------------------------
tg_res_step:
    cmp byte [tg_ph], TG_PH_RES
    je .go
    ret
.go:
    push ax
    call tg_log_draw1               ; a log line a frame, if one is owed
    cmp byte [tg_rwait], 0
    je .due
    dec byte [tg_rwait]
    jmp .out
.due:
    cmp byte [tg_rarr], 0           ; THE ARRIVAL: a cell a frame, then the
    je .fight                       ; hold before the first lane
    call tg_sync1
    jnc .out
    mov byte [tg_rarr], 0
    mov byte [tg_rwait], TG_RHOLD
    jmp .out
.fight:
    cmp byte [ti_clash], 0          ; a clash or a bolt still in the air: the
    jne .out                        ; numbers change when they LAND
    call ti_pj_live
    or ax, ax
    jnz .out
    cmp byte [tg_rsync], 0
    je .stage
    mov byte [tg_rsync], 0
    call tg_res_show
    mov byte [tg_rwait], TG_RGAP
    jmp .out
.stage:
    mov al, [tg_rs]
    cmp al, TR_LANES
    jb .lane
    je .cas
    cmp al, TR_LANES + 1
    jne .done
    inc byte [tg_rs]                ; the last look, before the screen
    mov byte [tg_rwait], TG_RHOLD * 2
    jmp .out
.done:
    call tg_res_done
    jmp .out
.lane:
    call tg_snap
    mov [tr_lr], al
    mov [ti_pjlane], al
    mov [tg_rlane], al
    call tr_lane
    inc byte [tg_rs]
    mov byte [tg_rsync], 1
    call tg_res_anim
    jmp short .out
.cas:
    call tg_snap
    mov byte [tg_rlane], 0FFh
    call tr_res_end
    inc byte [tg_rs]
    mov byte [tg_rsync], 1
.out:
    pop ax
    ret

; tg_res_anim - the lane just fought, animated from its HITS: a clash if any
; landed in melee, a bolt from each side that shot. Preserves every register.
tg_res_anim:
    push ax
    push bx
    push cx
    push si
    xor bx, bx                      ; BL = melee, BH = shooters (bit a side)
    mov cx, [tr_nhit]
    mov si, tr_hits
    jcxz .have
.h:
    cmp byte [si + HT_RNG], 0
    jne .rng
    mov bl, 1
    jmp short .n
.rng:
    mov al, [si + HT_E]             ; the side it LANDS on; the other shot
    xor al, 1
    inc al
    or bh, al
.n:
    add si, TR_HITSZ
    loop .h
.have:
    or bl, bl
    jz .nocl
    call ti_cl_fire
.nocl:
    or bh, bh
    jz .nopj
    call ti_pj_fire
    test bh, 1
    jnz .p1
    mov byte [ti_pjon], 0           ; P1 did not shoot
.p1:
    test bh, 2
    jnz .nopj
    mov byte [ti_pjon + 1], 0       ; ...P2 did not
.nopj:
    or bx, bx
    jnz .out
    mov byte [tg_rwait], TG_RGAP    ; a quiet lane: a beat, and on
.out:
    pop si
    pop cx
    pop bx
    pop ax
    ret

; tg_snap - what the board and the pools are before a step, for tg_res_show
tg_snap:
    push ax
    push bx
    push si
    mov si, tr_cells
    xor bx, bx
.c:
    mov al, [si + CE_CARD]
    mov [tg_snc + bx], al
    mov al, [si + CE_HP]
    mov [tg_snh + bx], al
    add si, TR_CELLSZ
    inc bx
    cmp bx, TR_CELLS
    jb .c
    xor bx, bx
.s:
    mov al, bl
    push di
    call tr_side
    mov ax, [di + SD_HP]
    shl bx, 1
    mov [tg_snp + bx], ax
    shr bx, 1
    mov al, [di + SD_GOLD]
    mov [tg_sng + bx], al
    mov al, [di + SD_SOULS]
    mov [tg_sns + bx], al
    pop di
    inc bx
    cmp bx, 2
    jb .s
    pop si
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tg_res_show - a step has landed: the log says what it changed, and the board
; and the HUD show it. Preserves every register.
; -----------------------------------------------------------------------------
tg_res_show:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov byte [tg_lhdr], 0
    mov byte [tg_rpool], 0
    mov si, tr_cells
    xor bx, bx
.c:
    mov al, [tg_snc + bx]
    cmp al, TR_EMPTY
    je .cn
    cmp byte [si + CE_CARD], TR_EMPTY
    jne .hp
    call .hdr                       ; gone: it FELL
    mov di, tg_buf1
    call .name
    push si
    mov si, ti_s_falls
    call ti_poke
    pop si
    mov byte [di], 0
    call tg_log_add
    jmp short .cn
.hp:
    mov ah, [si + CE_HP]
    sub ah, [tg_snh + bx]
    jz .cn
    call .hdr
    mov di, tg_buf1
    call .name
    mov al, ' '
    stosb
    mov al, '+'
    or ah, ah
    jns .sg
    mov al, '-'
    neg ah
.sg:
    stosb
    mov al, ah
    call tg_num
    mov byte [di], 0
    call tg_log_add
.cn:
    add si, TR_CELLSZ
    inc bx
    cmp bx, TR_CELLS
    jb .c
    xor bx, bx                      ; --- the players, and their pools
.s:
    mov al, bl
    call tr_side                    ; DI = the side
    mov si, di
    shl bx, 1
    mov ax, [si + SD_HP]
    sub ax, [tg_snp + bx]
    shr bx, 1
    or ax, ax
    jz .pool
    mov byte [tg_rpool], 1
    call .hdr
    mov di, tg_buf1
    call .who
    push ax
    mov al, '+'
    or ax, ax
    jns .ps
    mov al, '-'
.ps:
    stosb
    pop ax
    or ax, ax
    jns .pa
    neg ax
.pa:
    call tg_num
    push si
    mov si, ti_s_lhp
    call ti_poke
    pop si
    mov byte [di], 0
    call tg_log_add
.pool:
    mov al, [si + SD_GOLD]
    sub al, [tg_sng + bx]
    mov ah, [si + SD_SOULS]
    sub ah, [tg_sns + bx]
    or ax, ax
    jz .sn
    mov byte [tg_rpool], 1
    mov di, tg_buf1                 ; SPOILS: `P1 +2G +1S`
    call .who
    push ax
    call .signed
    mov al, 'G'
    stosb
    mov al, ' '
    stosb
    pop ax
    mov al, ah
    call .signed
    mov al, 'S'
    stosb
    mov byte [di], 0
    call tg_log_add
.sn:
    inc bx
    cmp bx, 2
    jb .s
    call tg_views                   ; ...and the board shows it
    mov word [tg_phs], ti_s_resolving
    call tg_sync
    cmp byte [tg_rpool], 0          ; ...and the pools, only if they moved
    je .nopool
    call ti_res_all
.nopool:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.hdr:                               ; the lane's header, before its first line
    cmp byte [tg_lhdr], 0
    jne .hx
    mov byte [tg_lhdr], 1
    cmp byte [tg_rlane], 0FFh
    je .hx
    push ax
    push di
    push si
    mov di, tg_buf1
    mov si, ti_s_lane
    call ti_poke
    mov al, [tg_rlane]
    add al, '1'
    stosb
    mov byte [di], 0
    call tg_log_add
    pop si
    pop di
    pop ax
.hx:
    ret
.name:                              ; the card that WAS in cell BX
    push ax
    push bx
    push si
    mov al, [tg_snc + bx]
    xor ah, ah
    mov bx, ax
    shl bx, 1
    mov si, [ti_cardname + bx]
    call ti_poke
    pop si
    pop bx
    pop ax
    ret
.who:                               ; `P1 ` or `P2 ` for side BL
    push ax
    mov al, 'P'
    stosb
    mov al, bl
    add al, '1'
    stosb
    mov al, ' '
    stosb
    pop ax
    ret
.signed:                            ; AL signed -> `+n` / `-n`
    push ax
    mov ah, '+'
    or al, al
    jns .sp
    mov ah, '-'
    neg al
.sp:
    push ax
    mov al, ah
    stosb
    pop ax
    call tg_num
    pop ax
    ret

; tg_num - AL as decimal, no leading zero, at DI. Preserves every register
; bar DI.
tg_num:
    push ax
    xor ah, ah
    cmp al, 10
    jb .one
    push bx
    mov bl, 10
    div bl
    add al, '0'
    stosb
    mov al, ah
    pop bx
.one:
    add al, '0'
    stosb
    pop ax
    ret

; tg_log_add - the NUL line at tg_buf1 onto the log (the oldest scrolls off).
; It DRAWS NOTHING: tg_log_draw1 owes it to the glass. Preserves every
; register.
tg_log_add:
    push ax
    push cx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov ax, [tg_logn]
    cmp ax, TG_LOGN
    jb .room
    mov di, tg_log                  ; full: every line up one
    mov si, tg_log + TG_LOGW
    mov cx, (TG_LOGN - 1) * TG_LOGW
    rep movsb
    dec word [tg_logn]
    mov ax, [tg_logn]
.room:
    mov cx, TG_LOGW
    mul cx
    add ax, tg_log
    mov di, ax
    mov si, tg_buf1
    mov cx, TG_LOGW - 1
.cp:
    lodsb
    or al, al
    jz .end
    stosb
    loop .cp
.end:
    mov byte [di], 0
    inc word [tg_logn]
    inc word [tg_ltot]              ; owed to the glass: tg_log_draw1 puts it
.out:                               ; down, a line a frame
    pop es
    pop di
    pop si
    pop cx
    pop ax
    ret

; tg_res_done - the round is over: its screen, and the next round's upkeep
; or the match's end. Preserves every register.
tg_res_done:
    push ax
    mov al, TM_RQ_END               ; ...and ends with the round: its tail,
    call tm_post                    ; then the theme back where it was cut
    call tg_result
    cmp byte [tr_result], 0
    jne .over
    call tg_upk
    call tg_save
    mov word [tg_msg2], ti_s_pass1
    mov byte [tg_ph], TG_PH_PASS
    call tg_idle
    call tg_replay
    call tm_run                     ; (the upkeep and the replay, then a fill
    call tg_screen                  ; of the whole window: the music between)
    jmp short .out
.over:
    call tg_save
    mov byte [tg_ph], TG_PH_OVER
    mov word [tg_msg2], ti_s_again
    call tg_idle
    call tg_views
    call tg_screen
.out:
    pop ax
    ret

TG_RHOLD    equ 18                  ; frames the board both plans made holds
TG_RGAP     equ 4                   ; ...and between one step and the next

TG_BUFW     equ 40

ti_s_p1plans: db '   P1 PLANS', 0
ti_s_resolving: db '   RESOLVING', 0
ti_s_falls: db ' FALLS', 0
ti_s_lane:  db 'LANE ', 0
ti_s_lhp:   db ' HP', 0
ti_s_plan:  db 'PLAN', 0            ; the panel's left button, both ways
ti_s_hand:  db 'HAND', 0
ti_s_reset: db 'RESET ALL', 0
ti_s_vlog:  db 'VIEW LAST ROUND', 0
ti_s_nolog: db 'NO ROUND FOUGHT YET', 0
ti_s_conc:  db 'CONCEDE', 0
ti_s_conc2: db 'CONCEDE? CLICK AGAIN', 0
ti_s_up:    db '    ...MORE ABOVE', 0
ti_s_dn:    db '    ...MORE BELOW', 0
ti_s_back:  db 'BACK', 0
ti_s_cqask: db 'CONCEDE THE MATCH? CLICK CONCEDE OR PRESS Q AGAIN', 0
ti_s_p1con: db 'PLAYER 1 CONCEDES - PLAYER 2 WINS', 0
ti_s_p2con: db 'PLAYER 2 CONCEDES - PLAYER 1 WINS', 0
ti_s_noplan: db 'NO ACTIONS YET', 0
ti_s_lord:  db 'ORDER ', 0
ti_s_lswap: db 'SWAP ', 0
ti_s_lfront: db 'FRONT ', 0
ti_s_lsnipe: db 'SNIPE ', 0
ti_s_pswap: db 'SWAP WITH WHICH OF YOUR CELLS?', 0
ti_s_pord:  db 'ORDER: ON WHICH OF YOUR CHARACTERS?', 0
ti_s_stf:   db 'STANCE: FRONT', 0
ti_s_nfront: db 'FRONT IS FULL - PLAY TO REAR', 0
ti_s_nrear: db 'REAR IS FULL - PLAY TO FRONT', 0
ti_s_ngold: db 'NOT ENOUGH GOLD', 0
ti_s_nsoul: db 'NOT ENOUGH SOULS', 0
ti_s_nplay: db 'THAT CARD CANNOT BE PLAYED NOW', 0
ti_s_nswap: db 'NO SWAPS LEFT THIS ROUND', 0
ti_s_nswap2: db 'THOSE TWO CANNOT SWAP', 0
ti_s_nord:  db 'THAT ORDER CANNOT GO THERE', 0
ti_s_cconf: db 'NOTHING PLANNED - COMMIT AGAIN TO PASS', 0
ti_s_income: db 'INCOME ', 0
ti_s_drew:  db '  DREW ', 0
ti_s_hfull: db '  HAND FULL - ', 0
ti_s_discd: db ' DISCARDED', 0
ti_s_sts:   db 'STANCE: SNIPE', 0
ti_s_stcs:  db ' - CLICK TO SNIPE', 0
ti_s_stcf:  db ' - CLICK TO AIM FRONT', 0
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
tg_tseed:   dw 0, 0                 ; ...and mode 3's two seeds
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
tg_plan0:   times TG_PBSZ db 0      ; each side's plan block
tg_plan1:   times TG_PBSZ db 0
tg_map:     times TG_MAXACT db 0    ; a replay's old entry -> new, 0FFh gone
tg_pinst:   times TG_MAXACT db 0    ; the instance each PLAY received
tg_mini:    db 1, 0, 0, 0           ; one action, as a plan of one
tg_skip:    db 0FFh                 ; the entry the next replay takes out
tg_nref:    db 0FFh                 ; the next action's subject: a play...
tg_ntgt:    db 0                    ; ...or a frozen instance
tg_n0:      db 0
tg_ninst:   db 0
tg_sdi:     dw 0
tg_list:    db 0                    ; the panel: 0 the hand, 1 the PLAN, 2 the
                                    ; round's log as it is fought, 3 the last
                                    ; round's log, read (97.12.10.6)
tg_lback:   db 0                    ; ...where the log view was opened from
tg_lscroll: dw 0                    ; ...the list's window: its first item,
tg_le:      dw 0                    ; ...the rows its items get,
tg_lsc:     db 0                    ; ...and whether they scroll
tg_cqarm:   db 0                    ; CONCEDE has been asked about
tg_sel:     dw -1                   ; a swap's first cell, chosen
tg_arm:     db 0FFh                 ; an ORDER's hand slot, armed
tg_tgt:     dw -1                   ; ...and the character it would land on
tg_cconf:   db 0                    ; an empty COMMIT has been asked about
tg_nx:      dw 0                    ; where the pointer was when a note went
tg_ny:      dw 0                    ; up (tg_note_at)
tg_pg:      db 0, 0                 ; each side's pool when it last committed,
tg_pso:     db 0, 0                 ; gold and souls (tg_snap_pools)
tg_nh0:     db 0, 0                 ; ...its hand's size before the upkeep,
tg_drew:    db 0FFh, 0FFh           ; ...the card the upkeep drew,
tg_disc:    db 0FFh, 0FFh           ; ...or discarded from a full hand,
tg_newslot: dw -1, -1               ; ...and the slot the drawn one is NEW in
tg_incbuf:  times 56 db 0           ; the income, as the status line says it
tg_prompt:  dw 0                    ; what the HUD says while one is pending
tg_lbl:     dw ti_s_plan            ; the left button's word
tg_lx:      dw 0                    ; where tg_list_draw put the rows
tg_ly:      dw 0
tg_lw:      dw 0
tg_lrows:   dw 0
tg_ln:      dw 0
tg_rowlen:  times TG_LMAXR db 0     ; what each list row holds, in cells
tg_lrcap:   db TG_LMAXR             ; the most rows a list is given
tg_ltot:    dw 0                    ; log lines added this round...
tg_ldrn:    dw 0                    ; ...and put on the glass
tg_lused:   dw 0                    ; the log's rows in use
tg_lfirst:  dw 0                    ; the first log line shown
tg_rs:      db 0                    ; the round's step: lanes, casualties, hold
tg_rsync:   db 0                    ; a step fought, and not yet shown
tg_rwait:   db 0                    ; frames before the next step
tg_rlane:   db 0                    ; the lane just fought, 0FFh casualties
tg_lhdr:    db 0
tg_rarr:    db 0                    ; the other side's cells still arriving
tg_rpool:   db 0                    ; a step moved a player's HP or pools
tg_snc:     times TR_CELLS db 0     ; the board and pools before a step
tg_snh:     times TR_CELLS db 0
tg_snp:     dw 0, 0
tg_sng:     db 0, 0
tg_sns:     db 0, 0
tg_logn:    dw 0
tg_log:     times TG_LOGN * TG_LOGW db 0
tg_mbuf:    times TG_BUFW db 0      ; the pass screen's first line
tg_buf1:    times TG_BUFW db 0
tg_frz:     times 2 * TR_SIDESZ + TR_CELLS * TR_CELLSZ db 0
ti_cards:   times TI_NVIEW * TI_C_SIZE db 0
