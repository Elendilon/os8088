; =============================================================================
; os8088 - apps/dotdel/ddrend.inc
;
; THE RENDERER (SPEC.md 93.5). Five bands a frame and nothing else moves.
;
; --- WHAT IS IN THE PICTURE, AND WHAT IS NOT ---------------------------------
;
; `dd_bd` holds the WALLS and only the walls. It was going to hold the dots as
; well - the board is one picture, so one blit puts it up - and that is wrong
; for a reason that is worth writing down, because it is the same reason twice:
; **a band is put down in ONE pen**, so every pixel in one has to be the same
; colour. Walls and dots in one picture is walls and dots in one colour, and on
; a VGA that is a blue board with blue dots on it.
;
; So the dots are not a picture at all. They live in `dd_grid`, one byte a
; tile, and they are STAMPED into whichever band needs them:
;
;   * an ACTOR's band stamps the two or three tiles it overlaps, which is
;     cheaper than reading them out of a bitmap would have been;
;   * a WHOLE-BOARD repaint walks each tile row and puts down one band per RUN
;     of adjacent dot tiles - about eighty bands for the classic board, ~36 ms -
;     and a run is safe to blit opaquely because two adjacent corridor tiles
;     have no wall between them to erase.
;
; That leaves the walls as the only thing big enough to want a bitmap, and one
; `gfx_blit1` a half puts the whole board up.
;
; --- THE ACTOR BAND ----------------------------------------------------------
;
; The band is the UNION of where the actor was drawn and where it is now,
; rounded out to the byte grid, with the sprite OR'd in at the bit offset its x
; has landed on. Drawing it IS the erase (SPEC.md 79.5): there is no instant at
; which the sprite is off the glass, no second call to be pre-empted between,
; and no erase pass to get the order of.
;
; A move too big for that band is a TELEPORT - the tunnel, a new life, the
; start of a level - and is drawn as two operations instead: put the tile back
; where the actor was, then draw it where it is.
; =============================================================================

DD_HUDROW equ 10                ; the HUD's line pitch, px

; The pen each actor draws in on a colour adapter. Index 0 is Smiles.
dd_ink:    db CYELLOW, CRED, CLMAGENTA, CLCYAN, CBROWN
DD_INKDOT  equ CWHITE
DD_INKWALL equ CBLUE
DD_INKFRI  equ CLBLUE           ; frightened - and CWHITE on the flash
DD_INKEYE  equ CWHITE
DD_INKFRU  equ CLRED
DD_INKTXT  equ CWHITE

; -----------------------------------------------------------------------------
; dd_pen - AL = ink, on black paper, and NOT SET AT ALL on a 1bpp adapter
; in:  AL = ink. Preserves every register.
;
; SPEC.md 5.4.2.2: the pen is ignored on one plane, where a band already means
; lit and unlit. Skipping it there is not tidiness - it is ~78 us a band, five
; bands a frame, on the two adapters that have the least to spare.
; -----------------------------------------------------------------------------
dd_pen:
    cmp byte [dd_bpp], 1
    jbe .out
    push ax
    mov ah, CBLACK
    call OSAPI_GFX_BLIT1_PEN
    pop ax
.out:
    ret

; =============================================================================
; TEXT (SPEC.md 93.5.5)
;
; Every line this package letters goes down as ONE BAND, composed out of the
; kernel's own 8x8 glyph table (`OSAPI_FONT_GLYPHS`) and put up with one
; `gfx_blit1`. It is not `font_run`, and the reason is measured: on a VGA
; `font_run` cannot reach SPEC.md 6.1's single-store path and falls to the
; `gfx_fill` + `font_str` pair (font.inc:740), which for the attract screen's
; nineteen-character play line is **176 ms** - three whole ticks, twice a
; second, and the whole of why that screen ran at 9.8 fps against the tick's
; 18.2. The same line as a band is ~1 ms.
;
; It is what SPEC.md 5.4.2 was written for, one row of type instead of a
; hundred and four.
; =============================================================================

; -----------------------------------------------------------------------------
; dd_font_get - bank the kernel's glyph table, once
; -----------------------------------------------------------------------------
dd_font_get:
    push ax
    push cx
    push dx
    push si
    call OSAPI_FONT_GLYPHS          ; DX:SI = the table, AL/AH = its range
    mov [dd_gseg], dx
    mov [dd_goff], si
    mov [dd_gfirst], al
    mov [dd_glast], ah
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_text - the NUL string at SI, in ink AL, at (BX, DX) in ABSOLUTE screen
;           coordinates. BX is rounded DOWN to the byte grid.
; Preserves every register. A string over DD_TEXTMAX cells is cut.
; -----------------------------------------------------------------------------
DD_TEXTMAX equ 34

dd_text:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    mov [dd_tink], al
    and bx, ~7                      ; gfx_blit1 wants the byte grid, and a line
    mov [dd_tx], bx                 ; of type nudged left by up to seven pixels
    mov [dd_ty], dx                 ; is a line of type
    ; --- how many cells, capped --------------------------------------------
    xor cx, cx
    push si
.len:
    cmp byte [si], 0
    je .have
    inc si
    inc cx
    cmp cx, DD_TEXTMAX
    jb .len
.have:
    pop si
    jcxz .out
    mov [dd_tn], cx
    ; --- eight rows of CX bytes, out of the glyph table ---------------------
    mov ax, [dd_gseg]
    mov es, ax
    xor bx, bx                      ; BX = the glyph row
.row:
    push bx
    mov ax, bx
    mul word [dd_tn]
    mov di, dd_band
    add di, ax                      ; DI = this band row
    pop bx
    push si
    mov cx, [dd_tn]
.cell:
    mov al, [si]
    cmp al, [dd_gfirst]
    jb .blank
    cmp al, [dd_glast]
    ja .blank
    sub al, [dd_gfirst]
    xor ah, ah
    push cx
    mov cl, 3
    shl ax, cl                      ; eight bytes a glyph
    pop cx
    add ax, [dd_goff]
    add ax, bx                      ; ...and BX says which row of it
    push bx
    mov bx, ax
    mov al, [es:bx]
    pop bx
    jmp short .put
