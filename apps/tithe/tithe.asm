; =============================================================================
; os8088 - apps/tithe/tithe.asm
;
; TITHE (SPEC.md 97) - a two-player turn-based card duel.
; docs/plans/TITHE-PLAN.md is the design record; SPEC.md 97 is the contract.
;
; **THIS IS WAVE 1a: THE RENDERER WITH NO GAME BEHIND IT.** The layout table,
; the board, the band composer and the pacing wheel, driven by a fixed board
; and a few keys. There are no rules, no cards, no AI and no network, and
; SPEC.md 97.9 lists what each later wave adds so a reader can tell a gap from
; a defect. It is on tests/unit/t_livefull.py's exemption list until wave 6,
; because a package that cannot be launched from a menu is not something to
; put on the live media.
;
; WHAT WAVE 1a IS FOR is the LAYOUT and the RATE - whether twenty figures at
; this size on this grid read as a crowd, and whether the wheel holds its rate
; while they do. Both are questions only eyes can answer, which is why the art
; here is procedural and the concept art is the owner's (TITHE-PLAN 16.1).
;
; --- THE THREE THINGS THAT DECIDE THE REST -----------------------------------
;
;  1. **ONE OPAQUE BLIT A FEATURE, GROUND BAKED IN** (SPEC.md 97.4). Drawing a
;     sprite where it was IS the erase; there is no erase pass and no instant
;     at which it is off the glass. SPEC.md 79.5.1 and 93.5.1 both paid for
;     that lesson and this package does not get to relearn it.
;
;  2. **ISOMETRIC IS A SHEAR** (SPEC.md 97.3). The cell grid is sheared rather
;     than projected, so the rectangles tile exactly: non-overlap is a
;     property of the layout, not a promise the art has to keep, and no
;     painter's order exists. CW is a multiple of 8, so every cell's x
;     satisfies gfx_blit1's one alignment rule for free.
;
;  3. **THE WHEEL'S CREDIT IS TIME AND IT IS CALIBRATED** (SPEC.md 97.5). A
;     band costs `arrival + rows x R + bytes x B`, so a byte credit
;     over-spends on tall bands; and the constants belong to THIS machine, so
;     they are measured at load off the PIT rather than read out of a table.
;
; Keys: F fullscreen, D detail, S sprite size, R recalibrate, P pause,
;       +/- the animation share, Esc leaves fullscreen or closes.
; =============================================================================

%include "os88api.inc"

    OS88_HEADER 'TITHE', ti_entry, 1, OS88_STACK_256
                                ; the worker's stack class (SPEC.md 8.7):
                                ; ti_worker's chain is 4 deep and its deepest
                                ; leaf is the band blit, which pushes eight
                                ; registers in front of a far call. Measured
                                ; static 88 over the 64-byte interrupt floor
                                ; is 152; 256 gives 1.7x

    OS88_ICON16
    dw 0x0000                   ; a shield over a coin: the tithe
    dw 0x0FF0
    dw 0x1FF8
    dw 0x3FFC
    dw 0x3FFC
    dw 0x3FFC
    dw 0x3FFC
    dw 0x1FF8
    dw 0x1FF8
    dw 0x0FF0
    dw 0x07E0
    dw 0x03C0
    dw 0x0180
    dw 0x0000
    dw 0x0000
    dw 0x0000
    dw 0x0000                   ; 16 data rows
    dw 0x0FF0
    dw 0x1008
    dw 0x2004
    dw 0x2664
    dw 0x2994
    dw 0x2994
    dw 0x2664
    dw 0x1008
    dw 0x1008
    dw 0x0810
    dw 0x0420
    dw 0x0240
    dw 0x0180
    dw 0x0000
    dw 0x0000
    OS88_ICON16_END

TI_HUDMAX   equ 92                ; the widest HUD row any surface asks for -
                                  ; a Hercules' 720 columns is 90 cells - plus
                                  ; the NUL and one to spare
