; =============================================================================
; os8088 - apps/tracker/trktxt.inc
;
; XT mode's fullscreen is an 80x25 TEXT screen (SPEC.md 45.13). Prefix ttx_;
; included by tracker.asm AFTER trkui.inc, so every tui_ helper it borrows -
; tui_scpy, tui_hexb, tui_dec3, tui_viewrow, tui_vu_step - is already defined.
;
; WHY THIS EXISTS, in one paragraph. The FT2 screen (SPEC.md 45.6) is drawn
; out of 8x8 glyph cells, and a glyph cell costs about a MILLISECOND on a
; 4.77 MHz 8088 with a Hercules card (PERFORMANCE.md Part 2). A Hercules
; pattern row is 44 of them, the grid is 29 rows, so a full tui_draw_pat is
; ~1.28 SECONDS and even SPEC.md 45.12's one-row scroll is ~174 ms against a
; row that arrives every 120 ms. That arithmetic is why SPEC.md 45.9.1 turned
; the grid off on a tier-0 machine and left one banded line moving in an empty
; field - the honest answer to a budget that had already been blown.
;
; In a text mode the card's own ROM font does everything font_char was doing.
; A character cell is ONE WORD STORE: no rasterization, no shift, no
; read-modify-write, no bank arithmetic. ~25 clocks for a rep movsw word on an
; 8088 (17 nominal + 4 + 4 for the 8-bit bus), call it ~38 with MDA wait
; states, against ~4,770 for a glyph cell. Two orders of magnitude, and it is
; the same two orders that the single-line view was buying by not drawing.
;
; So the whole 19-row grid comes back, scrolling per row, and the numbers are
; in SPEC.md 45.13.1. The short version: one row change is a 1,121-cell blit
; out of a prepared shadow (~8.9 ms) plus a 59-byte band relight, and rows
; arrive 8.3 times a second on a default-tempo module - about 4% of the
; machine, against the ~44% XT mode's mixer already spends.
;
; THE SHADOW is what makes the blit that cheap. A player never edits, so a
; pattern's 64 rows are constant text for as long as it is the current
; pattern: they are formatted ONCE into ttx_shadow as char/attribute WORDS
; (SPEC.md 45.13.2) - 256 mp_cell2txt calls, ~33 ms, once every eight seconds
; or so - and every row change after that is 19 rep movsw's out of it. The
; shadow carries TTX_HALF blank rows above row 0 and below row 63, so the
; window into it is `shadow + viewrow * TTX_RW * 2` with no clamp, no branch
; and no special case at the ends of a pattern.
;
; THE BAND IS AN ATTRIBUTE, not a redraw. The shadow holds every row in the
; normal attribute; the blit lands them all, and 59 attribute bytes turn the
; middle row inverse afterwards. Nothing has to remember which row USED to be
; the band, because the blit rewrote it on the way past.
;
; AND NOTHING HERE CAN FLASH. PERFORMANCE.md Part 1's double-draw defect is
; the erase-and-letter pair; a text cell goes from its old contents to its
; final contents in a single word write, so this file gets SPEC.md 6.1's
; one-store-per-cell property for free - which is also why every field is
; written space-padded to its full width rather than erased first.
;
; WHAT THIS MAY NOT DO. After the OSAPI_FSX_MODE call every kernel drawing
; slot is off-limits until the bracket returns (SPEC.md 53.1) - they render
; DESKTOP geometry into a framebuffer that is now a text page. [trk_tx] is
; the flag that says so, and tui_msg_draw is gated on it: a status message
; set from trk_play or trk_transport while the text screen is up lands in
; [tui_msgp] and is picked up by ttx_draw_dyn's own status line.
; =============================================================================

; --- the 80x25 page ------------------------------------------------------------
TTX_COLS   equ 80                   ; FSXM_TEXT80 is 80x25 on all three
TTX_ROWS   equ 25                   ; adapters (SPEC.md 53.4); only FSI_SEG
TTX_STRIDE equ TTX_COLS * 2         ; genuinely varies - B000 on Hercules and
                                    ; MDA, B800 on the CGA/VGA family - and
                                    ; that is read out of the block, never
                                    ; assumed

