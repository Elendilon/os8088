; =============================================================================
; os8088 - apps/dotdel/ddlay.inc
;
; THE LAYOUT (SPEC.md 93.3): how a 28x31 grid becomes pixels on four adapters
; whose pixels are four different shapes.
;
; The grid never changes - a maze that lost columns on a CGA would be a
; different game, and the AI, the dot count and the ghost house would all have
; to be per-adapter. What changes is the TILE, computed here from two numbers:
; the live content box, and the adapter's PIXEL ASPECT.
;
; --- THE ASPECT IS THE POINT, AND IT IS 1:1 NOWHERE BUT VGA ------------------
;
; A 4:3 monitor showing 640x480 has square pixels; showing 640x200 it has
; pixels 2.4x taller than they are wide, and 720x348 gives 1.55. A board laid
; out in square TILES is therefore three different SHAPES on the glass, and
; the one the eye reads as "a maze chase board" is the portrait one. So the
; tile HEIGHT is chosen first, from the height available, and the tile WIDTH
; is the largest of {8, 16} that keeps the tile within 1.3x of square on the
; glass.
;
;   VGA  640x480  aspect 100  ->  16 x 13   board 448 x 403   1.11 : 1
;   HERC 720x348  aspect 155  ->  16 x  9   board 448 x 279   1.15 : 1
;   EGA  640x350  aspect 137  ->  16 x  9   board 448 x 279   1.17 : 1
;   CGA  640x200  aspect 240  ->   8 x  4   board 224 x 124   0.83 : 1
;
; ...and in a fullscreen bracket the same arithmetic gives a CGA 16 x 6 and a
; board of 448 x 186, which is 1.00 : 1 - the best-proportioned board in the
; game, on the worst adapter in the machine. That is the whole argument for
; sizing from the surface rather than from a table.
;
; --- WHY THE TILE WIDTH IS A MULTIPLE OF EIGHT (binding) ---------------------
;
; `gfx_blit1` takes a destination x that is a multiple of 8 (SPEC.md 5.4.2),
; so an actor's band is its box rounded OUT to the byte grid. Rounding out is
; free when the extra columns hold something the band is allowed to draw, and
; expensive when they hold something it is not: a band is put down in ONE pen,
; so a wall inside it would be drawn in the actor's own colour.
;
; A tile width that is a multiple of 8 - with the board's own screen x a
; multiple of 8 - removes the case entirely:
;
;   * moving VERTICALLY, the actor's x is its column's x, which is already on
;     the grid, so the band is exactly the actor's own columns and reaches
;     neither wall beside it;
;   * moving HORIZONTALLY, the band rounds out along the corridor it is in,
;     and a corridor's neighbours along its own axis are corridor.
;
; So the only static ink a band can ever contain is DOTS, and SPEC.md 93.5.4
; is what that costs on a colour adapter.
; =============================================================================

; Pixel aspect as (pixel height / pixel width) * 100, indexed by VID_* kind:
; VGA, Hercules, CGA, EGA.
dd_aspect: db 100, 155, 240, 137

; -----------------------------------------------------------------------------
; dd_layout - fill every derived geometry word from dd_cx/cy/cw/ch + dd_vkind
; out: CF = 1 the surface is too small for a board; every register clobbered.
; -----------------------------------------------------------------------------
dd_layout:
    ; --- the tile height: as tall as 31 rows of it will fit, capped ----------
    mov ax, [dd_ch]
    cmp ax, DD_ROWS * DD_THMAX
    jb .divh
    mov ax, DD_THMAX
    jmp short .thok
.divh:
    mov bl, DD_ROWS
    div bl                          ; AL = ch / 31, and ch < 31*16 = 496 so
    xor ah, ah                      ; the quotient cannot overflow AL
.thok:
    cmp ax, 3
    jb .tiny                        ; under three rows to a tile there is no
    mov [dd_th], ax                 ; board worth drawing

    ; --- the aspect for the display we are on -------------------------------
    mov bl, [dd_vkind]
    xor bh, bh
    cmp bl, 4
    jb .kok
    xor bx, bx
.kok:
    mov al, [dd_aspect + bx]
    xor ah, ah
    mov [dd_asp], ax

    ; --- the tile width: 16 when it fits the width AND stays near square ----
    ; near square is  tw * 100 * 10  <=  th * aspect * 13
    mov word [dd_tw], DD_TWMAX
    mov ax, DD_COLS * DD_TWMAX + DD_HUDW
    cmp ax, [dd_cw]
    ja .narrow
    mov ax, [dd_th]
    mul word [dd_asp]               ; at most 16 * 240 = 3,840
    mov bx, 13
    mul bx                          ; at most 49,920 - still one word
    cmp ax, DD_TWMAX * 1000
    jae .twok
.narrow:
    mov word [dd_tw], 8
    mov ax, DD_COLS * 8 + DD_HUDW
    cmp ax, [dd_cw]
    ja .tiny