TI_HUDRIGHT equ 18                ; cells the right-hand field occupies
TI_HUDMID   equ 8                 ; ...and half the middle one's
TI_FEATURES equ 23                ; the brief's own number: 20 characters, 2
                                  ; player bases, 1 moused-over card
TI_SHARE    equ 40                ; per cent of a frame the idle may take
TI_FRAMEUS  equ 54925             ; one system tick, in microseconds
TI_CALN     equ 16                ; blits the calibration times (SPEC.md 97.5)

; =============================================================================
; ti_entry - package entry (SPEC.md 20.2)
; in:  DS=ES=KERNEL_SEG, IF=1, gfx lock NOT held
; out: BX = window ptr, CF set = refused
;
; NOTHING IS LAID OUT OR SPAWNED HERE, and it cost a session to learn why the
; obvious spelling does not work. The window exists the instant wm_create
; returns and is not VISIBLE until the LOADER shows it, which is after this
; proc has returned - so OSAPI_WM_GEOM answers CF=1 here, and OSAPI_TASK_SPAWN
; refuses outright because the loader has not published this instance yet.
; Both wait for the first paint, which is where ti_relayout_ck and ti_spawn_ck
; are. `apps/dotdel/dotdel.asm`'s entry proc is the same three sentences one
; game along, and the symptom of ignoring them is a window that opens as a
; sliver saying it is too small for a board.
; =============================================================================
ti_entry:
    push si
    mov si, ti_tpl
    call OSAPI_WM_CREATE
    jc .out
    mov [ti_win], bx
    OS88_REGION_MOVABLE             ; SPEC.md 66.6.1, here where the window
                                    ; exists: a package with no worker is the
                                    ; case that moves most easily, and putting
                                    ; this at the spawn leaves exactly those
                                    ; runs declaring nothing
    mov bx, [ti_win]
    mov al, 1
    call OSAPI_WM_SNAP              ; the content origin onto a multiple of 8
                                    ; (SPEC.md 11.94), which is what lets every
                                    ; cell's x be aligned without rounding
    mov si, ti_pref
    call OSAPI_WM_PREFER            ; preserves the flags, so the CF we owe the
                                    ; loader is still wm_create's
    mov bx, [ti_win]
    mov al, 1
    call OSAPI_WM_OWNBG             ; every pixel of the content is ours: the
                                    ; kernel's white fill would be one whole
                                    ; board of flash before the first frame
    mov bx, [ti_win]
    mov al, 1
    call OSAPI_WM_NOANIM            ; a zoom-open on a 450-pixel window is a
                                    ; second of nothing
    mov bx, [ti_win]
    mov ax, ti_onresize
    call OSAPI_WM_ONRESIZE          ; the box moved under us - a drag across a
                                    ; display seam is the case that matters
    mov si, ti_about
    call OSAPI_ABOUT_SET            ; SPEC.md 12.2, which SHEET and CHART both
                                    ; shipped without
    mov bx, [ti_win]
    clc
.out:
    pop si
    ret

; -----------------------------------------------------------------------------
; ti_relayout - the layout and the art, together, because one decides the other
; Preserves every register. [ti_ok] says whether the box could hold a board.
; -----------------------------------------------------------------------------
ti_relayout:
    push ax
    call ti_layout
    jc .no
    call ti_art_build
    mov byte [ti_ok], 1
    jmp short .out
.no:
    mov byte [ti_ok], 0             ; a refusal is a normal path
                                    ; (PERFORMANCE.md rule 6): the window says
                                    ; so in words rather than drawing nothing
