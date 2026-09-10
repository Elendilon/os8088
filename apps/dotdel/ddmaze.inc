; =============================================================================
; os8088 - apps/dotdel/ddmaze.inc
;
; THE BOARD AND ITS PICTURE (SPEC.md 93.2).
;
; A layout is 31 rows of 28 characters, written out as characters because a
; maze is a PICTURE and a nibble-packed one cannot be reviewed. `#` is wall,
; `.` a dot, `o` a power pellet, `=` the ghost-house door and a space is open
; floor with nothing on it. `tests/unit/t_ddmaze.py` reads these very bytes
; back out of this file and floods them: every layout is checked for width,
; height, four pellets, a reachable dot count, and the shared block below.
;
; --- WHAT EVERY LAYOUT SHARES, AND WHY (binding) -----------------------------
;
; Rows 9 to 19 are IDENTICAL in every layout: the ghost house, its door, the
; two columns above it the ghosts leave by, the tunnel row, and the two long
; verticals at columns 6 and 21 that carry the whole board's traffic past the
; house. Everything that knows where a ghost is born, where its eyes go home
; to, where the fruit appears and where Smiles starts reads those rows, so a
; layout that moved them would need its own copy of all of it. Changing the
; board every three levels is meant to change the CHASE, not the machinery.
;
; --- THE WALL IS THE CORRIDOR'S OUTLINE, NOT THE WALL'S FILL -----------------
;
; The ink is laid one line INTO the wall from every corridor edge, so what the
; player sees is each corridor traced in a thin line, with black inside the
; wall between two of them - which is what the arcade board looks like, and
; also what makes the sprite band cheap (ddlay.inc): the line lives in the
; wall tile and never in the corridor, so an actor's band may round out to the
; byte grid along its own corridor and still contain nothing but dots.
;
; A FILLED wall was the other candidate and loses twice. It is a screen mostly
; white on the two 1bpp adapters - the corridors read as the walls - and it
; puts ink inside the tile the band rounds into, which would cost a second
; blit per actor to keep the wall out of the actor's pen.
; =============================================================================

TT_WALL   equ 0
TT_EMPTY  equ 1
TT_DOT    equ 2
TT_PILL   equ 3
TT_DOOR   equ 4

DD_NPILL  equ 4                 ; power pellets on a board, and the layouts
                                ; are gated on exactly four (SPEC.md 93.2)
DD_NLAYS  equ 3                 ; ...and the board changes every three levels
DD_LEVLAY equ 3

; The fixed furniture of the shared block, in tiles.
DD_HOMEC  equ 13                ; above the door: where eyes go home to
DD_HOMER  equ 11
DD_HOUSER equ 14                ; the row the three penned ghosts wait on
; the pen's INTERIOR, which is six by three and open in all three layouts.
; dd_pen_ok walks a penned ghost inside this box and no further (SPEC.md 93.8.6)
DD_PENC0  equ 11
DD_PENC1  equ 16
DD_PENR0  equ 13
DD_PENR1  equ 15
DD_STARTC equ 13                ; Smiles
DD_STARTR equ 23
DD_FRUITC equ 13
DD_FRUITR equ 17

; -----------------------------------------------------------------------------
; dd_level_load - decode the layout this level uses into dd_grid
; in:  [dd_level], 1-based;  out: [dd_ndots] = dots + pellets left to eat
; Clobbers everything.
; -----------------------------------------------------------------------------
dd_level_load:
    mov al, [dd_level]
    dec al
    xor ah, ah
    mov bl, DD_LEVLAY
    div bl                          ; AL = (level-1)/3, the board's ordinal
    xor ah, ah
    mov bl, DD_NLAYS
    div bl                          ; AH = that, modulo the boards we have
    mov al, ah
    xor ah, ah
    shl ax, 1
    mov bx, ax
    mov si, [dd_lays + bx]
    mov di, dd_grid
    mov cx, DD_COLS * DD_ROWS
    xor dx, dx                      ; DX = things left to eat
    xor bx, bx                      ; BX = the tile ordinal, for the row test
