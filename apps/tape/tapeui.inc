; =============================================================================
; os8088 - apps/tape/tapeui.inc - the window's layout and its painters
;
; **EVERY RECT IS COMPUTED AT PAINT TIME FROM OSAPI_WM_GEOM, NEVER TABULATED**
; (SPEC.md 88.8). That is not tidiness: a fixed 320 x 146 content box does not
; fit CGA, which is the adapter of the machine class this feature is named
; after - wm_fit's ceiling there is 176 - 1 - 20 = 155, so wm_geom returns
; W_H - (TITLE_H + 1) = 136 rows and a tabulated layout would draw its footer
; through the bottom of its own frame. One formula, anchored at the BOTTOM,
; produces both arrangements: the two footer lines are folded away under
; TP_H_FULL and the panel simply gets taller when there is room.
;
; **EVERY STRING GOES THROUGH OSAPI_FONT_RUN** (SPEC.md 6.1, 6.6, 88.8): the
; status line, the block counter, the file line, the button captions, the
; refusal sentences and the footer. This package introduces no transparent-text
; call site and `tests/textsites.txt` does not move. The buttons and the
; radio/check glyphs are apps/os88ui.inc's, whose filled shapes take font_run
; too (SPEC.md 11.96.17.1) - which is also why they are worth using rather
; than drawing here: a control drawn by hand looks like a different operating
; system, and this one would have had four buttons and four toggles of it.
;
; **THE DRAW BURST IS FIVE CALLS, IN THIS ORDER** (SPEC.md 88.8), and every
; painter here that is not a W_PAINT callback goes through tp_paint_now:
;
;     OSAPI_WM_GEOM       ; jc -> not one pixel of us shows: skip, stay dirty
;     OSAPI_GFX_LOCK
;     OSAPI_WM_CLIP_SET   ; jc -> unlock and skip
;     ...draw...
;     OSAPI_GFX_UNLOCK    ; the clip dies here; nothing to undo
;
; NOTHING HAS ARMED A CLIP FOR A W_ONWAKE PAINTER. wm_draw_win kills the region
; before the title bar and never re-arms it, so a wake handler that draws
; without arming its own paints in ABSOLUTE SCREEN COORDINATES over whatever
; window is on top - which is what the field saw as the FTP log printed across
; the front of a Disk window (SPEC.md 77.33), and what apps/ftpd/ftpd.asm
; carries twenty-five lines about.
;
; GREY ROUNDS TO BLACK on both 1bpp adapters (SPEC.md 39.4), so nothing here
; is greyed by colour: a disabled control is os88ui_btn's OS88UI_DIS, which is
; OSAPI_GFX_PEN and therefore the [gfx_dis] dither as well as the pen (SPEC.md
; 47 rule 1). The one deliberate dither is the progress bar's IN-FLIGHT cell,
; which is a picture and not a state.
; =============================================================================

; --- the arrangement, in content-relative pixels ------------------------------
TP_H_FULL   equ 146             ; at or above this the two footer lines are
                                ; drawn; below it they fold into the status
                                ; line, which is the CGA arrangement
TP_MARG     equ 4
TP_BTN_H    equ 14
TP_BTN_G    equ 4
TP_HUB      equ 16              ; the reel sprites are 16 x 16
TP_CELL     equ 8               ; ...and a font cell is 8 wide and 8 tall
TP_NBTN     equ 4               ; Choose... / Go / Verify / Stop
TP_NTOG     equ 4               ; Save / Load / Catalog + Compress
TP_NRECT    equ TP_NBTN + TP_NTOG

; the button and toggle indices os88ui_bfind answers, PLUS ONE
TP_B_CHOOSE equ 1
TP_B_GO     equ 2
TP_B_VERIFY equ 3
TP_B_STOP   equ 4
TP_T_SAVE   equ 5
TP_T_LOAD   equ 6
TP_T_CAT    equ 7
TP_T_ZIP    equ 8

; -----------------------------------------------------------------------------
; tp_layout - every rect, from the live geometry
; in:  SI = our window ptr (any context; the answer is only STABLE under the
;      lock, which is when the painters ask)
; out: CF=1 the window is not visible and NOTHING was computed
;      CF=0 and every tp_* layout word is filled, in ABSOLUTE screen pixels
;      Every register preserved
; -----------------------------------------------------------------------------
tp_layout:
    push ax
    push bx
    push cx
    push dx
    push di
    mov bx, si
    call OSAPI_WM_GEOM          ; CX = content width, DX = content height
    jc .out
    mov [tp_cw], cx
    mov [tp_ch], dx
    mov bx, si
    call OSAPI_WM_CONTENT       ; AX = content left, DX = content top
    mov [tp_ox], ax
    mov [tp_oy], dx
    ; --- the vertical stack, anchored at the BOTTOM -------------------------
    mov dx, [tp_ch]
    mov byte [tp_compact], 1
    mov ax, dx
    sub ax, 3                   ; the compact arrangement: buttons at the foot
    cmp dx, TP_H_FULL
    jb .rows
    mov byte [tp_compact], 0
    mov ax, dx
    sub ax, 2 + TP_CELL         ; footer line 2
    mov [tp_ft2_y], ax
    sub ax, TP_CELL + 2         ; ...and line 1 above it
    mov [tp_ft1_y], ax
    sub ax, 6