.blank:
    xor al, al
.put:
    mov [di], al
    inc di
    inc si
    loop .cell
    pop si
    inc bx
    cmp bx, 8
    jb .row
    ; --- ...and one call ----------------------------------------------------
    mov al, [dd_tink]
    call dd_pen
    push ds
    pop es
    mov si, dd_band
    mov bp, [dd_tn]
    mov ax, [dd_tx]
    mov bx, [dd_ty]
    mov cx, [dd_tn]
    mov dx, cx
    mov cl, 3
    shl dx, cl                      ; the width in pixels
    mov cx, dx
    mov dx, 8
    call OSAPI_GFX_BLIT1
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

; =============================================================================
; PUTTING A BAND DOWN
; =============================================================================

; -----------------------------------------------------------------------------
; dd_blit - ES:SI = a band of ours, BP = stride, AX/BX = BOARD x/y, CX = width
;           in pixels, DX = rows. Clips to the board, translates to the screen.
; in:  AX must be a multiple of 8. Preserves every register.
; out: nothing - a refusal (kern_small has no body, SPEC.md 5.4.2.5) is
;      swallowed, because the honest degrade for a moving sprite is to leave
;      the frame alone rather than letter something in its place.
; -----------------------------------------------------------------------------
dd_blit:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    or cx, cx
    jle .out
    or dx, dx
    jle .out
    ; --- clip to the board in x, by whole byte columns -----------------------
    or ax, ax
    jge .noleft
    mov di, ax
    neg di                          ; DI = pixels off the left
    add cx, ax
    jle .out
    push cx
    mov cl, 3
    shr di, cl
    pop cx
    add si, di                      ; ...which is DI/8 band bytes skipped
    xor ax, ax
.noleft:
    mov di, ax
    add di, cx
    cmp di, [dd_mw]
    jbe .noright
    mov cx, [dd_mw]
    sub cx, ax
    jle .out
.noright:
    ; --- clip to the board in y ---------------------------------------------
    ; ...against [dd_clipy0] and not against zero: the attract screen shows a
    ; SLICE of the board (SPEC.md 93.11.2), and it says so by moving that word
    ; and the origin together rather than by having its own coordinates.
    cmp bx, [dd_clipy0]
    jge .notop
    mov di, [dd_clipy0]
    sub di, bx                      ; rows above the slice
    sub dx, di
    jle .out
    push ax
    push dx                         ; ...and MUL writes DX, which is the ROW
    mov ax, di                      ; COUNT: without saving it the band arrives
    mul bp                          ; nought rows tall and gfx_blit1 refuses it -
    add si, ax                      ; silently, because a refusal here is swallowed
    pop dx
    pop ax
    mov bx, [dd_clipy0]
.notop:
    mov di, bx
    add di, dx
    cmp di, [dd_mh]
    jbe .nobot
    mov dx, [dd_mh]
    sub dx, bx
    jle .out
.nobot:
    cmp dx, 255
    jbe .hok
    mov dx, 255                     ; gfx_blit1 takes 1..255 rows
.hok:
    add ax, [dd_bdx]                ; ...and only now into screen coordinates
    add bx, [dd_bdy]
    call OSAPI_GFX_BLIT1
.out:
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE WALL PICTURE, ON THE GLASS
; =============================================================================

; -----------------------------------------------------------------------------
; dd_walls_blit - the whole wall picture, in halves (gfx_blit1 takes 255 rows)
; Clobbers everything.
; -----------------------------------------------------------------------------
dd_walls_blit:
    mov al, DD_INKWALL
    call dd_pen
    xor bx, bx
.half:
    mov dx, [dd_mh]
    sub dx, bx
    jle .out
    cmp dx, 200
    jbe .last
    mov dx, 200
.last:
    push bx
    push dx
    mov ax, bx
    mul word [dd_sb]
    mov si, ax
    mov ax, [dd_bdseg]
    mov es, ax
    xor ax, ax
    mov cx, [dd_mw]
    mov bp, [dd_sb]
    pop dx
    pop bx
    push bx
    push dx
    call dd_blit
    pop dx
    pop bx
    add bx, dx
    cmp bx, [dd_mh]
    jb .half
.out:
    ret

; =============================================================================
; DOTS
; =============================================================================

; -----------------------------------------------------------------------------
; dd_dots_blit - every dot still on the board, one band per RUN of adjacent
;                dot tiles in a tile row
; Clobbers everything. ~36 ms for the classic board.
; -----------------------------------------------------------------------------
dd_dots_blit:
    mov al, DD_INKDOT
    call dd_pen
    mov byte [dd_gr], 0
.rows:
    mov byte [dd_gc], 0
.scan:
    ; find the start of a run
    mov cl, [dd_gc]
    cmp cl, DD_COLS
    jae .nextrow
    mov ch, [dd_gr]
    call dd_dotish
    jnc .adv
    mov al, [dd_gc]
    mov [dd_runa], al               ; the run's first column
.grow:
    inc byte [dd_gc]
    mov cl, [dd_gc]
    cmp cl, DD_COLS
    jae .emit
    mov ch, [dd_gr]
    call dd_dotish
    jc .grow
.emit:
    call dd_run_emit
    jmp short .scan
.adv:
    inc byte [dd_gc]
    jmp short .scan
.nextrow:
    inc byte [dd_gr]
    cmp byte [dd_gr], DD_ROWS
    jb .rows
    ret

; dd_dotish - CF = 1 when the tile at CL,CH carries a DOT. A pellet is not one:
; it is taller than the dot row a run's band is, and there are four of them, so
; each is put down whole by dd_tile_put instead.
dd_dotish:
    call dd_tile
    cmp al, TT_DOT
    je .yes
    clc
    ret
.yes:
    stc
    ret

; -----------------------------------------------------------------------------
; dd_pills_blit - the four pellets, each as its own tile
;
; IT READS A LIST AND DOES NOT WALK THE BOARD, and that is not tidiness: the
; blink turns over three times a second, and a walk of all 868 tiles to find
; four of them measured at 45 ms a turn - 11 ms of every frame amortised, and
; the whole of why a 4.77 MHz CGA ran at 12 fps against the tick's 18.2
; (SPEC.md 93.5.3). With the list it is four tile blits and the same machine
; holds 18.2.
; -----------------------------------------------------------------------------
dd_pills_blit:
    push si
    xor si, si
