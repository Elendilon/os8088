; KBHOLD.COM - DOES A KEY ARRIVING ON A FULL BIOS BUFFER MAKE THE ROM BEEP?
; OURS, MIT with the rest of the tree.
;
; The reported failure (SPEC.md 96.50) is: hold a direction key in a game busy
; drawing a frame, the BIOS key buffer fills, and the ROM's `int 09h` beeps -
; for longer than the typematic interval, so the next repeat overflows DURING
; the beep and it never stops. os8088's kernel has SPEC.md 9.8's guard in front
; of the ROM for exactly this; `kern_dos` did not.
;
; THE BUFFER IS FORGED FROM IN HERE, and that is the whole reason this is a DOS
; program rather than four host-side pokes. A forge written from the host is
; DRAINED before the test key lands - the guest is sitting in `int 16h` and
; empties it between the write and the keystroke, which is what an early
; attempt measured and misread as "both arms survived". Nothing drains it while
; this program is spinning, because this program never reads a key.
;
; THE OBSERVABLE IS THE SPEAKER AND NOT THE BUFFER, and that is not a detour:
; with the guard the tail winds back and the key is stored, without it the ROM
; drops the key - and BOTH leave a full buffer. The difference is audible and
; nothing else. So this samples port 61h's timer-2 gate and speaker-data bits
; across the window and counts how many samples had either set. A gated tone
; holds them for its whole duration and a toggled one has them on about half
; the samples; both count.
;
; It prints the int 09h VECTOR first, because that is the one-line answer to
; "which machine am I on": F000:xxxx is the ROM's own handler and anything else
; is a guard in front of it.
    org 0x100
    cpu 8086

BDA         equ 0x40
KB_HEAD     equ 0x1A
KB_TAIL     equ 0x1C
KB_BUFB     equ 0x1E
KB_BUFE     equ 0x3E
ROUNDS      equ 10              ; outer turns of a 65,536-sample inner loop.
                                ; ~35 cycles a sample on a 4.77MHz 8088 is
                                ; ~0.48s a round, so this is ~5 seconds - and
                                ; it is a COUNT rather than a clock read on
                                ; purpose: the window has to be the same
                                ; amount of WORK on both arms of the A/B, and
                                ; a beep that stops the machine dead would
                                ; make a tick-bounded window measure itself.
                                ; The first draft was 24,000 samples, which is
                                ; 0.1s: the program finished and the bracket
                                ; tore down between two 0.25s polls, so the
                                ; harness only ever saw the desktop behind it

start:
    mov ah, 0x1A                ; our own DTA (tests/dostrap/dosref.asm's
    mov dx, dta                 ; reason), before anything else
    int 0x21

    ; --- 1. WHOSE int 09h IS IT? --------------------------------------------
    mov si, s_vec
    call puts
    xor ax, ax
    mov es, ax
    mov ax, [es:0x09*4+2]
    call hex4
    mov al, ':'
    call putc
    mov ax, [es:0x09*4]
    call hex4
    call eol

    ; --- 2. FORGE A FULL BUFFER ---------------------------------------------
    ; Full, by the BIOS's own definition, is tail + 2 == head. head = 1Eh with
    ; tail = 3Ch is that: the next slot the ROM would fill wraps to 1Eh, which
    ; is the head.
    mov ax, BDA
    mov es, ax
    mov di, KB_BUFB
    mov cx, (KB_BUFE - KB_BUFB) / 2
    mov ax, 0x1E41              ; 'A' with a plausible scancode, sixteen times
    cld
    rep stosw
    cli
    mov word [es:KB_HEAD], KB_BUFB
    mov word [es:KB_TAIL], KB_BUFE - 2
    sti
    mov si, s_forged
    call puts
    call kbstate

    ; --- 2a. PROVE THE INSTRUMENT FIRST -------------------------------------
    ; **A ZERO NOBODY CAN VALIDATE IS NOT A MEASUREMENT.** If port 61h's bit 1
    ; never reads back set on this machine - a BIOS that drives the speaker
    ; some other way, an emulator that does not reflect the write - then the
    ; silent arm and the beeping arm both count zero and the probe reports the
    ; defect as fixed on every build for ever. So: sound one deliberately,
    ; count it, and print the count. A control of zero means the line below it
    ; says nothing at all.
    mov al, 0xB6                ; timer 2, square wave
    out 0x43, al
    mov al, 0x00
    out 0x42, al
    mov al, 0x08                ; ~2.3kHz; the pitch is irrelevant, the GATE
    out 0x42, al                ; is what this is about
    in al, 0x61
    mov [spk_sv], al
    or al, 0x03                 ; gate the timer AND let it reach the cone
    out 0x61, al
    xor ax, ax
    mov [spk], ax
    mov [spk+2], ax
    mov byte [rounds], 1
    call watch
    mov al, [spk_sv]            ; ...and off again, exactly as it was
    out 0x61, al
    mov si, s_ctl
    call puts
    mov ax, [spk+2]
    call hex4
    mov ax, [spk]
    call hex4
    call eol

    ; --- 3. ...AND WATCH THE SPEAKER WHILE KEYS ARRIVE ----------------------
    xor ax, ax
    mov [spk], ax
    mov [spk+2], ax
    mov byte [rounds], ROUNDS
    call watch
    mov si, s_spk
    call puts
    mov ax, [spk+2]
    call hex4
    mov ax, [spk]
    call hex4
    call eol
    mov si, s_after
    call puts
    call kbstate

    ; --- 4. leave the machine as we found it --------------------------------
    mov ax, BDA
    mov es, ax
    cli
    mov word [es:KB_HEAD], KB_BUFB
    mov word [es:KB_TAIL], KB_BUFB
    sti
    mov si, s_done
    call puts
    ; **AND WAIT, so the text screen outlives the bracket.** A program that
    ; prints and exits takes its screen with it: the box tears the bracket
    ; down and the harness, polling four times a second, reads the graphical
    ; desktop behind it and reports that nothing was printed.