.rows:
    mov [tp_bt_y2], ax
    sub ax, TP_BTN_H - 1
    mov [tp_bt_y1], ax
    sub ax, 4 + OS88UI_GW       ; the radio/check row
    mov [tp_rad_y], ax
    sub ax, 4 + TP_CELL         ; the status line
    mov [tp_st_y], ax
    sub ax, 4
    mov [tp_pb_y2], ax          ; the progress bar, 12 rows
    sub ax, 11
    mov [tp_pb_y1], ax
    sub ax, 4 + TP_CELL         ; the file line
    mov [tp_fl_y], ax
    sub ax, 4
    mov [tp_pan_y2], ax         ; ...and the cassette panel takes what is left
    ; the hubs, centred in whatever height the panel got
    sub ax, 2 + TP_HUB
    shr ax, 1
    add ax, 2
    mov [tp_hub_y], ax
    ; --- and now make every one of them absolute ----------------------------
    mov ax, [tp_oy]
    add [tp_bt_y1], ax
    add [tp_bt_y2], ax
    add [tp_rad_y], ax
    add [tp_st_y], ax
    add [tp_pb_y1], ax
    add [tp_pb_y2], ax
    add [tp_fl_y], ax
    add [tp_pan_y2], ax
    add [tp_hub_y], ax
    cmp byte [tp_compact], 0
    jne .horiz
    add [tp_ft1_y], ax
    add [tp_ft2_y], ax