.each:
    cmp si, [dd_piln]
    jae .out
    mov cl, [dd_pilc + si]
    mov ch, [dd_pilr + si]
    call dd_tile_put
    inc si
    jmp short .each
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; dd_run_emit - one band for the run of dot tiles [dd_runa] .. [dd_gc]-1 of
;               tile row [dd_gr]
; Clobbers everything but [dd_gc] / [dd_gr] / [dd_runa].
;
; The band is the run's tiles WHOLE - dots sit at a tile centre, so rounding
; their extent out to the byte grid lands exactly on the tile boundaries the
; run already owns, and two adjacent corridor tiles have no wall between them
; for an opaque band to erase.
; -----------------------------------------------------------------------------
dd_run_emit:
    mov al, [dd_runa]
    xor ah, ah
    mul word [dd_tw]
    mov [dd_rx], ax                 ; the band's board x, on the byte grid
    mov al, [dd_gc]
    xor ah, ah
    sub al, [dd_runa]
    sbb ah, 0
    mul word [dd_tw]
    mov [dd_rw], ax                 ; ...and its width, a whole number of tiles
    mov al, [dd_gr]
    xor ah, ah
    mul word [dd_th]
    mov bx, [dd_th]
    sub bx, [dd_doth]
    shr bx, 1
    add ax, bx
    mov [dd_ry], ax                 ; the dot row inside the tile row

    ; compose: one band, [dd_doth] rows of ceil(rw/8) bytes
    mov ax, [dd_rw]
    add ax, 7
    mov cl, 3
    shr ax, cl
    mov [dd_rb], ax                 ; the band's stride
    mul word [dd_doth]
    mov cx, ax
    cmp cx, DD_BANDSZ
    jbe .fits
    mov cx, DD_BANDSZ
.fits:
    mov word [dd_bbase], dd_band
    mov di, dd_band
    xor al, al
    push es
    push ds
    pop es
    cld
    rep stosb                       ; a clean band
    pop es

    mov al, [dd_runa]
.each:
    push ax
    mov [dd_gt], al
    ; this tile's dot, in band coordinates
    xor ah, ah
    sub al, [dd_runa]
    sbb ah, 0
    mul word [dd_tw]
    mov bx, [dd_tw]
    sub bx, [dd_dotw]
    shr bx, 1
    add ax, bx                      ; AX = the dot's x inside the band
    mov bx, ax                      ; BX = the dot's x inside the band
    mov ax, bx
    xor bx, bx                      ; y = 0: the band IS the dot row
    mov cx, [dd_dotw]
    mov dx, [dd_doth]
    call dd_band_rect
.next:
    pop ax
    inc al
    cmp al, [dd_gc]
    jb .each

    push ds
    pop es
    mov si, dd_band
    mov bp, [dd_rb]
    mov ax, [dd_rx]
    mov bx, [dd_ry]
    mov cx, [dd_rw]
    mov dx, [dd_doth]
    call dd_blit
    ret

; -----------------------------------------------------------------------------
; dd_band_rect - set a CX x DX rectangle at (AX, BX) inside dd_band
; in:  AX = x, BX = y, CX = w, DX = h, [dd_rb] = the band's stride
; Preserves every register.
; -----------------------------------------------------------------------------
dd_band_rect:
    push ax
    push bx
    push cx
    push dx
    push di
    or cx, cx
    jle .out
    or dx, dx
    jle .out
.row:
    push ax
    push bx
    push cx
    push dx
    mov ax, bx
    mul word [dd_rb]                ; MUL writes DX, which is the row counter
    mov di, [dd_bbase]
    add di, ax
    pop dx
    pop cx
    pop bx
    pop ax
    call dd_bandrun
    inc bx
    dec dx
    jnz .row
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_bandrun - set CX bits from x = AX in the band row based at DI
; Preserves every register.
; -----------------------------------------------------------------------------
dd_bandrun:
    push ax
    push bx
    push cx
    push dx
    push di
    mov dx, cx                      ; DX = bits still to lay
    or dx, dx
    jle .done
    mov bx, ax
    mov cl, 3
    shr bx, cl
    add di, bx                      ; DI = the first byte
    mov bl, al
    and bl, 7                       ; BL = the bit offset into it
.byte:
    mov al, 8
    sub al, bl                      ; AL = bits this byte can still take
    xor ah, ah
    cmp ax, dx
    jbe .n
    mov ax, dx                      ; ...capped by what is left
.n:
    mov ch, al                      ; CH = n, 1..8
    mov cl, 8
    sub cl, ch
    mov al, 0FFh
    shl al, cl                      ; n high bits...
    mov cl, bl
    shr al, cl                      ; ...slid to where they belong
    or [di], al
    xor ah, ah
    mov al, ch
    sub dx, ax
    jle .done
    inc di
    xor bl, bl                      ; every byte after the first starts left
    jmp short .byte
.done:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_tile_put - put tile (CL, CH) back on the glass exactly as the board says
;               it should look: black, with its dot or pellet if it has one
; Clobbers everything. This is the one "undo whatever was drawn there"
; primitive - a blinking pellet, a vanished fruit, a score that has been read.
; -----------------------------------------------------------------------------
dd_tile_put:
    mov [dd_gc], cl
    mov [dd_gr], ch
    call dd_tile
    mov [dd_gt], al
    call dd_tile_org
    ; a band the size of one tile
    mov ax, [dd_tw]
    mov cl, 3
    shr ax, cl
    mov [dd_rb], ax
    mul word [dd_th]
    mov cx, ax
    cmp cx, DD_BANDSZ
    jbe .fits
    mov cx, DD_BANDSZ
.fits:
    mov word [dd_bbase], dd_band
    mov di, dd_band
    xor al, al
    push es
    push ds
    pop es
    cld
    rep stosb
    pop es
    mov al, [dd_gt]
    cmp al, TT_DOT
    je .dot
    cmp al, TT_PILL
    je .pill
    jmp short .emit