; --- one pattern row: 'RR |C-2 01 A0F|...|C-2 01 A0F| RR' ----------------------
TTX_RW     equ 59                   ; characters in a row
TTX_X0     equ (TTX_COLS - TTX_RW) / 2  ; ...centred: column 10
TTX_SEPX   equ 3                    ; the first vertical rule inside the row
TTX_CHD    equ 13                   ; per-channel pitch: rule, space, 10, space
TTX_CELLX  equ 5                    ; cell text = TTX_CELLX + TTX_CHD*channel
TTX_CELLW  equ 10                   ; mp_cell2txt's pinned 'C-2 01 A0F'

; --- the rows of the screen ----------------------------------------------------
TTX_NAMEY  equ 0                    ; nameplate: TRACKER, the module title
TTX_RDY    equ 1                    ; Pos/Ptn/Row/BPM/Spd
TTX_VUY    equ 2                    ; the four volume bars
TTX_STY    equ 3                    ; the status line (SPEC.md 45.9.2)
TTX_HDRY   equ 4                    ; Channel 1..4
TTX_RULEY  equ 5                    ; ...and the rule under them
TTX_PATY   equ 6                    ; first pattern row
TTX_VIS    equ TTX_ROWS - TTX_PATY  ; 19 rows visible
TTX_HALF   equ (TTX_VIS - 1) / 2    ; 9 above the band, 9 below
TTX_BANDY  equ TTX_PATY + TTX_HALF  ; screen row 15

; the shadow carries the blank rows the ends of a pattern show, so the window
; into it needs no clamp: screen row 0 of the area is always shadow row
; [view], because shadow row (r + TTX_HALF) is pattern row r
TTX_SHROWS equ 64 + 2 * TTX_HALF
TTX_SHBYTES equ TTX_SHROWS * TTX_RW * 2
TTX_SHCHUNK equ 4                   ; rows formatted per frame while a
                                    ; periodic rebuild runs: ~25 ms of the
                                    ; ~330 ms the whole pattern costs, and
                                    ; 4 rows a frame against a view that
                                    ; moves 7.14 rows a SECOND

; --- attributes. These three are the whole palette, and they are the three an
; --- MDA can actually render, so they mean the same thing on Hercules, CGA and
; --- VGA text alike - the SPEC.md 39.4 discipline in its text-mode clothes ------
TTX_A_NORM equ 0x07                 ; normal
TTX_A_HI   equ 0x0F                 ; bright: headings and live readouts
TTX_A_INV  equ 0x70                 ; reverse: the nameplate and the row band

; --- CP437, which is the ROM font on every adapter that can set this mode -----
TTX_VBAR   equ 0xB3                 ; the channel rules
TTX_HBAR   equ 0xC4                 ; the rule under the header...
TTX_TEE    equ 0xC2                 ; ...and where a channel rule meets it
TTX_BLOCK  equ 0xDB                 ; a volume bar's lit cell

; cell (row, col) -> byte offset in the page
%define TTXAT(r, c) ((r) * TTX_STRIDE + (c) * 2)

; =============================================================================
; Page primitives. Each assumes ES is already the text segment and CLD is set;
; the public drawers below establish both. DI advances past what was written,
; which is what lets a line be composed out of several calls.
; =============================================================================

; ttx_put - SI = NUL string, AH = attribute, ES:DI = the first cell
ttx_put:
    push ax
    push si
.l:
    mov al, [si]
    or al, al
    jz .d
    inc si
    stosw
    jmp .l
.d:
    pop si
    pop ax
    ret

; ttx_putn - the same, space-padded to CX cells. The pad is not an erase in
;            front of the text, it is the rest of the same single pass - so a
;            field that got shorter cannot be blank for a frame.
ttx_putn:
    push ax
    push cx
    push si
.l:
    or cx, cx
    jz .d
    mov al, [si]
    or al, al
    jz .pad
    inc si
    stosw
    dec cx
    jmp .l
.pad:
    mov al, ' '                     ; CX >= 1 here: the loop above tested it
.p:
    stosw
    loop .p
.d:
    pop si
    pop cx
    pop ax
    ret

