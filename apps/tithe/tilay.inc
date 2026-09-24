; =============================================================================
; os8088 - apps/tithe/tilay.inc
;
; THE LAYOUT TABLE (SPEC.md 97.2, 97.3). Computed once per size change and
; never inside a frame - a resize is not a thing that happens during a frame,
; which is `ddlay.inc`'s rule one game along (SPEC.md 93.3) and for its reason.
;
; SCREEN_W AND SCREEN_H ARE NOT READ HERE. They are VGA reference values and
; are wrong on two adapters of three (SPEC.md 39); what is read is OSAPI_VIDEO
; for the adapter and OSAPI_WM_GEOM / OSAPI_WM_CONTENT for the box we actually
; got. A window can be dragged across a display seam and come back a different
; depth without changing size at all, so the geometry is re-derived and not
; remembered.
; =============================================================================

TI_COLS     equ 4                 ; the grid is 4 x 5 on EVERY adapter
TI_ROWS     equ 5                 ; (SPEC.md 97.2); what changes is the CELL
TI_CELLS    equ TI_COLS * TI_ROWS

; --- one row of the geometry table, in the order the fields are copied -------
TI_G_CW     equ 0                 ; cell width  - A MULTIPLE OF 8, which is
TI_G_CH     equ 2                 ; what makes every cell's x satisfy
TI_G_RISE   equ 4                 ; gfx_blit1's one alignment rule for free
TI_G_BW     equ 6                 ; the sprite band - also a multiple of 8
TI_G_BH     equ 8
TI_G_HUD    equ 10               ; rows of HUD above the board
TI_G_PAN    equ 12               ; columns of card panel down the right
TI_G_BASEW  equ 14               ; columns of BASE either side of the grid
; NUMS IS GONE. It was ROWS of numbers a cell carries beside its figure - a
; layout-table decision, 2 normally and 1 on CGA - and the small face (SPEC.md
; 97.4.1.1) made it arithmetic instead: `ti_cellnum` divides the cell's own
; height by the face's and caps at four, so an adapter states as many stats as
; it has room for without a table row saying so. The rule that field was an
; instance of still stands; this stopped being an instance of it.
TI_G_CARDH  equ 16               ; a hand row's height in the card panel
TI_G_INSX   equ 18               ; the band's inset inside its cell, which is
                                 ; ALSO the width of the stat column left of it
TI_G_SIZE   equ 20
TI_GCGA     equ 2                 ; the surface index a CGA gets (ti_georow)

; THE FULLSCREEN HAND (SPEC.md 97.4.12) is derived rather than tabled: the
; card is as tall as the rows under the board allow, up to a portrait's 112.
TI_HLIFT    equ 6                 ; rows a hovered card RISES
TI_HGAP     equ 2                 ; rows between the board and the hand
TI_HCARDMIN equ 64                ; a card shorter than this is not a
                                  ; portrait - and 64 is one on a Hercules,
                                  ; whose pixels are ~1.55 times as tall as
                                  ; they are wide
TI_HCARDMAX equ 112
TI_HCOMMITW equ 64                ; the COMMIT column's least width
TI_BASEGAP  equ 32                ; ...and how far out a fullscreen base may
                                  ; stand from its rear column
TI_RESW     equ 24                ; P2's resource block, stacked...
TI_RESWSIDE equ 56                ; ...and in one row (ti_res_draw)