.dot:
    mov ax, [dd_tw]
    sub ax, [dd_dotw]
    shr ax, 1
    mov bx, [dd_th]
    sub bx, [dd_doth]
    shr bx, 1
    mov cx, [dd_dotw]
    mov dx, [dd_doth]
    call dd_band_rect
    jmp short .emit
.pill:
    cmp byte [dd_pilon], 0
    je .emit
    mov ax, [dd_tw]
    sub ax, [dd_pilw]
    shr ax, 1
    mov bx, [dd_th]
    sub bx, [dd_pilh]
    shr bx, 1
    mov cx, [dd_pilw]
    mov dx, [dd_pilh]
    call dd_band_rect
.emit:
    mov al, DD_INKDOT
    call dd_pen
    push ds
    pop es
    mov si, dd_band
    mov bp, [dd_rb]
    mov ax, [dd_gx]
    mov bx, [dd_gy]
    mov cx, [dd_tw]
    mov dx, [dd_th]
    call dd_blit
    ret

; dd_dmg_tile - the same, from the [dd_gc]/[dd_gr] the caller already set
dd_dmg_tile:
    mov cl, [dd_gc]
    mov ch, [dd_gr]
    call dd_tile_put
    ret

; =============================================================================
; THE ACTOR BAND (SPEC.md 93.5.1)
; =============================================================================

; -----------------------------------------------------------------------------
; dd_actor_blit - draw actor SI (0..4) where it is now, taking up where it was
; in:  SI = the actor index. Clobbers everything.
;
; Nothing else in this game erases anything: the band is the union of the old
; box and the new one, so the same call that draws the sprite lays black over
; the trail behind it and puts back any dot the trail crossed.
; -----------------------------------------------------------------------------
dd_actor_blit:
    mov bx, si
    shl bx, 1
    cmp byte [dd_alive + si], 0
    je .gone
    ; --- where it is, in whole board pixels ---------------------------------
    mov ax, [dd_x + bx]
    mov cl, 4
    shr ax, cl
    mov [dd_nx], ax
    mov ax, [dd_y + bx]
    shr ax, cl
    mov [dd_ny], ax
    cmp byte [dd_shown + si], 0
    je .fresh
    ; --- ...and where it was ------------------------------------------------
    mov ax, [dd_ox + bx]
    mov [dd_px], ax
    mov ax, [dd_oy + bx]
    mov [dd_py], ax
    ; a move bigger than a tile is a TELEPORT, not a step
    mov ax, [dd_nx]
    sub ax, [dd_px]
    jns .dxp
    neg ax
.dxp:
    cmp ax, [dd_tw]
    ja .warp
    mov ax, [dd_ny]
    sub ax, [dd_py]
    jns .dyp
    neg ax
.dyp:
    cmp ax, [dd_th]
    ja .warp
    jmp short .band
.warp:
    call dd_actor_wipe              ; put the tiles it left back...
.fresh:
    mov ax, [dd_nx]                 ; ...and start the band at the new box
    mov [dd_px], ax
    mov ax, [dd_ny]
    mov [dd_py], ax
.band:
    call dd_band_compose
    call dd_band_emit
    mov bx, si
    shl bx, 1
    mov ax, [dd_nx]
    mov [dd_ox + bx], ax
    mov ax, [dd_ny]
    mov [dd_oy + bx], ax
    mov byte [dd_shown + si], 1
    ret
.gone:
    cmp byte [dd_shown + si], 0
    je .out
    call dd_actor_wipe
    mov byte [dd_shown + si], 0
.out:
    ret

; -----------------------------------------------------------------------------
; dd_untint - put back the tile actor SI has just stopped overlapping
;             (SPEC.md 93.5.4)
; in:  SI = the actor, [dd_nx]/[dd_ny] = where it is now, in whole px.
;
; A band is ONE pen, so a dot inside an actor's band is drawn in that actor's
; colour. That was written up as an artefact lasting two or three frames and it
; is not: nothing ever draws that dot again, so on a colour adapter the ghosts
; leave PERMANENT coloured trails behind them.
;
; The fix is one small blit and only when the actor's box has stopped touching
; a tile at all. An actor's box is exactly one tile wide, so it overlaps at
; most two, and the moment its top-left crosses into the next one the tile
; behind is free of it - which is both when the tile needs putting back and the
; only moment it is safe to.
;
; It is 4bpp only. On one plane a dot and a ghost are both lit and there is
; nothing to put back, and these are the two adapters with the least to spare.
; -----------------------------------------------------------------------------
dd_untint:
    push ax
    push bx
    push cx
    push dx
    mov bl, [dd_ac + si]            ; the tile it is in, carried along rather
    mov bh, [dd_ar + si]            ; than divided out (SPEC.md 93.7)
    mov cl, [dd_ptc + si]
    mov ch, [dd_ptr + si]
    mov [dd_ptc + si], bl
    mov [dd_ptr + si], bh
    cmp byte [dd_bpp], 1
    jbe .out
    cmp byte [dd_shown + si], 0
    je .out                         ; it has never been drawn: nothing to undo
    cmp cl, bl
    jne .put
    cmp ch, bh
    jne .put
    jmp short .out
.put:
    call dd_tile_put                ; CL, CH = the tile it has left
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_actor_wipe - put back the tiles actor SI was last drawn over
; in:  SI = the actor. Clobbers everything but SI.
; -----------------------------------------------------------------------------
dd_actor_wipe:
    push si
    mov bx, si
    shl bx, 1
    mov ax, [dd_ox + bx]
    mov [dd_wx], ax
    mov ax, [dd_oy + bx]
    mov [dd_wy], ax
    ; the sprite box covers at most two tiles each way
    mov ax, [dd_wx]
    xor dx, dx
    div word [dd_tw]
    mov [dd_wc], ax
    mov ax, [dd_wy]
    xor dx, dx
    div word [dd_th]
    mov [dd_wr], ax
    mov bx, 0
.r:
    mov cx, 0