.twok:
    ; --- and cap the height, so a tile cannot be much TALLER than square ----
    ; th  <=  tw * 100 * 13 / (aspect * 10)
    mov ax, [dd_tw]
    mov bx, 1300
    mul bx                          ; at most 20,800
    mov bx, [dd_asp]
    mov cx, bx
    shl bx, 1
    shl bx, 1
    shl bx, 1
    add bx, cx
    add bx, cx                      ; BX = aspect * 10, without a second mul
    div bx                          ; AX = the tallest square-ish tile
    cmp ax, [dd_th]
    jae .hok
    cmp ax, 3
    jb .tiny
    mov [dd_th], ax
.hok:

    ; --- the derived extents ------------------------------------------------
    mov ax, [dd_tw]
    mov bx, DD_COLS
    mul bx
    mov [dd_mw], ax                 ; board width in px, a multiple of 8
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [dd_sb], ax                 ; ...and the board picture's row stride
    mov ax, [dd_th]
    mov bx, DD_ROWS
    mul bx
    mov [dd_mh], ax                 ; board height in px

    ; --- where it sits ------------------------------------------------------
    ; THE BOARD IS CENTRED and the HUD lives in the margin beside it, whenever
    ; that margin is wide enough to hold one. It is the board the eye reads,
    ; and a board pushed right by the width of a score column looks like a
    ; mistake on a screen with 96 px of air on the other side. When the margin
    ; is too narrow the two are packed side by side and centred together,
    ; which is the only thing a narrow surface can do.
    mov ax, [dd_cw]
    sub ax, [dd_mw]
    jns .m0
    xor ax, ax
.m0:
    shr ax, 1
    mov bx, ax                      ; BX = the margin each side
    cmp ax, DD_HUDW + 8
    jb .packed
    add ax, [dd_cx]
    add ax, 7
    and ax, ~7                      ; **THE BOARD'S x IS ON THE BYTE GRID**,
    mov [dd_bdx], ax                ; which is what makes every column of it a
    sub bx, DD_HUDW                 ; legal gfx_blit1 destination
    shr bx, 1
    add bx, [dd_cx]
    mov [dd_hx], bx
    jmp short .vert
.packed:
    mov ax, [dd_cw]
    sub ax, DD_HUDW
    sub ax, [dd_mw]
    jns .padok
    xor ax, ax
.padok:
    shr ax, 1
    add ax, [dd_cx]
    mov [dd_hx], ax                 ; the HUD column's own left edge
    add ax, DD_HUDW
    add ax, 7
    and ax, ~7
    mov [dd_bdx], ax
.vert:
    mov ax, [dd_ch]
    sub ax, [dd_mh]
    jns .vpadok
    xor ax, ax
.vpadok:
    shr ax, 1
    add ax, [dd_cy]
    mov [dd_bdy], ax
    mov ax, [dd_cy]
    add ax, 6
    mov [dd_hy], ax

    ; --- the sub-pixel speeds (SPEC.md 93.7.1) ------------------------------
    ; One tile in DD_TILET ticks, so the game runs at the same TILES per
    ; second on every adapter and the pixel rate follows the tile.
    mov ax, [dd_tw]
    mov bx, DD_SUB
    mul bx
    mov bl, DD_TILET
    div bl
    xor ah, ah
    mov [dd_spx], ax
    mov ax, [dd_th]
    mov bx, DD_SUB
    mul bx
    mov bl, DD_TILET
    div bl
    xor ah, ah
    mov [dd_spy], ax
    ; the sub-pixel extent of one tile, which every wrap and every centring
    ; test below is measured in
    mov ax, [dd_tw]
    mov cl, 4
    shl ax, cl
    mov [dd_twS], ax
    mov ax, [dd_th]
    shl ax, cl
    mov [dd_thS], ax
    mov ax, [dd_mw]
    shl ax, cl
    mov [dd_mwS], ax
    call dd_metrics
    clc
    ret
.tiny:
    stc
    ret

; -----------------------------------------------------------------------------
; dd_metrics - how thick a wall line is, and how big a dot and a pellet are
; Every one is derived from the tile, so a windowed CGA's 8x4 and a fullscreen
; VGA's 16x15 get the same picture at two sizes rather than two pictures.
; -----------------------------------------------------------------------------
dd_metrics:
    mov word [dd_lth], 1            ; two pixels of wall once there is room for
    mov ax, [dd_th]                 ; the black between two of them
    cmp ax, 8
    jb .lok
    cmp word [dd_tw], 16
    jb .lok
    mov word [dd_lth], 2
.lok:
    mov ax, [dd_tw]                 ; a dot is a fifth of the tile, never under
    mov bl, 5                       ; two pixels wide or one tall
    div bl
    xor ah, ah
    cmp ax, 2
    jae .dw
    mov ax, 2
.dw:
    mov [dd_dotw], ax
    mov ax, [dd_th]
    mov bl, 4
    div bl
    xor ah, ah
    or ax, ax
    jnz .dh
    mov ax, 1
