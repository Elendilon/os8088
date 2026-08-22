; =============================================================================
; os8088 - ps2.inc
;
; SPEC.md 9.10 - the second mouse backend: an 8042 auxiliary device on IRQ12,
; decoded into SPEC.md 9.9's mou_report and no further. Everything about a
; POINTER - the clamp, the button edges, the events, the cursor move - is
; mouse.inc's and is not repeated here; this file is a packet decoder and an
; 8042 init, and that is the whole of it.
;
; kern_big's ALONE, and shipped there. The 8088 is this project's primary
; target and has no auxiliary device to put a mouse on - an IBM PC/XT has an
; 8255 PPI, not an 8042 - but big also runs on the 286 and 386, and by the
; time those were the machine on the desk the PS/2 port was the standard one.
; So big carries it and pays for it on the XT too, which is what the
; twenty-ninth budget move bought (kernel.asm, docs/KERNEL-MEMORY.md).
;
; kern_small does NOT, and that is a decision rather than a size accident:
; small is the 128KB build and is shrinking to fit those machines, and no
; 128KB machine needs a PS/2 mouse. Every byte below is inside %ifdef
; KERN_BIG.
; =============================================================================
%ifdef KERN_BIG

PS2_DATA    equ 0x60            ; the 8042's data register...
PS2_STAT    equ 0x64            ; ...and its status/command register
PS2_OBF     equ 0x01            ; status: a byte is waiting to be read
PS2_IBF     equ 0x02            ; status: the controller has not taken ours yet
PS2_AUX     equ 0x20            ; status: the waiting byte is the AUX device's
                                ; and NOT the keyboard's. Reading 0x60 without
                                ; testing this is the whole of why the first
                                ; version of this file hooked nothing (9.10.1)
PS2_ACK     equ 0xFA            ; what an aux device answers a command with

; -----------------------------------------------------------------------------
; ps2_wait_in / ps2_wait_out - poll the status register, BOUNDED
;
; The bound is the point. A machine with an 8042 that has no mouse on it, or
; a controller that NAKs the aux port, must fall through to SPEC.md 9.4's
; serial probe rather than spin - this runs from mouse_init, before the
; desktop, with nothing to notice a hang.
; outs: CF = 1 timed out; AL clobbered on the wait_out path only
; -----------------------------------------------------------------------------
ps2_wait_in:
    push ax
    push cx
    xor cx, cx                  ; 65,536 IN instructions - ~0.5s on the
.w:                             ; slowest machine that has an 8042 at all
    in  al, PS2_STAT
    test al, PS2_IBF
    jz .ok
    loop .w
    stc
    jmp short .out
.ok:
    clc
.out:
    pop cx
    pop ax
    ret

ps2_wait_out:
    push cx
    xor cx, cx
.w:
    in  al, PS2_STAT
    test al, PS2_OBF
    jnz .ok
    loop .w
    stc
    jmp short .out
.ok:
    clc
.out:
    pop cx
    ret

; -----------------------------------------------------------------------------
; ps2_wait_aux - wait for a byte THE AUX DEVICE sent, discarding the
;                keyboard's on the way
;
; SPEC.md 9.10.1. One data register serves both devices and only status bit 5
; says which one filled it, so a plain "wait for OBF" reads whatever is there
; - and what is there, on a BIOS that leaves the keyboard enabled, is a
; scancode. A keyboard byte is also DROPPED rather than waited out: left in
; the buffer it blocks the ACK behind it and the wait times out with the
; mouse working perfectly.
; outs: CF = 1 timed out; the byte is left IN the register for the caller
; -----------------------------------------------------------------------------
ps2_wait_aux:
    push cx
    xor cx, cx
.w:
    in  al, PS2_STAT
    test al, PS2_OBF
    jz .next
    test al, PS2_AUX
    jnz .ok
    in  al, PS2_DATA            ; the keyboard's, and in our way
.next:
    loop .w
    stc
    jmp short .out
.ok:
    clc
.out:
    pop cx
    ret

; -----------------------------------------------------------------------------
; ps2_drain - empty the output buffer before any of this starts
;
; Bounded by a count and not by OBF alone: a controller that answers every
; read with a byte would spin here forever.
; -----------------------------------------------------------------------------
ps2_drain:
    push ax
    push cx
    mov cx, 16