.c:
    push bx
    push cx
    mov ax, [dd_wc]
    add ax, cx
    mov cl, al
    mov ax, [dd_wr]
    add ax, bx
    mov ch, al
    call dd_tile_put
    pop cx
    pop bx
    inc cx
    cmp cx, 2
    jbe .c
    inc bx
    cmp bx, 2
    jbe .r
    pop si
    ret

; -----------------------------------------------------------------------------
; dd_band_compose - build the union band for actor SI into dd_band
; in:  SI = the actor, [dd_nx]/[dd_ny] where it is, [dd_px]/[dd_py] where it
;      was. Out: [dd_bx0]/[dd_by0] the band's board origin, [dd_bw]/[dd_bh]
;      its extent, [dd_rb] its stride.
; -----------------------------------------------------------------------------
dd_band_compose:
    ; --- the union box ------------------------------------------------------
    mov ax, [dd_nx]
    mov bx, [dd_px]
    cmp bx, ax
    jae .x0
    mov ax, bx
.x0:
    mov [dd_bx0], ax                ; the leftmost of the two boxes
    mov ax, [dd_nx]
    mov bx, [dd_px]
    cmp bx, ax
    jbe .x1
    mov ax, bx
.x1:
    add ax, [dd_tw]
    mov [dd_bx1], ax
    mov ax, [dd_ny]
    mov bx, [dd_py]
    cmp bx, ax
    jae .y0
    mov ax, bx
.y0:
    mov [dd_by0], ax
    mov ax, [dd_ny]
    mov bx, [dd_py]
    cmp bx, ax
    jbe .y1
    mov ax, bx
.y1:
    add ax, [dd_th]
    mov [dd_by1], ax
    ; --- round the x out to the byte grid -----------------------------------
    mov ax, [dd_bx0]
    and ax, ~7
    mov [dd_bx0], ax
    mov ax, [dd_bx1]
    add ax, 7
    and ax, ~7
    sub ax, [dd_bx0]
    mov [dd_bw], ax
    mov cl, 3
    shr ax, cl
    mov [dd_rb], ax                 ; the band's stride, in bytes
    mov ax, [dd_by1]
    sub ax, [dd_by0]
    mov [dd_bh], ax
    ; --- a clean band -------------------------------------------------------
    mov ax, [dd_rb]
    mul word [dd_bh]
    mov cx, ax
    cmp cx, DD_BANDSZ
    jbe .fits
    mov cx, DD_BANDSZ               ; cannot happen: the union is one tile plus
.fits:                              ; one step. Clamped rather than trusted
    mov word [dd_bbase], dd_band
    mov di, dd_band
    xor al, al
    push es
    push ds
    pop es
    cld
    rep stosb
    pop es
    ; --- the dots the band crosses, out of dd_grid --------------------------
    call dd_band_dots
    ; --- and the sprite, at the bit offset its x landed on ------------------
    call dd_band_sprite
    ret

; -----------------------------------------------------------------------------
; dd_band_dots - stamp every dot the band overlaps into it
; The band is at most two tiles each way, so this is a 3x3 walk with a test.
; -----------------------------------------------------------------------------
dd_band_dots:
    cmp byte [dd_bpp], 1
    jbe .lit
    ret                             ; **NOT ON A COLOUR ADAPTER** (SPEC.md
                                    ; 93.5.4). A band is one pen, so a dot
                                    ; stamped into an actor's band is drawn in
                                    ; that actor's colour - and dd_untint puts
                                    ; the tile back only once the actor has
                                    ; left it, so what the eye gets is a dot
                                    ; that changes colour as a ghost arrives.
                                    ; Leaving the dot OUT instead makes the
                                    ; actor occlude it, which is what a sprite
                                    ; over a tile is supposed to look like -
                                    ; and it is less work, not more.
                                    ; On one plane a dot and a ghost are the
                                    ; same ink, so the stamp is exact and free.
.lit:
    mov ax, [dd_bx0]
    xor dx, dx
    div word [dd_tw]
    mov [dd_wc], ax                 ; the first tile column the band touches
    mov ax, [dd_by0]
    xor dx, dx
    div word [dd_th]
    mov [dd_wr], ax
    xor bx, bx
.r:
    xor cx, cx
.c:
    push bx
    push cx
    mov ax, [dd_wc]
    add ax, cx
    mov [dd_tc], ax
    mov ax, [dd_wr]
    add ax, bx
    mov [dd_tr], ax
    mov cl, [dd_tc]
    mov ch, [dd_tr]
    call dd_tile
    cmp al, TT_DOT
    je .dot
    cmp al, TT_PILL
    je .pill
    jmp short .next
.pill:
    cmp byte [dd_pilon], 0
    je .next
    mov ax, [dd_pilw]
    mov [dd_sw], ax
    mov ax, [dd_pilh]
    mov [dd_sh], ax
    jmp short .stamp
.dot:
    mov ax, [dd_dotw]
    mov [dd_sw], ax
    mov ax, [dd_doth]
    mov [dd_sh], ax
.stamp:
    mov ax, [dd_tc]
    mul word [dd_tw]
    mov bx, [dd_tw]
    sub bx, [dd_sw]
    shr bx, 1
    add ax, bx
    sub ax, [dd_bx0]                ; ...in band coordinates
    js .next
    push ax
    mov ax, [dd_tr]
    mul word [dd_th]
    mov bx, [dd_th]
    sub bx, [dd_sh]
    shr bx, 1
    add ax, bx
    sub ax, [dd_by0]
    mov bx, ax
    pop ax
    js .next
    mov cx, [dd_sw]
    mov dx, [dd_sh]
    call dd_band_rect_c
.next:
    pop cx
    pop bx
    inc cx
    cmp cx, 2
    jbe .c
    inc bx
    cmp bx, 2
    jbe .r
    ret

; dd_band_rect_c - dd_band_rect, clipped to the band's own extent
dd_band_rect_c:
    push ax
    push bx
    push cx
    push dx
    push si                         ; SI is the caller's ACTOR
    cmp ax, [dd_bw]
    jge .out
    cmp bx, [dd_bh]
    jge .out
    mov si, ax
    add si, cx
    sub si, [dd_bw]
    jle .wok
    sub cx, si
    jle .out
