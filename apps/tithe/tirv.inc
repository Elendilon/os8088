; =============================================================================
; os8088 - apps/tithe/tirv.inc
;
; THE REVEAL (SPEC.md 97.4.11, TITHE-PLAN 16.2 item 7): a card played from the
; hand reaches its cell. Three things, OVERLAPPED, and the whole of it is
; nine frames where a clash is sixteen:
;
;   1. a TRAIL OF SPARKS from the card to the cell, a comet down the line -
;      the head arrives on frame TI_RVTRAVEL and the tail pours in over the
;      two after;
;   2. the card DISSOLVING OUT of the hand while the trail leaves it, gone
;      before the sparks arrive;
;   3. the character DISSOLVING IN over its cell's ground as the tail pours
;      in, through three ordered-dither steps, its numbers on the frame after.
;
; THE SPARKS ARE XOR, AND THAT IS NOT THE BOLT'S SHAPE ON PURPOSE. The bolt is
; a band composed over the ground it crosses (tipj.inc), which works because a
; lane is ground and nothing else in the bolt's rows. The trail crosses the
; FIGURES of every cell between the hand and the target, the numbers, the gap
; beside the board and the card panel - things no picture in this package
; holds. An XOR fill is its own erase over anything at all, needs no buffer,
; and is never refused: the save-under pair (SPEC.md 5.3) was the other way
; to leave the glass as it was, and it REFUSES a rect that straddles two
; displays, which a trail on an extended desktop would.
;
; WHAT XOR COSTS IS ORDER, and the frame keeps it: the sparks are erased FIRST
; in a frame, before anything draws, and put down LAST, after everything has.
; A band committed in between lands on a clean glass, so the next frame's
; erase restores exactly what the frame left. Anything that draws OUTSIDE the
; worker's frame breaks that - a W_PAINT - and so a paint that lands while
; sparks are up drops them and asks for a whole repaint (ti_rv_lost).
; =============================================================================

TI_RVTRAVEL equ 6                 ; frames of flight: a clash is sixteen, and a
                                  ; bolt crosses the board at 24 pixels a frame
                                  ; where this goes ~70
TI_RVCARD   equ 1                 ; the card fades on frames 1-4: 3, 2, 1, gone
TI_RVCELL   equ 5                 ; the character forms on frames 5-8: 1 to 4
TI_RVEND    equ 9                 ; its numbers...
TI_RVDONE   equ 10                ; ...the planner's gold, and it is over
TI_RVSPK    equ 6                 ; sparks a frame: the head and five behind,
                                  ; a quarter frame apart - a tail a frame and
                                  ; a half long. It was twelve, then eight;
                                  ; each is two XOR fills a frame, ~2 ms of an
                                  ; 8088, which is what lets the idle keep
                                  ; breathing through a reveal (97.4.11.1)
TI_THMAX    equ 16                ; the most words the fade's unrolled run
                                  ; ANDs a row: the strip's band is the panel's
                                  ; width, 152 pixels at the widest (20 bytes,
                                  ; 10 words), and a portrait's is 11 bytes
TI_RVMAX    equ 352               ; the largest cell band, a VGA's 64 x 44

; -----------------------------------------------------------------------------
; ti_rv_played - CF=1 if hand card AX has been played. Preserves every register.
; -----------------------------------------------------------------------------
ti_rv_played:
    push ax
    push cx
    mov cl, al
    mov al, 1
    shl al, cl
    test [ti_played], al
    pop cx
    pop ax
    jz .no
    stc
    ret
.no:
    clc
    ret