.each:
    mov al, [si]
    inc si
    push ax
    mov ax, bx
    push dx
    push cx
    xor dx, dx
    mov cx, DD_COLS
    div cx                          ; AX = the row this tile is on
    pop cx
    pop dx
    cmp al, [dd_rmin]
    pop ax
    jae .live
    mov al, '#'                     ; above the slice there is nothing but wall
.live:
    inc bx
    cmp al, '#'
    je .wall
    cmp al, '.'
    je .dot
    cmp al, 'o'
    je .pill
    cmp al, '='
    je .door
    mov al, TT_EMPTY
    jmp short .put
.wall:
    mov al, TT_WALL
    jmp short .put
.door:
    mov al, TT_DOOR
    jmp short .put
.dot:
    mov al, TT_DOT
    inc dx
    jmp short .put
.pill:
    mov al, TT_PILL
    inc dx
.put:
    mov [di], al
    inc di
    loop .each
    mov [dd_ndots], dx
    call dd_pill_list
    call dd_rowoff_fill
    call dd_home_map                ; the route home, once (SPEC.md 93.8.5)
    ret

; -----------------------------------------------------------------------------
; dd_pill_list - where the power pellets are, so the blink need not look
; -----------------------------------------------------------------------------
dd_pill_list:
    push ax
    push bx
    push cx
    push si
    xor si, si                      ; SI = how many we have found
    xor bx, bx                      ; BX = the tile ordinal
    xor cx, cx
.rows:
    xor cl, cl
.cols:
    cmp byte [dd_grid + bx], TT_PILL
    jne .next
    cmp si, DD_NPILL
    jae .next
    mov [dd_pilc + si], cl
    mov [dd_pilr + si], ch
    inc si
.next:
    inc bx
    inc cl
    cmp cl, DD_COLS
    jb .cols
    inc ch
    cmp ch, DD_ROWS
    jb .rows
    mov [dd_piln], si
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_rowoff_fill - row * 28, once, so dd_tile is a table read and not a MUL
; -----------------------------------------------------------------------------
dd_rowoff_fill:
    push ax
    push bx
    push cx
    xor bx, bx
    xor ax, ax
    mov cx, DD_ROWS
.r:
    mov [dd_rowoff + bx], ax
    add ax, DD_COLS
    add bx, 2
    loop .r
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE WAY HOME (SPEC.md 93.8.5)
;
; A pair of eyes needs a route to the pen and dd_gh_aim cannot give it one: a
; greedy descent on squared distance has LOCAL MINIMA, and the ghost house is
; behind a one-tile door that no descent finds from the wrong side. Two eyes
; ping-ponged between (11,20) and (12,20) for thirty seconds, which is the
; field report - "once eaten a ghost goes out a side path, and either never
; returns or loops across the map once".
;
; So the route is worked out ONCE, when the board is decoded: a breadth-first
; walk out from the pen leaves every reachable tile holding the direction to
; step to get one tile closer. An eaten ghost then reads one byte a tile and
; walks it. It is 868 bytes of map and 1,736 of queue against a board that
; changes three times in a game, and the walk itself is ~11 ms - a hundredth
; of what a per-move search would cost on this machine.
; =============================================================================

DD_HDROOT equ 0FEh              ; the pen itself: visited, and nowhere to go
DD_HDNONE equ 0FFh              ; not reached - a wall, or a board with no pen

; -----------------------------------------------------------------------------
; dd_tindex - AX = the flat tile index of column CL, row CH (both in range)
; Preserves every other register.
; -----------------------------------------------------------------------------
dd_tindex:
    push bx
    mov bl, ch
    xor bh, bh
    shl bx, 1
    mov ax, [dd_rowoff + bx]
    mov bl, cl
    xor bh, bh
    add ax, bx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dd_home_map - fill dd_hdir by breadth-first search out from the pen
