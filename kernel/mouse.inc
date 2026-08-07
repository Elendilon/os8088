; =============================================================================
; os8088 - mouse.inc
;
; Serial Microsoft mouse on COM1 (0x3F8, IRQ4 -> int 0x0C) plus the arrow
; cursor with save-under. The ISR decodes the 3-byte Microsoft packet, keeps
; mouse_x/mouse_y/mouse_btn fresh, queues EVT_MDOWN/EVT_MUP on left-button
; changes and EVT_RDOWN on the right button's PRESS edge, and moves the
; cursor itself only when the gfx lock is free and the cursor is
; refcount-visible (SPEC 7); otherwise it just sets cur_dirty.
;
; cursor_show/cursor_hide are refcounted via cur_level (-1 = hidden at boot,
; classic Show/HideCursor style) and guard their draw/restore sections with
; pushf/cli ... popf so the ISR never sees a half-drawn cursor. Both are
; called with the gfx lock held (from gfx_lock/gfx_unlock) or at boot.
;
; The hotspot is the drawn position (0,0 of the cell); at the right and
; bottom screen edges the cell is clipped, never shifted;
; mouse_x/mouse_y themselves range over the full 0..639 / 0..479.
; =============================================================================

MOU_COM1    equ 0x3F8           ; COM1 base: +1 IER, +2 IIR, +3 LCR, +4 MCR,
                                ;            +5 LSR (DLAB: +0 DLL, +1 DLM)
MOU_INTVEC  equ 0x30            ; int 0x0C vector offset in the IVT

MOU_RSTLOW  equ 3               ; ticks DTR/RTS are held LOW in a reset
                                ; (~165ms; a serial mouse wants >=100ms
                                ; unpowered to guarantee its power-on reset)
MOU_REPOLL  equ 55              ; ticks between hot-plug reset attempts
                                ; (~3s) while no packet has ever arrived
MOU_DRAINT  equ 9               ; ticks the ISR discards RX after a hot-plug
                                ; raise (~0.5s): the identify/PnP burst is
                                ; bit-6-set bytes the resync rule would read
                                ; as packet headers - phantom clicks

CUR_W       equ 16              ; cursor cell size, px - the size of the two
CUR_H       equ 16              ; bitmap TABLES, and nothing else

; The arrow inside that cell (SPEC.md 7.1). The tables are 16 rows of 16 bits
; because that is the classic shape; the ARROW is 8 pixels wide and 12 rows
; tall, and for years every save, every restore and both draw passes walked
; the whole 16x16 - a quarter of the rows and a third of the bytes per row of
; work on empty bits, on every gfx_lock and every gfx_unlock in the machine.
;
; Both are ASSERTED against the tables at the bottom of this file rather than
; trusted, so a redrawn arrow that outgrows either one fails the build instead
; of quietly losing its right-hand column. The width is what retires the cell's
; THIRD byte: a 16-bit row whose low byte is zero cannot reach one however far
; it is shifted, so `row << (8-shift)` was a byte that was always 0 and a
; branch that was never taken, once per row per pass.
CUR_GW      equ 8               ; the arrow's own width, px...
CUR_GH      equ 12              ; ...and height, rows
CUR_SPAN    equ 2               ; ...and the framebuffer bytes it spans once
                                ; shifted by x & 7, which CUR_GW <= 8 bounds
CUR_TABSZ   equ CUR_H * 2       ; cur_data is exactly one table past cur_and,
                                ; so one SI walks both (asserted below)
CUR_SAVE_SZ equ CUR_SPAN * CUR_GH * 4       ; ...x four planes, for VGA