.wok:
    mov si, bx
    add si, dx
    sub si, [dd_bh]
    jle .hok
    sub dx, si
    jle .out
.hok:
    call dd_band_rect
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_band_sprite - OR actor SI's current image into the band
; in:  SI = the actor. The image index is [dd_img + SI].
;
; The sprite is a whole number of BYTES wide and the band is on the byte grid,
; so the only shift in the whole renderer is this one: the actor's x modulo 8.
; -----------------------------------------------------------------------------
dd_band_sprite:
    push si
    mov al, [dd_img + si]
    xor ah, ah
    mov bx, DD_SPRSZ
    mul bx
    mov si, dd_spr
    add si, ax                      ; SI = the scaled image
    mov ax, [dd_nx]
    sub ax, [dd_bx0]                ; 0..7 plus whatever it travelled
    mov bx, ax
    push cx
    mov cl, 3
    shr bx, cl
    pop cx
    mov [dd_sbo], bx                ; the byte the sprite starts in
    and ax, 7
    mov [dd_ssh], ax                ; ...and the bit within it
    mov ax, [dd_ny]
    sub ax, [dd_by0]
    mul word [dd_rb]
    add ax, [dd_sbo]
    mov di, dd_band
    add di, ax                      ; DI = the band byte the sprite starts at
    mov cx, [dd_th]
.row:
    push cx
    mov dh, [si]                    ; the image row, left byte first
    xor dl, dl
    cmp word [dd_tw], 16
    jb .one
    mov dl, [si+1]
.one:
    mov cl, [dd_ssh]
    add cl, 8
    mov ax, dx
    shr ax, cl                      ; AL = the byte the row overflows into
    mov bl, al
    mov cl, 8
    sub cl, [dd_ssh]
    mov ax, dx
    shl ax, cl                      ; AH, AL = the other two
    or [di], bl
    or [di+1], ah
    or [di+2], al
    add si, DD_SPRB
    add di, [dd_rb]
    pop cx
    loop .row
    pop si
    ret

; -----------------------------------------------------------------------------
; dd_band_emit - the pen for actor SI, then the band
; -----------------------------------------------------------------------------
dd_band_emit:
    mov al, [dd_inkof + si]
    call dd_pen
    push ds
    pop es
    push si
    mov si, dd_band
    mov bp, [dd_rb]
    mov ax, [dd_bx0]
    mov bx, [dd_by0]
    mov cx, [dd_bw]
    mov dx, [dd_bh]
    call dd_blit
    pop si
    ret

; =============================================================================
; THE FRAME (SPEC.md 93.5.2)
; =============================================================================

; -----------------------------------------------------------------------------
; dd_render - one frame, windowed or in the bracket
; Clobbers everything. Takes the lock itself windowed; in a bracket the lock is
; already held for the whole session and there is no clip to arm.
; -----------------------------------------------------------------------------
dd_render:
    cmp byte [dd_inbr], 0
    jne .draw
    call OSAPI_GFX_LOCK
    mov ax, KERNEL_SEG              ; A WORKER MUST LOAD ES ITSELF - only a
    mov es, ax                      ; CALLBACK arrives with ES = KERNEL_SEG
    mov bx, [dd_win]
    test word [es:bx + W_FLAGS], 2  ; still visible?
    jz .skip
    call OSAPI_WM_CLIP_SET
    jc .skip                        ; not one pixel of us is showing
.draw:
    call dd_draw
    cmp byte [dd_inbr], 0
    jne .out
    call OSAPI_GFX_UNLOCK
    jmp short .out
.skip:
    ; the step ran and the glass did not follow, so every "where it is drawn"
    ; word is now a claim about pixels nobody can see: the next frame that CAN
    ; draw owes a whole one
    mov byte [dd_full], 1
    call dd_forget
    call OSAPI_GFX_UNLOCK
.out:
    ret

; dd_is_attract - CF = 1 when the title screen is what is showing, which is
;                 both the attract loop and the initials being typed over it
dd_is_attract:
    cmp byte [dd_state], DDS_ATTRACT
    je .yes
    cmp byte [dd_state], DDS_ENTER
    je .yes
    clc
    ret
.yes:
    stc
    ret

; dd_text_w - AX = the pixel width of the NUL string at SI, in whole 8px cells
dd_text_w:
    push cx
    push si
    xor cx, cx
.n:
    cmp byte [si], 0
    je .out
    inc si
    inc cx
    cmp cx, DD_TEXTMAX
    jb .n
.out:
    mov ax, cx
    mov cl, 3
    shl ax, cl
    pop si
    pop cx
    ret

; dd_forget - nothing on the glass is ours any more
dd_forget:
    push si
    xor si, si
.a:
    mov byte [dd_shown + si], 0
    inc si
    cmp si, DD_NACT
    jb .a
    pop si
    ret

; -----------------------------------------------------------------------------
; dd_draw - the picture, under whatever lock the caller has
; -----------------------------------------------------------------------------
dd_draw:
    inc word [dd_frames]            ; the ONE diagnostic this package keeps:
                                    ; SPEC.md 93.6's claim is that the frame
                                    ; is the tick, and a claim about a rate
                                    ; needs a count to check it against
    cmp byte [dd_ok], 0
    je dd_draw_toosmall
    cmp byte [dd_full], 0
    je .parts
    inc word [dd_fulls]
    call dd_draw_all
    mov byte [dd_full], 0
    jmp short .over
.parts:
    call dd_is_attract
    jc .attract
    call dd_pill_refresh
    call dd_fruit_draw
    xor si, si
.act:
    call dd_actor_blit
    inc si
    cmp si, DD_NACT
    jb .act
    cmp byte [dd_hudd], 0
    je .over
    call dd_hud_draw
    mov byte [dd_hudd], 0
    jmp short .over
.attract:
    call dd_attract_draw
.over:
    call dd_overlay
    cmp byte [dd_abon], 0
    je .out
    push bx
    push si
    mov bx, [dd_win]
    mov si, dd_ablines
    call os88ui_about_d
    pop si
    pop bx
.out:
    ret

