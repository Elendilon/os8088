; =============================================================================
; os8088 - apps/tithe/tirv.inc
;
; THE REVEAL (SPEC.md 97.4.11, TITHE-PLAN 16.2 item 7): a card played from the
; hand reaches its cell. Three things, one after another, and the whole of it
; is shorter than a clash:
;
;   1. a TRAIL OF SPARKS from the card to the cell - TI_RVTRAVEL frames;
;   2. the character DISSOLVING IN over its cell's ground, through three
;      ordered-dither steps, with its numbers arriving on the last;
;   3. the card DISSOLVING OUT of the hand the same way, a step behind, and
;      leaving an empty slot.
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
TI_RVSTEPS  equ 5                 ; frames of the dissolve, the card's included
TI_RVSPK    equ 12                ; sparks a frame: the head and eleven behind,
                                  ; a quarter frame apart - a tail nearly three
                                  ; frames long
TI_RVMAX    equ 384               ; the largest cell band (TI_ARENAKB's own)

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
; ti_rv_key - SPEC.md 97.7's `V`: play a card. The hovered one, else the first
; still in the hand, into the next of P1's cells in the row the FRONT/REAR
; toggle names - and an empty hand is dealt again.
; in:  a window callback, the gfx lock held. Preserves every register.
; -----------------------------------------------------------------------------
ti_rv_key:
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
    mov cl, al                      ; ...it leaves the hand
    mov al, 1
    shl al, cl
    or [ti_played], al
    mov word [ti_hover], -1         ; ...and stops being the hovered card, so
                                    ; the wheel stops animating its unit

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
    call ti_cell_build              ; ~90 ms on a windowed VGA, before a spark
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
    mov ax, [ti_cardw]              ; the card's centre
    shr ax, 1
    add ax, [ti_cardx]
    mov [ti_rvx0], ax
    mov ax, [ti_rvcard]
    call ti_card_y                  ; BX = its top
    mov ax, [ti_cardh]
    shr ax, 1
    add bx, ax
    mov [ti_rvy0], bx

    ; --- the CARD is composed now and banked for its fade, rather than on
    ; the fade's first step: ~35 ms of an 8088 is room a trail frame has not
    ; got, and here it is latency before the first spark instead of a stutter
    mov byte [ti_cfsave], 0
    mov byte [ti_cfade], TI_RVSTEPS - 2
    mov word [ti_calconly], 1       ; compose, bank - and put nothing down
    mov ax, [ti_rvcard]
    call ti_card_draw
    mov word [ti_calconly], 0
    mov byte [ti_cfade], 0

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
    cmp byte [ti_rv], 1
    jne .fade
    call ti_rv_sparks               ; --- 1: THE TRAIL ------------------------
    cmp byte [ti_rvt], TI_RVTRAVEL
    jb .out
    mov byte [ti_rv], 2
    mov byte [ti_rvt], 0
    jmp short .out
.fade:
    mov al, [ti_rvt]                ; --- 2: THE CHARACTER, levels 1 to 4 -----
    cmp al, 4
    ja .nums
    call ti_rv_cell
    jmp short .card
.nums:
    call ti_rv_nums                 ; ...and its NUMBERS a frame after it is
.card:                              ; whole, on the step that has room for them
    cmp al, 2                       ; --- 3: THE CARD, a step behind: 3, 2, 1,
    jb .out                         ; and then the empty slot
    mov ah, TI_RVSTEPS
    sub ah, al
    mov [ti_cfade], ah
    mov ax, [ti_rvcard]
    call ti_card_draw
    mov byte [ti_cfade], 0
    cmp byte [ti_rvt], TI_RVSTEPS
    jb .out
    mov byte [ti_rv], 0             ; done: the wheel has the cell back
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_rv_cost - AX = the model's price, in microseconds, of this frame's reveal
; work, which the wheel's credit pays before any idle does (SPEC.md 97.5).
; The same units as everything else it pays for: an arrival a call, rows at
; the calibrated row rate, and the card composition ti_cal_card measured.
; Preserves every other register.
; -----------------------------------------------------------------------------
ti_rv_cost:
    push bx
    push dx
    xor ax, ax
    cmp byte [ti_rv], 0
    je .out
    mov ax, [ti_arrus]              ; the trail: every spark twice, down and up
    mov bx, 2 * TI_RVSPK
    mul bx
    cmp byte [ti_rv], 1
    je .out
    mov ax, [ti_bh]                 ; the dissolve: the cell's band and the
    add ax, [ti_cardh]              ; card's, and composing the card
    mul word [ti_rowus]
    add ax, [ti_arrus]
    add ax, [ti_arrus]
    add ax, [ti_ccardus]
.out:
    pop dx
    pop bx
    ret

; ti_rv_cost_sub - AX = AX less ti_rv_cost, floored at nothing. Preserves
; every other register.
ti_rv_cost_sub:
    push bx
    mov bx, ax
    call ti_rv_cost
    sub bx, ax
    jnc .have
    xor bx, bx
.have:
    mov ax, bx
    pop bx
    ret

; -----------------------------------------------------------------------------
; ti_rv_sparks - frame [ti_rvt] of the trail: the head at t/T of the way, and
; each spark behind it a quarter of a frame further back, jittered off the
; line and smaller the older it is. Every rect is recorded for the erase.
; Preserves every register.
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
    jle .next                       ; not born yet: the trail grows from the card
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
    mov cx, 3                       ; ...a SPARK: off it, and further off and
    cmp bp, 3                       ; smaller the older it is - the trail
    jbe .jit                        ; spreads as it fades
    mov cx, 7
    cmp bp, 7
    jbe .jit
    mov cx, 15
.jit:
    call ti_rv_rand
    add [ti_rvpx], ax
    call ti_rv_rand
    add [ti_rvpy], ax
    mov cx, 3
    cmp bp, 3
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

; ti_rv_rand - AX = a signed offset off a 16-bit Galois LFSR: (lfsr AND CX)
; less half of CX + 1, so CX = 3, 7 or 15 is -2..1, -4..3 or -8..7. Preserves
; every other register.
ti_rv_rand:
    mov ax, [ti_rvseed]
    shr ax, 1
    jnc .keep
    xor ax, 0B400h
.keep:
    mov [ti_rvseed], ax
    and ax, cx
    push cx
    inc cx
    shr cx, 1
    sub ax, cx
    pop cx
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
    xor bp, bp                      ; BP = the band row
.row:
    cmp bp, [ti_bh]
    jae .done
    push si
    push bx
    mov bx, bp
    and bx, 3
    add bx, [ti_rvdp]
    mov dh, [bx]                    ; DH = this row's mask, DL its complement
    pop bx
    mov dl, dh
    not dl
    mov cx, [ti_bs]
.byte:
    mov al, [es:di]                 ; the character where the mask is set...
    and al, dh
    mov ah, [es:si]                 ; ...and the ground where it is not
    and ah, dl
    or al, ah
    mov [bx], al
    inc si
    inc di
    inc bx
    loop .byte
    pop si
    add si, [ti_sb]
    inc bp
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
; ti_rv_cardfade - thin the card band at ti_cardband to dither level
; [ti_cfade] (3, 2, 1), toward the panel's black. Preserves every register.
; -----------------------------------------------------------------------------
ti_rv_cardfade:
    push ax
    push bx
    push cx
    push dx
    push di
    cmp byte [ti_cfsave], 0         ; the FIRST step banks the composition
    jne .banked
    push si
    push es
    push ds
    pop es
    mov si, ti_cardband
    mov di, ti_cfband
    mov cx, TI_CARDBANDMAX / 2
    cld
    rep movsw
    pop es
    pop si
    mov byte [ti_cfsave], 1
.banked:
    mov al, [ti_cfade]
    xor ah, ah
    shl ax, 1
    shl ax, 1
    add ax, ti_rv_dith
    mov bx, ax
    mov di, ti_cardband
    xor dx, dx
.row:
    cmp dx, [ti_cardh]
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
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ti_rv_cardget - the fading card's banked composition back into ti_cardband.
; Preserves every register.
ti_rv_cardget:
    push cx
    push si
    push di
    push es
    push ds
    pop es
    mov si, ti_cfband
    mov di, ti_cardband
    mov cx, TI_CARDBANDMAX / 2
    cld
    rep movsw
    pop es
    pop di
    pop si
    pop cx
    ret

; A 4x4 BAYER MATRIX at five levels - 0/16, 4, 8, 12 and 16/16 - one byte a
; row, the 4-pixel pattern twice. A set bit is the NEW picture.
ti_rv_dith:
    db 000h, 000h, 000h, 000h
    db 0AAh, 000h, 0AAh, 000h
    db 0AAh, 055h, 0AAh, 055h
    db 0FFh, 055h, 0FFh, 055h
    db 0FFh, 0FFh, 0FFh, 0FFh

ti_rv:      db 0                    ; 0 idle, 1 the trail, 2 the dissolve
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
ti_rvn:     dw 0                    ; sparks on the glass
ti_rvseed:  dw 0ACE1h
ti_rvsp:    times TI_RVSPK * 4 dw 0
ti_rvband:  times TI_RVMAX db 0
ti_cellcard:
%assign ti_i 0
%rep TI_CELLS
    db ti_i % TI_HAND
%assign ti_i ti_i + 1
%endrep