; -----------------------------------------------------------------------------
; mouse_init - hook int 0x0C, program the UART (1200 baud 7N1, RX interrupt,
;              DTR|RTS|OUT2 so the mouse powers up), flush stale RX/LSR/IIR,
;              unmask IRQ4 at the 8259.
; ins:  none
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mouse_init:
    push ax
    push dx
    push es

    ; --- save the old int 0x0C vector, install ours --------------------------
    xor ax, ax
    mov es, ax
    pushf
    cli
    mov ax, [es:MOU_INTVEC]
    mov [mou_old_off], ax
    mov ax, [es:MOU_INTVEC+2]
    mov [mou_old_seg], ax
    mov word [es:MOU_INTVEC], mou_isr
    mov [es:MOU_INTVEC+2], cs
    popf

    ; --- UART: 1200 baud, 7 data bits, no parity, 1 stop ---------------------
    mov dx, MOU_COM1+3          ; LCR: DLAB=1 + 7N1 bits
    mov al, 0x82
    out dx, al
    mov dx, MOU_COM1            ; divisor low = 96 (115200/96 = 1200)
    mov al, 96
    out dx, al
    mov dx, MOU_COM1+1          ; divisor high = 0
    xor al, al
    out dx, al
    mov dx, MOU_COM1+3          ; LCR: DLAB=0, 7N1
    mov al, 0x02
    out dx, al

    ; --- reset the mouse: DTR/RTS LOW, hold, then raise ----------------------
    ; A serial mouse is POWERED by DTR/RTS and resets itself on the RISING
    ; edge. Writing the final MCR value straight away only makes that edge on
    ; a cold boot, where the lines start low; on a Ctrl-Alt-Del warm boot
    ; they are still high from the previous session, the rewrite is no edge
    ; at all, and a mouse that was wedged (hot-plugged onto live lines, say)
    ; STAYS wedged until the user finds the power switch - which is exactly
    ; how this was found on a real 5150. Hold low for ~150ms (the parts want
    ; >=100ms unpowered to guarantee a reset), then raise: every boot now
    ; hands the mouse the same clean power-on a cold start does.
    push bx
    mov dx, MOU_COM1+4          ; MCR: OUT2 only - DTR and RTS low. OUT2
    mov al, 0x08                ; stays up throughout so the IRQ gate never
    out dx, al                  ; glitches the bus
    mov bx, [ticks]
.rstlow:
    mov ax, [ticks]
    sub ax, bx
    cmp ax, MOU_RSTLOW
    jb .rstlow
    mov dx, MOU_COM1+4          ; MCR: DTR|RTS|OUT2 - powers the mouse and
    mov al, 0x0B                ; gates the IRQ onto the bus; this rising
    out dx, al                  ; edge is the mouse's reset

    ; --- drain the identify burst (IER still 0, IRQ4 still masked) -----------
    ; The DTR/RTS edge makes a real Microsoft mouse announce itself: 'M',
    ; maybe '3', maybe a whole PnP string - bytes with bit 6 set that the
    ; ISR's resync rule would misread as packet headers (phantom clicks,
    ; cursor jumps). Poll-and-discard for ~1 second before enabling RX
    ; interrupts; sched_init already runs, so [ticks] is live.
    mov bx, [ticks]
.settle:
    mov dx, MOU_COM1+5          ; LSR: RX data ready?
    in  al, dx
    test al, 0x01
    jz .nochar
    mov dx, MOU_COM1
    in  al, dx                  ; discard identify/PnP byte