; ttx_fill - CX cells of AX (AL = char, AH = attribute) at ES:DI
ttx_fill:
    push ax
    push cx
    rep stosw
    pop cx
    pop ax
    ret

; =============================================================================
; ttx_begin - take the screen (SPEC.md 53.4). Bracket context, exclusive task.
; out: CF=0 the text page is live and [ttx_seg] names it; CF=1 refused, and
;      the caller falls back to the graphics bracket having changed nothing.
; =============================================================================
ttx_begin:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es                          ; the FSI block is ours (the gfx_blit4
    mov di, ttx_fsi                 ; idiom: ES:DI is the caller's own)
    mov al, FSXM_TEXT80
    call OSAPI_FSX_MODE
    jc .out
    mov ax, [ttx_fsi + FSI_SEG]     ; the ONE thing that is not a constant
    mov [ttx_seg], ax
    mov ax, 0x0100                  ; park the CRTC cursor out of sight - it
    mov cx, 0x2000                  ; is ours now, and the mode set left it
    int 0x10                        ; blinking at 0,0 (SPEC.md 53.4)
    clc
.out:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; The shadow build, in three parts (SPEC.md 45.13.2). It used to be one
; routine that formatted all 64 rows in a single frame, and PERFORMANCE.md
; Part 9's field set says what that costs on the target: 256 mp_cell2txt
; calls plus 3,776 lodsb/stosw pairs plus a 9,676-byte blank at the measured
; 1.76 us/byte, which comes to 140-330 ms depending on how many cells carry
; notes. That is not a frame, it is a Part 1 VISIBLE REDRAW, it happened
; once per pattern - every ~9 s at 125 BPM speed 7 - and it is exactly what
; the field report describes: the screen stopping for about a third of a
; second and then jumping.
;
; So the periodic build is spread: ttx_shstart claims the pattern and arms a
; cursor, ttx_shstep formats TTX_SHCHUNK rows, and ttx_draw_dyn calls it once
; a frame until the cursor runs out. The worst frame goes from ~330 ms to
; ~25 ms and nothing else changes - the blit still comes out of a shadow, and
; a row is still formatted exactly once per pattern.
;
; Two things make that safe. The cursor starts at the row the VIEW needs
; (view - TTX_HALF, clamped) and WRAPS, so a Dxx break or a position jump
; that lands mid-pattern fills the visible window first rather than counting
; up to it; and the cursor advances at TTX_SHCHUNK rows per frame against a
; view that advances 7.14 rows a SECOND, so it can never be overtaken.
;
; ttx_shbuild is the synchronous whole thing, and the only caller is
; ttx_draw_all: the bracket has just set the video mode, there are no pixels
; on screen to stop updating, and paying it there is what lets the first
; frame after F be complete. It is also the only place that blanks - every
; later build rewrites all 64 content rows, and the TTX_HALF pad rows are
; never written at all.
; =============================================================================
ttx_shbuild:
    push ax
    push cx
    push di
    push es
    push ds
    pop es
    cld
    mov di, ttx_shadow
    mov cx, TTX_SHROWS * TTX_RW
    mov ax, (TTX_A_NORM << 8) | ' '
    rep stosw
    call ttx_shstart
.l:
    cmp byte [ttx_shbusy], 0
    je .done
    call ttx_shstep
    jmp short .l
.done:
    pop es
    pop di
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ttx_shstart - claim [mp_pattern] and arm the cursor. No formatting.
;
; The pattern is claimed at the START, not at the end: ttx_draw_dyn's change
; test would otherwise refire on every frame of the build. It also closes an
; old race - the worker can move [mp_pattern] mid-build, and recording it
; afterwards marked a mixed shadow as current. Recorded first, a mid-build
; move is caught by the same test on the next frame and simply restarts.
; -----------------------------------------------------------------------------
ttx_shstart:
    push ax
    mov al, [mp_pattern]
    mov [ttx_shpat], al
    mov byte [ttx_shok], 0
    mov byte [ttx_shbusy], 1
    mov byte [ttx_sleft], 64
    mov al, [tui_cvr]               ; the top of the visible window, so a
    sub al, TTX_HALF                ; jump into the middle of a pattern
    jnc .set                        ; fills what is on screen first
    xor al, al
.set:
    mov [ttx_srow], al
    cmp byte [mp_loaded], 0
    jne .out
    mov byte [ttx_shbusy], 0        ; no module: an empty grid IS the truth,
    mov byte [ttx_shok], 1          ; and the blank already wrote it
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; ttx_shstep - format up to TTX_SHCHUNK rows at the cursor; clears
;              [ttx_shbusy] and sets [ttx_shok] on the 64th
; -----------------------------------------------------------------------------
ttx_shstep:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    push ds
    pop es
    cld
    mov byte [ttx_sbudget], TTX_SHCHUNK
.r:
    cmp byte [ttx_shbusy], 0
    je .done
    mov bl, [ttx_srow]
    call ttx_rowtext                ; -> ttx_line, TTX_RW ascii
    mov al, [ttx_srow]
    xor ah, ah
    add ax, TTX_HALF
    mov dx, TTX_RW * 2
    mul dx                          ; (row + HALF) * rowbytes; 8,496 max, so
    add ax, ttx_shadow              ; DX is 0 and the product fits AX
    mov di, ax
    mov si, ttx_line
    mov cx, TTX_RW
    mov ah, TTX_A_NORM              ; lodsb leaves AH alone: one attribute
.w:                                 ; rides the whole row
    lodsb
    stosw
    loop .w
    mov al, [ttx_srow]
    inc al
    and al, 63                      ; the cursor wraps inside the pattern
    mov [ttx_srow], al
    dec byte [ttx_sleft]
    jnz .budget
    mov byte [ttx_shbusy], 0
    mov byte [ttx_shok], 1
    jmp short .done
.budget:
    dec byte [ttx_sbudget]
    jnz .r
.done:
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ttx_rowtext - pattern row BL (0..63) -> ttx_line as TTX_RW ascii characters.
; The row number is on both edges the FT2 way, and a cell the decoder refuses
; is left blank rather than guessed at.
;
; The row goes through a bss byte and not BL because mp_cell2txt spends every
; general register - it decodes through BX and CX and returns with ES = DS.
; -----------------------------------------------------------------------------
ttx_rowtext:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov [ttx_row], bl
    push ds
    pop es
    cld
    mov di, ttx_line
    mov cx, TTX_RW
    mov al, ' '
    rep stosb
    mov di, ttx_line + TTX_SEPX     ; five rules: four channel lefts and the
    mov cx, 5                       ; block's right edge, TTX_SEPX + 4*TTX_CHD
.sep:
    mov byte [di], TTX_VBAR
    add di, TTX_CHD
    loop .sep
    mov al, [ttx_row]
    mov di, ttx_line
    call tui_hexb                   ; the left row number...
    mov al, [ttx_row]
    mov di, ttx_line + TTX_RW - 2
    call tui_hexb                   ; ...and the right one
    mov byte [ttx_chn], 0
.cl:
    mov al, [mp_pattern]
    xor ah, ah
    mov di, ax
    mov al, [ttx_row]
    mov ah, [ttx_chn]
    call mp_cell2txt                ; -> mp_celltxt; clobbers everything
    jc .nx
    mov al, [ttx_chn]
    mov ah, TTX_CHD
    mul ah                          ; AX = channel * pitch
    add ax, ttx_line + TTX_CELLX
    mov di, ax
    mov si, mp_celltxt
    push ds
    pop es
    mov cx, TTX_CELLW
    cld
    rep movsb
.nx:
    inc byte [ttx_chn]
    cmp byte [ttx_chn], 4
    jb .cl
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; ttx_blit - the whole 19-row window, out of the shadow, in 19 rep movsw's.
; This is the frame's entire pattern cost: 1,121 word stores, ~8.9 ms.
; ttx_band then turns the middle row inverse - 59 attribute bytes, and no
; bookkeeping about which row used to be the band, because the blit rewrote
; it on the way past.
; =============================================================================
ttx_blit:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov al, [tui_cvr]               ; shadow row [view] IS screen row 0 of the
    xor ah, ah                      ; area: pattern row r lives at r + HALF and
    mov dx, TTX_RW * 2              ; the area starts at view - HALF
    mul dx
    add ax, ttx_shadow
    mov si, ax
    mov ax, [ttx_seg]
    mov es, ax
    mov di, TTXAT(TTX_PATY, TTX_X0)
    mov bx, TTX_VIS
    cld
.r:
    push si
    push di
    mov cx, TTX_RW
    rep movsw
    pop di
    pop si
    add si, TTX_RW * 2
    add di, TTX_STRIDE
    dec bx
    jnz .r
    mov di, TTXAT(TTX_BANDY, TTX_X0) + 1
    mov cx, TTX_RW
    mov al, TTX_A_INV
.b:
    mov [es:di], al
    add di, 2
    loop .b
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; The lines above the grid. Each is one padded pass over its own field, so
; none of them can be caught half-written (PERFORMANCE.md Part 1).
; =============================================================================

; --- row 0: TRACKER, the module title, and what the audio is doing -------------
ttx_name:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [ttx_seg]
    mov es, ax
    cld
    mov di, TTXAT(TTX_NAMEY, 0)
    mov cx, TTX_COLS
    mov ax, (TTX_A_INV << 8) | ' '
    call ttx_fill
    mov ah, TTX_A_INV
    mov di, TTXAT(TTX_NAMEY, 2)
    mov si, ttx_s_name
    call ttx_put
    mov si, mp_title                ; the title is hostile blob bytes, but
    cmp byte [mp_loaded], 0         ; mp_load already NUL-terminated it inside
    jne .title                      ; its own 21-byte buffer
    mov si, ttx_s_nomod
.title:
    mov di, TTXAT(TTX_NAMEY, 12)
    mov cx, 21
    mov ah, TTX_A_INV
    call ttx_putn
    mov di, TTXAT(TTX_NAMEY, TTX_COLS - 12)
    mov si, ttx_s_xtrate            ; XT mode IS 5,500 Hz for as long as it is
    mov ah, TTX_A_INV               ; on (SPEC.md 45.9), and this screen only
    call ttx_put                    ; exists while it is - so it is a fact
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- row 1: Pos / Ptn / Row / BPM / Spd ----------------------------------------
ttx_readout:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov di, ttx_line
    mov si, ttx_s_pos
    call tui_scpy
    mov al, [mp_songpos]
    call tui_hexb
    mov si, ttx_s_slash
    call tui_scpy
    mov al, [mp_songlen]            ; the LAST order, FT2's own reading - and
    or al, al                       ; 0 with no module loaded, where a bare
    jz .len                         ; dec would read '/FF'
    dec al
.len:
    call tui_hexb
    mov si, ttx_s_ptn
    call tui_scpy
    mov al, [mp_pattern]
    call tui_hexb
    mov si, ttx_s_rowl
    call tui_scpy
    mov al, [mp_row]
    call tui_hexb
    mov si, ttx_s_bpm
    call tui_scpy
    mov al, [mp_bpm]
    call tui_dec3
    mov si, tui_nbuf
    call tui_scpy
    mov si, ttx_s_spd
    call tui_scpy
    mov al, [mp_speed]
    call tui_hexb
    mov byte [di], 0
    mov ax, [ttx_seg]
    mov es, ax
    cld
    mov di, TTXAT(TTX_RDY, TTX_X0)
    mov si, ttx_line
    mov cx, TTX_RW
    mov ah, TTX_A_HI
    call ttx_putn
    mov al, [mp_songpos]            ; bank what this frame drew
    mov [tui_lpos], al
    mov al, [mp_pattern]
    mov [tui_lpat], al
    mov al, [mp_row]
    mov [tui_lrow], al
    mov al, [mp_bpm]
    mov [tui_lbpm], al
    mov al, [mp_speed]
    mov [tui_lspd], al
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- row 3: the status line. Same string [tui_msgp] carries everywhere else,
; --- so SPEC.md 45.9.2's transport legend follows the music here too ----------
ttx_status:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov si, [tui_msgp]
    or si, si
    jnz .have
    mov si, tui_s_hint
.have:
    mov ax, [ttx_seg]
    mov es, ax
    cld
    mov di, TTXAT(TTX_STY, TTX_X0)
    mov cx, TTX_RW
    mov ah, TTX_A_NORM
    call ttx_putn
    mov ax, [tui_msgp]
    mov [ttx_lmsg], ax
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; --- rows 4 and 5: the channel header and its rule. Drawn once per bracket -----
ttx_header:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [ttx_seg]
    mov es, ax
    cld
    mov di, TTXAT(TTX_HDRY, TTX_X0)
    mov si, ttx_s_rw
    mov ah, TTX_A_HI
    call ttx_put
    mov byte [ttx_chn], 0
.c:
    mov al, [ttx_chn]
    mov ah, TTX_CHD
    mul ah
    add ax, TTX_X0 + TTX_CELLX
    shl ax, 1                       ; a cell is a word (8086: shift by 1 only)
    add ax, TTXAT(TTX_HDRY, 0)
    mov di, ax
    mov si, ttx_s_chan
    mov ah, TTX_A_HI
    call ttx_put
    mov al, [ttx_chn]
    add al, '1'
    mov ah, TTX_A_HI
    stosw
    inc byte [ttx_chn]
    cmp byte [ttx_chn], 4
    jb .c
    mov di, TTXAT(TTX_HDRY, TTX_X0 + TTX_RW - 2)
    mov si, ttx_s_rw
    mov ah, TTX_A_HI
    call ttx_put
    mov di, TTXAT(TTX_RULEY, TTX_X0)
    mov cx, TTX_RW
    mov ax, (TTX_A_NORM << 8) | TTX_HBAR
    call ttx_fill
    mov di, TTXAT(TTX_RULEY, TTX_X0 + TTX_SEPX)
    mov cx, 5
    mov al, TTX_TEE
.t:
    mov [es:di], al                 ; where a channel rule meets the rule
    add di, TTX_CHD * 2
    loop .t
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; Row 2: the four volume bars, aligned with the four pattern columns.
;
; ttx_vuframe draws the brackets and the MUTE flags - a mute is a change of
; state, not of level, so it belongs here and not in the per-frame path - and
; zeroes the delta baseline, exactly as tui_el_scopes does for the graphics
; bars (SPEC.md 45.12).
; =============================================================================
ttx_vuframe:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [ttx_seg]
    mov es, ax
    cld
    mov byte [ttx_chn], 0
.c:
    mov al, [ttx_chn]
    mov ah, TTX_CHD
    mul ah
    add ax, TTX_X0 + TTX_CELLX - 1
    shl ax, 1
    add ax, TTXAT(TTX_VUY, 0)
    mov di, ax
    mov ax, (TTX_A_NORM << 8) | '['
    stosw
    mov bl, [ttx_chn]
    xor bh, bh
    mov byte [ttx_vuc + bx], 0      ; the delta baseline, dropped with the
    cmp byte [mp_mute + bx], 0      ; pixels it described
    je .live
    mov si, ttx_s_mute
    mov cx, TTX_CELLW
    mov ah, TTX_A_NORM
    call ttx_putn
    jmp short .close
.live:
    mov cx, TTX_CELLW
    mov ax, (TTX_A_NORM << 8) | ' '
    call ttx_fill
.close:
    mov ax, (TTX_A_NORM << 8) | ']'
    stosw
    inc byte [ttx_chn]
    cmp byte [ttx_chn], 4
    jb .c
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; ttx_vu - the levels, delta-drawn: a rising bar writes its growth, a falling
;          one erases its shrinkage, a steady one costs nothing. A muted
;          channel is skipped whole - its cells say MUTE and mp_chvol is 0
;          there anyway, so there is nothing for the needle to say.
ttx_vu:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [ttx_seg]
    mov es, ax
    cld
    mov byte [ttx_chn], 0
.c:
    mov bl, [ttx_chn]
    xor bh, bh
    cmp byte [mp_mute + bx], 0
    jne .next
    call tui_vu_step                ; AL = the decayed level 0..64; the needle
    xor ah, ah                      ; rule has one home (SPEC.md 45.12)
    mov cx, TTX_CELLW
    mul cx
    mov cl, 6
    shr ax, cl                      ; level * 10 / 64 -> 0..10 cells
    mov dl, al
    mov bl, [ttx_chn]
    xor bh, bh
    mov dh, [ttx_vuc + bx]
    cmp dl, dh
    je .next
    mov [ttx_vuc + bx], dl
    mov al, [ttx_chn]
    mov ah, TTX_CHD
    mul ah
    add ax, TTX_X0 + TTX_CELLX
    shl ax, 1
    add ax, TTXAT(TTX_VUY, 0)
    mov di, ax
    mov al, dl
    mov ah, dh
    cmp al, ah
    jb .fall
    sub al, ah                      ; rising: light [old .. new-1]
    mov cl, al
    xor ch, ch
    mov al, ah
    xor ah, ah
    shl ax, 1
    add di, ax
    mov ax, (TTX_A_NORM << 8) | TTX_BLOCK
    call ttx_fill
    jmp short .next
.fall:
    mov cl, ah                      ; falling: blank [new .. old-1]
    sub cl, al
    xor ch, ch
    xor ah, ah
    shl ax, 1
    add di, ax
    mov ax, (TTX_A_NORM << 8) | ' '
    call ttx_fill
.next:
    inc byte [ttx_chn]
    cmp byte [ttx_chn], 4
    jb .c
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; ttx_draw_all - the whole screen. Bracket entry, and nothing else calls it.
; The shadow is invalidated rather than trusted: a load can have happened
; between two brackets (Open is windowed, SPEC.md 53.7) and the shadow has no
; way to have heard about it.
; =============================================================================
ttx_draw_all:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push es
    mov ax, [ttx_seg]
    mov es, ax
    cld
    xor di, di
    mov cx, TTX_COLS * TTX_ROWS
    mov ax, (TTX_A_NORM << 8) | ' '
    call ttx_fill
    mov byte [ttx_shok], 0
    mov byte [ttx_shbusy], 0
    call ttx_name
    call ttx_header
    call ttx_vuframe
    call ttx_readout
    call ttx_status
    call tui_viewrow                ; before the build: ttx_shstart's cursor
    call ttx_shbuild                ; starts at the visible window
    call ttx_blit
    mov al, [tui_cvr]
    mov [tui_lcvr], al
    mov al, [mp_playing]
    mov [tui_lplay], al
    mov ax, [mp_mute]
    mov [tui_lmute], ax
    mov ax, [mp_mute + 2]
    mov [tui_lmute + 2], ax
    pop es
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; ttx_draw_dyn - one frame, change-driven, called once per OSAPI_FSX_WAIT.
; Nothing here redraws what did not move (PERFORMANCE.md Part 5 rule 1); the
; steady-state cost of a playing frame is four comparisons and the bars.
; =============================================================================
ttx_draw_dyn:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    mov al, [mp_playing]            ; the transport, from wherever it changed -
    cmp al, [tui_lplay]             ; a key, a song end, an F00, the SPEC.md
    je .noxn                        ; 45.2 watchdog. trk_transport writes the
    mov [tui_lplay], al             ; legend into [tui_msgp] and parks the view
    call trk_transport              ; row; the status line below spends it
.noxn:
    cmp byte [ttx_shbusy], 0        ; a spread rebuild continues before
    jne .step                       ; anything looks at the pattern again
    cmp byte [ttx_shok], 0          ; a position move can change the pattern,
    je .rebuild                     ; and a pattern is a whole new shadow
    mov al, [mp_pattern]
    cmp al, [ttx_shpat]
    je .nosh
.rebuild:
    call ttx_shstart                ; TTX_SHCHUNK rows a frame from here on,
    cmp byte [ttx_shbusy], 0        ; never all 64 in one (PERFORMANCE.md
    je .nosh                        ; Part 1: this was a visible redraw)
.step:
    call ttx_shstep
    mov byte [ttx_vdirty], 1
.nosh:
    call tui_viewrow                ; [tui_cvr]: the playing row, or the
    cmp byte [ttx_vdirty], 0        ; Up/Down scroll row while stopped
    jne .rows
    mov al, [tui_cvr]
    cmp al, [tui_lcvr]
    je .norows
.rows:
    mov byte [ttx_vdirty], 0
    call ttx_blit
    mov al, [tui_cvr]
    mov [tui_lcvr], al
.norows:
    mov al, [mp_songpos]
    cmp al, [tui_lpos]
    jne .ro
    mov al, [mp_pattern]
    cmp al, [tui_lpat]
    jne .ro
    mov al, [mp_row]
    cmp al, [tui_lrow]
    jne .ro
    mov al, [mp_bpm]
    cmp al, [tui_lbpm]
    jne .ro
    mov al, [mp_speed]
    cmp al, [tui_lspd]
    je .noro
.ro:
    call ttx_readout
.noro:
    mov ax, [mp_mute]
    cmp ax, [tui_lmute]
    jne .mu
    mov ax, [mp_mute + 2]
    cmp ax, [tui_lmute + 2]
    je .nomu
.mu:
    mov ax, [mp_mute]
    mov [tui_lmute], ax
    mov ax, [mp_mute + 2]
    mov [tui_lmute + 2], ax
    call ttx_vuframe
.nomu:
    call ttx_vu
    cmp byte [trk_diag], 0          ; the meter's SHB is live (SPEC.md 45.14),
    je .msg                         ; so it is re-rendered and re-drawn every
    call trk_diag_msg               ; frame - the [ttx_lmsg] pointer compare
    call ttx_status                 ; cannot see digits change inside one
    jmp short .out                  ; buffer
.msg:
    mov ax, [tui_msgp]
    cmp ax, [ttx_lmsg]
    je .out
    call ttx_status
.out:
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; Strings
; =============================================================================
ttx_s_name:   db 'TRACKER', 0
ttx_s_nomod:  db 'no module loaded', 0
ttx_s_xtrate: db 'XT 5500 Hz', 0
ttx_s_pos:    db 'Pos ', 0
ttx_s_slash:  db '/', 0
ttx_s_ptn:    db '  Ptn ', 0
ttx_s_rowl:   db '  Row ', 0
ttx_s_bpm:    db '  BPM ', 0
ttx_s_spd:    db '  Spd ', 0
ttx_s_rw:     db 'Rw', 0
ttx_s_chan:   db 'Channel ', 0
ttx_s_mute:   db '   MUTE', 0

; =============================================================================
; .bss (the TRKB/TRKW/TRKBUF accumulator tracker.asm defines; every name is an
; equ offset from os88_image_end)
; =============================================================================
    TRKW ttx_seg                    ; the text page's segment, out of FSI_SEG
                                    ; - B000 on Hercules and MDA, B800 on the
                                    ; CGA/VGA family. Read, never assumed
    TRKBUF ttx_fsi, FSI_SIZE        ; OSAPI_FSX_MODE's info block
    TRKBUF ttx_shadow, TTX_SHBYTES  ; the current pattern as char/attr words,
                                    ; TTX_HALF blank rows at each end so the
                                    ; window into it needs no clamp
    TRKB ttx_shpat                  ; ...the pattern it holds
    TRKB ttx_shok                   ; ...and whether it holds anything
    TRKB ttx_vdirty                 ; force the next blit (a fresh shadow)
    TRKBUF ttx_line, TTX_RW + 8     ; one composed line, ascii
    TRKB ttx_row                    ; ttx_rowtext's row (mp_cell2txt spends
                                    ; every general register, so it cannot
                                    ; live in one)
    TRKB ttx_srow                   ; the build cursor: the next row to
                                    ; format, wrapping inside the pattern
    TRKB ttx_sleft                  ; ...rows still owed, 64 down to 0
    TRKB ttx_sbudget                ; ...and this frame's share of them
    TRKB ttx_shbusy                 ; a spread rebuild is in progress
    TRKB ttx_chn                    ; shared small loop counter
    TRKW ttx_lmsg                   ; the status string last drawn
    TRKBUF ttx_vuc, 4               ; last-drawn bar widths, CELLS (SPEC.md
                                    ; 45.12's delta baseline, in this mode's
                                    ; own units - never tui_vupx, which is px)
