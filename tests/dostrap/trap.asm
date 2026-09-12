; DOSTRAP.COM - log every INT 21h under a REAL DOS, in os8088's own trace
; format (SPEC.md 96.22.1). OURS, MIT with the rest of the tree.
;
; WHY THIS EXISTS. A DOS program that behaves differently under this box and
; under real DOS is not debuggable from one side: our trace says what we were
; asked and what we answered, and both look right. What is missing is what
; DOS answers to the SAME questions, and the only place that exists is on a
; machine running DOS. So this hooks INT 21h there and writes a TRACE.LOG in
; the identical layout, and the two files diff line for line.
;
;   DOSTRAP            install, then run the program under test
;   DOSTRAP /D         write TRACE.LOG from the ring and stay installed
;
; It logs AX BX CX DX on the way in and AX/CF on the way out, 16 bytes an
; entry, and filters the console writers exactly as the box does - a
; hundred-character message is a hundred entries of noise standing where the
; calls that caused it should be.
    org 0x100
    cpu 8086

NENT    equ 256                     ; entries, 4KB. IT KEEPS THE FIRST ONES AND
                                    ; STOPS: this exists to find where two runs
                                    ; DIVERGE, and divergence is early - a ring
                                    ; that wrapped would throw away the only
                                    ; part that matters and keep the steady
                                    ; state, which is the same on both sides

start:
    mov si, 0x81                    ; the command tail
.sw:
    lodsb
    cmp al, 13
    je .install
    cmp al, '/'
    jne .sw
    lodsb
    or al, 0x20
    cmp al, 'd'
    jne .sw
    jmp dump

.install:
    mov ax, 0x3521                  ; the old handler, kept for the chain
    int 0x21
    mov [old21], bx
    mov [old21+2], es
    mov ax, es
    or ax, bx
    jz .nodos

    mov dx, new21
    mov ax, 0x2521
    int 0x21

    mov si, s_on
    call puts
    mov dx, resident_end            ; ...and stay, keeping the ring
    add dx, 15
    mov cl, 4
    shr dx, cl
    mov ax, 0x3100
    int 0x21
.nodos:
    mov si, s_nodos
    call puts
    mov ax, 0x4C01
    int 0x21

; --- the hook ---------------------------------------------------------------
new21:
    ; ARM ON THE EXEC, which is what makes the ring the PROGRAM's and not the
    ; shell's. COMMAND.COM spends hundreds of calls on its own prompt, so a
    ; ring that starts at install time is full of somebody else's work before
    ; the subject has been loaded. The first AH=4Bh after installation IS the
    ; subject being loaded.
    cmp byte [cs:armed], 0
    jne .live
    cmp ah, 0x4B
    jne .chain
    mov byte [cs:armed], 1
    jmp .chain
.live:
    cmp ah, 0x02
    je .chain
    cmp ah, 0x09
    je .chain
    cmp ah, 0x06
    je .chain

    cmp word [cs:total], NENT
    jae .chain                      ; full: the first NENT are the answer
    push si
    push ax
    mov si, [cs:wr]
    add si, ring
    mov [cs:here], si
    pop ax
    push ax
    mov [cs:si], ax
    mov [cs:si+2], bx
    mov [cs:si+4], cx
    mov [cs:si+6], dx
    mov word [cs:si+8], 0xFFFF
    mov word [cs:si+10], 0xFFFF
    mov word [cs:si+12], 0xFFFF
    mov word [cs:si+14], 0xFFFF
    add word [cs:wr], 16
    inc word [cs:total]
    pop ax
    pop si

    pushf
    call far [cs:old21]
    pushf                           ; ...the ANSWER's flags, banked across the
    push si                         ; logging below
    push ax
    mov si, [cs:here]
    mov [cs:si+8], ax
    mov [cs:si+12], bx              ; ES:BX IS THE ANSWER to AH=35h, 48h and
    mov ax, es                      ; 2Fh, and AX is not - a ring that logs
    mov [cs:si+14], ax              ; only AX is silent about all three
    mov word [cs:si+10], 0
    pushf                           ; ...still the far call's: every store
    pop ax                          ; above is a MOV, which sets no flag
    test al, 1                      ; CF is bit 0 of the flags word
    jz .noc
    mov word [cs:si+10], 1