; A surface too small for a board says so rather than drawing a broken one.
dd_draw_toosmall:
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [dd_cx]
    mov bx, [dd_cy]
    mov cx, ax
    add cx, [dd_cw]
    dec cx
    mov dx, bx
    add dx, [dd_ch]
    dec dx
    call OSAPI_GFX_FILL
    mov si, dd_s_small
    mov bx, [dd_cx]
    add bx, 8
    mov dx, [dd_cy]
    add dx, 8
    mov al, DD_INKTXT
    call dd_text
    ret

; -----------------------------------------------------------------------------
; dd_draw_all - everything: the ground, the walls, the dots, the HUD, everybody
; -----------------------------------------------------------------------------
dd_draw_all:
    mov al, CBLACK
    call OSAPI_SET_COLOR
    mov ax, [dd_cx]
    mov bx, [dd_cy]
    mov cx, ax
    add cx, [dd_cw]
    dec cx
    mov dx, bx
    add dx, [dd_ch]
    dec dx
    call OSAPI_GFX_FILL             ; the ONE full-surface fill in this game,
                                    ; and it happens when the window is
                                    ; painted rather than when it is playing
    call dd_forget
    call dd_is_attract
    jc .attract
    call dd_walls_blit
    call dd_dots_blit
    call dd_pills_blit
    call dd_hud_draw
    mov byte [dd_hudd], 0
    call dd_fruit_force
    xor si, si
.act:
    call dd_actor_blit
    inc si
    cmp si, DD_NACT
    jb .act
    ret
.attract:
    call dd_attract_all
    ret

; -----------------------------------------------------------------------------
; dd_pill_refresh - the pellets' blink, on the glass
; Only when the phase actually turned over, and only the four tiles.
; -----------------------------------------------------------------------------
dd_pill_refresh:
    cmp byte [dd_pilrf], 0
    je .out
    mov byte [dd_pilrf], 0
    call dd_pills_blit
.out:
    ret

; -----------------------------------------------------------------------------
; dd_fruit_draw / dd_fruit_force - the fruit under the house
; -----------------------------------------------------------------------------
dd_fruit_draw:
    cmp byte [dd_frdirty], 0
    je .out
    mov byte [dd_frdirty], 0
    call dd_fruit_force
.out:
    ret

dd_fruit_force:
    push si
    cmp word [dd_fruit], 0
    je .gone
    ; the fruit is one tile, drawn as its own band the same way an actor is
    mov ax, [dd_tw]
    mov cl, 3
    shr ax, cl
    mov [dd_rb], ax
    mul word [dd_th]
    mov cx, ax
    cmp cx, DD_BANDSZ
    jbe .ffits
    mov cx, DD_BANDSZ
.ffits:
    mov word [dd_bbase], dd_band
    mov di, dd_band
    xor al, al
    push es
    push ds
    pop es
    cld
    rep stosb
    pop es
    mov si, dd_spr + SP_FRUIT * DD_SPRSZ
    mov di, dd_band
    mov cx, [dd_th]
.row:
    mov al, [si]
    mov [di], al
    cmp word [dd_tw], 16
    jb .one
    mov al, [si+1]
    mov [di+1], al
.one:
    add si, DD_SPRB
    add di, [dd_rb]
    loop .row
    mov al, DD_INKFRU
    call dd_pen
    push ds
    pop es
    mov si, dd_band
    mov bp, [dd_rb]
    mov ax, DD_FRUITC
    mul word [dd_tw]
    push ax
    mov ax, DD_FRUITR
    mul word [dd_th]
    mov bx, ax
    pop ax
    mov cx, [dd_tw]
    mov dx, [dd_th]
    call dd_blit
    pop si
    ret
.gone:
    mov cl, DD_FRUITC
    mov ch, DD_FRUITR
    call dd_tile_put
    pop si
    ret

; =============================================================================
; THE HUD - a column beside the board (SPEC.md 93.3.1)
; =============================================================================

; -----------------------------------------------------------------------------
; dd_hud_draw - score, high score, level, and the lives still in hand
; Clobbers everything.
; -----------------------------------------------------------------------------
dd_hud_draw:
    mov ax, [dd_hy]
    mov [dd_hrow], ax
    mov si, dd_s_score
    call dd_hud_label
    mov ax, [dd_score]
    mov dx, [dd_score+2]
    call dd_hud_num
    call dd_hud_gap
    mov si, dd_s_high
    call dd_hud_label
    call dd_hs_top                  ; DX:AX = the table's top row, or this
    call dd_hud_num                 ; game's score if it has passed it
    call dd_hud_gap
    mov si, dd_s_level
    call dd_hud_label
    mov al, [dd_level]
    xor ah, ah
    xor dx, dx
    call dd_hud_num
    call dd_hud_gap
    call dd_hud_lives
    ret

dd_hud_label:
    push ax
    push bx
    push cx
    push dx
    mov bx, [dd_hx]
    mov dx, [dd_hrow]
    mov al, DD_INKTXT
    call dd_text
    mov ax, [dd_hrow]
    add ax, DD_HUDROW
    mov [dd_hrow], ax
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; dd_hud_num - DX:AX as decimal, padded to the HUD's width so the old digits
;              go with the new ones - a shorter number over a longer one is the
;              classic way to leave a stray digit on the glass
dd_hud_num:
    push si
    call dd_dec32
    mov si, dd_numbuf
    call dd_hud_label
    pop si
    ret

dd_hud_gap:
    push ax
    mov ax, [dd_hrow]
    add ax, 4
    mov [dd_hrow], ax
    pop ax
    ret

; -----------------------------------------------------------------------------
; dd_hud_lives - the lives in hand, drawn as SMILES rather than as characters
;
; One band wide enough for the CEILING of five, with the slots that are not
; owed left as paper: so a life lost is the same one call, and there is no
; erase to pair with it.
; -----------------------------------------------------------------------------
DD_LIVEMAX equ 5

dd_hud_lives:
    push si
    mov si, dd_s_lives
    call dd_hud_label
    mov al, [dd_lives]
    cmp al, DD_LIVEMAX
    jbe .n
    mov al, DD_LIVEMAX