.out:
    mov byte [ti_dirty], 1
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_relayout_ck - cut the layout IF anything it depends on has moved
; in:  [ti_win]; called from W_PAINT with the lock held
; out: nothing; preserves every register
;
; THE GEOMETRY READ IS THE GATE, not a flag we set ourselves: a window that is
; not visible answers CF=1 and there is nothing to lay out against, which is
; exactly the state the entry proc is in. Two things move the answer and the
; box is only one of them - an adapter change re-rows the table without moving
; the content box at all - so both are compared.
; -----------------------------------------------------------------------------
ti_relayout_ck:
    push ax
    push bx
    push cx
    push dx
    push si
    call ti_georow                  ; SI = the row this machine wants; asked
                                    ; FIRST because it eats CX and DX
    mov bx, [ti_win]
    call OSAPI_WM_GEOM              ; CX = content w, DX = content h
    jc .out                         ; not visible: nothing to size against
    cmp byte [ti_laid], 0
    je .cut
    cmp si, [ti_geo]
    jne .cut
    cmp cx, [ti_cw_box]
    jne .cut
    cmp dx, [ti_ch_box]
    je .out
.cut:
    call ti_relayout                ; ti_layout banks the box it read, so a
    mov byte [ti_laid], 1           ; REFUSAL caches too - a box too small for
                                    ; a board is re-tested when it changes and
                                    ; not once a frame
.out:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; =============================================================================
; the window callbacks
; =============================================================================

; ti_paint - W_PAINT: the board, then every feature at its current pose
ti_paint:
    push ax
    push bx
    push si
    mov [ti_win], si
    call ti_relayout_ck             ; the box may have moved, or the adapter
    call ti_spawn_ck                ; changed under us - and on the FIRST paint
                                    ; this is where the layout happens at all
    cmp byte [ti_ok], 0
    je .refuse
    call ti_ground                  ; WF_OWNBG's other half, and only on a
                                    ; W_PAINT: the worker's frames touch the
                                    ; features and nothing around them
    call ti_board
    call ti_all
    jmp short .out
.refuse:
    mov si, ti_s_small
    call ti_say
.out:
    pop si
    pop bx
    pop ax
    ret

; ti_onresize - the box changed and we did not ask
ti_onresize:
    push si
    mov [ti_win], si
    mov byte [ti_laid], 0           ; MUST NOT DRAW here, and a full repaint
    pop si                          ; follows immediately - so the cheapest
    ret                             ; correct thing is to drop the cache and
                                    ; let ti_relayout_ck cut against the box
                                    ; the kernel has finished settling

; ti_onclick - a click runs one wheel pass, so the prototype can be stepped
ti_onclick:
    push si
    mov [ti_win], si
    call ti_spawn_ck
    pop si
    ret

; -----------------------------------------------------------------------------
; ti_onkey - W_ONKEY. SPEC.md 97.7 is the table.
; -----------------------------------------------------------------------------
ti_onkey:
    push ax
    push bx
    push si
    mov [ti_win], si
    mov bl, al
    or bl, 0x20
    cmp bl, 'p'
    je .pause
    cmp bl, 'r'
    je .recal
    cmp bl, 's'
    je .size
    cmp al, '+'
    je .up
    cmp al, '-'
    je .down
    jmp short .out
.pause:
    xor byte [ti_paused], 1
    jmp short .out
.recal:
    call ti_calibrate
    jmp short .out
.size:
    xor byte [ti_full], 1           ; wave 1a's cheapest "three sizes side by
    mov byte [ti_laid], 0           ; side" is to step the surface's own band
    call ti_relayout_ck             ; and look at each in turn
    call ti_paint_now
    jmp short .out
.up:
    add word [ti_share], 10
    cmp word [ti_share], 90
    jbe .credit
    mov word [ti_share], 90
    jmp short .credit
.down:
    cmp word [ti_share], 20
    jbe .credit
    sub word [ti_share], 10
.credit:
    call ti_credit
.out:
    pop si
    pop bx
    pop ax
    ret

; ti_paint_now - repaint from a key handler, which already holds the lock
ti_paint_now:
    push si
    cmp byte [ti_ok], 0
    je .out
    call ti_board
    call ti_all
.out:
    pop si
    ret

