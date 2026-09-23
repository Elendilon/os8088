; =============================================================================
; os8088 - apps/tithe/tirv.inc
;
; THE REVEAL (SPEC.md 97.4.11, TITHE-PLAN 16.2 item 7): a card played from the
; hand reaches its cell. Three things, OVERLAPPED, and the whole of it is
; nine frames where a clash is sixteen:
;
;   1. a TRAIL OF SPARKS from the card to the cell, TWIRLING about the line
;      as it flies - the head arrives on frame TI_RVTRAVEL and the tail pours
;      in over the two after;
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
TI_RVEND    equ 9                 ; its numbers, and the reveal is over
TI_RVSPK    equ 8                 ; sparks a frame: the head and seven behind,
                                  ; a quarter frame apart - a tail two frames
                                  ; long. It was twelve, and the four it lost
                                  ; are what lets the idle keep breathing
                                  ; through a reveal rather than stopping
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
; still in the hand) into the next of P1's cells in the row the FRONT/REAR
; toggle names. A CLICK on a card is this, and so is `V`.
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
    jae .deal
    call ti_rv_played
    jnc .have
    inc ax
    jmp short .find
.deal:
    mov byte [ti_played], 0         ; wave 1a has no deck: the hand comes back
    xor ax, ax
.redraw:
    cmp ax, [ti_cardn]
    jae .out
    call ti_card_draw
    inc ax
    jmp short .redraw
.have:
    mov [ti_rvcard], ax
    call ti_rv_atk_flush            ; the LAST play's attack frames, if any are
                                    ; still owed (ti_rv_atk)
    mov cl, al                      ; ...it leaves the hand
    mov al, 1
    shl al, cl
    or [ti_played], al

    ; --- the CARD is composed now and banked for its fade, AS IT IS ON THE
    ; GLASS - hovered, if it is - rather than on the fade's first step: ~22 ms
    ; of an 8088 is room a trail frame has not got, and here it is latency
    ; before the first spark instead of a stutter in the middle
    mov byte [ti_cfsave], 0
    mov byte [ti_cfade], 3
    mov word [ti_calconly], 1       ; compose, bank - and put nothing down
    mov ax, [ti_rvcard]
    call ti_card_draw
    mov word [ti_calconly], 0
    mov byte [ti_cfade], 0
    mov word [ti_hover], -1         ; ...and it stops being the hovered card,
                                    ; so the wheel stops animating its unit

    ; --- WHERE: P1's column for the toggle's row, the next lane in turn ----
    xor ax, ax                      ; REAR is column 0
    cmp word [ti_row], TI_ROW_FRONT
    jne .col
    mov ax, 1                       ; ...FRONT is column 1
.col:
    mov bx, TI_ROWS
    mul bx
    mov bl, [ti_rvlane]
    xor bh, bh
    add ax, bx
    mov [ti_rvcell], ax
    inc bl                          ; the next reveal takes the next lane
    cmp bl, TI_ROWS
    jb .lane
    xor bl, bl
.lane:
    mov [ti_rvlane], bl

    ; --- WHO: the card now stands there, composed into the cell ------------
    mov bx, [ti_rvcell]
    mov al, [ti_rvcard]
    mov [ti_cellcard + bx], al
    push word [ti_ci]
    mov [ti_ci], bx
    mov word [ti_cfbeg], 0          ; ITS IDLE POSES ONLY: the four attack
    mov word [ti_cfend], TI_POSES   ; frames are nobody's until a clash, so they
    call ti_cell_build              ; follow the reveal a frame at a time
    mov word [ti_cfend], 2 * TI_POSES ; (ti_rv_atk) instead of standing
    mov [ti_atkcell], bx            ; between the click and the first spark
    mov word [ti_atkfr], TI_POSES
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
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_atk - one of the played cell's owed ATTACK frames, a frame at a time
; once the reveal is over. Preserves every register.
;
; A PLAY IS THE IDLE POSES AND NOTHING ELSE, and the attack frames come after.
; Composing all eight at the click was ~81 ms of the 112 between the click and
; the first spark, and nothing needs the four attack frames until the cell
; swings. One a frame, when no reveal is running, is ~10 ms of a frame that has
; room for it; a clash, a relayout or the next play takes the rest at once
; (ti_rv_atk_flush) rather than swing with frames that are not there.
; -----------------------------------------------------------------------------
ti_rv_atk:
    cmp byte [ti_rv], 0
    jne .out
    cmp word [ti_atkcell], -1
    je .out
    push ax
    push word [ti_ci]
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
    cmp word [ti_atkfr], 2 * TI_POSES
    jb .more
    mov word [ti_atkcell], -1       ; ...all four: the cell is whole
.more:
    pop word [ti_ci]
    pop ax
.out:
    ret

; ti_rv_atk_flush - every attack frame still owed, now. Preserves every
; register.
ti_rv_atk_flush:
    push ax
    push word [ti_ci]
    mov ax, [ti_atkcell]
    cmp ax, -1
    je .out
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
    je .out
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
    jb .out
    cmp al, TI_RVEND
    jae .nums
    sub al, TI_RVCELL - 1
    call ti_rv_cell
    jmp short .out