.dh:
    mov [dd_doth], ax
    mov ax, [dd_tw]                 ; a pellet is half of it
    shr ax, 1
    cmp ax, 3
    jae .pw
    mov ax, 3
.pw:
    mov [dd_pilw], ax
    mov ax, [dd_th]
    shr ax, 1
    cmp ax, 2
    jae .ph
    mov ax, 2
.ph:
    mov [dd_pilh], ax
    ret

; -----------------------------------------------------------------------------
; dd_relayout_ck - re-lay out only when something that decides the layout moved
; out: nothing; clobbers everything. Safe to call from any paint.
;
; Three things can change under a live window - its SIZE, its POSITION and the
; DISPLAY it is on - and only the first changes the tile. A move between two
; displays of different depth changes the PENS and not one coordinate, which
; is why the depth is banked in dd_geom_* and is not a reason to re-render the
; board picture: the picture is one bit a pixel and carries no colour at all.
; -----------------------------------------------------------------------------
dd_relayout_ck:
    cmp word [dd_bdseg], 0
    je .redo                        ; nothing has ever been laid out
    mov al, [dd_vkind]
    cmp al, [dd_lvkind]
    jne .redo                       ; a different CARD is a different pixel
    mov ax, [dd_cw]                 ; shape, and so a different tile
    cmp ax, [dd_lcw]
    jne .redo
    mov ax, [dd_ch]
    cmp ax, [dd_lch]
    jne .redo
    mov ax, [dd_cx]
    cmp ax, [dd_lcx]
    jne .move
    mov ax, [dd_cy]
    cmp ax, [dd_lcy]
    jne .move
    ret
.move:
    call dd_bank_box                ; only the origin moved: the tile, the
    call dd_layout                  ; picture and the sprites all stand
    jc .fail
    mov byte [dd_ok], 1
    ret
.redo:
    call dd_bank_box
    call dd_layout
    jc .fail
    call dd_fit_claim               ; claim it, or grow what is already there
    jc .fail
    call dd_spr_build               ; the sprite set is cut to the new tile
    mov byte [dd_ok], 1
    cmp byte [dd_started], 0
    jne .again
    mov byte [dd_started], 1        ; the FIRST layout is also the first board:
    call dd_attract_begin           ; it lays the slice and renders it
    ret
.again:
    call dd_is_attract              ; ...and every later one re-draws it at the
    jnc .board                      ; new tile - or, on the title screen, cuts
    call dd_attract_begin           ; the slice again, which decides how much
    ret                             ; of the board there even is
.board:
    call dd_board_render
    ret
.fail:
    mov byte [dd_ok], 0
    ret

dd_bank_box:
    mov al, [dd_vkind]
    mov [dd_lvkind], al
    mov ax, [dd_cx]
    mov [dd_lcx], ax
    mov ax, [dd_cy]
    mov [dd_lcy], ax
    mov ax, [dd_cw]
    mov [dd_lcw], ax
    mov ax, [dd_ch]
    mov [dd_lch], ax
    ret

; dd_bdkb_calc - AX = KB the board picture needs at the current layout
dd_bdkb_calc:
    push dx
    push cx
    mov ax, [dd_sb]
    mul word [dd_mh]                ; 56 * 496 = 27,776: one word, just
    add ax, 1023
    adc dx, 0
    mov cl, 10
.sh:
    shr dx, 1
    rcr ax, 1
    dec cl
    jnz .sh
    or ax, ax
    jnz .ok
    mov ax, 1
.ok:
    pop cx
    pop dx
    ret

; -----------------------------------------------------------------------------
; dd_fit_claim - make the board picture's claim big enough for this layout,
;                claiming it the first time and growing it after
; out: CF = 1 refused. Clobbers AX/BX/CX/DX.
;
; It is claimed rather than declared in bss for one reason: 56 bytes of stride
; by 496 rows is 27 KB and a windowed CGA needs 3.4 of them, so a package that
; reserved the ceiling would charge every machine for the largest board any
; machine could show - and APP_MAX_SIZE is 60 KB for the image and the bss
; together.
; -----------------------------------------------------------------------------
dd_fit_claim:
    cmp word [dd_bdseg], 0
    jne .grow
    call dd_bdkb_calc
    call OSAPI_MEM_CLAIM            ; out DX = the base, AX = KB given
    jc .no
    mov [dd_bdseg], dx
    mov [dd_bdkb], ax
    clc
    ret
.grow:
    call dd_bdkb_calc
    cmp ax, [dd_bdkb]
    jbe .fits
    push ax
    mov dx, [dd_bdseg]
    call OSAPI_MEM_REGROW           ; DX = the claim's base NOW - a regrow may
    pop cx                          ; move it, and every reader goes through
    jc .no                          ; [dd_bdseg]
    mov [dd_bdseg], dx
    mov [dd_bdkb], cx
.fits:
    clc
    ret
.no:
    stc
    ret
