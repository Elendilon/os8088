; =============================================================================
; os8088 - mouse.inc
;
; Serial Microsoft mouse on COM1 OR COM2 (SPEC.md 9.5) plus the arrow cursor
; with save-under. The ISR decodes the 3-byte Microsoft packet, keeps
; mouse_x/mouse_y/mouse_btn fresh, queues EVT_MDOWN/EVT_MUP on left-button
; changes and EVT_RDOWN on the right button's PRESS edge, and moves the
; cursor itself only when the gfx lock is free and the cursor is
; refcount-visible (SPEC 7); otherwise it just sets cur_dirty.
;
; Which port the mouse is on is not asked and not configured: both are probed
; for a UART, every one that answers is programmed, hooked and listened to at
; once, and the first port to deliver a complete packet WINS - the rest are
; retired on the UI task's next pass. On a machine with one serial card that
; degenerates to exactly the single-port code this replaced.
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

; UART register offsets from a port's base: +1 IER, +2 IIR, +3 LCR, +4 MCR,
; +5 LSR (and with LCR's DLAB set, +0 DLL and +1 DLM).
MOU_NPORT   equ 2               ; COM1 and COM2 (SPEC.md 9.5)
MOU_PEND    equ MOU_NPORT*2     ; ...as the end of a word-indexed table walk

MOU_LOCKN   equ 8               ; CLEAN packets in a row from ONE port before
                                ; it is declared the mouse's. Not 1: a modem's
                                ; 'O','K',CR,LF is a bit-6 header and two
                                ; bit-6-clear bytes, which IS a well-formed
                                ; Microsoft packet, and one of those would
                                ; have handed the mouse's slot to the modem.
                                ; Clean, because what really separates a mouse
                                ; from ASCII is that every byte is consumed -
                                ; see mou_claim and SPEC.md 9.5. Eight costs
                                ; a fifth of a second of the first movement
                                ; and nothing else: the packets before it are
                                ; decoded and acted on like any other

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
; The port table (SPEC.md 9.5)
;
; One row per candidate serial port, walked with BX as a WORD index (0, 2, ...
; MOU_PEND) so [bx+table] is a plain DS-relative fetch. [bx+mou_bases] is the
; only cell that changes at run time: mouse_init's probe ZEROES it where no
; UART answers, and every routine below reads that as "this port does not
; exist" - which is what keeps a one-serial-card machine on exactly the code
; path it had before COM2 was a possibility.
;
; The base decides the IRQ, because that is what the BIOS, DOS and every mouse
; driver ever written assume: 3F8 is IRQ4 and 2F8 is IRQ3. A card whose jumper
; disagrees with its base address is out of scope here, as it was before.
; -----------------------------------------------------------------------------
mou_bases   dw 0x3F8, 0x2F8     ; UART base per port; 0 = nothing answered
mou_ivecs   dw 0x30, 0x2C       ; ...its IVT offset: int 0x0C, int 0x0B
mou_masks   dw 0x10, 0x08       ; ...its bit in the master 8259's OCW1 (0x21)
mou_isrs    dw mou_isr, mou_isr3    ; ...and the stub that vector points at

; -----------------------------------------------------------------------------
; mou_pout - AL out to [port BX's base + AH]
;
; A port the probe rejected is a NO-OP, and that is the point: every caller
; below writes UART registers without a presence test of its own, and a
; machine with one serial card runs the identical sequence it always did with
; one dead call per step.
; ins:  BX = port row, AH = register offset, AL = value
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mou_pout:
    push cx
    push dx
    mov dx, [bx+mou_bases]
    or  dx, dx
    jz .out
    mov cl, ah
    xor ch, ch
    add dx, cx
    out dx, al
.out:
    pop dx
    pop cx
    ret

; -----------------------------------------------------------------------------
; mou_pall - mou_pout on every port. Both ports are reset, powered and drained
;            TOGETHER, because until a packet arrives there is no way to know
;            which one the mouse is on and no reason to prefer either.
; ins:  AH = register offset, AL = value
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mou_pall:
    push bx
    xor bx, bx
.port:
    call mou_pout
    add bx, 2
    cmp bx, MOU_PEND
    jb .port
    pop bx
    ret

; -----------------------------------------------------------------------------
; mou_uart - is there an 8250 at port BX's base? (SPEC.md 9.5)
;
; The DIVISOR LATCH is the test. With LCR's DLAB set, base+0 is an ordinary
; read/write register, so writing two distinct values and reading each back
; proves a latch is there to hold them; an unpopulated ISA address answers
; 0FFh to both. Every 8250 variant has it - unlike the scratch register at
; +7, which the original 8250 on a period serial card does not.
;
; Two values and not one, because a bus that happens to float to the first
; would otherwise pass. The probe leaves DLAB set and the divisor scrambled,
; which costs nothing: the caller programs both immediately afterwards.
;
; This is the ONLY reason an IRQ is ever unmasked here. Unmasking IRQ3 on a
; machine with no COM2 card would arm a line nothing drives.
; ins:  BX = port row
; outs: CF = 1 if a UART answered (all registers preserved)
; -----------------------------------------------------------------------------
mou_uart:
    push ax
    push dx
    mov dx, [bx+mou_bases]
    add dx, 3                   ; LCR: DLAB = 1, so base+0 is the latch
    mov al, 0x80
    out dx, al
    sub dx, 3
    mov al, 0xAA
    out dx, al
    jmp short $+2               ; I/O settling (kernel/clock.inc's idiom)
    in  al, dx
    cmp al, 0xAA
    jne .no
    mov al, 0x55
    out dx, al
    jmp short $+2
    in  al, dx
    cmp al, 0x55
    jne .no
    stc
    jmp short .out
.no:
    clc
.out:
    pop dx
    pop ax
    ret

; -----------------------------------------------------------------------------
; mouse_init - probe both ports, hook the vector of each one that answers,
;              program its UART (1200 baud 7N1, RX interrupt, DTR|RTS|OUT2 so
;              the mouse powers up), flush stale RX/LSR/IIR, unmask its IRQ.
; ins:  none
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mouse_init:
    push ax
    push bx
    push cx
    push dx
    push si
    push es

    ; --- which ports are actually there? (SPEC.md 9.5) -----------------------
    xor bx, bx
.probe:
    call mou_uart
    jc .next
    mov word [bx+mou_bases], 0  ; nothing answered: retire the row, and every
.next:                          ; routine below skips it from here on
    add bx, 2
    cmp bx, MOU_PEND
    jb .probe

    ; --- one port is not a contest -------------------------------------------
    ; With a single serial card there is nothing that could steal the mouse's
    ; slot and nothing to weigh against, so the first packet settles it and is
    ; acted on - which is this kernel's behaviour byte for byte before COM2
    ; was a possibility. Only a machine with two live ports pays MOU_LOCKN.
    xor cx, cx
    xor bx, bx
.count:
    cmp word [bx+mou_bases], 0
    je .cnext
    inc cx
.cnext:
    add bx, 2
    cmp bx, MOU_PEND
    jb .count
    mov al, 1
    cmp cx, 2
    jb .one
    mov al, MOU_LOCKN
.one:
    mov [mou_need], al

    ; --- save each present port's old vector, install ours -------------------
    xor ax, ax
    mov es, ax
    xor bx, bx
.hook:
    cmp word [bx+mou_bases], 0
    je .nohook
    mov si, [bx+mou_ivecs]
    pushf
    cli
    mov ax, [es:si]
    mov [bx+mou_old_off], ax
    mov ax, [es:si+2]
    mov [bx+mou_old_seg], ax
    mov ax, [bx+mou_isrs]
    mov [es:si], ax
    mov [es:si+2], cs
    popf
.nohook:
    add bx, 2
    cmp bx, MOU_PEND
    jb .hook

    ; --- UART: 1200 baud, 7 data bits, no parity, 1 stop ---------------------
    mov ax, 0x0382              ; LCR: DLAB=1 + 7N1 bits
    call mou_pall
    mov ax, 0x0060              ; divisor low = 96 (115200/96 = 1200)
    call mou_pall
    mov ax, 0x0100              ; divisor high = 0
    call mou_pall
    mov ax, 0x0302              ; LCR: DLAB=0, 7N1
    call mou_pall

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
    mov ax, 0x0408              ; MCR: OUT2 only - DTR and RTS low. OUT2
    call mou_pall               ; stays up throughout so the IRQ gate never
                                ; glitches the bus
    mov bx, [ticks]
.rstlow:
    mov ax, [ticks]
    sub ax, bx
    cmp ax, MOU_RSTLOW
    jb .rstlow
    mov ax, 0x040B              ; MCR: DTR|RTS|OUT2 - powers the mouse and
    call mou_pall               ; gates the IRQ onto the bus; this rising
                                ; edge is the mouse's reset

    ; --- drain the identify burst (IER still 0, the IRQs still masked) -------
    ; The DTR/RTS edge makes a real Microsoft mouse announce itself: 'M',
    ; maybe '3', maybe a whole PnP string - bytes with bit 6 set that the
    ; ISR's resync rule would misread as packet headers (phantom clicks,
    ; cursor jumps). Poll-and-discard for ~1 second before enabling RX
    ; interrupts; sched_init already runs, so [ticks] is live.
    mov cx, [ticks]
.settle:
    xor bx, bx
.sport:
    mov dx, [bx+mou_bases]
    or  dx, dx
    jz .snext
    add dx, 5                   ; LSR: RX data ready?
    in  al, dx
    test al, 0x01
    jz .snext
    sub dx, 5
    in  al, dx                  ; discard identify/PnP byte
.snext:
    add bx, 2
    cmp bx, MOU_PEND
    jb .sport
    mov ax, [ticks]
    sub ax, cx
    cmp ax, 19                  ; ~1s at 18.2Hz covers 'M3'+PnP at 1200 7N1
    jb .settle

    mov ax, 0x0101              ; IER: RX data available only
    call mou_pall
    call mou_newround           ; ...before anything is unmasked, or the store
                                ; could land on a packet already in progress

    ; --- flush whatever is stale, then unmask (in that order, per port) ------
    xor bx, bx
.flush:
    mov dx, [bx+mou_bases]
    or  dx, dx
    jz .fnext
    in  al, dx                  ; RX
    add dx, 5
    in  al, dx                  ; LSR
    sub dx, 3
    in  al, dx                  ; IIR
    mov cl, [bx+mou_masks]      ; ...and unmask this port's IRQ, which the
    not cl                      ; probe is what licenses: nothing is armed
    in  al, 0x21                ; on a line no card drives
    and al, cl
    out 0x21, al
.fnext:
    add bx, 2
    cmp bx, MOU_PEND
    jb .flush

    pop es
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; mou_claim - one more complete packet, on port BX (SPEC.md 9.5)
;
; [mou_need] of them IN A ROW on one port settles [mou_port] and sets
; [mou_seen]. The run is per port, like the decoder that feeds it, so the two
; ports race independently and whichever gets there first is the mouse.
;
; A run, and not the first packet, because a well-formed Microsoft packet is
; only "a byte with bit 6 set, then two without" - and a modem's 'O','K',CR,LF
; is exactly that. So is 'RING'+CRLF, and so is 'NO CARRIER'+CRLF: each of
; them completes ONE packet, which under a first-past-the-post rule handed the
; mouse's slot to the modem and masked the real mouse off for the session.
;
; But a COUNT alone is not enough either, and that is worth stating because it
; is what a first attempt got wrong: nothing decayed, so four result codes
; seconds apart accumulated to a run of four exactly as four mouse packets
; would. What actually separates a mouse from ASCII is not how many packets
; complete but that a mouse's bytes are ALL of them - they arrive in threes
; with nothing between - so the ISR breaks the run on either protocol
; violation: a bit-6 byte arriving mid-packet (a resync) and a bit-6-clear
; byte arriving between packets (a stray). Every modem string above dies on
; its second byte: 'RING' is R then I, both bit-6, and that is a resync.
; mou_hotplug's reset edge clears the run too, so nothing can be built up
; across one.
;
; The residual is a port carrying BINARY traffic in the seconds before the
; mouse is first moved - random bytes do satisfy the protocol occasionally,
; and MOU_LOCKN is what prices that: eight clean packets is 24 bytes that all
; had to fall right, against a mouse that emits them in a fifth of a second of
; motion. It is bounded anyway by mou_lockon masking the loser the moment the
; mouse is found.
;
; Nothing the OTHER port does can break this port's run, and that separation is
; the whole reason the decoders are per port. It was shared once, and a modem
; chattering on COM1 then reset the run of a mouse moving on COM2 - so the
; mouse never reached the threshold and never claimed its port at all, while
; the modem's own violations kept it from claiming one either. A device that
; cannot win must not be able to stop the one that should.
;
; ISR context, IF = 0.
; ins:  BX = the port row the packet arrived on
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mou_claim:
    push ax
    cmp byte [mou_seen], 0
    jne .out                    ; settled, and never revisited
    inc byte [bx+mou_run]
    mov al, [mou_need]          ; 1 where the probe found one port, MOU_LOCKN
    cmp byte [bx+mou_run], al   ; where it found two
    jb .out
    mov [mou_port], bl          ; settled. mou_hotplug's next pass retires
    mov byte [mou_seen], 1      ; every other port
.out:
    pop ax
    ret

; -----------------------------------------------------------------------------
; mou_newround - forget every port's part-built packet and part-built run
;
; A reset edge is a fresh contest and nothing may be carried across one. That
; is not tidiness: without it a modem accumulated a run out of result codes
; SECONDS apart - 'OK' then 'RING' then 'NO CARRIER', one packet each - which
; is indistinguishable, to a counter that never decays, from a mouse being
; moved.
; ins:  none
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mou_newround:
    mov word [mou_phase], 0
    mov word [mou_phase+2], 0
    mov word [mou_run], 0
    mov word [mou_run+2], 0
    ret

; -----------------------------------------------------------------------------
; mou_lockon - the mouse has spoken on port [mou_port]: retire the others
;
; IER = 0 so the UART stops interrupting, and its IRQ masked at the 8259. The
; base is deliberately LEFT in place, because mouse_unhook still owes that
; port its original vector back.
;
; A second serial device is somebody else's - a modem, a printer, a terminal -
; and once the mouse is found its bytes can only cost interrupts and, through
; the ISR's shared packet state, corrupt real packets.
; ins:  none (reads [mou_port])
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mou_lockon:
    push ax
    push bx
    push cx
    xor bx, bx
.port:
    cmp bl, [mou_port]
    je .next
    cmp word [bx+mou_bases], 0
    je .next
    mov ax, 0x0100              ; IER = 0
    call mou_pout
    mov cl, [bx+mou_masks]
    in  al, 0x21
    or  al, cl
    out 0x21, al
.next:
    add bx, 2
    cmp bx, MOU_PEND
    jb .port
    pop cx
    pop bx
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
; The cycle runs on EVERY present port at once (mou_pall), for the same
; reason mouse_init does: until a packet arrives there is nothing to say
; which port the mouse is on.
;
; The first complete packet sets [mou_seen] and this becomes one cmp per
; pass, forever. Until then the cost of being wrong is nil: with no serial
; card the port was never probed into existence, and with a healthy-but-idle
; mouse a cycle re-identifies it and the drain eats the burst. The one
; visible seam is that motion STARTED inside a drain window is eaten with it
; - up to half a second, self-healing on the next packet - which is the price
; of never mistaking a PnP string for a click.
; -----------------------------------------------------------------------------
mou_hotplug:
    cmp byte [mou_seen], 0
    jne .have                   ; the mouse exists: stand down - but see .have
    push ax
    push bx
    push cx
    push dx
    mov bx, [ticks]
    mov ax, bx
    sub ax, [mou_hpt]           ; wrap-safe: elapsed since the state's stamp
    cmp byte [mou_hpst], 1
    je .low
    cmp ax, MOU_REPOLL          ; state 0: waiting out the poll interval
    jb .done
    mov ax, 0x0408              ; drop DTR/RTS - power the mouse down. OUT2
    call mou_pall               ; stays up so the IRQ gate never glitches
    mov [mou_hpt], bx
    mov byte [mou_hpst], 1
    jmp short .done
.low:
    cmp ax, MOU_RSTLOW          ; state 1: held low long enough?
    jb .done
    mov ax, 0x040B              ; the rising edge a serial mouse resets on
    call mou_pall
    mov [mou_hpt], bx
    mov byte [mou_hpst], 0
    mov [mou_dstamp], bx        ; the burst comes through the ISR now: arm
    mov byte [mou_drain], 1     ; the discard window
    call mou_newround           ; ...and a fresh reset edge is a fresh contest
.done:
    pop dx
    pop cx
    pop bx
    pop ax
    ret

.have:                          ; proof can arrive at an awkward moment: a
    cmp byte [mou_hpst], 2      ; byte the UART latched before a drop can
    je .out                     ; complete a packet while DTR is LOW, and
    push ax                     ; standing down right there would leave the
    push bx                     ; mouse UNPOWERED forever - deader than the
    push cx                     ; bug this exists to fix. So put the power
    push dx                     ; back up on every port FIRST...
    mov ax, 0x040B
    call mou_pall
    call mou_lockon             ; ...and only then retire the ports the mouse
    mov byte [mou_hpst], 2      ; did not speak on. State 2 is terminal: this
    pop dx                      ; is two compares per UI pass from here on
    pop cx
    pop bx
    pop ax
.out:
    ret

; -----------------------------------------------------------------------------
; mouse_unhook - silence every UART we programmed (IER=0), mask its IRQ again,
;                restore its old vector. Used before reboot.
;
; This walks the ports the PROBE found, not the one the mouse turned out to be
; on, which is why mou_lockon leaves a retired port's base in place: a vector
; still pointing into KERNEL_SEG after the handoff is a vector nobody owns.
; ins:  none
; outs: none (all registers preserved)
; -----------------------------------------------------------------------------
mouse_unhook:
    push ax
    push bx
    push cx
    push si
    push es

    mov ax, 0x0100              ; IER = 0: no more UART interrupts
    call mou_pall

    xor ax, ax
    mov es, ax
    xor bx, bx
.port:
    cmp word [bx+mou_bases], 0
    je .next
    mov cl, [bx+mou_masks]      ; mask this port's IRQ...
    in  al, 0x21
    or  al, cl
    out 0x21, al
    mov si, [bx+mou_ivecs]      ; ...and put its vector back
    pushf
    cli
    mov ax, [bx+mou_old_off]
    mov [es:si], ax
    mov ax, [bx+mou_old_seg]
    mov [es:si+2], ax
    popf
.next:
    add bx, 2
    cmp bx, MOU_PEND
    jb .port

    pop es
    pop si
    pop cx
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; mou_isr / mou_isr3 - IRQ4 and IRQ3. One RX byte per interrupt. Microsoft
;           protocol: byte 0 has bit 6 set: 1 LB RB Y7 Y6 X7 X6; bytes 1/2
;           have bit 6 clear: low 6 bits of X then Y. Any bit-6 byte restarts
;           the packet (resync). Runs with IF=0 throughout; never sti (SPEC 7).
;
; The two stubs differ only in the port row they hand the body, and BX carries
; it because it is the one register that can be spent before DS is loaded and
; still index a table afterwards. Both vectors land on the MASTER 8259, so the
; EOI at the bottom is the same non-specific one it always was.
;
; BX then STAYS the port row all the way to .pkt, because every port decodes
; INDEPENDENTLY: phase, b0, b1 and the run are per-row arrays, not one shared
; set. Sharing them was tried and is wrong in both directions - a modem's byte
; resynced the MOUSE's half-built packet, and a modem's protocol violation
; reset the MOUSE's run, so a chattering modem on the other port could starve
; the real mouse out of ever being found (SPEC.md 9.5).
; -----------------------------------------------------------------------------
mou_isr:                        ; IRQ4 -> COM1, port row 0
    push bx
    xor bx, bx
    jmp short mou_isr_go
mou_isr3:                       ; IRQ3 -> COM2, port row 2
    push bx
    mov bx, 2
mou_isr_go:
    push ax
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

    mov dx, [bx+mou_bases]      ; DS-relative: the UART that interrupted
    in  al, dx                  ; ALWAYS read, whatever we mean to do with it:
                                ; the read is what clears this UART's
                                ; interrupt, and a byte left in the register
                                ; is an interrupt that comes straight back

    cmp byte [mou_seen], 0      ; is the mouse's port settled?
    je .drain
    cmp bl, [mou_port]          ; then every other port belongs to somebody
    jne .eoi                    ; else's device and is dropped unheard. This
                                ; also closes the window between the latch
                                ; below and mou_lockon masking the loser
.drain:
    cmp byte [mou_drain], 0     ; a hot-plug raise just happened (below):
    je .live                    ; this is the identify/PnP burst, and its
    mov dx, [ticks]             ; bit-6 bytes would resync as headers. DX is
    sub dx, [mou_dstamp]        ; free - the base has been read - and BX is
    cmp dx, MOU_DRAINT          ; NOT: it is the port row, and every array
    jb .eoi                     ; below is indexed on it
    mov byte [mou_drain], 0     ; window over: this byte is live
.live:
    test al, 0x40               ; bit 6 set -> first byte of a packet
    jz .cont
    cmp byte [bx+mou_phase], 0  ; ...but MID-PACKET it is a resync, and a real
    je .b0                      ; mouse never causes one: its bytes come in
    mov byte [bx+mou_run], 0    ; threes with nothing between them. Break the
.b0:                            ; run of clean packets (SPEC.md 9.5)
    mov [bx+mou_b0], al
    mov byte [bx+mou_phase], 1
    jmp .eoi

.cont:
    cmp byte [bx+mou_phase], 1
    jne .chk2
    mov [bx+mou_b1], al         ; second byte: X low 6 bits
    mov byte [bx+mou_phase], 2
    jmp .eoi

.chk2:
    cmp byte [bx+mou_phase], 2  ; anything else is a stray byte - drop it, and
    je .pkt                     ; break the run for the same reason: a byte
    mov byte [bx+mou_run], 0    ; with bit 6 clear arriving between packets is
    jmp .eoi                    ; a thing the protocol cannot produce
.pkt:
    mov byte [bx+mou_phase], 0  ; third byte: Y low 6 bits, packet complete
    call mou_claim              ; ...and a RUN of them is PROOF OF MOUSE: the
                                ; port is settled and the hot-plug poller
                                ; stands down for the session
    cmp byte [mou_seen], 0      ; still unsettled? then this packet COUNTS and
    je .eoi                     ; does nothing else. A device on its way to
                                ; losing the contest must not move the cursor
                                ; or queue a click while it loses - a modem's
                                ; 'no carrier' is lowercase, and bit 5 of a
                                ; lowercase letter is the LEFT BUTTON. The
                                ; packet that SETTLES the port is acted on, so
                                ; a one-port machine loses nothing at all
    mov dh, [bx+mou_b0]         ; stage the packet out of this port's slot: BX
    mov dl, [bx+mou_b1]         ; belongs to the decode from here on
    mov bl, al                  ; BL = Y low bits, decoded below

    ; --- dx = sign-extended {X7X6 from b0, X5..X0 from b1} -------------------
    mov al, dh
    and al, 0x03
    mov cl, 6
    shl al, cl                  ; X7X6 into bits 7:6
    mov ah, dl
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
    mov al, dh
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
    mov al, dh                  ; ...still the staged b0: nothing between here
    xor bl, bl                  ; and evq_push touches DX
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
    call cur_move               ; SPEC.md 7.1.2: erase-old and draw-new as one
    mov byte [cur_dirty], 0
    jmp .eoi

.dirty:
    mov byte [cur_dirty], 1     ; cursor_show catches up later

.eoi:
    mov al, 0x20                ; EOI - the BIOS handles neither IRQ4 nor
    out 0x20, al                ; IRQ3 for us, and both are on the master
    pop es
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop ax
    pop bx                      ; the stub pushed it FIRST (the port row)
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
    mov bp, [cur_sptr]          ; the live save buffer (SPEC.md 7.1.2)
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
    mov si, [cur_sptr]
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
; The DEFERRED hide (SPEC.md 7.1.4)
;
; gfx_lock used to erase the cursor unconditionally, so the pointer was absent
; for the whole of every lock hold - and a hold that repaints a window takes a
; visible amount of time on a 4.77MHz machine. With the mouse sitting still
; that reads as the cursor blinking off and on, once per refresh, forever.
;
; So gfx_lock only PROMISES the hide, in [cur_lazy], and something has to spend
; it before any pixel is written where the cursor is. Two things do:
;
;   cur_unlazy   take it now, unconditionally. Every path that can draw
;                ANYWHERE calls this: the unclipped branch of GFXCLIP, the
;                primitives SPEC.md 11.3 keeps off the clip list, the flush,
;                the save-under, a mode change and the fsx bracket.
;   cur_lazyck   take it only if the cursor could be reached. wm_clip_set
;                calls this, because once a region is armed the clipped
;                primitives are CONFINED to it - so a cursor outside the
;                window's frame is provably safe and the hide is not owed.
;
; The default is therefore "hide", and the win is the exception: a background
; painter that arms a region away from the pointer. That is the twelve
; wm_clip_set callers - the Task Manager's refresh, the menu bar clock,
; Fractal, Bounce, every package worker - and they get it without asking.
;
; [cur_lazy] is meaningful ONLY inside a lock hold: gfx_lock sets it, gfx_unlock
; clears it, and cursor_show is owed exactly when it was spent.
; -----------------------------------------------------------------------------
cur_unlazy:
    cmp byte [cur_lazy], 0      ; one-way within a hold, so the common case
    je .out                     ; after the first call is three instructions
    mov byte [cur_lazy], 0
    call cursor_hide
.out:
    ret

; cur_lazyck - spend the deferred hide unless SI's window provably cannot
;              reach the cursor. The test is the window's FRAME rect, not the
;              clip region: the region is the content minus what covers it, so
;              outside the frame is outside every fragment, and one rect test
;              is a great deal cheaper than sixteen.
; in:  SI = window ptr - wm_win_rect's own register, deliberately, so this
;      cannot be called with the window in the wrong one
; out: nothing (all registers preserved)
cur_lazyck:
    cmp byte [cur_lazy], 0
    je .out
    push ax
    push bx
    push cx
    push dx
    push si
    call wm_win_rect            ; AX/BX/CX/DX = the frame, drop shadow included
    mov si, [cur_drawn_x]       ; separated on x?  cell is [x, x+CUR_GW-1]
    cmp si, cx
    jg .clear                   ; ...wholly right of the frame
    add si, CUR_GW-1
    cmp si, ax
    jl .clear                   ; ...wholly left of it
    mov si, [cur_drawn_y]       ; ...and the same on y
    cmp si, dx
    jg .clear
    add si, CUR_GH-1
    cmp si, bx
    jl .clear
    pop si                      ; they overlap: the hide is owed after all
    pop dx
    pop cx
    pop bx
    pop ax
    jmp short cur_unlazy
.clear:
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
.out:
    ret

; cur_lazyend - gfx_unlock, when the hide was never spent. The cursor is still
;               on screen and cursor_show must NOT run (it would bank the
;               drawn arrow as background), but the ISR refused to move it all
;               through the hold, so any motion is owed here.
cur_lazyend:
    push ax
    push bx
    pushf
    cli
    mov byte [cur_lazy], 0
    cmp byte [cur_level], 0
    jl .out                     ; hidden by refcount: nothing is on screen
    mov ax, [mouse_x]
    mov bx, [mouse_y]
    cmp ax, [cur_drawn_x]
    jne .move
    cmp bx, [cur_drawn_y]
    je .out
.move:
    call cur_move
    mov byte [cur_dirty], 0
.out:
    popf
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; cur_move - move the cursor to (AX, BX), writing every byte EXACTLY ONCE
;
; SPEC.md 7.1.2. A move used to be `cur_get` then `cur_put`: two walks, and
; every framebuffer byte where the old and new cells overlap was written twice
; - once with the background, once with the arrow. The glass can catch the
; value in between, and on a real Hercules that reads as the whole arrow
; washing out to white while the mouse moves (docs/FIELD-NOTES.md 6). It is
; ~6.5% of every frame, on every mouse packet.
;
; The fix is not a union walk and does NOT need a gate on how far the cursor
; moved: the two passes still walk the OLD cell and the NEW cell exactly as
; before, and each byte is written once because
;
;   pass 1 SKIPS the bytes pass 2 is going to write, and
;   pass 2 takes their background from the SAVE BUFFER rather than the screen.
;
; Cells that do not overlap degenerate to the old behaviour on their own - the
; skip never fires and the background always comes from the screen - so there
; is nothing to bound and nothing to get wrong at the extremes.
;
; Which bytes those are is decided ONCE, before either walk, from the byte-
; column difference d = newcol - oldcol (mv_p1s0/1 and mv_p2s0/1), because it
; is the same answer for every row.
;
; in:       AX = new x, BX = new y; [cur_drawn_x/y] and the banked geometry
;           still describe where the cursor IS. IF = 0 (ISR, or the gfx lock).
; clobbers: ax, bx, cx, dx, si, di, bp, es
; -----------------------------------------------------------------------------
cur_move:
    cmp byte [vid_mono], 0
    jne cur_move_mono
    push ax                     ; planar: the save is four planes through Read
    push bx                     ; Map Select and cannot take a background from
    call cur_restoreu           ; a buffer, so it stays erase-then-draw
    pop bx
    pop ax
    mov [cur_drawn_x], ax
    mov [cur_drawn_y], bx
    call cur_saveu
    jmp cur_draw

cur_move_mono:
    push ax
    push bx
    ; --- bank the OLD geometry, which cur_geom is about to overwrite ---------
    mov ax, [cur_drawn_y]
    mov [mv_oy], ax
    mov ax, [cur_drawn_x]
    mov cl, 3
    shr ax, cl
    mov dx, ax                  ; DX = the old byte column
    mov al, [cur_rows]
    mov [mv_orows], al
    mov al, [cur_b1ok]
    mov [mv_ob1ok], al
    mov ax, [cur_off]
    mov [mv_ooff], ax
    mov ax, [cur_sptr]          ; the buffer holding the OLD background...
    mov [mv_osave], ax
    mov bx, cur_save            ; ...and the other one takes the new, so pass 2
    cmp ax, bx                  ; can read one while it fills the other
    jne .flip
    mov bx, cur_savex
.flip:
    mov [mv_nsave], bx
    mov [cur_sptr], bx
    pop bx
    pop ax
    mov [cur_drawn_x], ax
    mov [cur_drawn_y], bx
    mov cl, 3                   ; AX = new x still; d = newcol - oldcol
    shr ax, cl
    sub ax, dx
    mov [mv_d], ax
    call cur_geom               ; DI = new offset, CL = shift, [cur_rows],
                                ; [cur_b1ok], [cur_off] - all NEW now
    call cur_mvcols             ; ...and the four per-column answers

    ; --- pass 1: the old background back, except where pass 2 will draw ------
    mov ch, [mv_orows]
    or ch, ch
    jz .p2
    mov ax, [vid_seg]
    mov es, ax
    mov di, [mv_ooff]
    mov si, [mv_osave]
    mov bx, [mv_oy]
.p1row:
    mov ax, bx                  ; is this row one pass 2 will draw into?
    sub ax, [cur_drawn_y]
    mov dl, [cur_rows]
    xor dh, dh
    cmp ax, dx
    mov dl, 0                   ; DL = 1 = "pass 2 covers this row"
    jae .p1w                    ; unsigned: a row above the new cell is huge
    mov dl, 1
.p1w:
    lodsw                       ; AL/AH = the two saved bytes; the stride is
                                ; CUR_SPAN whatever the clip said
    or dl, dl
    jnz .p1s0                   ; row covered: consult the column answers
    mov [es:di], al
    cmp byte [mv_ob1ok], 0
    je .p1next
    mov [es:di+1], ah
    jmp short .p1next
.p1s0:
    cmp byte [mv_p1s0], 0
    jne .p1c1                   ; pass 2 writes this column: leave it alone
    mov [es:di], al
.p1c1:
    cmp byte [mv_ob1ok], 0
    je .p1next
    cmp byte [mv_p1s1], 0
    jne .p1next
    mov [es:di+1], ah
.p1next:
    inc bx
    add di, [cs:vid_rowadd]     ; gfx_nextrow, inlined (SPEC.md 39.3)
    test di, [cs:vid_wrapbit]
    jz .p1nw
    add di, [cs:vid_wrapfix]
.p1nw:
    dec ch
    jnz .p1row

    ; --- pass 2: save and draw the new cell, background from either place ----
.p2:
    mov ch, [cur_rows]
    or ch, ch
    jz .out
    mov ax, [vid_seg]
    mov es, ax
    mov di, [cur_off]
    mov si, cur_and
    mov bp, [mv_nsave]
.p2row:
    call cur_mvrow              ; [mv_orp] = this row's slot in the OLD save,
                                ; or 0 if the old cell does not reach it
    mov ax, [si]                ; the white row...
    mov dx, [si+CUR_TABSZ]      ; ...and the black one, one table along
    add si, 2
    shr ax, cl
    shr dx, cl
    not dx                      ; DH:DL = the black body as an AND mask

    push ax                     ; --- byte 0 ---
    mov al, [mv_p2s0]
    call cur_mvbg               ; BL = the background, from the buffer or the
    pop ax                      ; screen, whichever this byte's answer says
    mov [ds:bp], bl
    or  bl, ah
    and bl, dh
    mov [es:di], bl

    cmp byte [cur_b1ok], 0      ; --- byte 1 ---
    je .p2adv
    push ax
    mov al, [mv_p2s1]
    inc di
    call cur_mvbg
    dec di
    pop ax
    mov [ds:bp+1], bl
    or  bl, al
    and bl, dl
    mov [es:di+1], bl
.p2adv:
    add bp, CUR_SPAN
    inc word [mv_prow]
    add di, [cs:vid_rowadd]
    test di, [cs:vid_wrapbit]
    jz .p2nw
    add di, [cs:vid_wrapfix]
.p2nw:
    dec ch
    jnz .p2row
.out:
    ret

; cur_mvcols - the four per-column answers, from d = newcol - oldcol
;
; mv_p1s0/1: pass 1 must SKIP old column 0/1, because pass 2 writes it.
;            Old column j is a new column when j-d is 0 or 1, and column 1 of
;            the new cell only exists if the new cell's own clip kept it.
; mv_p2s0/1: pass 2 takes new column 0/1's background from the old save at
;            this offset - d+j, when that is 0 or 1 and the OLD clip kept it -
;            or 0FFh, meaning "read the screen".
; clobbers: ax, bx, flags
cur_mvcols:
    xor bx, bx                  ; --- pass 2, column 0 and 1 -----------------
.p2:
    mov ax, [mv_d]
    add ax, bx                  ; AX = d + j
    mov byte [bx + mv_p2s0], 0xFF
    or ax, ax
    jz .p2take                  ; offset 0: always saved
    cmp ax, 1
    jne .p2next
    cmp byte [mv_ob1ok], 0      ; offset 1 only exists if the OLD clip kept it
    je .p2next
.p2take:
    mov [bx + mv_p2s0], al
.p2next:
    inc bx
    cmp bx, 2
    jb .p2
    xor bx, bx                  ; --- pass 1, column 0 and 1 -----------------
.p1:
    mov ax, bx
    sub ax, [mv_d]              ; AX = j - d
    mov byte [bx + mv_p1s0], 0
    or ax, ax
    jz .p1skip                  ; new column 0: pass 2 always writes it
    cmp ax, 1
    jne .p1next
    cmp byte [cur_b1ok], 0      ; new column 1 only if the NEW clip kept it
    je .p1next
.p1skip:
    mov byte [bx + mv_p1s0], 1
.p1next:
    inc bx
    cmp bx, 2
    jb .p1
    mov word [mv_prow], 0
    ret

; cur_mvrow - does the OLD cell reach the new cell's row [mv_prow]?
; out: [mv_orp] = a pointer into the old save buffer, or 0
; clobbers: ax, bx, flags
cur_mvrow:
    push dx
    mov ax, [cur_drawn_y]
    add ax, [mv_prow]
    sub ax, [mv_oy]             ; AX = the row's index in the OLD cell
    mov word [mv_orp], 0
    mov bl, [mv_orows]
    xor bh, bh
    cmp ax, bx
    jae .out                    ; unsigned: a row above it is a huge number
    add ax, ax                  ; CUR_SPAN bytes a row
    add ax, [mv_osave]
    mov [mv_orp], ax
.out:
    pop dx
    ret

; cur_mvbg - one byte's background: the old save buffer if this column's
;            answer names an offset AND the old cell reaches this row,
;            otherwise the screen.
; in:  AL = the column answer (0, 1 or 0FFh), ES:DI = the screen byte
; out: BL = the background byte
; clobbers: ax, bx, flags
cur_mvbg:
    cmp al, 0xFF
    je .screen
    mov bx, [mv_orp]
    or bx, bx
    jz .screen
    xor ah, ah
    add bx, ax
    mov bl, [bx]
    ret
.screen:
    mov bl, [es:di]
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
    mov ch, [cur_rows]          ; [cur_rows]/[cur_b1ok] = how much is on screen
    or ch, ch
    jz .done                    ; wholly off the bottom
    mov ax, [vid_seg]
    mov es, ax
    mov si, cur_and
    mov dx, VGA_GC              ; the INDEX port: index and data go as one word
.row:
    mov ax, [si]                ; AX = white: every pixel the arrow touches...
    mov bx, [si+CUR_TABSZ]      ; ...and BX = the black body inside it
    add si, 2
    not bx
    and bx, ax                  ; BX = white & ~black = the pixels that go WHITE
    shr ax, cl                  ; AX = the Bit Mask, shifted into place
    shr bx, cl                  ; BX = the plane data, likewise
    mov bp, ax                  ; bank it: AX is the port register

    or ah, ah                   ; --- byte 0 ---
    jz .b1
    mov al, 8                   ; GC8 = Bit Mask = this byte's arrow bits
    out dx, ax
    mov al, [es:di]             ; the READ is the latch load; its value is
    mov al, bh                  ; discarded, and the byte written in its place
    mov [es:di], al             ; carries BOTH colours at once
.b1:
    mov ax, bp
    or al, al                   ; --- byte 1 ---
    jz .next
    cmp byte [cur_b1ok], 0      ; clipped off the right screen edge?
    je .next
    mov ah, al
    mov al, 8
    out dx, ax
    mov al, [es:di+1]           ; latch load, as above
    mov al, bl
    mov [es:di+1], al
.next:
    add di, ROW_BYTES
    dec ch
    jnz .row
    mov ax, 0xFF08              ; GC8 back to all bits (SPEC.md 1 rule 7)
    out dx, ax
.done:
    ret

; -----------------------------------------------------------------------------
; cursor bitmap - classic Mac arrow, hot spot (0,0), black body 11 rows tall
; with a 1px white outline. cur_and is the white mask (outline + fill),
; cur_data the black body inside it. MSB = leftmost pixel.
;
; ONE list, expanded TWICE. Both tables come out of CUR_ARROW, which carries
; each row's white and black words side by side and emits whichever the pass
; wants - because the invariant the drawing code now depends on is a statement
; about the PAIR, and a pair split across two tables thirty lines apart is a
; pair nobody checks. Three facts are accumulated and asserted below: the
; widest bit set anywhere (CUR_GW), the last row that sets one (CUR_GH), and
; that every black bit is also a white one. All three fail silently otherwise
; - a wider arrow loses its right-hand column on the two mono adapters, a
; taller one leaves its bottom rows on screen for the rest of the session, and
; an escaped black bit simply does not get drawn on VGA - and none of them
; shows up anywhere but on the glass.
;
; cur_bits and cur_hi are accumulated from the WHITE rows alone, which the
; subset assertion is what licenses: a black bit can neither be wider nor
; lower than the white bit that must accompany it.
; -----------------------------------------------------------------------------
%assign cur_bits 0              ; every bit any WHITE row sets, ORed together
%assign cur_hi   0              ; ...and one past the last one that sets any
%macro CUR_ROW 2                ; white row, black row
  %if cur_tab == 0
    dw %1
    %assign cur_bits cur_bits | (%1)
    %if (%1) != 0
      %if cur_row_i + 1 > cur_hi
        %assign cur_hi cur_row_i + 1
      %endif
    %endif
    ; ...and the third fact, which only the PLANAR draw needs: every black bit
    ; must also be a white one. cur_draw writes both colours in ONE masked
    ; store now - Bit Mask = the white row, plane data = white & ~black - so a
    ; black pixel outside its white row would be masked off and simply not
    ; drawn, where the old two-pass draw painted it in a pass of its own.
    ; It is checked HERE because here is the only place both rows are in view.
    %if ((%2) & ~(%1)) & 0xFFFF
      %error "mouse: a black cursor row escapes its white row - cur_draw's fused write would drop those pixels"
    %endif
  %else
    dw %2
  %endif
  %assign cur_row_i cur_row_i + 1
%endmacro

; white (outline + fill)        black (the body)
%macro CUR_ARROW 0
    CUR_ROW 0xE000,             0x8000      ; ***.....  #.......
    CUR_ROW 0xF000,             0xC000      ; ****....  ##......
    CUR_ROW 0xF800,             0xE000      ; *****...  ###.....
    CUR_ROW 0xFC00,             0xF000      ; ******..  ####....
    CUR_ROW 0xFE00,             0xF800      ; *******.  #####...
    CUR_ROW 0xFF00,             0xFC00      ; ********  ######..
    CUR_ROW 0xFF00,             0xFE00      ; ********  #######.
    CUR_ROW 0xFF00,             0xF800      ; ********  #####...
    CUR_ROW 0xFE00,             0xD800      ; *******.  ##.##...
    CUR_ROW 0xFE00,             0x8C00      ; *******.  #...##..
    CUR_ROW 0xDE00,             0x0C00      ; **.****.  ....##..
    CUR_ROW 0x1E00,             0x0000      ; ...****.  ........
    CUR_ROW 0x0000,             0x0000
    CUR_ROW 0x0000,             0x0000
    CUR_ROW 0x0000,             0x0000
    CUR_ROW 0x0000,             0x0000
%endmacro

%assign cur_tab   0
%assign cur_row_i 0
cur_and:                        ; white: the body dilated by 1px, right and down
    CUR_ARROW

%assign cur_tab   1
%assign cur_row_i 0
cur_data:                       ; black: the arrow body itself
    CUR_ARROW

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

cur_sptr    dw cur_save         ; -> whichever save buffer is live. In .text
                                ; with a REAL initialiser, not .bss: .bss
                                ; arrives zeroed (kernel.asm - NASM pads the
                                ; gap to OVL_START), and 0 here is a pointer
                                ; at the API jump table
cur_level   db -1               ; refcount; < 0 = hidden (boot state)
cur_dirty   db 0                ; set when the ISR could not move the cursor
cur_drawn_x dw 0                ; where the cursor pixels actually are
cur_drawn_y dw 0                ; (valid only while cur_level >= 0)

mou_old_off dw 0, 0             ; the vectors we displaced, per port row
mou_old_seg dw 0, 0
; The decoder, PER PORT ROW (stride 2, so [bx+...] indexes it directly - the
; odd byte of each pair is padding and costs 4 bytes in all). The two ports
; decode independently, which is what stops either one corrupting the other's
; packets or resetting the other's run (SPEC.md 9.5).
mou_phase   db 0,0,0,0          ; packet state: 0 idle, 1 got b0, 2 got b1
mou_b0      db 0,0,0,0          ; packet byte 0: 1 LB RB Y7 Y6 X7 X6
mou_b1      db 0,0,0,0          ; packet byte 1: X low 6 bits
mou_run     db 0,0,0,0          ; clean packets in a row on this port

mou_port    db 0                ; the mouse's row, settled by [mou_need] clean
                                ; packets and never moved again (SPEC.md 9.5).
                                ; A row index (0, 2), not a COM number
mou_need    db 1                ; the run a port must manage to be believed:
                                ; 1 where the probe found one port, MOU_LOCKN
                                ; where it found two
mou_evrec   times 8 db 0        ; scratch event record for evq_push (ISR only)
mou_seen    db 0                ; a complete packet has arrived this session;
                                ; set by the ISR, read by mou_hotplug, and
                                ; never cleared - proof the mouse exists
mou_hpst    db 0                ; hot-plug poller state: 0 waiting out the
                                ; interval, 1 DTR/RTS held low, 2 stood down
                                ; for good (the ports lost their contest)
mou_hpt     dw 0                ; tick stamp for whichever wait state 0/1 is in
mou_drain   db 0                ; ISR discards RX while set (armed by a
mou_dstamp  dw 0                ; hot-plug raise; expires MOU_DRAINT later)

section .bss
cur_save    resb CUR_SAVE_SZ    ; save-under: CUR_SPAN bytes x CUR_GH rows,
                                ; x four planes on VGA
cur_savex   resb CUR_SPAN * CUR_GH  ; ...and its twin. A MOVE reads one while
                                ; it fills the other (SPEC.md 7.1.2); 24 bytes,
                                ; and the pointer swap means nothing is copied
cur_lazy    resb 1              ; gfx_lock deferred the hide (SPEC.md 7.1.4):
                                ; the arrow is still on screen this hold
cur_off     resw 1              ; cur_geom's answers, banked for cur_get_mono:
cur_rows    resb 1              ; the cell's top-left framebuffer byte, the
cur_b1ok    resb 1              ; rows of it on screen, and whether the DI+1
                                ; byte of each row is still inside the row

mv_oy       resw 1              ; cur_move's banked OLD geometry: top row,
mv_ooff     resw 1              ; framebuffer offset, rows, right-byte clip
mv_orows    resb 1
mv_ob1ok    resb 1
mv_osave    resw 1              ; -> the buffer holding the old background...
mv_nsave    resw 1              ; ...and the one taking the new
mv_d        resw 1              ; newcol - oldcol, signed: the ONE number the
                                ; four column answers below come out of
mv_p1s0     resb 1              ; pass 1 skips this old column (pass 2 has it)
mv_p1s1     resb 1
mv_p2s0     resb 1              ; pass 2's background offset in the old save,
mv_p2s1     resb 1              ; or 0FFh for "read the screen"
mv_prow     resw 1              ; the new cell's row, as pass 2 walks it
mv_orp      resw 1              ; -> that row in the old save, or 0
section .text