.nums:
    call ti_rv_nums                 ; ...and its NUMBERS a frame after it is
    call ti_rv_home                 ; whole. Done: the wheel has the cell back
    mov byte [ti_rv], 0
.out:
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
    je .out
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
; THE REVEAL PAYS OUT OF THE TICK'S SLACK FIRST. The idle's credit is its
; SPEED - a share of the tick, sized for how fast a figure should breathe -
; and not the tick's spare room, so charging a reveal to it slowed the board
; while ~11 ms of every reveal frame sat unused. So the reveal is charged first
; to what no lane has claimed - TI_FRAMEMAX of the tick, less the combat and
; base lanes' allowances and the idle's own credit - and the idle pays only
; what is left over. The costs are the calibrated ones (ti_arrus, ti_rowus),
; so this is the same answer on every adapter without a constant per machine.
ti_rv_cost_sub:
    push bx
    push cx
    push dx
    mov bx, ax                      ; BX = the idle's credit
    call ti_rv_cost                 ; AX = what the reveal costs
    push ax
    mov ax, TI_FRAMEUS / 100        ; CX = the slack: the tick's usable share
    mov cx, TI_FRAMEMAX - TI_COMBAT - TI_BASESHARE
    mul cx                          ; less the other lanes'...
    sub ax, bx                      ; ...less the idle's own
    jnc .slack
    xor ax, ax
.slack:
    mov cx, ax
    pop ax
    sub ax, cx                      ; what the slack cannot cover
    jnc .over
    xor ax, ax
.over:
    sub bx, ax
    jnc .have
    xor bx, bx
.have:
    mov ax, bx
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_rv_sparks - frame [ti_rvt] of the trail: the head at t/T of the way, and
; each spark behind it a quarter of a frame further back, smaller the older it
; is and ORBITING the line - further out the older it is, and a turn round it
; every ~five frames, neighbours a third of a turn apart, so the trail TWIRLS.
; A spark that has reached the cell is poured in and drawn no more, which is
; how the tail follows the head home. Every rect is recorded for the erase.
; Preserves every register.
;
; THE TWIRL IS A TABLE: sixteen signed bytes of sine, a lookup and an IMUL a
; spark - microseconds against the ~2 ms of a spark's two XOR fills.
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
    mov si, ti_rvsp
    xor bp, bp                      ; BP = k, how far behind the head
.spark:
    cmp bp, TI_RVSPK
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
    mov cx, 5                       ; the HEAD: five pixels, on the line
    or bp, bp
    jz .size
    mov cx, 3                       ; ...a SPARK: on an ORBIT of the line,
    cmp bp, 2                       ; wider the older it is - the trail
    jbe .orbit                      ; spreads as it fades
    mov cx, 5
    cmp bp, 5
    jbe .orbit
    mov cx, 7
.orbit:
    mov al, [ti_rvt]                ; the angle: three sixteenths a frame, and
    mov bl, 3                       ; five between neighbours
    mul bl
    mov bx, bp
    mov bh, bl
    shl bl, 1
    shl bl, 1
    add bl, bh
    add al, bl
    and ax, 15
    mov bx, ax
    push bx
    mov al, [ti_rvsin + bx]         ; dy = R sin
    cbw
    imul cx
    push cx
    mov cl, 6
    sar ax, cl
    pop cx
    add [ti_rvpy], ax
    pop bx
    add bx, 4                       ; dx = R cos
    and bx, 15
    mov al, [ti_rvsin + bx]
    cbw
    imul cx
    push cx
    mov cl, 6
    sar ax, cl
    pop cx
    add [ti_rvpx], ax
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
    jmp short .out
.thin:
    mov al, [ti_cfade]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    add ax, ti_rv_dith
    mov bx, ax
    mov di, ti_cfband
    xor dx, dx
.row:
    cmp dx, [ti_cbrows]
    jae .out
    push bx
    mov ax, dx
    and ax, 3
    add bx, ax
    mov al, [bx]
    pop bx
    mov cx, [ti_cbs]
.byte:
    and [di], al
    inc di
    loop .byte
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

; sine, sixteen steps a turn, x 64
ti_rvsin:
    db 0, 24, 45, 59, 64, 59, 45, 24, 0, -24, -45, -59, -64, -59, -45, -24

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
ti_rvlane:  db 0                    ; the lane the next reveal takes
ti_played:  db 0                    ; hand cards played, a bit each
ti_cfade:   db 0                    ; ti_card_draw's dissolve level, or 0
ti_cfsave:  db 0                    ; ...and is the card's composition banked
ti_rvcard:  dw 0
ti_rvcell:  dw 0
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
ti_rvsp:    times TI_RVSPK * 4 dw 0
ti_rvband:  times TI_RVMAX db 0
ti_cellcard:
%assign ti_i 0
%rep TI_CELLS
    db ti_i % TI_HAND
%assign ti_i ti_i + 1
%endrep