.n:
    mov [dd_ltmp], al
    ; a clean band, five tiles wide
    mov ax, [dd_tw]
    mov bx, DD_LIVEMAX
    mul bx
    mov cl, 3
    shr ax, cl
    mov [dd_rb], ax
    mov word [dd_bbase], dd_tband
    mul word [dd_th]
    mov cx, ax
    cmp cx, DD_TBANDSZ
    jbe .lfits
    mov cx, DD_TBANDSZ
.lfits:
    mov di, dd_tband
    xor al, al
    push es
    push ds
    pop es
    cld
    rep stosb
    pop es
    ; ...and one Smiles a life, byte-aligned, so no shift is needed
    xor bx, bx
.life:
    cmp bl, [dd_ltmp]
    jae .emit
    push bx
    mov ax, bx
    mul word [dd_tw]
    mov cl, 3
    shr ax, cl
    mov di, dd_tband
    add di, ax                      ; the slot's first band byte
    mov si, dd_spr + (SP_PAC + DIR_L * 3 + 1) * DD_SPRSZ
    mov cx, [dd_th]
.row:
    mov al, [si]
    mov [di], al
    cmp word [dd_tw], 16
    jb .one
    mov al, [si+1]
    mov [di+1], al
.one:
    add si, DD_SPRB
    add di, [dd_rb]
    loop .row
    pop bx
    inc bx
    cmp bx, DD_LIVEMAX
    jb .life
.emit:
    mov al, [dd_ink]
    call dd_pen
    push ds
    pop es
    mov si, dd_tband
    mov bp, [dd_rb]
    mov ax, [dd_hx]
    add ax, 7
    and ax, ~7                      ; gfx_blit1 wants the byte grid
    mov bx, [dd_hrow]
    mov cx, [dd_tw]
    push dx
    mov dx, DD_LIVEMAX
    push ax
    mov ax, cx
    mul dx
    mov cx, ax
    pop ax
    pop dx
    mov dx, [dd_th]
    call OSAPI_GFX_BLIT1            ; ABSOLUTE: the HUD is not on the board
    mov ax, [dd_hrow]
    add ax, [dd_th]
    mov [dd_hrow], ax
    pop si
    ret

; -----------------------------------------------------------------------------
; dd_dec32 - DX:AX into dd_numbuf, decimal, space-padded to DD_NUMW
; -----------------------------------------------------------------------------
DD_NUMW equ 9

dd_dec32:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, dd_numbuf + DD_NUMW     ; written backwards from its NUL
    mov byte [di], 0
    mov cx, DD_NUMW
.digit:
    dec di
    push cx
    mov cx, ax                      ; the standard 32-by-16 divide: the high
    mov ax, dx                      ; word first, its remainder carried into
    xor dx, dx                      ; the low one
    div word [dd_ten]
    mov bx, ax
    mov ax, cx
    div word [dd_ten]
    mov cx, dx                      ; CX = this digit
    mov dx, bx                      ; DX:AX = what is left
    add cl, '0'
    mov [di], cl
    pop cx
    mov bx, ax
    or bx, dx
    jz .done
    dec cx
    jnz .digit
.done:
    mov si, di                      ; left-justify...
    mov di, dd_numbuf
.mv:
    mov al, [si]
    mov [di], al
    inc si
    inc di
    or al, al
    jnz .mv
    dec di                          ; ...and pad the rest with spaces, because
    mov cx, dd_numbuf + DD_NUMW     ; FONT_RUN is opaque over the cells it
    sub cx, di                      ; draws and no further: a shorter number
    jcxz .out                       ; over a longer one leaves a stray digit
.pad:
    mov byte [di], ' '
    inc di
    loop .pad
    mov byte [di], 0
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

dd_ten: dw 10

; =============================================================================
; THE OVERLAY - one centred line over the board, in the states that want one
;
; It sits on the row under the ghost house, which is the one row of the board
; that is EMPTY in every layout: a message there covers no dot, so taking it
; down is a black fill and not a repaint. The line that put it up is opaque
; (`font_run`), so nothing has to erase it before it changes either.
; =============================================================================
dd_overlay:
    mov si, 0
    mov al, [dd_state]
    cmp al, DDS_READY
    je .ready
    cmp al, DDS_OVER
    je .over
    cmp al, DDS_CLEAR
    je .clear
    cmp al, DDS_PLAY
    je .play
    jmp short .none
.play:
    cmp byte [dd_paused], 0
    je .none
    mov si, dd_s_paused
    jmp short .put
.ready:
    mov si, dd_s_ready
    jmp short .put
.over:
    mov si, dd_s_over
    jmp short .put
.clear:
    mov bx, [dd_anim]
    and bx, 2
    jz .none
    mov si, dd_s_clear
.put:
    call dd_centre_line
    ret
.none:
    cmp word [dd_ovw], 0
    je .out
    mov al, CBLACK                  ; a message came down: the row under it is
    call OSAPI_SET_COLOR            ; empty board, so black is the whole erase
    mov ax, [dd_ovx]
    mov bx, [dd_ovy]
    mov cx, ax
    add cx, [dd_ovw]
    dec cx
    mov dx, bx
    add dx, 7
    call OSAPI_GFX_FILL
    mov word [dd_ovw], 0
    mov byte [dd_frdirty], 1        ; ...and the fruit shares that row
.out:
    ret

; dd_centre_line - SI = a NUL string, centred on the board on the empty row
;                  below the ghost house, and banked so it can be taken down
dd_centre_line:
    push ax
    push bx
    push cx
    push dx
    push si
    call dd_text_w                  ; AX = its width in whole cells
    mov [dd_ovw], ax
    mov cx, [dd_mw]
    sub cx, ax
    shr cx, 1
    add cx, [dd_bdx]
    and cx, ~7
    mov [dd_ovx], cx
    mov ax, DD_FRUITR
    mul word [dd_th]
    mov dx, ax
    mov ax, [dd_th]
    sub ax, 8
    jns .mid
    xor ax, ax
.mid:
    shr ax, 1
    add dx, ax
    add dx, [dd_bdy]
    mov [dd_ovy], dx
    mov bx, cx
    mov al, DD_INKTXT
    call dd_text
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