; Clobbers everything.
; -----------------------------------------------------------------------------
dd_home_map:
    push si
    push di
    mov di, dd_hdir                 ; nothing is reachable until it is reached
    mov cx, DD_COLS * DD_ROWS
    mov al, DD_HDNONE
    push es
    push ds
    pop es
    cld
    rep stosb
    pop es
    mov word [dd_hqh], 0
    mov word [dd_hqt], 0
    mov cl, DD_HOMEC
    mov ch, DD_HOUSER
    call dd_tile
    cmp al, TT_WALL
    je .out                         ; no pen on this board - the attract slice
    mov cl, DD_HOMEC
    mov ch, DD_HOUSER
    call dd_tindex
    mov di, ax
    mov byte [dd_hdir + di], DD_HDROOT
    call dd_hq_push
.loop:
    call dd_hq_pop
    jc .out
    mov [dd_hpc], cl
    mov [dd_hpr], ch
    xor bx, bx
.nb:
    mov cl, [dd_hpc]
    mov ch, [dd_hpr]
    add cl, [dd_dx + bx]
    add ch, [dd_dy + bx]
    cmp ch, 0
    jl .next
    cmp ch, DD_ROWS
    jge .next
    cmp cl, 0                       ; the tunnel wraps, and so does the route
    jge .nolo
    add cl, DD_COLS
.nolo:
    cmp cl, DD_COLS
    jl .nohi
    sub cl, DD_COLS
.nohi:
    call dd_tile
    cmp al, TT_WALL
    je .next                        ; a DOOR is passable: eyes go through it
    call dd_tindex
    mov di, ax
    cmp byte [dd_hdir + di], DD_HDNONE
    jne .next
    mov al, [dd_rev + bx]           ; from THERE, the way back here
    mov [dd_hdir + di], al
    call dd_hq_push
.next:
    inc bx
    cmp bx, 4
    jb .nb
    jmp short .loop
.out:
    pop di
    pop si
    ret

; dd_hq_push - the tile at CL, CH onto the queue. Clobbers AX/DI.
dd_hq_push:
    push bx
    call dd_tindex
    mov di, [dd_hqt]
    shl di, 1
    mov [dd_hq + di], ax
    inc word [dd_hqt]
    pop bx
    ret

; dd_hq_pop - CL, CH = the next tile, or CF = 1 when the queue is empty
dd_hq_pop:
    push ax
    push bx
    push dx
    mov ax, [dd_hqh]
    cmp ax, [dd_hqt]
    je .empty
    shl ax, 1
    mov bx, ax
    mov ax, [dd_hq + bx]
    inc word [dd_hqh]
    xor dx, dx                      ; index -> column, row
    mov bx, DD_COLS
    div bx
    mov ch, al
    mov cl, dl
    pop dx
    pop bx
    pop ax
    clc
    ret
.empty:
    pop dx
    pop bx
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; dd_tile - AL = the tile type at column CL, row CH
; in:  CL = column (signed), CH = row (signed).  Preserves BX/CX/DX/SI/DI.
;
; Rows off the board are wall. COLUMNS WRAP, because the tunnel is a real edge
; of the world and not an error: column -1 is column 27.
; -----------------------------------------------------------------------------
dd_tile:
    push bx
    push cx
    cmp ch, 0
    jl .off
    cmp ch, DD_ROWS
    jge .off
    cmp cl, 0
    jge .nolo
    add cl, DD_COLS
.nolo:
    cmp cl, DD_COLS
    jl .nohi
    sub cl, DD_COLS
.nohi:
    mov bl, ch
    xor bh, bh
    shl bx, 1
    mov bx, [dd_rowoff + bx]        ; a TABLE and not a multiply: dd_tile is
    mov al, cl                      ; the most-called routine in the game
    xor ah, ah
    add bx, ax
    mov al, [dd_grid + bx]
    pop cx
    pop bx
    ret