; ti_say - SI = a NUL string, drawn where a refusal can be read
ti_say:
    push ax
    push bx
    push cx
    push dx
    mov bx, [ti_win]
    call OSAPI_WM_CONTENT
    mov cx, ax
    mov dx, dx
    add cx, 8
    add dx, 8
    mov al, CBLACK
    mov ah, CWHITE
    call OSAPI_FONT_RUN
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_spawn_ck - start the worker, once, from a window callback with the lock
;               held - which is what OSAPI_TASK_SPAWN requires and what an
;               entry proc is not
; Preserves every register. A refusal is TRANSIENT (the task table is full),
; so the flag is set only on success and the next paint tries again.
; -----------------------------------------------------------------------------
ti_spawn_ck:
    cmp byte [ti_spawned], 0
    jne .out
    push ax
    push bx
    mov ax, ti_worker
    mov bx, [ti_win]
    call OSAPI_TASK_SPAWN
    jc .no
    mov byte [ti_spawned], 1
    OS88_WORKER_RESTARTABLE ti_worker
                                    ; ...AND THE REGION CANNOT MOVE WITHOUT
                                    ; THIS (SPEC.md 66.6.2): the kernel wrote
                                    ; our segment into this worker's frame
                                    ; before its first instruction, so a
                                    ; region with an undeclared worker is
                                    ; pinned however the region is declared.
                                    ; The park is at OSAPI_TASK_ALIVE, which
                                    ; is the TOP of the loop, and every byte
                                    ; that outlives a pass is a static
.no:
    pop bx
    pop ax
.out:
    ret

; =============================================================================
; ti_worker - the frame
;
; The render runs once a tick - 18.2 Hz, flat, on every adapter - because that
; is the fastest clock this machine has that costs nothing to read. What the
; wheel does inside a tick is SPEC.md 97.5's, and the credit it spends was
; measured on this machine by ti_calibrate rather than modelled.
; =============================================================================
ti_worker:
    call OSAPI_GET_TICKS
    mov [ti_last], ax
.loop:
    mov bx, [ti_win]
    call OSAPI_TASK_ALIVE           ; the lock must NOT be held here; a clicked
                                    ; close box never returns
    cmp byte [ti_paused], 0
    jne .sleep
    cmp byte [ti_ok], 0
    je .sleep
    call OSAPI_GET_TICKS
    cmp ax, [ti_last]
    je .sleep                       ; the tick has not turned over: nothing is
    mov [ti_last], ax               ; due, and a frame that draws nothing is a
                                    ; frame that costs nothing
    call OSAPI_GFX_LOCK
    mov bx, [ti_win]
    call OSAPI_WM_CLIP_SET          ; A WORKER ARRIVES WITH NO REGION ARMED
    jc .unlk                        ; (SPEC.md 11.3) - only W_PAINT is handed
                                    ; one, so without this the frame draws
                                    ; straight over whatever is on top of us,
                                    ; and CF=1 means the window has gone
    call ti_frame
    call OSAPI_WM_CLIP_CLEAR
.unlk:
    call OSAPI_GFX_UNLOCK
.sleep:
    mov ax, 1
    call OSAPI_TASK_SLEEP
    jmp short .loop

; -----------------------------------------------------------------------------
; ti_frame - ONE PASS OF THE PACING WHEEL (SPEC.md 97.5)
; in:  the gfx lock is held
;
; Walk from where it stopped, commit every feature whose clock is due,
; subtract that band's own cost, stop when the credit is spent, and REMEMBER
; THE POSITION. A feature that misses its slot is late by one frame and never
; slowed: its clock advances on the tick and not on how many neighbours drew.
; -----------------------------------------------------------------------------
ti_frame:
    push ax
    push bx
    push cx
    push dx
    call ti_hover_ck                ; the pointer moved between cards: put the
    jnc .credit                     ; one it LEFT back, before the credit is
    cmp word [ti_hovold], -1        ; spent. The one it arrived on is feature
    je .credit                      ; 22 and is drawn by the walk below
    mov ax, [ti_hovold]
    call ti_card_draw
.credit:
    mov ax, [ti_creditus]
    mov [ti_left], ax
    mov cx, TI_FEATURES