.horiz:
    ; --- the horizontal half -------------------------------------------------
    mov ax, [tp_ox]
    mov bx, ax
    add bx, TP_MARG
    mov [tp_x1], bx             ; the left margin, absolute
    add ax, [tp_cw]
    sub ax, TP_MARG + 1
    mov [tp_x2], ax             ; ...and the right
    mov bx, [tp_x1]
    add bx, TP_HUB              ; the supply reel sits one hub in from the left
    mov [tp_hl_x], bx
    mov bx, [tp_x2]
    sub bx, TP_HUB + TP_HUB - 1
    mov [tp_hr_x], bx           ; ...and the take-up one hub in from the right
    call tp_rects_calc
    clc
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_rects_calc - the eight clickable rects, from the same numbers the painters
; use
; out: [tp_rects] filled; every register preserved
;
; THE DRAWN CONTROL AND THE CLICKABLE CONTROL READ THE SAME FOUR WORDS
; (SPEC.md 88.8.2, and fm_hit's discipline in SPEC.md 22): geometry is passed
; as a POINTER to a 4-word inclusive rect, so os88ui_btn and os88ui_bhit are
; looking at one array and cannot drift.
; -----------------------------------------------------------------------------
tp_rects_calc:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    ; --- the four buttons, evenly across the content ------------------------
    mov ax, [tp_x2]
    sub ax, [tp_x1]
    inc ax                      ; AX = the usable width
    sub ax, (TP_NBTN - 1) * TP_BTN_G
    mov cl, 2
    shr ax, cl                  ; AX = one button's width (8086: shift by CL)
    mov [tp_bw], ax
    mov di, tp_rects
    mov bx, [tp_x1]
    mov cx, TP_NBTN
.btn:
    mov [di], bx
    mov ax, [tp_bt_y1]
    mov [di+2], ax
    mov ax, bx
    add ax, [tp_bw]
    dec ax
    mov [di+4], ax
    mov ax, [tp_bt_y2]
    mov [di+6], ax
    add bx, [tp_bw]
    add bx, TP_BTN_G
    add di, 8
    loop .btn
    ; --- the three mode radios, a quarter of the width each -----------------
    mov ax, [tp_x2]
    sub ax, [tp_x1]
    inc ax
    mov cl, 2
    shr ax, cl                  ; AX = the span one radio is given
    mov [tp_tspan], ax
    mov si, tp_toglbl
    mov bx, [tp_x1]
    mov cx, 3
.rad:
    call tp_togrect             ; ...which answers the LABEL's width in AX, so
    add bx, [tp_tspan]          ; the stride comes back out of the variable
    add si, 2
    loop .rad
    ; --- ...and the Compress check, RIGHT-ALIGNED ---------------------------
    ; It is the only control whose x is not a share of the width: it is the
    ; one that must not collide with the radios on a narrow window, and the
    ; right edge is the only anchor that guarantees that.
    push si
    mov si, [si]
    call OSAPI_FONT_WIDTH       ; AX = the label's pixel width
    pop si
    mov bx, [tp_x2]
    sub bx, ax
    sub bx, OS88UI_GW + 2
    call tp_togrect
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_togrect - one toggle's rect, glyph and label together
; in:  BX = its left edge, SI -> the word holding its label's offset, DI = the
;      rect to fill
; out: DI advanced by 8; AX = the label's pixel width; everything else kept
;
; The GLYPH AND ITS WORD ARE ONE CONTROL: a click on `Catalog` selects Catalog,
; which is what every radio in this system does and what a hit rect around the
; 12x12 ring alone would not.
; -----------------------------------------------------------------------------
tp_togrect:
    push bx
    push cx
    push dx
    push si
    mov [di], bx
    mov ax, [tp_rad_y]
    mov [di+2], ax
    add ax, OS88UI_GW - 1
    mov [di+6], ax
    mov si, [si]
    call OSAPI_FONT_WIDTH       ; AX = the label's width in pixels
    add bx, OS88UI_GW + 2
    add bx, ax
    mov [di+4], bx
    pop si
    pop dx
    pop cx
    pop bx
    add di, 8
    ret

; =============================================================================
; THE PAINTERS
; =============================================================================

; -----------------------------------------------------------------------------
; tp_txt - one opaque run, black on white
; in:  CX = x, DX = y, SI = a NUL string in our segment
; out: nothing; every register preserved
;
; ONE PLACE, so that "every string goes through OSAPI_FONT_RUN" is a property
; of this file rather than a habit at thirty call sites. font_run draws the
; cells' ground and their glyphs in a single pass, so nothing here is ever
; momentarily blank and no pixel is written twice (SPEC.md 6.1).
; -----------------------------------------------------------------------------
tp_txt:
    push ax
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_field - a run PADDED to the content width, so it erases what was there
; in:  DX = y, SI = a NUL string in our segment
; out: nothing; every register preserved
;
; The alternative is a gfx_fill and then a font_str, which is the double-draw
; flash this project rates one of the three defects an emulator cannot show
; (PERFORMANCE.md Part 1). Padding costs the same single pass and erases the
; line for nothing.
; -----------------------------------------------------------------------------
tp_field:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, tp_line
    call tp_app                 ; DI advanced past the copy
    mov cx, [tp_x2]
    sub cx, [tp_x1]
    inc cx
    mov bx, cx
    mov cl, 3
    shr bx, cl                  ; BX = how many cells fit
    mov cx, di
    sub cx, tp_line             ; CX = how many we wrote
.pad:
    cmp cx, bx
    jae .done
    cmp cx, TP_LINE - 1
    jae .done
    mov byte [di], ' '
    inc di
    inc cx
    jmp short .pad
.done:
    mov byte [di], 0
    mov si, tp_line
    mov cx, [tp_x1]
    call tp_txt
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_app / tp_num / tp_numl - composing a line
;   tp_app   DS:SI -> DS:DI, NUL not copied; DI advanced
;   tp_num   AX as decimal, RIGHT-aligned in CX columns at DS:DI; DI unmoved
;   tp_numl  AX as decimal, left-aligned at DS:DI; DI advanced
;
; tp_num is what makes the per-record repaint four cells instead of forty-four
; (SPEC.md 88.8): the two numbers in the status line are fixed-width and
; right-aligned, so the block counter can be rewritten in place without the
; sentence around it moving.
; -----------------------------------------------------------------------------
tp_app:
    push ax
.next:
    mov al, [si]
    or al, al
    jz .done
    mov [di], al
    inc si
    inc di
    jmp short .next
.done:
    pop ax
    ret

tp_num:
    push ax
    push bx
    push cx
    push dx
    push di
    add di, cx
    dec di
    mov bx, 10
.digit:
    xor dx, dx
    div bx
    add dl, '0'
    mov [di], dl
    dec di
    dec cx
    jcxz .done                  ; the field is full: a wider number is clipped
    or ax, ax                   ; rather than allowed to move the sentence
    jnz .digit
.pad:
    mov byte [di], ' '
    dec di
    loop .pad
.done:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

tp_numl:
    push ax
    push bx
    push cx
    push dx
    push si
    mov si, tp_dbuf + 6         ; the digits fall out least-significant first,
    mov bx, 10                  ; so they are laid down BACKWARDS into a
    xor cx, cx                  ; scratch and copied forwards
.digit:
    xor dx, dx
    div bx
    add dl, '0'
    dec si
    mov [si], dl
    inc cx
    or ax, ax
    jnz .digit
.copy:                          ; ...and NOT pushed on the stack, which is the
    mov al, [si]                ; obvious spelling and the one tools/
    mov [di], al                ; stkbalance.py refuses: a variable number of
    inc si                      ; pushes given back by a `loop` cannot be
    inc di                      ; paired by a static walk, and the annotation
    loop .copy                  ; that silences it would be a promise about
    pop si                      ; this routine that nothing checks
    pop dx
    pop cx
    pop bx
    pop ax
    ret

tp_dbuf:    times 6 db 0        ; 65,535 is five digits

; -----------------------------------------------------------------------------
; tp_paint_now - THE DRAW BURST (SPEC.md 88.8), for every painter that is not
; a W_PAINT callback
; in:  BP = the near proc to run with the clip armed and the lock held
; out: nothing; every register but BP preserved
;
; It is ONE BODY for a reason apps/ftpd/ftpd.asm records at length: two copies
; of this is two chances to forget the clip, and one of them already had.
; -----------------------------------------------------------------------------
tp_paint_now:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, [tp_win]
    or si, si
    jz .out
    mov bx, si
    call OSAPI_WM_GEOM          ; CF=1 = not one pixel of us shows: draw
    jc .out                     ; nothing, and the next event tries again
    call OSAPI_GFX_LOCK
    mov bx, [tp_win]
    call OSAPI_WM_CLIP_SET      ; NOTHING has armed a clip for a W_ONWAKE
    jc .unlock                  ; painter: wm_draw_win kills the region before
    mov si, [tp_win]            ; the title bar and never re-arms it, and the
    call tp_layout              ; gfx_* primitives take ABSOLUTE screen
    jc .unlock                  ; coordinates
    call bp
.unlock:
    call OSAPI_GFX_UNLOCK       ; the clip dies here; nothing to undo
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_draw_all - the whole face. W_PAINT's body, and a state change's
; in:  the layout is computed and the clip armed; SI = our window
; out: nothing; every register preserved
; -----------------------------------------------------------------------------
tp_draw_all:
    push ax
    call tp_draw_panel
    call tp_draw_file
    call tp_draw_bar
    call tp_draw_status
    call tp_draw_togs
    call tp_draw_btns
    call tp_draw_foot
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_erase - white the whole content, for a repaint that is not the kernel's
; in:  the layout is computed; out: nothing, every register preserved
; -----------------------------------------------------------------------------
tp_erase:
    push ax
    push bx
    push cx
    push dx
    mov ax, [tp_ox]
    mov bx, [tp_oy]
    mov cx, ax
    add cx, [tp_cw]
    dec cx
    mov dx, bx
    add dx, [tp_ch]
    dec dx
    mov al, CWHITE
    call OSAPI_SET_COLOR
    mov ax, [tp_ox]
    call OSAPI_GFX_FILL
    mov al, CBLACK
    call OSAPI_SET_COLOR
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_draw_panel - the cassette, or the refusal that stands in its place
; -----------------------------------------------------------------------------
tp_draw_panel:
    push ax
    push bx
    push cx
    push dx
    push si
    mov ax, [tp_x1]
    mov bx, [tp_oy]
    add bx, 2
    mov cx, [tp_x2]
    mov dx, [tp_pan_y2]
    call OSAPI_GFX_FRAME
    cmp byte [tp_hw], TP_HW_OK
    jne .norm
    call tp_draw_reels
    ; --- the window the tape shows through, between the two hubs -----------
    mov ax, [tp_hl_x]
    add ax, TP_HUB + 8
    mov bx, [tp_hub_y]
    add bx, 2
    mov cx, [tp_hr_x]
    sub cx, 8
    mov dx, [tp_hub_y]
    add dx, TP_HUB - 3
    cmp ax, cx
    jae .out                    ; a window too narrow to hold one: the reels
    call OSAPI_GFX_FRAME        ; are the picture and this is the trim
    mov dx, [tp_hub_y]
    add dx, TP_HUB / 2 - 1
    mov ax, [tp_hl_x]
    add ax, TP_HUB + 8
    mov bx, [tp_hr_x]
    sub bx, 8
    call OSAPI_GFX_HLINE        ; ...and the tape itself, spooling across it
    jmp short .out
.norm:
    ; --- SPEC.md 88.1: it names WHICH gate refused, rather than looking
    ; broken. A user who launches TAPE.O88 directly still gets a window ------
    mov dx, [tp_hub_y]
    mov si, tp_r_line1
    mov cx, [tp_x1]
    add cx, 4
    call tp_txt
    add dx, TP_CELL + 2
    call tp_reason              ; SI = the sentence for THIS gate
    mov cx, [tp_x1]
    add cx, 4
    call tp_txt
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_draw_reels - the two hubs, at phase [tp_phase]
; out: nothing; every register preserved
;
; The take-up reel's phase is offset by TP_REEL_OFF so the two do not look
; mechanically linked (SPEC.md 88.8.1). ICON_DRAW's own clip is WHOLE-ICON
; (SPEC.md 25.6), so a partly covered hub is skipped entirely - a covered
; window's reels stop, and no caption here says otherwise.
; -----------------------------------------------------------------------------
TP_REEL_OFF equ 2

tp_draw_reels:
    push ax
    push bx
    push cx
    push dx
    push si
    mov al, [tp_phase]
    call tp_reel_at
    mov cx, [tp_hl_x]
    mov dx, [tp_hub_y]
    call OSAPI_ICON_DRAW
    mov al, [tp_phase]
    add al, TP_REEL_OFF
    call tp_reel_at
    mov cx, [tp_hr_x]
    mov dx, [tp_hub_y]
    call OSAPI_ICON_DRAW
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; tp_reel_at - SI = the phase record for AL, taken mod 8
tp_reel_at:
    push bx
    and al, 7
    mov bl, al
    mov bh, 0
    shl bx, 1
    mov si, [tp_reels + bx]
    pop bx
    ret

; -----------------------------------------------------------------------------
; tp_draw_file - the file line: the name, and the two sizes
; -----------------------------------------------------------------------------
tp_draw_file:
    push ax
    push cx
    push dx
    push si
    push di
    mov di, tp_line2
    mov si, tp_name
    cmp byte [si], 0
    jne .named
    mov si, tp_s_nofile
    call tp_app
    jmp short .draw
.named:
    call tp_app
    mov byte [di], ' '
    inc di
    mov byte [di], ' '
    inc di
    mov ax, [tp_size]
    call tp_numl
    mov si, tp_s_bytes
    call tp_app
    mov ax, [tp_usize]
    cmp ax, [tp_size]
    je .draw                    ; usize is DISPLAY ONLY (SPEC.md 88.9 row 10)
    or ax, ax                   ; and it is only worth a word when it says
    jz .draw                    ; something the size does not
    mov si, tp_s_unp
    call tp_app
    mov ax, [tp_usize]
    call tp_numl
    mov byte [di], ')'
    inc di
.draw:
    mov byte [di], 0
    mov si, tp_line2
    mov dx, [tp_fl_y]
    call tp_field
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_draw_bar - the progress bar: ONE CELL PER RECORD, not a smooth fill
; (SPEC.md 88.8)
;
; It is the pixel the user stares at for 8.7 seconds. It does not lie about
; being smooth, and it carries "we are in segment 4" through the whole freeze.
; -----------------------------------------------------------------------------
tp_draw_bar:
    push ax
    push bx
    push cx
    push dx
    mov ax, [tp_x1]
    mov bx, [tp_pb_y1]
    mov cx, [tp_x2]
    mov dx, [tp_pb_y2]
    call OSAPI_GFX_FRAME
    mov cx, [tp_nrecs]
    jcxz .out
    xor bx, bx
.cell:
    push cx
    mov ax, bx
    call tp_draw_cell
    inc bx
    pop cx
    loop .cell
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_draw_cell - one cell of the bar, in the state record AX is in
; in:  AX = the cell index (0 = the header record)
; out: nothing; every register preserved
;
; done -> filled, IN FLIGHT -> a 50% dither, to come -> white. The dither is a
; PICTURE and not a state, which is why it is the one grey in this window
; (SPEC.md 88.8.1 forbids grey in the CASSETTE, and 39.4 is why).
; -----------------------------------------------------------------------------
tp_draw_cell:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, ax                  ; SI = the index
    mov di, [tp_nrecs]
    or di, di
    jz .out
    cmp si, di
    jae .out
    mov bx, [tp_x2]
    sub bx, [tp_x1]
    dec bx                      ; BX = the bar's inner width
    mov ax, si
    mul bx
    div di                      ; AX = the cell's left, relative
    mov cx, ax
    mov ax, si
    inc ax
    mul bx
    div di                      ; AX = the NEXT cell's left
    dec ax
    add cx, [tp_x1]
    inc cx                      ; CX = x1, absolute
    add ax, [tp_x1]
    inc ax                      ; AX = x2, absolute
    cmp ax, cx
    jb .out                     ; more records than pixels: nothing to draw
    push ax                     ; the PEN is picked before AX becomes a
    push cx                     ; coordinate: OSAPI_SET_COLOR reads AL, and
    mov al, CBLACK              ; getting that order wrong paints the bar in
    cmp si, [tp_cellip]         ; the low byte of an x
    jbe .setc
    mov al, CWHITE
.setc:
    call OSAPI_SET_COLOR
    pop cx
    pop ax
    mov dx, ax
    mov ax, cx
    mov cx, dx                  ; AX = x1, CX = x2 - GFX_FILL's order
    mov bx, [tp_pb_y1]
    inc bx
    mov dx, [tp_pb_y2]
    dec dx
    cmp si, [tp_cellip]
    je .flight
    call OSAPI_GFX_FILL
    jmp short .restore
.flight:
    call OSAPI_GFX_FILL_GRAY
.restore:
    push ax
    mov al, CBLACK
    call OSAPI_SET_COLOR
    pop ax
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_draw_status - the status line, whatever the state is saying
; -----------------------------------------------------------------------------
tp_draw_status:
    push dx
    push si
    call tp_status_str          ; SI = the line, composed
    mov dx, [tp_st_y]
    call tp_field
    pop si
    pop dx
    ret

; -----------------------------------------------------------------------------
; tp_draw_nums - THE PRE-FREEZE REPAINT'S TEXT: the two fixed-width numbers,
; and NOT the caption (SPEC.md 88.8 step 3c)
; out: nothing; every register preserved
;
; Four cells of font_run, ~3.6 ms, against ~71 ms for the row
; (PERFORMANCE.md). The whole point of composing the caption once with
; right-aligned fields is that this is possible at all.
; -----------------------------------------------------------------------------
tp_draw_nums:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp byte [tp_state], TS_RUN
    jne .out
    call tp_run_line            ; recompose, which also re-derives the columns
    mov bx, [tp_nc1]
    call .one
    mov bx, [tp_nc2]
    call .one
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.one:
    mov si, tp_line
    add si, bx
    mov al, [si]
    mov [tp_pair], al
    mov al, [si+1]
    mov [tp_pair+1], al
    mov byte [tp_pair+2], 0
    mov cl, 3
    shl bx, cl                  ; the column, in pixels
    mov cx, [tp_x1]
    add cx, bx
    mov dx, [tp_st_y]
    mov si, tp_pair
    call tp_txt
    ret

; -----------------------------------------------------------------------------
; tp_status_str - compose the status line for the state we are in
; out: SI = a NUL string; every other register preserved
; -----------------------------------------------------------------------------
tp_status_str:
    push ax
    push bx
    push cx
    push dx
    push di
    cmp byte [tp_state], TS_RUN
    je .running
    mov si, [tp_msg]
    or si, si
    jnz .out
    mov si, tp_s_ready
    jmp short .out
.running:
    call tp_run_line
    mov si, tp_line
.out:
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_run_line - "Block  4 of 19 - stopped about  9s", and WHERE the two
; numbers sit
; out: [tp_line] composed, [tp_nc1] and [tp_nc2] = the two fields' COLUMNS;
;      every register preserved
;
; The columns are derived from the composition rather than typed as literals,
; so a change to the wording cannot leave tp_draw_nums writing two digits into
; the middle of a word.
; -----------------------------------------------------------------------------
tp_run_line:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, tp_line
    cmp byte [tp_mode], TM_CAT
    je .cat
    mov si, tp_s_block
    call tp_app
    mov ax, di
    sub ax, tp_line
    mov [tp_nc1], ax
    mov ax, [tp_step]
    inc ax                      ; the header record is block 1 to the user
    mov cx, 2
    call tp_num
    add di, cx
    mov si, tp_s_of
    call tp_app
    mov ax, [tp_nrecs]
    mov cx, 2
    call tp_num
    add di, cx
    mov si, tp_s_frozen
    call tp_app
    mov ax, di
    sub ax, tp_line
    mov [tp_nc2], ax
    call tp_secs                ; AX = this record's wall cost, rounded UP
    mov cx, 2
    call tp_num
    add di, cx
    mov si, tp_s_secs
    call tp_app
    jmp short .done
.cat:
    ; A scan has no length to promise: a tape has no directory and there is no
    ; seek (SPEC.md 88.10 item 14), so what it can honestly say is how many
    ; records have gone past.
    mov si, tp_s_scan
    call tp_app
    mov ax, di
    sub ax, tp_line
    mov [tp_nc1], ax
    mov [tp_nc2], ax
    mov ax, [tp_step]
    mov cx, 2
    call tp_num
    add di, cx
.done:
    mov byte [di], 0
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_secs - what the record in flight costs, in whole seconds, ROUNDED UP
; out: AX = seconds; every other register preserved
;
; From SPEC.md 88.0's own constants and not from a table: TP_FIX is 2.60 s
; whatever the record carries and a 256-byte block is 1.536 s of compressed or
; random data, so one record is 260 + blocks x 154 hundredths. **Every
; published duration rounds UP** - an estimate that runs late on a machine
; that is stopped is the wrong direction of error.
; -----------------------------------------------------------------------------
TP_FIX_CS   equ 260             ; the fixed cost of one record, in hundredths
TP_BLK_CS   equ 154             ; ...and one 256-byte block's

tp_secs:
    push bx
    push cx
    push dx
    mov ax, [tp_step]
    or ax, ax
    jnz .body
    mov ax, 1                   ; the header record is exactly one block
    jmp short .have
.body:
    call tp_blocks              ; AX = blocks in THIS body record
.have:
    mov bx, TP_BLK_CS
    mul bx
    add ax, TP_FIX_CS + 99
    mov bx, 100
    xor dx, dx
    div bx
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tp_total_secs - the WHOLE operation, in seconds, rounded up
; out: AX = seconds; every other register preserved
;
;   total = TP_FIX + hdrblk + (nrec-1) x (TP_FIX + recblk x blk)
;                           + (TP_FIX + lastblk x blk)
;                           + (nrec+1) x (TP_COAST + TP_PAINT)
;
; The last term is not decoration (SPEC.md 88.0): the coast and the pre-freeze
; paint are sequenced strictly before each record, so both are additive wall
; time the user waits through - 0.567 s a record.
; -----------------------------------------------------------------------------
TP_COAST_CS equ 57              ; the coast plus the pre-freeze paint

tp_total_secs:
    push bx
    push cx
    push dx
    push si
    xor si, si                  ; SI = hundredths, running
    mov al, [tp_nrec]
    mov ah, 0
    mov cx, ax                  ; CX = the body records
    inc ax
    mov bx, TP_FIX_CS + TP_COAST_CS
    mul bx
    add si, ax                  ; every record's fixed cost, the header's too
    add si, TP_BLK_CS           ; ...and the header record is one block
    mov al, [tp_recblk]
    mov ah, 0
    mov bx, TP_BLK_CS
    mul bx
    push ax
    mov ax, cx
    dec ax                      ; nrec - 1 FULL records
    pop bx
    mul bx
    add si, ax
    mov al, [tp_lastblk]
    mov ah, 0
    mov bx, TP_BLK_CS
    mul bx
    add si, ax
    mov ax, si
    add ax, 99
    mov bx, 100
    xor dx, dx
    div bx
    pop si
    pop dx
    pop cx
    pop bx
    ret

; -----------------------------------------------------------------------------
; tp_draw_togs - the three mode radios and the Compress check
; -----------------------------------------------------------------------------
tp_draw_togs:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov di, tp_rects + TP_NBTN * 8
    mov si, tp_toglbl
    xor bx, bx                  ; BX = the toggle index, 0..3
.next:
    mov al, OS88UI_GRADIO
    cmp bx, 3
    jne .radio
    mov al, OS88UI_GCHECK
    cmp byte [tp_wantz], 0
    je .state
    or al, OS88UI_GON
    jmp short .state
.radio:
    cmp bl, [tp_mode]
    jne .state
    or al, OS88UI_GON
.state:
    push ax                     ; is THIS the control the press landed on?
    mov ax, bx                  ; [tp_down] is os88ui_bfind's own answer, so
    add ax, TP_NBTN + 1         ; it is the index PLUS ONE and 0 means none
    cmp ax, [tp_down]
    pop ax                      ; (a pop writes no flags)
    jne .nodown
    or al, OS88UI_GDOWN         ; the PRESSED look, DRAWN and not XOR-ed
.nodown:
    mov ah, 0
    call tp_tog_on              ; ...and disabled outranks it (SPEC.md 47 r1)
    jnc .live
    mov ah, 1
.live:
    mov cx, [di]
    mov dx, [tp_rad_y]
    call os88ui_glyph
    mov cx, [di]
    add cx, OS88UI_GW + 2
    mov dx, [tp_rad_y]
    add dx, (OS88UI_GW - TP_CELL) / 2
    push si
    mov si, [si]
    call tp_txt
    pop si
    add si, 2
    add di, 8
    inc bx
    cmp bx, TP_NTOG
    jb .next
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_draw_btns - the four buttons, through apps/os88ui.inc's shared control
;
; [tp_down] is what the painters READ, never a flag threaded from the press
; (SPEC.md 13.8, 88.8.2), which is what makes every repaint agree with the
; glass for free: there is nothing to un-draw and no order to get wrong.
; -----------------------------------------------------------------------------
tp_draw_btns:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov cx, 0                   ; CX = the index, 0..3
.next:
    mov bx, cx
    shl bx, 1
    shl bx, 1
    shl bx, 1                   ; *8: four words a rect (8086: no shl by an
    add bx, tp_rects            ; immediate but 1)
    mov si, cx
    shl si, 1
    mov si, [tp_blbls + si]
    mov di, OS88UI_FILL         ; NOT `xor di, di`: a release redraws this
                                ; button over a PRESSED one, whose interior is
                                ; black, and without the erase the upright
                                ; redraw letters a black caption onto black
    mov ax, cx
    call tp_btn_on
    jnc .live
    or di, OS88UI_DIS           ; ADDS to the fill: a control does not stop
.live:                          ; needing the erase by being greyed
    mov ax, cx
    inc ax
    cmp ax, [tp_down]
    jne .up
    or di, OS88UI_DOWN
.up:
    call os88ui_btn
    inc cx
    cmp cx, TP_NBTN
    jb .next
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; tp_btn_on / tp_tog_on - SPEC.md 88.8.2's greying table, as two predicates
; in:  AL = the control's index (0-based)
; out: CF=0 live, CF=1 disabled; every register preserved
;
; **START IS NEVER GREYED FOR A TRANSIENT REASON AND NEVER ON AN ERROR**
; (SPEC.md 88.8.2, 48.5, 77.17): no deck plugged in, no PLAY pressed, a
; mis-cued or blank tape are all unknowable without playing tape and all
; fixable by the user in five seconds - and a greyed button is a dead end you
; cannot retry from. After an error the caption becomes `Retry` and stays live.
;
; The row SPEC.md 88.8.2 has that this CANNOT implement is "another Tape window
; holds the deck". OSAPI_PIT_LEND has no non-destructive way to ask - the only
; question it answers is OSAPI_PL_CLAIM, which TAKES the deck if it is free -
; so the second window finds out by asking at Go and refuses in words, with
; AH = 3 named. Greying on a state we would have to acquire to learn is worse
; than the refusal.
; -----------------------------------------------------------------------------
tp_btn_on:
    push bx
    mov bl, [tp_state]
    cmp al, TP_B_STOP - 1
    je .stop
    cmp bl, TS_RUN
    je .grey
    cmp bl, TS_CUE
    je .grey
    cmp al, TP_B_CHOOSE - 1
    je .live
    cmp byte [tp_hw], TP_HW_OK
    jne .grey
    cmp al, TP_B_VERIFY - 1
    je .needfile
    cmp byte [tp_mode], TM_SAVE
    jne .live                   ; a Load or a Catalog needs no file of ours
.needfile:
    cmp byte [tp_name], 0
    je .grey
.live:
    pop bx
    clc
    ret
.grey:
    pop bx
    stc
    ret
.stop:
    cmp bl, TS_RUN
    je .live
    cmp bl, TS_CUE
    je .live
    jmp short .grey

tp_tog_on:
    push bx
    mov bl, [tp_state]
    cmp bl, TS_RUN
    je .grey
    cmp bl, TS_CUE
    je .grey
    pop bx
    clc
    ret
.grey:
    pop bx
    stc
    ret

; -----------------------------------------------------------------------------
; tp_draw_foot - the two footer lines, and what they say about each direction
;
; They fold away entirely under TP_H_FULL, which is the CGA arrangement
; (SPEC.md 88.8): what replaces them there is the idle status line, which says
; the same thing when there is nothing else to say.
;
; The second line is MODE-DEPENDENT because the two warnings are about
; different directions, which is SPEC.md 88.2's IRQ1 asymmetry as a sentence:
; a write masks the keyboard because a keystroke there makes a corrupt tape
; nobody can report, and a read leaves it live because Ctrl+Break is the only
; way out of a read that has hung on noise.
; -----------------------------------------------------------------------------
tp_draw_foot:
    push dx
    push si
    cmp byte [tp_compact], 0
    jne .out
    mov si, tp_f_line1
    mov dx, [tp_ft1_y]
    call tp_field
    mov si, tp_f_write
    cmp byte [tp_mode], TM_SAVE
    je .two
    mov si, tp_f_read
.two:
    mov dx, [tp_ft2_y]
    call tp_field
.out:
    pop si
    pop dx
    ret

; -----------------------------------------------------------------------------
; tp_reason - SI = the second line of SPEC.md 88.1's refusal, composed
; out: SI = a NUL string; every other register preserved
; -----------------------------------------------------------------------------
tp_reason:
    push ax
    push di
    mov di, tp_line2
    cmp byte [tp_hw], TP_HW_MODEL
    jne .bios
    mov si, tp_r_model
    call tp_app
    mov al, [tp_model]
    call tp_hex2
    mov byte [di], '.'
    inc di
    mov byte [di], 0
    mov si, tp_line2
    jmp short .out
.bios:
    mov si, tp_r_bios
    cmp byte [tp_hw], TP_HW_BIOS
    je .out
    mov si, tp_r_wip
.out:
    pop di
    pop ax
    ret

; tp_hex2 - AL as two hex digits at DS:DI; DI advanced
tp_hex2:
    push ax
    push bx
    push cx
    mov ah, al
    mov cl, 4
    shr al, cl
    call .one
    mov al, ah
    and al, 0x0F
    call .one
    pop cx
    pop bx
    pop ax
    ret
.one:
    add al, '0'
    cmp al, '9'
    jbe .put
    add al, 7
.put:
    mov [di], al
    inc di
    ret

; =============================================================================
; THE COAST (SPEC.md 88.8.1)
; =============================================================================

; -----------------------------------------------------------------------------
; tp_coast - eight decelerating frames, 560 ms, and then the reels STOP
; out: nothing; every register preserved
;
; **8 frames = one full visual revolution = one record.** The ramp is
; 28, 35, 44, 55, 69, 86, 108, 135 ms: every interval clears the ~22 ms of
; work a frame costs, so the deceleration is real from the first frame - a
; ramp starting at 22 would be draw-bound at the top and read as a flat burst
; that then slows.
;
; It is paced by apps/os88pit.inc's `pit_now` and NOT by OSAPI_WM_TIMER, which
; is kern_big's alone, under SPEC.md 11.99.4's three rules: sample the deadline
; at the TOP of the frame so the drawing is absorbed by the wait rather than
; added to it; compare with `js`, not `jb`; and MISS a frame rather than chase
; one.
;
; A Stop click landing inside the coast is queued and honoured before the next
; record starts - at most 560 ms - which is what [tp_stop] is polled between
; frames for.
; -----------------------------------------------------------------------------
tp_coast:
    push ax
    push bx
    push cx
    push si
    push bp
    mov cx, 8
    mov si, tp_ramp
.frame:
    mov al, [si]
    mov ah, 0
    call tp_arm_ms              ; the deadline FIRST, then the drawing
    mov al, [tp_phase]
    cmp byte [tp_mode], TM_SAVE
    je .fwd
    dec al                      ; Load and Verify run BACKWARDS. Physically a
    jmp short .set              ; cassette runs the same way for both; this is
.fwd:                           ; a legibility choice (SPEC.md 88.8.1)
    inc al
.set:
    and al, 7
    mov [tp_phase], al
    mov bp, tp_draw_reels
    call tp_paint_now
    call tp_wait
    cmp byte [tp_stop], 0
    jne .out
    inc si
    loop .frame
.out:
    pop bp
    pop si
    pop cx
    pop bx
    pop ax
    ret

tp_ramp:    db 28, 35, 44, 55, 69, 86, 108, 135

; -----------------------------------------------------------------------------
; tp_arm_ms / tp_wait - a deadline in 838ns units, and the spin to it
; in:  AX = milliseconds (tp_arm_ms)
; out: nothing; every register preserved
;
; One PIT count is 838 ns and a millisecond is 1,193 of them. The span is
; 32-bit because it has to be: `pit_now`'s own header spends a page on the
; failure of reading the counter alone, where a 561 ms span reports 12 - a
; small plausible number with nothing wrong-looking about it.
; -----------------------------------------------------------------------------
TP_PER_MS   equ 1193

tp_arm_ms:
    push ax
    push bx
    push cx
    push dx
    mov bx, TP_PER_MS
    mul bx                      ; DX:AX = the delta in counts
    mov cx, ax
    mov bx, dx
    call pit_now                ; DX:AX = now (it clobbers exactly those two)
    add ax, cx
    adc dx, bx
    mov [tp_deadline], ax
    mov [tp_deadline+2], dx
    pop dx
    pop cx
    pop bx
    pop ax
    ret

tp_wait:
    push ax
    push dx
.again:
    call pit_now
    sub ax, [tp_deadline]
    sbb dx, [tp_deadline+2]
    js .again                   ; now - deadline is still negative
    pop dx
    pop ax
    ret

; =============================================================================
; THE LAYOUT'S OWN WORDS, and every string this window draws
; =============================================================================
TP_LINE     equ 88              ; a line buffer: 638 px of content is 79 cells

tp_ox:      dw 0                ; the content origin, screen pixels
tp_oy:      dw 0
tp_cw:      dw 0                ; ...and its size, from OSAPI_WM_GEOM
tp_ch:      dw 0
tp_x1:      dw 0                ; the left and right margins, absolute
tp_x2:      dw 0
tp_pan_y2:  dw 0                ; the cassette panel's bottom
tp_hub_y:   dw 0                ; the two hubs
tp_hl_x:    dw 0
tp_hr_x:    dw 0
tp_fl_y:    dw 0                ; the file line
tp_pb_y1:   dw 0                ; the progress bar
tp_pb_y2:   dw 0
tp_st_y:    dw 0                ; the status line
tp_rad_y:   dw 0                ; the radio/check row
tp_bt_y1:   dw 0                ; the buttons
tp_bt_y2:   dw 0
tp_ft1_y:   dw 0                ; the two footer lines, when there is room
tp_ft2_y:   dw 0
tp_bw:      dw 0                ; one button's width
tp_tspan:   dw 0                ; ...and one radio's share
tp_compact: db 0                ; 1 = the CGA arrangement, footer folded away
tp_rects:   times TP_NRECT * 4 dw 0
tp_deadline: dw 0, 0
tp_nc1:     dw 0                ; where the two fixed-width numbers sit, in
tp_nc2:     dw 0                ; COLUMNS, derived by tp_run_line
tp_pair:    db 0, 0, 0          ; ...and the two characters, as a run
tp_line:    times TP_LINE db 0      ; the status line, composed
tp_line2:   times TP_LINE db 0      ; ...the file line's, and the refusal's
tp_line3:   times TP_LINE db 0      ; ...and a message that OUTLIVES the paint
                                    ; that made it: [tp_msg] points here

tp_blbls:   dw tp_l_choose, tp_l_go, tp_l_verify, tp_l_stop
tp_l_choose: db 'Choose...', 0
tp_l_go:    db 'Go', 0
tp_l_retry: db 'Retry', 0       ; SPEC.md 88.8.2: after an error the caption
tp_l_verify: db 'Verify', 0     ; changes and the button STAYS LIVE
tp_l_stop:  db 'Stop', 0

tp_toglbl:  dw tp_l_save, tp_l_load, tp_l_cat, tp_l_zip
tp_l_save:  db 'Save', 0
tp_l_load:  db 'Load', 0
tp_l_cat:   db 'Catalog', 0
tp_l_zip:   db 'Compress', 0

tp_s_block: db 'Block ', 0
tp_s_of:    db ' of ', 0
tp_s_frozen: db ' - stopped about ', 0
tp_s_secs:  db 's', 0
tp_s_scan:  db 'Scanning - records past: ', 0
tp_s_ready: db 'Ready.', 0
tp_s_nofile: db 'No file chosen.', 0
tp_s_bytes: db ' bytes', 0
tp_s_unp:   db ' (', 0

tp_f_line1: db 'Stop takes effect at the end of a block.', 0
tp_f_write: db 'Do not type while writing.', 0
tp_f_read:  db 'Ctrl+Break stops a read at once.', 0

tp_r_line1: db 'No cassette port.', 0
tp_r_model: db 'An IBM PC 5150 feature; model is ', 0
tp_r_bios:  db 'This ROM has no cassette support.', 0
tp_r_wip:   db 'This build has no cassette transport.', 0