.off:
    mov al, TT_WALL
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; dd_iswall - CF = 1 when the tile at CL,CH blocks everything
; A DOOR IS A WALL TO SMILES AND A FLOOR TO A GHOST, so it is NOT answered
; here: the two callers that care test TT_DOOR themselves.
; -----------------------------------------------------------------------------
dd_iswall:
    call dd_tile
    cmp al, TT_WALL
    je .yes
    clc
    ret
.yes:
    stc
    ret

; =============================================================================
; THE PICTURE - a 1bpp bitmap of the board, one bit a pixel, bit 7 leftmost
;
; It is the only thing the renderer copies a band out of, and the only place a
; dot's death is recorded in pixels: eating one clears its bits here and the
; very next band that crosses the tile carries the absence with it.
; =============================================================================

; -----------------------------------------------------------------------------
; dd_bd_hrun - lay CX pixels of row BX from board x = AX, in ink DH (1 set,
;              0 clear). Pixels off the board are DROPPED, never wrapped.
; in:  AX = x (signed), BX = y (signed), CX = width, DH = ink
; out: nothing; preserves every register but the flags.
; -----------------------------------------------------------------------------
dd_bd_hrun:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    mov [dd_hrunk], dh              ; THE INK, out of DX: the row-base multiply
                                    ; below writes DX, and the ink has to
                                    ; survive it
    or cx, cx
    jle .out
    or bx, bx
    jl .out
    cmp bx, [dd_mh]
    jge .out
    or ax, ax
    jge .noleft
    add cx, ax                      ; a negative x eats into the width
    jle .out
    xor ax, ax
.noleft:
    mov di, ax                      ; NOT dx: DH is the ink for the whole run
    add di, cx
    cmp di, [dd_mw]
    jbe .noright
    mov cx, [dd_mw]
    sub cx, ax
    jle .out
.noright:
    ; ES:DI = the first byte, DL = the pixel's bit offset from the left (0..7)
    push ax
    mov ax, bx
    mul word [dd_sb]
    mov di, ax
    pop ax
    mov bx, ax
    push cx
    mov cl, 3
    shr bx, cl
    pop cx
    add di, bx
    and al, 7
    mov dl, al                      ; DL = offset into the byte, 0 = leftmost
    mov bx, [dd_bdseg]
    mov es, bx
.byte:
    mov al, 8
    sub al, dl                      ; AL = bits this byte can still take
    cmp cx, 8
    jae .nfull
    cmp al, cl
    jbe .nfull
    mov al, cl                      ; ...capped by what is left to lay
.nfull:
    mov bl, al                      ; BL = n, the bits this byte gets
    mov ah, 0FFh
    push cx
    mov cl, 8
    sub cl, bl
    shl ah, cl                      ; AH = n high bits set
    mov cl, dl
    shr ah, cl                      ; ...slid to where they belong
    pop cx
    cmp byte [dd_hrunk], 0
    je .clr
    or [es:di], ah
    jmp short .adv
.clr:
    not ah
    and [es:di], ah
.adv:
    xor bh, bh
    sub cx, bx
    jle .out
    inc di
    xor dl, dl                      ; every byte after the first starts left
    jmp short .byte
.out:
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_bd_rect - CX x BP pixels of ink DH, top-left (AX, BX)
; in:  AX = x, BX = y, CX = w, BP = h, DH = ink. Preserves every register.
; -----------------------------------------------------------------------------
dd_bd_rect:
    push bx
    push bp
    or bp, bp
    jle .out
.row:
    call dd_bd_hrun
    inc bx
    dec bp
    jnz .row
.out:
    pop bp
    pop bx
    ret

; -----------------------------------------------------------------------------
; dd_bd_wipe - zero the whole picture
; -----------------------------------------------------------------------------
dd_bd_wipe:
    push ax
    push cx
    push di
    push es
    mov ax, [dd_bdseg]
    mov es, ax
    xor di, di
    mov ax, [dd_sb]
    mul word [dd_mh]                ; 56 * 496 = 27,776: still one word
    mov cx, ax
    inc cx
    shr cx, 1
    xor ax, ax
    cld
    rep stosw
    pop es
    pop di
    pop cx
    pop ax
    ret