.walk:
    or cx, cx
    jz .out
    mov ax, [ti_wpos]
    inc ax
    cmp ax, TI_FEATURES
    jb .keep
    xor ax, ax
.keep:
    mov [ti_wpos], ax
    mov bx, ax
    add bx, ti_clock
    mov al, [bx]                    ; this feature's own phase counter
    inc al
    cmp al, TI_POSES
    jb .store
    xor al, al
.store:
    mov [bx], al
    mov ax, [ti_wpos]
    call ti_feature                 ; ...and the commit
    mov ax, [ti_bandus]
    cmp [ti_left], ax
    jbe .out                        ; the credit is the contract: overrun is
    sub [ti_left], ax               ; impossible by construction
    dec cx
    jmp short .walk
.out:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_all - every feature, once: what a full repaint owes
; -----------------------------------------------------------------------------
ti_all:
    push ax
    push cx
    xor ax, ax
.f:
    cmp ax, TI_FEATURES
    jae .out
    push ax
    call ti_feature
    pop ax
    inc ax
    jmp short .f
.out:
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ti_feature - commit feature AX: ONE opaque band, ground baked in
; Preserves every register.
; -----------------------------------------------------------------------------
ti_feature:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp ax, TI_CELLS
    jb .cell
    cmp ax, TI_CELLS + 2            ; ...and 20 and 21 are the two BASES, which
    jae .hand                       ; sit outside the grid behind each player's
    sub ax, TI_CELLS                ; rear column (SPEC.md 97.2.1). 22 is the
    mov bx, ax                      ; moused-over card and belongs to the card
    add bx, TI_CELLS                ; panel, which is the next increment
    add bx, ti_clock
    mov bl, [bx]
    xor bh, bh
    mov [ti_pi], bx
    mov bx, [ti_b1x]
    or ax, ax
    jz .bx
    mov bx, [ti_b2x]
.bx:
    mov ax, bx
    call ti_base_draw
    jmp short .out
.hand:
    cmp word [ti_hover], -1         ; 22 is the MOUSED-OVER CARD, the one
    je .out                         ; feature that is not a character: it is
    mov ax, [ti_hover]              ; inverted, so redrawing it is what makes
    call ti_card_draw               ; the hover read as a state and not a flash
    jmp short .out
.cell:
    mov [ti_ci], ax
    mov bx, ax
    add bx, ti_clock
    mov al, [bx]
    xor ah, ah
    mov [ti_pi], ax
    call ti_pose_addr               ; DI = the pose's band
    mov si, di
    mov ax, [ti_ci]
    call ti_cell_xy                 ; AX = the cell's x, BX = its y
    add ax, [ti_insx]               ; ...and the figure's own inset inside it,
    add bx, [ti_insy]               ; rounded to the byte grid by ti_layout
    push ds
    pop es
    mov cx, [ti_bw]
    mov dx, [ti_bh]
    mov bp, [ti_bs]
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
; ti_calibrate - what a band costs ON THIS MACHINE (SPEC.md 97.5)
;
; Blit one band TI_CALN times off the wall clock and divide. The credit is
; then this adapter's, this CPU's and this kernel's - with or without SPEC.md
; 5.4.2.6's fast path - rather than a number derived from a model of some
; other machine. It costs a few milliseconds, once, and there is no CPU-tier
; table to be wrong about.
;
; THE PIT IS LATCHED AND NOT REPROGRAMMED. Control word 00h freezes a copy for
; reading and changes neither the mode nor the reload value, so the system
; tick is undisturbed; tests/benchlib.inc's bl_pit is the same read.
; =============================================================================
ti_calibrate:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    cmp byte [ti_ok], 0
    je .out

    pushf
    cli                             ; the span must not have a tick ISR in it
    call ti_pit
    mov [ti_t0], ax
    mov cx, TI_CALN
