; =============================================================================
; os8088 - apps/os88con.inc
;
; AN 80x25 TEXT CONSOLE - the fourth shared include in apps/, and the third
; carrying code. os88ui.inc is the first and its header is the argument for
; all of them: an include costs each package its own copy and can be revised
; freely because it is source, where a slot costs a published contract.
;
; It exists because there are about to be THREE of these. apps/telnet had the
; only one - a real terminal screen with an attribute per cell, a dirty-row
; bitmap and a composer that writes eight bytes a cell and calls nothing - and
; SPEC.md 96.32's DOS box needs the same thing for its console band, and the
; wave after that needs it again for a DOS program's captured output. A second
; copy would have drifted from the first the day either grew a feature, which
; is what the header of every file in this directory says.
;
; --- USING IT ----------------------------------------------------------------
; `%include "os88con.inc"` AT THE END OF YOUR CODE, just before OS88_BSS -
; os88ui.inc's rule and for its reason: the header and any OS88_ICON16 block
; are at FIXED OFFSETS in the image (SPEC.md 20.2), so code emitted between
; them fails the icon macro's own assertion.
;
; ONE CONSOLE PER PACKAGE, and that is deliberate. os88line.inc takes a
; caller-declared BLOCK because a window may hold two text fields; this file
; declares its own storage instead, because nothing wants two terminals and
; the cost of the other shape lands in the worst possible place: con_compose
; writes eight bytes a cell with no call at all, and addressing the buffer
; through a block would put an indirect base in that inner loop - eighty cells
; a row, twenty-five rows, on a 4.77MHz machine.
;
; --- WHAT YOU OWE IT ---------------------------------------------------------
; THE GEOMETRY, before anything draws. The console does not know where your
; window is and must not guess:
;
;   [con_px]               the text pen's x, in SCREEN pixels, and it must be
;                          a MULTIPLE OF 8 - con_emit hands it to
;                          OSAPI_GFX_BLIT1 (SPEC.md 5.4.2)
;   [con_oy]               ...and the content top
;   [con_topy]             the first text row's offset from that top, so a
;                          carrier can put a bar above the text
;   [con_vcols]/[con_vrows]  how much of the fixed 80x25 is on view
;   [con_vtop]             the first buffer row shown, for a short window
;   [con_mono]             this screen is 1bpp (SPEC.md 70.8.4)
;
; ...and NOTHING ELSE. The window's own left edge, width and height are not in
; that list and deliberately: the console is told where its TEXT goes, so a
; carrier that centres the band, insets it, or puts furniture either side of it
; needs no permission from this file. The extraction carried [con_ox],
; [con_cw] and [con_chh] in before anybody checked who reads them, and the
; answer was that no routine here does - they were telnet's layout with a
; console's prefix on it.
;
; **ASK FOR THEM AT EVERY PAINT, NEVER ONCE AT LAUNCH.** A window can be
; resized, dragged across an extended desktop's seam, or land on an adapter of
; a different size - and a MOVED window does not call your paint proc at all
; (SPEC.md 11.96.12), so a geometry computed once is a geometry describing
; where the window used to be. apps/os88api.inc's header carries that rule.
;
; --- WHAT IT IS ---------------------------------------------------------------
; A FIXED 80x25 buffer of (character, IBM attribute) pairs - text VRAM's own
; layout, so a full-screen renderer is a move and not a translation - plus:
;
;   con_putc / con_clear / con_scrollup / con_scrolldown
;   con_mark / con_markall / con_markcur     the dirty-ROW bitmap
;   con_rows_owed                            draw what is owed, and clear it
;   con_row / con_compose / con_emit         one row: buffer -> band -> glass
;   con_font                                 the 256 CP437 glyphs, once
;
; THE SCREEN IS FIXED AND DOES NOT REFLOW. A terminal that reflows on a resize
; is a terminal whose host has the wrong idea of how wide it is; a resize
; changes how much of the 80x25 is VISIBLE and changes the screen not at all.
;
; REGISTERS: every routine preserves everything except its documented output.
; =============================================================================

CON_COLS     equ 80                 ; the screen is FIXED, not derived
CON_ROWS     equ 25
CON_CELLS    equ CON_COLS * CON_ROWS        ; 2,000 cells...
CON_SCRSZ    equ CON_CELLS * 2              ; ...of a character and an attribute
CON_BAND     equ CON_COLS * 8               ; one composed row, 1bpp, 640 bytes
CON_GLYF     equ 256 * 8                    ; ...and the CP437 face (70.8.6)

%if CON_ROWS > 32
  %error "con_drb is four bytes: CON_ROWS must fit twenty-five bits and no more"
%endif

; THE FACE IS OURS, not the carrier's. con_font builds [con_glyf] out of it at
; launch and nothing else in apps/ reads it, so a carrier that had to include
; it too would be a carrier that can forget to (SPEC.md 70.8.6).
%include "os88cp437.inc"

; WHERE THE BSS LIVES - os88parts.inc's chain, and for its reason: a carrier
; already has its own bss laid out from os88_image_end, so this one is based
; wherever it says and adds CON_BSS to the total it declares.
%ifndef CON_BSS_AT
    %define CON_BSS_AT os88_image_end
%endif

; =============================================================================
; WHICH ROWS ARE OWED - A BITMAP NOW (SPEC.md 70.8.1)
;
; It was a RANGE (SPEC.md 70.4), on a stated assumption: terminal output is
; sequential, so a burst of bytes touches a contiguous run of rows and one
; compare a mark plus one bound at the draw is the whole cost. **CURSOR
; ADDRESSING IS EXACTLY THE THING THAT ASSUMPTION EXCLUDES.** A board that
; draws a menu writes row 3, then row 20, then row 3 again; the range spanning
; them is eighteen rows and seventeen of them are clean, which on the machine
; this is for is about fifty milliseconds of drawing to change two rows.
;
; So it is four bytes and twenty-five bits: bit r of byte r>>3. Both renderers
; walk it, for 70.6's reason unchanged - con_putc runs on the kept worker and
; marks the row it wrote whichever screen is up, so the two cannot drift about
; what changed.
; =============================================================================