.d:
    in  al, PS2_STAT
    test al, PS2_OBF
    jz .done
    in  al, PS2_DATA
    loop .d
.done:
    pop cx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ps2_auxcmd - AL to the aux device, and read back its ACK
; ins:  AL = the command byte
; outs: CF = 1 if it timed out or answered anything but 0xFA
; -----------------------------------------------------------------------------
ps2_auxcmd:
    push ax
    call ps2_wait_in
    jc .bad
    mov al, 0xD4                ; "the next byte written to 0x60 is the aux
    out PS2_STAT, al            ; device's, not the keyboard's"
    call ps2_wait_in
    jc .bad
    pop ax
    push ax
    out PS2_DATA, al
    call ps2_wait_aux           ; ...and NOT ps2_wait_out (SPEC.md 9.10.1)
    jc .bad
    in  al, PS2_DATA
    cmp al, PS2_ACK
    jne .bad
    pop ax
    clc
    ret
.bad:
    pop ax
    stc
    ret

; -----------------------------------------------------------------------------
; ps2_init - find an aux device, hook IRQ12, and start it reporting
; outs: CF = 1 having hooked NOTHING - no vector, no mask bit, no port left
;       in a state the serial probe would trip over
; -----------------------------------------------------------------------------
ps2_init:
    push ax
    push bx
    push es
    cmp byte [cpu_tier], CPU_8086   ; an XT has an 8255 PPI: 0x64 is not a
    je .none                        ; status register there, it is nothing

    call ps2_drain              ; whatever the BIOS left behind
    call ps2_wait_in
    jc .none
    mov al, 0xA8                ; enable the auxiliary port
    out PS2_STAT, al

    ; --- is anything ON that port? ------------------------------------------
    ; 0xF5 - DISABLE reporting - is the probe, and it is 0xF5 rather than the
    ; 0xF4 that would seem the natural one for an ordering reason that cost
    ; this file its first version (SPEC.md 9.10.1): a device told to report
    ; starts streaming AT ONCE, and its packets then land in the same data
    ; register the command-byte read below is waiting on. The stream is
    ; started LAST, after the vector is in and the masks are open.
    mov al, 0xF5
    call ps2_auxcmd             ; NO ACK IS THE DETECTION: an empty aux port
    jc .none                    ; answers nothing and the serial probe stands

    ; --- hook int 74h BEFORE the first interrupt can possibly arrive --------
    xor ax, ax
    mov es, ax
    pushf
    cli
    mov word [es:0x74*4], ps2_isr
    mov [es:0x74*4+2], cs
    popf

    ; --- everything from here to the stream runs at IF = 0 -------------------
    ; The moment the command byte below enables IRQ12, EVERY aux byte is
    ; delivered by interrupt - and a command ACK is an aux byte. With IF on,
    ; ps2_isr takes 0xF4's ACK out of the data register before ps2_auxcmd's
    ; poll can see it, auxcmd times out, and init fails having already hooked
    ; the vector and opened the masks. SPEC.md 9.10.1: the poll and the ISR
    ; are two readers of one register, and the fence between them is IF.
    pushf
    cli

    ; --- the command byte: aux IRQ on, aux clock ungated --------------------
    call ps2_wait_in
    jc .nonep                   ; ...and the pushf above still has to come off
    mov al, 0x20
    out PS2_STAT, al
    call ps2_wait_out           ; the CONTROLLER's answer, so wait_out and not
    jc .nonep                   ; wait_aux: this byte has status bit 5 CLEAR
    in  al, PS2_DATA
    or  al, 0x02                ; bit 1: raise IRQ12 on an aux byte
    and al, 0xDF                ; bit 5: clear the aux DISABLE
    mov bl, al
    call ps2_wait_in
    jc .nonep
    mov al, 0x60                ; ...and write it back
    out PS2_STAT, al
    call ps2_wait_in
    jc .nonep
    mov al, bl
    out PS2_DATA, al

    ; --- unmask IRQ12 AND the cascade ---------------------------------------
    ; IRQ12 is the first interrupt this kernel takes on the SLAVE 8259, and
    ; the slave reaches the CPU only through IRQ2 on the master. Unmasking
    ; bit 4 of 0xA1 and stopping is a mouse that never once interrupts.
    in  al, 0xA1
    and al, 0xEF                ; slave bit 4 = IRQ12
    out 0xA1, al
    in  al, 0x21
    and al, 0xFB                ; master bit 2 = the slave's cascade
    out 0x21, al

    mov al, 0xF4                ; ...and only NOW start it reporting
    call ps2_auxcmd
    sbb bh, bh                  ; BANK the carry: popf is about to overwrite
    popf                        ; it with the flags from before the cli
    or  bh, bh
    jnz .none
    mov byte [ps2_live], 1
    clc
    jmp short .out