.b:
    push cx
    mov word [ti_pi], 0
    call ti_pose_addr
    mov si, di
    push ds
    pop es
    mov ax, [ti_bx]
    mov bx, [ti_by]
    mov cx, [ti_bw]
    mov dx, [ti_bh]
    mov bp, [ti_bs]
    call OSAPI_GFX_BLIT1
    pop cx
    loop .b
    call ti_pit
    mov bx, [ti_t0]
    sub bx, ax                      ; counter 0 counts DOWN: start - end, and
    popf                            ; modular, because it reloads every 55 ms

    mov ax, bx                      ; counts -> microseconds: one count is
    mov dx, 0                       ; 0.8381 us, so us = counts * 8381 / 10000
    mov cx, 8381
    mul cx
    mov cx, 10000
    div cx
    xor dx, dx
    mov cx, TI_CALN
    div cx                          ; AX = microseconds a band
    or ax, ax
    jnz .have
    inc ax                          ; a machine too fast to measure this way
.have:                              ; still gets a credit it can divide by
    mov [ti_bandus], ax
    call ti_credit
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

; ti_credit - the frame's credit, from the share and the measured band
ti_credit:
    push ax
    push dx
    push cx
    mov ax, TI_FRAMEUS
    xor dx, dx
    mov cx, 100
    div cx
    mov cx, [ti_share]
    mul cx                          ; AX = the share of one frame, in us
    mov [ti_creditus], ax
    pop cx
    pop dx
    pop ax
    ret

; ti_pit - latch and read counter 0 of the 8253 (a READ, not a reprogram)
; out: AX = the counter. Every caller has IF = 0: a latch interrupted between
;      the two byte reads returns a torn count.
ti_pit:
    push dx
    mov al, 0
    out 0x43, al
    jmp short $+2                   ; I/O settling, the period-hardware idiom
    in al, 0x40
    mov dl, al
    jmp short $+2
    in al, 0x40
    mov ah, al
    mov al, dl
    pop dx
    ret

%include "tilay.inc"
%include "tirend.inc"
%include "ticard.inc"

; =============================================================================
; data
; =============================================================================

ti_tpl:
    dw 0, 30, 640, 355
    dw ti_ttl, ti_paint, ti_onkey, ti_onclick

; --- the preferred frame, PER ADAPTER ---------------------------------------
; THE WIDTH IS THE WHOLE DISPLAY, ON PURPOSE (SPEC.md 11.95.2). A window whose
; x is its display's first column and whose width spans it loses BOTH side
; borders - `wm_flush_ck` - so its content starts at W_X, which is 0, and is
; 8-ALIGNED BY CONSTRUCTION. That matters here far more than it does for text:
; OSAPI_FONT_RUN on an unaligned origin is merely slower, while
; OSAPI_GFX_BLIT1 REFUSES an x off the byte grid outright, so an unaligned
; content origin is not a slow board, it is NO BOARD AT ALL.
;
; ASKING FOR *NEARLY* THE SCREEN IS THE WORST OF BOTH and is what this asked
; for first: 634 of 640 is not flush, so the window keeps its borders AND the
; snap that would align them is refused, because wm_snap_ax may only move a
; window LEFT except from x = 0..6, where moving right to 7 would push a
; 634-wide window off the edge. The content came out at x = 7 and every blit
; on the board refused in silence. Anything at or under 633 would have snapped;
; the whole display is better still, because it also hands back the two columns
; the borders were eating.
;
; The height is what the board NEEDS and no more. SPEC.md 11.100.1's advice to
; ask for a real width and a GENEROUS height is for a window whose content
; grows into whatever it is given, and this one's does not - the board's size
; is fixed by the table above, so a generous ask buys dead pixels. It bought
; 176 dead columns and 60 dead rows on a VGA.
ti_pref:                            ; VGA / Hercules / CGA (SPEC.md 11.100.1)
    dw 640, 355                     ; 624x328 of content needed
    dw 720, 271                     ; 712x244
    dw 640, 155                     ; 632x128