; =============================================================================
; DRAWING THE BOARD INTO THE PICTURE
; =============================================================================

; -----------------------------------------------------------------------------
; dd_board_render - the whole board: wall outline, dots, pellets, door
; Clobbers everything. ~200 ms on a 4.77 MHz 8088 at the VGA tile, which is a
; level-start cost and is spent behind "READY!".
; -----------------------------------------------------------------------------
dd_board_render:
    call dd_bd_wipe
    mov byte [dd_gr], 0
.rows:
    mov byte [dd_gc], 0
.cols:
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    call dd_tile
    cmp al, TT_WALL
    jne .open                       ; the wall draws nothing of its own: it is
    call dd_tile_org                ; its neighbours' outline - but its own
    call dd_wall_round              ; CORNERS are its to round (93.2.3)
    jmp short .next
.open:
    mov [dd_gt], al
    call dd_tile_org                ; [dd_gx], [dd_gy] = the tile's top-left
    call dd_walls_of
    cmp byte [dd_gt], TT_DOOR
    jne .next
    call dd_door_draw
.next:
    inc byte [dd_gc]
    cmp byte [dd_gc], DD_COLS
    jb .cols
    inc byte [dd_gr]
    cmp byte [dd_gr], DD_ROWS
    jb .rows
    call dd_bord_round              ; the playfield's own four (93.2.4)
    ret

; dd_tile_org - [dd_gx],[dd_gy] = the board pixel of tile ([dd_gc],[dd_gr])
dd_tile_org:
    push ax
    push dx
    mov al, [dd_gc]
    xor ah, ah
    mul word [dd_tw]
    mov [dd_gx], ax
    mov al, [dd_gr]
    xor ah, ah
    mul word [dd_th]
    mov [dd_gy], ax
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_walls_of - the outline this CORRIDOR tile owes, one line into each wall
;               that touches it. Clobbers AX/BX/CX/DX/BP.
;
; Each line is EXTENDED by the line thickness at an end whose perpendicular
; neighbour is also wall, which is the whole of how the corners close: two
; lines that both stop at the tile boundary leave the corner pixel unlit, and
; a maze full of pinholes is what that looks like on the glass.
; -----------------------------------------------------------------------------
dd_walls_of:
    ; bank the four neighbours as bytes: 1 = wall
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    dec cl
    call dd_iswall
    call dd_cf_byte
    mov [dd_nL], al
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    inc cl
    call dd_iswall
    call dd_cf_byte
    mov [dd_nR], al
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    dec ch
    call dd_iswall
    call dd_cf_byte
    mov [dd_nT], al
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    inc ch
    call dd_iswall
    call dd_cf_byte
    mov [dd_nB], al
    mov dh, 1                       ; every wall line is ink
    ; --- left ---------------------------------------------------------------
    cmp byte [dd_nL], 0
    je .noL
    mov ax, [dd_gx]
    sub ax, [dd_lth]
    mov bx, [dd_gy]
    mov bp, [dd_th]
    cmp byte [dd_nT], 0
    je .lnt
    sub bx, [dd_lth]
    add bp, [dd_lth]
.lnt:
    cmp byte [dd_nB], 0
    je .lnb
    add bp, [dd_lth]
.lnb:
    mov cx, [dd_lth]
    push ax
    push bx
    push cx
    push bp
    call dd_bd_rect
    pop bp
    pop cx
    pop bx
    pop ax
    cmp byte [dd_gc], 1             ; ...and THE PLAYFIELD'S OWN BORDER is a
    jne .noL                        ; DOUBLE line (SPEC.md 93.2.4)
    sub ax, [dd_bgap]
    ; ...and the OUTER line's corner needs the extension the inner one got,
    ; plus the gap it sits beyond it (SPEC.md 93.2.4): extending by [dd_lth]
    ; reaches the inner corner and leaves the outer one a notch short.
    cmp byte [dd_nT], 0
    je .lo1
    sub bx, [dd_bgap]
    add bp, [dd_bgap]