.nonep:
    popf                        ; the cli window's exit - the flags it pushed
.none:                          ; come off before the carry below is set
    stc
.out:
    pop es
    pop bx
    pop ax
    ret

; -----------------------------------------------------------------------------
; ps2_isr - IRQ12: one byte of a 3-byte PS/2 packet
;
; byte 0: YV XV YS XS 1 M R L    byte 1: dx     byte 2: dy (UP positive)
; -----------------------------------------------------------------------------
ps2_isr:
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
    ; --- is this interrupt OURS, and is there a byte at all? ----------------
    ; Both halves are needed and neither is theoretical. Enabling the aux IRQ
    ; leaves ONE edge latched from the ACK that ps2_init already polled away
    ; (SPEC.md 9.10.1), so the first interrupt after boot arrives with an
    ; EMPTY buffer - and a bare `in al, 0x60` there reads a stale byte whose
    ; bit 3 may well be set, which the decode below takes for a packet header
    ; and which costs the next real packet its sync. That is one lost pointer
    ; movement per boot, and it is exactly the defect an emulator shows you
    ; and a user never reports.
    in  al, PS2_STAT
    and al, PS2_OBF|PS2_AUX
    cmp al, PS2_OBF|PS2_AUX
    jne .eoi                    ; nothing, or the keyboard's - and a keyboard
                                ; byte is LEFT for int 09h rather than eaten
    in  al, PS2_DATA

    mov bl, [ps2_phase]
    or  bl, bl
    jnz .p1
    test al, 0x08               ; byte 0 carries a hard 1 in bit 3, and that
    jz .eoi                     ; is the only resync this protocol offers
    mov [ps2_b0], al
    inc byte [ps2_phase]
    jmp short .eoi
.p1:
    cmp bl, 1
    jne .p2
    mov [ps2_b1], al
    inc byte [ps2_phase]
    jmp short .eoi
.p2:
    mov byte [ps2_phase], 0
    mov dh, [ps2_b0]
    test dh, 0xC0               ; either overflow bit set: the deltas are
    jnz .nomove                 ; meaningless, but the BUTTONS are not

    mov bl, [ps2_b1]            ; dx, sign-extended out of byte 0's bit 4
    xor bh, bh
    test dh, 0x10
    jz .xp
    dec bh
.xp:
    mov si, bx

    mov bl, al                  ; dy, the same way out of bit 5...
    xor bh, bh
    test dh, 0x20
    jz .yp
    dec bh
.yp:
    neg bx                      ; ...and NEGATED: PS/2 counts up positive and
    jmp short .rep              ; mou_report counts in screen order (SPEC 9.9)
.nomove:
    xor si, si
    xor bx, bx
.rep:
    mov byte [mou_ptr], 1       ; A POINTING DEVICE HAS PROVEN ITSELF (SPEC.md
                                ; 9.6.6), which is what switches the keyboard
                                ; mouse OFF. One store rather than a test and
                                ; a branch: it is the same byte every packet
                                ; and the ISR has no spare register here.
                                ; NOT [mou_seen] - that byte means "the SERIAL
                                ; contest is settled and [mou_port] names the
                                ; winner", and setting it from here would mute
                                ; a serial mouse on COM2 (mou_byte drops every
                                ; port but [mou_port] once it is set)
    mov dl, dh                  ; buttons: bit 0 left, bit 1 right - which is
    and dl, 0x03                ; already mou_report's numbering
    call mou_report
.eoi:
    mov al, 0x20
    out 0xA0, al                ; the SLAVE first, then the master: EOI the
    out 0x20, al                ; master alone and the slave never raises
    pop es                      ; another line as long as the machine runs
    pop ds
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    iret

section .bss
ps2_phase   resb 1              ; 0, 1, 2 - which byte of the packet is next
ps2_b0      resb 1
ps2_b1      resb 1
ps2_live    resb 1              ; an aux device answered and IRQ12 is hooked

section .text
%endif