; --- the stat icons (SPEC.md 97.4.1) ----------------------------------------
; 8x8 1bpp bands, bit 7 leftmost, a set bit LIT. One cell each, which is what
; makes an icon cost exactly as much room as the digit it labels.
ti_ic_cost: db 03Ch, 066h, 0DBh, 0DBh, 0DBh, 0DBh, 066h, 03Ch   ; a coin
ti_ic_atk:  db 018h, 018h, 018h, 018h, 07Eh, 018h, 018h, 03Ch   ; a sword
ti_ic_def:  db 0FFh, 0C3h, 0C3h, 066h, 066h, 03Ch, 018h, 000h   ; a shield
ti_ic_hp:   db 066h, 0FFh, 0FFh, 0FFh, 07Eh, 03Ch, 018h, 000h   ; a heart

ti_s_commit: db 'COMMIT  SWAP ', 0
ti_n_1:     db 'PIKEMAN', 0
ti_n_2:     db 'ARCHER', 0
ti_n_3:     db 'WARDEN', 0
ti_n_4:     db 'ACOLYTE', 0
ti_n_5:     db 'RAM', 0
ti_n_6:     db 'HERALD', 0
ti_n_7:     db 'BULWARK', 0
                                    ; cost, atk, def, name - a fixed hand,
                                    ; because wave 1a has no deck behind it and
ti_cards:                           ; what is being judged is the LOOK
    db 2, 3, 2
    dw ti_n_1
    db 3, 4, 1
    dw ti_n_2
    db 4, 2, 6
    dw ti_n_3
    db 2, 1, 3
    dw ti_n_4
    db 5, 7, 2
    dw ti_n_5
    db 3, 2, 4
    dw ti_n_6
    db 6, 5, 8
    dw ti_n_7

ti_s_p1:    db 'P1  HP ', 0
ti_s_p2:    db 'P2  HP ', 0
ti_s_gold:  db '  GOLD ', 0
ti_s_round: db 'ROUND ', 0
ti_s_phase: db '  PLAN', 0

ti_p1hp:    db 20                  ; wave 1a has no rules behind it, so the
ti_p1gold:  db 7                   ; HUD's numbers are a fixed position rather
ti_p2hp:    db 18                  ; than a running game. What is being judged
ti_p2gold:  db 5                   ; is whether the STRIP reads at all four
ti_round:   db 3                   ; surface sizes (TITHE-PLAN 16.1)

ti_ttl:     db 'Tithe', 0
ti_about:   db 'TITHE - wave 1a, the renderer. SPEC.md 97.', 0
ti_s_small: db 'This window is too small for a board.', 0

ti_win:     dw 0
ti_laid:    db 0                  ; ti_relayout_ck has cut against ti_geo +
                                  ; ti_cw_box/ti_ch_box as they stand
ti_ok:      db 0
ti_full:    db 0
ti_paused:  db 0
ti_spawned: db 0
ti_dirty:   db 0
ti_last:    dw 0
ti_t0:      dw 0
ti_wpos:    dw 0
ti_left:    dw 0
ti_creditus: dw 21970
ti_bandus:  dw 4800                 ; a starting guess, replaced by the first
                                    ; ti_calibrate - and it is only ever a
                                    ; guess until then (SPEC.md 97.5)
ti_share:   dw TI_SHARE
ti_geo:     dw 0
ti_ci:      dw 0
ti_pi:      dw 0
ti_ry:      dw 0