.lo1:
    cmp byte [dd_nB], 0
    je .lo2
    add bp, [dd_bgap]
.lo2:
    call dd_bd_rect
.noL:
    ; --- right --------------------------------------------------------------
    cmp byte [dd_nR], 0
    je .noR
    mov ax, [dd_gx]
    add ax, [dd_tw]
    mov bx, [dd_gy]
    mov bp, [dd_th]
    cmp byte [dd_nT], 0
    je .rnt
    sub bx, [dd_lth]
    add bp, [dd_lth]
.rnt:
    cmp byte [dd_nB], 0
    je .rnb
    add bp, [dd_lth]
.rnb:
    mov cx, [dd_lth]
    push ax
    push bx
    push cx
    push bp
    call dd_bd_rect
    pop bp
    pop cx
    pop bx
    pop ax
    cmp byte [dd_gc], DD_COLS - 2
    jne .noR
    add ax, [dd_bgap]
    cmp byte [dd_nT], 0
    je .ro1
    sub bx, [dd_bgap]
    add bp, [dd_bgap]
.ro1:
    cmp byte [dd_nB], 0
    je .ro2
    add bp, [dd_bgap]
.ro2:
    call dd_bd_rect
.noR:
    ; --- top ----------------------------------------------------------------
    cmp byte [dd_nT], 0
    je .noT
    mov ax, [dd_gx]
    mov cx, [dd_tw]
    cmp byte [dd_nL], 0
    je .tnl
    sub ax, [dd_lth]
    add cx, [dd_lth]
.tnl:
    cmp byte [dd_nR], 0
    je .tnr
    add cx, [dd_lth]
.tnr:
    mov bx, [dd_gy]
    sub bx, [dd_lth]
    mov bp, [dd_lth]
    push ax
    push bx
    push cx
    push bp
    call dd_bd_rect
    pop bp
    pop cx
    pop bx
    pop ax
    cmp byte [dd_gr], 1
    jne .noT
    sub bx, [dd_bgap]
    cmp byte [dd_nL], 0
    je .to1
    sub ax, [dd_bgap]
    add cx, [dd_bgap]
.to1:
    cmp byte [dd_nR], 0
    je .to2
    add cx, [dd_bgap]
.to2:
    call dd_bd_rect
.noT:
    ; --- bottom -------------------------------------------------------------
    cmp byte [dd_nB], 0
    je .noB
    mov ax, [dd_gx]
    mov cx, [dd_tw]
    cmp byte [dd_nL], 0
    je .bnl
    sub ax, [dd_lth]
    add cx, [dd_lth]
.bnl:
    cmp byte [dd_nR], 0
    je .bnr
    add cx, [dd_lth]
.bnr:
    mov bx, [dd_gy]
    add bx, [dd_th]
    mov bp, [dd_lth]
    push ax
    push bx
    push cx
    push bp
    call dd_bd_rect
    pop bp
    pop cx
    pop bx
    pop ax
    cmp byte [dd_gr], DD_ROWS - 2
    jne .noB
    add bx, [dd_bgap]
    cmp byte [dd_nL], 0
    je .bo1
    sub ax, [dd_bgap]
    add cx, [dd_bgap]
.bo1:
    cmp byte [dd_nR], 0
    je .bo2
    add cx, [dd_bgap]
.bo2:
    call dd_bd_rect
.noB:
    ret