.hold:
    mov ah, 0x00
    int 0x16
    cmp al, 'x'
    jne .hold
    mov ax, 0x4C00
    int 0x21

; --- watch - sample port 61h [rounds] x 65,536 times, counting the speaker --
; Clobbers AX and CX; [spk] is the 32-bit tally and the caller zeroes it.
;
; A COUNT AND NOT A CLOCK, deliberately: the window has to be the same amount
; of WORK on both arms of the A/B, and a beep that stops the machine dead
; would make a tick-bounded window measure itself.
watch:
.round:
    xor cx, cx                  ; 0 is 65,536 turns of `loop`
.w:
    in al, 0x61
    test al, 0x02               ; **BIT 1, THE SPEAKER DATA LINE, AND NOT BIT 0
                                ; AS WELL.** Bit 0 is the timer-2 GATE and a PC
                                ; leaves it set whether or not anything is
                                ; sounding, so `test al, 3` matched every
                                ; sample of a SILENT machine - 655,360 of
                                ; 655,360, which reads exactly like a beep that
                                ; never stops.
    jz .next
    add word [spk], 1
    adc word [spk+2], 0
.next:
    loop .w
    dec byte [rounds]
    jnz .round
    ret

; --- kbstate - "head=xxxx tail=xxxx" ----------------------------------------
kbstate:
    push ax
    push es
    mov ax, BDA
    mov es, ax
    mov si, s_head
    call puts
    mov ax, [es:KB_HEAD]
    call hex4
    mov si, s_tail
    call puts
    mov ax, [es:KB_TAIL]
    call hex4
    call eol
    pop es
    pop ax
    ret

; --- helpers (tests/dostrap/dosref.asm's, and through statics for its reason)
hex4:
    push ax
    mov al, ah
    call hex2
    pop ax
    call hex2
    ret
hex2:
    push ax
    push cx
    push ax
    mov cl, 4
    shr al, cl
    call hexd
    pop ax
    and al, 0x0F
    call hexd
    pop cx
    pop ax
    ret
hexd:
    add al, '0'
    cmp al, '9'
    jbe putc
    add al, 7
putc:
    push ax
    push bx
    push cx
    push dx
    push si
    push di
    push bp
    mov dl, al
    mov ah, 0x02
    int 0x21
    pop bp
    pop di
    pop si
    pop dx
    pop cx
    pop bx
    pop ax
    ret
eol:
    mov al, 13
    call putc
    mov al, 10
    jmp short putc
puts:
    push ax
.l:
    mov al, [si]
    inc si
    or al, al
    jz .o
    call putc
    jmp short .l
.o:
    pop ax
    ret

s_vec:    db 'KBHOLD int09=', 0
s_forged: db 'forged FULL   ', 0
s_after:  db 'after  watch  ', 0
s_head:   db 'head=', 0
s_tail:   db ' tail=', 0
s_ctl:    db 'speaker CONTROL     =', 0
s_spk:    db 'speaker-on samples  =', 0
s_done:   db 'KBHOLD READY', 13, 10, 0
spk:      dd 0
spk_sv:   db 0
rounds:   db 0
dta:      times 128 db 0