; --- the layout, filled by ti_layout ----------------------------------------
ti_cw:      dw 0
ti_ch:      dw 0
ti_rise:    dw 0
ti_bw:      dw 0
ti_bh:      dw 0
ti_bs:      dw 0
ti_hud:     dw 0
ti_pan:     dw 0
ti_panx:    dw 0
ti_basew:   dw 0                    ; a base zone's columns, each side
ti_baseh:   dw 0                    ; ...and its rows: three lanes
ti_bas:     dw 0                    ; ...and its band's stride in bytes
ti_b1x:     dw 0                    ; P1's base x, behind column 0
ti_b2x:     dw 0                    ; P2's, behind column 3
ti_basey:   dw 0
ti_cardh:   dw 0                    ; a hand row's height
ti_cardx:   dw 0
ti_cardw:   dw 0
ti_cardn:   dw 0
ti_cardpitch: dw 0
ti_cardi:   dw 0
ti_cardy:   dw 0
ti_cardp:   dw 0
ti_cardl2:  dw 0
ti_cx:      dw 0                    ; is this card the hovered one?
ti_cbx:     dw 0                    ; ...and the box it is actually drawn in
ti_cbw:     dw 0
ti_cink:    db 0
ti_cpap:    db 0
ti_hover:   dw -1                   ; the card under the pointer, -1 for none
ti_hovold:  dw -1                   ; ...and the one it just left
ti_swaps:   db 2
ti_nums:    dw 0                    ; rows of numbers a cell carries
ti_nx:      dw 0                    ; the cell whose numbers are being drawn
ti_ny:      dw 0
ti_ktop:    dw 0                    ; the keep's top row, banked because two
                                    ; `mul`s stand between it and its reader
ti_spanw:   dw 0                    ; what ti_pose_span clips against
ti_bx:      dw 0
ti_by:      dw 0
ti_ox:      dw 0
ti_oy:      dw 0
ti_cw_box:  dw 0
ti_ch_box:  dw 0
ti_boardw:  dw 0
ti_boardh:  dw 0
ti_lift:    dw 0
ti_insx:    dw 0
ti_insy:    dw 0

; --- SPEC.md 97.2's table: CW, CH, RISE, BW, BH, HUD, PAN ------------------
; THE PROPORTION IS THE CELL'S APPARENT ONE AND NOT ITS PIXEL ONE. A CGA pixel
; is about 2.4 times as tall as it is wide and a Hercules one 1.5, so 120x40 on
; a Hercules and 112x56 on a VGA are the same tile to look at. The first cut of
; the VGA rows was 80x56 - very nearly SQUARE on the one adapter with square
; pixels - and a diamond inscribed in a square cell is a tall lozenge that
; meets its neighbours at four points, which is the opposite of an isometric
; read. Every row is ~2:1 apparent now bar CGA's, whose height has 8 pixels of
; slack in the whole window.
;
; CUT AGAINST THE CONTENT BOXES THIS MACHINE ACTUALLY HANDS OUT, and the first
; three rows of it were not: the boxes are VGA 640x416, Hercules 680x284 and
; CGA 504x136, so the Hercules and CGA rows asked for a board 56 and 62 pixels
; taller than the window they had to live in and BOTH refused themselves on
; every machine. The short screens are short in HEIGHT and not in width - a
; CGA has 504 columns of content and 136 rows - which is why what came down
; is CH and RISE and not CW.
;            CW   CH  RISE  BW  BH  HUD  PAN  BASEW  NUMS  CARDH  INSX
ti_geo_vgaf: dw  96, 52, 22, 64, 48, 36, 136, 56, 2, 36, 24
ti_geo_vgaw: dw  96, 48, 20, 64, 44, 28, 128, 56, 2, 32, 24
ti_geo_herc: dw 104, 36, 12, 64, 32, 28, 152, 72, 2, 22, 24
ti_geo_cga:  dw  96, 20,  4, 64, 18, 16, 152, 48, 1, 12, 24

ti_clock:   times TI_FEATURES db 0
ti_hudn:    dw 0
ti_hudbuf:  times TI_HUDMAX db 0
ti_numbuf:  times 4 db 0
ti_cardbuf: times 24 db 0

TI_BSS      equ TI_CELLMAX + TI_BANDMAX * TI_POSES + TI_BASEMAX * TI_BASEPOSES

    OS88_BSS TI_BSS
    OS88_IMAGE_END

ti_cell     equ os88_image_end + 0
ti_pose     equ os88_image_end + TI_CELLMAX
ti_base     equ os88_image_end + TI_CELLMAX + TI_BANDMAX * TI_POSES