; -----------------------------------------------------------------------------
; dd_wall_round - a WALL tile's corners, rounded where two sides are open
;                 (SPEC.md 93.2.3). Clobbers AX/BX/CX/DX/BP.
;
; IT HAS TO BE THE WALL'S JOB. The outline is drawn by the CORRIDOR tiles, one
; line into each wall that touches them - so a block's outer corner is made by
; two lines from two DIFFERENT tiles, and neither of them can see that a corner
; is being formed. The first attempt at this looked for a corner square inside
; dd_walls_of and never fired once.
;
; The pixel to take is the wall tile's own, because that is where the corridor
; drew: a line goes [dd_lth] INTO the wall from the shared edge, so the two
; lines that meet overlap exactly on the wall tile's corner.
; -----------------------------------------------------------------------------
dd_wall_round:
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    dec ch
    call dd_iswall
    call dd_cf_byte
    mov [dd_nT], al
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    inc ch
    call dd_iswall
    call dd_cf_byte
    mov [dd_nB], al
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    dec cl
    call dd_iswall
    call dd_cf_byte
    mov [dd_nL], al
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    inc cl
    call dd_iswall
    call dd_cf_byte
    mov [dd_nR], al

    mov al, [dd_nT]
    or al, [dd_nL]
    jnz .tr
    mov ax, [dd_gx]                 ; top-left
    mov bx, [dd_gy]
    mov cx, [dd_lth]
    mov dx, cx
    call dd_rnd_cnr
.tr:
    mov al, [dd_nT]
    or al, [dd_nR]
    jnz .bl
    mov ax, [dd_gx]                 ; top-right
    add ax, [dd_tw]
    sub ax, [dd_lth]
    mov bx, [dd_gy]
    mov dx, [dd_lth]
    mov cx, dx
    neg cx
    call dd_rnd_cnr
.bl:
    mov al, [dd_nB]
    or al, [dd_nL]
    jnz .br
    mov ax, [dd_gx]                 ; bottom-left
    mov bx, [dd_gy]
    add bx, [dd_th]
    sub bx, [dd_lth]
    mov cx, [dd_lth]
    mov dx, cx
    neg dx
    call dd_rnd_cnr
.br:
    mov al, [dd_nB]
    or al, [dd_nR]
    jnz .out
    mov ax, [dd_gx]                 ; bottom-right
    add ax, [dd_tw]
    sub ax, [dd_lth]
    mov bx, [dd_gy]
    add bx, [dd_th]
    sub bx, [dd_lth]
    mov cx, [dd_lth]
    neg cx
    mov dx, cx
    call dd_rnd_cnr
.out:
    ret

; -----------------------------------------------------------------------------
; dd_rnd_cnr - round the elbow whose [dd_lth] square has its top-left at
;              (AX, BX) and whose two arms run in the directions (CX, DX),
;              each of which is plus or minus [dd_lth]. Preserves everything.
;
; THE ARCADE'S OWN SHAPE, read off a pixel-perfect capture rather than guessed:
; at a block's corner the horizontal line stops two pixels short, one pixel
; sits on the diagonal, and the vertical starts two pixels down. So a round is
; a SQUARE TAKEN OUT and ONE BLOCK PUT BACK on the diagonal inside it - not an
; arc anybody has to walk, and not a chamfer either, a chamfer being what this
; degenerates to at [dd_rnd] = [dd_lth] where there is no room for the block.
;
; The elbow is the wall tile's own corner because that is where the corridor
; drew: a line goes [dd_lth] INTO the wall from the shared edge, so the two
; lines that meet overlap exactly there.
; -----------------------------------------------------------------------------
dd_rnd_cnr:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov si, ax
    add si, cx                      ; (SI, DI) = the block that goes back, one
    mov di, bx                      ; line width along each arm
    add di, dx
    mov bp, [dd_rnd]
    cmp bp, [dd_lth]
    je .clear                       ; one width: a chamfer, nothing goes back
    or cx, cx
    jns .rx
    mov ax, si                      ; an arm running LEFT or UP anchors the
.rx:                                ; square that comes out at its far end
    or dx, dx
    jns .clear
    mov bx, di