.nochar:
    mov ax, [ticks]
    sub ax, bx
    cmp ax, 19                  ; ~1s at 18.2Hz covers 'M3'+PnP at 1200 7N1
    jb .settle
    pop bx

    mov dx, MOU_COM1+1          ; IER: RX data available only
    mov al, 0x01
    out dx, al

    ; --- flush whatever is stale (IRQ4 still masked, so no race) -------------
    mov dx, MOU_COM1            ; RX
    in  al, dx
    mov dx, MOU_COM1+5          ; LSR
    in  al, dx
    mov dx, MOU_COM1+2          ; IIR
    in  al, dx

    mov byte [mou_phase], 0

    ; --- unmask IRQ4 ----------------------------------------------------------
    in  al, 0x21
    and al, 0xEF
    out 0x21, al

    pop es
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; mou_hotplug - keep offering a hot-plugged mouse its reset (SPEC.md 9.4)
; in:  nothing; UI task, every pass, no lock needed (port I/O + .bss only)
; out: nothing (all registers preserved)
;
; mouse_init runs blind - there is no probe, and a machine with no mouse at
; boot is indistinguishable from one whose mouse has not spoken yet. So while
; NO packet has ever arrived ([mou_seen]), this re-runs init's reset edge
; every MOU_REPOLL ticks: drop DTR/RTS (the mouse's power), hold MOU_RSTLOW,
; raise - and a mouse plugged in at any point since the last attempt gets the
; same clean power-on a cold boot with it attached does. The identify burst
; the raise provokes arrives through the ISR this time (IER is live), so the
; raise arms [mou_drain] and the ISR discards RX for MOU_DRAINT.
;
; The first complete packet sets [mou_seen] and this becomes one cmp per
; pass, forever. Until then the cost of being wrong is nil: with no serial
; card the writes land on a floating bus, and with a healthy-but-idle mouse
; a cycle re-identifies it and the drain eats the burst. The one visible
; seam is that motion STARTED inside a drain window is eaten with it -
; up to half a second, self-healing on the next packet - which is the price
; of never mistaking a PnP string for a click.
; -----------------------------------------------------------------------------
mou_hotplug:
    cmp byte [mou_seen], 0
    jne .have                   ; the mouse exists: stand down - but see .have
    push ax
    push bx
    push dx
    mov bx, [ticks]
    mov ax, bx
    sub ax, [mou_hpt]           ; wrap-safe: elapsed since the state's stamp
    cmp byte [mou_hpst], 1
    je .low
    cmp ax, MOU_REPOLL          ; state 0: waiting out the poll interval
    jb .done
    mov dx, MOU_COM1+4          ; drop DTR/RTS - power the mouse down. OUT2
    mov al, 0x08                ; stays up so the IRQ gate never glitches
    out dx, al
    mov [mou_hpt], bx
    mov byte [mou_hpst], 1
    jmp short .done
.low:
    cmp ax, MOU_RSTLOW          ; state 1: held low long enough?
    jb .done
    mov dx, MOU_COM1+4
    mov al, 0x0B                ; the rising edge a serial mouse resets on
    out dx, al
    mov [mou_hpt], bx
    mov byte [mou_hpst], 0
    mov [mou_dstamp], bx        ; the burst comes through the ISR now: arm
    mov byte [mou_drain], 1     ; the discard window
    mov byte [mou_phase], 0
.done:
    pop dx
    pop bx
    pop ax
    ret

.have:                          ; proof can arrive at an awkward moment: a
    cmp byte [mou_hpst], 0      ; byte the UART latched before a drop can
    je .out                     ; complete a packet while DTR is LOW, and
    push ax                     ; standing down right there would leave the
    push dx                     ; mouse UNPOWERED forever - deader than the
    mov dx, MOU_COM1+4          ; bug this exists to fix. Put the power back
    mov al, 0x0B                ; up first, then never come here again in
    out dx, al                  ; anger
    mov byte [mou_hpst], 0
    pop dx
    pop ax
.out:
    ret

; -----------------------------------------------------------------------------
; mouse_unhook - silence the UART (IER=0), mask IRQ4 again, restore the old
;                int 0x0C vector. Used before reboot.
; ins:  none
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mouse_unhook:
    push ax
    push dx
    push es

    mov dx, MOU_COM1+1          ; IER = 0: no more UART interrupts
    xor al, al
    out dx, al

    in  al, 0x21                ; mask IRQ4
    or  al, 0x10
    out 0x21, al

    xor ax, ax
    mov es, ax
    pushf
    cli
    mov ax, [mou_old_off]
    mov [es:MOU_INTVEC], ax
    mov ax, [mou_old_seg]
    mov [es:MOU_INTVEC+2], ax
    popf

    pop es
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; mou_isr - IRQ4 handler. One RX byte per interrupt. Microsoft protocol:
;           byte 0 has bit 6 set: 1 LB RB Y7 Y6 X7 X6; bytes 1/2 have bit 6
;           clear: low 6 bits of X then Y. Any bit-6 byte restarts the packet
;           (resync). Runs with IF=0 throughout; never sti (SPEC 7).
; -----------------------------------------------------------------------------
mou_isr:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push ds
    push es
    mov ax, KERNEL_SEG
    mov ds, ax
    cld

    mov dx, MOU_COM1
    in  al, dx

    cmp byte [mou_drain], 0     ; a hot-plug raise just happened (below):
    je .live                    ; this is the identify/PnP burst, and its
    mov bx, [ticks]             ; bit-6 bytes would resync as headers. BX is
    sub bx, [mou_dstamp]        ; free - pushed above, first used well below
    cmp bx, MOU_DRAINT
    jb .eoi                     ; discard the byte
    mov byte [mou_drain], 0     ; window over: this byte is live
.live:
    test al, 0x40               ; bit 6 set -> first byte of a packet
    jz .cont
    mov [mou_b0], al
    mov byte [mou_phase], 1
    jmp .eoi

.cont:
    cmp byte [mou_phase], 1
    jne .chk2
    mov [mou_b1], al            ; second byte: X low 6 bits
    mov byte [mou_phase], 2
    jmp .eoi

.chk2:
    cmp byte [mou_phase], 2     ; anything else is a stray byte - drop it
    jne .eoi
    mov byte [mou_phase], 0     ; third byte: Y low 6 bits, packet complete
    mov byte [mou_seen], 1      ; ...and a packet is PROOF OF MOUSE: the
                                ; hot-plug poller stands down for the session
    mov bl, al                  ; BL = Y low bits, decoded below

    ; --- dx = sign-extended {X7X6 from b0, X5..X0 from b1} -------------------
    mov al, [mou_b0]
    and al, 0x03
    mov cl, 6
    shl al, cl                  ; X7X6 into bits 7:6
    mov ah, [mou_b1]
    and ah, 0x3F
    or  al, ah
    cbw                         ; AX = dx, signed
    add ax, [mouse_x]
    or  ax, ax                  ; clamp 0..[vid_wm1]
    jns .xlo
    xor ax, ax
.xlo:
    cmp ax, [vid_wm1]
    jle .xok
    mov ax, [vid_wm1]
.xok:
    mov [mouse_x], ax

    ; --- dy = sign-extended {Y7Y6 from b0, Y5..Y0 from b2}; positive = down --
    mov al, [mou_b0]
    and al, 0x0C
    mov cl, 4
    shl al, cl                  ; Y7Y6 into bits 7:6
    and bl, 0x3F
    or  al, bl
    cbw                         ; AX = dy, signed
    add ax, [mouse_y]
    or  ax, ax                  ; clamp 0..[vid_hm1]
    jns .ylo
    xor ax, ax
.ylo:
    cmp ax, [vid_hm1]
    jle .yok
    mov ax, [vid_hm1]
.yok:
    mov [mouse_y], ax

    ; --- buttons: b0 bit 5 = left, bit 4 = right -----------------------------
    mov al, [mou_b0]
    xor bl, bl
    test al, 0x20
    jz .nol
    or  bl, 0x01
.nol:
    test al, 0x10
    jz .nor
    or  bl, 0x02
.nor:
    mov bh, [mouse_btn]
    mov [mouse_btn], bl
    xor bh, bl                  ; changed bits
    test bh, 0x01               ; left button changed?
    jz .rbtn

    mov ax, EVT_MUP             ; queue EVT_MDOWN / EVT_MUP, a=x b=y (SPEC 10)
    test bl, 0x01
    jz .fill
    mov ax, EVT_MDOWN
    jmp short .fill

    ; The right button is tested on the LEFT test's fall-through, and that
    ; ordering is binding (SPEC.md 9): a packet reporting both buttons
    ; changed queues the left event ONLY, so a chord can never steal a left
    ; press from the drag loop or the double-click detector. Only the press
    ; edge is queued - the context menu it opens lives on a level poll of
    ; mouse_btn bit 1 (SPEC.md 12.4), so an EVT_RUP would be a record
    ; nobody ever pops.
.rbtn:
    test bh, 0x02               ; right button changed?
    jz .move
    test bl, 0x02
    jz .move                    ; a right RELEASE queues nothing
    mov ax, EVT_RDOWN

.fill:
    mov si, mou_evrec
    mov [si], ax
    mov ax, [mouse_x]
    mov [si+2], ax
    mov ax, [mouse_y]
    mov [si+4], ax
    mov ax, [ticks]             ; c = birth time: double-click detection must
    mov [si+6], ax              ; not use processing time - clicks queued
                                ; behind a slow disk mount would collapse
                                ; into one instant and read as double-clicks
    call evq_push               ; guards internally with pushf/cli; IF stays 0

.move:
    ; --- cursor: draw only if the lock is free AND cur_level >= 0 (SPEC 7) ---
    cmp byte [gfx_lock_flag], 0
    jne .dirty
    mov al, [cur_level]
    or  al, al
    js .dirty

    mov ax, [mouse_x]           ; hotspot = drawn position; the cell is
    mov bx, [mouse_y]           ; clipped at the screen edges in cur_draw
    cmp ax, [cur_drawn_x]       ; button-only packet: nothing to redraw
    jne .redraw
    cmp bx, [cur_drawn_y]
    je .eoi
.redraw:
    push ax
    push bx
    call cur_get                ; erase at the old position
    pop bx
    pop ax
    mov [cur_drawn_x], ax
    mov [cur_drawn_y], bx
    call cur_put                ; save under + draw at the new one
    mov byte [cur_dirty], 0
    jmp .eoi

.dirty:
    mov byte [cur_dirty], 1     ; cursor_show catches up later

.eoi:
    mov al, 0x20                ; EOI - the BIOS does not handle IRQ4 for us
    out 0x20, al
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    iret

; -----------------------------------------------------------------------------
; cursor_show - increment cur_level; on the -1 -> 0 transition, save under and
;               draw the cursor at the latest mouse position (clipped) and
;               clear cur_dirty. Interrupt-safe: the critical section runs
;               under pushf/cli so the ISR never sees a half-drawn state.
; ins:  none
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
cursor_show:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    pushf
    cli
    inc byte [cur_level]
    jnz .done                   ; only the -1 -> 0 edge draws

    mov ax, [mouse_x]           ; hotspot = drawn position; the cell is
    mov bx, [mouse_y]           ; clipped at the screen edges in cur_draw
    mov [cur_drawn_x], ax
    mov [cur_drawn_y], bx
    mov byte [cur_dirty], 0
    call cur_put
.done:
    popf
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cursor_hide - decrement cur_level; on the 0 -> -1 transition, restore the
;               save-under (the buffer is only valid while the cursor is
;               drawn). Same pushf/cli guard as cursor_show.
; ins:  none
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
cursor_hide:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    push es
    pushf
    cli
    dec byte [cur_level]
    cmp byte [cur_level], -1
    jne .done                   ; only the 0 -> -1 edge erases
    call cur_get
.done:
    popf
    pop es
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cur_put / cur_get - draw the cursor over what it covers, and put that back
;
; The pair is the whole of what gfx_lock and gfx_unlock cost (SPEC.md 7.1):
; the mutex itself is one flag and six instructions, and everything else in
; those two routines is here. A field log of Missile Command put the pair at
; 21.8% of a session with no pixel of the game in it (PERFORMANCE.md Part 9
; Set 4), which is what this shape is for.
;
; Both dispatch on the adapter, and the two sides are NOT symmetrical:
;
;   1bpp   cur_put_mono / cur_get_mono, below. The framebuffer IS the
;          renderer's target (SPEC.md 39.5), so the byte under the cursor can
;          be read, banked, painted and written back in ONE pass - where the
;          old path made three, through the generic rect machinery, twice.
;   VGA    cur_saveu + cur_draw / cur_restoreu, unchanged in shape: the save
;          is four planes through Read Map Select and the draw is Set/Reset
;          through the Bit Mask, so there is no single byte to fuse.
;
; Internal; the caller guarantees IF = 0 or the gfx lock.
; clobbers: ax, bx, cx, dx, si, di, bp, es
; -----------------------------------------------------------------------------
cur_put:
    cmp byte [vid_mono], 0
    jne cur_put_mono
    call cur_saveu
    jmp cur_draw

cur_get:
    cmp byte [vid_mono], 0
    jne cur_get_mono
    ; fall through to cur_restoreu

; -----------------------------------------------------------------------------
; cur_restoreu - write cur_save back under (cur_drawn_x, cur_drawn_y).
;                VRAM-direct (SPEC.md 32) - the cursor lives on the screen
;                only, never in the back buffer, and this runs from the ISR
;                where the bb dispatch must not apply.
; clobbers: ax, bx, cx, dx, si
; -----------------------------------------------------------------------------
cur_restoreu:
    push es
    call cur_rect
    push ds
    pop es
    mov si, cur_save
    call vga_restore_vram
    pop es
    ret

; -----------------------------------------------------------------------------
; cur_saveu - copy the cell under (cur_drawn_x, cur_drawn_y) into cur_save via
;             vga_save_vram. vga_save_vram clips the rect at the screen edges
;             the same way vga_restore_vram does, so partial cells stay
;             coherent - which is the whole reason these two share cur_rect.
; clobbers: ax, bx, cx, dx, di
; -----------------------------------------------------------------------------
cur_saveu:
    push es
    call cur_rect
    push ds
    pop es                      ; buffer lives in kernel .bss
    mov di, cur_save
    call vga_save_vram
    pop es
    ret

; cur_rect - the cell the two above save and restore, as a rect. ONE place,
; because a save and a restore that disagree about it by a byte smear the
; cursor across the screen. CUR_GW/CUR_GH, not CUR_W/CUR_H: the tables are
; 16x16 and the arrow is not.
; out: AX/BX/CX/DX = x1/y1/x2/y2
cur_rect:
    mov ax, [cur_drawn_x]
    mov bx, [cur_drawn_y]
    mov cx, ax
    add cx, CUR_GW-1
    mov dx, bx
    add dx, CUR_GH-1
    ret

; -----------------------------------------------------------------------------
; cur_geom - where the cursor cell is, and how much of it is on the screen
;
; out:      DI = framebuffer offset of the cell's top-left byte, CL = x & 7,
;           [cur_rows] = rows on screen (0..CUR_GH), [cur_b1ok] = may the byte
;           at DI+1 be written. The offset is BANKED in [cur_off] as well,
;           because cur_get_mono has to put back exactly the bytes
;           cur_put_mono took and re-deriving them is a second place that can
;           disagree - which, for a save-under, means the cursor smeared
;           across the screen rather than a pixel out of place.
; clobbers: AX, BX, DX, DI, CL
; -----------------------------------------------------------------------------
cur_geom:
    mov ax, [cur_drawn_y]       ; DI = rowbase(y) + x/8
    call gfx_rowbase
    mov di, ax
    mov bx, [cur_drawn_x]
    mov ax, bx
    mov cl, 3
    shr ax, cl
    add di, ax                  ; AX = the byte column, for the clip below
    mov cl, bl
    and cl, 7                   ; CL = shift (x & 7)

    ; --- clip the cell at the right and bottom screen edges ------------------
    ; bytes-in-row = stride - column; skip the DI+1 write that would otherwise
    ; wrap onto the next scan line. There is no DI+2: an 8px arrow spans two
    ; bytes however far it is shifted (CUR_SPAN).
    mov dx, [vid_stride]
    sub dx, ax                  ; DX = bytes available in this row (>= 1)
    mov byte [cur_b1ok], 0
    cmp dx, 2
    jb .cols_done
    mov byte [cur_b1ok], 1
.cols_done:
    mov ax, [vid_h]             ; UNSIGNED - vid_apply homes the cursor into
    sub ax, [cur_drawn_y]       ; the new screen precisely so this cannot
                                ; borrow. rows on screen at this y (>= 1)
    cmp ax, CUR_GH
    jbe .rows_set
    mov ax, CUR_GH
.rows_set:
    mov [cur_rows], al
    mov [cur_off], di
    ret

; -----------------------------------------------------------------------------
; cur_put_mono - save the cell under the cursor and draw the arrow into it, in
;                ONE pass (SPEC.md 7.1)
;
; The three passes this replaces - vga_save_vram's row loop, then cur_pass_mono
; for the white outline, then cur_pass_mono again for the black body - read the
; same framebuffer byte three times and wrote it twice, each time through its
; own row walk, its own gfx_nextrow call and, for the save, the whole of
; vga_rect_setup's generic clipping. They are the same bytes in the same order,
; and the two masks compose: (under | white) & ~black is what drawing one pass
; on top of the other always produced. So the byte is read once, banked once,
; painted once and written once.
;
; The row advance is gfx_nextrow INLINED, which is PERFORMANCE.md Part 9 Set
; 3's rule: at two framebuffer bytes a row, a near call and a ret are most of
; the loop.
;
; in:       cur_drawn_x/y; IF = 0 or the gfx lock held
; clobbers: ax, bx, cx, dx, si, di, bp, es
; -----------------------------------------------------------------------------
cur_put_mono:
    call cur_geom
    mov ch, [cur_rows]
    or ch, ch
    jz .out                     ; wholly off the bottom: nothing to bank
    mov ax, [vid_seg]
    mov es, ax
    mov si, cur_and
    mov bp, cur_save
.row:
    mov ax, [si]                ; the white pass's row...
    mov dx, [si+CUR_TABSZ]      ; ...and the black one's, one table along
    add si, 2
    shr ax, cl                  ; AH:AL = white bits, byte 0 : byte 1
    shr dx, cl                  ; DH:DL = black bits, likewise...
    not dx                      ; ...as an AND mask, so the body clears to 0

    mov bl, [es:di]             ; ONE read of the byte under the arrow...
    mov [ds:bp], bl             ; ...banked (SS is LOW_SEG, so ds: is not
                                ; decoration - SPEC.md 2.1)
    or  bl, ah                  ; ...white outline...
    and bl, dh                  ; ...black body over it...
    mov [es:di], bl             ; ...and ONE write

    cmp byte [cur_b1ok], 0      ; the second byte, unless the screen edge is
    je .adv                     ; between them
    mov bl, [es:di+1]
    mov [ds:bp+1], bl
    or  bl, al
    and bl, dl
    mov [es:di+1], bl
.adv:
    add bp, CUR_SPAN            ; RESERVED whether or not byte 1 was taken, so
                                ; cur_get_mono's walk needs no clip of its own
    add di, [cs:vid_rowadd]     ; gfx_nextrow, inlined (SPEC.md 39.3)
    test di, [cs:vid_wrapbit]
    jz .nowrap
    add di, [cs:vid_wrapfix]
.nowrap:
    dec ch
    jnz .row
.out:
    ret

; -----------------------------------------------------------------------------
; cur_get_mono - put cur_put_mono's bytes back, replaying its geometry
;
; [cur_off], [cur_shift], [cur_rows] and [cur_b1ok] are not recomputed: the
; cursor cannot have moved between the two, because every caller that moves it
; (the ISR's .redraw path) erases at the OLD position before it writes the new
; one. Recomputing would be a second answer to a question that already has one.
; clobbers: ax, cx, si, di, es
; -----------------------------------------------------------------------------
cur_get_mono:
    mov ch, [cur_rows]
    or ch, ch
    jz .out
    mov ax, [vid_seg]
    mov es, ax
    mov di, [cur_off]
    mov si, cur_save
.row:
    lodsb                       ; both bytes are always CONSUMED - the stride
    mov [es:di], al             ; is CUR_SPAN whatever the clip said - and only
    lodsb                       ; the second one is conditionally written
    cmp byte [cur_b1ok], 0
    je .adv
    mov [es:di+1], al
.adv:
    add di, [cs:vid_rowadd]     ; gfx_nextrow, inlined
    test di, [cs:vid_wrapbit]
    jz .nowrap
    add di, [cs:vid_wrapfix]
.nowrap:
    dec ch
    jnz .row
.out:
    ret

; -----------------------------------------------------------------------------
; cur_draw - paint the arrow at (cur_drawn_x, cur_drawn_y) on a PLANAR screen:
;            white pass with the cur_and outline mask, black pass with the
;            cur_data body. Set/Reset supplies the color; the Bit Mask register
;            carries the row bits, shifted across the cell's two VRAM bytes; a
;            read of each target byte loads the latches before the masked
;            write. Leaves the GC in the default state (SPEC 1 rule 7).
;            Internal; caller guarantees IF=0 and default GC state on entry.
; clobbers: ax, bx, cx, dx, si, di, bp, es
; -----------------------------------------------------------------------------
cur_draw:
    call cur_geom               ; DI = the top-left byte, CL = shift, and
    mov ax, [vid_seg]           ; [cur_rows]/[cur_b1ok] = how much is on screen
    mov es, ax
    mov dx, 0x3CE               ; GC1: enable Set/Reset on all planes
    mov ax, 0x0F01
    out dx, ax
    mov ah, CWHITE              ; GC0: Set/Reset color = white
    mov al, 0
    out dx, ax
    mov al, 8                   ; leave the index at GC8 (Bit Mask)
    out dx, al
    mov si, cur_and
    call cur_pass               ; white outline + fill

    mov dx, 0x3CE
    mov ah, CBLACK              ; GC0: Set/Reset color = black
    mov al, 0
    out dx, ax
    mov al, 8
    out dx, al
    mov si, cur_data
    call cur_pass               ; black body on top

    mov dx, 0x3CE               ; back to defaults: Set/Reset off, mask FF
    mov ax, 0x0001
    out dx, ax
    mov ax, 0xFF08
    out dx, ax
    ret

; -----------------------------------------------------------------------------
; cur_pass - one masked pass over the cell. Each 16-bit row lands at bit offset
;            CL inside a 16-bit window: B0:B1 = row >> CL. Zero mask bytes are
;            skipped.
;
; There is no third byte. Every row of both tables has a zero low byte - an
; 8px arrow (CUR_GW, asserted at the tables) - so `row << (8-CL)` could only
; ever be 0, and what it bought was a shift pair, a branch and a cur_b2ok test
; on every row of every pass.
; ins:  SI -> CUR_H-word row table, DI = VRAM offset of the top-left byte,
;       CL = shift, ES = VGA_SEG,
;       GC: Set/Reset enabled + color set, index register = 8
; outs: none; preserves CX, DI; clobbers ax, bx, dx, si, bp
; -----------------------------------------------------------------------------
cur_pass:
    push di
    xor ax, ax
    mov al, [cur_rows]          ; clipped row count from cur_geom
    mov bp, ax
    or  bp, bp
    jz .out
    mov dx, 0x3CF               ; GC data port; index already 8 (Bit Mask)
.row:
    lodsw                       ; AX = row bits, MSB = leftmost pixel
    shr ax, cl                  ; AH:AL = B0:B1
    mov bx, ax

    mov al, bh                  ; --- byte 0 ---
    or  al, al
    jz .b1
    out dx, al
    mov al, [es:di]             ; load latches
    mov [es:di], al
.b1:
    mov al, bl                  ; --- byte 1 ---
    or  al, al
    jz .next
    cmp byte [cur_b1ok], 0      ; clipped off the right screen edge?
    je .next
    out dx, al
    mov al, [es:di+1]
    mov [es:di+1], al
.next:
    add di, ROW_BYTES
    dec bp
    jnz .row
.out:
    pop di
    ret

; -----------------------------------------------------------------------------
; cursor bitmap - classic Mac arrow, hot spot (0,0), black body 11 rows tall
; with a 1px white outline. cur_and is the white pass (outline + fill),
; cur_data the black body drawn on top. MSB = leftmost pixel.
;
; The rows go in through CUR_ROW rather than `dw`, which emits the same word
; and ALSO accumulates the two facts the drawing code is built on: the widest
; bit set anywhere (CUR_GW) and the last row that has one (CUR_GH). Both are
; checked below. Neither can be trusted as a comment, because both fail
; silently - a wider arrow loses its right-hand column on the two mono
; adapters, a taller one leaves its bottom rows on the screen for the rest of
; the session, and neither shows up anywhere but on the glass.
; -----------------------------------------------------------------------------
%assign cur_bits 0              ; every bit any row sets, ORed together
%assign cur_hi   0              ; ...and one past the last row that sets any
%macro CUR_ROW 1
    dw %1
  %if (%1) != 0
   %if cur_row_i + 1 > cur_hi
    %assign cur_hi cur_row_i + 1
   %endif
  %endif
  %assign cur_bits  cur_bits | (%1)
  %assign cur_row_i cur_row_i + 1
%endmacro

%assign cur_row_i 0
cur_and:                        ; white: body dilated by 1px in all directions
    CUR_ROW 0xE000              ; ***.............
    CUR_ROW 0xF000              ; ****............
    CUR_ROW 0xF800              ; *****...........
    CUR_ROW 0xFC00              ; ******..........
    CUR_ROW 0xFE00              ; *******.........
    CUR_ROW 0xFF00              ; ********........
    CUR_ROW 0xFF00              ; ********........
    CUR_ROW 0xFF00              ; ********........
    CUR_ROW 0xFE00              ; *******.........
    CUR_ROW 0xFE00              ; *******.........
    CUR_ROW 0xDE00              ; **.****.........
    CUR_ROW 0x1E00              ; ...****.........
    CUR_ROW 0x0000
    CUR_ROW 0x0000
    CUR_ROW 0x0000
    CUR_ROW 0x0000

%assign cur_row_i 0
cur_data:                       ; black: the arrow body itself
    CUR_ROW 0x8000              ; #...............
    CUR_ROW 0xC000              ; ##..............
    CUR_ROW 0xE000              ; ###.............
    CUR_ROW 0xF000              ; ####............
    CUR_ROW 0xF800              ; #####...........
    CUR_ROW 0xFC00              ; ######..........
    CUR_ROW 0xFE00              ; #######.........
    CUR_ROW 0xF800              ; #####...........
    CUR_ROW 0xD800              ; ##.##...........
    CUR_ROW 0x8C00              ; #...##..........
    CUR_ROW 0x0C00              ; ....##..........
    CUR_ROW 0x0000
    CUR_ROW 0x0000
    CUR_ROW 0x0000
    CUR_ROW 0x0000
    CUR_ROW 0x0000
cur_tabend:

; --- what the drawing code above claims about those two tables ---------------
%if cur_data - cur_and != CUR_TABSZ
  %error "mouse: cur_data must sit exactly one table past cur_and - cur_put_mono reads the black row at [si+CUR_TABSZ]"
%endif
%if cur_tabend - cur_data != CUR_TABSZ
  %error "mouse: a cursor table is not CUR_H rows"
%endif
%if cur_hi > CUR_GH
  %error "mouse: the arrow is taller than CUR_GH - raise it, or its bottom rows are neither drawn nor erased"
%endif
%if (cur_bits & ((1 << (16 - CUR_GW)) - 1)) != 0
  %error "mouse: the arrow is wider than CUR_GW - raise it, and give cur_pass and cur_put_mono the third byte back"
%endif

; -----------------------------------------------------------------------------
; module state (small - stays inline)
; -----------------------------------------------------------------------------
mouse_x     dw SCREEN_W/2       ; public: cursor position, 0..639
mouse_y     dw SCREEN_H/2       ; public: 0..479
mouse_btn   db 0                ; public: bit 0 = left, bit 1 = right

cur_level   db -1               ; refcount; < 0 = hidden (boot state)
cur_dirty   db 0                ; set when the ISR could not move the cursor
cur_drawn_x dw 0                ; where the cursor pixels actually are
cur_drawn_y dw 0                ; (valid only while cur_level >= 0)

mou_old_off dw 0                ; saved int 0x0C vector
mou_old_seg dw 0
mou_phase   db 0                ; packet state: 0 idle, 1 got b0, 2 got b1
mou_b0      db 0                ; packet byte 0: 1 LB RB Y7 Y6 X7 X6
mou_b1      db 0                ; packet byte 1: X low 6 bits
mou_evrec   times 8 db 0        ; scratch event record for evq_push (ISR only)
mou_seen    db 0                ; a complete packet has arrived this session;
                                ; set by the ISR, read by mou_hotplug, and
                                ; never cleared - proof the mouse exists
mou_hpst    db 0                ; hot-plug poller state: 0 waiting out the
                                ; interval, 1 DTR/RTS held low
mou_hpt     dw 0                ; tick stamp for whichever wait state 0/1 is in
mou_drain   db 0                ; ISR discards RX while set (armed by a
mou_dstamp  dw 0                ; hot-plug raise; expires MOU_DRAINT later)

section .bss
cur_save    resb CUR_SAVE_SZ    ; save-under: CUR_SPAN bytes x CUR_GH rows,
                                ; x four planes on VGA
cur_off     resw 1              ; cur_geom's answers, banked for cur_get_mono:
cur_rows    resb 1              ; the cell's top-left framebuffer byte, the
cur_b1ok    resb 1              ; rows of it on screen, and whether the DI+1
                                ; byte of each row is still inside the row
section .text