; -----------------------------------------------------------------------------
; ti_layout - fill the layout state from the live content box
; in:  [ti_win]; ti_full says which VGA row to take
; out: every ti_* below set; CF=1 the box cannot hold a board
; clobbers: flags (every register preserved)
; -----------------------------------------------------------------------------
; -----------------------------------------------------------------------------
; ti_georow - which row of the geometry table this machine wants right now
; out: SI = the row
; clobbers: AX, BX, CX, DX, flags
;
; Its own proc because ti_relayout_ck asks the same question every paint, to
; decide whether anything has to be cut at all - an adapter change moves the
; row without moving the content box by one pixel (SPEC.md 39.11.2), so the
; box alone is not the cache key.
; -----------------------------------------------------------------------------
ti_georow:
    call OSAPI_VIDEO                ; AX=w BX=h CX=dock row DL=adapter DH=bpp
    mov si, ti_geo_vgaw
    mov word [ti_gidx], 0           ; THE INDEX IS SET WITH THE POINTER, and
    cmp dh, 1                       ; not derived from it: TI_G_SIZE is 20, so
    jbe .mono                       ; a pointer difference is a DIVIDE where
    ret                             ; four stores are free. SPEC.md's own rule
                                    ; is to branch on DEPTH, and on the adapter
                                    ; only to tell the two 1bpp ones apart.
                                    ; ONE VGA ROW, windowed and fullscreen
                                    ; alike (SPEC.md 97.4.12): a fullscreen
                                    ; board of its own was 366 rows with its
                                    ; lip and cliff and left 78 for a hand -
                                    ; a card 70 tall, which is not a
                                    ; portrait - so it and its art are gone
.mono:
    mov si, ti_geo_herc
    mov word [ti_gidx], 1
    cmp dl, VID_CGA
    jne .have
    mov si, ti_geo_cga
    mov word [ti_gidx], 2
.have:
    ret

ti_layout:
    push ax
    push bx
    push cx
    push dx
    push si
    push di

    call ti_georow
    mov [ti_geo], si                ; ...banked, for a reader that wants to
                                    ; know which row this layout came from
    mov ax, [si + TI_G_CW]
    mov [ti_cw], ax
    mov ax, [si + TI_G_CH]
    mov [ti_ch], ax
    mov ax, [si + TI_G_RISE]
    mov [ti_rise], ax
    mov ax, [si + TI_G_BW]
    mov bx, [si + TI_G_BH]
    and ax, 0FFF8h                  ; gfx_blit1's one rule
    or ax, ax
    jnz .bwok
    mov ax, 8
.bwok:
    mov [ti_bw], ax
    or bx, bx
    jnz .bhok
    mov bx, 1
.bhok:
    mov [ti_bh], bx
    mov ax, [si + TI_G_HUD]
    mov [ti_hud], ax
    mov ax, [si + TI_G_PAN]
    mov [ti_pan], ax
    mov ax, [si + TI_G_BASEW]
    mov [ti_basew], ax
    mov ax, [si + TI_G_CARDH]
    mov [ti_cardh], ax
    mov ax, [si + TI_G_INSX]
    mov [ti_insx], ax
    ; ...AND P2's CELLS ARE ITS MIRROR (SPEC.md 97.4.9): figure then numbers,
    ; so the band sits CW - INSX - BW in and the stat column is the cell's
    ; right-hand INSX. Every term is a multiple of 8, so this is too.
    mov ax, [ti_cw]
    sub ax, [ti_insx]
    sub ax, [ti_bw]
    mov [ti_insx2], ax

    mov ax, [ti_bw]                 ; the band's stride in BYTES, which is the
    shr ax, 1                       ; one number the renderer hands gfx_blit1
    shr ax, 1                       ; three single-bit shifts: an 8088 charges
    shr ax, 1                       ; 8 + 4/bit for the CL form
    mov [ti_bs], ax
    mov ax, [ti_basew]              ; ...and the base band's
    shr ax, 1
    shr ax, 1
    shr ax, 1
    mov [ti_bas], ax
    mov ax, [ti_ch]                 ; a base is THREE LANES tall, centred on
    mov cx, 3                       ; the grid it sits behind
    mul cx
    mov [ti_baseh], ax

    ; --- the board's own box: 4 cells across, and 5 cells plus 3 rises down
    mov ax, [ti_cw]
    mov cx, TI_COLS
    mul cx
    mov [ti_boardw], ax
    mov ax, [ti_ch]
    mov cx, TI_ROWS
    mul cx
    push ax                         ; 5 * CH
    mov ax, [ti_rise]               ; the shear lifts the far column by one
    mov cx, TI_COLS - 1             ; RISE per column, so the box is taller
    mul cx                          ; than the cells by (cols-1) of them...
    mov [ti_lift], ax               ; ...and THAT is what row 0 is pushed DOWN
    pop cx                          ; by, so the highest cell of all - column
    add ax, cx                      ; 3, row 0 - lands exactly on the board's
    mov [ti_boardh], ax             ; top edge
    call ti_place_lay               ; ...AND THE FRONT EDGE UNDER IT: the lip
    jnc .placed                     ; and the cliff grow the board by E rows,
    jmp .no
                                    ; and the arena has to hold this surface
                                    ; (SPEC.md 97.4.10, tiplace.inc)