.clear:
    mov cx, bp
    xor dh, dh                      ; paper: the elbow comes out
    call dd_bd_rect
    cmp bp, [dd_lth]
    je .out
    mov ax, si
    mov bx, di
    mov cx, [dd_lth]
    mov bp, cx
    mov dh, 1                       ; ...and the diagonal block goes back in
    call dd_bd_rect
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_bord_round - the PLAYFIELD BORDER's own four corners (SPEC.md 93.2.4)
;
; dd_wall_round cannot reach these. Its rule is "a wall tile with two OPEN
; sides", which is a block's corner seen from outside; the border's corners are
; the same elbow seen from INSIDE, and the wall tile that owns them - the one
; in the ring's corner - has wall on both of the sides that matter. So they are
; done once, off the geometry, rather than looked for tile by tile.
;
; Eight elbows, not four: the border is a DOUBLE line, and the outer one sits
; 2*[dd_lth] further out on every side.
; -----------------------------------------------------------------------------
dd_bord_round:
    mov ax, [dd_tw]                 ; the INNER line, one thickness into the
    sub ax, [dd_lth]                ; wall ring from the corridor it edges
    mov [dd_bcx], ax
    mov ax, DD_COLS - 1
    mul word [dd_tw]
    mov [dd_bcx2], ax
    mov ax, [dd_th]
    sub ax, [dd_lth]
    mov [dd_bcy], ax
    mov ax, DD_ROWS - 1
    mul word [dd_th]
    mov [dd_bcy2], ax
    call .four
    mov ax, [dd_bgap]               ; ...and the outer one, then FALL THROUGH
    sub [dd_bcx], ax
    add [dd_bcx2], ax
    sub [dd_bcy], ax
    add [dd_bcy2], ax
.four:
    mov ax, [dd_bcx]
    mov bx, [dd_bcy]
    mov cx, [dd_lth]                ; top-left: the arms run right and down
    mov dx, cx
    call dd_rnd_cnr
    mov ax, [dd_bcx2]
    mov bx, [dd_bcy]
    mov dx, [dd_lth]                ; top-right: left and down
    mov cx, dx
    neg cx
    call dd_rnd_cnr
    mov ax, [dd_bcx]
    mov bx, [dd_bcy2]
    mov cx, [dd_lth]                ; bottom-left: right and up
    mov dx, cx
    neg dx
    call dd_rnd_cnr
    mov ax, [dd_bcx2]
    mov bx, [dd_bcy2]
    mov cx, [dd_lth]                ; bottom-right: left and up
    neg cx
    mov dx, cx
    call dd_rnd_cnr
    ret

; dd_cf_byte - AL = 1 when CF was set, 0 when it was not
dd_cf_byte:
    mov al, 0
    jnc .out
    mov al, 1
.out:
    ret

; The door: a bar across the tile, so the house reads as closed from outside.
dd_door_draw:
    mov ax, [dd_gx]
    mov bx, [dd_th]
    sub bx, [dd_lth]
    shr bx, 1
    add bx, [dd_gy]
    mov cx, [dd_tw]
    mov bp, [dd_lth]
    mov dh, 1
    call dd_bd_rect
    ret

; -----------------------------------------------------------------------------
; dd_eat_tile - take the dot or pellet at column CL, row CH off the board and
;               answer what it was in AL (TT_EMPTY when there was nothing)
; Clobbers AX/BX/DX.
;
; IT DRAWS NOTHING, and that is the whole point of keeping the dots out of the
; wall picture: the tile Smiles just ate is inside Smiles' own band, and the
; band is composed from dd_grid, so the next frame carries the absence without
; anybody erasing anything.
; -----------------------------------------------------------------------------
dd_eat_tile:
    call dd_tile
    cmp al, TT_DOT
    je .go
    cmp al, TT_PILL
    je .go
    mov al, TT_EMPTY
    ret
.go:
    push cx
    push ax
    mov bl, cl
    xor bh, bh
    mov al, ch
    xor ah, ah
    mov cl, DD_COLS
    mul cl
    add bx, ax
    mov byte [dd_grid + bx], TT_EMPTY
    dec word [dd_ndots]
    pop ax
    pop cx
    ret

; --- the layouts --------------------------------------------------------------
dd_lays: dw dd_lay0, dd_lay1, dd_lay2

%include "ddmzdat.inc"