.noc:
    pop ax
    pop si
    popf
    retf 2                          ; ...discarding the caller's pushed flags

.chain:
    jmp far [cs:old21]

; --- the dumper -------------------------------------------------------------
dump:
    mov ah, 0x3C                    ; create TRACE.LOG, replacing any
    xor cx, cx
    mov dx, s_file
    int 0x21
    jc .noopen
    mov [fh], ax

    mov di, line
    mov si, s_hdr
    call cat
    mov ax, [total]
    call hex4
    mov al, '/'
    stosb
    mov ax, [wr]
    call hex4
    call eol
    call flush

    mov cx, [total]
    cmp cx, NENT
    jbe .short
    mov cx, NENT
.short:
    xor bx, bx                      ; ...always from the first entry
    jcxz .done
.ent:
    push cx
    mov di, line
    mov ax, [bx+ring]
    call hex4
    mov al, ' '
    stosb
    mov ax, [bx+ring+2]
    call hex4
    mov al, ' '
    stosb
    mov ax, [bx+ring+4]
    call hex4
    mov al, ' '
    stosb
    mov ax, [bx+ring+6]
    call hex4
    mov al, '>'
    stosb
    mov ax, [bx+ring+8]
    call hex4
    mov al, '/'
    stosb
    mov ax, [bx+ring+10]
    call hex4
    mov al, '/'
    stosb
    mov ax, [bx+ring+14]
    call hex4
    mov al, ':'
    stosb
    mov ax, [bx+ring+12]
    call hex4
    call eol
    call flush
    add bx, 16
    pop cx
    loop .ent
.done:
    mov bx, [fh]
    mov ah, 0x3E
    int 0x21
    mov si, s_wrote
    call puts
    mov ax, 0x4C00
    int 0x21
.noopen:
    mov si, s_nofile
    call puts
    mov ax, 0x4C01
    int 0x21

; --- helpers ----------------------------------------------------------------
cat:
    lodsb
    or al, al
    jz .o
    stosb
    jmp short cat
.o:
    ret
eol:
    mov al, 13
    stosb
    mov al, 10
    stosb
    ret
flush:
    push ax
    push bx
    push cx
    push dx
    mov cx, di
    sub cx, line
    mov dx, line
    mov bx, [fh]
    mov ah, 0x40
    int 0x21
    pop dx
    pop cx
    pop bx
    pop ax
    ret
hexd:
    add al, '0'
    cmp al, '9'
    jbe .o
    add al, 7
.o:
    ret
hex2:
    push ax
    push ax
    shr al, 1
    shr al, 1
    shr al, 1
    shr al, 1
    call hexd
    stosb
    pop ax
    and al, 0x0F
    call hexd
    stosb
    pop ax
    ret
hex4:
    push ax
    mov al, ah
    call hex2
    pop ax
    call hex2
    ret
puts:
    lodsb
    or al, al
    jz .o
    push si
    mov dl, al
    mov ah, 0x02
    int 0x21
    pop si
    jmp short puts
.o:
    ret

s_on:     db 'DOSTRAP installed - it arms on the next EXEC', 13, 10, 0
s_nodos:  db 'no INT 21h to hook', 13, 10, 0
s_wrote:  db 'TRACE.LOG written', 13, 10, 0
s_nofile: db 'could not create TRACE.LOG', 13, 10, 0
s_file:   db 'TRACE.LOG', 0
s_hdr:    db 'os8088 DOS INT 21h trace', 13, 10
          db 'AX BX CX DX>AXout/CF/ES:BX ', 0

armed:    db 0                      ; 0 until the EXEC that loads the subject
old21:    dd 0
here:     dw 0
wr:       dw 0
total:    dw 0
fh:       dw 0
line:     times 128 db 0             ; ...a whole line: the header plus its
                                    ; two numbers is 60, and an entry 41
ring:     times NENT * 16 db 0
resident_end:
