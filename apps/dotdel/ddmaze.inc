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
    je .next                        ; the wall draws nothing of its own: it is
    mov [dd_gt], al                 ; its neighbours' outline
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
    call dd_bd_rect
.noB:
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