; --- con_wpx - AX = the visible text width in PIXELS, from con_vcols ----------
; One routine because two rects are cut to it - the scroll blit's and the
; About panel's fill - and a second copy of `<< 3` is a second opinion about
; how wide the terminal is.
con_wpx:
    push cx
    mov ax, [con_vcols]
    mov cl, 3
    shl ax, cl
    pop cx
    ret

; --- con_bit - BX = a row; out AL = its bit, BX = its byte's index -----------
; The one place the shape of the bitmap is written down, so a mark and a test
; cannot disagree about it. CL is spent and restored by the callers.
con_bit:
    mov cl, bl
    and cl, 7
    mov al, 1
    shl al, cl                      ; `shl reg, CL` is 8086; `shl reg, imm` is
    mov cl, 3                       ; not, and only the imm form is refused
    shr bx, cl
    ret

; --- con_mark - BX = a row that must be redrawn ------------------------------
con_mark:
    push ax
    push bx
    push cx
    cmp bx, CON_ROWS
    jae .out                        ; the cursor may sit one past the end
    call con_bit
    or [con_drb + bx], al
.out:
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_takerow - BX = a row; CF=1 if it was owed, AND ITS BIT IS CLEARED
;
; **THE BIT IS TAKEN, NOT READ AND LATER FORGOTTEN**, and that is a fix rather
; than a style (the w2 review's MAJOR 2b). Both renderers used to walk rows
; 0..24 and then call te_markclr, which zeroes all four bytes - so a con_mark
; the WORKER set for a row the loop had already passed was cleared unread, and
; the character that arrived for row 3 while the loop was on row 18 never
; reached the screen at all. The window was the whole twenty-five-row pass, and
; in full screen (FSXF_KEEPWORKER, SPEC.md 70.8.7) the two really are different
; tasks.
;
; Clearing as it draws makes a lost mark impossible instead of unlikely: a mark
; set for a row already passed stays set and the next pass draws it. The
; read-modify-write is SPEC.md 70.2's own critical section, one byte along -
; `pushf`/`cli` … `popf`, never `cli`/`sti` (SPEC.md 1).
; -----------------------------------------------------------------------------
con_takerow:
    push ax
    push bx
    push cx
    cmp byte [con_scrbusy], 0
    jne .no                         ; a scroll is HALF DONE (the w3 review's
                                    ; MAJOR 1): the buffer has moved and the
                                    ; debt is not visible yet, so a row drawn
                                    ; now is a row the blit is about to move
                                    ; again. One skipped frame, and the mark
                                    ; SURVIVES because this is what clears it
    cmp bx, CON_ROWS
    jae .no
    call con_bit                     ; AL = the bit, BX = its byte
    pushf
    cli
    and al, [con_drb + bx]           ; AL = the bit if it was set, else 0
    xor [con_drb + bx], al           ; ...and a zero XORs nothing, so there is
    popf                            ; no second branch to get wrong
    or al, al
    jz .no
    pop cx
    pop bx
    pop ax
    stc
    ret
.no:
    pop cx
    pop bx
    pop ax
    clc
    ret

; -----------------------------------------------------------------------------
; con_takescroll - AX = the scroll debt, and the counter is zeroed with it
;
; The w2 review's MAJOR 2a. `mov ax, [con_scrl]` … `mov word [con_scrl], 0` is a
; read-modify-write with the same two tasks either side of it, and con_scrollup
; ADDS to that counter: a board that scrolled twice in the window between the
; read and the store lost one of them, VRAM moved N rows where the buffer moved
; N+1, and every row the board did not touch again stayed one line out of place
; for the rest of the session. Nothing short of `^]` repaired it.
; -----------------------------------------------------------------------------
con_takescroll:
    pushf
    cli
    xor ax, ax
    cmp byte [con_scrbusy], 0
    jne .out                        ; ...and the same answer for the same
    mov ax, [con_scrl]               ; reason: the debt is not yet what it is
    mov word [con_scrl], 0           ; going to be
.out:
    popf
    ret

; --- con_markcur - the row the cursor is on ----------------------------------
; Called BOTH SIDES of every cursor move: the underline is composed into the
; band (SPEC.md 70.8.2), so the row it LEFT owes a redraw as much as the row
; it arrived on.
con_markcur:
    push bx
    mov bx, [con_cy]
    call con_mark
    pop bx
    ret

; --- con_markall - every row. **AND THERE IS NO te_markclr**: a bitmap that
; is cleared wholesale is a bitmap that drops the marks another task set
; while it was being walked, which is con_takerow's whole subject.
con_markall:
    mov word [con_drb], 0xFFFF
    mov word [con_drb + 2], 0x01FF   ; ...twenty-five bits and not thirty-two:
    ret                             ; byte 3 carries row 24 alone

; --- con_markup - the bitmap follows the buffer up one row -------------------
; **A DEFECT THE RANGE HAD AND NOBODY COULD FIX CHEAPLY.** A row marked before
; a scroll names a row of the BUFFER, and the scroll moved every row up one:
; row 5's pixels are on the glass at row 4 now, and the mark still says 5. The
; range could only widen to cover both; the bitmap is a 25-bit number, and
; moving every mark down one row is moving that number right one bit.
con_markup:
    shr byte [con_drb + 3], 1        ; ...highest byte first, and the carry then
    rcr byte [con_drb + 2], 1        ; walks down through the other three
    rcr byte [con_drb + 1], 1
    rcr byte [con_drb + 0], 1
    ret

; -----------------------------------------------------------------------------
; con_rows_owed - draw the rows in the dirty range, and clear it
; in:  gfx lock held; out: nothing, all registers preserved
;
; **THIS IS WHAT STOPPED TYPING REDRAWING THE WHOLE TERMINAL.** A character
; echoed back by the host reaches con_putc, which used to leave te_show to
; repaint all eighteen rows - 1,152 glyph cells at PERFORMANCE.md's ~900us
; each on the machine this is for - to change one of them.
; -----------------------------------------------------------------------------
con_rows_owed:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    xor bx, bx
.row:
    call con_takerow                 ; ...which CLEARS the bit it answers for,
    jnc .next                       ; so a mark the worker sets for a row this
    call con_row                     ; loop has passed survives into the next
.next:                              ; pass instead of being dropped
    inc bx
    cmp bx, CON_ROWS
    jb .row
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_scrollpaint - spend [con_scrl] as a BLIT rather than as eighteen runs
; in:  gfx lock held, the carrier's layout run; out: nothing, all registers preserved
;
; The buffer scroll is a rep movsb in te_scrollck and always was; what this
; adds is that the SCREEN follows it by moving the pixels it already has.
; OSAPI_GFX_SCROLL needs the rect on byte columns, which is what the aligned
; pen above bought, and it REFUSES under a clip region that does not wholly
; contain the rect - so every failure falls back to marking the lot, which is
; exactly what happened before this existed.
; -----------------------------------------------------------------------------
con_scrollpaint:
    push ax
    push bx
    push cx
    push dx
    push si
    call con_takescroll              ; ...read and zeroed together (70.8.8)
    or ax, ax
    jz .out
    cmp ax, [con_vrows]
    jae .all                        ; the whole window scrolled away: the blit
                                    ; would move nothing anybody can see
    push ax                         ; ...the ROWS, for the repaint below
    mov cl, 3
    shl ax, cl
    mov si, ax                      ; SI = the pixels to move, positive = up
    mov ax, [con_vrows]
    shl ax, cl
    dec ax                          ; ...the window's last pixel row, from y1
    mov bx, [con_oy]
    add bx, [con_topy]                 ; BX = y1
    mov dx, bx
    add dx, ax                      ; DX = y2
    call con_wpx                     ; AX = the visible width in pixels - the
    mov cx, ax                      ; routine that owns the `<< 3`, so DX (y2)
    add cx, [con_px]                 ; stays out of the width entirely
    dec cx                          ; CX = x2, so x2+1 is a byte column too
    mov ax, [con_px]                 ; AX = x1, a byte column (the carrier's layout)
    call OSAPI_GFX_SCROLL
    pop ax
    jc .all
    mov bx, CON_ROWS                 ; the rows it vacated are OURS to repaint
    sub bx, ax
.mk:
    call con_mark
    inc bx
    cmp bx, CON_ROWS
    jb .mk
    call con_markcur                 ; **AND THE CURSOR'S ROW.** The underline
                                    ; is composed into a band (SPEC.md
                                    ; 70.8.2), so the blit carries it up the
                                    ; window with everything else and the row
                                    ; it LEFT keeps a stale one. A scroll from
                                    ; con_scroll1 always leaves the cursor on
                                    ; the row it opened, which is marked
                                    ; already; a scroll the PARSER asks for
                                    ; (SPEC.md 70.9.3's SU) does not, and the
                                    ; gate found this with a debt spent
                                    ; against a cursor that had not moved
    jmp short .out
.all:                               ; (con_markall covers it on this arm)
    call con_markall
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; THE WINDOWED RENDERER (SPEC.md 70.8.2)
;
; **A GLYPH CALL PER CELL IS NOT AFFORDABLE AND NEVER WAS.** PERFORMANCE.md
; prices an 8x8 cell at ~900us on a 4.77 MHz 8088, so an 80x25 screen lettered
; a cell at a time is 1.8 seconds. The row is COMPOSED instead - eighty cells
; of eight byte stores each, at RAM speed and with no drawing call at all -
; and then put down with OSAPI_GFX_BLIT1, once per ATTRIBUTE RUN, with
; OSAPI_GFX_BLIT1_PEN set to that run's ink and paper.
;
; Both of the blit's alignment demands hold BY CONSTRUCTION: a cell is eight
; pixels, so a run's x and a run's width are multiples of eight whatever the
; run is, and the pen was 70.4's aligned pen already.
;
; EVERY PIXEL IS WRITTEN ONCE. That is PERFORMANCE.md Part 1's rule rather
; than an optimisation, and it is what the erase-then-letter pair the old
; font_run fallback produced could not offer.
; =============================================================================

; --- con_row - BX = a buffer row: compose it, then put it down ---------------
con_row:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    cmp bx, [con_vtop]
    jb .done                        ; above the visible window on a short one
    call con_compose
    call con_emit
.done:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_compose - BX = a buffer row -> con_band, CON_COLS bytes a scanline
;
; Eight byte stores a cell and no call at all. The 1bpp polarity (SPEC.md
; 70.8.4) is folded in here as an XOR mask, because the CALLS are identical
; either way and the calls are what the machine is priced in: a cell whose
; background is not black and whose foreground is black or dark grey is drawn
; INVERSE, which is the only rule that keeps a board's highlighted menu item
; from rendering as nothing at all in one bit.
;
; **THE PREDICATE IS A MACRO AND IS EMITTED TWICE**, once in the cell loop and
; once for the cursor's own cell, because those two must not be able to
; disagree and neither may pay for a call: a `call` a cell is eighty of them a
; row on a machine PERFORMANCE.md prices a near call at 11us on. One source,
; two emissions - and it is the third reader of 70.8.4's rule, te_tx_mattr
; being the second.
;
;   in:  AL = the cell's attribute, DL = which bits are the background
;   out: CH = 00 (a lit glyph on dark paper) or FF (INVERSE)
%macro CON_INVMASK 0
    xor ch, ch
    cmp byte [con_mono], 0
    je %%done                       ; a colour screen takes its polarity from
    test al, 0x07                   ; the PEN and never from the band
    jnz %%done                      ; a foreground that is not 0 or 8 reads as
    test al, dl                     ; text whatever the paper is
    jz %%done
    mov ch, 0xFF
%%done:
%endmacro

con_compose:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov [con_rr], bx                 ; the row, for the cursor test at the foot:
    mov ax, CON_COLS * 2             ; every register is spent by then
    mul bx                          ; **MUL WRITES DX** (SPEC.md 1)
    mov si, con_scr
    add si, ax                      ; SI = the row's first cell
    mov [con_rowp], si               ; ...kept, because the cursor block at the
                                    ; foot needs the CURSOR's cell and SI has
                                    ; walked to the end of the row by then
    mov di, con_band
    mov cl, [con_vcols]              ; <= CON_COLS, clamped in the carrier's layout
    mov dl, 0x70                    ; which bits are a BACKGROUND: bit 7 joins
    cmp byte [con_mono], 0           ; them under iCE, where it is the fourth
    jne .cell                       ; background bit and not blink (70.8.9)
    cmp byte [con_ice], 0            ; **AND ONLY ON A COLOUR SCREEN.** This
    je .cell                        ; widened the mask above the [con_mono] test,
    mov dl, 0xF0                    ; so 0x88 - blink set, black on black - read
.cell:                              ; as INVERSE windowed on CGA and as plain
                                    ; in full screen on MDA, where te_tx_mattr
                                    ; always masks 0x70. The two 1bpp
                                    ; predicates ARE one predicate (70.8.4), and
                                    ; on one bit a bright background means
                                    ; nothing at all
    mov al, [si+1]
    CON_INVMASK                      ; -> CH, the cell's XOR mask
    mov bl, [si]
    xor bh, bh
    shl bx, 1                       ; three single shifts: `shl reg, imm` is
    shl bx, 1                       ; not 8086 and `mov cl, 3` would cost the
    shl bx, 1                       ; cell counter
    add bx, con_glyf
    mov ah, [bx]
    xor ah, ch
    mov [di], ah
    mov ah, [bx+1]
    xor ah, ch
    mov [di + CON_COLS], ah
    mov ah, [bx+2]
    xor ah, ch
    mov [di + CON_COLS*2], ah
    mov ah, [bx+3]
    xor ah, ch
    mov [di + CON_COLS*3], ah
    mov ah, [bx+4]
    xor ah, ch
    mov [di + CON_COLS*4], ah
    mov ah, [bx+5]
    xor ah, ch
    mov [di + CON_COLS*5], ah
    mov ah, [bx+6]
    xor ah, ch
    mov [di + CON_COLS*6], ah
    mov ah, [bx+7]
    xor ah, ch
    mov [di + CON_COLS*7], ah
    inc si
    inc si
    inc di
    dec cl
    jnz .cell

    ; --- THE CURSOR IS COMPOSED IN, not painted (SPEC.md 70.8.2) -----------
    ; Two lit scanlines in the cell's bottom two band rows. It is not a second
    ; paint and it never flashes: the cell goes from its old pixels to its
    ; final pixels in the band, and the band reaches the glass once.
    cmp byte [con_cvis], 0
    je .out
    mov ax, [con_cy]
    cmp ax, [con_rr]
    jne .out
    mov ax, [con_cx]
    cmp ax, [con_vcols]
    jae .out                        ; the cursor is off the right of a narrow
    mov di, con_band + CON_COLS*6     ; window: there is no cell to underline
    add di, ax
    ; **IT IS THE CURSOR CELL'S OWN POLARITY AND NOT ALWAYS `or`.** On a 1bpp
    ; screen a cell the loop drew INVERSE has those two scanlines at 0xFF
    ; already, so an OR drew nothing at all - the cursor vanished inside a
    ; board's highlighted menu bar, which is exactly where a user looks for it.
    ; The mask is re-derived from THAT cell's attribute rather than taken from
    ; CH, which after the loop is the LAST column's and not the cursor's.
    mov bx, ax
    shl bx, 1
    add bx, [con_rowp]
    mov al, [bx+1]
    CON_INVMASK
    mov al, ch
    not al                          ; AL = FF on a normal cell, 00 on inverse
    or [di], al
    or [di + CON_COLS], al
    mov al, ch
    and [di], al                    ; ...and an inverse cell has those two rows
    and [di + CON_COLS], al          ; CLEARED instead: a dark underline on lit
                                    ; paper, the same two scanlines the other
                                    ; way up
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_emit - the composed band onto the glass. BX = the buffer row
; in:  con_band composed, the carrier's layout run, THE GFX LOCK HELD
;
; On a 1bpp adapter that is ONE blit for the whole row: the pen is not read
; there (SPEC.md 5.4.2.2) and the polarity is already in the band, so there
; are no attribute runs to walk at all. On a colour one it is one blit per
; maximal run of cells sharing an attribute byte, each with the pen set to
; that run's (ink, paper).
;
; **THE PEN DIES WITH THE LOCK** (SPEC.md 5.4.2.2): gfx_unlock puts
; CWHITE/CBLACK back, so it is set inside the caller's hold and never banked
; across one.
; -----------------------------------------------------------------------------
con_emit:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    push ds
    pop es                          ; ES:SI = OUR band: the blit takes the
                                    ; caller's own segment (SPEC.md 5.4.2)
    mov ax, bx
    sub ax, [con_vtop]
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, [con_oy]
    add ax, [con_topy]
    mov [con_ry], ax                 ; the band's y, out of the registers' way
    mov ax, CON_COLS * 2
    mul bx
    add ax, con_scr
    mov [con_rcp], ax                ; ...and where the row's cells are
    cmp byte [con_nob], 0
    je .live
    call con_rowfont                 ; **THE LATCH IS TESTED PER ROW AND NOT PER
    jmp short .out                  ; RUN**, which is the w2 review's MAJOR 1.
                                    ; It used to sit at the head of con_blitrun,
                                    ; where it returned BEFORE the fallback: the
                                    ; first refused run lettered its own row and
                                    ; every later call - the first run of every
                                    ; OTHER row included - returned having drawn
                                    ; nothing. One row of text and twenty-four
                                    ; blank ones, for the life of the instance
.live:
    cmp byte [con_mono], 0
    je .runs
    xor ax, ax                      ; ONE band, ONE blit, no runs (70.8.4)
    mov cx, [con_vcols]
    call con_blitrun
    jmp short .out
.runs:
    xor di, di                      ; DI = the run's first column
.run:
    cmp di, [con_vcols]
    jae .out
    mov si, [con_rcp]
    mov ax, di
    shl ax, 1
    add si, ax
    mov ah, [si+1]                  ; the run's attribute
    xor cx, cx
.grow:
    inc cx
    mov bx, di
    add bx, cx
    cmp bx, [con_vcols]
    jae .emit                       ; the row ends the run
    add si, 2
    cmp ah, [si+1]
    je .grow
.emit:
    push cx
    push di
    call con_pen                     ; AH = the attribute
    pop di
    pop cx
    mov ax, di
    call con_blitrun
    cmp byte [con_nob], 0
    jne .out                        ; **AND THIS ROW STOPS HERE.** con_blitrun
                                    ; latched and con_rowfont lettered the WHOLE
                                    ; row, so the runs after this one have
                                    ; nothing left to put down - and walking on
                                    ; would letter the same row once per
                                    ; remaining run. The latch IS the signal;
                                    ; con_emit tested it zero at the top
    add di, cx
    jmp short .run
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

; --- con_pen - AH = a cell attribute -> OSAPI_GFX_BLIT1_PEN ------------------
; Bit 7 is BLINK, which is ignored windowed - there is nothing here that
; blinks - unless [con_ice] says the board asked for bright backgrounds
; instead, when it is the background's fourth bit (SPEC.md 70.8.9).
con_pen:
    push ax
    push bx
    push cx
    mov bl, ah
    mov cl, 4
    shr bl, cl
    and bl, 0x07
    cmp byte [con_ice], 0
    je .ink
    test ah, 0x80
    jz .ink
    or bl, 0x08
.ink:
    mov al, ah
    and al, 0x0F                    ; AL = ink, AH = paper
    mov ah, bl
    call OSAPI_GFX_BLIT1_PEN
    pop cx
    pop bx
    pop ax
    ret

; --- con_blitrun - AX = the first column, CX = columns -----------------------
; ES = ours, [con_ry] the band's y. A REFUSAL is not a hypothetical: SPEC.md
; 5.4.2 says kern_small carries the slot and a stc/retf stub and nothing else,
; so the documented degrade - letter the row in the kernel's 8x8 face - is
; what happens, once for the whole row and not once per run.
con_blitrun:
    push ax
    push bx
    push cx
    push dx
    push si
    push bp
    mov si, con_band                 ; ...and no [con_nob] test here: con_emit
                                    ; answers for the whole row before it walks
                                    ; a single run (the w2 review's MAJOR 1)
    add si, ax
    mov bp, CON_COLS
    shl ax, 1
    shl ax, 1
    shl ax, 1
    add ax, [con_px]                 ; ...8-aligned (the carrier's layout), and a cell is
    mov bx, [con_ry]                 ; eight wide, so the run's x and width are
    shl cx, 1                       ; multiples of 8 by construction
    shl cx, 1
    shl cx, 1
    mov dx, 8
    call OSAPI_GFX_BLIT1
    jnc .out
    mov byte [con_nob], 1            ; ...and every later ROW takes the fallback
    call con_rowfont                 ; at the head of con_emit, without asking the
.out:                               ; kernel again
    pop bp
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- con_rowfont - the documented degrade: letter the row with font_run ------
; [con_rcp] is the row's cells and [con_ry] its y. The characters are copied out
; of the interleaved buffer into a NUL-terminated run, because font_run wants
; a string and a cell is two bytes; the ATTRIBUTES are lost, which is what a
; machine with no band blitter can offer.
con_rowfont:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov si, [con_rcp]
    mov di, con_run
    mov cx, [con_vcols]
.copy:
    mov al, [si]
    mov [di], al
    inc si
    inc si
    inc di
    loop .copy
    mov byte [di], 0
    mov cx, [con_px]
    mov dx, [con_ry]
    mov si, con_run
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- con_clear - blank the screen and home the cursor -------------------------
; A CELL IS A WORD now: AL = the space, AH = the current attribute, which is
; ANSI.SYS's convention rather than VT's and is what a board expects an erase
; to leave behind (SPEC.md 70.9.3).
con_clear:
    push ax
    push cx
    push di
    push es
    push ds
    pop es                          ; ...ES is the KERNEL's on a callback
    cld
    mov di, con_scr
    mov cx, CON_CELLS
    mov al, ' '
    mov ah, [con_attr]
    rep stosw
    pop es
    mov word [con_cx], 0
    mov word [con_cy], 0
    mov byte [con_pwrap], 0
    mov word [con_scrl], 0           ; ...and a cleared screen owes no blit
    call con_markall
    pop di
    pop cx
    pop ax
    ret

; =============================================================================
; con_font - the 256 CP437 glyphs, built once at launch (SPEC.md 70.8.6)
;
; OSAPI_FONT_GLYPHS answers the KERNEL's own face and kernel/font.inc keeps
; 32..126 of it - 95 glyphs. A terminal needs 0..255, and it needs them to be
; CP437 rather than the system face: a `make FONT=` kernel replaces the OS's
; letters, and a board's box-drawing character is not a design choice this
; package may inherit.
;
; THE SPLIT IS ON A FACT RATHER THAN CAUTION, and the fact is about the ROM and
; not about the code point. **AN EGA-OR-LATER BIOS's 8x8 set IS CP437, all 256
; of it, by the adapter's own definition** - so where there is one, all 256 come
; off the machine and the shipped table is overwritten entirely. That is
; deliberate and it is not the shipped table going to waste: it is the terminal
; drawing the letters the rest of the machine draws.
;
; A PRE-EGA ROM has 128 glyphs at F000:FA6E and no standard says what a clone
; put in the low 32 of them, so there only 32..127 - which is ASCII, and every
; ROM agrees about ASCII - is trusted, and 0..31 and 128..255 stay the shipped
; table's: tools/cp437font.py's clean-room 160.
;
;   an EGA/VGA BIOS   int 10h AX=1130h BH=3 answers all 256, and all 256 are
;                     taken
;   a CGA/Hercules    F000:FA6E is 0..127; 32..127 is taken and the shipped
;                     table keeps the other 160
;
; kernel/font.inc's font_init is the probe, verbatim in its shape and for its
; stated reason: ZERO ES:BP, call AX=1130h, and treat an unchanged 0:0 as "no
; EGA-or-later BIOS" - AH=11h is not implemented on a pre-EGA ROM and returns
; with the pair untouched.
; =============================================================================
con_font:
    push ax
    push bx
    push cx
    push dx                         ; **int 10h AX=1130h ANSWERS IN DX**: DL is
    push si                         ; the character rows and CX the bytes per
    push di                         ; character, so this proc came back with DX
    push es                         ; changed and said nothing (CLAUDE.md's
                                    ; register discipline)
    ; --- the shipped half first, so the ROM half can simply overwrite it ----
    mov si, con_cp437
    mov di, con_glyf
    mov cx, 32 * 8                  ; 0..31
    call .blk
    mov di, con_glyf + 128 * 8
    mov cx, 128 * 8                 ; ...and 128..255, SI walking straight on
    call .blk
    ; --- then the machine's, if it has one ---------------------------------
    push bp
    xor bp, bp
    mov es, bp
    mov ax, 0x1130
    mov bh, 3
    int 0x10                        ; out ES:BP = the 8x8 set
    mov ax, es
    mov bx, bp
    pop bp
    or ax, ax
    jnz .rom
    or bx, bx
    jnz .rom
    mov ax, 0xF000                  ; no EGA-or-later ROM: the CGA/MDA half
    mov bx, 0xFA6E + 32*8           ; table, which is 0..127 and no further
    mov es, ax
    mov si, bx
    mov di, con_glyf + 32 * 8
    mov cx, 96 * 8
    call .far
    jmp short .out
.rom:
    mov es, ax
    mov si, bx
    mov di, con_glyf
    mov cx, 256 * 8
    call .far
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
.blk:                               ; CX bytes DS:SI -> DS:DI
    mov al, [si]
    mov [di], al
    inc si
    inc di
    loop .blk
    ret
.far:                               ; CX bytes ES:SI -> DS:DI
    mov al, [es:si]
    mov [di], al
    inc si
    inc di
    loop .far
    ret

; --- con_celloff - AX = the cursor's byte offset within con_scr ----------------
con_celloff:
    push dx
    mov ax, CON_COLS * 2
    mul word [con_cy]                ; **MUL WRITES DX** (SPEC.md 1), and the
    add ax, [con_cx]                 ; product is under 4,000 either way
    add ax, [con_cx]
    pop dx
    ret

; --- con_putc - AL, a GLYPH, onto the screen at the cursor --------------------
; **IT IS ONLY A GLYPH NOW.** The controls and the escape sequences are the
; parser's (SPEC.md 70.9, teansi.inc), which is what replaced the "recognised
; and discarded" this proc carried; what is left here is con_putc's own half of
; the contract, ansisim's `_put` to the line:
;
;   * a cell is a character AND THE CURRENT ATTRIBUTE, which the parser derived
;     (SPEC.md 70.9.4) and this only reads;
;   * **a glyph written in column 79 STAYS VISIBLE and the cursor stays on it**
;     with [con_pwrap] set, so the next GLYPH wraps (SPEC.md 70.9.5). The naive
;     alternative loses a character on every board that fills the last column
;     and then sends CR LF;
;   * 0x00-0x1F and 0x7F reach here as ordinary glyphs, because on a board they
;     are CP437's faces, suits and arrows - and 0x80-0xFF are CP437 too and
;     never C1 controls.
con_putc:
    push ax
    push bx
    push cx
    push dx
    push di
    call con_markcur                 ; the row the cursor is LEAVING owes a
                                    ; redraw: the underline is in its band
    cmp byte [con_pwrap], 0
    je .noww
    mov byte [con_pwrap], 0          ; ...the wrap the LAST glyph promised
    mov word [con_cx], 0
    call con_nextrow
    call con_markcur
.noww:
    push ax
    call con_celloff
    mov di, ax
    pop ax
    mov [con_scr + di], al
    mov bl, [con_attr]
    mov [con_scr + di + 1], bl
    call con_markcur                 ; ...BEFORE the cursor moves: this row is
    mov ax, [con_cx]                 ; the one whose pixels changed
    inc ax
    cmp ax, CON_COLS
    jb .cxok
    mov byte [con_pwrap], 1          ; the glyph in the last column STAYS
    dec ax                          ; visible and the cursor stays on it
.cxok:
    mov [con_cx], ax
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- con_nextrow - the cursor down one, scrolling at the bottom ---------------
con_nextrow:
    push ax
    mov ax, [con_cy]
    inc ax
    cmp ax, CON_ROWS
    jb .set
    call con_scroll1
    mov ax, CON_ROWS - 1
.set:
    mov [con_cy], ax
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_scroll1 - the buffer up ONE row, which is what an LF at the bottom does
;
; **THE GENERAL CASE IS con_scrollup** (teansi.inc), because SPEC.md 70.9.3's
; `SU` scrolls by a parameter and nothing about the one-row case was special
; except that it was the only one before the parser. One `rep movsw`, one
; blanked row in the CURRENT attribute, every existing mark carried up with the
; buffer, and one row of scroll debt for the renderers to spend as a blit.
; -----------------------------------------------------------------------------
con_scroll1:
    push ax
    mov ax, 1
    call con_scrollup
    pop ax
    ret

; =============================================================================
; A CARRIER'S WORKER DRAWS UNDER THE LOCK, AND TESTS ITS OWN FENCES FIRST
;
; SPEC.md 20.6 rule 3 is take the lock, draw, release - and the rule a carrier
; keeps getting wrong is one level in from that: **every path to a drawing slot
; is gated on "is a foreign screen up" BEFORE the lock, not inside it**
; (SPEC.md 70.8.8). An fsx bracket holds the gfx lock for its whole life
; (SPEC.md 53.6) and gfx_lock is a yield-spin with no owner field, so a kept
; worker that takes the lock and THEN looks parks on a byte that cannot change
; until the bracket exits. In Telnet the first byte off the wire after entering
; full screen froze the session until ^].
; =============================================================================

; -----------------------------------------------------------------------------
; con_fillcells - AX = the first cell, CX = how many; SPACE + [con_attr]
; -----------------------------------------------------------------------------
con_fillcells:
    push ax
    push bx
    push cx
    push dx
    push di
    push es
    or cx, cx
    jz .out
    cmp ax, CON_CELLS
    jae .out
    mov bx, ax
    add bx, cx
    cmp bx, CON_CELLS
    jbe .have
    mov bx, CON_CELLS
    mov cx, bx
    sub cx, ax
.have:
    dec bx                          ; BX = the last cell touched
    push ax
    push cx
    call con_markcells               ; AX = first, BX = last
    pop cx
    pop ax
    push ds
    pop es
    cld
    mov di, ax
    shl di, 1
    add di, con_scr
    mov al, ' '
    mov ah, [con_attr]
    rep stosw
.out:
    pop es
    pop di
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- con_markcells - AX = the first cell, BX = the last: mark their rows -----
con_markcells:
    push ax
    push bx
    push cx
    push dx
    push bx
    xor dx, dx
    mov cx, CON_COLS
    div cx                          ; AX = the first row
    mov bx, ax
    pop ax
    xor dx, dx
    div cx                          ; AX = the last row
    mov cx, ax
.mk:
    call con_mark
    inc bx
    cmp bx, cx
    jbe .mk
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_cmove - CX cells within con_scr, from cell AX to cell DX
; in:  AX = source, DX = destination, CX = how many cells
;
; **ONE MOVER FOR ALL SIX EDITS**, and it picks its own direction. IL, SD and
; ICH open a gap and so copy BACKWARDS; DL, SU and DCH close one and copy
; forwards; a routine per direction is two chances to get an overlap wrong, and
; six copies of the address arithmetic is six chances to get the doubling
; wrong. DF is left CLEAR whichever way it went (SPEC.md 1).
; -----------------------------------------------------------------------------
con_cmove:
    push ax
    push cx
    push si
    push di
    push es
    jcxz .out
    push ds
    pop es
    mov si, ax
    shl si, 1
    add si, con_scr
    mov di, dx
    shl di, 1
    add di, con_scr
    cmp di, si
    jbe .fwd
    mov ax, cx                      ; the destination is ABOVE the source, so
    dec ax                          ; the last cell moves first
    shl ax, 1
    add si, ax
    add di, ax
    std
    rep movsw
    cld
    jmp short .out
.fwd:
    cld
    rep movsw
.out:
    pop es
    pop di
    pop si
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_scrollup - AX = rows, the whole screen up; the vacated rows blanked
;
; **ONLY THIS AND `LF` AT THE BOTTOM TAKE [con_scrl]** (SPEC.md 70.9.3), because
; only they move the screen as a whole in the direction the blit can follow.
; con_markup carries every existing mark up with the buffer, which is 70.8.1's
; own rule, and the debt is spent as ONE OSAPI_GFX_SCROLL windowed or ONE
; `rep movsw` in text mode.
; -----------------------------------------------------------------------------
; **THE BUFFER, THE MARKS AND THE DEBT ARE ONE TRANSACTION** (the w3 review's
; MAJOR 1). This runs on the WORKER and both renderers run on the UI task at the
; same time - that is what FSXF_KEEPWORKER means (SPEC.md 53.5.1) and why
; SPEC.md 70.8.8 made the debt a shared word at all. The three steps used to be
; visible separately: con_cmove moved 2,000 cells, con_markup moved the bitmap,
; con_fillcells marked the vacated rows, and only THEN did `add [con_scrl], ax`
; make the debt visible.
;
; A renderer that preempted between the move and the add drew a row from a mark
; set BEFORE the scroll, so it put post-scroll content at a post-scroll position
; - correct - and the next pass then spent the debt as one `rep movsw` and moved
; it a row too far. **Only the rows the scroll VACATED are marked**, so nothing
; repaired the rows above them and a board that scrolls and then sits at a menu
; left them wrong for the rest of the session. con_takescroll made the COUNTER
; atomic; this makes the SCROLL atomic, which is the same defect one step out.
;
; [con_scrbusy] is that transaction, and the renderers' two takers answer "there
; is nothing owed" while it is set: one skipped frame against a screen that
; cannot be repaired. It is one byte in the parser's own bss run, so te_reset
; covers it for free.
con_scrollup:
    push ax
    push bx
    push cx
    push dx
    or ax, ax
    jz .out
    mov byte [con_scrbusy], 1
    cmp ax, CON_ROWS
    jae .all
    push ax                         ; N, for the marks and the debt
    mov bx, CON_COLS
    mul bx                          ; AX = n*80 cells, DX = 0 (under 2,000)
    mov bx, ax                      ; BX = the cells it vacates
    mov cx, CON_CELLS
    sub cx, bx                      ; CX = the cells that survive
    xor dx, dx                      ; ...moved to cell 0 from cell n*80
    call con_cmove
    pop ax
    mov cx, ax
.up:
    call con_markup                  ; a mark names a row of the BUFFER, and the
    loop .up                        ; buffer just moved - so the marks move too,
                                    ; BEFORE the fill below adds its own
    push ax
    mov cx, bx
    mov ax, CON_CELLS
    sub ax, bx
    call con_fillcells               ; ...which marks the vacated rows, and only
    pop ax                          ; those: the SCROLL DEBT is what redraws the
    jmp short .debt                 ; rest, as one blit
.all:
    push ax
    xor ax, ax
    mov cx, CON_CELLS
    call con_fillcells               ; ...which marks every row it filled
    pop ax
.debt:
    pushf                           ; **THE ADD AND ITS SATURATION ARE ONE
    cli                             ; OPERATION** (the w3 review's MINOR 5): the
    add [con_scrl], ax               ; `cmp`/`mov` used to sit outside the atomic
    cmp word [con_scrl], CON_ROWS     ; add, so con_takescroll zeroing the counter
    jbe .sat                        ; between them wrote 25 back - a phantom
    mov word [con_scrl], CON_ROWS     ; full-screen scroll that never happened.
.sat:                               ; SATURATED, so a board that scrolls a
    popf                            ; thousand rows while the window is covered
                                    ; cannot wrap the word; both renderers read
                                    ; anything at or past CON_ROWS as "repaint
                                    ; the lot"
    mov byte [con_scrbusy], 0        ; ...and the transaction closes HERE, with
                                    ; the buffer, the bitmap and the debt all
                                    ; agreeing with each other again
.out:
    mov byte [con_scrbusy], 0
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; con_scrolldown - AX = rows, the whole screen down. NO SCROLL DEBT: [con_scrl]
; is "rows the buffer has moved UP", which is the one direction the windowed
; blit and the text-mode `rep movsw` are both written for, so this marks
; instead.
; -----------------------------------------------------------------------------
con_scrolldown:
    push ax
    push bx
    push cx
    push dx
    or ax, ax
    jz .out
    cmp ax, CON_ROWS
    jae .all
    mov bx, CON_COLS
    mul bx                          ; AX = n*80 cells
    mov bx, ax
    mov cx, CON_CELLS
    sub cx, bx                      ; CX = the cells that survive
    mov dx, bx                      ; ...from cell 0 down to cell n*80
    xor ax, ax
    call con_cmove
    xor ax, ax
    mov cx, bx
    call con_fillcells
    call con_markall
    jmp short .out
.all:
    xor ax, ax
    mov cx, CON_CELLS
    call con_fillcells
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

%ifdef CON_TTY
; =============================================================================
; THE TELETYPE HALF - `%define CON_TTY` (SPEC.md 96.33)
;
; con_putc takes a GLYPH and nothing else, because Telnet's controls are the
; ANSI parser's (SPEC.md 70.9) and a console with a parser over it wants no
; second opinion about what 0x0A means. A carrier with NO parser - the DOS box's
; command line, and the wave after it that captures a DOS program's output -
; wants exactly the ROM teletype's five: CR, LF, BS, TAB and BEL, with
; everything else a CP437 glyph.
;
; It is an opt-in for os88ui.inc's reason: Telnet must not carry forty bytes it
; cannot reach, and the fence between the two is one `%define` rather than a
; rule somebody has to remember.
;
; **LF SCROLLS AND CR DOES NOT MOVE THE ROW**, which is the ROM's behaviour and
; not ANSI's NEL. A program that ends its lines `13, 10` gets one new line from
; the pair; one that ends them `10` alone gets a staircase, and so it does under
; a real DOS on a real PC.
; =============================================================================

; --- con_write - AL = a byte, as the ROM teletype would take it ---------------
con_write:
    push ax
    cmp al, 13
    je .cr
    cmp al, 10
    je .lf
    cmp al, 8
    je .bs
    cmp al, 9
    je .tab
    cmp al, 7
    je .out                         ; BEL: a console is not a speaker, and a
                                    ; machine that beeps per byte of a DOS
                                    ; program's output is worse than one that
                                    ; does not
    call con_putc
.out:
    pop ax
    ret
.cr:
    mov word [con_cx], 0
    mov byte [con_pwrap], 0         ; ...and the wrap the last glyph promised is
    call con_markcur                ; OFF: `...79th char, CR, LF` must not eat
    jmp short .out                  ; the first character of the next line
.lf:
    call con_markcur                ; the row being LEFT owes its underline
    call con_nextrow
    call con_markcur
    mov byte [con_pwrap], 0
    jmp short .out
.bs:
    cmp word [con_cx], 0
    je .out                         ; column 0: DOS does not wrap back up, and
    call con_markcur                ; a console that did would scroll the other
    dec word [con_cx]               ; way on the first keystroke of a new line
    mov byte [con_pwrap], 0
    call con_markcur
    jmp short .out
.tab:
    push cx                         ; the next multiple of eight, and the stops
    mov cx, [con_cx]                ; are not settable (SPEC.md 70.8)
    and cx, 7
    neg cx
    add cx, 8                        ; CX = 1..8 spaces
.sp:
    mov al, ' '
    call con_putc
    dec cx
    jnz .sp
    pop cx
    jmp short .out

; --- con_say - SI = a NUL-terminated string, through con_write ----------------
con_say:
    push ax
    push si
.c:
    mov al, [si]
    or al, al
    jz .done
    call con_write
    inc si
    jmp short .c
.done:
    pop si
    pop ax
    ret

; --- con_open - the console a teletype carrier starts with -------------------
; A CARRIER MUST CALL THIS, once, before the first con_write: the loader zeroes
; bss (SPEC.md 21 step 5), and attribute 0 is black on black. Telnet does the
; same two stores in te_reset off its SGR state, which is why they are not in
; con_clear - an erase takes the CURRENT attribute and may not invent one
; (SPEC.md 70.9.3).
;
; **AND THE FACE, WHICH IS THE ONE THAT LOOKS LIKE NOTHING IS WRONG.** A zeroed
; [con_glyf] is 256 blank glyphs, so a console whose carrier forgot con_font
; holds all the right characters and draws a black rectangle - the buffer reads
; perfectly and the screen is empty, which is the worst shape a defect can
; have. Telnet calls it itself because it has a launch path of its own; a
; carrier that calls con_open gets it for free and cannot forget.
con_open:
    mov byte [con_attr], 0x07       ; light grey on black: DOS's own default,
    mov byte [con_cvis], 1          ; and what `PROMPT` draws against
    call con_font
    call con_clear
    ret
%endif

; --- the console's own bss (SPEC.md 21 step 5 zeroes it) --------------------
con_scr     equ CON_BSS_AT + 0          ; CON_SCRSZ: the cells, character then
                                        ; attribute - text VRAM's own layout
con_band    equ con_scr + CON_SCRSZ     ; CON_BAND: one composed screen row
con_glyf    equ con_band + CON_BAND     ; CON_GLYF: the 256 CP437 glyphs
con_run     equ con_glyf + CON_GLYF     ; CON_COLS+1: con_rowfont's NUL run.
                                        ; ITS OWN, where telnet lent it the
                                        ; status line's buffer on the argument
                                        ; that the two could not overlap in
                                        ; time - true there and not a promise
                                        ; a library may make about a carrier
con_px      equ con_run + CON_COLS + 1  ; --- the geometry the CARRIER sets ---
con_oy      equ con_px + 2              ; the text pen, 8-ALIGNED, and the
con_topy    equ con_oy + 2              ; content top it measures rows from
con_vcols   equ con_topy + 2            ; columns the LIVE box shows...
con_vrows   equ con_vcols + 2           ; ...rows it fits...
con_vtop    equ con_vrows + 2           ; ...and the first buffer row shown
con_mono    equ con_vtop + 2            ; byte: 1bpp, so the polarity goes in
                                        ; the band and not the pen (70.8.4)
con_ry      equ con_mono + 1            ; --- the renderer's own ---
con_rcp     equ con_ry + 2              ; word: ...and its first cell
con_rowp    equ con_rcp + 2             ; word: con_compose's row base
con_rr      equ con_rowp + 2            ; word: the row being composed
con_cx      equ con_rr + 2              ; word: the cursor column, 0..79
con_cy      equ con_cx + 2              ; word: ...and its row, 0..24
con_scrl    equ con_cy + 2              ; word: rows the BUFFER has scrolled
                                        ; since the screen last agreed with it
con_drb     equ con_scrl + 2            ; 4 bytes: the dirty ROW bitmap
con_attr    equ con_drb + 4             ; byte: the current attribute
con_pwrap   equ con_attr + 1            ; byte: a glyph landed in column 79
con_cvis    equ con_pwrap + 1           ; byte: the cursor is drawn
con_ice     equ con_cvis + 1            ; byte: bit 7 is a BRIGHT BACKGROUND
con_nob     equ con_ice + 1             ; byte: OSAPI_GFX_BLIT1 refused once
con_scrbusy equ con_nob + 1             ; byte: a scroll is half done
CON_BSS     equ con_scrbusy + 1 - CON_BSS_AT