; -----------------------------------------------------------------------------
; ti_rv_key - SPEC.md 97.7's `V`: play the hovered card, else the first still
; in the hand - and an empty hand is dealt again. Preserves every register.
; -----------------------------------------------------------------------------
ti_rv_key:
    push ax
    mov ax, -1
    call ti_rv_play
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_play - PLAY hand card AX (or, AX = -1, the hovered card else the first
; still in the hand) into the topmost empty cell of the planner's column that
; the FRONT/REAR toggle names (tigame.inc's tg_play, TITHE-PLAN 5.6). A CLICK
; on a card is this, and so is `V`.
; in:  a window callback, the gfx lock held. Preserves every register.
;
; THE CARD THAT DISSOLVES IS THE ONE ON THE GLASS. A click lands on the
; HOVERED card - expanded and in its own polarity - so it is composed and
; banked while it is still the hovered one, and only then stops being it.
; -----------------------------------------------------------------------------
ti_rv_play:
    push ax
    push bx
    push cx
    push dx
    cmp byte [ti_ok], 0
    je .out
    cmp byte [ti_rv], 0
    jne .out
    cmp byte [ti_clash], 0          ; a clash owns the front line's bands
    jne .out
    cmp word [ti_cardn], 0
    je .out
    cmp byte [tg_list], 0           ; the hand is not on the glass
    jne .out
    cmp ax, -1
    je .pick
    cmp ax, [ti_cardn]              ; ...a card named: it must be one still
    jae .out                        ; in the hand
    call ti_rv_played
    jc .out
    jmp short .have
.pick:
    mov ax, [ti_hover]
    cmp ax, -1
    jne .have
    xor ax, ax
.find:
    cmp ax, [ti_cardn]
    jae .out                        ; nothing left in the hand
    call ti_rv_played
    jnc .have
    inc ax
    jmp short .find
.have:
    mov [ti_rvcard], ax
    call ti_rv_atk_flush            ; the LAST play's attack frames, if any are
                                    ; still owed (ti_rv_atk)
    ; --- THE ENGINE SAYS WHETHER AND WHERE (tigame.inc): the play goes on the
    ; end of the plan and the plan is applied again, and a refusal - no gold,
    ; a full column - is the rules' own and moves nothing. Past this the card
    ; is marked played and its cell's VIEW already names who stands there.
    call tg_play
    jnc .placed
    jmp .out
.placed:
    mov [ti_rvcell], ax
    call tm_run                     ; THE CLICK IS ~80 ms WITH THE LOCK HELD:
                                    ; the music from here, as the relayout
                                    ; steps it (timus.inc)

    ; --- the CARD is composed now and banked for its fade, AS IT IS ON THE
    ; GLASS - hovered, if it is - rather than on the fade's first step: ~22 ms
    ; of an 8088 is room a trail frame has not got, and here it is latency
    ; before the first spark instead of a stutter in the middle
    mov byte [ti_cfsave], 0
    mov ax, [ti_rvcard]
    call ti_rv_frombank             ; THE CARD IS ALREADY COMPOSED: its bank
    jnc .banked                     ; (SPEC.md 97.4.12.1), hovered or not, is
    mov byte [ti_cfade], 3          ; the picture on the glass - ~28 ms of
    mov word [ti_calconly], 1       ; the click that was a composition
    call ti_card_draw               ; ...else compose, bank - and put nothing
    mov word [ti_calconly], 0       ; down
    mov byte [ti_cfade], 0
.banked:
    mov word [ti_hover], -1         ; ...and it stops being the hovered card,
                                    ; so the wheel stops animating its unit

    ; --- WHO: the card now stands there, composed into the cell ------------
    mov bx, [ti_rvcell]
    push word [ti_ci]
    mov [ti_ci], bx
    mov word [ti_cfbeg], 0          ; ITS RESTING POSE ONLY: the dissolve
    mov word [ti_cfend], 1          ; forms pose 0, and the other three idle
    call ti_cell_build              ; poses and the four attack frames follow
    mov word [ti_cfend], 2 * TI_POSES ; the reveal a frame at a time
    mov [ti_atkcell], bx            ; (ti_rv_atk) - where all eight stood
    mov word [ti_atkfr], 1          ; between the click and the first spark
    call tm_run
    mov byte [bx + ti_clock], 0     ; ...and it will idle from its first pose

    ; --- the two ends of the trail -----------------------------------------
    call ti_cell_xy                 ; AX, BX = the cell
    push ax
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_ROWS
    div cx
    call ti_col_insx
    mov cx, ax
    pop ax
    add ax, cx                      ; ...the figure band's centre
    mov cx, [ti_bs]
    shl cx, 1
    shl cx, 1
    add ax, cx                      ; + BS x 8 / 2
    mov [ti_rvx1], ax
    add bx, [ti_insy]
    mov cx, [ti_bh]
    shr cx, 1
    add bx, cx
    mov [ti_rvy1], bx
    pop word [ti_ci]
    mov ax, [ti_rvcard]             ; the card's centre, down the strip or
    call ti_card_pos                ; across the fullscreen hand (97.4.12)
    mov cx, [ti_cardw]
    cmp byte [ti_horiz], 0          ; a strip band has its margin before the
    jne .across                     ; card, a portrait band none
    add ax, [ti_cardx]
    sub ax, [ti_panx]
.across:
    shr cx, 1
    add ax, cx
    mov [ti_rvx0], ax
    mov ax, [ti_cardh]
    shr ax, 1
    add bx, ax
    mov [ti_rvy0], bx

    ; --- the cell is VACATED, and the trail begins -------------------------
    xor al, al                      ; level 0: the ground alone
    call ti_rv_cell
    mov byte [ti_rv], 1
    mov byte [ti_rvt], 0
    mov word [ti_rvn], 0
    mov word [ti_rvlast], 0         ; no frame of it measured yet
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_atk - one of the played cell's owed frames - its idle poses 1 to 3,
; then its four ATTACK frames - a frame at a time once the reveal is over.
; Preserves every register.
;
; A PLAY IS POSE 0 AND NOTHING ELSE. Composing all eight at the click was ~81
; ms of the 112 between the click and the first spark; the attack frames came
; out first, and since SPEC.md 97.4.11.1 the idle poses too - ~20 ms each on a
; VGA's cell, which put a reveal frame over its tick. The wheel holds the cell
; at pose 0 until they are built (ti_frame), and its clock comes back to 0
; with the last of them. One a frame, when no reveal is running; a clash, a
; relayout or the next play takes the rest at once (ti_rv_atk_flush) rather
; than swing with frames that are not there.
; -----------------------------------------------------------------------------
ti_rv_atk:
    cmp byte [ti_rv], 0
    jne .out
    cmp word [ti_atkcell], -1
    je .out
    push ax
    push bx
    push dx
    call ti_pit                     ; TIMED, for the next frame's credit
    mov [ti_rvp0], ax               ; (ti_rv_cost): ~18 ms on a VGA's cell,
    push word [ti_ci]               ; after the wheel had spent its own
    mov ax, [ti_atkcell]
    mov [ti_ci], ax
    mov ax, [ti_atkfr]
    mov [ti_cfbeg], ax
    inc ax
    mov [ti_cfend], ax
    call ti_cell_build
    mov word [ti_cfbeg], 0
    mov word [ti_cfend], 2 * TI_POSES
    inc word [ti_atkfr]
    cmp word [ti_atkfr], TI_POSES   ; THE LAST IDLE POSE: the wheel has held
    jne .held                       ; the cell at pose 0 while its clock ran,
    call ti_rv_clock0               ; so its clock comes back to the glass
.held:
    cmp word [ti_atkfr], 2 * TI_POSES
    jb .more
    mov word [ti_atkcell], -1       ; ...all four: the cell is whole
.more:
    pop word [ti_ci]
    call ti_pit
    mov bx, [ti_rvp0]
    sub bx, ax
    mov ax, bx
    mov bx, 8381
    mul bx
    mov bx, 10000
    div bx
    mov [ti_rvlast], ax
    pop dx
    pop bx
    pop ax
.out:
    ret

; ti_rv_clock0 - the played cell [ti_atkcell] back on pose 0, which is what
; the glass shows while the wheel holds it (ti_frame). Preserves every
; register.
ti_rv_clock0:
    push bx
    mov bx, [ti_atkcell]
    mov byte [bx + ti_clock], 0
    pop bx
    ret

; ti_rv_atk_flush - every frame still owed, now. Preserves every register.
ti_rv_atk_flush:
    push ax
    push word [ti_ci]
    mov ax, [ti_atkcell]
    cmp ax, -1
    je .out
    cmp word [ti_atkfr], TI_POSES   ; (its idle poses too: the clock comes
    jae .idle                       ; back to the pose 0 the glass shows)
    call ti_rv_clock0
.idle:
    mov [ti_ci], ax
    mov ax, [ti_atkfr]
    mov [ti_cfbeg], ax
    call ti_cell_build
    mov word [ti_cfbeg], 0
    mov word [ti_atkcell], -1
.out:
    pop word [ti_ci]
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_erase - take the last frame's sparks off the glass. FIRST in a frame.
; Preserves every register.
; -----------------------------------------------------------------------------
ti_rv_erase:
    push ax
    push bx
    push cx
    push dx
    push si
    call ti_pit                     ; TIMED, for the next frame's price
    mov [ti_rvp0], ax               ; (ti_rv_cost)
    mov si, ti_rvsp
.next:
    cmp word [ti_rvn], 0
    je .out
    mov ax, [si]
    mov bx, [si + 2]
    mov cx, [si + 4]
    mov dx, [si + 6]
    call OSAPI_GFX_XOR_FILL
    add si, 8
    dec word [ti_rvn]
    jmp short .next
.out:
    call ti_pit
    mov bx, [ti_rvp0]
    sub bx, ax
    mov [ti_rvera], bx              ; PIT counts
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_lost - a W_PAINT is about to draw, outside the worker's frame. The
; sparks it lands on are gone and the ones it does not are still up, and no
; erase can tell the two apart - so drop the record and ask the next frame
; for a whole repaint, which leaves none anywhere. Preserves every register.
; -----------------------------------------------------------------------------
ti_rv_lost:
    cmp word [ti_rvn], 0
    je .out
    mov word [ti_rvn], 0
    mov byte [ti_rvfull], 1
.out:
    ret

; -----------------------------------------------------------------------------
; ti_rv_step - one frame of the reveal. LAST in a frame, after every band.
; in:  the gfx lock held, the window's region armed. Preserves every register.
; -----------------------------------------------------------------------------
ti_rv_step:
    push ax
    cmp byte [ti_rv], 0
    jne .on
    jmp .out
.on:
    cmp byte [ti_rv], 1             ; 2 and 3 are an UNDO's fade and a SWAP's
    je .rev                         ; sparks (SPEC.md 97.12.10.7)
    call ti_rv_other
    jmp .out
.rev:
    push bx
    push dx
    call ti_pit                     ; TIMED, for the next frame's price
    mov [ti_rvp0], ax               ; (ti_rv_cost)
    cmp byte [ti_rvfull], 0         ; an expose landed on the sparks: the
    je .go                          ; whole window again, now, under the
    mov byte [ti_rvfull], 0         ; region the worker armed
    call ti_ground
    call ti_board
    call ti_all
.go:
    inc byte [ti_rvt]
    call ti_rv_sparks               ; --- THE TRAIL, until its tail is in ------
    mov al, [ti_rvt]
    cmp al, TI_RVCARD + 3           ; --- THE CARD, while the trail leaves it:
    ja .cell                        ; 3, 2, 1 and then the empty slot
    mov ah, TI_RVCARD + 3
    sub ah, al
    mov [ti_cfade], ah
    push ax
    mov ax, [ti_rvcard]
    call ti_card_draw
    pop ax
    mov byte [ti_cfade], 0
.cell:
    cmp al, TI_RVCELL               ; --- THE CHARACTER, as the sparks pour in
    jb .timed
    cmp al, TI_RVEND
    jae .nums
    sub al, TI_RVCELL - 1
    call ti_rv_cell
    jmp short .timed
.nums:
    jne .done
    call ti_rv_nums                 ; ...its NUMBERS a frame after it is whole
    jmp short .timed
.done:
    call ti_res_mine                ; ...and the gold it cost off the HUD, a
    call ti_rv_home                 ; frame after that: the two were ~50 ms of
    mov byte [ti_rv], 0             ; one frame. Done: the wheel has the cell
.timed:                             ; back
    call ti_pit                     ; THE PRICE OF THIS FRAME'S REVEAL, the
    mov bx, [ti_rvp0]               ; erase at the top of the frame included:
    sub bx, ax                      ; the next frame's credit pays it first
    add bx, [ti_rvera]              ; (ti_rv_cost). PIT counts to us as
    mov ax, bx                      ; ti_cal_card converts them
    mov bx, 8381
    mul bx
    mov bx, 10000
    div bx
    mov [ti_rvlast], ax
    pop dx
    pop bx
.out:
    pop ax
    ret

; ti_rv_frombank - the played card's BANK (ti_card_bank) into ti_cfband as
; the fade's picture: the hovered twin if it is the hovered card, the resting
; one otherwise. CF=1 if it has no bank (ti_card_draw composes it instead).
; in: AX = the card. Preserves every register.
ti_rv_frombank:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push ds
    push es
    mov si, ax
    cmp byte [si + ti_cvalid], 0
    je .none
    mov [ti_cardi], ax
    call ti_card_pos
    mov [ti_cposx], ax
    mov [ti_cardy], bx
    call ti_card_geo                ; the geometry the fade will blit with
    call ti_card_slot               ; SI = the resting bank
    mov ax, [ti_cardi]
    cmp ax, [ti_hover]
    jne .rest
    add si, TI_HAND * TI_CARDBANDMAX
.rest:
    mov ax, [ti_cbs]
    mul word [ti_cbrows]
    mov cx, ax
    push ds
    pop es
    mov di, ti_cfband
    call ti_ess                     ; ES = the scratch part...
    push es
    pop ds                          ; ...as the source
    push cs                         ; (the package's own segment: the near
    pop es                          ; model)
    cld
    rep movsb
    pop es
    pop ds
    mov byte [ti_cfsave], 1
    clc
    jmp short .out2
.none:
    pop es
    pop ds
    stc
.out2:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_cost - AX = the model's price, in microseconds, of this frame's reveal
; work, which the wheel's credit pays before any idle does (SPEC.md 97.5).
; The same units as everything else it pays for: an arrival a call and rows at
; the calibrated row rate.
; Preserves every other register.
; -----------------------------------------------------------------------------
ti_rv_cost:
    push bx
    push dx
    xor ax, ax
    cmp byte [ti_rv], 0
    jne .rv
    cmp word [ti_atkcell], -1       ; ...and the played cell's owed frames
    je .out                         ; after it, one a frame (ti_rv_atk)
    mov ax, [ti_rvlast]
    jmp short .out
.rv:
    mov ax, [ti_rvlast]             ; WHAT THE LAST FRAME OF IT REALLY TOOK,
    or ax, ax                       ; from the PIT (ti_rv_step): the model
    jnz .out                        ; below priced a blit and not the thin in
    xor ax, ax                      ; front of it or a pose's build, and the
                                    ; idle spent the difference - frames of
                                    ; 50-58 ms and the music two ticks at a
                                    ; time. The first frame has only this:
    mov ax, [ti_arrus]              ; the trail: every spark twice, down and up
    mov bx, 2 * TI_RVSPK            ; - and on the last frame, which has none,
    mul bx                          ; the numbers, which cost about as much
    mov bx, ax
    mov al, [ti_rvt]                ; the frame this one is about to draw
    inc al
    cmp al, TI_RVCARD + 3
    ja .cell
    mov ax, [ti_cbrows]             ; the card's band - composed at the key,
    mul word [ti_rowus]             ; so rows and an arrival
    add bx, ax
    add bx, [ti_arrus]
    jmp short .have
.cell:
    cmp al, TI_RVCELL
    jb .have
    mov ax, [ti_bh]                 ; the cell's band
    mul word [ti_rowus]
    add bx, ax
    add bx, [ti_arrus]
.have:
    mov ax, bx
.out:
    pop dx
    pop bx
    ret

; ti_rv_cost_sub - AX = the idle's credit AX less what the reveal owes it
; this frame, floored at nothing. Preserves every other register.
;
; THE IDLE PAYS FOR THE REVEAL, ALL OF IT (SPEC.md 97.4.11.1). It used to pay
; only what a "slack" could not - TI_FRAMEMAX of the tick less the other
; lanes' allowances and the idle's own credit, ~11 ms - because a reveal
; charged in full slowed the board while that room sat unused. The room was a
; MODEL's: measured on a 4.77 MHz VGA the reveal's frames ran 45-58 ms, the
; wheel spending its whole credit on top of a reveal it believed fitted, and
; the music went two ticks at a time. The cost is MEASURED now (ti_rv_cost),
; so the board's breathing slows for the half second a reveal lasts and the
; frame keeps its tick.
ti_rv_cost_sub:
    push bx
    mov bx, ax                      ; BX = the idle's credit
    call ti_rv_cost                 ; AX = what the reveal costs
    sub bx, ax
    jnc .have
    xor bx, bx
.have:
    mov ax, bx
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_rv_sparks - frame [ti_rvt] of the trail: the head at t/T of the way, and
; each spark behind it a quarter of a frame further back, smaller the older it
; is. A spark that has reached the cell is poured in and drawn no more, which
; is how the tail follows the head home. Every rect is recorded for the erase.
; Preserves every register.
;
; THE TWIRL IS GONE (SPEC.md 97.4.11.1). Each spark ORBITED the line, three to
; seven pixels out and a turn every ~five frames - and a reveal is nine frames
; at the rate a reveal runs, so no spark was ever seen going round: the owner
; saw a ragged line and asked whether it twirled at all. A comet down the
; line is what was on the glass anyway, without the table and the IMULs.
; -----------------------------------------------------------------------------
ti_rv_sparks:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov word [ti_rvn], 0
    mov word [ti_rvk], TI_RVSPK
    mov si, ti_rvsp
    call ti_rv_trail
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_rv_trail - one trail of [ti_rvk] sparks, [ti_rvx0],[ti_rvy0] to
; [ti_rvx1],[ti_rvy1] at frame [ti_rvt], appended at SI to the record
; ([ti_rvn] counts it). out: SI past what it recorded. Preserves the rest.
ti_rv_trail:
    push ax
    push bx
    push cx
    push dx
    push di
    push bp
    xor bp, bp                      ; BP = k, how far behind the head
.spark:
    cmp bp, [ti_rvk]
    jb .born
    jmp .out
.born:
    mov al, [ti_rvt]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    sub ax, bp
    jg .aged
    jmp .next                       ; not born yet: the trail grows from the card
.aged:
    cmp ax, 4 * TI_RVTRAVEL
    jbe .flying
    jmp .next                       ; ...and home: poured into the cell
.flying:
    mov cx, ax                      ; CX = the spark's share of the way...
    mov di, 4 * TI_RVTRAVEL         ; ...in quarter frames
    mov ax, [ti_rvx0]
    mov bx, [ti_rvx1]
    call ti_rv_lerp
    mov [ti_rvpx], ax
    mov ax, [ti_rvy0]
    mov bx, [ti_rvy1]
    call ti_rv_lerp
    mov [ti_rvpy], ax
    mov cx, 5                       ; the HEAD: five pixels, and the tail
    or bp, bp                       ; behind it three and then two, all ON
    jz .size                        ; the line - a comet and not a spiral
    mov cx, 3
    cmp bp, 2
    jbe .size
    dec cx
.size:
    mov ax, [ti_rvpx]               ; the rect, CX pixels square about it
    mov bx, [ti_rvpy]
    mov dx, cx
    shr dx, 1
    sub ax, dx
    jns .x0
    xor ax, ax
.x0:
    sub bx, dx
    jns .y0
    xor bx, bx
.y0:
    dec cx
    mov dx, bx
    add dx, cx
    add cx, ax
    mov [si], ax
    mov [si + 2], bx
    mov [si + 4], cx
    mov [si + 6], dx
    call OSAPI_GFX_XOR_FILL
    add si, 8
    inc word [ti_rvn]
.next:
    inc bp
    jmp .spark
.out:
    pop bp
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_other - a frame of an UNDO's fade (ti_rv = 2) or a SWAP's sparks
; (ti_rv = 3), LAST in a frame like the reveal's (SPEC.md 97.12.10.7).
; Preserves every register.
;
; AN UNDO IS THE REVEAL BACKWARDS, WITH NO SPARKS: the character dissolves out
; of its cell - pose 0 over the cell's ground at dither levels 3, 2, 1 and the
; ground alone, the reveal's own ti_rv_cell - while its card comes back into
; the hand at 1, 2, 3 and whole, the bank copied out fresh for each step and
; thinned (ti_rv_cardfade). A SWAP is two short comets CROSSING, one each way
; between the two cells, and then the cells are drawn swapped. In both, the
; cells the edit changed wait for the end (tg_sync1 skips them), and the
; frame after the last draws them: tg_sync.
; -----------------------------------------------------------------------------
ti_rv_other:
    push ax
    push bx
    push dx
    call ti_pit                     ; TIMED, for the next frame's credit
    mov [ti_rvp0], ax
    inc byte [ti_rvt]
    mov al, [ti_rvt]
    cmp byte [ti_rv], 3
    je .swap
    cmp al, 4                       ; --- UNDO: frames 1-4, then the sync ---
    ja .end
    push ax
    mov ah, 4
    sub ah, al
    mov al, ah                      ; the cell: 3, 2, 1, 0
    call ti_rv_cell
    pop ax
    push ax
    mov ax, [ti_rvcard]             ; the card: 1, 2, 3, whole
    cmp byte [ti_rvt], 4
    je .whole
    mov bl, [ti_rvt]
    call ti_card_fadein
    pop ax
    jmp short .timed
.whole:
    call ti_card_fast
    pop ax
    jmp short .timed
.swap:
    cmp al, TI_RVTRAVEL + 2         ; --- SWAP: the trails, then the sync ----
    ja .end
    push si
    mov word [ti_rvn], 0
    mov word [ti_rvk], 3
    mov si, ti_rvsp
    call ti_rv_trail                ; A to B...
    call ti_rv_ends
    call ti_rv_trail                ; ...and B to A
    call ti_rv_ends
    pop si
    jmp short .timed
.end:
    mov byte [ti_rv], 0             ; the edit's cells, drawn now - the
    call tg_sync                    ; undone one is ground, the swapped two
                                    ; each other's
.timed:
    call ti_pit
    mov bx, [ti_rvp0]
    sub bx, ax
    add bx, [ti_rvera]
    mov ax, bx
    mov bx, 8381
    mul bx
    mov bx, 10000
    div bx
    mov [ti_rvlast], ax
    pop dx
    pop bx
    pop ax
    ret

; ti_rv_ends - the trail's two ends swapped. Preserves every register.
ti_rv_ends:
    push ax
    mov ax, [ti_rvx0]
    xchg ax, [ti_rvx1]
    mov [ti_rvx0], ax
    mov ax, [ti_rvy0]
    xchg ax, [ti_rvy1]
    mov [ti_rvy0], ax
    pop ax
    ret

; ti_rv_centre - AX = a cell -> AX, BX = its figure band's centre on the
; glass. Preserves every other register.
ti_rv_centre:
    push cx
    push dx
    push word [ti_ci]
    mov [ti_ci], ax
    xor dx, dx
    mov cx, TI_ROWS
    div cx
    call ti_col_insx                ; AX = the band's inset
    mov cx, ax
    call ti_cell_xy                 ; AX, BX = the cell
    add ax, cx
    mov cx, [ti_bs]
    shl cx, 1
    shl cx, 1
    add ax, cx                      ; + BS x 8 / 2
    add bx, [ti_insy]
    mov cx, [ti_bh]
    shr cx, 1
    add bx, cx
    pop word [ti_ci]
    pop dx
    pop cx
    ret

; ti_rv_swap_go - cells AX and BX were SWAPPED: their sparks cross before
; they are drawn (ti_rv = 3). A window callback, the lock held. Preserves
; every register.
ti_rv_swap_go:
    push ax
    push bx
    mov [ti_rvcell], ax
    mov [ti_rvcell2], bx
    push bx
    call ti_rv_centre
    mov [ti_rvx0], ax
    mov [ti_rvy0], bx
    pop ax
    call ti_rv_centre
    mov [ti_rvx1], ax
    mov [ti_rvy1], bx
    mov byte [ti_rvt], 0
    mov word [ti_rvn], 0
    mov word [ti_rvlast], 0
    mov byte [ti_rv], 3
    pop bx
    pop ax
    ret

; ti_rv_undo_go - the PLAY that stood in cell AX, from hand slot BX, was
; taken back: it dissolves out and its card comes home (ti_rv = 2). A window
; callback, the lock held. Preserves every register.
ti_rv_undo_go:
    mov [ti_rvcell], ax
    mov word [ti_rvcell2], -1
    mov [ti_rvcard], bx
    mov byte [ti_rvt], 0
    mov word [ti_rvn], 0
    mov word [ti_rvlast], 0
    mov byte [ti_rv], 2
    ret

; ti_card_fadein - hand card AX at dither level BL (1-3) out of its BANK: the
; bank copied fresh (ti_rv_frombank) and thinned toward the panel's black,
; then put down. A card with no bank is drawn whole. Preserves every register.
ti_card_fadein:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    push es
    call ti_rv_frombank
    jnc .have
    call ti_card_fast
    jmp short .out
.have:
    mov [ti_cfade], bl
    call ti_rv_cardfade
    mov byte [ti_cfade], 0
    mov byte [ti_cfsave], 0
    push ds
    pop es
    mov si, ti_cfband
    mov ax, [ti_cbx]
    mov bx, [ti_cardy]
    mov cx, [ti_cbbw]
    mov dx, [ti_cbrows]
    mov bp, [ti_cbs]
    call OSAPI_GFX_BLIT1
.out:
    pop es
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_rv_lerp - AX = AX + (BX - AX) x CX / DI, signed. Preserves every other
; register.
ti_rv_lerp:
    push dx
    push si
    mov si, ax
    mov ax, bx
    sub ax, si
    imul cx
    idiv di
    add ax, si
    pop si
    pop dx
    ret

; -----------------------------------------------------------------------------
; ti_rv_cell - cell [ti_rvcell]'s band at dissolve level AL, composed and put
; down: 0 is its ground alone, 4 the character whole. Preserves every
; register.
;
; A 4x4 ORDERED DITHER between two pictures the arena already holds: the
; cell's pose 0, and its column's strip under the same band. Each byte is
; (pose AND mask) OR (ground AND NOT mask) - one pass, one commit, and no
; pixel written twice.
; -----------------------------------------------------------------------------
ti_rv_cell:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov bp, [ti_cslot]
    cmp bp, TI_RVMAX
    jbe .fits
    jmp .out                        ; a band the buffer cannot hold keeps what
.fits:                              ; the wheel will draw at the end
    xor ah, ah
    shl ax, 1
    shl ax, 1
    add ax, ti_rv_dith
    mov [ti_rvdp], ax               ; this level's four row masks
    push word [ti_ci]
    push word [ti_pi]
    mov ax, [ti_rvcell]
    mov [ti_ci], ax
    mov word [ti_pi], 0
    call ti_cellpose_addr           ; DI = pose 0, in the arena
    call ti_cell_gsrc               ; [ti_gsrc] = its ground, in the strip
    mov si, [ti_gsrc]
    mov es, [ti_aseg]
    mov bx, ti_rvband
    mov word [ti_rvrow], 0
.row:
    mov ax, [ti_rvrow]
    cmp ax, [ti_bh]
    jae .done
    push si
    and ax, 3
    add ax, [ti_rvdp]
    push bx
    mov bx, ax
    mov al, [bx]                    ; this row's mask, in both halves of a
    pop bx                          ; word: BP = mask, DX = its complement
    mov ah, al
    mov bp, ax
    not ax
    mov dx, ax
    mov cx, [ti_bs]
    shr cx, 1                       ; A WORD AT A TIME: a band is a whole
.word:                              ; number of words on every surface
    mov ax, [es:si]                 ; the ground where the mask is clear...
    and ax, dx
    mov [bx], ax
    mov ax, [es:di]                 ; ...and the character where it is set
    and ax, bp
    or [bx], ax
    add si, 2
    add di, 2
    add bx, 2
    loop .word
    pop si
    add si, [ti_sb]
    inc word [ti_rvrow]
    jmp short .row
.done:
    call ti_cell_xy                 ; AX, BX = the cell - and the band inset
    push ax                         ; the same as ti_feature's
    mov ax, [ti_ci]
    xor dx, dx
    mov cx, TI_ROWS
    div cx
    call ti_col_insx
    mov cx, ax
    pop ax
    push ax
    push bx
    add ax, cx
    add bx, [ti_insy]
    push ds
    pop es
    mov si, ti_rvband
    call ti_shown_set               ; the cell shows the dissolve now
    mov cx, [ti_bs]
    shl cx, 1
    shl cx, 1
    shl cx, 1
    mov dx, [ti_bh]
    mov bp, [ti_bs]
    call OSAPI_GFX_BLIT1
    pop bx
    pop ax

    pop word [ti_pi]
    pop word [ti_ci]
.out:
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_rv_home - hand cell [ti_rvcell] back to the wheel AS IT STANDS: the glass
; shows its pose 0, whole, so that is its clock and its shown band. Preserves
; every register.
;
; THE WHEEL KEPT TURNING ITS CLOCK through the reveal while skipping its
; commits, so the clock came out four-odd poses from the glass - and the next
; DIRTY RECT committed only the rows that transition moved, over a picture
; that was not the one it moved them from.
ti_rv_home:
    push bx
    push di
    push es
    push word [ti_ci]
    push word [ti_pi]
    mov bx, [ti_rvcell]
    mov byte [bx + ti_clock], 0
    mov [ti_ci], bx
    mov word [ti_pi], 0
    call ti_cellpose_addr           ; DI = its pose 0, in the arena
    mov es, [ti_aseg]
    push si
    mov si, di
    call ti_shown_set
    pop si
    pop word [ti_pi]
    pop word [ti_ci]
    pop es
    pop di
    pop bx
    ret

; ti_rv_nums - cell [ti_rvcell]'s numbers, the new card's. Preserves every
; register.
ti_rv_nums:
    push ax
    push bx
    push word [ti_ci]
    mov ax, [ti_rvcell]
    mov [ti_ci], ax
    call ti_cell_xy
    call ti_cellnum
    pop word [ti_ci]
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_cardfade - the fading card, THINNED IN PLACE to dither level
; [ti_cfade] (3, 2, 1) toward the panel's black. The first call - the play's,
; which puts nothing down - banks the composition in ti_cfband and thins
; nothing. Preserves every register.
;
; THE LEVELS NEST: every set bit of level 1 is set in 2 and every one of 2 in
; 3, so thinning the banked card at 3, then 2, then 1 is the same picture as
; thinning a fresh copy at each - and needs no copy. Each step copied the whole
; 800-byte bank back first, ~1.5 ms of a frame that has the sparks in it.
; -----------------------------------------------------------------------------
ti_rv_cardfade:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    cmp byte [ti_cfsave], 0         ; the PLAY banks the composition
    jne .thin
    push ds
    pop es
    mov si, ti_cardband
    mov di, ti_cfband
    mov cx, TI_CARDBANDMAX / 2
    cld
    rep movsw
    mov byte [ti_cfsave], 1
    jmp .out
.thin:
    mov al, [ti_cfade]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    add ax, ti_rv_dith
    mov bx, ax                      ; BX = this level's four row masks
    mov cx, [ti_cbs]                ; UNROLLED: the row's words are ANDed by a
    shr cx, 1                       ; run of `and [di+n], ax` entered part
    cmp cx, TI_THMAX                ; (a band wider than the run is thinned
    jbe .wok                        ; across the run's width and no further:
    mov cx, TI_THMAX                ; entered before its first instruction it
.wok:                               ; would run the code in front of it)
    mov ax, TI_THMAX                ; way down, so there is no `loop` a word -
    sub ax, cx                      ; the loop was most of the cost, ~13 ms of
    mov cx, ax                      ; a VGA card a step against ~6 now
    shl ax, 1
    add ax, cx
    add ax, .unroll
    mov [ti_thjmp], ax
    mov di, [ti_cbase]              ; the CARD's rows: the band's TI_HLIFT above
    sub di, ti_cardband             ; a portrait card are ground and stay so
    mov ax, di
    xor dx, dx
    div word [ti_cbs]
    mov dx, ax                      ; DX = the band row (the dither's phase)
    add di, ti_cfband
    mov si, [ti_cardh]
    add si, dx                      ; SI = the row to stop at
.row:
    cmp dx, si
    jae .out
    push si
    mov si, dx
    and si, 3
    mov al, [bx + si]
    mov ah, al
    pop si
    jmp word [ti_thjmp]
.unroll:
%assign ti_th TI_THMAX - 1
%rep TI_THMAX
    and [byte di + ti_th * 2], ax
%assign ti_th ti_th - 1
%endrep
    test byte [ti_cbs], 1           ; ...and an odd band's last byte
    jz .rowdone
    push si
    mov si, [ti_cbs]
    dec si
    add si, di
    and [si], al
    pop si
.rowdone:
    add di, [ti_cbs]
    inc dx
    jmp short .row
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; A 4x4 BAYER MATRIX at five levels - 0/16, 4, 8, 12 and 16/16 - one byte a
; row, the 4-pixel pattern twice. A set bit is the NEW picture.
ti_rv_dith:
    db 000h, 000h, 000h, 000h
    db 0AAh, 000h, 0AAh, 000h
    db 0AAh, 055h, 0AAh, 055h
    db 0FFh, 055h, 0FFh, 055h
    db 0FFh, 0FFh, 0FFh, 0FFh

ti_rv:      db 0                    ; 1 while a reveal runs
ti_rvt:     db 0                    ; the frame within the phase
ti_rvfull:  db 0                    ; an expose landed on the sparks
ti_played:  db 0                    ; hand slots EMPTY: played, or past the
                                    ; hand's end (tigame.inc's tg_views)
ti_cfade:   db 0                    ; ti_card_draw's dissolve level, or 0
ti_cfsave:  db 0                    ; ...and is the card's composition banked
ti_rvcard:  dw 0
ti_rvcell:  dw 0
ti_rvcell2: dw -1                   ; a SWAP's other cell (ti_rv = 3)
ti_rvk:     dw TI_RVSPK             ; sparks a trail
ti_rvx0:    dw 0
ti_rvy0:    dw 0
ti_rvx1:    dw 0
ti_rvy1:    dw 0
ti_rvpx:    dw 0
ti_rvpy:    dw 0
ti_rvdp:    dw 0
ti_rvrow:   dw 0                    ; the dissolve's band row
ti_atkcell: dw -1                   ; the played cell whose attack frames are
ti_atkfr:   dw 0                    ; still owed, and the next of them
ti_rvn:     dw 0                    ; sparks on the glass
ti_rvp0:    dw 0                    ; the PIT when the timed stretch began
ti_rvera:   dw 0                    ; ...the erase's counts, this frame
ti_rvlast:  dw 0                    ; ...and the last frame's reveal, in us
ti_thjmp:   dw 0                    ; ti_rv_cardfade's way into its unrolled run
ti_rvsp:    times TI_RVSPK * 4 dw 0
ti_rvband:  times TI_RVMAX db 0