.placed:

    ; --- where it goes, inside the content box we actually got
    mov bx, [ti_win]
    call OSAPI_WM_GEOM              ; CX = content w, DX = content h
    jc .no
    mov [ti_cw_box], cx
    mov [ti_ch_box], dx
    mov bx, [ti_win]
    call OSAPI_WM_CONTENT           ; AX = content left, DX = top
    mov [ti_ox], ax
    mov [ti_oy], dx

    ; --- THE HAND GOES ALONG THE BOTTOM IN FULLSCREEN (SPEC.md 97.4.12) -----
    ; On VGA and Hercules fullscreen the board leaves a hundred rows below it
    ; and the vertical strip would leave them empty, so the hand becomes a row
    ; of portrait cards there and the board centres above. Not on CGA: its
    ; spare rows are there, but seven cards across 640 at 2.4:1 pixels are
    ; cards that LOOK 91 x 30, and the strip is the right shape for it. The
    ; room is ASKED rather than assumed, and a surface without it keeps the
    ; strip - so this is a layout that is taken when it fits and not a mode.
    mov byte [ti_horiz], 0
    cmp byte [ti_full], 0
    je .strip
    cmp word [ti_gidx], TI_GCGA
    je .strip
    mov ax, [ti_ch_box]
    sub ax, [ti_hud]
    jb .strip
    sub ax, [ti_boardh]
    jb .strip
    cmp ax, TI_HLIFT + TI_HCARDMIN + TI_HGAP
    jb .strip
    mov ax, [ti_bs]                 ; ...and the portraits fit their claim
    mul word [ti_bh]
    mov cx, TI_HAND * TI_POSES      ; one figure per hand SLOT
    mul cx
    or dx, dx
    jnz .strip
    cmp ax, TI_FIGKB * 1024
    ja .strip
    mov byte [ti_horiz], 1
    mov word [ti_pan], 0            ; no strip down the right
.strip:

    ; --- P1's BASE, THE GRID, P2's BASE, THE CARD PANEL -------------------
    ; The bases sit OUTSIDE the grid, behind each player's rear column
    ; (SPEC.md 97.2.1) - column 0 is P1's rear and column 3 is P2's - so the
    ; grid does NOT start at the content's left edge. The content origin is
    ; already a multiple of 8 (SPEC.md 11.94's snap, which ti_entry asks for)
    ; and so are BASEW and CW, so every cell's x and both bases' satisfy
    ; gfx_blit1's one alignment rule without rounding anything.
    mov ax, [ti_ox]
    add ax, 7                       ; THE CONTENT ORIGIN IS NOT NECESSARILY
    and ax, 0FFF8h                  ; ALIGNED, and assuming it is cost this
                                    ; board every pixel it had. WF_SNAP is
                                    ; BEST-EFFORT: wm_snap_ax proposes an x
                                    ; with the content on a multiple of 8 and
                                    ; then REFUSES it when that would push the
                                    ; window off its display's right edge -
                                    ; which a window 634 of 640 wide does. So
                                    ; the first aligned column is derived here,
                                    ; and the <=7 pixels of lead-in are charged
                                    ; to the fit check below
    mov word [ti_bgap], 0
    cmp byte [ti_horiz], 0          ; ...and with no strip down the right the
    je .left                        ; board CENTRES, by a whole number of
    push bx                         ; bytes so every x below stays aligned
    push cx
    mov bx, ax
    sub bx, [ti_ox]                 ; the lead-in
    mov cx, [ti_cw_box]
    sub cx, bx
    sub cx, [ti_boardw]
    jb .nocen
    sub cx, [ti_basew]
    jb .nocen
    sub cx, [ti_basew]
    jb .nocen
    shr cx, 1                       ; the room each side...
    and cx, 0FFF8h
    mov bx, cx                      ; ...and THE BASES STAND OUT IN IT: a
    cmp bx, TI_BASEGAP              ; fullscreen board has the width, so each
    jbe .gap                        ; base moves away from its rear column by
    mov bx, TI_BASEGAP              ; up to TI_BASEGAP and the board and its
.gap:                               ; two bases stay centred as one
    mov [ti_bgap], bx
    sub cx, bx
    add ax, cx
.nocen:
    pop cx
    pop bx
.left:
    mov [ti_b1x], ax                ; P1's base, hard against the left
    add ax, [ti_basew]
    add ax, [ti_bgap]
    mov [ti_bx], ax                 ; ...then the four combat columns
    add ax, [ti_boardw]
    add ax, [ti_bgap]
    mov [ti_b2x], ax                ; ...then P2's, behind their rear column
    mov ax, [ti_oy]
    add ax, [ti_hud]
    mov [ti_by], ax
    ; --- A BASE FOLLOWS THE SHEAR, like the column it stands behind --------
    ; Column 0 is pushed DOWN by the whole LIFT and column 3 is not pushed at
    ; all (SPEC.md 97.3), so a base centred on the BOARD sits between the two
    ; heights it is meant to belong to. Each is centred on ITS OWN column's
    ; span instead: P1's drops by the lift, P2's rises by it, and the two read
    ; as standing on the same ground as the lanes in front of them.
    push cx
    mov ax, [ti_ch]
    mov cx, TI_ROWS
    mul cx                          ; AX = one column's own height
    push ax
    sub ax, [ti_baseh]
    shr ax, 1
    add ax, [ti_by]
    mov [ti_basey2], ax             ; column 3 stands at the board's top edge
    add ax, [ti_lift]
    mov [ti_basey], ax              ; ...and column 0 a whole lift below it

    ; --- and the SHEAR's own empty corners carry the resource counters -----
    ; The strip above column 0 and the strip below column 3 are empty by
    ; construction - the lift is exactly what one is pushed down by and the
    ; other is not - so each player's gold and souls go in their own, beside
    ; the lanes they belong to rather than in a bar across the top.
    mov ax, [ti_bx]
    mov [ti_p1x], ax
    mov ax, [ti_by]
    mov [ti_p1y], ax
    mov ax, [ti_bx]                 ; P2's ENDS AT THE BOARD'S RIGHT EDGE, as
    add ax, [ti_boardw]             ; P1's starts at its left: the stacked
    sub ax, TI_RESW                 ; block is 24 wide (a coin and two digits)
    cmp word [ti_lift], 24          ; and the sideways one, which P2 draws
    jae .p2w                        ; with no swaps, is 56 - ti_res_draw's
    sub ax, TI_RESWSIDE - TI_RESW   ; own test picks between them
.p2w:
    mov [ti_p2x], ax
    pop ax                          ; 5 * CH again
    add ax, [ti_by]
    add ax, [ti_ext]                ; ...past column 3's own lip and cliff,
                                    ; which is where its strip ends now
    ; ...AND P2'S BLOCK SITS DOWN IN ITS STRIP RATHER THAN ON THE BOARD'S
    ; EDGE. P1's hangs from the top of a strip that is empty BELOW it; P2's
    ; starts at the exact row its rear column's last cell ends, so it reads as
    ; wedged against the board. Half the slack is the nudge - 14 pixels on a
    ; VGA, 2 on the two 1bpp rows, which is all those have.
    push bx
    push dx
    mov bx, [ti_lift]
    mov dx, 32                      ; the stacked block: label, gold, souls,
    cmp bx, 24                      ; swaps
    jae .p2slack
    mov dx, 8                       ; ...or the sideways one, which is one row
.p2slack:
    sub bx, dx
    jbe .p2y                        ; no slack at all: leave it where it is
    shr bx, 1
    add ax, bx
.p2y:
    pop dx
    pop bx
    mov [ti_p2y], ax
    pop cx

    ; --- and does it FIT? A refusal is a normal path (PERFORMANCE.md rule 6)
    mov ax, [ti_b1x]
    sub ax, [ti_ox]                 ; the lead-in the snap could not give us
    add ax, [ti_boardw]
    add ax, [ti_basew]
    add ax, [ti_basew]
    add ax, [ti_bgap]
    add ax, [ti_bgap]
    add ax, [ti_pan]
    cmp ax, [ti_cw_box]
    ja .no
    mov ax, [ti_boardh]
    add ax, [ti_hud]
    cmp ax, [ti_ch_box]
    ja .no
    mov ax, [ti_ox]                 ; the card panel is hard against the right
    add ax, [ti_cw_box]             ; edge, which is what rescues CGA: every
    sub ax, [ti_pan]                ; row the hand does not take is a row the
    and ax, 0FFF8h                  ; five lanes get (SPEC.md 97.2)
    mov [ti_panx], ax

    ; --- the band's inset, WHICH IS ALSO THE STAT COLUMN'S WIDTH ------------
    ; It was CENTRED and derived, and that made the columns either side of a
    ; figure 16 pixels - two glyph cells, which holds two digits and no way of
    ; saying what they are (SPEC.md 97.4.1). A number with no icon beside it is
    ; a number the reader has to guess the meaning of, so the inset is a table
    ; field now at 24: three cells, an icon and two digits. What it costs is
    ; that the figure no longer sits at its tile's exact centre - 8 pixels
    ; toward the back of it, which on an isometric tile reads as standing
    ; rather than as an error. INSX is read from the table above; only the
    ; vertical inset is still derived.
    mov ax, [ti_ch]                 ; the figure stands ON
    sub ax, [ti_bh]                 ; the cell's floor, which needs no rounding
    mov [ti_insy], ax
    call ti_panel_lay               ; ...AND THE PANEL, HERE. It used to be
                                    ; ti_board's, which runs AFTER the art is
                                    ; composed - so the mini unit that rides a
                                    ; card was built at a height of ZERO and
                                    ; every card drew a blank corner
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
; ti_cellpos - the top-left of cell (c, r), in screen coordinates
; in:  AL = column 0..3, AH = row 0..4
; out: AX = x, BX = y
; clobbers: AX, BX, flags
;
; SPEC.md 97.3's shear, and the whole of it:
;     x = BX + c * CW
;     y = BY + LIFT + r * CH - c * RISE
; Two cells in one column are CH apart and two in adjacent columns are CW
; apart, so THE RECTANGLES TILE EXACTLY - non-overlap is a property of the
; layout and not a promise the art has to keep.
; -----------------------------------------------------------------------------
ti_cellpos:
    push cx
    push dx
    mov cx, ax                      ; CL = column, CH = row, both banked before
                                    ; the first `mul` eats AX
    mov al, cl
    xor ah, ah
    mul word [ti_cw]
    add ax, [ti_bx]
    push ax                         ; THE X GOES ON THE STACK AND NOT IN DX.
                                    ; Both `mul`s below write DX as their high
                                    ; half, and row 0 multiplies by ZERO - so
                                    ; a banked x came back as 0 and every cell
                                    ; of every column was drawn in column 0,
                                    ; twenty bands piled in one place. Column 0
                                    ; is the one column whose x IS 0, which is
                                    ; why the board looked half-right

    mov al, ch
    xor ah, ah
    mul word [ti_ch]
    add ax, [ti_by]
    add ax, [ti_lift]
    push ax
    mov al, cl                      ; ...less this column's own lift: the far
    xor ah, ah                      ; column sits HIGHER, which is the
    mul word [ti_rise]              ; up-and-to-the-right lane an attack
    mov bx, ax                      ; travels along
    pop ax
    sub ax, bx
    mov bx, ax                      ; BX = y
    pop ax                          ; AX = x
    pop dx
    pop cx
    ret
